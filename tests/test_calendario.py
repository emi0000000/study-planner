"""Pruebas de la conexión con Google Calendar.

No se conectan a Google de verdad: usan un "Google de mentira" (HttpMockSequence, de la
propia librería de Google) que devuelve respuestas preparadas y apunta qué se le pidió.
Si las librerías de Google no están instaladas, estas pruebas se saltan.
"""

# json para preparar las respuestas falsas y leer lo enviado.
import json
# sys para añadir la carpeta de la app a la ruta de módulos.
import sys
# tempfile para la prueba de credenciales que faltan.
import tempfile
# unittest es el sistema de pruebas de Python.
import unittest
# Herramientas de fechas.
from datetime import date, datetime
# Path para manejar rutas.
from pathlib import Path
# patch cambia temporalmente un valor durante la prueba; Mock crea objetos de mentira.
from unittest.mock import Mock, patch
# Para leer los parámetros de una dirección web.
from urllib.parse import parse_qs, urlparse

# Añadimos la carpeta de la app para poder importar sus módulos.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Módulos de la app.
import almacen  # noqa: E402
import calendario_google  # noqa: E402
from repartidor import Sesion  # noqa: E402

# Intentamos cargar las librerías de Google.
try:
    # Constructor del servicio.
    from googleapiclient.discovery import build
    # "Google de mentira".
    from googleapiclient.http import HttpMockSequence

    # Están instaladas.
    HAY_GOOGLE = True
# Si no están instaladas...
except ImportError:
    # ...lo apuntamos para saltar las pruebas que las necesitan.
    HAY_GOOGLE = False


def plan_de_prueba():
    """Plan con dos sesiones de Matemáticas."""
    # Primera sesión: lunes 26/10 a las 18:00.
    s1 = Sesion("Matemáticas", 5, 25, datetime(2026, 10, 26, 18, 0), datetime(2026, 10, 26, 18, 25), 1, 2)
    # Segunda sesión: miércoles 28/10 a las 18:00.
    s2 = Sesion("Matemáticas", 5, 25, datetime(2026, 10, 28, 18, 0), datetime(2026, 10, 28, 18, 25), 2, 2)
    # Plan de lunes a domingo.
    return {"desde": date(2026, 10, 26), "hasta": date(2026, 11, 1), "sesiones": [s1, s2], "sin_lugar": []}


def respuesta(estado, contenido=None):
    """Prepara una respuesta falsa de Google con un código de estado y un JSON."""
    # Formato que espera HttpMockSequence: (cabeceras, cuerpo).
    return ({"status": str(estado)}, json.dumps(contenido) if contenido is not None else "")


if HAY_GOOGLE:

    class HttpGrabador(HttpMockSequence):
        """HttpMockSequence que además apunta cada petición recibida."""

        def __init__(self, respuestas):
            # Preparamos las respuestas en orden.
            super().__init__(respuestas)
            # Lista de (método, dirección, cuerpo) de cada petición.
            self.peticiones = []

        def request(self, uri, method="GET", body=None, headers=None, redirections=1, connection_type=None):
            # Apuntamos la petición.
            self.peticiones.append((method, uri, body))
            # Respondemos con la siguiente respuesta preparada.
            return super().request(uri, method, body, headers, redirections, connection_type)


def servicio_falso(*respuestas):
    """Crea un servicio de Calendar real que habla con el Google de mentira."""
    # Grabador con las respuestas.
    http = HttpGrabador(list(respuestas))
    # static_discovery usa la descripción de la API que viene dentro de la librería (sin internet).
    return build("calendar", "v3", http=http, static_discovery=True), http


class EventoDesdeSesion(unittest.TestCase):
    """Pruebas del formato de evento (no necesitan las librerías de Google)."""

    def test_formato_del_evento(self):
        # Convertimos la primera sesión del plan.
        evento = calendario_google.evento_desde_sesion(plan_de_prueba()["sesiones"][0], 5)
        # Título con número de sesión.
        self.assertEqual(evento["summary"], "Estudiar: Matemáticas (1/2)")
        # Aviso tipo notificación 5 minutos antes.
        self.assertEqual(evento["reminders"], {"useDefault": False, "overrides": [{"method": "popup", "minutes": 5}]})
        # Marca oculta de la app.
        self.assertEqual(evento["extendedProperties"]["private"], {"planificador_estudio": "si"})
        # Prioridad 5 = color rojo tomate.
        self.assertEqual(evento["colorId"], "11")
        # La hora lleva zona horaria (Google la necesita).
        inicio = datetime.fromisoformat(evento["start"]["dateTime"])
        # Una fecha con zona horaria tiene "utcoffset".
        self.assertIsNotNone(inicio.utcoffset())
        # Y sigue siendo las 18:00 locales.
        self.assertEqual(f"{inicio:%Y-%m-%d %H:%M}", "2026-10-26 18:00")


@unittest.skipUnless(HAY_GOOGLE, "faltan las librerías de Google (pip install -r requirements.txt)")
class SubirYBorrar(unittest.TestCase):
    """Pruebas de subir y borrar, con el Google de mentira."""

    def test_subir_crea_un_evento_por_sesion(self):
        # Google responde: no hay eventos previos, y luego confirma dos creaciones.
        servicio, http = servicio_falso(respuesta(200, {"items": []}), respuesta(200, {"id": "a"}), respuesta(200, {"id": "b"}))
        # Subimos el plan.
        creados, borrados = calendario_google.subir_plan(servicio, "primary", plan_de_prueba(), 5)
        # Se crearon 2 y no se borró nada.
        self.assertEqual((creados, borrados), (2, 0))
        # La primera petición fue buscar eventos de la app.
        metodo, uri, _ = http.peticiones[0]
        # Es una lectura (GET).
        self.assertEqual(metodo, "GET")
        # Filtra por nuestra marca oculta.
        self.assertEqual(parse_qs(urlparse(uri).query)["privateExtendedProperty"], ["planificador_estudio=si"])
        # Las dos siguientes fueron creaciones (POST).
        self.assertEqual([p[0] for p in http.peticiones[1:]], ["POST", "POST"])
        # El cuerpo enviado lleva el aviso al teléfono.
        enviado = json.loads(http.peticiones[1][2])
        # Comprobamos el aviso.
        self.assertEqual(enviado["reminders"]["overrides"], [{"method": "popup", "minutes": 5}])

    def test_no_duplica_si_ya_hay_sesiones(self):
        # Google responde que ya hay un evento de la app en esas fechas.
        servicio, http = servicio_falso(respuesta(200, {"items": [{"id": "viejo"}]}))
        # Sin --reemplazar debe detenerse con un mensaje.
        with self.assertRaisesRegex(almacen.ErrorPlanificador, "--reemplazar"):
            # Intento de subida.
            calendario_google.subir_plan(servicio, "primary", plan_de_prueba(), 5)
        # Solo se hizo la búsqueda: no se creó nada.
        self.assertEqual(len(http.peticiones), 1)

    def test_reemplazar_borra_y_crea(self):
        # Hay un evento viejo; se borra (204) y se crean dos nuevos.
        servicio, http = servicio_falso(
            respuesta(200, {"items": [{"id": "viejo"}]}), respuesta(204), respuesta(200, {"id": "a"}), respuesta(200, {"id": "b"})
        )
        # Subimos reemplazando.
        creados, borrados = calendario_google.subir_plan(servicio, "primary", plan_de_prueba(), 5, reemplazar=True)
        # 2 creados, 1 borrado.
        self.assertEqual((creados, borrados), (2, 1))
        # La segunda petición borró el evento viejo.
        self.assertEqual(http.peticiones[1][0], "DELETE")
        # Y apuntaba a su ID.
        self.assertTrue(urlparse(http.peticiones[1][1]).path.endswith("/events/viejo"))

    def test_borrar_ignora_eventos_ya_borrados(self):
        # Dos eventos: el primero ya no existía (410), el segundo se borra bien (204).
        servicio, _ = servicio_falso(respuesta(200, {"items": [{"id": "x"}, {"id": "y"}]}), respuesta(410), respuesta(204))
        # Limpiamos la semana.
        borrados = calendario_google.quitar_plan(servicio, "primary", date(2026, 10, 26), date(2026, 11, 1))
        # Cuenta los dos sin fallar.
        self.assertEqual(borrados, 2)

    def test_lee_todas_las_paginas(self):
        # Google devuelve los resultados en dos páginas.
        servicio, http = servicio_falso(
            respuesta(200, {"items": [{"id": "a"}], "nextPageToken": "p2"}), respuesta(200, {"items": [{"id": "b"}]})
        )
        # Buscamos.
        eventos = calendario_google.buscar_eventos_propios(servicio, "primary", date(2026, 10, 26), date(2026, 11, 1))
        # Encontró los de ambas páginas.
        self.assertEqual([e["id"] for e in eventos], ["a", "b"])
        # La segunda petición pidió la página 2.
        self.assertEqual(parse_qs(urlparse(http.peticiones[1][1]).query)["pageToken"], ["p2"])

    def test_error_de_google_se_explica(self):
        # Google responde 403 (por ejemplo, la API no está habilitada).
        servicio, _ = servicio_falso(({"status": "403"}, json.dumps({"error": {"message": "Calendar API has not been used"}})))
        # Debe convertirse en un error para el usuario con el código.
        with self.assertRaisesRegex(almacen.ErrorPlanificador, "403"):
            # Intento de subida.
            calendario_google.subir_plan(servicio, "primary", plan_de_prueba(), 5)

    def test_sin_credentials_json_explica_que_falta(self):
        # Carpeta vacía: no hay credentials.json ni token.json.
        with tempfile.TemporaryDirectory() as carpeta:
            # Debe pedir el archivo con un mensaje claro.
            with self.assertRaisesRegex(almacen.ErrorPlanificador, "credentials.json"):
                # Intento de conexión.
                calendario_google.conectar(Path(carpeta) / "credentials.json", Path(carpeta) / "token.json")

    def test_avisa_si_credentials_tiene_otro_nombre(self):
        # Carpeta temporal para la prueba.
        with tempfile.TemporaryDirectory() as carpeta:
            # Ruta de la carpeta.
            base = Path(carpeta)
            # El archivo quedó con la extensión repetida, como pasa en Windows.
            (base / "credentials.json.json").write_text("{}", encoding="utf-8")
            # El mensaje dice qué archivo renombrar.
            with self.assertRaisesRegex(almacen.ErrorPlanificador, "credentials.json.json"):
                # Intento de conexión.
                calendario_google.conectar(base / "credentials.json", base / "token.json")


@unittest.skipUnless(HAY_GOOGLE, "faltan las librerías de Google (pip install -r requirements.txt)")
class InicioDeSesion(unittest.TestCase):
    """Qué pasa si el permiso en el navegador no sale bien (sin abrir el navegador de verdad)."""

    def conectar_con_error(self, error):
        """Simula que el inicio de sesión falla con `error` y devuelve el mensaje para el usuario."""
        # Flujo de inicio de sesión de Google.
        from google_auth_oauthlib.flow import InstalledAppFlow

        # Flujo de mentira cuyo navegador "falla" con el error indicado.
        self.flujo = Mock()
        # El error.
        self.flujo.run_local_server.side_effect = error
        # Carpeta temporal con un credentials.json cualquiera y sin token.json.
        with tempfile.TemporaryDirectory() as carpeta:
            # Ruta de la carpeta.
            base = Path(carpeta)
            # Archivo de credenciales (su contenido no importa: el flujo es de mentira).
            (base / "credentials.json").write_text("{}", encoding="utf-8")
            # Usamos el flujo de mentira.
            with patch.object(InstalledAppFlow, "from_client_secrets_file", return_value=self.flujo):
                # Debe dar un error para el usuario.
                with self.assertRaises(almacen.ErrorPlanificador) as contexto:
                    # Intento de conexión.
                    calendario_google.conectar(base / "credentials.json", base / "token.json")
        # Devolvemos el mensaje.
        return str(contexto.exception)

    def test_si_no_llega_el_permiso_a_tiempo(self):
        # Google avisa del tiempo agotado con un AttributeError.
        self.assertIn("a tiempo", self.conectar_con_error(AttributeError("Timed out")))
        # Y se le pidió esperar como mucho 5 minutos.
        self.assertEqual(self.flujo.run_local_server.call_args.kwargs["timeout_seconds"], 300)

    def test_si_se_cancela_el_permiso(self):
        # Error que da Google al pulsar "Cancelar".
        from oauthlib.oauth2.rfc6749.errors import AccessDeniedError

        # El mensaje explica qué pasó.
        self.assertIn("access_denied", self.conectar_con_error(AccessDeniedError()))

    def test_si_no_se_marca_la_casilla_del_permiso(self):
        # Así avisa la librería cuando falta el permiso de Calendar.
        self.assertIn("marca la casilla", self.conectar_con_error(Warning("Scope has changed")))


# Permite ejecutar este archivo directamente.
if __name__ == "__main__":
    # Lanza las pruebas.
    unittest.main()

"""Pruebas del asistente: sus herramientas y la conversación con Claude o Gemini.

No se conectan a internet: las respuestas de la IA son de mentira.
Las pruebas de cada IA se saltan si su librería no está instalada.
"""

# json para leer los resultados de las herramientas.
import json
# os para probar la clave en una variable de entorno.
import os
# sys para añadir la carpeta de la app a la ruta de módulos.
import sys
# tempfile crea carpetas temporales para no tocar tus datos reales.
import tempfile
# unittest es el sistema de pruebas de Python.
import unittest
# Herramientas de fechas.
from datetime import date, datetime, time, timedelta
# Path para manejar rutas.
from pathlib import Path
# SimpleNamespace crea objetos sencillos con atributos (para imitar respuestas).
from types import SimpleNamespace
# patch cambia temporalmente un valor durante la prueba; Mock crea objetos de mentira.
from unittest.mock import Mock, patch

# Añadimos la carpeta de la app para poder importar sus módulos.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Módulos de la app.
import almacen  # noqa: E402
import asistente  # noqa: E402
import progreso  # noqa: E402

# ¿Está la librería de Claude?
try:
    # Librería de Anthropic.
    import anthropic
    # Librería de conexiones que usa.
    import httpx2
# Si no está, se saltan sus pruebas.
except ImportError:
    # Sin librería.
    anthropic = None

# ¿Está la librería de Gemini?
try:
    # Librería de Google.
    from google import genai
    # Sus errores.
    from google.genai import errors as errores_gemini
    # Sus tipos de datos.
    from google.genai import types as tipos_gemini
# Si no está, se saltan sus pruebas.
except ImportError:
    # Sin librería.
    genai = None

# Próximo lunes (para que el plan de prueba nunca quede en el pasado).
LUNES = date.today() + timedelta(days=7 - date.today().weekday())


class ConDatosDePrueba(unittest.TestCase):
    """Base: todos los archivos de la app van a una carpeta temporal."""

    def setUp(self):
        # Carpeta temporal.
        self.carpeta = tempfile.TemporaryDirectory()
        # Ruta como Path.
        base = Path(self.carpeta.name)
        # Archivos que redirigimos.
        archivos = {"ARCHIVO_CONFIG": "config.json", "ARCHIVO_TEMAS": "temas.json", "ARCHIVO_PLAN": "plan.json",
                    "ARCHIVO_REGISTRO": "registro.json", "ARCHIVO_METAS": "metas.json",
                    "ARCHIVO_MEMORIA": "memoria.json", "ARCHIVO_CLAVES": "claves.json"}
        # Un parche por archivo.
        for atributo, nombre in archivos.items():
            # Activamos el parche.
            patch.object(almacen, atributo, base / "datos" / nombre).start()
        # Variables de entorno sin claves (para no usar las de quien ejecuta las pruebas).
        patch.dict(os.environ, {v: "" for vs in asistente.VARIABLES_CLAVE.values() for v in vs}).start()

    def tearDown(self):
        # Quitamos todos los parches.
        patch.stopall()
        # Borramos la carpeta temporal.
        self.carpeta.cleanup()

    def herramienta(self, herramienta, /, **argumentos):
        """Ejecuta una herramienta y comprueba que no dio error. Devuelve su resultado."""
        # Ejecutamos.
        resultado, es_error, _resumen = asistente.ejecutar(herramienta, argumentos)
        # No debe ser un error.
        self.assertFalse(es_error, resultado)
        # Resultado.
        return resultado


class Herramientas(ConDatosDePrueba):
    """Las herramientas cambian los datos como deben."""

    def test_temas_plan_y_marcar_sesion(self):
        # Agregamos dos temas.
        self.herramienta("guardar_tema", nombre="Química", prioridad=4, minutos_semana=100)
        # Segundo tema.
        self.herramienta("guardar_tema", nombre="Inglés", prioridad=2, minutos_semana=50)
        # Están guardados.
        self.assertEqual([t["nombre"] for t in almacen.cargar_temas()], ["Química", "Inglés"])
        # Generamos el plan desde el próximo lunes.
        plan = json.loads(self.herramienta("generar_plan", desde=LUNES.isoformat()))
        # Empieza ese lunes.
        self.assertEqual(plan["desde"], LUNES.isoformat())
        # Marcamos como hecha la sesión de Química del lunes (escrita sin tilde).
        self.herramienta("marcar_sesion", fecha=LUNES.isoformat(), tema="quimica", estado="hecha")
        # ver_estado lo refleja (mirando desde ese lunes por la noche, para que la sesión ya haya pasado).
        resultado, es_error, _resumen = asistente.ejecutar("ver_estado", {}, ahora=datetime.combine(LUNES, time(23, 0)))
        # Sin error.
        self.assertFalse(es_error)
        # Estado como diccionario.
        estado = json.loads(resultado)
        # Primera línea del lunes.
        lunes = next(iter(estado["plan"]["dias"].values()))
        # La de Química está hecha.
        self.assertTrue(any("Química" in linea and linea.endswith(": hecha") for linea in lunes))
        # El progreso cuenta una hecha.
        self.assertEqual(estado["progreso_14_dias"]["hechas"], 1)
        # Quitamos un tema.
        self.herramienta("quitar_tema", nombre="ingles")
        # Ya no está.
        self.assertEqual([t["nombre"] for t in almacen.cargar_temas()], ["Química"])

    def test_metas(self):
        # Tema para la meta.
        self.herramienta("guardar_tema", nombre="Química", prioridad=3, minutos_semana=100)
        # Meta con tema y fecha.
        meta = json.loads(self.herramienta("agregar_meta", texto="Examen", tema="Química", fecha="2026-11-13"))
        # Número 1.
        self.assertEqual(meta["id"], 1)
        # La marcamos como cumplida.
        self.herramienta("marcar_meta", id=1, cumplida=True)
        # Lo está.
        self.assertTrue(almacen.cargar_metas()[0]["cumplida"])
        # La quitamos.
        self.herramienta("quitar_meta", id=1)
        # No queda ninguna.
        self.assertEqual(almacen.cargar_metas(), [])

    def test_horario_maximo_y_notas(self):
        # Dejamos de estudiar los sábados.
        self.herramienta("cambiar_horario", dia="sabado", hora="")
        # Ya no están en el horario.
        self.assertNotIn("sabado", almacen.cargar_config()["horario"])
        # El domingo a las 11:00.
        self.herramienta("cambiar_horario", dia="domingo", hora="11:00")
        # Está.
        self.assertEqual(almacen.cargar_config()["horario"]["domingo"], "11:00")
        # Máximo diario de 90 minutos.
        self.herramienta("cambiar_maximo_diario", minutos=90)
        # Guardado.
        self.assertEqual(almacen.cargar_config()["maximo_minutos_por_dia"], 90)
        # Guardamos una nota.
        self.herramienta("guardar_nota", texto="Prefiere estudiar por la mañana")
        # Está guardada con número 1.
        self.assertEqual(almacen.cargar_memoria()[0]["id"], 1)
        # La borramos.
        self.herramienta("borrar_nota", id=1)
        # Ya no está.
        self.assertEqual(almacen.cargar_memoria(), [])

    def test_errores_se_devuelven_a_la_ia(self):
        # Casos que deben dar error (sin romper nada).
        casos = [
            # Prioridad fuera de rango.
            ("guardar_tema", {"nombre": "Física", "prioridad": 9, "minutos_semana": 60}),
            # Hora imposible.
            ("cambiar_horario", {"dia": "lunes", "hora": "25:00"}),
            # Día inventado.
            ("cambiar_horario", {"dia": "lunez", "hora": "18:00"}),
            # Máximo negativo.
            ("cambiar_maximo_diario", {"minutos": -5}),
            # Marcar sin plan.
            ("marcar_sesion", {"fecha": "2026-10-26", "tema": "Química", "estado": "hecha"}),
            # Herramienta inventada.
            ("borrar_todo", {}),
        ]
        # Probamos cada uno.
        for nombre, argumentos in casos:
            # Ejecutamos.
            resultado, es_error, _resumen = asistente.ejecutar(nombre, argumentos)
            # Es un error, con explicación.
            self.assertTrue(es_error, nombre)
            # Empieza por "Error:".
            self.assertTrue(resultado.startswith("Error:"), resultado)
        # Quitar todos los días deja el horario vacío: también es un error.
        for dia in list(almacen.cargar_config()["horario"])[:-1]:
            # Quitamos el día.
            self.herramienta("cambiar_horario", dia=dia, hora="")
        # El último no se puede quitar.
        ultimo = next(iter(almacen.cargar_config()["horario"]))
        # Error.
        self.assertTrue(asistente.ejecutar("cambiar_horario", {"dia": ultimo, "hora": ""})[1])

    def test_sin_clave_explica_como_ponerla(self):
        # Sin clave guardada ni en variables de entorno.
        with self.assertRaisesRegex(almacen.ErrorPlanificador, "Falta la clave de Claude"):
            # Intento.
            asistente.crear_conversacion()
        # La clave se guarda y se borra.
        almacen.guardar_clave("gemini", "  clave-de-prueba  ")
        # Guardada sin espacios.
        self.assertEqual(asistente.clave_de("gemini"), "clave-de-prueba")
        # La borramos.
        almacen.guardar_clave("gemini", "")
        # Ya no está.
        self.assertEqual(asistente.clave_de("gemini"), "")


def bloque(tipo, **datos):
    """Imita un bloque de respuesta de Claude."""
    # Objeto con el tipo y los datos.
    return SimpleNamespace(type=tipo, **datos)


@unittest.skipUnless(anthropic, "falta la librería de Claude (pip install -r requirements.txt)")
class ConversacionConClaude(ConDatosDePrueba):
    """La conversación con Claude usa las herramientas y traduce los errores."""

    def conversacion(self, respuestas):
        """Conversación con un Claude de mentira que da estas respuestas en orden."""
        # Cliente de mentira.
        self.cliente = Mock()
        # Sus respuestas.
        self.cliente.beta.messages.create.side_effect = respuestas
        # La librería devuelve nuestro cliente.
        with patch.object(anthropic, "Anthropic", return_value=self.cliente):
            # Conversación.
            return asistente.ConversacionClaude("clave", "claude-opus-5-5")

    def test_usa_herramientas_y_responde(self):
        # Claude pide guardar un tema y luego responde.
        conversacion = self.conversacion([
            # Primera respuesta: usar una herramienta.
            SimpleNamespace(stop_reason="tool_use", content=[
                bloque("thinking", thinking=""),
                bloque("tool_use", id="t1", name="guardar_tema",
                       input={"nombre": "Física", "prioridad": 3, "minutos_semana": 60})]),
            # Segunda respuesta: el texto final.
            SimpleNamespace(stop_reason="end_turn", content=[bloque("text", text="Listo, agregué Física.")]),
        ])
        # Lo que se le muestra al usuario mientras trabaja.
        avisos = []
        # Enviamos el mensaje.
        respuesta = conversacion.enviar("Agrega Física, 60 min", avisar=avisos.append)
        # Respuesta final.
        self.assertEqual(respuesta, "Listo, agregué Física.")
        # El tema se guardó de verdad.
        self.assertEqual(almacen.cargar_temas()[0]["nombre"], "Física")
        # Se avisó al usuario.
        self.assertIn("Física", avisos[0])
        # Segunda petición: lleva el resultado de la herramienta.
        segunda = self.cliente.beta.messages.create.call_args_list[1].kwargs
        # Tercer mensaje (usuario, asistente, resultados...): el resultado de la herramienta.
        resultado = segunda["messages"][2]["content"][0]
        # Corresponde a la llamada t1 y no es un error.
        self.assertEqual((resultado["type"], resultado["tool_use_id"], resultado["is_error"]), ("tool_result", "t1", False))
        # La respuesta anterior se reenvió completa (con su bloque de "pensamiento").
        self.assertEqual(segunda["messages"][1]["content"][0].type, "thinking")
        # Con respaldo automático, esfuerzo medio y caché.
        self.assertEqual((segunda["fallbacks"], segunda["betas"], segunda["output_config"], segunda["cache_control"]),
                         ("default", ["server-side-fallback-2026-07-01"], {"effort": "medium"}, {"type": "ephemeral"}))
        # El mensaje del usuario lleva la fecha y hora.
        self.assertTrue(segunda["messages"][0]["content"].startswith("["))

    def test_rechazo_deja_el_historial_en_orden(self):
        # Claude rechaza, y después responde normal.
        conversacion = self.conversacion([
            # Rechazo.
            SimpleNamespace(stop_reason="refusal", content=[]),
            # Respuesta normal.
            SimpleNamespace(stop_reason="end_turn", content=[bloque("text", text="Hola")]),
        ])
        # El rechazo se explica.
        self.assertIn("No puedo ayudar", conversacion.enviar("algo"))
        # La siguiente funciona.
        self.assertEqual(conversacion.enviar("hola"), "Hola")
        # El historial alterna usuario y asistente.
        roles = [m["role"] for m in self.cliente.beta.messages.create.call_args.kwargs["messages"]]
        # Usuario, asistente, usuario.
        self.assertEqual(roles[:3], ["user", "assistant", "user"])

    def test_errores_claros(self):
        # Petición de mentira para construir los errores.
        peticion = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        # Error y parte del mensaje esperado.
        casos = [
            (anthropic.AuthenticationError("invalid x-api-key", response=httpx2.Response(401, request=peticion),
                                           body=None), "no es válida"),
            (anthropic.BadRequestError("Your credit balance is too low", response=httpx2.Response(400, request=peticion),
                                       body=None), "no tiene saldo"),
            (anthropic.RateLimitError("rate limit", response=httpx2.Response(429, request=peticion), body=None),
             "demasiadas peticiones"),
            (anthropic.APIConnectionError(request=peticion), "conexión a internet"),
        ]
        # Probamos cada uno.
        for error, esperado in casos:
            # Conversación que falla con ese error.
            conversacion = self.conversacion([error])
            # El mensaje es claro.
            with self.assertRaisesRegex(almacen.ErrorPlanificador, esperado):
                # Intento.
                conversacion.enviar("hola")


def respuesta_gemini(*partes):
    """Imita una respuesta de Gemini con estas partes."""
    # Respuesta real de la librería, con una sola propuesta.
    return tipos_gemini.GenerateContentResponse(candidates=[tipos_gemini.Candidate(
        content=tipos_gemini.Content(role="model", parts=list(partes)))])


@unittest.skipUnless(genai, "falta la librería de Gemini (pip install -r requirements.txt)")
class ConversacionConGemini(ConDatosDePrueba):
    """La conversación con Gemini usa las herramientas y traduce los errores."""

    def conversacion(self, respuestas):
        """Conversación con un Gemini de mentira que da estas respuestas en orden."""
        # Cliente de mentira.
        self.cliente = Mock()
        # Sus respuestas.
        self.cliente.models.generate_content.side_effect = respuestas
        # La librería devuelve nuestro cliente.
        with patch.object(genai, "Client", return_value=self.cliente):
            # Conversación.
            return asistente.ConversacionGemini("clave", "gemini-3.8-flash")

    def test_usa_herramientas_y_responde(self):
        # Primero hacen falta temas y un plan.
        self.herramienta("guardar_tema", nombre="Química", prioridad=4, minutos_semana=100)
        # Plan desde el próximo lunes.
        self.herramienta("generar_plan", desde=LUNES.isoformat())
        # Gemini pide marcar una sesión y luego responde.
        conversacion = self.conversacion([
            # Llamada a una herramienta.
            respuesta_gemini(tipos_gemini.Part(function_call=tipos_gemini.FunctionCall(
                id="c1", name="marcar_sesion", args={"fecha": LUNES.isoformat(), "tema": "Química", "estado": "no_hecha"}))),
            # Texto final (más una parte de "pensamiento", que no se muestra).
            respuesta_gemini(tipos_gemini.Part(text="pensando…", thought=True), tipos_gemini.Part(text="Anotado.")),
        ])
        # Enviamos el mensaje.
        self.assertEqual(conversacion.enviar("Hoy no pude con química"), "Anotado.")
        # La sesión quedó marcada como no hecha.
        registro = almacen.cargar_registro()
        # Una sesión marcada, no hecha.
        self.assertEqual([e["estado"] for e in registro["sesiones"].values()], ["no_hecha"])
        # La segunda petición lleva la respuesta de la herramienta, con el mismo id.
        contenidos = self.cliente.models.generate_content.call_args_list[1].kwargs["contents"]
        # Tercer contenido (usuario, modelo, resultados...): la respuesta de la herramienta.
        respuesta_herramienta = contenidos[2].parts[0].function_response
        # Mismo id y nombre, sin error.
        self.assertEqual((respuesta_herramienta.id, respuesta_herramienta.name), ("c1", "marcar_sesion"))
        # Y el resultado.
        self.assertIn("resultado", respuesta_herramienta.response)
        # Gemini no ejecuta herramientas por su cuenta y piensa poco.
        config = self.cliente.models.generate_content.call_args.kwargs["config"]
        # Comprobamos.
        self.assertTrue(config.automatic_function_calling.disable)

    def test_errores_claros(self):
        # Error de red de mentira (mismo nombre que el de la librería de conexiones).
        class ConnectError(Exception):
            pass

        # Error y parte del mensaje esperado.
        casos = [
            (errores_gemini.ClientError(400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid "
                                                         "API key.", "status": "INVALID_ARGUMENT"}}), "no es válida"),
            (errores_gemini.ClientError(429, {"error": {"code": 429, "message": "Quota exceeded",
                                                         "status": "RESOURCE_EXHAUSTED"}}), "límite gratuito"),
            (errores_gemini.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}}),
             "saturado"),
            (ConnectError("sin red"), "conexión a internet"),
        ]
        # Probamos cada uno.
        for error, esperado in casos:
            # Conversación que falla con ese error.
            conversacion = self.conversacion([error])
            # El mensaje es claro.
            with self.assertRaisesRegex(almacen.ErrorPlanificador, esperado):
                # Intento.
                conversacion.enviar("hola")


@unittest.skipUnless(anthropic and genai, "faltan las librerías de Claude o Gemini (pip install -r requirements.txt)")
class PeticionesReales(ConDatosDePrueba):
    """Con las librerías de verdad (sin internet: la conexión se responde aquí), las peticiones salen bien formadas."""

    def test_claude(self):
        # Peticiones recibidas (cabeceras y cuerpo).
        peticiones = []
        # Respuestas: primero usa una herramienta (con "pensamiento" firmado), luego responde.
        respuestas = [
            {"id": "m1", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "stop_reason": "tool_use",
             "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
             "content": [{"type": "thinking", "thinking": "", "signature": "firma"},
                         {"type": "tool_use", "id": "t1", "name": "guardar_nota", "input": {"texto": "Le cuesta química"}}]},
            {"id": "m2", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "stop_reason": "end_turn",
             "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
             "content": [{"type": "text", "text": "Apuntado."}]},
        ]

        def responder(peticion):
            # Guardamos la petición.
            peticiones.append((peticion.headers, json.loads(peticion.content)))
            # Respuesta que toca.
            return httpx2.Response(200, json=respuestas[len(peticiones) - 1])

        # Cliente real, pero con la conexión de mentira.
        original = anthropic.Anthropic
        # Mismo cliente, con nuestra conexión.
        with patch.object(anthropic, "Anthropic", side_effect=lambda **o: original(
                http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(responder)), **o)):
            # Conversación.
            conversacion = asistente.ConversacionClaude("clave", "claude-opus-5-5")
        # Respuesta final.
        self.assertEqual(conversacion.enviar("Me cuesta química"), "Apuntado.")
        # Segunda petición.
        cabeceras, cuerpo = peticiones[1]
        # Lleva el respaldo automático.
        self.assertEqual((cabeceras["anthropic-beta"], cuerpo["fallbacks"]), ("server-side-fallback-2026-07-01", "default"))
        # El "pensamiento" se reenvía intacto, con su firma.
        self.assertEqual(cuerpo["messages"][1]["content"][0], {"type": "thinking", "thinking": "", "signature": "firma"})
        # Y el resultado de la herramienta, enlazado a su llamada.
        self.assertEqual(cuerpo["messages"][2]["content"][0]["tool_use_id"], "t1")
        # La nota se guardó.
        self.assertEqual(almacen.cargar_memoria()[0]["texto"], "Le cuesta química")

    def test_gemini(self):
        # Librería de conexiones que usa Gemini.
        try:
            # La habitual.
            import httpx
        # O la nueva.
        except ImportError:
            # Mismo nombre.
            import httpx2 as httpx
        # Cuerpos de las peticiones recibidas.
        peticiones = []
        # Respuestas: primero usa una herramienta (con firma de razonamiento), luego responde.
        respuestas = [
            {"candidates": [{"content": {"role": "model", "parts": [
                {"functionCall": {"id": "c1", "name": "guardar_nota", "args": {"texto": "Estudia por la mañana"}},
                 "thoughtSignature": "ZmlybWE="}]}}]},
            {"candidates": [{"content": {"role": "model", "parts": [{"text": "Apuntado."}]}}]},
        ]

        def responder(peticion):
            # Guardamos la petición.
            peticiones.append(json.loads(peticion.content))
            # Respuesta que toca.
            return httpx.Response(200, json=respuestas[len(peticiones) - 1])

        # Cliente real, pero con la conexión de mentira.
        original = genai.Client
        # Mismo cliente, con nuestra conexión.
        with patch.object(genai, "Client", side_effect=lambda **o: original(http_options=tipos_gemini.HttpOptions(
                httpx_client=httpx.Client(transport=httpx.MockTransport(responder))), **o)):
            # Conversación.
            conversacion = asistente.ConversacionGemini("clave", "gemini-3.8-flash")
        # Respuesta final.
        self.assertEqual(conversacion.enviar("Estudio mejor por la mañana"), "Apuntado.")
        # Contenidos de la segunda petición.
        contenidos = peticiones[1]["contents"]
        # La firma de razonamiento se reenvía.
        self.assertEqual(contenidos[1]["parts"][0]["thoughtSignature"], "ZmlybWE=")
        # Y la respuesta de la herramienta, con su id.
        self.assertEqual(contenidos[2]["parts"][0]["functionResponse"]["id"], "c1")
        # Las 13 herramientas van declaradas.
        self.assertEqual(len(peticiones[1]["tools"][0]["functionDeclarations"]), len(asistente.HERRAMIENTAS))


class Estado(ConDatosDePrueba):
    """ver_estado incluye todo lo necesario, aunque no haya nada guardado."""

    def test_estado_vacio(self):
        # Sin datos.
        estado = asistente.estado_actual(datetime(2026, 10, 25, 19, 5))
        # Fecha en palabras.
        self.assertEqual(estado["ahora"], "domingo 25/10/2026, 19:05")
        # Sin plan.
        self.assertIsNone(estado["plan"])
        # Sin temas, metas ni notas.
        self.assertEqual((estado["temas"], estado["metas"], estado["notas_guardadas"]), ([], [], []))
        # Racha cero.
        self.assertEqual(estado["progreso_14_dias"]["racha"], 0)
        # Se puede convertir a texto para la IA.
        self.assertTrue(json.dumps(estado))
        # Y progreso entiende el plan vacío.
        self.assertIsNone(progreso.plan_guardado())


# Permite ejecutar este archivo directamente.
if __name__ == "__main__":
    # Lanza las pruebas.
    unittest.main()

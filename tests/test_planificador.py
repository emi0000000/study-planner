"""Pruebas de los comandos de punta a punta (sin conectar con Google)."""

# copy duplica la configuración por defecto para modificarla.
import copy
# io.StringIO captura lo que el programa imprime.
import io
# sys para añadir la carpeta de la app a la ruta de módulos.
import sys
# tempfile crea carpetas temporales para no tocar tus datos reales.
import tempfile
# unittest es el sistema de pruebas de Python.
import unittest
# redirect_stdout desvía lo que se imprime hacia nuestro StringIO.
from contextlib import redirect_stdout
# Herramientas de fechas.
from datetime import date, timedelta
# Path para manejar rutas.
from pathlib import Path
# patch cambia temporalmente un valor durante la prueba.
from unittest.mock import patch

# Añadimos la carpeta de la app para poder importar sus módulos.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Módulos de la app.
import almacen  # noqa: E402
import planificador  # noqa: E402
import repartidor  # noqa: E402


class Comandos(unittest.TestCase):
    """Ejecuta los comandos como si se escribieran en la terminal."""

    def setUp(self):
        # Carpeta temporal para los datos de la prueba.
        self.carpeta = tempfile.TemporaryDirectory()
        # Ruta de la carpeta como Path.
        base = Path(self.carpeta.name)
        # Redirigimos los tres archivos de la app a la carpeta temporal.
        self.parches = [
            # Configuración.
            patch.object(almacen, "ARCHIVO_CONFIG", base / "config.json"),
            # Temas.
            patch.object(almacen, "ARCHIVO_TEMAS", base / "datos" / "temas.json"),
            # Plan.
            patch.object(almacen, "ARCHIVO_PLAN", base / "datos" / "plan.json"),
        ]
        # Activamos los parches.
        for parche in self.parches:
            # Activación.
            parche.start()

    def tearDown(self):
        # Desactivamos los parches.
        for parche in self.parches:
            # Desactivación.
            parche.stop()
        # Borramos la carpeta temporal.
        self.carpeta.cleanup()

    def ejecutar(self, *argumentos):
        """Ejecuta el programa con esos argumentos y devuelve (código, texto impreso)."""
        # Lugar donde se acumula lo impreso.
        salida = io.StringIO()
        # Desviamos la salida mientras corre el programa.
        with redirect_stdout(salida):
            # Ejecutamos.
            codigo = planificador.main(list(argumentos))
        # Devolvemos el resultado.
        return codigo, salida.getvalue()

    def test_flujo_completo_sin_google(self):
        # Próximo lunes (para que el plan nunca quede en el pasado).
        lunes = date.today() + timedelta(days=7 - date.today().weekday())
        # Agregamos dos temas.
        self.assertEqual(self.ejecutar("agregar", "Matemáticas", "-p", "5", "-m", "120")[0], 0)
        # Segundo tema.
        self.assertEqual(self.ejecutar("agregar", "Inglés", "-p", "2", "-m", "50")[0], 0)
        # La lista muestra ambos.
        codigo, texto = self.ejecutar("temas")
        # Sin error.
        self.assertEqual(codigo, 0)
        # Aparece el total.
        self.assertIn("Total: 170 min", texto)
        # Generamos el plan desde el lunes.
        codigo, texto = self.ejecutar("generar", "--desde", lunes.isoformat())
        # Sin error.
        self.assertEqual(codigo, 0)
        # El resumen confirma que entró todo.
        self.assertIn("Matemáticas: 120 de 120 min", texto)
        # El plan quedó guardado en disco.
        self.assertTrue(almacen.ARCHIVO_PLAN.exists())
        # El lunes tiene la primera sesión de Matemáticas a las 18:00.
        codigo, texto = self.ejecutar("hoy", "--fecha", lunes.isoformat())
        # Comprobamos.
        self.assertIn("18:00-18:25  Matemáticas (1/", texto)
        # La simulación lista 7 eventos (5 de Matemáticas + 2 de Inglés), sin conectar con Google.
        codigo, texto = self.ejecutar("subir", "--simular")
        # Sin error.
        self.assertEqual(codigo, 0)
        # Cantidad correcta.
        self.assertIn("se crearían 7 eventos", texto)

    def test_generar_sin_temas_da_error(self):
        # Sin temas, generar falla con código 1 (y un mensaje en la salida de errores).
        with redirect_stdout(io.StringIO()), patch("sys.stderr", io.StringIO()) as errores:
            # Ejecutamos.
            codigo = planificador.main(["generar"])
        # Código de error.
        self.assertEqual(codigo, 1)
        # Mensaje útil.
        self.assertIn("No hay temas", errores.getvalue())

    def test_limpiar_revisa_las_fechas_antes_de_conectar(self):
        # Casos que deben fallar sin llegar a conectar con Google.
        casos = [
            # --hasta sin --desde.
            (["limpiar", "--hasta", "2026-11-01"], "indica también --desde"),
            # --hasta antes que --desde.
            (["limpiar", "--desde", "2026-11-05", "--hasta", "2026-11-01"], "es anterior"),
        ]
        # Probamos cada caso.
        for argumentos, mensaje in casos:
            # Si llegara a conectar, la prueba fallaría con este parche.
            with patch.object(planificador.calendario_google, "conectar", side_effect=AssertionError("no debe conectar")):
                # Capturamos la salida de errores.
                with redirect_stdout(io.StringIO()), patch("sys.stderr", io.StringIO()) as errores:
                    # Ejecutamos.
                    codigo = planificador.main(argumentos)
            # Código de error.
            self.assertEqual(codigo, 1, argumentos)
            # Mensaje útil.
            self.assertIn(mensaje, errores.getvalue())


class FuncionesCompartidas(unittest.TestCase):
    """Funciones que usan tanto los comandos como la ventana."""

    def test_resumen_por_tema(self):
        # Configuración: solo lunes, con 50 minutos como máximo.
        config = copy.deepcopy(almacen.CONFIG_POR_DEFECTO)
        # Cambios.
        config.update(horario={"lunes": "18:00"}, maximo_minutos_por_dia=50)
        # Dos temas que no caben enteros.
        temas = [{"nombre": "A", "prioridad": 5, "minutos_semana": 50}, {"nombre": "B", "prioridad": 1, "minutos_semana": 25}]
        # Plan.
        plan = repartidor.generar_plan(temas, config, date(2026, 10, 26))
        # A entra entero; B se queda fuera.
        self.assertEqual(planificador.resumen_por_tema(plan), [("A", 50, 50), ("B", 0, 25)])

    def test_capacidad_semanal(self):
        # Configuración por defecto: 6 días de 120 minutos.
        config = copy.deepcopy(almacen.CONFIG_POR_DEFECTO)
        # 720 minutos.
        self.assertEqual(planificador.capacidad_semanal(config), 720)
        # Un día que empieza a las 23:00 solo aporta 60 minutos.
        config["horario"] = {"lunes": "23:00"}
        # 60 minutos.
        self.assertEqual(planificador.capacidad_semanal(config), 60)
        # Sin máximo diario no hay cifra.
        config["maximo_minutos_por_dia"] = 0
        # Ninguna.
        self.assertIsNone(planificador.capacidad_semanal(config))


# Permite ejecutar este archivo directamente.
if __name__ == "__main__":
    # Lanza las pruebas.
    unittest.main()

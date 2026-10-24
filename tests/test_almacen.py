"""Pruebas de la lectura/escritura de temas y configuración."""

# json para escribir archivos de configuración de prueba.
import json
# sys para añadir la carpeta de la app a la ruta de módulos.
import sys
# tempfile crea carpetas temporales que se borran solas al terminar.
import tempfile
# unittest es el sistema de pruebas de Python.
import unittest
# Path para manejar rutas.
from pathlib import Path

# Añadimos la carpeta de la app para poder importar sus módulos.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Módulo que vamos a probar.
import almacen  # noqa: E402


class Configuracion(unittest.TestCase):
    """Pruebas de config.json."""

    def setUp(self):
        # Carpeta temporal para cada prueba.
        self.carpeta = tempfile.TemporaryDirectory()
        # Ruta del config.json de prueba.
        self.ruta = Path(self.carpeta.name) / "config.json"

    def tearDown(self):
        # Borramos la carpeta temporal.
        self.carpeta.cleanup()

    def escribir(self, **cambios):
        """Escribe un config.json con los cambios indicados."""
        # Guardamos solo las claves indicadas (el resto se toma por defecto).
        self.ruta.write_text(json.dumps(cambios), encoding="utf-8")

    def test_si_no_existe_se_crea_con_valores_por_defecto(self):
        # Cargamos sin que exista el archivo.
        config = almacen.cargar_config(self.ruta)
        # Ahora el archivo existe.
        self.assertTrue(self.ruta.exists())
        # Y tiene los valores por defecto.
        self.assertEqual(config, almacen.CONFIG_POR_DEFECTO)

    def test_acepta_dias_con_tilde_y_mayusculas(self):
        # Escribimos días con tilde y mayúscula.
        self.escribir(horario={"Miércoles": "19:30", "SÁBADO": "09:00"})
        # Se normalizan a minúsculas sin tilde.
        self.assertEqual(almacen.cargar_config(self.ruta)["horario"], {"miercoles": "19:30", "sabado": "09:00"})

    def test_rechaza_hora_invalida(self):
        # 25:00 no existe.
        self.escribir(horario={"lunes": "25:00"})
        # Debe dar un error para el usuario.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento de carga.
            almacen.cargar_config(self.ruta)

    def test_rechaza_dia_inexistente(self):
        # "lunez" no es un día.
        self.escribir(horario={"lunez": "18:00"})
        # Debe dar error.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento de carga.
            almacen.cargar_config(self.ruta)

    def test_rechaza_minima_mayor_que_la_sesion(self):
        # Mínimo de 30 con sesiones de 25 no tiene sentido.
        self.escribir(duracion_sesion=25, duracion_minima=30)
        # Debe dar error.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento de carga.
            almacen.cargar_config(self.ruta)

    def test_rechaza_true_como_numero(self):
        # true no es un número de minutos.
        self.escribir(descanso_corto=True)
        # Debe dar error.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento de carga.
            almacen.cargar_config(self.ruta)

    def test_json_mal_escrito_da_error_claro(self):
        # Falta cerrar la llave.
        self.ruta.write_text('{"duracion_sesion": 25', encoding="utf-8")
        # Debe dar un error que menciona la línea.
        with self.assertRaisesRegex(almacen.ErrorPlanificador, "línea"):
            # Intento de carga.
            almacen.cargar_config(self.ruta)


class Temas(unittest.TestCase):
    """Pruebas de agregar y quitar temas."""

    def test_agregar_y_actualizar_sin_importar_tildes(self):
        # Empezamos sin temas.
        temas = []
        # Primer alta: es nuevo.
        self.assertTrue(almacen.agregar_tema(temas, "Matemáticas", 5, 120))
        # Mismo tema escrito distinto: se actualiza, no se duplica.
        self.assertFalse(almacen.agregar_tema(temas, "matematicas", 4, 90))
        # Sigue habiendo un solo tema...
        self.assertEqual(len(temas), 1)
        # ...con los datos nuevos.
        self.assertEqual(temas[0], {"nombre": "matematicas", "prioridad": 4, "minutos_semana": 90})

    def test_rechaza_datos_invalidos(self):
        # Prioridad fuera de rango.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento con prioridad 9.
            almacen.agregar_tema([], "Física", 9, 60)
        # Minutos no positivos.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento con 0 minutos.
            almacen.agregar_tema([], "Física", 3, 0)
        # Nombre vacío.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento con solo espacios.
            almacen.agregar_tema([], "   ", 3, 60)

    def test_quitar(self):
        # Lista con un tema.
        temas = [{"nombre": "Física", "prioridad": 3, "minutos_semana": 60}]
        # Se quita aunque se escriba sin tilde.
        almacen.quitar_tema(temas, "fisica")
        # La lista queda vacía.
        self.assertEqual(temas, [])
        # Quitar algo que no existe da error.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento.
            almacen.quitar_tema(temas, "Física")


# Permite ejecutar este archivo directamente.
if __name__ == "__main__":
    # Lanza las pruebas.
    unittest.main()

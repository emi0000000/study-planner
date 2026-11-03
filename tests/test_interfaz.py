"""Pruebas de la ventana: la abren sin mostrarla y pulsan sus botones como lo haría una persona.

No se conectan a Google: la conexión se reemplaza por una de mentira.
Si tkinter no está instalado o no hay pantalla (por ejemplo, en un servidor), estas pruebas se saltan.
"""

# sys para añadir la carpeta de la app a la ruta de módulos.
import sys
# tempfile crea carpetas temporales para no tocar tus datos reales.
import tempfile
# time para esperar a las tareas en segundo plano.
import time
# unittest es el sistema de pruebas de Python.
import unittest
# Herramientas de fechas.
from datetime import date, timedelta
# Path para manejar rutas.
from pathlib import Path
# patch cambia temporalmente un valor durante la prueba; Mock crea objetos de mentira.
from unittest.mock import Mock, patch

# Añadimos la carpeta de la app para poder importar sus módulos.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Módulos de la app.
import almacen  # noqa: E402
import calendario_google  # noqa: E402
import progreso  # noqa: E402

# Intentamos cargar tkinter.
try:
    # Librería de ventanas.
    import tkinter
# Algunos Python (por ejemplo, en servidores Linux) vienen sin ella.
except ImportError:
    # Sin tkinter.
    tkinter = None


def hay_pantalla():
    """True si se puede abrir una ventana (hay tkinter y hay pantalla)."""
    # Sin tkinter no hay ventana.
    if tkinter is None:
        # No se puede.
        return False
    # Probamos a abrir una ventana vacía.
    try:
        # Ventana de prueba.
        raiz = tkinter.Tk()
        # La cerramos enseguida.
        raiz.destroy()
    # Sin pantalla, tkinter da este error.
    except tkinter.TclError:
        # No se puede.
        return False
    # Sí se puede.
    return True


# Lo comprobamos una sola vez.
HAY_PANTALLA = hay_pantalla()
# La ventana solo se importa si se puede usar.
if HAY_PANTALLA:
    # Módulo de la ventana.
    import interfaz


def proximo_lunes():
    """Fecha del próximo lunes (así el plan de prueba nunca queda en el pasado)."""
    # Días que faltan hasta el lunes que viene.
    return date.today() + timedelta(days=7 - date.today().weekday())


def textos(control):
    """Devuelve todos los textos que muestra un control y sus hijos (para buscar mensajes)."""
    # Aquí juntamos los textos.
    encontrados = []
    # Intentamos leer el texto del propio control.
    try:
        # Texto (si el control tiene).
        encontrados.append(str(control.cget("text")))
    # Algunos controles no tienen texto.
    except tkinter.TclError:
        # Seguimos.
        pass
    # Repetimos con cada hijo.
    for hijo in control.winfo_children():
        # Sumamos sus textos.
        encontrados.extend(textos(hijo))
    # Devolvemos todos.
    return encontrados


class BaseVentana(unittest.TestCase):
    """Base de las pruebas de la ventana: datos en una carpeta temporal y cuadros de mensaje de mentira."""

    def setUp(self):
        # Carpeta temporal para los datos de la prueba.
        self.carpeta = tempfile.TemporaryDirectory()
        # Ruta de la carpeta como Path.
        base = Path(self.carpeta.name)
        # Ruta del credentials.json de prueba (no existe al empezar).
        self.credenciales = base / "credentials.json"
        # Redirigimos los archivos de la app a la carpeta temporal y cambiamos los cuadros de mensaje.
        self.parches = [
            # Configuración.
            patch.object(almacen, "ARCHIVO_CONFIG", base / "config.json"),
            # Temas.
            patch.object(almacen, "ARCHIVO_TEMAS", base / "datos" / "temas.json"),
            # Plan.
            patch.object(almacen, "ARCHIVO_PLAN", base / "datos" / "plan.json"),
            # Sesiones hechas y no hechas.
            patch.object(almacen, "ARCHIVO_REGISTRO", base / "datos" / "registro.json"),
            # Metas.
            patch.object(almacen, "ARCHIVO_METAS", base / "datos" / "metas.json"),
            # Notas del asistente.
            patch.object(almacen, "ARCHIVO_MEMORIA", base / "datos" / "memoria.json"),
            # Claves del asistente.
            patch.object(almacen, "ARCHIVO_CLAVES", base / "datos" / "claves.json"),
            # La ventana cambia este texto: lo dejamos como estaba al terminar.
            patch.object(almacen, "COMO_GENERAR", almacen.COMO_GENERAR),
            # Archivo de credenciales.
            patch.object(calendario_google, "ARCHIVO_CREDENCIALES", self.credenciales),
            # Archivo del permiso guardado.
            patch.object(calendario_google, "ARCHIVO_TOKEN", base / "token.json"),
            # Carpeta donde se buscan credenciales con otro nombre.
            patch.object(calendario_google, "CARPETA_APP", base),
        ]
        # Activamos los parches.
        for parche in self.parches:
            # Activación.
            parche.start()
        # Cuadros de mensaje de mentira (los de verdad esperarían a que alguien pulse "Aceptar").
        self.mensajes = {nombre: patch.object(interfaz.messagebox, nombre).start()
                         for nombre in ("showinfo", "showerror", "askyesno")}
        # Por defecto, a las preguntas se responde "sí".
        self.mensajes["askyesno"].return_value = True
        # Abrimos la ventana.
        self.app = interfaz.Aplicacion()
        # La escondemos (no hace falta verla).
        self.app.withdraw()
        # Procesamos lo pendiente.
        self.app.update()

    def tearDown(self):
        # Cerramos la ventana.
        self.app.destroy()
        # Quitamos todos los parches.
        patch.stopall()
        # Borramos la carpeta temporal.
        self.carpeta.cleanup()

    def esperar(self, segundos=5):
        """Deja trabajar a la ventana hasta que termine la tarea en segundo plano."""
        # Hora límite.
        limite = time.monotonic() + segundos
        # Mientras haya algo a medias...
        while (self.app.ocupado or not self.app.cola.empty()) and time.monotonic() < limite:
            # ...procesamos eventos...
            self.app.update()
            # ...y esperamos un poco.
            time.sleep(0.02)
        # Últimos eventos.
        self.app.update()

    def agregar_tema(self, nombre, posicion_prioridad, minutos):
        """Rellena el formulario de Temas y pulsa «Guardar tema»."""
        # Pestaña de temas.
        temas = self.app.pestana_temas
        # Nombre.
        temas.nombre.set(nombre)
        # Prioridad (posición en la lista: 0 = 5 Muy alta ... 4 = 1 Muy baja).
        temas.prioridad.current(posicion_prioridad)
        # Minutos.
        temas.minutos.set(str(minutos))
        # Botón «Guardar tema».
        temas.guardar()

    def preparar_plan(self):
        """Agrega dos temas y genera el plan desde el próximo lunes."""
        # Tema de prioridad 5.
        self.agregar_tema("Matemáticas", 0, 120)
        # Tema de prioridad 2.
        self.agregar_tema("Inglés", 3, 50)
        # Botón «Generar plan».
        self.app.pestana_semana.generar(desde=proximo_lunes())



@unittest.skipUnless(HAY_PANTALLA, "no hay tkinter o no hay pantalla donde abrir la ventana")
class Ventana(BaseVentana):
    """Usa la ventana de principio a fin con datos de prueba."""

    def test_temas_plan_y_hoy(self):
        # Agregamos dos temas con el formulario.
        self.agregar_tema("Matemáticas", 0, 120)
        # Segundo tema.
        self.agregar_tema("Inglés", 3, 50)
        # Quedaron guardados con su prioridad.
        self.assertEqual({(t["nombre"], t["prioridad"]) for t in almacen.cargar_temas()}, {("Matemáticas", 5), ("Inglés", 2)})
        # La lista muestra los dos.
        self.assertEqual(len(self.app.pestana_temas.tabla.get_children()), 2)
        # La pestaña Semana avisa de que hay que generar el plan.
        self.assertIn("Generar plan", self.app.pestana_semana.aviso.cget("text"))
        # Generamos el plan.
        self.app.pestana_semana.generar(desde=proximo_lunes())
        # Se guardó en disco.
        self.assertTrue(almacen.ARCHIVO_PLAN.exists())
        # La ventana usa el plan nuevo.
        self.assertEqual(self.app.plan["desde"], proximo_lunes())
        # Ya no está desactualizado.
        self.assertFalse(self.app.plan_desactualizado)
        # La semana tiene 7 columnas.
        self.assertEqual(len(self.app.pestana_semana.cuadricula.winfo_children()), 7)
        # El resumen tiene una fila por tema.
        self.assertEqual(len(self.app.pestana_semana.tabla.get_children()), 2)
        # La pestaña Hoy se dibuja sin errores y muestra la fecha de hoy.
        self.app.pestana_hoy.refrescar()
        # Título con "Hoy, ...".
        self.assertTrue(self.app.pestana_hoy.titulo.cget("text").startswith("Hoy, "))
        # No hubo ningún error.
        self.mensajes["showerror"].assert_not_called()

    def test_barra_lateral(self):
        # El logo y los iconos se cargaron (están en la carpeta recursos/).
        self.assertIn("logo", self.app.imagenes)
        # Mostramos la ventana (los clics simulados solo llegan a ventanas visibles).
        self.app.deiconify()
        # Esperamos a que se dibuje.
        self.app.update()
        # Pulsamos «Metas» en la barra lateral.
        self.app.filas_lateral["metas"][3].event_generate("<Button-1>")
        # Procesamos el clic.
        self.app.update()
        # La sección elegida es Metas.
        self.assertIs(self.app.nametowidget(self.app.cuaderno.select()), self.app.pestana_metas)
        # Y se ve marcada: barrita ámbar y texto blanco.
        _fila, barrita, _icono, texto, _atributo = self.app.filas_lateral["metas"]
        # Comprobamos los colores.
        self.assertEqual((barrita.cget("background"), texto.cget("foreground")), (interfaz.COLOR_AMBAR, "white"))
        # Las demás no.
        self.assertEqual(self.app.filas_lateral["hoy"][1].cget("background"), interfaz.COLOR_LATERAL)
        # El atajo Ctrl+2 lleva a Semana (el teclado va al control que tiene el foco).
        self.app.pestana_metas.focus_force()
        # Pulsamos Ctrl+2.
        self.app.pestana_metas.event_generate("<Control-Key-2>")
        # Procesamos el atajo.
        self.app.update()
        # Ahora la elegida es Semana.
        self.assertIs(self.app.nametowidget(self.app.cuaderno.select()), self.app.pestana_semana)

    def test_quitar_tema(self):
        # Un tema.
        self.agregar_tema("Historia", 2, 60)
        # Lo elegimos en la lista.
        self.app.pestana_temas.tabla.selection_set("Historia")
        # Botón «Quitar el tema elegido» (askyesno responde "sí").
        self.app.pestana_temas.quitar()
        # Ya no está.
        self.assertEqual(almacen.cargar_temas(), [])

    def test_minutos_que_no_son_numero_dan_error(self):
        # Escribimos letras en los minutos.
        self.agregar_tema("Física", 2, "mucho")
        # Se mostró un error...
        self.mensajes["showerror"].assert_called_once()
        # ...y no se guardó nada.
        self.assertEqual(almacen.cargar_temas(), [])

    def test_ajustes_se_revisan_antes_de_guardar(self):
        # Pestaña de ajustes.
        ajustes = self.app.pestana_ajustes
        # Una hora que no existe el martes.
        ajustes.dias["martes"][1].set("25:00")
        # Botón «Guardar ajustes».
        ajustes.guardar()
        # Se mostró un error.
        self.mensajes["showerror"].assert_called_once()
        # Y config.json sigue con la hora de antes.
        self.assertEqual(almacen.cargar_config()["horario"]["martes"], "18:00")
        # Ahora una hora válida, sin estudiar los lunes y con 90 minutos de máximo.
        ajustes.dias["martes"][1].set("17:30")
        # Desmarcamos el lunes.
        ajustes.dias["lunes"][0].set(False)
        # Máximo diario.
        ajustes.valores["maximo_minutos_por_dia"].set("90")
        # Guardamos.
        ajustes.guardar()
        # Configuración guardada.
        config = almacen.cargar_config()
        # El martes empieza a las 17:30.
        self.assertEqual(config["horario"]["martes"], "17:30")
        # El lunes ya no está.
        self.assertNotIn("lunes", config["horario"])
        # El máximo cambió.
        self.assertEqual(config["maximo_minutos_por_dia"], 90)

    def test_ver_que_se_subiria(self):
        # Plan con dos temas.
        self.preparar_plan()
        # Botón «Ver qué se subiría».
        self.app.pestana_google.simular()
        # El registro muestra los eventos.
        self.assertIn("Estudiar: Matemáticas (1/", self.app.pestana_google.registro.get("1.0", "end"))

    def test_subir_pregunta_si_ya_hay_sesiones(self):
        # Plan con dos temas.
        self.preparar_plan()
        # Google de mentira: la conexión funciona.
        patch.object(calendario_google, "conectar", return_value=Mock()).start()
        # La primera subida encuentra 3 sesiones; la segunda (reemplazando) crea 7 y borra 3.
        subir = patch.object(calendario_google, "subir_plan", side_effect=[
            calendario_google.YaHaySesiones(3, proximo_lunes(), proximo_lunes() + timedelta(days=6)), (7, 3)]).start()
        # Botón «Subir al calendario».
        self.app.pestana_google.subir()
        # Esperamos a que termine.
        self.esperar()
        # Se preguntó si reemplazar.
        self.mensajes["askyesno"].assert_called_once()
        # La segunda subida fue reemplazando.
        self.assertTrue(subir.call_args.kwargs.get("reemplazar"))
        # Se avisó del resultado.
        self.assertIn("Se crearon 7 sesiones", self.mensajes["showinfo"].call_args.args[1])
        # Los botones vuelven a estar disponibles.
        self.assertFalse(self.app.ocupado)

    def test_error_de_google_se_muestra(self):
        # Plan con dos temas.
        self.preparar_plan()
        # La conexión falla con un error para el usuario.
        patch.object(calendario_google, "conectar",
                     side_effect=almacen.ErrorPlanificador("No encuentro credentials.json")).start()
        # Botón «Subir al calendario».
        self.app.pestana_google.subir()
        # Esperamos a que termine.
        self.esperar()
        # Se mostró el error.
        self.assertIn("credentials.json", self.mensajes["showerror"].call_args.args[1])
        # Los botones vuelven a estar disponibles.
        self.assertFalse(self.app.ocupado)

    def test_un_fallo_no_bloquea_las_siguientes_tareas(self):
        # Una tarea cuyo paso final falla de forma inesperada.
        self.app.en_segundo_plano(lambda: 1, lambda _resultado: 1 / 0)
        # Esperamos a que termine.
        self.esperar()
        # Se mostró el error inesperado.
        self.assertIn("Error inesperado", self.mensajes["showerror"].call_args.args[0])
        # Aquí apuntaremos el resultado de la tarea siguiente.
        resultados = []
        # Otra tarea normal.
        self.app.en_segundo_plano(lambda: 2, resultados.append)
        # Esperamos a que termine.
        self.esperar()
        # La ventana la atendió igual.
        self.assertEqual(resultados, [2])

    def test_estado_de_la_conexion(self):
        # Sin credentials.json, la comprobación dice que falta.
        self.app.pestana_google.refrescar()
        # Buscamos el texto.
        self.assertIn("Archivo credentials.json en la carpeta: falta", textos(self.app.pestana_google.lineas_estado))
        # Ponemos el archivo.
        self.credenciales.write_text("{}", encoding="utf-8")
        # «Comprobar otra vez».
        self.app.pestana_google.refrescar()
        # Ahora dice que está listo.
        self.assertIn("Archivo credentials.json en la carpeta: listo", textos(self.app.pestana_google.lineas_estado))

    def test_plan_danado_no_impide_abrir_la_ventana(self):
        # Escribimos un plan roto.
        almacen.guardar_plan({"roto": True})
        # Releemos todo.
        self.app.refrescar_todo()
        # La ventana sigue funcionando, sin plan.
        self.assertIsNone(self.app.plan)
        # Y avisa abajo de que está dañado.
        self.assertIn("dañado", self.app.barra_avisos.cget("text"))


@unittest.skipUnless(HAY_PANTALLA, "no hay tkinter o no hay pantalla donde abrir la ventana")
class VentanaAdaptativa(BaseVentana):
    """Marcar sesiones, metas, progreso y asistente desde la ventana."""

    def plan_con_hoy(self, dias_atras=0):
        """Plan que estudia todos los días a las 06:00 y empieza hace `dias_atras` días."""
        # Todos los días de la semana.
        almacen.guardar_config({**almacen.cargar_config(), "horario": {d: "06:00" for d in almacen.DIAS_SEMANA}})
        # Dos temas.
        self.agregar_tema("Matemáticas", 0, 175)
        # Segundo tema.
        self.agregar_tema("Química", 3, 175)
        # Plan.
        self.app.pestana_semana.generar(desde=date.today() - timedelta(days=dias_atras))

    def test_marcar_desde_hoy_y_ver_el_progreso(self):
        # Plan que incluye hoy.
        self.plan_con_hoy()
        # Primera sesión de hoy.
        sesion = next(s for s in self.app.plan["sesiones"] if s.inicio.date() == date.today())
        # La marcamos como hecha (como el botón «Hecha»).
        self.app.pestana_hoy.marcar(sesion, "hecha")
        # Quedó guardada.
        self.assertEqual(progreso.estado_de(almacen.cargar_registro(), sesion), "hecha")
        # La pestaña Metas cuenta una hecha.
        self.assertIn("1 sesiones hechas", self.app.pestana_metas.totales.cget("text"))
        # Pulsar otra vez quita la marca.
        self.app.pestana_hoy.marcar(sesion, None)
        # Ya no está marcada.
        self.assertIsNone(progreso.estado_de(almacen.cargar_registro(), sesion))

    def test_sesiones_atrasadas_y_plan_que_recupera(self):
        # Plan que empezó hace 3 días.
        self.plan_con_hoy(dias_atras=3)
        # Hoy muestra las de días anteriores sin marcar.
        self.app.pestana_hoy.refrescar()
        # Sección.
        self.assertTrue(any(t.startswith("Sin marcar de días anteriores") for t in textos(self.app.pestana_hoy.lista)))
        # Marcamos una de anteayer como no hecha.
        sesion = next(s for s in self.app.plan["sesiones"] if s.inicio.date() == date.today() - timedelta(days=2))
        # No hecha.
        self.app.pestana_hoy.marcar(sesion, "no_hecha")
        # Generamos un plan nuevo desde mañana.
        self.app.pestana_semana.generar(desde=date.today() + timedelta(days=1))
        # Tiene una sesión de recuperación.
        self.assertTrue(any(s.recuperacion for s in self.app.plan["sesiones"]))
        # Y la pestaña Semana explica cómo se adaptó.
        self.assertIn("Cómo se adaptó", self.app.pestana_semana.notas.cget("text"))

    def test_metas_desde_la_ventana(self):
        # Un tema para la meta.
        self.agregar_tema("Química", 3, 100)
        # Pestaña de metas.
        metas = self.app.pestana_metas
        # Escribimos una meta con tema y fecha.
        metas.texto.set("Examen de Química")
        # Tema (la lista empieza por «(ninguno)»).
        metas.tema.current(1)
        # Fecha.
        metas.fecha.set((date.today() + timedelta(days=5)).isoformat())
        # Botón «Guardar meta».
        metas.guardar()
        # Guardada con su tema.
        self.assertEqual([(m["texto"], m["tema"]) for m in almacen.cargar_metas()], [("Examen de Química", "Química")])
        # El plan conviene generarlo otra vez.
        self.assertTrue(self.app.plan_desactualizado)
        # La elegimos y la marcamos como cumplida.
        metas.tabla.selection_set("1")
        # Botón «Cumplida / pendiente».
        metas.alternar()
        # Cumplida.
        self.assertTrue(almacen.cargar_metas()[0]["cumplida"])
        # Botón «Quitar» (askyesno responde "sí").
        metas.quitar()
        # Ya no hay metas.
        self.assertEqual(almacen.cargar_metas(), [])
        # Una fecha mal escrita da error y no guarda nada.
        metas.texto.set("Otra meta")
        # Fecha imposible.
        metas.fecha.set("31/12")
        # Intento.
        metas.guardar()
        # Error mostrado.
        self.mensajes["showerror"].assert_called_once()
        # Nada guardado.
        self.assertEqual(almacen.cargar_metas(), [])

    def test_asistente_configurar_y_conversar(self):
        # Pestaña del asistente.
        pestana = self.app.pestana_asistente
        # Sin clave, se muestra la configuración.
        self.assertTrue(pestana.ajuste.winfo_manager())
        # Elegimos Gemini y pegamos una clave.
        pestana.proveedor.set("gemini")
        # Modelo de Gemini.
        pestana._al_cambiar_proveedor()
        # Clave.
        pestana.clave.set("clave-de-prueba")
        # Botón «Guardar y empezar».
        pestana.guardar_configuracion()
        # Guardada, elegida y de vuelta al chat.
        self.assertEqual((almacen.cargar_claves()["gemini"], almacen.cargar_config()["asistente"],
                          bool(pestana.chat.winfo_manager())), ("clave-de-prueba", "gemini", True))
        # Conversación de mentira: avisa de una acción y responde con formato Markdown.
        pestana.conversacion = Mock()
        # Respuesta.
        pestana.conversacion.enviar.side_effect = lambda texto, avisar: (avisar("Meta guardada: Examen."),
                                                                          "**Hecho.** Te lo apunto.")[1]
        # Escribimos y enviamos.
        pestana.entrada.insert(0, "Tengo examen el viernes")
        # Botón «Enviar».
        pestana.enviar()
        # Esperamos a la respuesta.
        self.esperar()
        # La conversación muestra el mensaje, la acción y la respuesta sin asteriscos.
        texto = pestana.texto.get("1.0", "end")
        # Comprobamos.
        self.assertIn("Tengo examen el viernes", texto)
        # Acción.
        self.assertIn("Meta guardada: Examen.", texto)
        # Respuesta.
        self.assertIn("Hecho. Te lo apunto.", texto)
        # Ya no pone «Pensando…».
        self.assertNotIn("Pensando", texto)
        # La casilla vuelve a estar disponible.
        self.assertNotIn("disabled", pestana.entrada.state())

    def test_asistente_sin_clave_explica_y_muestra_la_configuracion(self):
        # Pestaña del asistente.
        pestana = self.app.pestana_asistente
        # Volvemos al chat a la fuerza (sin clave).
        pestana.mostrar_chat()
        # Crear la conversación falla por falta de clave.
        patch.object(interfaz.asistente, "crear_conversacion",
                     side_effect=almacen.ErrorPlanificador("Falta la clave de Claude.")).start()
        # Escribimos y enviamos.
        pestana.entrada.insert(0, "hola")
        # Botón «Enviar».
        pestana.enviar()
        # Esperamos.
        self.esperar()
        # El error aparece en la conversación (sin ventanita).
        self.assertIn("No pude responder: Falta la clave de Claude.", pestana.texto.get("1.0", "end"))
        # Sin ventanita de error.
        self.mensajes["showerror"].assert_not_called()
        # Y se muestra la configuración.
        self.assertTrue(pestana.ajuste.winfo_manager())

    def test_ajustes_conserva_la_ia_elegida(self):
        # IA y modelo elegidos.
        almacen.guardar_config({**almacen.cargar_config(), "asistente": "gemini", "modelo_gemini": "gemini-prueba"})
        # Cargamos los ajustes en la pestaña.
        self.app.pestana_ajustes.refrescar()
        # Desactivamos la recuperación.
        self.app.pestana_ajustes.recuperar.set(False)
        # Botón «Guardar ajustes».
        self.app.pestana_ajustes.guardar()
        # Configuración guardada.
        config = almacen.cargar_config()
        # Se conserva la IA y se guardó la recuperación.
        self.assertEqual((config["asistente"], config["modelo_gemini"], config["recuperar_no_hechas"]),
                         ("gemini", "gemini-prueba", False))


# Permite ejecutar este archivo directamente.
if __name__ == "__main__":
    # Lanza las pruebas.
    unittest.main()

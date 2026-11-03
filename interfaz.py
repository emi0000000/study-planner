"""Ventana del planificador de estudio: hace lo mismo que los comandos, pero con botones.

Para abrirla:
  - en Windows, doble clic en «Abrir planificador.bat»;
  - o, en la terminal:  python interfaz.py

Usa tkinter, que viene incluido con Python: no hay que instalar nada más.
Los datos son los mismos que usan los comandos (config.json y la carpeta datos/),
así que puedes usar la ventana y la terminal indistintamente.
"""

# copy duplica los ajustes de fábrica para usarlos sin cambiarlos.
import copy
# functools ayuda a crear el "envoltorio" que muestra los errores en una ventanita.
import functools
# queue pasa mensajes desde las tareas en segundo plano a la ventana.
import queue
# sys para saber en qué sistema estamos (Windows, Mac, Linux).
import sys
# threading permite hablar con Google sin que la ventana se congele.
import threading
# traceback convierte un error inesperado en texto para mostrarlo.
import traceback
# webbrowser abre la guía de inicio en el navegador.
import webbrowser
# redirect_stdout desvía lo que imprimen las librerías de Google hacia el registro de la ventana.
from contextlib import redirect_stdout
# Herramientas de fechas.
from datetime import date, datetime, timedelta
# Path encuentra la carpeta de imágenes junto al programa.
from pathlib import Path

# tkinter es la librería de ventanas que trae Python.
import tkinter as tk
# Fuentes de letra.
from tkinter import font as tkfont
# Cuadros de mensaje (avisos y preguntas de sí o no).
from tkinter import messagebox
# Controles con mejor aspecto (botones, pestañas, listas...).
from tkinter import ttk

# Módulo que guarda y lee los datos (temas, configuración, plan).
import almacen
# Asistente con inteligencia artificial (Claude o Gemini).
import asistente
# Módulo que habla con Google Calendar.
import calendario_google
# El programa de comandos: reutilizamos sus funciones de ayuda.
import planificador
# Lo hecho, las metas y el plan adaptado.
import progreso
# Módulo que reparte el tiempo en sesiones.
import repartidor
# "150" -> "2 h 30 min" (la misma función que usan los comandos).
from progreso import minutos_a_texto

# Dirección de la guía de inicio en GitHub (se ve con formato en el navegador).
URL_GUIA = "https://github.com/emi0000000/study-planner/blob/main/GUIA_DE_INICIO.md"

# Color de fondo de la ventana.
COLOR_FONDO = "#f5f6fb"
# Color de fondo de las tarjetas.
COLOR_TARJETA = "#ffffff"
# Color del texto normal.
COLOR_TEXTO = "#1e2235"
# Color del texto secundario (explicaciones, fechas).
COLOR_SUAVE = "#6b7086"
# Color de los bordes.
COLOR_BORDE = "#e2e5ef"
# Índigo de los botones principales (el color del logo).
COLOR_ACENTO = "#4f46e5"
# Índigo más oscuro (botón principal al pasar el ratón).
COLOR_ACENTO_OSCURO = "#4338ca"
# Fondo índigo muy claro (filas seleccionadas, botones al pasar el ratón).
COLOR_ACENTO_SUAVE = "#eef2ff"
# Naranja oscuro para avisos.
COLOR_AVISO = "#b45309"
# Verde para lo que está bien.
COLOR_BIEN = "#15803d"
# Rojo para errores y para borrar.
COLOR_MAL = "#dc2626"
# Gris para las sesiones que ya pasaron.
COLOR_PASADO = "#f1f2f7"
# Barra lateral: fondo índigo oscuro.
COLOR_LATERAL = "#1e1b4b"
# Barra lateral: fila al pasar el ratón.
COLOR_LATERAL_ENCIMA = "#2b2770"
# Barra lateral: fila elegida.
COLOR_LATERAL_ACTIVO = "#3730a3"
# Barra lateral: texto normal.
COLOR_LATERAL_TEXTO = "#c7d2fe"
# Barra lateral: texto secundario.
COLOR_LATERAL_SUAVE = "#8b93d6"
# Ámbar (el reloj del logo): marca de la sección elegida.
COLOR_AMBAR = "#f59e0b"

# Carpeta con el logo y los iconos.
CARPETA_RECURSOS = Path(__file__).resolve().parent / "recursos"
# Secciones de la barra lateral: (nombre del icono, texto, atributo de la pestaña).
SECCIONES = [("hoy", "Hoy", "pestana_hoy"), ("semana", "Semana", "pestana_semana"),
             ("temas", "Temas", "pestana_temas"), ("metas", "Metas", "pestana_metas"),
             ("asistente", "Asistente", "pestana_asistente"), ("google", "Google Calendar", "pestana_google"),
             ("ajustes", "Ajustes", "pestana_ajustes")]

# Colores por prioridad: (color fuerte para la franja, color suave para el fondo). Son los de Google Calendar.
COLORES_PRIORIDAD = {
    # Prioridad 5: rojo tomate.
    5: ("#d50000", "#fde4e2"),
    # Prioridad 4: mandarina.
    4: ("#f4511e", "#fdebe2"),
    # Prioridad 3: amarillo plátano.
    3: ("#f6bf26", "#fdf5d6"),
    # Prioridad 2: verde salvia.
    2: ("#33b679", "#e2f4ea"),
    # Prioridad 1: gris grafito.
    1: ("#616161", "#ededed"),
}
# Texto que se muestra para cada prioridad en la lista desplegable.
NOMBRES_PRIORIDAD = {5: "5 · Muy alta", 4: "4 · Alta", 3: "3 · Media", 2: "2 · Baja", 1: "1 · Muy baja"}

# Días de la semana con tilde, para mostrarlos (lunes = 0).
DIAS_VISIBLES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
# Meses del año, para mostrar fechas largas.
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

# Ajustes numéricos de config.json: (clave, título, explicación, mínimo, máximo, paso de las flechitas).
CAMPOS_NUMERICOS = [
    # Duración de cada sesión.
    ("duracion_sesion", "Duración de cada sesión", "minutos", 1, 240, 5),
    # Sesión más corta.
    ("duracion_minima", "Sesión más corta", "minutos (si sobra menos, se suma a la última sesión)", 1, 240, 5),
    # Descanso corto.
    ("descanso_corto", "Descanso entre sesiones", "minutos", 0, 120, 5),
    # Descanso largo.
    ("descanso_largo", "Descanso largo", "minutos", 0, 240, 5),
    # Cada cuántas sesiones hay descanso largo.
    ("sesiones_antes_de_descanso_largo", "Descanso largo cada", "sesiones (0 = nunca)", 0, 20, 1),
    # Máximo diario.
    ("maximo_minutos_por_dia", "Máximo de estudio al día", "minutos, sin contar descansos (0 = sin límite)", 0, 1440, 15),
    # Aviso en el teléfono.
    ("aviso_minutos_antes", "Aviso en el teléfono", "minutos antes de cada sesión (0 = al empezar)", 0, 40320, 5),
]


def fecha_corta(fecha):
    """Devuelve algo como "martes 27/10"."""
    # Nombre del día y fecha con dos cifras.
    return f"{DIAS_VISIBLES[fecha.weekday()]} {fecha:%d/%m}"


def fecha_larga(fecha):
    """Devuelve algo como "martes 27 de octubre"."""
    # Nombre del día, número y mes.
    return f"{DIAS_VISIBLES[fecha.weekday()]} {fecha.day} de {MESES[fecha.month - 1]}"


def proxima_sesion(plan, ahora):
    """Devuelve la primera sesión del plan que todavía no terminó (o None si no queda ninguna)."""
    # Si no hay plan, no hay sesión.
    if plan is None:
        # Nada.
        return None
    # Las sesiones del plan ya están ordenadas por hora.
    return next((s for s in plan["sesiones"] if s.fin > ahora), None)


def con_avisos(metodo):
    """Envoltorio para los botones: si algo sale mal, lo explica en una ventanita en vez de fallar."""

    # functools.wraps conserva el nombre y la descripción del método original.
    @functools.wraps(metodo)
    def envoltura(self, *argumentos, **opciones):
        # Ejecutamos el método normalmente.
        try:
            # Resultado del método.
            return metodo(self, *argumentos, **opciones)
        # Errores pensados para el usuario: mostramos el mensaje tal cual.
        except almacen.ErrorPlanificador as error:
            # Ventanita de error.
            messagebox.showerror("No se pudo completar", str(error), parent=self.winfo_toplevel())
            # Sin resultado.
            return None

    # Devolvemos la versión envuelta.
    return envoltura


class EscritorCola:
    """Hace de "pantalla" para print(): manda cada línea a la ventana a través de la cola."""

    def __init__(self, cola, pestana):
        # Cola por la que viajan los mensajes.
        self.cola = cola
        # Pestaña donde se escriben.
        self.pestana = pestana

    def write(self, texto):
        # Ignoramos los saltos de línea sueltos.
        if texto.strip():
            # Mandamos la línea a la pestaña.
            self.cola.put(("registro", self.pestana, texto.rstrip()))

    def flush(self):
        # No hace falta hacer nada: cada línea ya se envió.
        pass


class MarcoDesplazable(ttk.Frame):
    """Un marco con barra de desplazamiento vertical, para contenidos que pueden no caber."""

    def __init__(self, padre, fondo=COLOR_FONDO):
        # Creamos el marco exterior.
        super().__init__(padre)
        # El lienzo es lo que se desplaza.
        self.lienzo = tk.Canvas(self, background=fondo, highlightthickness=0, borderwidth=0)
        # Barra de desplazamiento unida al lienzo.
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview)
        # Marco interior: aquí se ponen los contenidos.
        self.interior = tk.Frame(self.lienzo, background=fondo)
        # Metemos el marco interior dentro del lienzo.
        self.ventana = self.lienzo.create_window((0, 0), window=self.interior, anchor="nw")
        # Cuando el lienzo se mueve, la barra se actualiza.
        self.lienzo.configure(yscrollcommand=self.barra.set)
        # El lienzo ocupa todo el espacio (la barra solo aparece si hace falta).
        self.lienzo.pack(side="left", fill="both", expand=True)
        # De momento la barra está escondida.
        self.barra_visible = False
        # Si cambia el tamaño de los contenidos, recalculamos hasta dónde se puede desplazar.
        self.interior.bind("<Configure>", self._ajustar_region)
        # Si cambia el tamaño de la ventana, el contenido se estira con ella.
        self.lienzo.bind("<Configure>", self._ajustar_ancho)

    def _ajustar_region(self, _evento=None):
        # La región desplazable es lo que ocupan los contenidos.
        self.lienzo.configure(scrollregion=self.lienzo.bbox("all"))
        # Mostramos u ocultamos la barra.
        self._mostrar_barra()

    def _ajustar_ancho(self, evento):
        # El marco interior toma el ancho del lienzo.
        self.lienzo.itemconfigure(self.ventana, width=evento.width)
        # Mostramos u ocultamos la barra.
        self._mostrar_barra()

    def _mostrar_barra(self):
        """Muestra la barra solo si el contenido no cabe."""
        # ¿Es el contenido más alto que lo que se ve? (altura 1 = todavía no se dibujó)
        hace_falta = self.interior.winfo_reqheight() > self.lienzo.winfo_height() > 1
        # Hace falta y no se ve: la mostramos.
        if hace_falta and not self.barra_visible:
            # A la derecha del lienzo.
            self.barra.pack(side="right", fill="y", before=self.lienzo)
        # No hace falta y se ve: la escondemos.
        elif not hace_falta and self.barra_visible:
            # La quitamos.
            self.barra.pack_forget()
            # Y volvemos arriba.
            self.lienzo.yview_moveto(0)
        # Apuntamos cómo quedó.
        self.barra_visible = hace_falta

    def desplazar(self, pasos):
        """Mueve el contenido hacia abajo (pasos > 0) o hacia arriba (pasos < 0), si no cabe entero."""
        # Solo si el contenido es más alto que lo que se ve.
        if self.interior.winfo_reqheight() > self.lienzo.winfo_height():
            # Movemos el lienzo.
            self.lienzo.yview_scroll(pasos, "units")

    def vaciar(self, mantener_posicion=False):
        """Quita todos los contenidos y vuelve arriba del todo (o, si se pide, deja la barra donde estaba)."""
        # Posición actual de la barra (0 = arriba del todo).
        posicion = self.lienzo.yview()[0]
        # Borramos cada elemento del interior.
        for hijo in self.interior.winfo_children():
            # Lo destruimos.
            hijo.destroy()
        # Volvemos arriba...
        self.lienzo.yview_moveto(0)
        # ...o, si se pidió, a donde estaba cuando ya se hayan dibujado los contenidos nuevos.
        if mantener_posicion and posicion:
            # Después de dibujar.
            self.lienzo.after_idle(lambda: self.lienzo.yview_moveto(posicion))


def ajustar_al_ancho(etiqueta):
    """Hace que el texto de una etiqueta pase a la línea siguiente según el ancho que tenga en cada momento.

    La etiqueta debe colocarse estirada (fill="x" o sticky="ew"): ocupa el ancho que le dé la ventana.
    """
    # Pide el mínimo ancho posible: así su texto nunca ensancha la columna (si no, ancho y texto se
    # empujarían el uno al otro sin parar).
    etiqueta.configure(width=1)
    # Cada vez que cambia de tamaño, el ancho de línea pasa a ser su ancho real.
    etiqueta.bind("<Configure>", lambda evento: evento.widget.configure(wraplength=max(evento.width - 4, 40)))
    # Devolvemos la etiqueta para poder colocarla en la misma línea.
    return etiqueta


def tarjeta(padre, titulo=None):
    """Crea una tarjeta blanca con borde fino y, si se indica, un título dentro.

    Devuelve (marco, contenido): `marco` es lo que se coloca y `contenido` donde van los controles.
    """
    # Marco blanco con borde gris de 1 píxel.
    marco = tk.Frame(padre, background=COLOR_TARJETA, highlightbackground=COLOR_BORDE, highlightcolor=COLOR_BORDE,
                     highlightthickness=1)
    # Margen interior.
    interior = ttk.Frame(marco, style="Tarjeta.TFrame", padding=(20, 14, 20, 18))
    # Ocupa toda la tarjeta.
    interior.pack(fill="both", expand=True)
    # Título, si lo hay.
    if titulo:
        # Título en negrita grande.
        ttk.Label(interior, text=titulo, style="TituloTarjeta.TLabel").pack(anchor="w", pady=(0, 10))
    # Contenido de la tarjeta.
    contenido = ttk.Frame(interior, style="Tarjeta.TFrame")
    # Debajo del título.
    contenido.pack(fill="both", expand=True)
    # Devolvemos las dos partes.
    return marco, contenido


def botones_marcar(padre, marca, al_marcar, fondo):
    """Botones «Hecha» y «No la hice». El marcado se resalta; pulsarlo otra vez quita la marca.

    `al_marcar(estado)` recibe "hecha", "no_hecha" o None (quitar la marca).
    """
    # Marco para los dos botones.
    marco = tk.Frame(padre, background=fondo)
    # Los dos botones, con su estado y su estilo cuando están activos.
    for posicion, (estado, texto, estilo_activo) in enumerate((("hecha", "Hecha", "MarcaHecha.TButton"),
                                                                ("no_hecha", "No la hice", "MarcaNo.TButton"))):
        # ¿Es el estado marcado ahora?
        activo = marca == estado
        # Botón: resaltado si está activo; al pulsarlo marca ese estado, o quita la marca si ya lo tenía.
        ttk.Button(marco, text=texto, style=estilo_activo if activo else "Marca.TButton",
                   command=lambda e=estado, a=activo: al_marcar(None if a else e)).pack(
            side="left", padx=(6 if posicion else 0, 0))
    # Devolvemos el marco para colocarlo.
    return marco


def tarjeta_sesion(padre, sesion, fuentes, estado="", marca=None, al_marcar=None):
    """Crea la tarjeta de una sesión para la sección Hoy.

    `estado` (según la hora) puede ser "ahora", "siguiente" o "pasada"; `marca` es "hecha", "no_hecha" o None;
    con `al_marcar`, la tarjeta lleva los botones «Hecha» y «No la hice».
    """
    # Colores según la prioridad del tema.
    fuerte, _suave = COLORES_PRIORIDAD.get(sesion.prioridad, COLORES_PRIORIDAD[1])
    # ¿Ya terminó esta sesión?
    pasada = estado == "pasada"
    # Fondo de la tarjeta: gris si ya pasó.
    fondo = COLOR_PASADO if pasada else COLOR_TARJETA
    # Color del texto: más apagado si ya pasó.
    texto = COLOR_SUAVE if pasada else COLOR_TEXTO
    # Borde azul para la sesión que toca ahora.
    borde = COLOR_ACENTO if estado == "ahora" else COLOR_BORDE
    # Marco de la tarjeta, con un borde fino.
    marco = tk.Frame(padre, background=fondo, highlightbackground=borde, highlightcolor=borde,
                     highlightthickness=2 if estado == "ahora" else 1)
    # Franja de color a la izquierda (el color de la prioridad).
    tk.Frame(marco, background="#c4c8cf" if pasada else fuerte, width=7).pack(side="left", fill="y")
    # Hora de inicio y de fin, una debajo de la otra.
    tk.Label(marco, text=f"{sesion.inicio:%H:%M}\n{sesion.fin:%H:%M}", font=fuentes["hora"], background=fondo,
             foreground=texto, justify="center").pack(side="left", padx=(16, 18), pady=12)
    # Etiqueta de estado a la derecha (si la hay): texto y color.
    etiquetas = {"ahora": ("Ahora", COLOR_ACENTO), "siguiente": ("Siguiente", COLOR_BIEN), "pasada": ("Ya pasó", "#9aa0a6")}
    # Hueco de ancho fijo para la etiqueta (aunque no haya), para que los botones de todas las tarjetas queden alineados.
    hueco = tk.Frame(marco, background=fondo, width=fuentes["pequena_negrita"].measure("Siguiente") + 36)
    # A la derecha del todo.
    hueco.pack(side="right", fill="y", padx=(0, 12))
    # El hueco no cambia de tamaño con lo que lleva dentro.
    hueco.pack_propagate(False)
    # Si la sesión tiene estado, mostramos su etiqueta dentro del hueco.
    if estado in etiquetas:
        # Texto y color de la etiqueta.
        rotulo, color = etiquetas[estado]
        # Etiqueta tipo "píldora", centrada en vertical.
        tk.Label(hueco, text=rotulo, font=fuentes["pequena_negrita"], background=color, foreground="white",
                 padx=10, pady=3).pack(side="right", expand=True)
    # Botones para marcarla (a la izquierda de la etiqueta).
    if al_marcar:
        # Los colocamos.
        botones_marcar(marco, marca, al_marcar, fondo).pack(side="right", padx=(8, 0))
    # Parte central con el tema y los detalles.
    centro = tk.Frame(marco, background=fondo)
    # Ocupa el espacio que sobra.
    centro.pack(side="left", fill="both", expand=True, pady=10)
    # Nombre del tema, grande.
    tk.Label(centro, text=sesion.tema, font=fuentes["tema"], background=fondo, foreground=texto,
             anchor="w").pack(fill="x")
    # Detalles: número de sesión, duración, prioridad y si es una recuperación.
    detalles = f"Sesión {sesion.numero} de {sesion.total} esta semana  ·  {sesion.minutos} min  ·  prioridad {sesion.prioridad}"
    # Recuperación.
    if sesion.recuperacion:
        # Lo añadimos.
        detalles += "  ·  para recuperar una no hecha"
    # Etiqueta de los detalles.
    ajustar_al_ancho(tk.Label(centro, text=detalles, font=fuentes["normal"], background=fondo,
                              foreground=COLOR_SUAVE, anchor="w", justify="left")).pack(fill="x")
    # Devolvemos la tarjeta para colocarla.
    return marco


class PestanaHoy(ttk.Frame):
    """Sección "Hoy": las sesiones del día, para marcarlas como hechas o no hechas."""

    def __init__(self, padre, app):
        # Marco de la pestaña con margen interior.
        super().__init__(padre, padding=(28, 22))
        # Referencia a la ventana principal.
        self.app = app
        # Título: "Hoy, martes 27 de octubre".
        self.titulo = ttk.Label(self, style="Titulo.TLabel")
        # Lo colocamos arriba.
        self.titulo.pack(anchor="w")
        # Subtítulo: cuántas sesiones y cuánto tiempo.
        self.subtitulo = ttk.Label(self, style="Suave.TLabel")
        # Debajo del título.
        self.subtitulo.pack(anchor="w", pady=(2, 14))
        # Lista desplazable de tarjetas.
        self.lista = MarcoDesplazable(self)
        # Ocupa el resto de la pestaña.
        self.lista.pack(fill="both", expand=True)

    def refrescar(self):
        """Vuelve a dibujar la sección con la hora actual (sin perder hasta dónde se había bajado)."""
        # Fecha y hora de este momento.
        ahora = datetime.now()
        # Fecha de hoy.
        hoy = ahora.date()
        # Título con la fecha larga, con mayúscula inicial.
        self.titulo.configure(text=f"Hoy, {fecha_larga(hoy)}")
        # Quitamos las tarjetas anteriores (recordando la posición de la barra).
        self.lista.vaciar(mantener_posicion=True)
        # Plan guardado (o None si no hay).
        plan = self.app.plan
        # Sin plan todavía.
        if plan is None:
            # Explicamos qué hacer.
            self._mensaje("Todavía no hay un plan de estudio.",
                          "Agrega tus temas en la sección Temas y luego pulsa «Generar plan» en la sección Semana.",
                          ("Ir a Temas", self.app.pestana_temas))
            # Terminamos.
            return
        # Sesiones hechas y no hechas.
        registro = self.app.registro()
        # El plan no incluye el día de hoy.
        if not plan["desde"] <= hoy <= plan["hasta"]:
            # Explicamos qué hacer.
            self._mensaje("El plan guardado no incluye hoy.",
                          f"Va del {fecha_corta(plan['desde'])} al {fecha_corta(plan['hasta'])}. "
                          "Genera uno nuevo en la sección Semana.",
                          ("Ir a Semana", self.app.pestana_semana))
        # Hoy sí está en el plan.
        else:
            # Sesiones de hoy.
            self._dibujar_hoy(repartidor.sesiones_del_dia(plan, hoy), plan, registro, ahora)
        # Sesiones de días anteriores que quedaron sin marcar.
        atrasadas = [s for s in progreso.sin_marcar(plan, registro, ahora) if s.inicio.date() < hoy]
        # Si hay, las mostramos debajo.
        if atrasadas:
            # Sección.
            self._dibujar_atrasadas(atrasadas)

    def _dibujar_hoy(self, sesiones, plan, registro, ahora):
        """Dibuja las tarjetas de las sesiones de hoy (o el aviso de día libre)."""
        # Día sin sesiones.
        if not sesiones:
            # Próxima sesión del plan (otro día).
            siguiente = proxima_sesion(plan, ahora)
            # Texto según haya o no otra sesión más adelante.
            detalle = (f"Tu próxima sesión es el {fecha_corta(siguiente.inicio.date())} a las {siguiente.inicio:%H:%M} "
                       f"({siguiente.tema})." if siguiente else "No quedan más sesiones en este plan.")
            # Mostramos el mensaje.
            self._mensaje("Hoy es día libre.", f"No tienes sesiones de estudio hoy. {detalle}")
            # Terminamos.
            return
        # Minutos de estudio del día.
        total = sum(s.minutos for s in sesiones)
        # Cuántas hechas.
        hechas = sum(1 for s in sesiones if progreso.estado_de(registro, s) == "hecha")
        # Subtítulo con el resumen del día.
        self.subtitulo.configure(text=f"{len(sesiones)} sesiones · {minutos_a_texto(total)} de estudio · "
                                      f"{hechas} hechas. Marca cada una al terminar: así el plan se adapta a ti.")
        # La siguiente sesión que todavía no empezó.
        siguiente = next((s for s in sesiones if s.inicio > ahora), None)
        # Una tarjeta por sesión.
        for sesion in sesiones:
            # Estado de la sesión según la hora.
            if sesion.fin <= ahora:
                # Ya terminó.
                estado = "pasada"
            # Empezó y no terminó.
            elif sesion.inicio <= ahora:
                # Es la de ahora.
                estado = "ahora"
            # Es la próxima.
            elif sesion is siguiente:
                # La siguiente.
                estado = "siguiente"
            # Más adelante.
            else:
                # Sin etiqueta.
                estado = ""
            # Creamos y colocamos la tarjeta, con sus botones para marcarla.
            tarjeta_sesion(self.lista.interior, sesion, self.app.fuentes, estado, progreso.estado_de(registro, sesion),
                           lambda nuevo, s=sesion: self.marcar(s, nuevo)).pack(fill="x", pady=5, padx=(0, 8))

    def _dibujar_atrasadas(self, sesiones):
        """Lista compacta de sesiones de días anteriores sin marcar, con sus botones."""
        # Título de la sección.
        tk.Label(self.lista.interior, text=f"Sin marcar de días anteriores ({len(sesiones)})",
                 font=self.app.fuentes["subtitulo"], background=COLOR_FONDO, foreground=COLOR_TEXTO).pack(
            anchor="w", pady=(18, 0))
        # Explicación.
        tk.Label(self.lista.interior, text="Márcalas para que el próximo plan sepa qué recuperar.",
                 font=self.app.fuentes["normal"], background=COLOR_FONDO, foreground=COLOR_SUAVE).pack(
            anchor="w", pady=(0, 6))
        # Las más recientes primero (como mucho 15).
        for sesion in sorted(sesiones, key=lambda s: s.inicio, reverse=True)[:15]:
            # Fila blanca con borde.
            fila = tk.Frame(self.lista.interior, background=COLOR_TARJETA, highlightbackground=COLOR_BORDE,
                            highlightthickness=1)
            # Ocupa el ancho.
            fila.pack(fill="x", pady=3, padx=(0, 8))
            # Franja de color de la prioridad.
            tk.Frame(fila, background=COLORES_PRIORIDAD.get(sesion.prioridad, COLORES_PRIORIDAD[1])[0],
                     width=5).pack(side="left", fill="y")
            # Botones para marcarla.
            botones_marcar(fila, None, lambda nuevo, s=sesion: self.marcar(s, nuevo), COLOR_TARJETA).pack(
                side="right", padx=12, pady=6)
            # Día, hora y tema.
            tk.Label(fila, text=f"{fecha_corta(sesion.inicio.date()).capitalize()}  {sesion.inicio:%H:%M}   "
                                f"{sesion.tema}", font=self.app.fuentes["normal"], background=COLOR_TARJETA,
                     foreground=COLOR_TEXTO, anchor="w").pack(side="left", fill="x", expand=True, padx=12)
        # Si había más, lo decimos.
        if len(sesiones) > 15:
            # Aviso.
            tk.Label(self.lista.interior, text=f"…y {len(sesiones) - 15} más.", font=self.app.fuentes["normal"],
                     background=COLOR_FONDO, foreground=COLOR_SUAVE).pack(anchor="w")

    @con_avisos
    def marcar(self, sesion, estado):
        """Marca una sesión como hecha o no hecha (o le quita la marca) y actualiza la ventana."""
        # Sesiones marcadas.
        registro = almacen.cargar_registro()
        # Marcamos.
        progreso.marcar(registro, sesion, estado)
        # Guardamos.
        almacen.guardar_registro(registro)
        # Actualizamos lo que depende de esto.
        self.app.refrescar_progreso()
        # Mensaje abajo según el caso.
        texto = {None: "Marca quitada", "hecha": "¡Bien! Sesión hecha", "no_hecha": "Anotado: no la hiciste"}[estado]
        # Si no la hizo y se recupera, lo explicamos.
        if estado == "no_hecha" and self.app.config_o_defecto()["recuperar_no_hechas"]:
            # Explicación.
            texto += ". Ese tiempo se añadirá al próximo plan para recuperarlo"
        # Mensaje.
        self.app.avisar(f"{texto}: {sesion.tema}, {fecha_corta(sesion.inicio.date())} a las {sesion.inicio:%H:%M}.")

    def _mensaje(self, titulo, detalle, boton=None):
        """Muestra un mensaje grande en lugar de la lista (y, si se indica, un botón para ir a otra sección)."""
        # Sin subtítulo.
        self.subtitulo.configure(text="")
        # Marco blanco para el mensaje.
        marco = tk.Frame(self.lista.interior, background=COLOR_TARJETA, highlightbackground=COLOR_BORDE,
                         highlightthickness=1)
        # Lo colocamos.
        marco.pack(fill="x", padx=(0, 8))
        # Título del mensaje.
        tk.Label(marco, text=titulo, font=self.app.fuentes["subtitulo"], background=COLOR_TARJETA,
                 foreground=COLOR_TEXTO).pack(anchor="w", padx=22, pady=(20, 4))
        # Explicación.
        ajustar_al_ancho(tk.Label(marco, text=detalle, font=self.app.fuentes["normal"], background=COLOR_TARJETA,
                                  foreground=COLOR_SUAVE, justify="left", anchor="w")).pack(fill="x", padx=22)
        # Si hay botón, lo añadimos.
        if boton:
            # Texto del botón y pestaña a la que lleva.
            texto, pestana = boton
            # Botón principal.
            ttk.Button(marco, text=texto, style="Acento.TButton",
                       command=lambda: self.app.cuaderno.select(pestana)).pack(anchor="w", padx=22, pady=(14, 0))
        # Espacio al final.
        tk.Frame(marco, background=COLOR_TARJETA, height=20).pack()


class PestanaSemana(ttk.Frame):
    """Sección "Semana": genera el plan y lo muestra día por día."""

    def __init__(self, padre, app):
        # Marco de la pestaña con margen interior.
        super().__init__(padre, padding=(28, 22))
        # Referencia a la ventana principal.
        self.app = app
        # Fila superior con el título y los controles.
        arriba = ttk.Frame(self)
        # Ocupa todo el ancho.
        arriba.pack(fill="x")
        # Título.
        ttk.Label(arriba, text="Plan de la semana", style="Titulo.TLabel").pack(side="left")
        # Botón para generar el plan (a la derecha).
        ttk.Button(arriba, text="Generar plan", style="Acento.TButton", command=self.generar).pack(side="right")
        # Lista desplegable con el día de inicio.
        self.inicio = ttk.Combobox(arriba, state="readonly", width=24)
        # A la izquierda del botón.
        self.inicio.pack(side="right", padx=(8, 12))
        # Texto delante de la lista.
        ttk.Label(arriba, text="Empezar:").pack(side="right")
        # Fechas que corresponden a cada opción de la lista (None = automático).
        self.fechas_inicio = []
        # Línea con las fechas del plan.
        self.rango = ttk.Label(self, style="Suave.TLabel")
        # Debajo del título.
        self.rango.pack(anchor="w", pady=(2, 0))
        # Cómo se adaptó el plan (recuperaciones, metas); solo se muestra si hay algo.
        self.notas = ajustar_al_ancho(ttk.Label(self, style="Info.TLabel", justify="left", anchor="w"))
        # Aviso cuando el plan está desactualizado o algo no entró (solo se muestra si hay algo que avisar).
        self.aviso = ajustar_al_ancho(ttk.Label(self, style="Aviso.TLabel", justify="left", anchor="w"))
        # Página desplazable con la semana y, debajo, el resumen.
        pagina = MarcoDesplazable(self)
        # Ocupa el resto de la pestaña.
        pagina.pack(fill="both", expand=True, pady=(12, 0))
        # Cuadrícula con los 7 días.
        self.cuadricula = tk.Frame(pagina.interior, background=COLOR_FONDO)
        # Arriba de la página.
        self.cuadricula.pack(fill="x")
        # Resumen por tema, debajo de la semana.
        marco_resumen, resumen = tarjeta(pagina.interior, "Resumen por tema")
        # Todo el ancho, con un poco de espacio.
        marco_resumen.pack(fill="x", padx=4, pady=(14, 4))
        # Tabla del resumen.
        self.tabla = ttk.Treeview(resumen, columns=("tema", "plan", "pedido", "estado"), show="headings", height=4)
        # Títulos y anchos de las columnas.
        for columna, titulo, ancho in (("tema", "Tema", 260), ("plan", "En el plan", 120),
                                       ("pedido", "Pedido", 120), ("estado", "", 220)):
            # Título de la columna.
            self.tabla.heading(columna, text=titulo, anchor="w")
            # Ancho de la columna.
            self.tabla.column(columna, width=int(ancho * app.escala), anchor="w")
        # Colores de las filas según la prioridad.
        for prioridad, (_fuerte, suave) in COLORES_PRIORIDAD.items():
            # Una etiqueta de color por prioridad.
            self.tabla.tag_configure(f"p{prioridad}", background=suave)
        # La tabla ocupa todo el recuadro.
        self.tabla.pack(fill="x")

    def actualizar_opciones_inicio(self):
        """Rellena la lista "Empezar" con "Automático" y los próximos 14 días."""
        # Opción elegida antes, para conservarla (la primera vez todavía no hay ninguna).
        anterior = self.inicio.current() if self.fechas_inicio else 0
        # Fecha de hoy.
        hoy = date.today()
        # Opción automática primero.
        textos = ["Automático (hoy o mañana)"]
        # Su fecha: ninguna (se calcula al generar).
        self.fechas_inicio = [None]
        # Los próximos 14 días.
        for desplazamiento in range(14):
            # Fecha de ese día.
            fecha = hoy + timedelta(days=desplazamiento)
            # "Hoy", "Mañana" o nada delante.
            prefijo = {0: "Hoy, ", 1: "Mañana, "}.get(desplazamiento, "")
            # Texto de la opción.
            textos.append(f"{prefijo}{fecha_corta(fecha)}")
            # Fecha de la opción.
            self.fechas_inicio.append(fecha)
        # Ponemos las opciones en la lista.
        self.inicio.configure(values=textos)
        # Mantenemos la elegida, o "Automático" si no había.
        self.inicio.current(anterior if 0 <= anterior < len(textos) else 0)

    @con_avisos
    def generar(self, desde=None):
        """Crea el plan de 7 días (adaptado a lo hecho y a tus metas), lo guarda y lo muestra."""
        # Sin temas no hay nada que planificar.
        if not almacen.cargar_temas():
            # Explicamos qué hacer.
            messagebox.showinfo("Primero agrega temas", "Todavía no hay temas. Agrégalos en la sección Temas.",
                                parent=self.winfo_toplevel())
            # Llevamos al usuario a esa pestaña.
            self.app.cuaderno.select(self.app.pestana_temas)
            # Terminamos.
            return
        # Día de inicio: el indicado, el de la lista o (si es None) el automático.
        desde = desde or self.fechas_inicio[max(self.inicio.current(), 0)]
        # Creamos el plan adaptado y lo guardamos en datos/plan.json.
        plan = progreso.generar_y_guardar(desde)
        # La ventana pasa a usar este plan.
        self.app.plan = plan
        # Ya no está desactualizado.
        self.app.plan_desactualizado = False
        # Redibujamos todas las pestañas.
        self.app.refrescar_todo()
        # Mensaje en la barra de abajo.
        self.app.avisar(f"Plan generado: {len(plan['sesiones'])} sesiones del {fecha_corta(plan['desde'])} al "
                        f"{fecha_corta(plan['hasta'])}. Para recibir los avisos, súbelo en la sección Google Calendar.")

    def refrescar(self):
        """Vuelve a dibujar la semana con el plan actual."""
        # Opciones de la lista "Empezar".
        self.actualizar_opciones_inicio()
        # Vaciamos la cuadrícula.
        for hijo in self.cuadricula.winfo_children():
            # Quitamos cada día.
            hijo.destroy()
        # Vaciamos la tabla del resumen.
        self.tabla.delete(*self.tabla.get_children())
        # Plan actual.
        plan = self.app.plan
        # Avisos que se mostrarán (puede haber varios).
        avisos = []
        # Si cambiaron los temas o los ajustes, el plan está viejo.
        if self.app.plan_desactualizado:
            # Lo avisamos.
            avisos.append("Cambiaste tus temas o ajustes: pulsa «Generar plan» para actualizar el plan.")
        # Sin plan todavía.
        if plan is None:
            # Explicación en lugar de las fechas.
            self.rango.configure(text="Todavía no hay plan. Agrega tus temas y pulsa «Generar plan».")
            # Mostramos los avisos (si los hay).
            self._mostrar_textos([], avisos)
            # Terminamos.
            return
        # Fechas del plan.
        self.rango.configure(text=f"Del {fecha_larga(plan['desde'])} al {fecha_larga(plan['hasta'])}  ·  "
                                  f"{len(plan['sesiones'])} sesiones  ·  "
                                  f"{minutos_a_texto(sum(s.minutos for s in plan['sesiones']))} de estudio")
        # Si el plan ya terminó, lo decimos.
        if plan["hasta"] < date.today():
            # Aviso.
            avisos.append("Este plan ya terminó. Pulsa «Generar plan» para crear el de esta semana.")
        # Si algo no entró, lo explicamos.
        if plan["sin_lugar"]:
            # Minutos que no entraron.
            faltan = sum(s.minutos for s in plan["sin_lugar"])
            # Aviso con el consejo.
            avisos.append(f"No entraron {len(plan['sin_lugar'])} sesiones ({minutos_a_texto(faltan)}) porque no caben en "
                          "tus días de estudio. Para que entren: sube el máximo diario, agrega días o empieza más "
                          "temprano (sección Ajustes), o baja los minutos de algún tema.")
        # Mostramos las notas y los avisos.
        self._mostrar_textos(plan.get("notas", []), avisos)
        # Dibujamos los 7 días.
        self._dibujar_dias(plan, self.app.registro())
        # Prioridad de cada tema, para colorear el resumen.
        prioridades = {s.tema: s.prioridad for s in plan["sesiones"] + plan["sin_lugar"]}
        # Una fila por tema.
        for tema, en_plan, pedido in planificador.resumen_por_tema(plan):
            # Estado: completo o cuánto falta.
            estado = "Completo" if en_plan >= pedido else f"Faltan {minutos_a_texto(pedido - en_plan)}"
            # Añadimos la fila con el color de su prioridad.
            self.tabla.insert("", "end", values=(tema, minutos_a_texto(en_plan), minutos_a_texto(pedido), estado),
                              tags=(f"p{prioridades.get(tema, 1)}",))
        # La tabla crece un poco si hay muchos temas (hasta 8 filas).
        self.tabla.configure(height=min(max(len(self.tabla.get_children()), 3), 8))

    def _mostrar_textos(self, notas, avisos):
        """Muestra, debajo de las fechas, cómo se adaptó el plan y los avisos (o los esconde si no hay)."""
        # Primero se quitan los dos, para volver a colocarlos en orden.
        self.notas.pack_forget()
        # El aviso también.
        self.aviso.pack_forget()
        # Debajo de qué va cada línea.
        anterior = self.rango
        # Notas, con una viñeta cada una.
        if notas:
            # Texto.
            self.notas.configure(text="Cómo se adaptó este plan:\n" + "\n".join(f"  •  {nota}" for nota in notas))
            # Debajo de las fechas.
            self.notas.pack(fill="x", pady=(6, 0), after=anterior)
            # El aviso irá debajo de las notas.
            anterior = self.notas
        # Avisos, uno por línea.
        if avisos:
            # Texto.
            self.aviso.configure(text="\n".join(avisos))
            # Debajo de lo anterior.
            self.aviso.pack(fill="x", pady=(6, 0), after=anterior)

    def _dibujar_dias(self, plan, registro):
        """Dibuja una columna por día, con sus sesiones como tarjetas de colores (y si se hicieron)."""
        # Marco de la cuadrícula.
        interior = self.cuadricula
        # Fuentes de la ventana.
        fuentes = self.app.fuentes
        # Fecha de hoy, para resaltarla.
        hoy = date.today()
        # Siete columnas del mismo ancho.
        for columna in range(7):
            # Todas crecen igual.
            interior.columnconfigure(columna, weight=1, uniform="dia")
        # Una columna por día.
        for columna in range(7):
            # Fecha de ese día.
            fecha = plan["desde"] + timedelta(days=columna)
            # Sesiones de ese día.
            sesiones = repartidor.sesiones_del_dia(plan, fecha)
            # ¿Es hoy?
            es_hoy = fecha == hoy
            # Marco del día, con borde azul si es hoy.
            dia = tk.Frame(interior, background=COLOR_TARJETA, highlightthickness=2 if es_hoy else 1,
                           highlightbackground=COLOR_ACENTO if es_hoy else COLOR_BORDE,
                           highlightcolor=COLOR_ACENTO if es_hoy else COLOR_BORDE)
            # Lo colocamos en su columna.
            dia.grid(row=0, column=columna, sticky="nsew", padx=4, pady=2)
            # Nombre del día.
            tk.Label(dia, text=DIAS_VISIBLES[fecha.weekday()].capitalize(), font=fuentes["negrita"],
                     background=COLOR_TARJETA, foreground=COLOR_ACENTO if es_hoy else COLOR_TEXTO).pack(
                anchor="w", padx=10, pady=(10, 0))
            # Fecha (y "hoy" si lo es).
            tk.Label(dia, text=f"{fecha:%d/%m}" + ("  ·  hoy" if es_hoy else ""), font=fuentes["pequena"],
                     background=COLOR_TARJETA, foreground=COLOR_SUAVE).pack(anchor="w", padx=10)
            # Minutos del día, o "Libre".
            total = sum(s.minutos for s in sesiones)
            # Texto del total.
            tk.Label(dia, text=minutos_a_texto(total) if sesiones else "Libre", font=fuentes["pequena"],
                     background=COLOR_TARJETA, foreground=COLOR_SUAVE).pack(anchor="w", padx=10, pady=(0, 8))
            # Una tarjeta por sesión.
            for sesion in sesiones:
                # Colores según la prioridad.
                fuerte, suave = COLORES_PRIORIDAD.get(sesion.prioridad, COLORES_PRIORIDAD[1])
                # Tarjeta con el color suave de fondo.
                tarjeta = tk.Frame(dia, background=suave)
                # Ocupa el ancho de la columna.
                tarjeta.pack(fill="x", padx=8, pady=3)
                # Franja de color fuerte a la izquierda.
                tk.Frame(tarjeta, background=fuerte, width=4).pack(side="left", fill="y")
                # Textos de la tarjeta.
                textos = tk.Frame(tarjeta, background=suave)
                # Al lado de la franja.
                textos.pack(side="left", fill="x", expand=True, padx=7, pady=5)
                # Horario de la sesión.
                tk.Label(textos, text=f"{sesion.inicio:%H:%M}–{sesion.fin:%H:%M}", font=fuentes["pequena_negrita"],
                         background=suave, foreground=COLOR_TEXTO).pack(anchor="w")
                # Tema y número de sesión.
                # Si el nombre es largo, pasa a la línea siguiente según el ancho real de la columna.
                ajustar_al_ancho(tk.Label(textos, text=f"{sesion.tema} ({sesion.numero}/{sesion.total})", anchor="w",
                                          font=fuentes["pequena"], background=suave, foreground=COLOR_TEXTO,
                                          justify="left")).pack(fill="x")
                # Si es una recuperación, lo decimos.
                if sesion.recuperacion:
                    # Etiqueta pequeña.
                    tk.Label(textos, text="recuperación", font=fuentes["pequena"], background=suave,
                             foreground=COLOR_SUAVE).pack(anchor="w")
                # Si ya está marcada, lo decimos en verde o en rojo.
                marca = progreso.estado_de(registro, sesion)
                # Marcada.
                if marca:
                    # Etiqueta.
                    tk.Label(textos, text=progreso.NOMBRES_ESTADO[marca], font=fuentes["pequena_negrita"],
                             background=suave, foreground=COLOR_BIEN if marca == "hecha" else COLOR_MAL).pack(anchor="w")
            # Espacio al final de la columna.
            tk.Frame(dia, background=COLOR_TARJETA, height=8).pack()


class PestanaTemas(ttk.Frame):
    """Sección "Temas": lista de temas y formulario para agregarlos, cambiarlos o quitarlos."""

    def __init__(self, padre, app):
        # Marco de la pestaña con margen interior.
        super().__init__(padre, padding=(28, 22))
        # Referencia a la ventana principal.
        self.app = app
        # Título.
        ttk.Label(self, text="Tus temas", style="Titulo.TLabel").pack(anchor="w")
        # Explicación breve.
        ttk.Label(self, text="Cuántos minutos por semana quieres dedicar a cada tema y qué prioridad tiene. "
                             "Haz clic en un tema para cambiarlo.", style="Suave.TLabel").pack(anchor="w", pady=(2, 14))
        # Contenedor de las dos columnas.
        cuerpo = ttk.Frame(self)
        # Ocupa el resto de la pestaña.
        cuerpo.pack(fill="both", expand=True)
        # La columna de la lista crece; la del formulario no.
        cuerpo.columnconfigure(0, weight=1)
        # La fila crece hacia abajo.
        cuerpo.rowconfigure(0, weight=1)
        # Columna izquierda: lista y total.
        izquierda = ttk.Frame(cuerpo)
        # A la izquierda, estirándose.
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        # Tabla de temas.
        self.tabla = ttk.Treeview(izquierda, columns=("tema", "prioridad", "minutos", "horas"), show="headings",
                                  selectmode="browse")
        # Títulos y anchos de las columnas.
        for columna, titulo, ancho in (("tema", "Tema", 260), ("prioridad", "Prioridad", 130),
                                       ("minutos", "Min/semana", 110), ("horas", "Tiempo", 120)):
            # Título de la columna.
            self.tabla.heading(columna, text=titulo, anchor="w")
            # Ancho de la columna.
            self.tabla.column(columna, width=int(ancho * app.escala), anchor="w")
        # Colores de las filas según la prioridad.
        for prioridad, (_fuerte, suave) in COLORES_PRIORIDAD.items():
            # Una etiqueta de color por prioridad.
            self.tabla.tag_configure(f"p{prioridad}", background=suave)
        # Barra de desplazamiento de la tabla.
        barra = ttk.Scrollbar(izquierda, orient="vertical", command=self.tabla.yview)
        # Unimos la tabla con su barra.
        self.tabla.configure(yscrollcommand=barra.set)
        # Al elegir un tema, se carga en el formulario.
        self.tabla.bind("<<TreeviewSelect>>", self._al_elegir)
        # Total de minutos (debajo de la tabla).
        self.total = ttk.Label(izquierda, style="Suave.TLabel")
        # Abajo del todo.
        self.total.pack(side="bottom", anchor="w", pady=(10, 0))
        # La barra a la derecha de la tabla.
        barra.pack(side="right", fill="y")
        # La tabla ocupa el resto.
        self.tabla.pack(side="left", fill="both", expand=True)
        # Columna derecha: formulario.
        marco_formulario, formulario = tarjeta(cuerpo, "Agregar o cambiar un tema")
        # Arriba a la derecha.
        marco_formulario.grid(row=0, column=1, sticky="n")
        # Nombre del tema.
        ttk.Label(formulario, text="Nombre del tema", style="Tarjeta.TLabel").pack(anchor="w")
        # Texto del nombre.
        self.nombre = tk.StringVar()
        # Casilla para escribir el nombre.
        self.casilla_nombre = ttk.Entry(formulario, textvariable=self.nombre, width=30)
        # Debajo de su título.
        self.casilla_nombre.pack(fill="x", pady=(4, 12))
        # Prioridad.
        ttk.Label(formulario, text="Prioridad", style="Tarjeta.TLabel").pack(anchor="w")
        # Lista desplegable de prioridades (de 5 a 1).
        self.prioridad = ttk.Combobox(formulario, state="readonly", values=[NOMBRES_PRIORIDAD[p] for p in range(5, 0, -1)])
        # Por defecto, prioridad media (3).
        self.prioridad.current(2)
        # Debajo de su título.
        self.prioridad.pack(fill="x", pady=(4, 12))
        # Minutos por semana.
        ttk.Label(formulario, text="Minutos por semana", style="Tarjeta.TLabel").pack(anchor="w")
        # Texto de los minutos.
        self.minutos = tk.StringVar(value="120")
        # Casilla con flechitas (de 5 en 5).
        ttk.Spinbox(formulario, from_=5, to=almacen.MINUTOS_EN_UNA_SEMANA, increment=5,
                    textvariable=self.minutos).pack(fill="x", pady=(4, 2))
        # Ayuda que se actualiza al escribir los minutos ("= 2 h por semana").
        self.ayuda_minutos = ttk.Label(formulario, style="TarjetaSuave.TLabel")
        # Debajo de la casilla.
        self.ayuda_minutos.pack(anchor="w", pady=(0, 16))
        # Cada vez que cambian los minutos, actualizamos la ayuda.
        self.minutos.trace_add("write", self._actualizar_ayuda)
        # Fila de botones.
        botones = ttk.Frame(formulario, style="Tarjeta.TFrame")
        # Debajo de los campos.
        botones.pack(fill="x")
        # Guardar.
        ttk.Button(botones, text="Guardar tema", style="Acento.TButton", command=self.guardar).pack(side="left")
        # Vaciar el formulario para escribir uno nuevo.
        ttk.Button(botones, text="Nuevo", command=self.nuevo).pack(side="left", padx=(8, 0))
        # Separador.
        ttk.Separator(formulario).pack(fill="x", pady=16)
        # Quitar el tema elegido.
        self.boton_quitar = ttk.Button(formulario, text="Quitar el tema elegido", style="Peligro.TButton",
                                       command=self.quitar)
        # Abajo del formulario.
        self.boton_quitar.pack(anchor="w")
        # Enter en el nombre guarda el tema.
        self.casilla_nombre.bind("<Return>", lambda _evento: self.guardar())
        # Ayuda inicial.
        self._actualizar_ayuda()

    def refrescar(self):
        """Vuelve a llenar la lista de temas."""
        # Leemos los temas (si el archivo está mal, mostramos el error y una lista vacía).
        try:
            # Temas guardados.
            temas = almacen.cargar_temas()
        # Archivo dañado.
        except almacen.ErrorPlanificador as error:
            # Lo avisamos abajo.
            self.app.avisar(str(error), error=True)
            # Lista vacía.
            temas = []
        # Vaciamos la tabla.
        self.tabla.delete(*self.tabla.get_children())
        # Una fila por tema, de mayor a menor prioridad.
        for tema in sorted(temas, key=lambda t: (-t["prioridad"], t["nombre"].lower())):
            # Añadimos la fila; su identificador es el nombre del tema.
            self.tabla.insert("", "end", iid=tema["nombre"], tags=(f"p{tema['prioridad']}",), values=(
                tema["nombre"], NOMBRES_PRIORIDAD[tema["prioridad"]], tema["minutos_semana"],
                minutos_a_texto(tema["minutos_semana"])))
        # Total de minutos pedidos.
        total = sum(t["minutos_semana"] for t in temas)
        # Texto del total.
        texto = f"{len(temas)} temas · {minutos_a_texto(total)} por semana" if temas else "Todavía no hay temas."
        # Cuánto cabe por semana con los ajustes actuales.
        try:
            # Capacidad (None si no hay máximo diario).
            capacidad = planificador.capacidad_semanal(almacen.cargar_config())
        # Si la configuración está mal, no la mostramos.
        except almacen.ErrorPlanificador:
            # Sin capacidad.
            capacidad = None
        # Si la hay, la añadimos al texto.
        if capacidad is not None and temas:
            # Caben como mucho.
            texto += f"  ·  con tus ajustes caben hasta {minutos_a_texto(capacidad)}"
            # Si se pide más de lo que cabe, lo avisamos.
            if total > capacidad:
                # Aviso.
                texto += " (pides más de lo que cabe: lo de menor prioridad quedará fuera)"
        # Mostramos el total.
        self.total.configure(text=texto)

    def _al_elegir(self, _evento=None):
        """Carga en el formulario el tema elegido en la lista."""
        # Fila elegida.
        elegidos = self.tabla.selection()
        # Si no hay ninguna, nada que hacer.
        if not elegidos:
            # Terminamos.
            return
        # Datos de la fila.
        nombre, _prioridad, minutos, _horas = self.tabla.item(elegidos[0], "values")
        # Prioridad numérica (está en la etiqueta de color "p4").
        prioridad = int(self.tabla.item(elegidos[0], "tags")[0][1:])
        # Ponemos el nombre.
        self.nombre.set(nombre)
        # Ponemos la prioridad (la lista va de 5 a 1).
        self.prioridad.current(5 - prioridad)
        # Ponemos los minutos.
        self.minutos.set(minutos)

    def _actualizar_ayuda(self, *_):
        """Muestra debajo de los minutos cuánto tiempo es y en cuántas sesiones se parte."""
        # Intentamos leer el número.
        try:
            # Minutos escritos.
            minutos = int(self.minutos.get())
        # Si no es un número, lo decimos.
        except ValueError:
            # Ayuda.
            self.ayuda_minutos.configure(text="Escribe un número de minutos.")
            # Terminamos.
            return
        # Duración de las sesiones según los ajustes (25 si los ajustes están mal).
        try:
            # Duración y mínimo de los ajustes.
            config = almacen.cargar_config()
        # Si fallan, usamos los valores por defecto.
        except almacen.ErrorPlanificador:
            # Por defecto.
            config = almacen.CONFIG_POR_DEFECTO
        # En cuántas sesiones se partiría.
        bloques = repartidor.partir_en_bloques(minutos, config["duracion_sesion"], config["duracion_minima"])
        # Texto de ayuda.
        self.ayuda_minutos.configure(text=f"= {minutos_a_texto(max(minutos, 0))} por semana, en {len(bloques)} "
                                          f"sesiones" if bloques else "Tiene que ser más de 0.")

    @con_avisos
    def guardar(self):
        """Agrega el tema del formulario (o lo actualiza si ya existe)."""
        # Leemos los minutos como número.
        try:
            # Minutos escritos.
            minutos = int(self.minutos.get())
        # Si no es un número, lo avisamos.
        except ValueError as error:
            # Error para el usuario.
            raise almacen.ErrorPlanificador("Los minutos por semana tienen que ser un número entero, por ejemplo 120.") from error
        # Prioridad elegida (la lista va de 5 a 1).
        prioridad = 5 - self.prioridad.current()
        # Temas guardados.
        temas = almacen.cargar_temas()
        # Agregamos o actualizamos (aquí se revisa que los datos tengan sentido).
        es_nuevo = almacen.agregar_tema(temas, self.nombre.get(), prioridad, minutos)
        # Guardamos la lista.
        almacen.guardar_temas(temas)
        # El plan ya no coincide con los temas.
        self.app.plan_desactualizado = True
        # Redibujamos.
        self.app.refrescar_todo()
        # Seleccionamos el tema guardado en la lista.
        nombre = almacen.buscar_tema(temas, self.nombre.get())["nombre"]
        # Lo marcamos.
        self.tabla.selection_set(nombre)
        # Mensaje abajo.
        self.app.avisar(f"{'Agregado' if es_nuevo else 'Actualizado'}: «{nombre}». "
                        "Cuando termines, pulsa «Generar plan» en la sección Semana.")

    def nuevo(self):
        """Vacía el formulario para escribir un tema nuevo."""
        # Quitamos la selección de la lista.
        self.tabla.selection_remove(*self.tabla.selection())
        # Nombre vacío.
        self.nombre.set("")
        # Prioridad media.
        self.prioridad.current(2)
        # 120 minutos por defecto.
        self.minutos.set("120")
        # El cursor va al nombre.
        self.casilla_nombre.focus_set()

    @con_avisos
    def quitar(self):
        """Quita el tema elegido en la lista (después de preguntar)."""
        # Fila elegida.
        elegidos = self.tabla.selection()
        # Si no hay ninguna, lo explicamos.
        if not elegidos:
            # Aviso.
            messagebox.showinfo("Elige un tema", "Primero haz clic en el tema que quieres quitar.",
                                parent=self.winfo_toplevel())
            # Terminamos.
            return
        # Nombre del tema elegido.
        nombre = elegidos[0]
        # Pedimos confirmación.
        if not messagebox.askyesno("Quitar tema", f"¿Quitar «{nombre}» de tus temas?", parent=self.winfo_toplevel()):
            # Si dice que no, no hacemos nada.
            return
        # Temas guardados.
        temas = almacen.cargar_temas()
        # Quitamos el tema.
        almacen.quitar_tema(temas, nombre)
        # Guardamos la lista.
        almacen.guardar_temas(temas)
        # El plan ya no coincide con los temas.
        self.app.plan_desactualizado = True
        # Vaciamos el formulario.
        self.nuevo()
        # Redibujamos.
        self.app.refrescar_todo()
        # Mensaje abajo.
        self.app.avisar(f"Quitado: «{nombre}». Pulsa «Generar plan» en la sección Semana para actualizar el plan.")


class PestanaMetas(ttk.Frame):
    """Sección "Metas": tus metas (exámenes, entregas...) y tu progreso de los últimos 14 días."""

    def __init__(self, padre, app):
        # Marco de la pestaña con margen interior.
        super().__init__(padre, padding=(28, 22))
        # Referencia a la ventana principal.
        self.app = app
        # Título.
        ttk.Label(self, text="Metas y progreso", style="Titulo.TLabel").pack(anchor="w")
        # Explicación breve.
        ajustar_al_ancho(ttk.Label(self, style="Suave.TLabel", justify="left", text=(
            "Una meta con tema y fecha (por ejemplo, un examen) hace que el plan le dé más prioridad las dos semanas "
            "anteriores y coloque sus sesiones antes de esa fecha."))).pack(fill="x", pady=(2, 14))
        # Contenedor de las dos tarjetas.
        cuerpo = ttk.Frame(self)
        # Ocupa el resto de la pestaña.
        cuerpo.pack(fill="both", expand=True)
        # Columnas proporcionales: un poco más de sitio para el progreso (su tabla tiene más columnas).
        cuerpo.columnconfigure(0, weight=9, uniform="metas")
        # Columna del progreso.
        cuerpo.columnconfigure(1, weight=11, uniform="metas")
        # La fila crece hacia abajo.
        cuerpo.rowconfigure(0, weight=1)
        # Tarjeta izquierda: las metas.
        marco_metas, metas = tarjeta(cuerpo, "Tus metas")
        # A la izquierda.
        marco_metas.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        # Formulario de meta nueva (abajo; se coloca antes que la tabla para que nunca quede cortado).
        formulario = ttk.Frame(metas, style="Tarjeta.TFrame")
        # Abajo del todo.
        formulario.pack(side="bottom", fill="x")
        # Fila del título y el botón de guardar.
        titulo = ttk.Frame(formulario, style="Tarjeta.TFrame")
        # Ocupa el ancho.
        titulo.pack(fill="x")
        # Título.
        ttk.Label(titulo, text="Meta nueva", style="Tarjeta.TLabel").pack(side="left")
        # Guardar (a la derecha).
        ttk.Button(titulo, text="Guardar meta", style="Acento.TButton", command=self.guardar).pack(side="right")
        # Texto de la meta.
        self.texto = tk.StringVar()
        # Casilla del texto.
        casilla = ttk.Entry(formulario, textvariable=self.texto)
        # Debajo.
        casilla.pack(fill="x", pady=(4, 8))
        # Enter guarda.
        casilla.bind("<Return>", lambda _evento: self.guardar())
        # Fila con tema, fecha y el botón de guardar.
        fila = ttk.Frame(formulario, style="Tarjeta.TFrame")
        # Ocupa el ancho.
        fila.pack(fill="x")
        # Título del tema.
        ttk.Label(fila, text="Tema", style="Tarjeta.TLabel").pack(side="left")
        # Lista de temas.
        self.tema = ttk.Combobox(fila, state="readonly", width=14)
        # Al lado.
        self.tema.pack(side="left", padx=(6, 12))
        # Título de la fecha.
        ttk.Label(fila, text="Fecha", style="Tarjeta.TLabel").pack(side="left")
        # Fecha escrita.
        self.fecha = tk.StringVar()
        # Casilla de la fecha.
        ttk.Entry(fila, textvariable=self.fecha, width=11).pack(side="left", padx=(6, 0))
        # Ayuda del formato (pasa a otra línea si no cabe).
        ajustar_al_ancho(ttk.Label(formulario, style="TarjetaSuave.TLabel", justify="left",
                                   text="Fecha como AAAA-MM-DD (por ejemplo 2026-11-13). Tema y fecha son opcionales.")
                         ).pack(fill="x", pady=(4, 0))
        # Separador encima del formulario.
        ttk.Separator(metas).pack(side="bottom", fill="x", pady=12)
        # Botones para la meta elegida (encima del separador).
        botones = ttk.Frame(metas, style="Tarjeta.TFrame")
        # Abajo.
        botones.pack(side="bottom", fill="x", pady=(8, 0))
        # Cumplida / pendiente.
        ttk.Button(botones, text="Cumplida / pendiente", command=self.alternar).pack(side="left")
        # Quitar.
        ttk.Button(botones, text="Quitar", style="Peligro.TButton", command=self.quitar).pack(side="left", padx=(8, 0))
        # Tabla de metas (ocupa lo que queda).
        self.tabla = ttk.Treeview(metas, columns=("meta", "tema", "fecha", "estado"), show="headings", height=5,
                                  selectmode="browse")
        # Títulos y anchos de las columnas.
        for columna, titulo, ancho in (("meta", "Meta", 160), ("tema", "Tema", 90), ("fecha", "Fecha", 90),
                                       ("estado", "Estado", 85)):
            # Título.
            self.tabla.heading(columna, text=titulo, anchor="w")
            # Ancho.
            self.tabla.column(columna, width=int(ancho * app.escala), anchor="w")
        # Las cumplidas, en gris.
        self.tabla.tag_configure("cumplida", foreground=COLOR_SUAVE)
        # Las de esta semana, resaltadas.
        self.tabla.tag_configure("cerca", background="#fff4e5")
        # La tabla ocupa el espacio disponible.
        self.tabla.pack(fill="both", expand=True)
        # Tarjeta derecha: el progreso.
        marco_progreso, progreso_ = tarjeta(cuerpo, f"Tu progreso (últimos {progreso.DIAS_RECUENTO} días)")
        # A la derecha.
        marco_progreso.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        # Racha.
        self.racha = ttk.Label(progreso_, style="RachaTarjeta.TLabel")
        # Arriba.
        self.racha.pack(anchor="w")
        # Totales.
        self.totales = ttk.Label(progreso_, style="TarjetaSuave.TLabel")
        # Debajo.
        self.totales.pack(anchor="w", pady=(2, 10))
        # Explicación (abajo; se coloca antes que la tabla para que nunca quede cortada).
        ajustar_al_ancho(ttk.Label(progreso_, style="TarjetaSuave.TLabel", justify="left", text=(
            "Lo que no haces se añade al próximo plan para recuperarlo, si cabe. «Olvidar» sirve cuando ya no tiene "
            "sentido recuperarlo. Puedes desactivar la recuperación en Ajustes."))).pack(side="bottom", fill="x", pady=(8, 0))
        # Olvidar lo pendiente del tema elegido.
        ttk.Button(progreso_, text="Olvidar lo pendiente del tema elegido",
                   command=self.olvidar).pack(side="bottom", anchor="w", pady=(8, 0))
        # Tabla de progreso por tema (ocupa lo que queda).
        self.tabla_progreso = ttk.Treeview(progreso_, columns=("tema", "hechas", "no", "sin", "cumplido", "pendiente"),
                                           show="headings", height=5, selectmode="browse")
        # Títulos y anchos de las columnas ("%" = porcentaje de sesiones hechas entre las marcadas).
        for columna, titulo, ancho in (("tema", "Tema", 100), ("hechas", "Hechas", 68), ("no", "No hechas", 88),
                                       ("sin", "Sin marcar", 92), ("cumplido", "%", 50),
                                       ("pendiente", "Recuperar", 86)):
            # Título.
            self.tabla_progreso.heading(columna, text=titulo, anchor="w")
            # Ancho.
            self.tabla_progreso.column(columna, width=int(ancho * app.escala), anchor="w")
        # Ocupa el espacio disponible.
        self.tabla_progreso.pack(fill="both", expand=True)

    def refrescar(self):
        """Vuelve a llenar las metas y el progreso."""
        # Fecha y hora actuales.
        ahora = datetime.now()
        # Temas guardados (lista vacía si el archivo está mal).
        try:
            # Temas.
            temas = almacen.cargar_temas()
        # Archivo mal escrito.
        except almacen.ErrorPlanificador:
            # Sin temas.
            temas = []
        # Opciones de tema para una meta nueva.
        self.tema.configure(values=["(ninguno)"] + [t["nombre"] for t in temas])
        # Si no hay ninguno elegido, "(ninguno)".
        if self.tema.get() not in self.tema.cget("values"):
            # Primera opción.
            self.tema.current(0)
        # Metas guardadas.
        try:
            # Metas.
            metas = almacen.cargar_metas()
        # Archivo mal escrito.
        except almacen.ErrorPlanificador as error:
            # Lo avisamos.
            self.app.avisar(str(error), error=True)
            # Sin metas.
            metas = []
        # Meta y tema elegidos antes (para volver a elegirlos después de redibujar).
        elegida, tema_elegido = self.tabla.selection(), self.tabla_progreso.selection()
        # Vaciamos la tabla.
        self.tabla.delete(*self.tabla.get_children())
        # Pendientes primero, luego por fecha.
        for meta in sorted(metas, key=lambda m: (bool(m.get("cumplida")), m.get("fecha") or "9999")):
            # Fecha (si tiene).
            fecha = date.fromisoformat(meta["fecha"]) if meta.get("fecha") else None
            # Etiqueta: cumplida, o cercana (próximos 7 días).
            etiqueta = "cumplida" if meta.get("cumplida") else (
                "cerca" if fecha and 0 <= (fecha - ahora.date()).days <= 7 else "")
            # Fila; su identificador es el número de la meta.
            self.tabla.insert("", "end", iid=str(meta["id"]), tags=(etiqueta,), values=(
                meta["texto"], meta.get("tema") or "—", f"{fecha:%d/%m/%Y}" if fecha else "—",
                self._texto_estado(meta, fecha, ahora.date())))
        # Progreso de los últimos días.
        datos = progreso.resumen(self.app.registro(), self.app.plan, temas, ahora)
        # Racha.
        self.racha.configure(text=f"Racha: {datos['racha']} {'día' if datos['racha'] == 1 else 'días'} seguidos estudiando")
        # Totales.
        marcadas = datos["hechas"] + datos["no_hechas"]
        # Texto de los totales.
        self.totales.configure(text=f"{datos['hechas']} sesiones hechas y {datos['no_hechas']} no hechas"
                                    f"{' (' + str(round(100 * datos['hechas'] / marcadas)) + ' % cumplido)' if marcadas else ''}.")
        # Vaciamos la tabla de progreso.
        self.tabla_progreso.delete(*self.tabla_progreso.get_children())
        # Una fila por tema.
        for fila in datos["temas"]:
            # Fila; su identificador es el nombre del tema.
            self.tabla_progreso.insert("", "end", iid=fila["tema"], values=(
                fila["tema"], fila["hechas"], fila["no_hechas"], fila["sin_marcar"],
                f"{fila['cumplimiento']} %" if fila["cumplimiento"] is not None else "—",
                minutos_a_texto(fila["pendiente"]) if fila["pendiente"] else "—"))
        # Volvemos a elegir lo que estaba elegido (si sigue existiendo).
        for tabla, filas in ((self.tabla, elegida), (self.tabla_progreso, tema_elegido)):
            # Solo las filas que siguen en la tabla.
            existentes = [fila for fila in filas if tabla.exists(fila)]
            # Las elegimos.
            if existentes:
                # Selección.
                tabla.selection_set(existentes)

    @staticmethod
    def _texto_estado(meta, fecha, hoy):
        """Estado corto de una meta: «Cumplida», «Hoy», «Mañana», «En 5 días», «Pasó» o «Pendiente»."""
        # Cumplida.
        if meta.get("cumplida"):
            # Texto.
            return "Cumplida"
        # Sin fecha.
        if fecha is None:
            # Texto.
            return "Pendiente"
        # Días que faltan.
        faltan = (fecha - hoy).days
        # Según los días.
        return {0: "Hoy", 1: "Mañana"}.get(faltan, f"En {faltan} días" if faltan > 1 else "Pasó")

    @con_avisos
    def guardar(self):
        """Guarda la meta escrita en el formulario."""
        # Metas guardadas.
        metas = almacen.cargar_metas()
        # Tema elegido ("(ninguno)" = sin tema).
        tema = self.tema.get() if self.tema.current() > 0 else None
        # Nueva meta (aquí se revisa el texto, el tema y la fecha).
        meta = progreso.agregar_meta(metas, self.texto.get(), tema, self.fecha.get().strip() or None,
                                     almacen.cargar_temas())
        # Guardamos.
        almacen.guardar_metas(metas)
        # Vaciamos el formulario.
        self.texto.set("")
        # Fecha vacía.
        self.fecha.set("")
        # Si cambia el plan, conviene generarlo otra vez.
        if meta["tema"] and meta["fecha"]:
            # Plan desactualizado.
            self.app.plan_desactualizado = True
        # Redibujamos.
        self.app.refrescar_todo()
        # Mensaje abajo.
        self.app.avisar(f"Meta guardada: {progreso.texto_meta(meta)}."
                        f"{' Pulsa «Generar plan» en la sección Semana para adaptar el plan.' if self.app.plan_desactualizado else ''}")

    def _meta_elegida(self):
        """Número de la meta elegida en la tabla, o None (avisando) si no hay ninguna."""
        # Fila elegida.
        elegidas = self.tabla.selection()
        # Si no hay, lo explicamos.
        if not elegidas:
            # Aviso.
            messagebox.showinfo("Elige una meta", "Primero haz clic en una meta de la lista.", parent=self.winfo_toplevel())
            # Ninguna.
            return None
        # Su número.
        return int(elegidas[0])

    @con_avisos
    def alternar(self):
        """Marca la meta elegida como cumplida, o como pendiente si ya lo estaba."""
        # Meta elegida.
        numero = self._meta_elegida()
        # Si no hay, terminamos.
        if numero is None:
            # Nada.
            return
        # Metas guardadas.
        metas = almacen.cargar_metas()
        # Cambiamos su estado.
        meta = progreso.cumplir_meta(metas, numero, not progreso.buscar_meta(metas, numero).get("cumplida"))
        # Guardamos.
        almacen.guardar_metas(metas)
        # Redibujamos.
        self.refrescar()
        # Mensaje abajo.
        self.app.avisar(f"«{meta['texto']}»: {'¡cumplida! Bien hecho.' if meta['cumplida'] else 'pendiente otra vez.'}")

    @con_avisos
    def quitar(self):
        """Quita la meta elegida (después de preguntar)."""
        # Meta elegida.
        numero = self._meta_elegida()
        # Si no hay, terminamos.
        if numero is None:
            # Nada.
            return
        # Metas guardadas.
        metas = almacen.cargar_metas()
        # Texto de la meta.
        texto = progreso.buscar_meta(metas, numero)["texto"]
        # Confirmación.
        if not messagebox.askyesno("Quitar meta", f"¿Quitar la meta «{texto}»?", parent=self.winfo_toplevel()):
            # No.
            return
        # La quitamos.
        progreso.quitar_meta(metas, numero)
        # Guardamos.
        almacen.guardar_metas(metas)
        # Redibujamos.
        self.refrescar()
        # Mensaje abajo.
        self.app.avisar(f"Meta quitada: «{texto}».")

    @con_avisos
    def olvidar(self):
        """Deja de recuperar lo pendiente del tema elegido en la tabla de progreso."""
        # Fila elegida.
        elegidas = self.tabla_progreso.selection()
        # Si no hay, lo explicamos.
        if not elegidas:
            # Aviso.
            messagebox.showinfo("Elige un tema", "Primero haz clic en un tema de la tabla de progreso.",
                                parent=self.winfo_toplevel())
            # Terminamos.
            return
        # Tema elegido.
        tema = elegidas[0]
        # Confirmación.
        if not messagebox.askyesno("Olvidar lo pendiente", f"¿Dejar de recuperar lo pendiente de «{tema}»?\n\n"
                                   "Lo que marques a partir de ahora sí contará.", parent=self.winfo_toplevel()):
            # No.
            return
        # Registro de lo hecho.
        registro = almacen.cargar_registro()
        # Olvidamos.
        progreso.olvidar_pendiente(registro, tema)
        # Guardamos.
        almacen.guardar_registro(registro)
        # Redibujamos.
        self.app.refrescar_progreso()
        # Mensaje abajo.
        self.app.avisar(f"Ya no se recupera lo pendiente de «{tema}».")


def texto_plano(texto):
    """Quita el formato Markdown más común (**negrita**, # títulos, - listas) para mostrarlo en la ventana."""
    # Líneas resultantes.
    lineas = []
    # Cada línea.
    for linea in texto.splitlines():
        # Sin espacios a la izquierda, para mirar cómo empieza.
        limpia = linea.lstrip()
        # Títulos "# ...": solo el texto.
        if limpia.startswith("#"):
            # Sin almohadillas.
            linea = limpia.lstrip("#").strip()
        # Listas "- ..." o "* ...": con viñeta.
        elif limpia.startswith(("- ", "* ")):
            # Viñeta.
            linea = "  •  " + limpia[2:]
        # Sin asteriscos ni guiones bajos dobles de negrita.
        lineas.append(linea.replace("**", "").replace("__", ""))
    # Todo junto.
    return "\n".join(lineas).strip()


class PestanaAsistente(ttk.Frame):
    """Sección "Asistente": habla con Claude o Gemini sobre tu estudio (puede cambiar temas, metas y plan)."""

    # Ejemplos de lo que se le puede decir.
    EJEMPLOS = ["¿Cómo voy esta semana?", "Hoy no pude estudiar", "Tengo un examen el viernes",
                "Ajusta el plan a lo que de verdad hago"]
    # Saludo al empezar una conversación.
    SALUDO = ("Hola. Te ayudo a organizar tus metas y a ajustar el plan a lo que de verdad haces. Cuéntame cómo te "
              "fue hoy, si tienes algún examen o entrega, o pregúntame cómo vas.")

    def __init__(self, padre, app):
        # Marco de la pestaña con margen interior.
        super().__init__(padre, padding=(28, 22))
        # Referencia a la ventana principal.
        self.app = app
        # Conversación en curso (se crea al enviar el primer mensaje).
        self.conversacion = None
        # Fila del título y los botones.
        arriba = ttk.Frame(self)
        # Ocupa el ancho.
        arriba.pack(fill="x")
        # Título.
        ttk.Label(arriba, text="Asistente", style="Titulo.TLabel").pack(side="left")
        # Cambiar de IA o de clave.
        ttk.Button(arriba, text="Cambiar IA o clave", command=self.mostrar_configuracion).pack(side="right")
        # Empezar de cero.
        ttk.Button(arriba, text="Nueva conversación", command=self.nueva).pack(side="right", padx=8)
        # Qué IA se está usando.
        self.usando = ttk.Label(self, style="Suave.TLabel")
        # Debajo del título.
        self.usando.pack(anchor="w", pady=(2, 12))
        # --- Modo chat ---
        self.chat = ttk.Frame(self)
        # Fila para escribir (abajo del todo; se coloca primero para que nunca quede fuera de la vista).
        fila = ttk.Frame(self.chat)
        # Abajo.
        fila.pack(side="bottom", fill="x")
        # Texto que escribe el usuario.
        self.entrada = ttk.Entry(fila)
        # Ocupa casi todo el ancho.
        self.entrada.pack(side="left", fill="x", expand=True)
        # Enter envía.
        self.entrada.bind("<Return>", lambda _evento: self.enviar())
        # Botón de enviar.
        self.boton_enviar = ttk.Button(fila, text="Enviar", style="Acento.TButton", command=self.enviar)
        # A la derecha.
        self.boton_enviar.pack(side="right", padx=(8, 0))
        # Fila de ejemplos (encima de la casilla).
        ejemplos = ttk.Frame(self.chat)
        # Abajo, sobre la casilla.
        ejemplos.pack(side="bottom", fill="x", pady=(10, 6))
        # Texto delante.
        ttk.Label(ejemplos, text="Prueba:", style="Suave.TLabel").pack(side="left", padx=(0, 6))
        # Un botón por ejemplo: rellena la casilla.
        for ejemplo in self.EJEMPLOS:
            # Botón pequeño.
            ttk.Button(ejemplos, text=ejemplo, style="Marca.TButton",
                       command=lambda t=ejemplo: self._usar_ejemplo(t)).pack(side="left", padx=(0, 6))
        # Marco del texto con su barra (ocupa lo que queda).
        marco_texto = ttk.Frame(self.chat)
        # Todo el espacio restante.
        marco_texto.pack(fill="both", expand=True)
        # Conversación (solo lectura; height pequeño: crece con la ventana).
        self.texto = tk.Text(marco_texto, wrap="word", relief="flat", background=COLOR_TARJETA, foreground=COLOR_TEXTO,
                             font=app.fuentes["normal"], padx=16, pady=12, highlightthickness=1, height=8,
                             highlightbackground=COLOR_BORDE, state="disabled", spacing3=4)
        # Barra del texto.
        barra = ttk.Scrollbar(marco_texto, orient="vertical", command=self.texto.yview)
        # Unimos el texto con su barra.
        self.texto.configure(yscrollcommand=barra.set)
        # Barra a la derecha.
        barra.pack(side="right", fill="y")
        # Texto en el resto.
        self.texto.pack(side="left", fill="both", expand=True)
        # Estilos del texto: quién habla, mensajes, acciones y errores.
        self.texto.tag_configure("nombre_tu", font=app.fuentes["negrita"], foreground=COLOR_ACENTO, spacing1=10)
        # Nombre del asistente.
        self.texto.tag_configure("nombre_ia", font=app.fuentes["negrita"], foreground=COLOR_BIEN, spacing1=10)
        # Acciones que hizo el asistente.
        self.texto.tag_configure("accion", font=app.fuentes["pequena"], foreground=COLOR_SUAVE, lmargin1=14, lmargin2=14)
        # Errores.
        self.texto.tag_configure("error", foreground=COLOR_MAL, spacing1=8)
        # "Pensando…".
        self.texto.tag_configure("pensando", font=app.fuentes["pequena"], foreground=COLOR_SUAVE, spacing1=6)
        # --- Modo configuración ---
        self.ajuste = ttk.Frame(self)
        # Tarjeta de configuración.
        marco, contenido = tarjeta(self.ajuste, "Elige la inteligencia artificial y pon tu clave")
        # Arriba.
        marco.pack(fill="x")
        # Explicación (incluye qué datos se envían).
        ajustar_al_ancho(ttk.Label(contenido, style="Tarjeta.TLabel", justify="left", text=(
            "El asistente lee tus temas, tu plan, lo que has hecho y tus metas, y puede cambiarlos cuando se lo pidas. "
            "Lo que escribes aquí y esos datos se envían a la IA que elijas. La clave se guarda solo en este "
            "ordenador (datos/claves.json)."))).pack(fill="x", pady=(0, 12))
        # IA elegida.
        self.proveedor = tk.StringVar(value="gemini")
        # Opción Gemini.
        ttk.Radiobutton(contenido, variable=self.proveedor, value="gemini", style="Tarjeta.TRadiobutton",
                        command=self._al_cambiar_proveedor,
                        text="Gemini (Google): tiene un nivel gratuito con límites. Clave en aistudio.google.com").pack(
            anchor="w")
        # Opción Claude.
        ttk.Radiobutton(contenido, variable=self.proveedor, value="claude", style="Tarjeta.TRadiobutton",
                        command=self._al_cambiar_proveedor,
                        text="Claude (Anthropic): de pago según el uso, con saldo previo. Clave en platform.claude.com").pack(
            anchor="w", pady=(4, 12))
        # Título de la clave.
        ttk.Label(contenido, text="Clave", style="Tarjeta.TLabel").pack(anchor="w")
        # Clave escrita (se muestra con puntos).
        self.clave = tk.StringVar()
        # Casilla de la clave.
        ttk.Entry(contenido, textvariable=self.clave, show="•").pack(fill="x", pady=(4, 2))
        # Ayuda sobre la clave.
        self.ayuda_clave = ttk.Label(contenido, style="TarjetaSuave.TLabel")
        # Debajo.
        self.ayuda_clave.pack(anchor="w", pady=(0, 10))
        # Título del modelo.
        ttk.Label(contenido, text="Modelo", style="Tarjeta.TLabel").pack(anchor="w")
        # Modelo escrito.
        self.modelo = tk.StringVar()
        # Casilla del modelo.
        ttk.Entry(contenido, textvariable=self.modelo, width=30).pack(anchor="w", pady=(4, 2))
        # Ayuda sobre el modelo.
        ttk.Label(contenido, text="Déjalo como está si no sabes cuál elegir.", style="TarjetaSuave.TLabel").pack(
            anchor="w", pady=(0, 14))
        # Fila de botones.
        botones = ttk.Frame(contenido, style="Tarjeta.TFrame")
        # Abajo.
        botones.pack(fill="x")
        # Guardar.
        ttk.Button(botones, text="Guardar y empezar", style="Acento.TButton",
                   command=self.guardar_configuracion).pack(side="left")
        # Abrir la guía (paso 7).
        ttk.Button(botones, text="Cómo conseguir la clave",
                   command=lambda: webbrowser.open(URL_GUIA + "#paso-7-activar-el-asistente-opcional")).pack(
            side="left", padx=8)
        # Volver al chat sin cambiar nada.
        self.boton_volver = ttk.Button(botones, text="Volver al chat", command=self.mostrar_chat)
        # A la derecha de los demás.
        self.boton_volver.pack(side="left")
        # Saludo inicial.
        self._agregar("Asistente", self.SALUDO, "ia")
        # Empezamos en modo chat.
        self.chat.pack(fill="both", expand=True)

    def refrescar(self):
        """Actualiza qué IA se usa y, si falta la clave, muestra la configuración."""
        # Ajustes.
        config = self.app.config_o_defecto()
        # IA elegida.
        proveedor = config["asistente"]
        # ¿Tiene clave?
        try:
            # Clave (vacía si no hay).
            clave = asistente.clave_de(proveedor)
        # Archivo de claves mal escrito.
        except almacen.ErrorPlanificador:
            # Sin clave.
            clave = ""
        # Texto con la IA y el modelo.
        self.usando.configure(text=f"Usando {asistente.NOMBRES[proveedor]} ({config['modelo_' + proveedor]}). "
                                   "Puede consultar y cambiar tus temas, metas, horario y plan."
                                   if clave else "Todavía no has elegido una IA ni puesto su clave.")
        # Sin clave: configuración.
        if not clave and not self.ajuste.winfo_manager():
            # La mostramos.
            self.mostrar_configuracion()

    def mostrar_configuracion(self):
        """Cambia al modo de configuración, con los valores actuales."""
        # Ajustes.
        config = self.app.config_o_defecto()
        # IA elegida.
        self.proveedor.set(config["asistente"])
        # Modelo y ayuda según la IA.
        self._al_cambiar_proveedor()
        # Escondemos el chat.
        self.chat.pack_forget()
        # Mostramos la configuración.
        self.ajuste.pack(fill="both", expand=True)

    def mostrar_chat(self):
        """Vuelve al modo chat."""
        # Escondemos la configuración.
        self.ajuste.pack_forget()
        # Mostramos el chat.
        self.chat.pack(fill="both", expand=True)
        # El cursor va a la casilla de escribir.
        self.entrada.focus_set()

    def _al_cambiar_proveedor(self):
        """Pone el modelo de la IA elegida y dice si ya tiene clave."""
        # Ajustes.
        config = self.app.config_o_defecto()
        # IA elegida.
        proveedor = self.proveedor.get()
        # Su modelo.
        self.modelo.set(config["modelo_" + proveedor])
        # ¿Tiene clave?
        try:
            # Clave guardada (o vacía).
            tiene = bool(asistente.clave_de(proveedor))
        # Archivo de claves mal escrito.
        except almacen.ErrorPlanificador:
            # Sin clave.
            tiene = False
        # Ayuda.
        self.ayuda_clave.configure(text="Ya hay una clave guardada: déjalo vacío para conservarla." if tiene else
                                   "Pega aquí la clave (la guía de inicio, paso 7, explica cómo conseguirla).")

    @con_avisos
    def guardar_configuracion(self):
        """Guarda la IA elegida, su modelo y (si se escribió) su clave."""
        # IA elegida.
        proveedor = self.proveedor.get()
        # Clave escrita.
        clave = self.clave.get().strip()
        # Sin clave escrita ni guardada no se puede usar.
        if not clave and not asistente.clave_de(proveedor):
            # Error para el usuario.
            raise almacen.ErrorPlanificador(f"Pega tu clave de {asistente.NOMBRES[proveedor]}. "
                                            "Pulsa «Cómo conseguir la clave» si no la tienes.")
        # Si se escribió, la guardamos.
        if clave:
            # En datos/claves.json.
            almacen.guardar_clave(proveedor, clave)
        # Ajustes con la IA y el modelo elegidos.
        config = {**self.app.config_o_defecto(), "asistente": proveedor,
                  "modelo_" + proveedor: self.modelo.get().strip() or almacen.CONFIG_POR_DEFECTO["modelo_" + proveedor]}
        # Los guardamos (aquí se revisan).
        almacen.guardar_config(config)
        # Vaciamos la casilla de la clave.
        self.clave.set("")
        # La próxima conversación usará la nueva configuración.
        self.conversacion = None
        # Actualizamos el texto de arriba.
        self.refrescar()
        # Volvemos al chat.
        self.mostrar_chat()
        # Lo apuntamos en la conversación.
        self._agregar("Asistente", f"Listo: ahora hablas con {asistente.NOMBRES[proveedor]}. ¿En qué te ayudo?", "ia")

    def nueva(self):
        """Empieza una conversación nueva (el asistente olvida esta, pero no sus notas guardadas)."""
        # Sin conversación.
        self.conversacion = None
        # Permitimos editar el texto.
        self.texto.configure(state="normal")
        # Lo borramos.
        self.texto.delete("1.0", "end")
        # Volvemos a bloquearlo.
        self.texto.configure(state="disabled")
        # Saludo.
        self._agregar("Asistente", self.SALUDO, "ia")

    def _agregar(self, quien, mensaje, etiqueta):
        """Añade un mensaje a la conversación con el nombre de quien habla."""
        # Permitimos escribir.
        self.texto.configure(state="normal")
        # Nombre.
        self.texto.insert("end", f"{quien}\n", ("nombre_tu" if etiqueta == "tu" else "nombre_ia",))
        # Mensaje.
        self.texto.insert("end", f"{mensaje.strip()}\n", (etiqueta,))
        # Volvemos a bloquearlo.
        self.texto.configure(state="disabled")
        # Bajamos hasta el final.
        self.texto.see("end")

    def _usar_ejemplo(self, ejemplo):
        """Pone un ejemplo en la casilla para que el usuario lo complete o lo envíe."""
        # Vaciamos la casilla.
        self.entrada.delete(0, "end")
        # Ponemos el ejemplo.
        self.entrada.insert(0, ejemplo)
        # El cursor al final.
        self.entrada.focus_set()

    def escribir(self, linea):
        """Apunta una acción del asistente (por ejemplo, «Meta guardada: ...»)."""
        # Permitimos escribir.
        self.texto.configure(state="normal")
        # Línea pequeña en gris.
        self.texto.insert("end", f"·  {linea}\n", ("accion",))
        # Volvemos a bloquearlo.
        self.texto.configure(state="disabled")
        # Bajamos hasta el final.
        self.texto.see("end")

    def ocupado(self, si):
        """Mientras la IA piensa: «Pensando…» y la casilla bloqueada."""
        # Permitimos escribir en la conversación.
        self.texto.configure(state="normal")
        # Si empieza a pensar...
        if si:
            # ...lo decimos.
            self.texto.insert("end", "Pensando…\n", ("pensando",))
        # Si terminó...
        else:
            # ...quitamos el «Pensando…» (de atrás hacia delante para no mover los índices).
            rangos = self.texto.tag_ranges("pensando")
            # Cada par (inicio, fin).
            for posicion in range(len(rangos) - 2, -1, -2):
                # Lo borramos.
                self.texto.delete(rangos[posicion], rangos[posicion + 1])
        # Volvemos a bloquearlo.
        self.texto.configure(state="disabled")
        # Bajamos hasta el final.
        self.texto.see("end")
        # Casilla y botón bloqueados mientras piensa.
        for control in (self.entrada, self.boton_enviar):
            # Estado.
            control.state(["disabled"] if si else ["!disabled"])
        # Al terminar, el cursor vuelve a la casilla.
        if not si:
            # Foco.
            self.entrada.focus_set()

    def informar_error(self, texto):
        """Muestra un error en la conversación (y la configuración, si falta la clave)."""
        # Mensaje en rojo.
        self._agregar("Asistente", f"No pude responder: {texto}", "error")
        # Si falta la clave o es incorrecta, mostramos la configuración.
        if "clave" in texto.lower():
            # Configuración.
            self.mostrar_configuracion()

    def enviar(self):
        """Envía lo escrito a la IA (en segundo plano) y muestra su respuesta."""
        # Texto escrito.
        texto = self.entrada.get().strip()
        # Si está vacío o la IA está pensando, no hacemos nada.
        if not texto or "disabled" in self.boton_enviar.state():
            # Nada.
            return
        # Vaciamos la casilla.
        self.entrada.delete(0, "end")
        # Mostramos el mensaje del usuario.
        self._agregar("Tú", texto, "tu")
        # Conversación actual (None la primera vez).
        conversacion = self.conversacion
        # Cola por la que se avisa de cada acción.
        cola = self.app.cola

        def tarea():
            # La primera vez se crea la conversación (con la IA y la clave elegidas).
            actual = conversacion or asistente.crear_conversacion()
            # Respuesta (cada acción se avisa por la cola, porque aquí no se puede tocar la ventana).
            return actual, actual.enviar(texto, avisar=lambda linea: cola.put(("registro", self, linea)))

        # En segundo plano, para que la ventana no se congele mientras la IA piensa.
        self.app.en_segundo_plano(tarea, self._tras_responder, pestana=self, capturar_salida=False)

    def _tras_responder(self, resultado):
        """Muestra la respuesta y actualiza las demás secciones (la IA pudo cambiar datos)."""
        # Conversación (para seguir) y respuesta.
        self.conversacion, respuesta = resultado
        # Mostramos la respuesta sin formato Markdown.
        self._agregar("Asistente", texto_plano(respuesta), "ia")
        # Redibujamos lo demás.
        self.app.refrescar_todo(salvo=self)


class PestanaGoogle(ttk.Frame):
    """Sección "Google Calendar": estado de la conexión, subir el plan y borrar sesiones."""

    def __init__(self, padre, app):
        # Marco de la pestaña con margen interior.
        super().__init__(padre, padding=(28, 22))
        # Referencia a la ventana principal.
        self.app = app
        # Título.
        ttk.Label(self, text="Google Calendar", style="Titulo.TLabel").pack(anchor="w")
        # Explicación breve.
        ttk.Label(self, text="Sube tu plan al calendario para que el teléfono te avise antes de cada sesión.",
                  style="Suave.TLabel").pack(anchor="w", pady=(2, 14))
        # Contenedor de las dos tarjetas de arriba.
        arriba = ttk.Frame(self)
        # Ocupa todo el ancho.
        arriba.pack(fill="x")
        # Las dos columnas crecen igual.
        arriba.columnconfigure((0, 1), weight=1, uniform="google")
        # Tarjeta 1: estado de la conexión.
        marco_estado, tarjeta_estado = tarjeta(arriba, "1. Conexión")
        # A la izquierda.
        marco_estado.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        # Marco donde se dibujan las comprobaciones.
        self.lineas_estado = ttk.Frame(tarjeta_estado, style="Tarjeta.TFrame")
        # Ocupa la tarjeta.
        self.lineas_estado.pack(fill="x")
        # Botones de la tarjeta de conexión.
        botones_estado = ttk.Frame(tarjeta_estado, style="Tarjeta.TFrame")
        # Debajo de las comprobaciones.
        botones_estado.pack(fill="x", pady=(10, 0))
        # Volver a comprobar (por ejemplo, después de poner credentials.json).
        ttk.Button(botones_estado, text="Comprobar otra vez", command=self.refrescar).pack(side="left")
        # Abrir la guía en el navegador.
        ttk.Button(botones_estado, text="Abrir la guía de inicio",
                   command=lambda: webbrowser.open(URL_GUIA)).pack(side="left", padx=(8, 0))
        # Tarjeta 2: el plan y los botones.
        marco_plan, tarjeta_plan = tarjeta(arriba, "2. Tu plan")
        # A la derecha.
        marco_plan.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        # Descripción del plan que se subiría.
        self.info_plan = ajustar_al_ancho(ttk.Label(tarjeta_plan, style="Tarjeta.TLabel", justify="left", anchor="w"))
        # Arriba de la tarjeta.
        self.info_plan.pack(fill="x")
        # Fila de botones.
        botones = ttk.Frame(tarjeta_plan, style="Tarjeta.TFrame")
        # Debajo de la descripción.
        botones.pack(fill="x", pady=(14, 0))
        # Subir el plan.
        self.boton_subir = ttk.Button(botones, text="Subir al calendario", style="Acento.TButton", command=self.subir)
        # A la izquierda.
        self.boton_subir.pack(side="left")
        # Ver qué se subiría, sin conectar.
        self.boton_simular = ttk.Button(botones, text="Ver qué se subiría", command=self.simular)
        # Al lado.
        self.boton_simular.pack(side="left", padx=(8, 0))
        # Borrar del calendario las sesiones del plan.
        self.boton_borrar = ttk.Button(tarjeta_plan, text="Borrar del calendario las sesiones de estas fechas",
                                       style="Peligro.TButton", command=self.borrar)
        # Debajo.
        self.boton_borrar.pack(anchor="w", pady=(8, 0))
        # Barra de progreso (se mueve mientras se habla con Google; vacía el resto del tiempo).
        self.progreso = ttk.Progressbar(self, mode="determinate", value=0)
        # Debajo de las tarjetas.
        self.progreso.pack(fill="x", pady=(16, 6))
        # Título del registro.
        ttk.Label(self, text="Registro", style="Negrita.TLabel").pack(anchor="w")
        # Marco del registro con su barra.
        marco_registro = ttk.Frame(self)
        # Ocupa el resto de la pestaña.
        marco_registro.pack(fill="both", expand=True, pady=(4, 0))
        # Cuadro de texto donde se apunta lo que va pasando.
        self.registro = tk.Text(marco_registro, height=8, wrap="word", relief="flat", background=COLOR_TARJETA,
                                foreground=COLOR_TEXTO, font=app.fuentes["normal"], padx=12, pady=10,
                                highlightthickness=1, highlightbackground=COLOR_BORDE, state="disabled")
        # Barra del registro.
        barra = ttk.Scrollbar(marco_registro, orient="vertical", command=self.registro.yview)
        # Unimos el texto con su barra.
        self.registro.configure(yscrollcommand=barra.set)
        # Barra a la derecha.
        barra.pack(side="right", fill="y")
        # Texto en el resto.
        self.registro.pack(side="left", fill="both", expand=True)

    def escribir(self, texto):
        """Añade una línea al registro (con la hora delante)."""
        # Permitimos escribir.
        self.registro.configure(state="normal")
        # Añadimos la línea al final.
        self.registro.insert("end", f"{datetime.now():%H:%M}  {texto}\n")
        # Bajamos hasta el final.
        self.registro.see("end")
        # Volvemos a bloquearlo para que no se edite a mano.
        self.registro.configure(state="disabled")

    def informar_error(self, texto):
        """Muestra un error de Google: en el registro y en una ventanita."""
        # En el registro.
        self.escribir(f"Error: {texto}")
        # Ventanita.
        messagebox.showerror("No se pudo completar", texto, parent=self.winfo_toplevel())

    def ocupado(self, si):
        """Bloquea los botones y mueve la barra mientras se habla con Google."""
        # Estado de los botones.
        estado = ["disabled"] if si else ["!disabled"]
        # Aplicamos el estado a cada botón.
        for boton in (self.boton_subir, self.boton_simular, self.boton_borrar):
            # Cambiamos su estado.
            boton.state(estado)
        # Si está ocupado...
        if si:
            # ...la barra se mueve de un lado a otro.
            self.progreso.configure(mode="indeterminate")
            # La ponemos en marcha.
            self.progreso.start(12)
        # Si no...
        else:
            # ...se para.
            self.progreso.stop()
            # Y queda vacía.
            self.progreso.configure(mode="determinate", value=0)

    def refrescar(self):
        """Comprueba qué falta para conectar y describe el plan que se subiría."""
        # Quitamos las comprobaciones anteriores.
        for hijo in self.lineas_estado.winfo_children():
            # La borramos.
            hijo.destroy()
        # ¿Están las librerías?
        librerias = calendario_google.hay_librerias()
        # ¿Está credentials.json?
        credenciales = calendario_google.ARCHIVO_CREDENCIALES.exists()
        # ¿Ya se inició sesión alguna vez?
        sesion = calendario_google.ARCHIVO_TOKEN.exists()
        # Si falta credentials.json, ¿hay un archivo parecido con otro nombre?
        parecidos = [] if credenciales else calendario_google.credenciales_con_otro_nombre(calendario_google.CARPETA_APP)
        # Ayuda para credentials.json según el caso.
        ayuda_credenciales = (f"Encontré «{parecidos[0]}»: cámbiale el nombre a credentials.json." if parecidos else
                              "Descárgalo de Google Cloud siguiendo el paso 4 de la guía de inicio y ponlo en la "
                              "carpeta del programa.")
        # Las tres comprobaciones: (¿bien?, texto, ayuda si falta, ¿es grave que falte?).
        comprobaciones = [
            # Librerías.
            (librerias, "Librerías de Google instaladas",
             "Abre la terminal en la carpeta del programa y escribe:  python -m pip install -r requirements.txt", True),
            # Credenciales.
            (credenciales, "Archivo credentials.json en la carpeta", ayuda_credenciales, True),
            # Sesión.
            (sesion, "Sesión iniciada con Google",
             "La primera vez que subas el plan se abrirá el navegador para dar permiso.", False),
        ]
        # Dibujamos cada comprobación.
        for bien, texto, ayuda, grave in comprobaciones:
            # Fila de la comprobación.
            fila = tk.Frame(self.lineas_estado, background=COLOR_TARJETA)
            # Ocupa el ancho.
            fila.pack(fill="x", pady=3)
            # Color del punto: verde si está bien, rojo si falta algo necesario y gris si es solo un aviso.
            color = COLOR_BIEN if bien else (COLOR_MAL if grave else "#b0b6c0")
            # Tamaño del punto según la escala de la pantalla.
            lado = int(18 * self.app.escala)
            # Dibujamos el punto en un pequeño lienzo (se ve igual con cualquier fuente de letra).
            punto = tk.Canvas(fila, width=lado, height=lado, background=COLOR_TARJETA, highlightthickness=0)
            # Círculo de color.
            punto.create_oval(3, 3, lado - 3, lado - 3, fill=color, outline=color)
            # A la izquierda, arriba.
            punto.pack(side="left", anchor="n", padx=(0, 8), pady=1)
            # Textos a la derecha.
            textos = tk.Frame(fila, background=COLOR_TARJETA)
            # Ocupan el resto.
            textos.pack(side="left", fill="x", expand=True)
            # Texto de la comprobación, con "listo" o "falta" al final.
            ajustar_al_ancho(tk.Label(textos, text=f"{texto}: {'listo' if bien else 'falta'}", anchor="w",
                                      font=self.app.fuentes["normal"], background=COLOR_TARJETA, foreground=COLOR_TEXTO,
                                      justify="left")).pack(fill="x")
            # Si falta, explicamos qué hacer.
            if not bien:
                # Ayuda en gris, debajo.
                ajustar_al_ancho(tk.Label(textos, text=ayuda, font=self.app.fuentes["pequena"], background=COLOR_TARJETA,
                                          foreground=COLOR_SUAVE, anchor="w", justify="left")).pack(fill="x")
        # Describimos el plan que se subiría.
        plan = self.app.plan
        # Ajustes (para el calendario y el aviso).
        try:
            # Ajustes actuales.
            config = almacen.cargar_config()
        # Si están mal, no podemos decir a qué calendario se sube.
        except almacen.ErrorPlanificador:
            # Sin ajustes.
            config = None
        # Sin plan.
        if plan is None:
            # Explicación.
            self.info_plan.configure(text="Todavía no hay plan. Genéralo en la sección Semana.")
        # Con plan.
        else:
            # Texto con las fechas y cuántas sesiones.
            texto = (f"Del {fecha_corta(plan['desde'])} al {fecha_corta(plan['hasta'])}: "
                     f"{len(plan['sesiones'])} sesiones.")
            # Si tenemos los ajustes, decimos dónde y con qué aviso.
            if config:
                # Calendario y aviso.
                texto += (f"\nSe crearán en el calendario «{config['id_calendario']}», cada una con aviso "
                          f"{config['aviso_minutos_antes']} min antes.")
            # Mostramos el texto.
            self.info_plan.configure(text=texto)

    @con_avisos
    def simular(self):
        """Apunta en el registro los eventos que se crearían, sin conectar con Google."""
        # Plan guardado (comprobando que tenga sesiones y no haya terminado).
        plan = planificador.cargar_plan_para_subir()
        # Minutos de aviso.
        aviso = almacen.cargar_config()["aviso_minutos_antes"]
        # Encabezado.
        self.escribir(f"Se crearían {len(plan['sesiones'])} eventos (sin conectar con Google):")
        # Un evento por línea.
        for sesion in plan["sesiones"]:
            # Convertimos la sesión en evento, igual que al subir de verdad.
            evento = calendario_google.evento_desde_sesion(sesion, aviso)
            # Día, hora y título.
            self.escribir(f"    {fecha_corta(sesion.inicio.date())}  {sesion.inicio:%H:%M}-{sesion.fin:%H:%M}  "
                          f"{evento['summary']}")

    @con_avisos
    def subir(self):
        """Crea las sesiones del plan en Google Calendar (preguntando si ya había otras en esas fechas)."""
        # Plan guardado (comprobando que tenga sesiones y no haya terminado).
        plan = planificador.cargar_plan_para_subir()
        # Ajustes (calendario y aviso).
        config = almacen.cargar_config()
        # Avisamos de lo que va a pasar.
        self.escribir("Conectando con Google Calendar… La primera vez se abre el navegador: elige tu cuenta y "
                      "acepta el permiso.")

        def tarea():
            # Conectamos (puede abrir el navegador).
            servicio = calendario_google.conectar()
            # Intentamos subir sin borrar nada.
            try:
                # Resultado: (creados, borrados).
                return "subido", calendario_google.subir_plan(servicio, config["id_calendario"], plan,
                                                              config["aviso_minutos_antes"])
            # Si ya había sesiones en esas fechas, hay que preguntar qué hacer.
            except calendario_google.YaHaySesiones as ya_hay:
                # Devolvemos lo necesario para preguntar.
                return "preguntar", servicio, ya_hay.cantidad

        # Lo hacemos en segundo plano para que la ventana no se congele.
        self.app.en_segundo_plano(tarea, lambda resultado: self._tras_subir(resultado, plan, config))

    def _tras_subir(self, resultado, plan, config):
        """Sigue con la subida cuando Google responde."""
        # Ya había sesiones en esas fechas.
        if resultado[0] == "preguntar":
            # Conexión ya abierta y cuántas sesiones había.
            _, servicio, cantidad = resultado
            # Preguntamos si reemplazarlas.
            reemplazar = messagebox.askyesno(
                "Ya hay sesiones subidas",
                f"En tu calendario ya hay {cantidad} sesiones del planificador entre el {fecha_corta(plan['desde'])} "
                f"y el {fecha_corta(plan['hasta'])}.\n\n¿Quieres borrarlas y subir el plan nuevo?\n"
                "(Tus otros eventos no se tocan.)", parent=self.winfo_toplevel())
            # Si dice que no, no subimos nada.
            if not reemplazar:
                # Lo apuntamos.
                self.escribir("No se subió nada: ya había sesiones en esas fechas.")
                # Terminamos.
                return
            # Lo apuntamos.
            self.escribir(f"Borrando las {cantidad} sesiones anteriores y subiendo el plan nuevo…")
            # Subimos reemplazando, también en segundo plano.
            self.app.en_segundo_plano(
                lambda: ("subido", calendario_google.subir_plan(servicio, config["id_calendario"], plan,
                                                                config["aviso_minutos_antes"], reemplazar=True)),
                lambda nuevo: self._tras_subir(nuevo, plan, config))
            # Terminamos (seguirá cuando Google responda).
            return
        # Se subió: cuántas se crearon y cuántas se borraron.
        creados, borrados = resultado[1]
        # Si se borraron sesiones viejas, lo apuntamos.
        if borrados:
            # Mensaje.
            self.escribir(f"Se borraron {borrados} sesiones anteriores del planificador en esas fechas.")
        # Resultado final.
        self.escribir(f"Listo: {creados} sesiones creadas en Google Calendar.")
        # Actualizamos el estado (ahora ya hay sesión iniciada).
        self.refrescar()
        # Ventanita de confirmación.
        messagebox.showinfo("¡Listo!", f"Se crearon {creados} sesiones en Google Calendar.\n\nCada una te avisará "
                                       f"{config['aviso_minutos_antes']} min antes en el teléfono (app Google Calendar "
                                       "con las notificaciones activadas).", parent=self.winfo_toplevel())

    @con_avisos
    def borrar(self):
        """Borra del calendario las sesiones de esta app en las fechas del plan (después de preguntar)."""
        # Fechas del plan guardado.
        desde, hasta = planificador.fechas_a_limpiar()
        # Ajustes (para saber qué calendario usar).
        config = almacen.cargar_config()
        # Pedimos confirmación.
        if not messagebox.askyesno(
                "Borrar sesiones",
                f"Se borrarán de Google Calendar las sesiones del planificador entre el {fecha_corta(desde)} y el "
                f"{fecha_corta(hasta)}.\n\nTus otros eventos no se tocan. ¿Seguir?", parent=self.winfo_toplevel()):
            # Si dice que no, no hacemos nada.
            return
        # Avisamos.
        self.escribir("Conectando con Google Calendar para borrar las sesiones…")
        # Lo hacemos en segundo plano.
        self.app.en_segundo_plano(
            lambda: (calendario_google.quitar_plan(calendario_google.conectar(), config["id_calendario"], desde, hasta)),
            lambda borrados: self._tras_borrar(borrados, desde, hasta))

    def _tras_borrar(self, borrados, desde, hasta):
        """Informa de cuántas sesiones se borraron."""
        # Lo apuntamos.
        self.escribir(f"Se borraron {borrados} sesiones del planificador entre el {fecha_corta(desde)} y el "
                      f"{fecha_corta(hasta)}.")
        # Actualizamos el estado.
        self.refrescar()


class PestanaAjustes(ttk.Frame):
    """Sección "Ajustes": edita config.json con casillas en vez de a mano."""

    def __init__(self, padre, app):
        # Marco de la pestaña.
        super().__init__(padre)
        # Referencia a la ventana principal.
        self.app = app
        # Todo va dentro de un marco desplazable por si la ventana es pequeña.
        desplazable = MarcoDesplazable(self)
        # Ocupa toda la pestaña.
        desplazable.pack(fill="both", expand=True)
        # Contenedor con margen.
        cuerpo = tk.Frame(desplazable.interior, background=COLOR_FONDO, padx=28, pady=22)
        # Ocupa el ancho.
        cuerpo.pack(fill="both", expand=True)
        # Fila del título y los botones (arriba, para que siempre se vean).
        arriba = tk.Frame(cuerpo, background=COLOR_FONDO)
        # Ocupa el ancho.
        arriba.pack(fill="x")
        # Título.
        ttk.Label(arriba, text="Ajustes", style="Titulo.TLabel").pack(side="left")
        # Volver a los valores de fábrica (a la derecha del todo).
        ttk.Button(arriba, text="Valores por defecto", command=self.por_defecto).pack(side="right")
        # Deshacer los cambios no guardados.
        ttk.Button(arriba, text="Deshacer cambios", command=self.refrescar).pack(side="right", padx=8)
        # Guardar.
        ttk.Button(arriba, text="Guardar ajustes", style="Acento.TButton", command=self.guardar).pack(side="right")
        # Dónde se guardan.
        ttk.Label(cuerpo, text=f"Se guardan en {almacen.ARCHIVO_CONFIG.name}, en la carpeta del programa.", style="Suave.TLabel").pack(
            anchor="w", pady=(2, 14))
        # Contenedor de las dos columnas.
        columnas = tk.Frame(cuerpo, background=COLOR_FONDO)
        # Ocupa el ancho.
        columnas.pack(fill="x")
        # Las dos columnas crecen igual.
        columnas.columnconfigure((0, 1), weight=1, uniform="ajustes")
        # Tarjeta izquierda: sesiones, descansos y aviso.
        marco_izquierda, izquierda = tarjeta(columnas, "Sesiones y avisos")
        # A la izquierda.
        marco_izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        # Textos de cada ajuste numérico, por clave.
        self.valores = {}
        # Una fila por ajuste numérico.
        for fila, (clave, titulo, explicacion, minimo, maximo, paso) in enumerate(CAMPOS_NUMERICOS):
            # Título del ajuste.
            ttk.Label(izquierda, text=titulo, style="Tarjeta.TLabel").grid(row=fila * 2, column=0, sticky="w",
                                                                           pady=(8 if fila else 0, 0))
            # Texto del valor.
            self.valores[clave] = tk.StringVar()
            # Casilla con flechitas.
            ttk.Spinbox(izquierda, from_=minimo, to=maximo, increment=paso, width=8,
                        textvariable=self.valores[clave]).grid(row=fila * 2, column=1, sticky="e",
                                                               pady=(8 if fila else 0, 0))
            # Explicación en gris, debajo.
            ttk.Label(izquierda, text=explicacion, style="TarjetaSuave.TLabel").grid(row=fila * 2 + 1, column=0,
                                                                                     columnspan=2, sticky="w")
        # La columna de los títulos crece.
        izquierda.columnconfigure(0, weight=1)
        # Título del calendario.
        ttk.Label(izquierda, text="Calendario de Google", style="Tarjeta.TLabel").grid(
            row=len(CAMPOS_NUMERICOS) * 2, column=0, sticky="w", pady=(8, 0))
        # Texto del calendario.
        self.calendario = tk.StringVar()
        # Casilla para el calendario.
        ttk.Entry(izquierda, textvariable=self.calendario, width=24).grid(
            row=len(CAMPOS_NUMERICOS) * 2, column=1, sticky="e", pady=(8, 0))
        # Explicación.
        ttk.Label(izquierda, text="«primary» es tu calendario principal (ver «Configuración» en el README)",
                  style="TarjetaSuave.TLabel").grid(row=len(CAMPOS_NUMERICOS) * 2 + 1, column=0, columnspan=2, sticky="w")
        # ¿Recuperar lo no hecho?
        self.recuperar = tk.BooleanVar()
        # Casilla de marcar (la clásica: en Windows se marca con ✓).
        tk.Checkbutton(izquierda, text="Recuperar en el próximo plan las sesiones que no hice", variable=self.recuperar,
                       font=app.fuentes["normal"], background=COLOR_TARJETA, activebackground=COLOR_TARJETA,
                       foreground=COLOR_TEXTO, highlightthickness=0, borderwidth=0, anchor="w").grid(
            row=len(CAMPOS_NUMERICOS) * 2 + 2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        # Tarjeta derecha: días y horas.
        marco_derecha, derecha = tarjeta(columnas, "Días y hora de inicio")
        # A la derecha.
        marco_derecha.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        # Explicación.
        ajustar_al_ancho(ttk.Label(derecha, text="Marca los días en que estudias y a qué hora empiezas (formato HH:MM).",
                                   style="TarjetaSuave.TLabel", justify="left")).grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        # Casilla marcada y hora de cada día, por nombre interno.
        self.dias = {}
        # Una fila por día de la semana.
        for fila, (interno, visible) in enumerate(zip(almacen.DIAS_SEMANA, DIAS_VISIBLES), start=1):
            # ¿Se estudia ese día?
            marcado = tk.BooleanVar()
            # Hora de inicio.
            hora = tk.StringVar()
            # Casilla para escribir la hora.
            casilla = ttk.Entry(derecha, textvariable=hora, width=8)
            # Casilla de marcar con el nombre del día (la clásica: en Windows se marca con ✓).
            tk.Checkbutton(derecha, text=visible.capitalize(), variable=marcado, font=app.fuentes["normal"],
                           background=COLOR_TARJETA, activebackground=COLOR_TARJETA, foreground=COLOR_TEXTO,
                           highlightthickness=0, borderwidth=0, anchor="w",
                           command=lambda c=casilla, m=marcado: c.state(["!disabled"] if m.get() else ["disabled"])
                           ).grid(row=fila, column=0, sticky="w", pady=4)
            # La casilla de la hora a la derecha.
            casilla.grid(row=fila, column=1, sticky="e", pady=4)
            # Guardamos las tres cosas.
            self.dias[interno] = (marcado, hora, casilla)
        # La columna de los días crece.
        derecha.columnconfigure(0, weight=1)
        # Cuánto cabe por semana.
        self.capacidad = ajustar_al_ancho(ttk.Label(derecha, style="TarjetaSuave.TLabel", justify="left"))
        # Debajo de los días.
        self.capacidad.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def _mostrar(self, config):
        """Pone en las casillas los valores de una configuración."""
        # Ajustes numéricos.
        for clave, variable in self.valores.items():
            # Valor como texto.
            variable.set(str(config[clave]))
        # Calendario.
        self.calendario.set(config["id_calendario"])
        # Recuperar lo no hecho.
        self.recuperar.set(config["recuperar_no_hechas"])
        # Días y horas.
        for interno, (marcado, hora, casilla) in self.dias.items():
            # ¿Está ese día en el horario?
            estudia = interno in config["horario"]
            # Marcamos (o no) la casilla.
            marcado.set(estudia)
            # Hora: la del horario o, si no se estudia, una sugerida.
            hora.set(config["horario"].get(interno, "18:00"))
            # La hora solo se puede escribir si el día está marcado.
            casilla.state(["!disabled"] if estudia else ["disabled"])
        # Cuánto cabe por semana.
        capacidad = planificador.capacidad_semanal(config)
        # Texto.
        self.capacidad.configure(text=f"Con estos ajustes caben hasta {minutos_a_texto(capacidad)} de estudio por "
                                      "semana." if capacidad is not None else
                                 "Sin máximo diario: cada día se llena hasta medianoche si hace falta.")

    def refrescar(self):
        """Carga en las casillas lo que hay guardado en config.json."""
        # Intentamos leer los ajustes.
        try:
            # Ajustes guardados.
            config = almacen.cargar_config()
        # Si el archivo está mal, mostramos los valores por defecto y avisamos.
        except almacen.ErrorPlanificador as error:
            # Aviso abajo.
            self.app.avisar(f"{error} Corrígelo aquí y pulsa «Guardar ajustes».", error=True)
            # Valores por defecto.
            config = almacen.CONFIG_POR_DEFECTO
        # Los ponemos en las casillas.
        self._mostrar(config)

    def por_defecto(self):
        """Pone los valores de fábrica en las casillas (no se guardan hasta pulsar «Guardar ajustes»)."""
        # Valores por defecto.
        self._mostrar(almacen.CONFIG_POR_DEFECTO)
        # Recordatorio.
        self.app.avisar("Valores por defecto puestos. Pulsa «Guardar ajustes» para usarlos.")

    @con_avisos
    def guardar(self):
        """Revisa los valores de las casillas y los guarda en config.json."""
        # Partimos de los ajustes guardados, para conservar los que no están en esta pestaña (el asistente).
        datos = dict(self.app.config_o_defecto())
        # Ajustes numéricos.
        for clave, titulo, *_resto in CAMPOS_NUMERICOS:
            # Convertimos el texto a número.
            try:
                # Valor numérico.
                datos[clave] = int(self.valores[clave].get().strip())
            # Si no es un número entero, lo avisamos.
            except ValueError as error:
                # Error para el usuario.
                raise almacen.ErrorPlanificador(f"«{titulo}» tiene que ser un número entero.") from error
        # Calendario.
        datos["id_calendario"] = self.calendario.get().strip()
        # Recuperar lo no hecho.
        datos["recuperar_no_hechas"] = bool(self.recuperar.get())
        # Horario: solo los días marcados.
        datos["horario"] = {interno: hora.get().strip() for interno, (marcado, hora, _c) in self.dias.items()
                            if marcado.get()}
        # Revisamos y guardamos (si algo está mal, se explica y no se guarda).
        config = almacen.guardar_config(datos)
        # Mostramos lo guardado (por ejemplo, con la capacidad actualizada).
        self._mostrar(config)
        # El plan se hizo con los ajustes anteriores.
        self.app.plan_desactualizado = True
        # Redibujamos las demás pestañas.
        self.app.refrescar_todo(salvo=self)
        # Mensaje abajo.
        self.app.avisar("Ajustes guardados. Pulsa «Generar plan» en la sección Semana para aplicarlos.")


class Aplicacion(tk.Tk):
    """La ventana principal: cabecera, secciones y barra de mensajes."""

    def __init__(self):
        # Creamos la ventana.
        super().__init__()
        # Título de la ventana.
        self.title("Planificador de estudio")
        # Escala de la pantalla (1 = normal; 1.5 en pantallas con zoom del 150 %).
        self.escala = max(self.winfo_fpixels("1i") / 96, 1)
        # Tamaño inicial: el pensado o, si la pantalla es más pequeña, lo que quepa.
        ancho = min(int(1380 * self.escala), self.winfo_screenwidth() - 60)
        # Alto inicial.
        alto = min(int(820 * self.escala), self.winfo_screenheight() - 100)
        # Aplicamos el tamaño.
        self.geometry(f"{ancho}x{alto}")
        # Tamaño mínimo para que nada quede cortado.
        self.minsize(min(int(1180 * self.escala), ancho), min(int(620 * self.escala), alto))
        # Color de fondo.
        self.configure(background=COLOR_FONDO)
        # Los mensajes de error hablan del botón, no del comando.
        almacen.COMO_GENERAR = "el botón «Generar plan» de la sección Semana"
        # Fuentes de letra.
        self.fuentes = self._crear_fuentes()
        # Colores y formas de los controles.
        self._aplicar_estilo()
        # Plan guardado (se lee en refrescar_todo).
        self.plan = None
        # True cuando cambiaron temas o ajustes y conviene volver a generar el plan.
        self.plan_desactualizado = False
        # Tareas en segundo plano en marcha (hablando con Google o con la IA).
        self.tareas = 0
        # Cola por la que llegan los resultados de las tareas en segundo plano.
        self.cola = queue.Queue()
        # Identificadores de las tareas programadas (para cancelarlas al cerrar).
        self._borrar_aviso = self._id_cola = self._id_minuto = None
        # Construimos las partes de la ventana.
        self._construir()
        # Errores inesperados: los mostramos en una ventanita.
        self.report_callback_exception = self._error_inesperado
        # La rueda del ratón desplaza las listas largas.
        self.bind_all("<MouseWheel>", self._rueda)
        # En Linux la rueda llega como botones 4 y 5.
        self.bind_all("<Button-4>", self._rueda)
        # Rueda hacia abajo en Linux.
        self.bind_all("<Button-5>", self._rueda)
        # Al cerrar la ventana, comprobamos que no haya nada a medias.
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        # Empezamos a revisar la cola (guardamos el identificador para poder cancelarlo al cerrar).
        self._id_cola = self.after(100, self._revisar_cola)
        # Cada minuto actualizamos la pestaña Hoy (para marcar la sesión de ahora).
        self._id_minuto = self.after(60_000, self._cada_minuto)
        # Dibujamos todo con los datos guardados.
        self.refrescar_todo()

    def _crear_fuentes(self):
        """Prepara las fuentes de letra (Segoe UI en Windows; la del sistema en los demás)."""
        # Fuente por defecto del sistema.
        base = tkfont.nametofont("TkDefaultFont")
        # En Windows usamos Segoe UI, la de Windows 10 y 11.
        familia = "Segoe UI" if sys.platform == "win32" else base.actual("family")
        # Para los títulos, Segoe UI Semibold si existe (Windows); si no, la misma en negrita.
        titulos = "Segoe UI Semibold" if "Segoe UI Semibold" in tkfont.families(self) else familia
        # Esa fuente ya es seminegrita: no le añadimos negrita encima.
        grosor = "normal" if titulos == "Segoe UI Semibold" else "bold"
        # Ajustamos las fuentes estándar de tkinter.
        for nombre in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            # Misma familia y tamaño 10.
            tkfont.nametofont(nombre).configure(family=familia, size=10)
        # Fuentes propias de la ventana.
        return {
            # Texto normal.
            "normal": tkfont.Font(self, family=familia, size=10),
            # Texto pequeño.
            "pequena": tkfont.Font(self, family=familia, size=9),
            # Texto pequeño en negrita.
            "pequena_negrita": tkfont.Font(self, family=familia, size=9, weight="bold"),
            # Texto normal en negrita.
            "negrita": tkfont.Font(self, family=familia, size=10, weight="bold"),
            # Horas de las tarjetas de Hoy.
            "hora": tkfont.Font(self, family=familia, size=12, weight="bold"),
            # Nombre del tema en las tarjetas de Hoy.
            "tema": tkfont.Font(self, family=familia, size=13, weight="bold"),
            # Subtítulos.
            "subtitulo": tkfont.Font(self, family=familia, size=12, weight="bold"),
            # Títulos de las secciones.
            "titulo": tkfont.Font(self, family=titulos, size=20, weight=grosor),
            # Nombre de la app en la barra lateral.
            "marca": tkfont.Font(self, family=titulos, size=14, weight=grosor),
            # Secciones de la barra lateral.
            "nav": tkfont.Font(self, family=familia, size=11),
            # Sección elegida en la barra lateral.
            "nav_activa": tkfont.Font(self, family=familia, size=11, weight="bold"),
        }

    def _aplicar_estilo(self):
        """Define colores y formas de los controles (tema "clam", que se ve igual en todos los sistemas)."""
        # Objeto de estilos.
        estilo = ttk.Style(self)
        # Tema base.
        estilo.theme_use("clam")
        # Valores generales para todos los controles.
        estilo.configure(".", background=COLOR_FONDO, foreground=COLOR_TEXTO, font=self.fuentes["normal"],
                         bordercolor=COLOR_BORDE, lightcolor=COLOR_TARJETA, darkcolor=COLOR_BORDE,
                         troughcolor="#eceef5", focuscolor=COLOR_ACENTO)
        # Marcos.
        estilo.configure("TFrame", background=COLOR_FONDO)
        # Marcos dentro de tarjetas.
        estilo.configure("Tarjeta.TFrame", background=COLOR_TARJETA)
        # Textos.
        estilo.configure("TLabel", background=COLOR_FONDO, foreground=COLOR_TEXTO)
        # Títulos.
        estilo.configure("Titulo.TLabel", font=self.fuentes["titulo"])
        # Textos en negrita.
        estilo.configure("Negrita.TLabel", font=self.fuentes["negrita"])
        # Textos secundarios.
        estilo.configure("Suave.TLabel", foreground=COLOR_SUAVE)
        # Avisos.
        estilo.configure("Aviso.TLabel", foreground=COLOR_AVISO)
        # Información (por ejemplo, cómo se adaptó el plan).
        estilo.configure("Info.TLabel", foreground="#4338ca")
        # Texto grande dentro de tarjetas (la racha).
        estilo.configure("RachaTarjeta.TLabel", background=COLOR_TARJETA, foreground=COLOR_TEXTO,
                         font=self.fuentes["subtitulo"])
        # Opciones a elegir dentro de tarjetas.
        estilo.configure("Tarjeta.TRadiobutton", background=COLOR_TARJETA, foreground=COLOR_TEXTO,
                         indicatorbackground=COLOR_TARJETA)
        # Al pasar el ratón, sin cambiar el fondo.
        estilo.map("Tarjeta.TRadiobutton", background=[("active", COLOR_TARJETA)],
                   indicatorbackground=[("selected", COLOR_ACENTO)])
        # Textos dentro de tarjetas.
        estilo.configure("Tarjeta.TLabel", background=COLOR_TARJETA)
        # Textos secundarios dentro de tarjetas.
        estilo.configure("TarjetaSuave.TLabel", background=COLOR_TARJETA, foreground=COLOR_SUAVE,
                         font=self.fuentes["pequena"])
        # Título de las tarjetas.
        estilo.configure("TituloTarjeta.TLabel", background=COLOR_TARJETA, foreground=COLOR_TEXTO,
                         font=self.fuentes["subtitulo"])
        # Botones normales: blancos con borde.
        estilo.configure("TButton", background=COLOR_TARJETA, foreground=COLOR_TEXTO, padding=(14, 7),
                         bordercolor=COLOR_BORDE, lightcolor=COLOR_TARJETA, darkcolor=COLOR_TARJETA,
                         focusthickness=0)
        # Botones normales al pasar el ratón o desactivados.
        estilo.map("TButton", background=[("disabled", "#f1f3f6"), ("pressed", "#e0e7ff"), ("active", COLOR_ACENTO_SUAVE)],
                   foreground=[("disabled", "#a0a6b0")], lightcolor=[("active", COLOR_ACENTO_SUAVE)],
                   darkcolor=[("active", COLOR_ACENTO_SUAVE)])
        # Botón principal: azul con letra blanca.
        estilo.configure("Acento.TButton", background=COLOR_ACENTO, foreground="white", bordercolor=COLOR_ACENTO,
                         lightcolor=COLOR_ACENTO, darkcolor=COLOR_ACENTO, font=self.fuentes["negrita"])
        # Botón principal al pasar el ratón o desactivado.
        estilo.map("Acento.TButton", background=[("disabled", "#c7d2fe"), ("pressed", "#3730a3"),
                                                 ("active", COLOR_ACENTO_OSCURO)],
                   foreground=[("disabled", "white")], bordercolor=[("disabled", "#c7d2fe")],
                   lightcolor=[("disabled", "#c7d2fe"), ("active", COLOR_ACENTO_OSCURO)],
                   darkcolor=[("disabled", "#c7d2fe"), ("active", COLOR_ACENTO_OSCURO)])
        # Botones pequeños para marcar sesiones y para los ejemplos del asistente.
        estilo.configure("Marca.TButton", padding=(10, 4), font=self.fuentes["pequena"])
        # Botón «Hecha» marcado: verde.
        estilo.configure("MarcaHecha.TButton", padding=(10, 4), font=self.fuentes["pequena_negrita"],
                         background=COLOR_BIEN, foreground="white", bordercolor=COLOR_BIEN, lightcolor=COLOR_BIEN,
                         darkcolor=COLOR_BIEN)
        # Al pasar el ratón, verde más oscuro.
        estilo.map("MarcaHecha.TButton", background=[("active", "#166534")], lightcolor=[("active", "#166534")],
                   darkcolor=[("active", "#166534")])
        # Botón «No la hice» marcado: rojo.
        estilo.configure("MarcaNo.TButton", padding=(10, 4), font=self.fuentes["pequena_negrita"],
                         background=COLOR_MAL, foreground="white", bordercolor=COLOR_MAL, lightcolor=COLOR_MAL,
                         darkcolor=COLOR_MAL)
        # Al pasar el ratón, rojo más oscuro.
        estilo.map("MarcaNo.TButton", background=[("active", "#b91c1c")], lightcolor=[("active", "#b91c1c")],
                   darkcolor=[("active", "#b91c1c")])
        # Botón de borrar: letra roja.
        estilo.configure("Peligro.TButton", foreground=COLOR_MAL)
        # Botón de borrar al pasar el ratón.
        estilo.map("Peligro.TButton", background=[("disabled", "#f1f3f6"), ("active", "#fce8e6")],
                   foreground=[("disabled", "#a0a6b0")], lightcolor=[("active", "#fce8e6")],
                   darkcolor=[("active", "#fce8e6")])
        # Secciones: un "cuaderno" sin bordes ni solapas (se cambia de sección desde la barra lateral).
        estilo.configure("Lateral.TNotebook", background=COLOR_FONDO, borderwidth=0, tabmargins=0,
                         lightcolor=COLOR_FONDO, darkcolor=COLOR_FONDO, bordercolor=COLOR_FONDO)
        # Solapas sin dibujo: no ocupan sitio.
        estilo.layout("Lateral.TNotebook.Tab", [])
        # Tablas.
        estilo.configure("Treeview", background=COLOR_TARJETA, fieldbackground=COLOR_TARJETA, foreground=COLOR_TEXTO,
                         rowheight=int(30 * self.escala), bordercolor=COLOR_BORDE, borderwidth=1)
        # Fila elegida.
        estilo.map("Treeview", background=[("selected", "#e0e7ff")], foreground=[("selected", COLOR_TEXTO)])
        # Títulos de las columnas.
        estilo.configure("Treeview.Heading", background="#f3f4fa", foreground=COLOR_TEXTO, relief="flat",
                         font=self.fuentes["negrita"], padding=(8, 6), lightcolor="#f3f4fa", darkcolor="#f3f4fa",
                         bordercolor=COLOR_BORDE)
        # Títulos al pasar el ratón.
        estilo.map("Treeview.Heading", background=[("active", "#e8eaf4")])
        # Casillas de texto.
        estilo.configure("TEntry", padding=(8, 5), fieldbackground=COLOR_TARJETA, lightcolor=COLOR_BORDE)
        # Casillas con flechitas.
        estilo.configure("TSpinbox", padding=(8, 5), fieldbackground=COLOR_TARJETA, arrowsize=13,
                         lightcolor=COLOR_BORDE, background=COLOR_TARJETA)
        # Listas desplegables.
        estilo.configure("TCombobox", padding=(8, 5), fieldbackground=COLOR_TARJETA, arrowsize=14,
                         lightcolor=COLOR_BORDE, background=COLOR_TARJETA)
        # Lista desplegable de solo lectura: fondo blanco.
        estilo.map("TCombobox", fieldbackground=[("readonly", COLOR_TARJETA)],
                   selectbackground=[("readonly", COLOR_TARJETA)], selectforeground=[("readonly", COLOR_TEXTO)])
        # Barra de progreso azul.
        estilo.configure("Horizontal.TProgressbar", background=COLOR_ACENTO, troughcolor="#eceef5",
                         bordercolor="#eceef5", lightcolor=COLOR_ACENTO, darkcolor=COLOR_ACENTO, thickness=6)
        # Barras de desplazamiento discretas.
        estilo.configure("Vertical.TScrollbar", background="#d4d8e6", troughcolor=COLOR_FONDO,
                         bordercolor=COLOR_FONDO, arrowcolor=COLOR_SUAVE, lightcolor="#d4d8e6", darkcolor="#d4d8e6")
        # Lista que se despliega en las Combobox (es un control clásico: se configura aparte).
        self.option_add("*TCombobox*Listbox.background", COLOR_TARJETA)
        # Fila elegida de esa lista.
        self.option_add("*TCombobox*Listbox.selectBackground", "#e0e7ff")
        # Texto de la fila elegida.
        self.option_add("*TCombobox*Listbox.selectForeground", COLOR_TEXTO)
        # Fuente de esa lista.
        self.option_add("*TCombobox*Listbox.font", self.fuentes["normal"])

    def _cargar_imagenes(self):
        """Carga el logo y los iconos (del tamaño adecuado al zoom de la pantalla) y pone el icono de la ventana."""
        # Aquí se guardan (tkinter las borra si nadie las guarda).
        self.imagenes = {}
        # Si falta la carpeta recursos/ (o una imagen), la ventana funciona igual, solo que sin imágenes.
        try:
            # Tamaño de los iconos más parecido a 20 píxeles por la escala de la pantalla.
            tam_icono = min((20, 30, 40), key=lambda t: abs(t - 20 * self.escala))
            # Tamaño del logo más parecido a 40 píxeles por la escala.
            tam_logo = min((40, 64, 80), key=lambda t: abs(t - 40 * self.escala))
            # Iconos de cada sección, en color claro (normal) y blanco (elegida).
            for nombre, _texto, _atributo in SECCIONES:
                # Los dos colores.
                for color in ("claro", "blanco"):
                    # Imagen PNG.
                    self.imagenes[f"{nombre}-{color}"] = tk.PhotoImage(
                        file=str(CARPETA_RECURSOS / "iconos" / f"{nombre}-{color}-{tam_icono}.png"))
            # Logo de la barra lateral.
            self.imagenes["logo"] = tk.PhotoImage(file=str(CARPETA_RECURSOS / f"logo-{tam_logo}.png"))
            # Logo en varios tamaños para la barra de título y la de tareas.
            self.imagenes["ventana"] = [tk.PhotoImage(file=str(CARPETA_RECURSOS / f"logo-{t}.png"))
                                        for t in (16, 32, 48, 64, 128, 256)]
            # Icono de la ventana (True = también para las ventanitas de aviso).
            self.iconphoto(True, *self.imagenes["ventana"])
        # Sin imágenes: seguimos sin ellas.
        except (tk.TclError, OSError):
            # Diccionario vacío.
            self.imagenes = {}

    def _construir(self):
        """Crea la barra lateral, las secciones y la barra de mensajes."""
        # Logo e iconos.
        self._cargar_imagenes()
        # Barra lateral a la izquierda.
        self._construir_lateral()
        # Zona principal a la derecha.
        principal = tk.Frame(self, background=COLOR_FONDO)
        # Ocupa el resto de la ventana.
        principal.pack(side="left", fill="both", expand=True)
        # Barra de mensajes, abajo del todo.
        self.barra_avisos = tk.Label(principal, anchor="w", font=self.fuentes["normal"], background="#eceef5",
                                     foreground=COLOR_TEXTO, padx=28, pady=7)
        # Abajo.
        self.barra_avisos.pack(side="bottom", fill="x")
        # Las secciones son pestañas sin solapas visibles: se eligen desde la barra lateral.
        self.cuaderno = ttk.Notebook(principal, style="Lateral.TNotebook")
        # Ocupan el resto de la zona principal.
        self.cuaderno.pack(fill="both", expand=True, pady=(6, 0))
        # Pestaña Hoy.
        self.pestana_hoy = PestanaHoy(self.cuaderno, self)
        # Pestaña Semana.
        self.pestana_semana = PestanaSemana(self.cuaderno, self)
        # Pestaña Temas.
        self.pestana_temas = PestanaTemas(self.cuaderno, self)
        # Pestaña Metas y progreso.
        self.pestana_metas = PestanaMetas(self.cuaderno, self)
        # Pestaña Asistente.
        self.pestana_asistente = PestanaAsistente(self.cuaderno, self)
        # Pestaña Google Calendar.
        self.pestana_google = PestanaGoogle(self.cuaderno, self)
        # Pestaña Ajustes.
        self.pestana_ajustes = PestanaAjustes(self.cuaderno, self)
        # Añadimos las pestañas en el mismo orden que la barra lateral.
        for _nombre, texto, atributo in SECCIONES:
            # Añadimos la pestaña.
            self.cuaderno.add(getattr(self, atributo), text=texto)
        # Al cambiar de sección, la actualizamos y marcamos en la barra lateral.
        self.cuaderno.bind("<<NotebookTabChanged>>", self._al_cambiar_pestana)
        # Atajos de teclado: Ctrl+1 ... Ctrl+7 para ir a cada sección.
        for numero, (_nombre, _texto, atributo) in enumerate(SECCIONES, start=1):
            # Atajo.
            self.bind_all(f"<Control-Key-{numero}>", lambda _evento, a=atributo: self.cuaderno.select(getattr(self, a)))
        # Marcamos la primera sección.
        self._pintar_lateral()

    def _construir_lateral(self):
        """Barra lateral oscura: logo, una fila por sección y la próxima sesión abajo."""
        # Marco de la barra, de ancho fijo.
        lateral = tk.Frame(self, background=COLOR_LATERAL, width=int(236 * self.escala))
        # A la izquierda, de arriba abajo.
        lateral.pack(side="left", fill="y")
        # El ancho no cambia con el contenido.
        lateral.pack_propagate(False)
        # Logo y nombre.
        marca = tk.Frame(lateral, background=COLOR_LATERAL)
        # Arriba.
        marca.pack(fill="x", padx=20, pady=(24, 28))
        # Logo (si se pudo cargar).
        tk.Label(marca, image=self.imagenes.get("logo"), background=COLOR_LATERAL).pack(side="left")
        # Textos del nombre.
        nombre = tk.Frame(marca, background=COLOR_LATERAL)
        # A la derecha del logo.
        nombre.pack(side="left", padx=(12, 0))
        # "Planificador", grande y blanco.
        tk.Label(nombre, text="Planificador", font=self.fuentes["marca"], background=COLOR_LATERAL,
                 foreground="white").pack(anchor="w")
        # "de estudio", más pequeño.
        tk.Label(nombre, text="de estudio", font=self.fuentes["normal"], background=COLOR_LATERAL,
                 foreground=COLOR_LATERAL_SUAVE).pack(anchor="w")
        # Filas de cada sección: nombre del icono -> (fila, marca, icono, texto, atributo).
        self.filas_lateral = {}
        # Una fila por sección.
        for nombre_icono, texto, atributo in SECCIONES:
            # Fila (con la mano como puntero, para que se note que se puede pulsar).
            fila = tk.Frame(lateral, background=COLOR_LATERAL, cursor="hand2")
            # Ocupa el ancho.
            fila.pack(fill="x", padx=12, pady=2)
            # Barrita ámbar a la izquierda (solo se ve en la sección elegida).
            barrita = tk.Frame(fila, background=COLOR_LATERAL, width=4)
            # A la izquierda, de arriba abajo de la fila.
            barrita.pack(side="left", fill="y")
            # Icono.
            icono = tk.Label(fila, image=self.imagenes.get(f"{nombre_icono}-claro"), background=COLOR_LATERAL,
                             cursor="hand2")
            # A la izquierda.
            icono.pack(side="left", padx=(12, 12), pady=int(9 * self.escala))
            # Texto.
            etiqueta = tk.Label(fila, text=texto, font=self.fuentes["nav"], background=COLOR_LATERAL,
                                foreground=COLOR_LATERAL_TEXTO, anchor="w", cursor="hand2")
            # Ocupa el resto.
            etiqueta.pack(side="left", fill="x", expand=True)
            # Guardamos las piezas.
            self.filas_lateral[nombre_icono] = (fila, barrita, icono, etiqueta, atributo)
            # Pulsar, pasar el ratón por encima y salir, en todas las piezas de la fila.
            for pieza in (fila, barrita, icono, etiqueta):
                # Pulsar: ir a la sección.
                pieza.bind("<Button-1>", lambda _evento, a=atributo: self.cuaderno.select(getattr(self, a)))
                # Ratón encima: resaltar.
                pieza.bind("<Enter>", lambda _evento, n=nombre_icono: self._pintar_lateral(encima=n))
                # Ratón fuera: quitar el resaltado.
                pieza.bind("<Leave>", lambda _evento: self.after_idle(self._pintar_lateral))
        # Tarjeta de la próxima sesión, abajo del todo.
        tarjeta = tk.Frame(lateral, background=COLOR_LATERAL_ENCIMA)
        # Abajo.
        tarjeta.pack(side="bottom", fill="x", padx=16, pady=20)
        # Título pequeño.
        tk.Label(tarjeta, text="PRÓXIMA SESIÓN", font=self.fuentes["pequena_negrita"], background=COLOR_LATERAL_ENCIMA,
                 foreground=COLOR_LATERAL_SUAVE).pack(anchor="w", padx=14, pady=(12, 2))
        # Cuándo y qué (se rellena en _actualizar_cabecera).
        self.proxima = tk.Label(tarjeta, font=self.fuentes["negrita"], background=COLOR_LATERAL_ENCIMA,
                                foreground="white", justify="left", anchor="w", wraplength=int(176 * self.escala))
        # Debajo del título.
        self.proxima.pack(anchor="w", padx=14, pady=(0, 12))

    def _pintar_lateral(self, encima=None):
        """Colorea las filas de la barra lateral: la elegida, la que tiene el ratón encima y las demás."""
        # Sección elegida ahora mismo.
        try:
            # Pestaña elegida.
            elegida = self.nametowidget(self.cuaderno.select())
        # Si la ventana se está cerrando, no hay nada que pintar.
        except (KeyError, tk.TclError):
            # Terminamos.
            return
        # Control que tiene el ratón encima (para saber si sigue sobre alguna fila).
        if encima is None:
            # Intentamos averiguarlo.
            try:
                # Control bajo el ratón.
                bajo_raton = self.winfo_containing(*self.winfo_pointerxy())
            # En algunos casos tkinter no lo encuentra.
            except (KeyError, tk.TclError):
                # Ninguno.
                bajo_raton = None
            # ¿Es parte de alguna fila?
            encima = next((n for n, piezas in self.filas_lateral.items() if bajo_raton in piezas[:4]), None)
        # Pintamos cada fila.
        for nombre_icono, (fila, barrita, icono, etiqueta, atributo) in self.filas_lateral.items():
            # ¿Es la elegida?
            activa = getattr(self, atributo) is elegida
            # Fondo: elegida, con el ratón encima o normal.
            fondo = COLOR_LATERAL_ACTIVO if activa else (COLOR_LATERAL_ENCIMA if nombre_icono == encima else COLOR_LATERAL)
            # Fondo de las piezas.
            for pieza in (fila, icono, etiqueta):
                # Mismo fondo.
                pieza.configure(background=fondo)
            # Barrita ámbar solo en la elegida.
            barrita.configure(background=COLOR_AMBAR if activa else fondo)
            # Icono blanco en la elegida; claro en las demás.
            icono.configure(image=self.imagenes.get(f"{nombre_icono}-{'blanco' if activa else 'claro'}", ""))
            # Texto blanco y en negrita en la elegida.
            etiqueta.configure(foreground="white" if activa else COLOR_LATERAL_TEXTO,
                               font=self.fuentes["nav_activa" if activa else "nav"])

    def leer_plan(self):
        """Lee el plan guardado en datos/plan.json (None si no hay o si está dañado)."""
        # Si todavía no hay plan, no hay nada que leer.
        if not almacen.ARCHIVO_PLAN.exists():
            # Sin plan.
            self.plan = None
            # Terminamos.
            return
        # Intentamos leerlo.
        try:
            # Plan listo para usar.
            self.plan = repartidor.plan_desde_dict(almacen.cargar_plan())
        # Si está dañado, lo avisamos y seguimos sin plan.
        except almacen.ErrorPlanificador as error:
            # Sin plan.
            self.plan = None
            # Aviso abajo.
            self.avisar(str(error), error=True)

    def registro(self):
        """Sesiones hechas y no hechas (vacío, avisando, si el archivo está mal)."""
        # Intentamos leerlo.
        try:
            # Registro.
            return almacen.cargar_registro()
        # Archivo mal escrito.
        except almacen.ErrorPlanificador as error:
            # Aviso abajo.
            self.avisar(str(error), error=True)
            # Registro vacío.
            return {"sesiones": {}, "perdonado": {}}

    def config_o_defecto(self):
        """Ajustes guardados (o los de fábrica, si config.json está mal escrito)."""
        # Intentamos leerlos.
        try:
            # Ajustes.
            return almacen.cargar_config()
        # Archivo mal escrito.
        except almacen.ErrorPlanificador:
            # Valores de fábrica.
            return copy.deepcopy(almacen.CONFIG_POR_DEFECTO)

    def refrescar_progreso(self):
        """Redibuja lo que depende de las sesiones marcadas: Hoy, Semana, Metas y la cabecera."""
        # Cada pestaña.
        for pestana in (self.pestana_hoy, self.pestana_semana, self.pestana_metas):
            # La redibujamos.
            pestana.refrescar()
        # Cabecera.
        self._actualizar_cabecera()

    def refrescar_todo(self, salvo=None):
        """Vuelve a leer el plan y redibuja todas las secciones (menos `salvo`, si se indica)."""
        # Releemos el plan del disco.
        self.leer_plan()
        # Redibujamos cada pestaña.
        for pestana in (self.pestana_hoy, self.pestana_semana, self.pestana_temas, self.pestana_metas,
                        self.pestana_asistente, self.pestana_google, self.pestana_ajustes):
            # Saltamos la indicada (por ejemplo, Ajustes justo después de guardar).
            if pestana is not salvo:
                # La redibujamos.
                pestana.refrescar()
        # Cabecera con la próxima sesión.
        self._actualizar_cabecera()

    def _actualizar_cabecera(self):
        """Muestra en la tarjeta de la barra lateral cuál es la próxima sesión."""
        # Fecha y hora actuales.
        ahora = datetime.now()
        # Próxima sesión que no terminó.
        sesion = proxima_sesion(self.plan, ahora)
        # Si no hay, lo decimos.
        if sesion is None:
            # Texto.
            self.proxima.configure(text="Nada pendiente.\nGenera un plan en Semana.")
            # Terminamos.
            return
        # "Ahora" si ya empezó; si no, cuándo empieza.
        if sesion.inicio <= ahora:
            # Está en curso.
            cuando = f"Ahora, hasta las {sesion.fin:%H:%M}"
        # Empieza hoy.
        elif sesion.inicio.date() == ahora.date():
            # Hoy a tal hora.
            cuando = f"Hoy a las {sesion.inicio:%H:%M}"
        # Empieza mañana.
        elif sesion.inicio.date() == ahora.date() + timedelta(days=1):
            # Mañana a tal hora.
            cuando = f"Mañana a las {sesion.inicio:%H:%M}"
        # Otro día.
        else:
            # Día y hora.
            cuando = f"{fecha_corta(sesion.inicio.date()).capitalize()} a las {sesion.inicio:%H:%M}"
        # Texto de la tarjeta: cuándo y, debajo, el tema.
        self.proxima.configure(text=f"{cuando}\n{sesion.tema}")

    def avisar(self, texto, error=False):
        """Muestra un mensaje en la barra de abajo durante unos segundos."""
        # Texto y color (rojo si es un error).
        self.barra_avisos.configure(text=texto.replace("\n", " "), foreground=COLOR_MAL if error else COLOR_TEXTO)
        # Si había un borrado pendiente, lo cancelamos.
        if self._borrar_aviso:
            # Cancelamos el temporizador anterior.
            self.after_cancel(self._borrar_aviso)
        # El mensaje se borra a los 12 segundos (los errores, a los 30).
        self._borrar_aviso = self.after(30_000 if error else 12_000, lambda: self.barra_avisos.configure(text=""))

    @property
    def ocupado(self):
        """True mientras haya alguna tarea en segundo plano (hablando con Google o con la IA)."""
        # Hay tareas en marcha.
        return self.tareas > 0

    def en_segundo_plano(self, tarea, al_terminar, pestana=None, capturar_salida=True):
        """Ejecuta `tarea` sin congelar la ventana y, cuando acaba, llama a `al_terminar(resultado)`.

        `pestana` (por defecto, Google Calendar) es la que se bloquea mientras tanto y la que muestra lo que pasa.
        Con `capturar_salida`, lo que imprima la tarea (por ejemplo, la dirección para dar permiso a Google)
        se apunta en esa sección.
        """
        # Pestaña que espera el resultado.
        pestana = pestana or self.pestana_google
        # Una tarea más en marcha.
        self.tareas += 1
        # Bloqueamos sus botones.
        pestana.ocupado(True)

        def trabajar():
            # Hacemos la tarea.
            try:
                # Si se pidió, desviamos print() hacia la pestaña.
                if capturar_salida:
                    # Con la salida desviada.
                    with redirect_stdout(EscritorCola(self.cola, pestana)):
                        # Tarea.
                        resultado = tarea()
                # Si no, tal cual.
                else:
                    # Tarea.
                    resultado = tarea()
            # Errores pensados para el usuario.
            except almacen.ErrorPlanificador as error:
                # Los mandamos a la ventana.
                self.cola.put(("error", pestana, str(error)))
            # Cualquier otro error (no debería pasar).
            except Exception:  # noqa: BLE001 - lo mostramos en la ventana en vez de perderlo.
                # Mandamos el detalle técnico a la ventana.
                self.cola.put(("fallo", pestana, traceback.format_exc()))
            # Si todo fue bien...
            else:
                # ...mandamos el resultado.
                self.cola.put(("listo", pestana, al_terminar, resultado))

        # daemon=True: si cierras la ventana, la tarea no impide que el programa termine.
        threading.Thread(target=trabajar, daemon=True).start()

    def _revisar_cola(self):
        """Atiende los mensajes de las tareas en segundo plano (se repite cada 100 ms)."""
        # Pase lo que pase al atenderlos, seguimos revisando (si no, la ventana dejaría de enterarse de nada).
        try:
            # Atendemos los mensajes pendientes.
            self._atender_cola()
        # Al terminar, con o sin errores...
        finally:
            # ...volvemos a mirar dentro de 100 ms.
            self._id_cola = self.after(100, self._revisar_cola)

    def _atender_cola(self):
        """Atiende todos los mensajes que hay ahora mismo en la cola."""
        # Hasta vaciar la cola.
        while True:
            # Siguiente mensaje (sin esperar).
            try:
                # Lo sacamos de la cola.
                mensaje = self.cola.get_nowait()
            # Cola vacía: no hay más mensajes por ahora.
            except queue.Empty:
                # Terminamos.
                return
            # Tipo de mensaje y pestaña a la que va.
            tipo, pestana = mensaje[0], mensaje[1]
            # Una línea para la pestaña (registro de Google o acción del asistente).
            if tipo == "registro":
                # La escribimos.
                pestana.escribir(mensaje[2])
                # Siguiente mensaje.
                continue
            # Cualquier otro mensaje significa que la tarea terminó.
            self.tareas -= 1
            # Desbloqueamos los botones de esa pestaña.
            pestana.ocupado(False)
            # Terminó bien: seguimos con lo que había que hacer después.
            if tipo == "listo":
                # Llamamos a la función con el resultado.
                mensaje[2](mensaje[3])
            # Error pensado para el usuario: lo muestra la pestaña.
            elif tipo == "error":
                # A su manera.
                pestana.informar_error(mensaje[2])
            # Error inesperado.
            else:
                # Lo mostramos con el detalle técnico.
                self._mostrar_fallo(mensaje[2])

    def _cada_minuto(self):
        """Actualiza la sección Hoy y la cabecera (para que "Ahora" y "Siguiente" estén al día)."""
        # Redibujamos Hoy.
        self.pestana_hoy.refrescar()
        # Y la cabecera.
        self._actualizar_cabecera()
        # Volvemos a hacerlo dentro de un minuto.
        self._id_minuto = self.after(60_000, self._cada_minuto)

    def _al_cambiar_pestana(self, _evento=None):
        """Actualiza la sección que se acaba de abrir y la marca en la barra lateral."""
        # Marcamos la sección en la barra lateral.
        self._pintar_lateral()
        # Pestaña elegida.
        elegida = self.nametowidget(self.cuaderno.select())
        # Estas dependen de la hora o de archivos que pueden cambiar fuera de la ventana.
        if elegida in (self.pestana_hoy, self.pestana_metas, self.pestana_google):
            # La redibujamos.
            elegida.refrescar()

    def _rueda(self, evento):
        """Desplaza la lista que está debajo del ratón al usar la rueda."""
        # Control que está debajo del ratón (en algunos casos tkinter falla al buscarlo).
        try:
            # Buscamos el control.
            control = self.winfo_containing(evento.x_root, evento.y_root)
        # Si falla, no hacemos nada.
        except (KeyError, tk.TclError):
            # Terminamos.
            return
        # Dirección: en Linux, botón 4 = arriba y 5 = abajo; en Windows y Mac, el signo de delta.
        pasos = -1 if evento.num == 4 else 1 if evento.num == 5 else (-1 if evento.delta > 0 else 1)
        # Subimos por los "padres" del control hasta encontrar un marco desplazable.
        while control is not None:
            # ¿Es un marco desplazable?
            if isinstance(control, MarcoDesplazable):
                # Lo desplazamos.
                control.desplazar(pasos * 3)
                # Terminamos.
                return
            # Pasamos al padre.
            control = control.master

    def _error_inesperado(self, tipo, valor, rastro):
        """Muestra en una ventanita cualquier error no previsto de un botón."""
        # Detalle técnico.
        self._mostrar_fallo("".join(traceback.format_exception(tipo, valor, rastro)))

    def _mostrar_fallo(self, detalle):
        """Ventanita para errores inesperados, con el final del detalle técnico."""
        # Lo apuntamos también en el registro.
        self.pestana_google.escribir("Error inesperado:\n" + detalle)
        # Mostramos las últimas líneas (las más útiles).
        messagebox.showerror("Error inesperado", "Algo salió mal. Copia este mensaje y pide ayuda:\n\n" +
                             "\n".join(detalle.strip().splitlines()[-6:]), parent=self)

    def destroy(self):
        """Cierra la ventana cancelando antes las tareas programadas (así no quedan avisos sueltos)."""
        # Cada tarea programada que pueda estar pendiente.
        for identificador in (self._id_cola, self._id_minuto, self._borrar_aviso):
            # Si existe, la cancelamos.
            if identificador:
                # Cancelación.
                self.after_cancel(identificador)
        # Cerramos la ventana de verdad.
        super().destroy()

    def _al_cerrar(self):
        """Cierra la ventana (preguntando antes si hay una tarea a medias)."""
        # Si se está hablando con Google, preguntamos.
        if self.ocupado and not messagebox.askyesno(
                "Hay una tarea en curso", "Todavía se está hablando con Google Calendar o con el asistente. "
                                          "¿Cerrar igualmente?",
                parent=self):
            # Si dice que no, no cerramos.
            return
        # Cerramos la ventana.
        self.destroy()


def main():
    """Abre la ventana del planificador."""
    # En Windows, avisamos de que la ventana sabe dibujarse nítida en pantallas con zoom.
    if sys.platform == "win32":
        # Puede no estar disponible en versiones antiguas de Windows.
        try:
            # ctypes permite llamar a funciones de Windows.
            import ctypes
            # 1 = la ventana se adapta al zoom de la pantalla en la que se abre.
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        # Si no se puede, la ventana se verá igual, solo que algo borrosa.
        except (AttributeError, OSError):
            # Seguimos sin más.
            pass
    # Creamos la ventana.
    try:
        # Ventana principal.
        aplicacion = Aplicacion()
    # Si falla al abrirse, lo mostramos en una ventanita (abierta con doble clic no hay consola donde verlo).
    except Exception:  # noqa: BLE001 - mejor un aviso que un cierre sin explicación.
        # Detalle técnico.
        detalle = traceback.format_exc()
        # Ventanita con las últimas líneas.
        messagebox.showerror("No se pudo abrir el planificador", "Copia este mensaje y pide ayuda:\n\n" +
                             "\n".join(detalle.strip().splitlines()[-6:]))
        # Terminamos con error.
        raise
    # La mostramos y esperamos a que el usuario la use.
    aplicacion.mainloop()


# Esto solo se ejecuta si lanzas el archivo directamente (no si otro módulo lo importa).
if __name__ == "__main__":
    # Abrimos la ventana.
    main()

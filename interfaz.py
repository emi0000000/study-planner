"""Ventana del planificador de estudio: hace lo mismo que los comandos, pero con botones.

Para abrirla:
  - en Windows, doble clic en «Abrir planificador.bat»;
  - o, en la terminal:  python interfaz.py

Usa tkinter, que viene incluido con Python: no hay que instalar nada más.
Los datos son los mismos que usan los comandos (config.json y la carpeta datos/),
así que puedes usar la ventana y la terminal indistintamente.
"""

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
# Módulo que habla con Google Calendar.
import calendario_google
# El programa de comandos: reutilizamos sus funciones de ayuda.
import planificador
# Módulo que reparte el tiempo en sesiones.
import repartidor

# Dirección de la guía de inicio en GitHub (se ve con formato en el navegador).
URL_GUIA = "https://github.com/emi0000000/study-planner/blob/main/GUIA_DE_INICIO.md"

# Color de fondo de la ventana.
COLOR_FONDO = "#f4f6fb"
# Color de fondo de las tarjetas.
COLOR_TARJETA = "#ffffff"
# Color del texto normal.
COLOR_TEXTO = "#1f2933"
# Color del texto secundario (explicaciones, fechas).
COLOR_SUAVE = "#667085"
# Color de los bordes.
COLOR_BORDE = "#dde2ec"
# Azul de los botones principales.
COLOR_ACENTO = "#1a73e8"
# Azul más oscuro (botón principal al pasar el ratón).
COLOR_ACENTO_OSCURO = "#1557b0"
# Fondo azul muy claro (filas seleccionadas, botones al pasar el ratón).
COLOR_ACENTO_SUAVE = "#e8f0fe"
# Naranja oscuro para avisos.
COLOR_AVISO = "#b45309"
# Verde para lo que está bien.
COLOR_BIEN = "#188038"
# Rojo para errores y para borrar.
COLOR_MAL = "#c5221f"
# Gris para las sesiones que ya pasaron.
COLOR_PASADO = "#eef0f3"

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


def minutos_a_texto(minutos):
    """Convierte 150 en "2 h 30 min", 45 en "45 min" y 120 en "2 h"."""
    # Horas completas y minutos sueltos.
    horas, resto = divmod(minutos, 60)
    # Menos de una hora.
    if not horas:
        # Solo minutos.
        return f"{resto} min"
    # Horas justas.
    if not resto:
        # Solo horas.
        return f"{horas} h"
    # Horas y minutos.
    return f"{horas} h {resto} min"


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

    def __init__(self, cola):
        # Cola por la que viajan los mensajes.
        self.cola = cola

    def write(self, texto):
        # Ignoramos los saltos de línea sueltos.
        if texto.strip():
            # Mandamos la línea al registro de la ventana.
            self.cola.put(("registro", texto.rstrip()))

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

    def vaciar(self):
        """Quita todos los contenidos y vuelve arriba del todo."""
        # Borramos cada elemento del interior.
        for hijo in self.interior.winfo_children():
            # Lo destruimos.
            hijo.destroy()
        # Volvemos arriba.
        self.lienzo.yview_moveto(0)


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


def tarjeta_sesion(padre, sesion, fuentes, estado=""):
    """Crea la tarjeta de una sesión para la pestaña Hoy. `estado` puede ser "ahora", "siguiente" o "pasada"."""
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
    # Parte central con el tema y los detalles.
    centro = tk.Frame(marco, background=fondo)
    # Ocupa el espacio que sobra.
    centro.pack(side="left", fill="both", expand=True, pady=10)
    # Nombre del tema, grande.
    tk.Label(centro, text=sesion.tema, font=fuentes["tema"], background=fondo, foreground=texto,
             anchor="w").pack(fill="x")
    # Detalles: número de sesión, duración y prioridad.
    tk.Label(centro, text=f"Sesión {sesion.numero} de {sesion.total} esta semana  ·  {sesion.minutos} min  ·  "
             f"prioridad {sesion.prioridad}", font=fuentes["normal"], background=fondo,
             foreground=COLOR_SUAVE, anchor="w").pack(fill="x")
    # Etiqueta de estado a la derecha (si la hay): texto y color.
    etiquetas = {"ahora": ("Ahora", COLOR_ACENTO), "siguiente": ("Siguiente", COLOR_BIEN), "pasada": ("Ya pasó", "#9aa0a6")}
    # Si la sesión tiene estado, mostramos su etiqueta.
    if estado in etiquetas:
        # Texto y color de la etiqueta.
        rotulo, color = etiquetas[estado]
        # Etiqueta tipo "píldora".
        tk.Label(marco, text=rotulo, font=fuentes["pequena_negrita"], background=color, foreground="white",
                 padx=10, pady=3).pack(side="right", padx=16)
    # Devolvemos la tarjeta para colocarla.
    return marco


class PestanaHoy(ttk.Frame):
    """Pestaña "Hoy": las sesiones del día, con la que toca ahora resaltada."""

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
        """Vuelve a dibujar la pestaña con la hora actual."""
        # Fecha y hora de este momento.
        ahora = datetime.now()
        # Fecha de hoy.
        hoy = ahora.date()
        # Título con la fecha larga, con mayúscula inicial.
        self.titulo.configure(text=f"Hoy, {fecha_larga(hoy)}")
        # Quitamos las tarjetas anteriores.
        self.lista.vaciar()
        # Plan guardado (o None si no hay).
        plan = self.app.plan
        # Sin plan todavía.
        if plan is None:
            # Explicamos qué hacer.
            self._mensaje("Todavía no hay un plan de estudio.",
                          "Agrega tus temas en la pestaña Temas y luego pulsa «Generar plan» en la pestaña Semana.",
                          ("Ir a Temas", self.app.pestana_temas))
            # Terminamos.
            return
        # El plan no incluye el día de hoy.
        if not plan["desde"] <= hoy <= plan["hasta"]:
            # Explicamos qué hacer.
            self._mensaje("El plan guardado no incluye hoy.",
                          f"Va del {fecha_corta(plan['desde'])} al {fecha_corta(plan['hasta'])}. "
                          "Genera uno nuevo en la pestaña Semana.",
                          ("Ir a Semana", self.app.pestana_semana))
            # Terminamos.
            return
        # Sesiones de hoy.
        sesiones = repartidor.sesiones_del_dia(plan, hoy)
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
        # Cuántas quedan por hacer.
        pendientes = sum(1 for s in sesiones if s.fin > ahora)
        # Subtítulo con el resumen del día.
        self.subtitulo.configure(text=f"{len(sesiones)} sesiones · {minutos_a_texto(total)} de estudio · "
                                      f"{'te quedan ' + str(pendientes) if pendientes else 'ya terminaste por hoy'}")
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
            # Creamos y colocamos la tarjeta.
            tarjeta_sesion(self.lista.interior, sesion, self.app.fuentes, estado).pack(fill="x", pady=5, padx=(0, 8))

    def _mensaje(self, titulo, detalle, boton=None):
        """Muestra un mensaje grande en lugar de la lista (y, si se indica, un botón para ir a otra pestaña)."""
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
    """Pestaña "Semana": genera el plan y lo muestra día por día."""

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
        """Crea el plan de 7 días, lo guarda y lo muestra."""
        # Leemos la configuración.
        config = almacen.cargar_config()
        # Leemos los temas.
        temas = almacen.cargar_temas()
        # Sin temas no hay nada que planificar.
        if not temas:
            # Explicamos qué hacer.
            messagebox.showinfo("Primero agrega temas", "Todavía no hay temas. Agrégalos en la pestaña Temas.",
                                parent=self.winfo_toplevel())
            # Llevamos al usuario a esa pestaña.
            self.app.cuaderno.select(self.app.pestana_temas)
            # Terminamos.
            return
        # Día de inicio: el indicado, el de la lista o el automático.
        desde = desde or self.fechas_inicio[max(self.inicio.current(), 0)] or repartidor.primer_dia_por_defecto(
            config["horario"], datetime.now())
        # Creamos el plan.
        plan = repartidor.generar_plan(temas, config, desde)
        # Lo guardamos en datos/plan.json.
        almacen.guardar_plan(repartidor.plan_a_dict(plan))
        # La ventana pasa a usar este plan.
        self.app.plan = plan
        # Ya no está desactualizado.
        self.app.plan_desactualizado = False
        # Redibujamos todas las pestañas.
        self.app.refrescar_todo()
        # Mensaje en la barra de abajo.
        self.app.avisar(f"Plan generado: {len(plan['sesiones'])} sesiones del {fecha_corta(plan['desde'])} al "
                        f"{fecha_corta(plan['hasta'])}. Para recibir los avisos, súbelo en la pestaña Google Calendar.")

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
            self._mostrar_avisos(avisos)
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
                          "temprano (pestaña Ajustes), o baja los minutos de algún tema.")
        # Mostramos los avisos.
        self._mostrar_avisos(avisos)
        # Dibujamos los 7 días.
        self._dibujar_dias(plan)
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

    def _mostrar_avisos(self, avisos):
        """Muestra los avisos debajo de las fechas, o esconde la línea si no hay ninguno."""
        # Texto de los avisos, uno por línea.
        self.aviso.configure(text="\n".join(avisos))
        # Si hay avisos, la línea se ve debajo de las fechas.
        if avisos:
            # La colocamos.
            self.aviso.pack(fill="x", pady=(6, 0), after=self.rango)
        # Si no, la escondemos para que no ocupe espacio.
        else:
            # La quitamos.
            self.aviso.pack_forget()

    def _dibujar_dias(self, plan):
        """Dibuja una columna por día, con sus sesiones como tarjetas de colores."""
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
            # Espacio al final de la columna.
            tk.Frame(dia, background=COLOR_TARJETA, height=8).pack()


class PestanaTemas(ttk.Frame):
    """Pestaña "Temas": lista de temas y formulario para agregarlos, cambiarlos o quitarlos."""

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
                        "Cuando termines, pulsa «Generar plan» en la pestaña Semana.")

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
        self.app.avisar(f"Quitado: «{nombre}». Pulsa «Generar plan» en la pestaña Semana para actualizar el plan.")


class PestanaGoogle(ttk.Frame):
    """Pestaña "Google Calendar": estado de la conexión, subir el plan y borrar sesiones."""

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
            self.info_plan.configure(text="Todavía no hay plan. Genéralo en la pestaña Semana.")
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
    """Pestaña "Ajustes": edita config.json con casillas en vez de a mano."""

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
        ttk.Label(cuerpo, text=f"Se guardan en {almacen.ARCHIVO_CONFIG}", style="Suave.TLabel").pack(
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
        ttk.Label(izquierda, text="«primary» es tu calendario principal (ver README, sección 7)",
                  style="TarjetaSuave.TLabel").grid(row=len(CAMPOS_NUMERICOS) * 2 + 1, column=0, columnspan=2, sticky="w")
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
        # Aquí armamos la configuración nueva.
        datos = {}
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
        self.app.avisar("Ajustes guardados. Pulsa «Generar plan» en la pestaña Semana para aplicarlos.")


class Aplicacion(tk.Tk):
    """La ventana principal: cabecera, pestañas y barra de mensajes."""

    def __init__(self):
        # Creamos la ventana.
        super().__init__()
        # Título de la ventana.
        self.title("Planificador de estudio")
        # Escala de la pantalla (1 = normal; 1.5 en pantallas con zoom del 150 %).
        self.escala = max(self.winfo_fpixels("1i") / 96, 1)
        # Tamaño inicial: el pensado o, si la pantalla es más pequeña, lo que quepa.
        ancho = min(int(1180 * self.escala), self.winfo_screenwidth() - 60)
        # Alto inicial.
        alto = min(int(780 * self.escala), self.winfo_screenheight() - 100)
        # Aplicamos el tamaño.
        self.geometry(f"{ancho}x{alto}")
        # Tamaño mínimo para que nada quede cortado.
        self.minsize(min(int(980 * self.escala), ancho), min(int(620 * self.escala), alto))
        # Color de fondo.
        self.configure(background=COLOR_FONDO)
        # Los mensajes de error hablan del botón, no del comando.
        almacen.COMO_GENERAR = "el botón «Generar plan» de la pestaña Semana"
        # Fuentes de letra.
        self.fuentes = self._crear_fuentes()
        # Colores y formas de los controles.
        self._aplicar_estilo()
        # Plan guardado (se lee en refrescar_todo).
        self.plan = None
        # True cuando cambiaron temas o ajustes y conviene volver a generar el plan.
        self.plan_desactualizado = False
        # True mientras se habla con Google.
        self.ocupado = False
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
            # Títulos de las pestañas.
            "titulo": tkfont.Font(self, family=familia, size=18, weight="bold"),
            # Nombre de la app en la cabecera.
            "marca": tkfont.Font(self, family=familia, size=15, weight="bold"),
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
                         troughcolor="#e9edf4", focuscolor=COLOR_ACENTO)
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
        estilo.map("TButton", background=[("disabled", "#f1f3f6"), ("pressed", "#d2e3fc"), ("active", COLOR_ACENTO_SUAVE)],
                   foreground=[("disabled", "#a0a6b0")], lightcolor=[("active", COLOR_ACENTO_SUAVE)],
                   darkcolor=[("active", COLOR_ACENTO_SUAVE)])
        # Botón principal: azul con letra blanca.
        estilo.configure("Acento.TButton", background=COLOR_ACENTO, foreground="white", bordercolor=COLOR_ACENTO,
                         lightcolor=COLOR_ACENTO, darkcolor=COLOR_ACENTO, font=self.fuentes["negrita"])
        # Botón principal al pasar el ratón o desactivado.
        estilo.map("Acento.TButton", background=[("disabled", "#a8c7fa"), ("pressed", "#174ea6"),
                                                 ("active", COLOR_ACENTO_OSCURO)],
                   foreground=[("disabled", "white")], bordercolor=[("disabled", "#a8c7fa")],
                   lightcolor=[("disabled", "#a8c7fa"), ("active", COLOR_ACENTO_OSCURO)],
                   darkcolor=[("disabled", "#a8c7fa"), ("active", COLOR_ACENTO_OSCURO)])
        # Botón de borrar: letra roja.
        estilo.configure("Peligro.TButton", foreground=COLOR_MAL)
        # Botón de borrar al pasar el ratón.
        estilo.map("Peligro.TButton", background=[("disabled", "#f1f3f6"), ("active", "#fce8e6")],
                   foreground=[("disabled", "#a0a6b0")], lightcolor=[("active", "#fce8e6")],
                   darkcolor=[("active", "#fce8e6")])
        # Pestañas: sin bordes, con margen.
        estilo.configure("TNotebook", background=COLOR_FONDO, borderwidth=0, tabmargins=(20, 6, 20, 0))
        # Cada pestaña.
        estilo.configure("TNotebook.Tab", background="#e6eaf2", foreground=COLOR_SUAVE, padding=(20, 8),
                         borderwidth=0, font=self.fuentes["negrita"], lightcolor="#e6eaf2", bordercolor=COLOR_FONDO)
        # Pestaña elegida y al pasar el ratón.
        estilo.map("TNotebook.Tab", background=[("selected", COLOR_FONDO), ("active", "#eef1f7")],
                   foreground=[("selected", COLOR_ACENTO)], lightcolor=[("selected", COLOR_FONDO)],
                   expand=[("selected", (0, 2, 0, 0))])
        # Tablas.
        estilo.configure("Treeview", background=COLOR_TARJETA, fieldbackground=COLOR_TARJETA, foreground=COLOR_TEXTO,
                         rowheight=int(30 * self.escala), bordercolor=COLOR_BORDE, borderwidth=1)
        # Fila elegida.
        estilo.map("Treeview", background=[("selected", "#d2e3fc")], foreground=[("selected", COLOR_TEXTO)])
        # Títulos de las columnas.
        estilo.configure("Treeview.Heading", background="#eef1f7", foreground=COLOR_TEXTO, relief="flat",
                         font=self.fuentes["negrita"], padding=(8, 6), lightcolor="#eef1f7", darkcolor="#eef1f7",
                         bordercolor=COLOR_BORDE)
        # Títulos al pasar el ratón.
        estilo.map("Treeview.Heading", background=[("active", "#e4e9f2")])
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
        estilo.configure("Horizontal.TProgressbar", background=COLOR_ACENTO, troughcolor="#e9edf4",
                         bordercolor="#e9edf4", lightcolor=COLOR_ACENTO, darkcolor=COLOR_ACENTO, thickness=6)
        # Barras de desplazamiento discretas.
        estilo.configure("Vertical.TScrollbar", background="#d5dbe5", troughcolor=COLOR_FONDO,
                         bordercolor=COLOR_FONDO, arrowcolor=COLOR_SUAVE, lightcolor="#d5dbe5", darkcolor="#d5dbe5")
        # Lista que se despliega en las Combobox (es un control clásico: se configura aparte).
        self.option_add("*TCombobox*Listbox.background", COLOR_TARJETA)
        # Fila elegida de esa lista.
        self.option_add("*TCombobox*Listbox.selectBackground", "#d2e3fc")
        # Texto de la fila elegida.
        self.option_add("*TCombobox*Listbox.selectForeground", COLOR_TEXTO)
        # Fuente de esa lista.
        self.option_add("*TCombobox*Listbox.font", self.fuentes["normal"])

    def _construir(self):
        """Crea la cabecera, las pestañas y la barra de mensajes."""
        # Cabecera azul oscuro.
        cabecera = tk.Frame(self, background="#173a73", padx=28, pady=14)
        # Arriba del todo.
        cabecera.pack(fill="x")
        # Nombre de la app.
        tk.Label(cabecera, text="Planificador de estudio", font=self.fuentes["marca"], background="#173a73",
                 foreground="white").pack(side="left")
        # Próxima sesión (a la derecha de la cabecera).
        self.proxima = tk.Label(cabecera, font=self.fuentes["normal"], background="#173a73", foreground="#d6e2ff")
        # A la derecha.
        self.proxima.pack(side="right")
        # Barra de mensajes, abajo del todo.
        self.barra_avisos = tk.Label(self, anchor="w", font=self.fuentes["normal"], background="#e9edf4",
                                     foreground=COLOR_TEXTO, padx=28, pady=7)
        # Abajo.
        self.barra_avisos.pack(side="bottom", fill="x")
        # Pestañas.
        self.cuaderno = ttk.Notebook(self)
        # Ocupan el resto de la ventana.
        self.cuaderno.pack(fill="both", expand=True, pady=(8, 0))
        # Pestaña Hoy.
        self.pestana_hoy = PestanaHoy(self.cuaderno, self)
        # Pestaña Semana.
        self.pestana_semana = PestanaSemana(self.cuaderno, self)
        # Pestaña Temas.
        self.pestana_temas = PestanaTemas(self.cuaderno, self)
        # Pestaña Google Calendar.
        self.pestana_google = PestanaGoogle(self.cuaderno, self)
        # Pestaña Ajustes.
        self.pestana_ajustes = PestanaAjustes(self.cuaderno, self)
        # Añadimos las pestañas en orden, con su título.
        for pestana, titulo in ((self.pestana_hoy, "Hoy"), (self.pestana_semana, "Semana"),
                                (self.pestana_temas, "Temas"), (self.pestana_google, "Google Calendar"),
                                (self.pestana_ajustes, "Ajustes")):
            # Añadimos la pestaña.
            self.cuaderno.add(pestana, text=titulo)
        # Al cambiar de pestaña, la actualizamos (por ejemplo, para ver si ya está credentials.json).
        self.cuaderno.bind("<<NotebookTabChanged>>", self._al_cambiar_pestana)

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

    def refrescar_todo(self, salvo=None):
        """Vuelve a leer el plan y redibuja todas las pestañas (menos `salvo`, si se indica)."""
        # Releemos el plan del disco.
        self.leer_plan()
        # Redibujamos cada pestaña.
        for pestana in (self.pestana_hoy, self.pestana_semana, self.pestana_temas, self.pestana_google,
                        self.pestana_ajustes):
            # Saltamos la indicada (por ejemplo, Ajustes justo después de guardar).
            if pestana is not salvo:
                # La redibujamos.
                pestana.refrescar()
        # Cabecera con la próxima sesión.
        self._actualizar_cabecera()

    def _actualizar_cabecera(self):
        """Muestra en la cabecera cuál es la próxima sesión."""
        # Fecha y hora actuales.
        ahora = datetime.now()
        # Próxima sesión que no terminó.
        sesion = proxima_sesion(self.plan, ahora)
        # Si no hay, dejamos la cabecera sin texto.
        if sesion is None:
            # Sin texto.
            self.proxima.configure(text="")
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
        # Texto de la cabecera.
        self.proxima.configure(text=f"Próxima sesión:  {cuando}  ·  {sesion.tema}")

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

    def en_segundo_plano(self, tarea, al_terminar):
        """Ejecuta `tarea` sin congelar la ventana y, cuando acaba, llama a `al_terminar(resultado)`."""
        # Marcamos la ventana como ocupada.
        self.ocupado = True
        # Bloqueamos los botones de Google.
        self.pestana_google.ocupado(True)

        def trabajar():
            # Lo que imprima Google (por ejemplo, la dirección para dar permiso) va al registro.
            try:
                # Desviamos print() hacia la cola.
                with redirect_stdout(EscritorCola(self.cola)):
                    # Hacemos la tarea.
                    resultado = tarea()
            # Errores pensados para el usuario.
            except almacen.ErrorPlanificador as error:
                # Los mandamos a la ventana.
                self.cola.put(("error", str(error)))
            # Cualquier otro error (no debería pasar).
            except Exception:  # noqa: BLE001 - lo mostramos en la ventana en vez de perderlo.
                # Mandamos el detalle técnico a la ventana.
                self.cola.put(("fallo", traceback.format_exc()))
            # Si todo fue bien...
            else:
                # ...mandamos el resultado.
                self.cola.put(("listo", al_terminar, resultado))

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
            # Una línea para el registro.
            if mensaje[0] == "registro":
                # La escribimos.
                self.pestana_google.escribir(mensaje[1])
                # Siguiente mensaje.
                continue
            # Cualquier otro mensaje significa que la tarea terminó.
            self.ocupado = False
            # Desbloqueamos los botones.
            self.pestana_google.ocupado(False)
            # Terminó bien: seguimos con lo que había que hacer después.
            if mensaje[0] == "listo":
                # Llamamos a la función con el resultado.
                mensaje[1](mensaje[2])
            # Error pensado para el usuario.
            elif mensaje[0] == "error":
                # Lo apuntamos en el registro.
                self.pestana_google.escribir(f"Error: {mensaje[1]}")
                # Y lo mostramos.
                messagebox.showerror("No se pudo completar", mensaje[1], parent=self)
            # Error inesperado.
            else:
                # Lo mostramos con el detalle técnico.
                self._mostrar_fallo(mensaje[1])

    def _cada_minuto(self):
        """Actualiza la pestaña Hoy y la cabecera (para que "Ahora" y "Siguiente" estén al día)."""
        # Redibujamos Hoy.
        self.pestana_hoy.refrescar()
        # Y la cabecera.
        self._actualizar_cabecera()
        # Volvemos a hacerlo dentro de un minuto.
        self._id_minuto = self.after(60_000, self._cada_minuto)

    def _al_cambiar_pestana(self, _evento=None):
        """Actualiza la pestaña que se acaba de abrir."""
        # Pestaña elegida.
        elegida = self.nametowidget(self.cuaderno.select())
        # Hoy y Google dependen de la hora o de archivos que pueden cambiar fuera de la ventana.
        if elegida in (self.pestana_hoy, self.pestana_google):
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
                "Hay una tarea en curso", "Todavía se está hablando con Google Calendar. ¿Cerrar igualmente?",
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

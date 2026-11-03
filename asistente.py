"""Asistente de estudio con inteligencia artificial (Claude o Gemini).

Hablas con él en lenguaje normal ("el viernes tengo examen de química", "hoy no pude estudiar inglés")
y él usa "herramientas" para mirar y cambiar tus datos: temas, metas, sesiones hechas, horario y plan.

  - Claude (de Anthropic): de pago; necesitas una clave de platform.claude.com con saldo.
  - Gemini (de Google): tiene un nivel gratuito con límites; la clave se saca en aistudio.google.com.

La clave se guarda en datos/claves.json (nunca se sube a internet). Ver GUIA_DE_INICIO.md, paso 7.
"""

# json convierte los datos en texto para enviárselos a la IA.
import json
# os permite leer la clave de una variable de entorno, si no está en datos/claves.json.
import os
# Herramientas de fechas.
from datetime import datetime

# Módulo que guarda y lee los datos.
import almacen
# Lo hecho, las metas y el plan adaptado.
import progreso
# Error pensado para el usuario.
from almacen import ErrorPlanificador

# Máximo de herramientas seguidas que puede usar la IA en una sola respuesta (evita bucles).
MAX_VUELTAS = 12
# Nombre que se muestra de cada proveedor.
NOMBRES = {"claude": "Claude", "gemini": "Gemini"}
# Variables de entorno donde también se busca la clave.
VARIABLES_CLAVE = {"claude": ("ANTHROPIC_API_KEY",), "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
# Días de la semana con tilde, para mostrarlos (lunes = 0).
DIAS_VISIBLES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Instrucciones fijas para la IA (no cambian durante la conversación; así se reaprovechan entre mensajes).
SISTEMA = """Eres el asistente del «Planificador de estudio», una app que reparte el tiempo de estudio \
en sesiones cortas y las sube a Google Calendar para que el teléfono avise. Hablas con el estudiante \
dentro de la app.

Tu trabajo es ayudarle a planificar sus metas (exámenes, entregas, objetivos) y a cumplirlas: llevar \
la cuenta de lo que hace y de lo que no, y adaptar el plan a lo que de verdad consigue.

Cómo funciona la app (para que lo expliques si hace falta):
- Cada tema tiene prioridad (1 a 5) y minutos por semana. El plan de 7 días parte esos minutos en \
sesiones cortas con descansos, según el horario y el máximo diario.
- Cada sesión se marca como hecha o no hecha. Lo no hecho de los últimos 14 días se recupera en el \
siguiente plan, si cabe.
- Una meta con tema y fecha hace que ese tema suba de prioridad las dos semanas anteriores y que sus \
sesiones vayan antes de esa fecha.
- El plan se sube a Google Calendar desde la sección «Google Calendar» de la ventana \
(o con «python planificador.py subir --reemplazar»). Tú no puedes subirlo.

Cómo trabajar:
- Usa ver_estado al empezar la conversación y antes de aconsejar o cambiar algo. No inventes datos.
- Si cuenta que hizo o no hizo una sesión, márcala con marcar_sesion (pregunta si no está claro cuál).
- Si menciona un examen, una entrega u otro objetivo con fecha, guárdalo con agregar_meta, con su tema \
si existe.
- Si ves que no llega (muchas sesiones no hechas o poco cumplimiento), propón ajustes realistas: menos \
minutos, otros días u horas, otra prioridad, o olvidar lo pendiente si ya no tiene sentido recuperarlo. \
Explica el porqué en una frase.
- Después de cambiar temas, metas u horario, usa generar_plan y recuérdale que suba el plan nuevo.
- Pide confirmación antes de quitar temas o metas, o de cambiar mucho el plan.
- Guarda con guardar_nota lo que convenga recordar para próximas conversaciones (preferencias, \
dificultades, cómo le fue en un examen).
- Responde breve, cercano y en el idioma del estudiante (normalmente español), en texto sencillo: sin \
formato Markdown (ni asteriscos ni almohadillas) ni tablas; para listas cortas, usa guiones.
- Si notas mucho estrés o cansancio, anímale a descansar; no das consejos médicos."""

# Herramientas que puede usar la IA: nombre, explicación y datos que recibe (en formato JSON Schema).
HERRAMIENTAS = [
    {
        "nombre": "ver_estado",
        "descripcion": "Devuelve la fecha y hora actuales, los temas, el horario, el plan de la semana (cada "
                       "sesión con su estado: hecha, no hecha o sin marcar), el progreso de los últimos 14 días, "
                       "lo pendiente de recuperar, las metas y las notas guardadas.",
        "parametros": {"type": "object", "properties": {}, "required": []},
    },
    {
        "nombre": "guardar_tema",
        "descripcion": "Agrega un tema o cambia uno que ya existe (mismo nombre, sin importar mayúsculas ni tildes).",
        "parametros": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre del tema, por ejemplo «Química»."},
                "prioridad": {"type": "integer", "description": "De 1 (baja) a 5 (alta)."},
                "minutos_semana": {"type": "integer", "description": "Minutos por semana para el tema."},
            },
            "required": ["nombre", "prioridad", "minutos_semana"],
        },
    },
    {
        "nombre": "quitar_tema",
        "descripcion": "Quita un tema. Pide confirmación al estudiante antes de usarla.",
        "parametros": {"type": "object", "properties": {"nombre": {"type": "string"}}, "required": ["nombre"]},
    },
    {
        "nombre": "agregar_meta",
        "descripcion": "Guarda una meta (examen, entrega, objetivo). Con tema y fecha, el plan se adapta a ella.",
        "parametros": {
            "type": "object",
            "properties": {
                "texto": {"type": "string", "description": "La meta, por ejemplo «Examen de Química»."},
                "tema": {"type": "string", "description": "Tema relacionado (uno de los temas), o vacío."},
                "fecha": {"type": "string", "description": "Fecha límite AAAA-MM-DD, o vacío si no tiene."},
            },
            "required": ["texto"],
        },
    },
    {
        "nombre": "marcar_meta",
        "descripcion": "Marca una meta como cumplida (true) o como pendiente otra vez (false).",
        "parametros": {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "cumplida": {"type": "boolean"}},
            "required": ["id", "cumplida"],
        },
    },
    {
        "nombre": "quitar_meta",
        "descripcion": "Quita una meta. Pide confirmación al estudiante antes de usarla.",
        "parametros": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
    },
    {
        "nombre": "marcar_sesion",
        "descripcion": "Marca una sesión del plan como hecha, no hecha o sin marcar. Si ese día hay varias del "
                       "mismo tema y no se indica la hora, marca la primera que todavía no tenga ese estado.",
        "parametros": {
            "type": "object",
            "properties": {
                "fecha": {"type": "string", "description": "Día de la sesión, AAAA-MM-DD."},
                "tema": {"type": "string"},
                "estado": {"type": "string", "enum": ["hecha", "no_hecha", "sin_marcar"]},
                "hora": {"type": "string", "description": "Hora de inicio HH:MM (opcional)."},
            },
            "required": ["fecha", "tema", "estado"],
        },
    },
    {
        "nombre": "olvidar_pendiente",
        "descripcion": "Deja de contar lo pendiente de recuperar de un tema (cuando ya no tiene sentido recuperarlo).",
        "parametros": {"type": "object", "properties": {"tema": {"type": "string"}}, "required": ["tema"]},
    },
    {
        "nombre": "cambiar_horario",
        "descripcion": "Cambia la hora de inicio de un día de estudio, o deja de estudiar ese día (hora vacía).",
        "parametros": {
            "type": "object",
            "properties": {
                "dia": {"type": "string", "enum": almacen.DIAS_SEMANA},
                "hora": {"type": "string", "description": "Hora de inicio HH:MM, o vacío para no estudiar ese día."},
            },
            "required": ["dia", "hora"],
        },
    },
    {
        "nombre": "cambiar_maximo_diario",
        "descripcion": "Cambia el máximo de minutos de estudio por día (0 = sin límite).",
        "parametros": {"type": "object", "properties": {"minutos": {"type": "integer"}}, "required": ["minutos"]},
    },
    {
        "nombre": "generar_plan",
        "descripcion": "Crea de nuevo el plan de 7 días, adaptado a lo hecho, lo pendiente y las metas. No lo sube "
                       "a Google Calendar.",
        "parametros": {
            "type": "object",
            "properties": {"desde": {"type": "string", "description": "Primer día AAAA-MM-DD (opcional)."}},
            "required": [],
        },
    },
    {
        "nombre": "guardar_nota",
        "descripcion": "Guarda algo que convenga recordar en próximas conversaciones.",
        "parametros": {"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]},
    },
    {
        "nombre": "borrar_nota",
        "descripcion": "Borra una nota guardada que ya no sirve.",
        "parametros": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
    },
]


def ahora_texto(ahora=None):
    """Fecha y hora en palabras, por ejemplo "domingo 25/10/2026, 19:05"."""
    # Momento actual.
    ahora = ahora or datetime.now()
    # Día de la semana, fecha y hora.
    return f"{DIAS_VISIBLES[ahora.weekday()]} {ahora:%d/%m/%Y, %H:%M}"


def estado_actual(ahora=None):
    """Todo lo que la IA necesita saber, como un diccionario."""
    # Momento actual.
    ahora = ahora or datetime.now()
    # Ajustes.
    config = almacen.cargar_config()
    # Temas.
    temas = almacen.cargar_temas()
    # Registro de lo hecho.
    registro = almacen.cargar_registro()
    # Plan (o None).
    plan = progreso.plan_guardado()
    # Estado básico.
    estado = {
        # Fecha y hora.
        "ahora": ahora_texto(ahora),
        # Temas.
        "temas": [{"nombre": t["nombre"], "prioridad": t["prioridad"], "minutos_semana": t["minutos_semana"]}
                  for t in temas],
        # Horario y límites.
        "horario": config["horario"],
        # Máximo diario.
        "maximo_minutos_por_dia": config["maximo_minutos_por_dia"],
        # Duración de cada sesión.
        "duracion_sesion": config["duracion_sesion"],
        # Si se recupera lo no hecho.
        "recuperar_no_hechas": config["recuperar_no_hechas"],
        # Plan (se rellena abajo).
        "plan": None,
    }
    # Si hay plan, lo describimos día por día.
    if plan is not None:
        # Días con sus sesiones.
        dias = {}
        # Cada sesión.
        for sesion in plan["sesiones"]:
            # Clave del día, por ejemplo "2026-10-26 (lunes)".
            dia = f"{sesion.inicio:%Y-%m-%d} ({DIAS_VISIBLES[sesion.inicio.weekday()]})"
            # Línea de la sesión.
            linea = (f"{sesion.inicio:%H:%M}-{sesion.fin:%H:%M} {sesion.tema}"
                     f"{' (recuperación)' if sesion.recuperacion else ''}: "
                     f"{progreso.NOMBRES_ESTADO[progreso.estado_de(registro, sesion)]}")
            # La añadimos a su día.
            dias.setdefault(dia, []).append(linea)
        # Plan resumido.
        estado["plan"] = {"desde": plan["desde"].isoformat(), "hasta": plan["hasta"].isoformat(), "dias": dias,
                          "minutos_que_no_entraron": sum(s.minutos for s in plan["sin_lugar"]),
                          "notas": plan.get("notas", [])}
    # Progreso de los últimos 14 días.
    estado["progreso_14_dias"] = progreso.resumen(registro, plan, temas, ahora)
    # Metas.
    estado["metas"] = almacen.cargar_metas()
    # Notas guardadas.
    estado["notas_guardadas"] = almacen.cargar_memoria()
    # Listo.
    return estado


def _texto(argumentos, clave):
    """Lee un argumento de texto (vacío si no viene)."""
    # Valor como texto, sin espacios sobrantes.
    return str(argumentos.get(clave) or "").strip()


def _entero(argumentos, clave):
    """Lee un argumento que debe ser un número entero."""
    # Intentamos convertirlo.
    try:
        # Número entero.
        return int(argumentos.get(clave))
    # Si no es un número, avisamos.
    except (TypeError, ValueError) as error:
        # Mensaje para la IA.
        raise ErrorPlanificador(f'"{clave}" tiene que ser un número entero.') from error


def ejecutar(nombre, argumentos, ahora=None):
    """Ejecuta una herramienta. Devuelve (resultado para la IA, ¿fue un error?, resumen para el usuario)."""
    # Argumentos como diccionario (algunas IA mandan None si no hay).
    argumentos = dict(argumentos or {})
    # Momento actual.
    ahora = ahora or datetime.now()
    # Lo intentamos; los errores se le devuelven a la IA para que los corrija o los explique.
    try:
        # Buscamos la función de la herramienta.
        funcion = _FUNCIONES.get(nombre)
        # Si no existe, avisamos.
        if funcion is None:
            # Error para la IA.
            raise ErrorPlanificador(f"No existe la herramienta «{nombre}».")
        # La ejecutamos.
        resultado, resumen = funcion(argumentos, ahora)
        # Todo bien.
        return resultado, False, resumen
    # Error con explicación.
    except ErrorPlanificador as error:
        # Lo devolvemos como error.
        return f"Error: {error}", True, f"No se pudo: {error}"


def _ver_estado(_argumentos, ahora):
    # Estado completo como texto JSON.
    return json.dumps(estado_actual(ahora), ensure_ascii=False), "Consultando tus datos…"


def _guardar_tema(argumentos, _ahora):
    # Temas guardados.
    temas = almacen.cargar_temas()
    # Agregar o actualizar.
    es_nuevo = almacen.agregar_tema(temas, _texto(argumentos, "nombre"), _entero(argumentos, "prioridad"),
                                    _entero(argumentos, "minutos_semana"))
    # Guardamos.
    almacen.guardar_temas(temas)
    # Texto del resultado.
    texto = (f"Tema «{_texto(argumentos, 'nombre')}» {'agregado' if es_nuevo else 'actualizado'}: prioridad "
             f"{argumentos['prioridad']}, {argumentos['minutos_semana']} min por semana.")
    # Mismo texto para la IA y para el usuario.
    return texto, texto


def _quitar_tema(argumentos, _ahora):
    # Temas guardados.
    temas = almacen.cargar_temas()
    # Quitamos el tema.
    quitado = almacen.quitar_tema(temas, _texto(argumentos, "nombre"))
    # Guardamos.
    almacen.guardar_temas(temas)
    # Texto del resultado.
    texto = f"Tema «{quitado['nombre']}» quitado."
    # Mismo texto para los dos.
    return texto, texto


def _agregar_meta(argumentos, ahora):
    # Metas guardadas.
    metas = almacen.cargar_metas()
    # Nueva meta.
    meta = progreso.agregar_meta(metas, _texto(argumentos, "texto"), _texto(argumentos, "tema") or None,
                                 _texto(argumentos, "fecha") or None, almacen.cargar_temas(), ahora.date())
    # Guardamos.
    almacen.guardar_metas(metas)
    # Resultado.
    return (json.dumps(meta, ensure_ascii=False), f"Meta guardada: {progreso.texto_meta(meta)}.")


def _marcar_meta(argumentos, _ahora):
    # Metas guardadas.
    metas = almacen.cargar_metas()
    # Cambiamos su estado.
    meta = progreso.cumplir_meta(metas, _entero(argumentos, "id"), bool(argumentos.get("cumplida")))
    # Guardamos.
    almacen.guardar_metas(metas)
    # Texto del resultado.
    texto = f"Meta «{meta['texto']}» marcada como {'cumplida' if meta['cumplida'] else 'pendiente'}."
    # Mismo texto para los dos.
    return texto, texto


def _quitar_meta(argumentos, _ahora):
    # Metas guardadas.
    metas = almacen.cargar_metas()
    # La quitamos.
    meta = progreso.quitar_meta(metas, _entero(argumentos, "id"))
    # Guardamos.
    almacen.guardar_metas(metas)
    # Texto del resultado.
    texto = f"Meta «{meta['texto']}» quitada."
    # Mismo texto para los dos.
    return texto, texto


def _marcar_sesion(argumentos, ahora):
    # Estado pedido ("sin_marcar" = quitar la marca).
    estado = _texto(argumentos, "estado")
    # Solo estados conocidos.
    if estado not in ("hecha", "no_hecha", "sin_marcar"):
        # Error para la IA.
        raise ErrorPlanificador('"estado" debe ser "hecha", "no_hecha" o "sin_marcar".')
    # Día de la sesión.
    fecha = progreso.leer_fecha(_texto(argumentos, "fecha"))
    # Registro de lo hecho.
    registro = almacen.cargar_registro()
    # Marcamos.
    sesion = progreso.marcar_por_tema(registro, progreso.plan_guardado(), fecha, _texto(argumentos, "tema"),
                                      None if estado == "sin_marcar" else estado, _texto(argumentos, "hora") or None,
                                      ahora)
    # Guardamos.
    almacen.guardar_registro(registro)
    # Texto del resultado.
    texto = (f"Sesión de «{sesion.tema}» del {sesion.inicio:%d/%m} a las {sesion.inicio:%H:%M} marcada como "
             f"{progreso.NOMBRES_ESTADO[None if estado == 'sin_marcar' else estado]}.")
    # Mismo texto para los dos.
    return texto, texto


def _olvidar_pendiente(argumentos, ahora):
    # Tema indicado (tiene que existir).
    tema = almacen.buscar_tema(almacen.cargar_temas(), _texto(argumentos, "tema"))
    # Si no existe, avisamos.
    if tema is None:
        # Error para la IA.
        raise ErrorPlanificador(f"No hay ningún tema llamado «{_texto(argumentos, 'tema')}».")
    # Registro de lo hecho.
    registro = almacen.cargar_registro()
    # Olvidamos lo pendiente.
    progreso.olvidar_pendiente(registro, tema["nombre"], ahora)
    # Guardamos.
    almacen.guardar_registro(registro)
    # Texto del resultado.
    texto = f"Ya no se recupera lo pendiente de «{tema['nombre']}»."
    # Mismo texto para los dos.
    return texto, texto


def _cambiar_horario(argumentos, _ahora):
    # Ajustes actuales.
    config = almacen.cargar_config()
    # Día (sin tildes ni mayúsculas).
    dia = almacen.quitar_tildes(_texto(argumentos, "dia"))
    # Tiene que ser un día de la semana.
    if dia not in almacen.DIAS_SEMANA:
        # Error para la IA.
        raise ErrorPlanificador(f"«{_texto(argumentos, 'dia')}» no es un día de la semana.")
    # Hora nueva (vacía = no estudiar ese día).
    hora = _texto(argumentos, "hora")
    # Copia del horario.
    horario = dict(config["horario"])
    # Con hora: se estudia ese día a esa hora.
    if hora:
        # Revisamos el formato.
        almacen.leer_hora(hora)
        # Cambiamos.
        horario[dia] = hora
    # Sin hora: ese día no se estudia.
    else:
        # Quitamos el día.
        horario.pop(dia, None)
    # Guardamos (aquí se revisa que quede al menos un día).
    almacen.guardar_config({**config, "horario": horario})
    # Texto del resultado.
    texto = (f"Ahora el {DIAS_VISIBLES[almacen.DIAS_SEMANA.index(dia)]} empiezas a las {hora}." if hora else
             f"Ya no estudias los {DIAS_VISIBLES[almacen.DIAS_SEMANA.index(dia)]}.")
    # Mismo texto para los dos.
    return texto, texto


def _cambiar_maximo_diario(argumentos, _ahora):
    # Ajustes actuales.
    config = almacen.cargar_config()
    # Minutos nuevos.
    minutos = _entero(argumentos, "minutos")
    # Guardamos (aquí se revisa el valor).
    almacen.guardar_config({**config, "maximo_minutos_por_dia": minutos})
    # Texto del resultado.
    texto = f"Máximo diario: {progreso.minutos_a_texto(minutos) if minutos else 'sin límite'}."
    # Mismo texto para los dos.
    return texto, texto


def _generar_plan(argumentos, ahora):
    # Primer día (si se indicó).
    desde = progreso.leer_fecha(_texto(argumentos, "desde"), "la fecha de inicio") if _texto(argumentos, "desde") else None
    # Generamos y guardamos el plan.
    plan = progreso.generar_y_guardar(desde, ahora)
    # Resultado para la IA.
    resultado = {"desde": plan["desde"].isoformat(), "hasta": plan["hasta"].isoformat(),
                 "sesiones": len(plan["sesiones"]), "minutos": sum(s.minutos for s in plan["sesiones"]),
                 "minutos_que_no_entraron": sum(s.minutos for s in plan["sin_lugar"]), "notas": plan["notas"],
                 "recordatorio": "El plan no se ha subido a Google Calendar: recuérdale subirlo."}
    # Resumen para el usuario.
    resumen = (f"Plan nuevo del {plan['desde']:%d/%m} al {plan['hasta']:%d/%m}: {len(plan['sesiones'])} sesiones. "
               "Súbelo en la sección «Google Calendar».")
    # Los dos.
    return json.dumps(resultado, ensure_ascii=False), resumen


def _guardar_nota(argumentos, ahora):
    # Texto de la nota.
    texto = _texto(argumentos, "texto")
    # Tiene que tener algo.
    if not texto:
        # Error para la IA.
        raise ErrorPlanificador("La nota está vacía.")
    # Notas guardadas.
    notas = almacen.cargar_memoria()
    # Número nuevo.
    nuevo_id = max((n.get("id", 0) for n in notas), default=0) + 1
    # Añadimos la nota con la fecha.
    notas.append({"id": nuevo_id, "texto": texto, "fecha": ahora.date().isoformat()})
    # Si hay muchas, nos quedamos con las 40 más recientes.
    del notas[:-40]
    # Guardamos.
    almacen.guardar_memoria(notas)
    # Resultado.
    return f"Nota {nuevo_id} guardada.", f"Lo apunto para recordarlo: {texto}"


def _borrar_nota(argumentos, _ahora):
    # Notas guardadas.
    notas = almacen.cargar_memoria()
    # Número de la nota.
    identificador = _entero(argumentos, "id")
    # Notas sin esa.
    restantes = [n for n in notas if n.get("id") != identificador]
    # Si no estaba, avisamos.
    if len(restantes) == len(notas):
        # Error para la IA.
        raise ErrorPlanificador(f"No hay ninguna nota con el número {identificador}.")
    # Guardamos.
    almacen.guardar_memoria(restantes)
    # Texto del resultado.
    return f"Nota {identificador} borrada.", "Borré una nota que ya no servía."


# Función de cada herramienta.
_FUNCIONES = {
    "ver_estado": _ver_estado, "guardar_tema": _guardar_tema, "quitar_tema": _quitar_tema,
    "agregar_meta": _agregar_meta, "marcar_meta": _marcar_meta, "quitar_meta": _quitar_meta,
    "marcar_sesion": _marcar_sesion, "olvidar_pendiente": _olvidar_pendiente, "cambiar_horario": _cambiar_horario,
    "cambiar_maximo_diario": _cambiar_maximo_diario, "generar_plan": _generar_plan, "guardar_nota": _guardar_nota,
    "borrar_nota": _borrar_nota,
}


def _es_error_de_red(error):
    """True si el error es de conexión (sin internet, tiempo agotado...)."""
    # Errores del sistema (por ejemplo, sin red) o de la librería de conexiones.
    return isinstance(error, OSError) or any(
        clase.__name__ in ("TransportError", "TimeoutException", "NetworkError", "ConnectError")
        for clase in type(error).__mro__)


class ConversacionClaude:
    """Conversación con Claude (Anthropic) usando sus herramientas."""

    # Modelos que aceptan el reintento automático en otro modelo si este rechaza la petición.
    CON_RESPALDO = ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1")
    # Prefijos de modelos que aceptan "effort" (cuánto piensa antes de responder).
    CON_ESFUERZO = ("claude-opus-5", "claude-sonnet-5", "claude-haiku-5", "claude-fable-5", "claude-opus-4-6",
                    "claude-opus-4-7", "claude-opus-4-8", "claude-sonnet-4-6")

    def __init__(self, clave, modelo):
        # Importamos aquí la librería: así el resto de la app funciona aunque no esté instalada.
        try:
            # Librería oficial de Anthropic.
            import anthropic
        # Si falta, explicamos cómo instalarla.
        except ImportError as error:
            # Mensaje para el usuario.
            raise ErrorPlanificador("Falta la librería de Claude. Instálala con:\n"
                                    "  python -m pip install -r requirements.txt") from error
        # Guardamos el módulo para reconocer sus errores.
        self._anthropic = anthropic
        # Cliente (2 reintentos automáticos si hay un fallo pasajero).
        self.cliente = anthropic.Anthropic(api_key=clave, timeout=120.0, max_retries=2)
        # Modelo elegido.
        self.modelo = modelo
        # Nombre para mostrar.
        self.nombre = f"Claude ({modelo})"
        # Historial de la conversación.
        self.mensajes = []
        # Herramientas en el formato de Claude.
        self.herramientas = [{"name": h["nombre"], "description": h["descripcion"], "input_schema": h["parametros"]}
                             for h in HERRAMIENTAS]

    def _pedir(self):
        """Envía la conversación a Claude y devuelve su respuesta."""
        # Opciones según lo que acepte el modelo.
        extra = {}
        # Cuánto piensa: "medium" equilibra calidad, rapidez y coste para este tipo de ayuda.
        if self.modelo.startswith(self.CON_ESFUERZO):
            # Esfuerzo medio.
            extra["output_config"] = {"effort": "medium"}
        # Si el modelo rechaza la petición por precaución, el servidor la reintenta en otro modelo adecuado.
        if self.modelo in self.CON_RESPALDO:
            # Respaldo automático.
            extra.update(fallbacks="default", betas=["server-side-fallback-2026-07-01"])
        # Petición.
        return self.cliente.beta.messages.create(
            # Modelo.
            model=self.modelo,
            # Espacio para pensar y responder.
            max_tokens=16000,
            # Instrucciones fijas.
            system=SISTEMA,
            # Herramientas.
            tools=self.herramientas,
            # Conversación completa (Claude no recuerda nada entre peticiones).
            messages=self.mensajes,
            # Reaprovecha lo ya enviado (instrucciones e historial) para que cada mensaje cueste menos.
            cache_control={"type": "ephemeral"},
            # Opciones según el modelo.
            **extra,
        )

    def _traducir_error(self, error):
        """Convierte un error de Claude en un mensaje claro."""
        # Módulo de Anthropic.
        a = self._anthropic
        # Clave incorrecta.
        if isinstance(error, a.AuthenticationError):
            # Mensaje.
            return "La clave de Claude no es válida. Revísala en la sección Asistente (botón «Cambiar IA o clave»)."
        # Sin permiso.
        if isinstance(error, a.PermissionDeniedError):
            # Mensaje.
            return f"Tu clave de Claude no tiene permiso para usar «{self.modelo}»."
        # Modelo desconocido.
        if isinstance(error, a.NotFoundError):
            # Mensaje.
            return f"Claude no reconoce el modelo «{self.modelo}». Revisa «modelo_claude» en config.json."
        # Demasiadas peticiones.
        if isinstance(error, a.RateLimitError):
            # Mensaje.
            return "Claude recibió demasiadas peticiones seguidas. Espera un minuto y vuelve a intentarlo."
        # Petición rechazada (por ejemplo, sin saldo).
        if isinstance(error, a.BadRequestError):
            # Sin saldo.
            if "credit" in str(error).lower():
                # Mensaje.
                return ("Tu cuenta de Claude no tiene saldo. Compra créditos en platform.claude.com "
                        "(Settings → Billing) o usa Gemini, que tiene un nivel gratuito.")
            # Otro motivo.
            return f"Claude rechazó la petición: {getattr(error, 'message', error)}"
        # Problema en los servidores de Anthropic.
        if isinstance(error, a.APIStatusError):
            # Mensaje.
            return "Claude está saturado o con problemas ahora mismo. Vuelve a intentarlo en un rato."
        # Sin conexión o tiempo agotado.
        if isinstance(error, a.APIConnectionError):
            # Mensaje.
            return "No se pudo conectar con Claude. Revisa tu conexión a internet."
        # Otro error (no debería pasar).
        return None

    def enviar(self, texto, avisar=None):
        """Envía un mensaje del usuario y devuelve la respuesta de Claude (usando herramientas si hace falta).

        `avisar(texto)` se llama cada vez que Claude usa una herramienta, para mostrarlo al usuario.
        """
        # Mensaje del usuario, con la fecha y hora (así Claude sabe qué día es).
        self.mensajes.append({"role": "user", "content": f"[{ahora_texto()}]\n{texto}"})
        # Ida y vuelta: Claude responde o pide usar herramientas.
        for _vuelta in range(MAX_VUELTAS):
            # Pedimos la respuesta.
            try:
                # Respuesta de Claude.
                respuesta = self._pedir()
            # Errores de Anthropic: los explicamos.
            except self._anthropic.APIError as error:
                # Mensaje claro.
                mensaje = self._traducir_error(error)
                # Si no lo reconocemos, que se vea tal cual.
                if mensaje is None:
                    # Lo volvemos a lanzar.
                    raise
                # Error para el usuario.
                raise ErrorPlanificador(mensaje) from error
            # Si el modelo rechazó responder, lo decimos (el historial queda en orden).
            if respuesta.stop_reason == "refusal":
                # Respuesta corta en el historial en lugar de la rechazada.
                self.mensajes.append({"role": "assistant", "content": "No puedo ayudar con eso."})
                # Mensaje para el usuario.
                return "No puedo ayudar con eso. Prueba a decirlo de otra forma."
            # Guardamos la respuesta completa tal cual (Claude necesita sus partes internas en la siguiente petición).
            self.mensajes.append({"role": "assistant", "content": respuesta.content})
            # Herramientas que pide usar.
            llamadas = [bloque for bloque in respuesta.content if bloque.type == "tool_use"]
            # Si no pide ninguna, esta es la respuesta final.
            if not llamadas:
                # Texto de la respuesta.
                final = "\n".join(bloque.text for bloque in respuesta.content if bloque.type == "text").strip()
                # Si se cortó por largo, lo indicamos.
                if respuesta.stop_reason == "max_tokens":
                    # Aviso.
                    final += "\n(La respuesta se cortó por ser muy larga.)"
                # Devolvemos el texto.
                return final or "(Sin respuesta.)"
            # Resultados de las herramientas (todos juntos en un mismo mensaje).
            resultados = []
            # Ejecutamos cada una.
            for llamada in llamadas:
                # Ejecutamos.
                salida, es_error, resumen = ejecutar(llamada.name, llamada.input)
                # Avisamos al usuario de lo que se hizo.
                if avisar:
                    # Línea para la ventana o la terminal.
                    avisar(resumen)
                # Resultado para Claude.
                resultados.append({"type": "tool_result", "tool_use_id": llamada.id, "content": salida,
                                   "is_error": es_error})
            # Mandamos los resultados en la siguiente vuelta.
            self.mensajes.append({"role": "user", "content": resultados})
        # Demasiadas vueltas seguidas.
        return "He hecho muchos pasos seguidos. Dime si quieres que siga."


class ConversacionGemini:
    """Conversación con Gemini (Google) usando sus herramientas."""

    def __init__(self, clave, modelo):
        # Importamos aquí la librería: así el resto de la app funciona aunque no esté instalada.
        try:
            # Librería oficial de Google para Gemini.
            from google import genai
            # Errores de esa librería.
            from google.genai import errors
            # Tipos de datos de esa librería.
            from google.genai import types
        # Si falta, explicamos cómo instalarla.
        except ImportError as error:
            # Mensaje para el usuario.
            raise ErrorPlanificador("Falta la librería de Gemini. Instálala con:\n"
                                    "  python -m pip install -r requirements.txt") from error
        # Guardamos los módulos.
        self._errores, self._tipos = errors, types
        # Cliente.
        self.cliente = genai.Client(api_key=clave)
        # Modelo elegido.
        self.modelo = modelo
        # Nombre para mostrar.
        self.nombre = f"Gemini ({modelo})"
        # Historial de la conversación.
        self.contenidos = []
        # Herramientas en el formato de Gemini.
        declaraciones = [types.FunctionDeclaration(name=h["nombre"], description=h["descripcion"],
                                                   parameters_json_schema=h["parametros"]) for h in HERRAMIENTAS]
        # Opciones: instrucciones, herramientas, y que no las ejecute solo (las ejecutamos nosotros).
        opciones = {"system_instruction": SISTEMA, "tools": [types.Tool(function_declarations=declaraciones)],
                    "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True)}
        # Los modelos Gemini 3 piensan menos (y responden antes) con nivel bajo.
        if modelo.startswith("gemini-3"):
            # Nivel de razonamiento bajo.
            opciones["thinking_config"] = types.ThinkingConfig(thinking_level="low")
        # Configuración de cada petición.
        self.config = types.GenerateContentConfig(**opciones)

    def _traducir_error(self, error):
        """Convierte un error de Gemini en un mensaje claro."""
        # Código del error.
        codigo = getattr(error, "code", None)
        # Texto del error (en minúsculas, para buscar palabras).
        texto = str(error).lower()
        # Clave incorrecta.
        if codigo in (400, 401, 403) and ("api key" in texto or "api_key" in texto or codigo == 401):
            # Mensaje.
            return "La clave de Gemini no es válida. Revísala en la sección Asistente (botón «Cambiar IA o clave»)."
        # Modelo desconocido.
        if codigo == 404:
            # Mensaje.
            return f"Gemini no reconoce el modelo «{self.modelo}». Revisa «modelo_gemini» en config.json."
        # Límite gratuito agotado.
        if codigo == 429:
            # Mensaje.
            return ("Se acabó el límite gratuito de Gemini por ahora (peticiones por minuto o por día). "
                    "Espera un rato y vuelve a intentarlo.")
        # Problema en los servidores de Google.
        if codigo and codigo >= 500:
            # Mensaje.
            return "Gemini está saturado o con problemas ahora mismo. Vuelve a intentarlo en un rato."
        # Otro error.
        return f"Gemini rechazó la petición: {getattr(error, 'message', None) or error}"

    def enviar(self, texto, avisar=None):
        """Envía un mensaje del usuario y devuelve la respuesta de Gemini (usando herramientas si hace falta)."""
        # Tipos de Gemini.
        t = self._tipos
        # Mensaje del usuario, con la fecha y hora.
        self.contenidos.append(t.Content(role="user", parts=[t.Part(text=f"[{ahora_texto()}]\n{texto}")]))
        # Ida y vuelta: Gemini responde o pide usar herramientas.
        for _vuelta in range(MAX_VUELTAS):
            # Pedimos la respuesta.
            try:
                # Respuesta de Gemini.
                respuesta = self.cliente.models.generate_content(model=self.modelo, contents=self.contenidos,
                                                                 config=self.config)
            # Errores de la API de Gemini: los explicamos.
            except self._errores.APIError as error:
                # Error para el usuario.
                raise ErrorPlanificador(self._traducir_error(error)) from error
            # Sin conexión.
            except Exception as error:  # noqa: BLE001 - la librería usa sus propios errores de red.
                # Si no es de red, que se vea tal cual.
                if not _es_error_de_red(error):
                    # Lo volvemos a lanzar.
                    raise
                # Error para el usuario.
                raise ErrorPlanificador("No se pudo conectar con Gemini. Revisa tu conexión a internet.") from error
            # Primera respuesta propuesta (puede no haber, si Gemini la bloqueó).
            candidato = respuesta.candidates[0] if respuesta.candidates else None
            # Sin respuesta.
            if candidato is None or candidato.content is None or not candidato.content.parts:
                # Respuesta corta en el historial para que siga en orden.
                self.contenidos.append(t.Content(role="model", parts=[t.Part(text="No puedo ayudar con eso.")]))
                # Mensaje para el usuario.
                return "Gemini no dio respuesta (quizá la bloqueó por precaución). Prueba a decirlo de otra forma."
            # Guardamos la respuesta completa tal cual (incluye partes internas que Gemini necesita después).
            self.contenidos.append(candidato.content)
            # Herramientas que pide usar.
            llamadas = respuesta.function_calls or []
            # Si no pide ninguna, esta es la respuesta final.
            if not llamadas:
                # Texto de la respuesta (sin las partes de "pensamiento").
                final = "".join(parte.text for parte in candidato.content.parts
                                if parte.text and not getattr(parte, "thought", False)).strip()
                # Devolvemos el texto.
                return final or "(Sin respuesta.)"
            # Resultados de las herramientas.
            partes = []
            # Ejecutamos cada una.
            for llamada in llamadas:
                # Ejecutamos.
                salida, es_error, resumen = ejecutar(llamada.name, llamada.args)
                # Avisamos al usuario de lo que se hizo.
                if avisar:
                    # Línea para la ventana o la terminal.
                    avisar(resumen)
                # Resultado para Gemini.
                partes.append(t.Part(function_response=t.FunctionResponse(
                    id=llamada.id, name=llamada.name, response={"error" if es_error else "resultado": salida})))
            # Mandamos los resultados en la siguiente vuelta.
            self.contenidos.append(t.Content(role="user", parts=partes))
        # Demasiadas vueltas seguidas.
        return "He hecho muchos pasos seguidos. Dime si quieres que siga."


def clave_de(proveedor, claves=None):
    """Clave guardada para un proveedor (o la de su variable de entorno), o "" si no hay."""
    # Claves guardadas.
    claves = claves if claves is not None else almacen.cargar_claves()
    # La guardada, o la de alguna variable de entorno.
    return claves.get(proveedor) or next((os.environ[v] for v in VARIABLES_CLAVE[proveedor] if os.environ.get(v)), "")


def crear_conversacion(config=None, claves=None):
    """Empieza una conversación con la IA elegida en los ajustes."""
    # Ajustes.
    config = config or almacen.cargar_config()
    # Proveedor elegido.
    proveedor = config["asistente"]
    # Su clave.
    clave = clave_de(proveedor, claves)
    # Sin clave no se puede.
    if not clave:
        # Explicamos cómo ponerla.
        raise ErrorPlanificador(
            f"Falta la clave de {NOMBRES[proveedor]}. Ponla en la sección Asistente de la ventana, o con:\n"
            f"  python planificador.py clave {proveedor}\n(Cómo conseguirla: GUIA_DE_INICIO.md, paso 7.)")
    # Claude.
    if proveedor == "claude":
        # Conversación con Claude.
        return ConversacionClaude(clave, config["modelo_claude"])
    # Gemini.
    return ConversacionGemini(clave, config["modelo_gemini"])

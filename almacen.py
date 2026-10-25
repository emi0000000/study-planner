"""Lectura y escritura de los datos del planificador.

Todo se guarda en archivos JSON (texto) junto al programa:
  - config.json           -> ajustes que puedes editar a mano.
  - datos/temas.json      -> los temas que vas agregando.
  - datos/plan.json       -> el último plan de sesiones generado.
  - datos/registro.json   -> qué sesiones hiciste y cuáles no.
  - datos/metas.json      -> tus metas (por ejemplo, un examen con fecha).
  - datos/memoria.json    -> notas que el asistente guarda para recordar cómo estudias.
  - datos/claves.json     -> tus claves del asistente (Claude o Gemini). Privado.
"""

# json convierte datos de Python (listas, diccionarios) en texto y al revés.
import json
# copy permite duplicar diccionarios sin tocar el original.
import copy
# unicodedata sirve para quitar tildes ("miércoles" -> "miercoles").
import unicodedata
# Path maneja rutas de archivos igual en Windows, Mac y Linux.
from pathlib import Path

# Carpeta donde está este archivo: los datos se guardan al lado del programa.
CARPETA_APP = Path(__file__).resolve().parent
# Subcarpeta donde la app guarda lo que genera.
CARPETA_DATOS = CARPETA_APP / "datos"
# Archivo con la lista de temas.
ARCHIVO_TEMAS = CARPETA_DATOS / "temas.json"
# Archivo con el último plan generado.
ARCHIVO_PLAN = CARPETA_DATOS / "plan.json"
# Archivo de ajustes que el usuario puede editar.
ARCHIVO_CONFIG = CARPETA_APP / "config.json"
# Archivo con las sesiones marcadas como hechas o no hechas.
ARCHIVO_REGISTRO = CARPETA_DATOS / "registro.json"
# Archivo con las metas.
ARCHIVO_METAS = CARPETA_DATOS / "metas.json"
# Archivo con las notas del asistente.
ARCHIVO_MEMORIA = CARPETA_DATOS / "memoria.json"
# Archivo con las claves del asistente (está en datos/, que nunca se sube a internet).
ARCHIVO_CLAVES = CARPETA_DATOS / "claves.json"

# Días de la semana en el mismo orden que usa Python (lunes = 0 ... domingo = 6).
DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

# Prioridad más baja que acepta un tema.
PRIORIDAD_MINIMA = 1
# Prioridad más alta que acepta un tema.
PRIORIDAD_MAXIMA = 5
# Una semana tiene 7 * 24 * 60 = 10080 minutos: ningún tema puede pedir más.
MINUTOS_EN_UNA_SEMANA = 7 * 24 * 60
# Cómo se crea un plan nuevo; aparece en los mensajes de error. La ventana lo cambia por el nombre de su botón.
COMO_GENERAR = "python planificador.py generar"
# Inteligencias artificiales que puede usar el asistente.
PROVEEDORES = ("claude", "gemini")

# Ajustes que se usan si config.json no existe o le falta alguna clave.
CONFIG_POR_DEFECTO = {
    # Minutos que dura cada sesión corta.
    "duracion_sesion": 25,
    # Si al partir un tema sobran menos minutos que esto, se suman a la última sesión.
    "duracion_minima": 10,
    # Minutos de descanso entre una sesión y la siguiente.
    "descanso_corto": 5,
    # Minutos de descanso largo, cada cierto número de sesiones.
    "descanso_largo": 15,
    # Cada cuántas sesiones toca el descanso largo (0 = nunca).
    "sesiones_antes_de_descanso_largo": 4,
    # Máximo de minutos de estudio por día, sin contar descansos (0 = sin límite).
    "maximo_minutos_por_dia": 120,
    # Días en los que estudias y a qué hora empiezas cada uno.
    "horario": {
        "lunes": "18:00",
        "martes": "18:00",
        "miercoles": "18:00",
        "jueves": "18:00",
        "viernes": "18:00",
        "sabado": "10:00",
    },
    # Cuántos minutos antes de cada sesión avisa el teléfono.
    "aviso_minutos_antes": 5,
    # Calendario de Google donde se crean las sesiones ("primary" = el principal).
    "id_calendario": "primary",
    # Si no hiciste una sesión, el plan siguiente añade ese tiempo para recuperarlo.
    "recuperar_no_hechas": True,
    # Inteligencia artificial del asistente: "claude" o "gemini".
    "asistente": "claude",
    # Modelo de Claude que usa el asistente.
    "modelo_claude": "claude-opus-5-5",
    # Modelo de Gemini que usa el asistente.
    "modelo_gemini": "gemini-3.8-flash",
}


class ErrorPlanificador(Exception):
    """Error pensado para mostrarse tal cual al usuario (sin mensajes técnicos)."""


def quitar_tildes(texto):
    """Devuelve el texto en minúsculas y sin tildes, para comparar nombres."""
    # NFD separa cada letra de su tilde ("é" pasa a ser "e" + "´").
    descompuesto = unicodedata.normalize("NFD", str(texto))
    # Nos quedamos solo con los caracteres que no son marcas de tilde ("Mn").
    sin_marcas = "".join(letra for letra in descompuesto if unicodedata.category(letra) != "Mn")
    # Pasamos a minúsculas y quitamos espacios sobrantes en los extremos.
    return sin_marcas.lower().strip()


def leer_json(ruta, valor_si_no_existe):
    """Lee un archivo JSON; si no existe, devuelve una copia del valor indicado."""
    # Si el archivo todavía no existe, devolvemos el valor por defecto.
    if not ruta.exists():
        # deepcopy evita que alguien modifique sin querer el valor original.
        return copy.deepcopy(valor_si_no_existe)
    # Abrimos el archivo como texto UTF-8 para que las tildes se lean bien.
    with open(ruta, encoding="utf-8") as archivo:
        # Intentamos convertir el texto en datos de Python.
        try:
            # json.load hace la conversión de texto JSON a listas/diccionarios.
            return json.load(archivo)
        # Si el archivo está mal escrito (por ejemplo, falta una coma)...
        except json.JSONDecodeError as error:
            # ...avisamos en qué línea y columna está el problema.
            raise ErrorPlanificador(
                f"El archivo {ruta.name} tiene un error de formato "
                f"(línea {error.lineno}, columna {error.colno})."
            ) from error


def escribir_json(ruta, datos):
    """Guarda datos de Python en un archivo JSON fácil de leer."""
    # Creamos la carpeta del archivo si todavía no existe.
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # Abrimos (o creamos) el archivo para escribir en UTF-8.
    with open(ruta, "w", encoding="utf-8") as archivo:
        # indent=2 lo deja ordenado; ensure_ascii=False conserva las tildes.
        json.dump(datos, archivo, indent=2, ensure_ascii=False)
        # Terminamos con un salto de línea, como cualquier archivo de texto.
        archivo.write("\n")


def leer_hora(texto):
    """Convierte "18:30" en (18, 30). Si la hora no es válida, lanza un error claro."""
    # Separamos horas y minutos por los dos puntos.
    partes = str(texto).split(":")
    # Tiene que haber justo dos partes y las dos tienen que ser números.
    if len(partes) != 2 or not all(parte.isdigit() for parte in partes):
        # Si no es así, explicamos el formato correcto.
        raise ErrorPlanificador(f'La hora "{texto}" no es válida: usa el formato HH:MM, por ejemplo "18:30".')
    # Convertimos cada parte de texto a número entero.
    horas, minutos = int(partes[0]), int(partes[1])
    # Comprobamos que estén dentro del rango de un reloj (0-23 y 0-59).
    if not (0 <= horas <= 23 and 0 <= minutos <= 59):
        # Si no lo están, avisamos.
        raise ErrorPlanificador(f'La hora "{texto}" no existe: las horas van de 00 a 23 y los minutos de 00 a 59.')
    # Devolvemos las dos cifras ya como números.
    return horas, minutos


def _es_entero(valor):
    """True si el valor es un número entero (en Python true/false cuentan como enteros; los descartamos)."""
    # Entero, pero no true/false.
    return isinstance(valor, int) and not isinstance(valor, bool)


def _validar_entero(config, clave, minimo, maximo=None):
    """Comprueba que config[clave] sea un número entero dentro del rango permitido."""
    # Tomamos el valor que hay en la configuración.
    valor = config[clave]
    # ¿Es un número entero?
    es_entero = _es_entero(valor)
    # Si es entero, miramos si se sale por abajo o por arriba.
    fuera_de_rango = es_entero and (valor < minimo or (maximo is not None and valor > maximo))
    # Si no es entero o se sale del rango, avisamos con el rango correcto.
    if not es_entero or fuera_de_rango:
        # Armamos la frase del rango según haya o no un máximo.
        rango = f"entre {minimo} y {maximo}" if maximo is not None else f"mayor o igual que {minimo}"
        # Lanzamos el error con el valor que encontramos.
        raise ErrorPlanificador(f'En config.json, "{clave}" debe ser un número entero {rango} (ahora vale {valor!r}).')


def cargar_config(ruta=None):
    """Lee config.json (lo crea con valores por defecto si no existe) y lo valida."""
    # Si no nos pasan una ruta, usamos la de siempre.
    ruta = ruta or ARCHIVO_CONFIG
    # La primera vez creamos el archivo para que el usuario pueda editarlo.
    if not ruta.exists():
        # Guardamos los ajustes por defecto.
        escribir_json(ruta, CONFIG_POR_DEFECTO)
    # Leemos lo que haya en el archivo y lo revisamos.
    return validar_config(leer_json(ruta, {}))


def guardar_config(datos, ruta=None):
    """Revisa los ajustes y, si están bien, los guarda en config.json. Devuelve los ajustes ya revisados."""
    # Si algo está mal, validar_config lanza un error y no se guarda nada.
    config = validar_config(datos)
    # Guardamos la versión revisada (con los nombres de los días ya normalizados).
    escribir_json(ruta or ARCHIVO_CONFIG, config)
    # La devolvemos para usarla sin volver a leer el archivo.
    return config


def validar_config(leida):
    """Comprueba que los ajustes tengan sentido y completa los que falten con los valores por defecto."""
    # Tiene que ser un objeto { ... }, no una lista u otra cosa.
    if not isinstance(leida, dict):
        # Si no, avisamos.
        raise ErrorPlanificador("config.json debe contener un objeto entre llaves { }.")
    # Partimos de los valores por defecto...
    config = copy.deepcopy(CONFIG_POR_DEFECTO)
    # ...y encima ponemos lo que el usuario escribió (así no falta ninguna clave).
    config.update(leida)
    # Cada sesión dura entre 1 minuto y 4 horas.
    _validar_entero(config, "duracion_sesion", 1, 240)
    # La duración mínima no puede ser mayor que una sesión normal.
    _validar_entero(config, "duracion_minima", 1, config["duracion_sesion"])
    # Descanso corto razonable: de 0 a 120 minutos.
    _validar_entero(config, "descanso_corto", 0, 120)
    # Descanso largo razonable: de 0 a 240 minutos.
    _validar_entero(config, "descanso_largo", 0, 240)
    # Cada cuántas sesiones hay descanso largo (0 = nunca).
    _validar_entero(config, "sesiones_antes_de_descanso_largo", 0)
    # Máximo diario de estudio (0 = sin límite).
    _validar_entero(config, "maximo_minutos_por_dia", 0)
    # Google Calendar acepta avisos de 0 a 40320 minutos (4 semanas) antes.
    _validar_entero(config, "aviso_minutos_antes", 0, 40320)
    # El horario tiene que ser un objeto con al menos un día.
    if not isinstance(config["horario"], dict) or not config["horario"]:
        # Si está vacío o mal escrito, explicamos cómo debe ser.
        raise ErrorPlanificador('En config.json, "horario" debe tener al menos un día, por ejemplo {"lunes": "18:00"}.')
    # Aquí guardaremos el horario con los nombres de los días ya normalizados.
    horario = {}
    # Revisamos cada día y su hora.
    for dia, hora in config["horario"].items():
        # Aceptamos "Miércoles", "miercoles", "MIÉRCOLES"... todos valen igual.
        nombre = quitar_tildes(dia)
        # Si el día no existe, avisamos con la lista de días válidos.
        if nombre not in DIAS_SEMANA:
            # Mostramos qué días se pueden usar.
            raise ErrorPlanificador(f'En config.json, "{dia}" no es un día válido. Usa: {", ".join(DIAS_SEMANA)}.')
        # Comprobamos que la hora tenga el formato HH:MM.
        leer_hora(hora)
        # Guardamos el día con su hora.
        horario[nombre] = str(hora)
    # Reemplazamos el horario original por el normalizado.
    config["horario"] = horario
    # El calendario y los modelos tienen que ser textos no vacíos.
    for clave, ejemplo in (("id_calendario", "primary"), ("modelo_claude", "claude-opus-5-5"),
                           ("modelo_gemini", "gemini-3.8-flash")):
        # Comprobamos que sea un texto con algo escrito.
        if not isinstance(config[clave], str) or not config[clave].strip():
            # Si no, avisamos con un ejemplo.
            raise ErrorPlanificador(f'En config.json, "{clave}" debe ser un texto, por ejemplo "{ejemplo}".')
    # Recuperar lo no hecho: sí (true) o no (false).
    if not isinstance(config["recuperar_no_hechas"], bool):
        # Si no, avisamos.
        raise ErrorPlanificador('En config.json, "recuperar_no_hechas" debe ser true (sí) o false (no).')
    # El asistente tiene que ser uno de los que conocemos.
    if config["asistente"] not in PROVEEDORES:
        # Si no, avisamos con las opciones.
        raise ErrorPlanificador(f'En config.json, "asistente" debe ser "claude" o "gemini" (ahora vale {config["asistente"]!r}).')
    # Devolvemos la configuración lista para usar.
    return config


def cargar_temas(ruta=None):
    """Devuelve la lista de temas guardados (vacía si todavía no hay ninguno)."""
    # Leemos el archivo de temas; si no existe, empezamos con una lista vacía.
    temas = leer_json(ruta or ARCHIVO_TEMAS, [])
    # Debe ser una lista; si alguien lo editó mal, avisamos.
    if not isinstance(temas, list):
        # Mensaje para el usuario.
        raise ErrorPlanificador("datos/temas.json debe contener una lista [ ].")
    # Revisamos cada tema por si el archivo se editó a mano.
    for posicion, tema in enumerate(temas, start=1):
        # Si le falta algo o tiene un valor raro, avisamos cuál es.
        if not _tema_valido(tema):
            # Mensaje con lo que debe tener cada tema.
            raise ErrorPlanificador(
                f"El tema número {posicion} de datos/temas.json está mal escrito. Cada tema necesita "
                '"nombre", "prioridad" (1 a 5) y "minutos_semana".\n'
                'Corrígelo con el Bloc de notas, o bórralo y vuelve a agregarlo con "agregar".'
            )
    # Devolvemos los temas.
    return temas


def _tema_valido(tema):
    """True si el tema tiene nombre, prioridad de 1 a 5 y minutos por semana válidos."""
    # Tiene que ser un objeto { ... }.
    if not isinstance(tema, dict):
        # No lo es.
        return False
    # Nombre del tema.
    nombre = tema.get("nombre")
    # Prioridad del tema.
    prioridad = tema.get("prioridad")
    # Minutos por semana.
    minutos = tema.get("minutos_semana")
    # Las mismas reglas que usa agregar_tema().
    return (
        # Un texto que no esté vacío.
        isinstance(nombre, str) and bool(nombre.strip())
        # Un entero de 1 a 5.
        and _es_entero(prioridad) and PRIORIDAD_MINIMA <= prioridad <= PRIORIDAD_MAXIMA
        # Un entero que quepa en una semana.
        and _es_entero(minutos) and 0 < minutos <= MINUTOS_EN_UNA_SEMANA
    )


def guardar_temas(temas, ruta=None):
    """Guarda la lista de temas en disco."""
    # Escribimos la lista en datos/temas.json (o en la ruta indicada).
    escribir_json(ruta or ARCHIVO_TEMAS, temas)


def buscar_tema(temas, nombre):
    """Busca un tema por nombre sin importar mayúsculas ni tildes. Devuelve None si no está."""
    # Normalizamos el nombre buscado ("Matemáticas" -> "matematicas").
    clave = quitar_tildes(nombre)
    # Recorremos los temas guardados.
    for tema in temas:
        # Si coincide al normalizarlo, es el que buscamos.
        if quitar_tildes(tema["nombre"]) == clave:
            # Lo devolvemos.
            return tema
    # Si no apareció ninguno, devolvemos None.
    return None


def agregar_tema(temas, nombre, prioridad, minutos_semana):
    """Agrega un tema nuevo o actualiza uno existente. Devuelve True si era nuevo."""
    # Quitamos espacios sobrantes del nombre.
    nombre = nombre.strip()
    # El nombre no puede quedar vacío.
    if not nombre:
        # Avisamos.
        raise ErrorPlanificador("El nombre del tema no puede estar vacío.")
    # La prioridad debe estar entre 1 y 5.
    if not PRIORIDAD_MINIMA <= prioridad <= PRIORIDAD_MAXIMA:
        # Avisamos con el rango correcto.
        raise ErrorPlanificador(f"La prioridad debe ser un número del {PRIORIDAD_MINIMA} (baja) al {PRIORIDAD_MAXIMA} (alta).")
    # Los minutos por semana deben ser positivos y caber en una semana.
    if not 0 < minutos_semana <= MINUTOS_EN_UNA_SEMANA:
        # Avisamos.
        raise ErrorPlanificador(f"Los minutos por semana deben estar entre 1 y {MINUTOS_EN_UNA_SEMANA}.")
    # Miramos si ya existe un tema con ese nombre.
    existente = buscar_tema(temas, nombre)
    # Si existe, lo actualizamos en lugar de duplicarlo.
    if existente is not None:
        # Cambiamos sus datos por los nuevos.
        existente.update(nombre=nombre, prioridad=prioridad, minutos_semana=minutos_semana)
        # Indicamos que no era nuevo.
        return False
    # Si no existía, lo añadimos al final de la lista.
    temas.append({"nombre": nombre, "prioridad": prioridad, "minutos_semana": minutos_semana})
    # Indicamos que sí era nuevo.
    return True


def quitar_tema(temas, nombre):
    """Quita un tema de la lista y lo devuelve. Si no existe, lanza un error."""
    # Buscamos el tema por nombre.
    tema = buscar_tema(temas, nombre)
    # Si no está, avisamos.
    if tema is None:
        # Mensaje para el usuario.
        raise ErrorPlanificador(f'No hay ningún tema llamado "{nombre}". Mira la lista con:  python planificador.py temas')
    # Lo sacamos de la lista.
    temas.remove(tema)
    # Devolvemos el tema quitado (sirve para mostrar su nombre exacto).
    return tema


def cargar_plan(ruta=None):
    """Lee el último plan guardado. Si no hay ninguno, lanza un error con instrucciones."""
    # Si no nos pasan una ruta, usamos la de siempre.
    ruta = ruta or ARCHIVO_PLAN
    # Si todavía no se generó ningún plan, explicamos cómo hacerlo.
    if not ruta.exists():
        # Mensaje para el usuario.
        raise ErrorPlanificador(f"Todavía no hay un plan. Créalo con:  {COMO_GENERAR}")
    # Leemos y devolvemos el plan.
    return leer_json(ruta, {})


def guardar_plan(datos_plan, ruta=None):
    """Guarda el plan (ya convertido a diccionario) en disco."""
    # Escribimos el plan en datos/plan.json (o en la ruta indicada).
    escribir_json(ruta or ARCHIVO_PLAN, datos_plan)


def _cargar_lista(ruta, nombre):
    """Lee un archivo que debe contener una lista (vacía si todavía no existe)."""
    # Leemos el archivo; si no existe, empezamos con una lista vacía.
    datos = leer_json(ruta, [])
    # Debe ser una lista; si alguien lo editó mal, avisamos.
    if not isinstance(datos, list):
        # Mensaje para el usuario.
        raise ErrorPlanificador(f"datos/{nombre} debe contener una lista [ ]. Corrígelo o bórralo.")
    # Devolvemos la lista.
    return datos


def cargar_registro(ruta=None):
    """Devuelve el registro de sesiones hechas y no hechas."""
    # Leemos el archivo; si no existe, empezamos vacío.
    registro = leer_json(ruta or ARCHIVO_REGISTRO, {"sesiones": {}, "perdonado": {}})
    # Debe ser un objeto con las dos partes.
    if not isinstance(registro, dict) or not isinstance(registro.get("sesiones", {}), dict):
        # Mensaje para el usuario.
        raise ErrorPlanificador("datos/registro.json está mal escrito. Corrígelo o bórralo (perderás lo marcado).")
    # Completamos lo que falte.
    registro.setdefault("sesiones", {})
    # Temas cuyos pendientes se olvidaron, con la fecha en que se olvidaron.
    registro.setdefault("perdonado", {})
    # Devolvemos el registro.
    return registro


def guardar_registro(registro, ruta=None):
    """Guarda el registro de sesiones."""
    # Escribimos el archivo.
    escribir_json(ruta or ARCHIVO_REGISTRO, registro)


def cargar_metas(ruta=None):
    """Devuelve la lista de metas."""
    # Lista de metas.
    return _cargar_lista(ruta or ARCHIVO_METAS, "metas.json")


def guardar_metas(metas, ruta=None):
    """Guarda la lista de metas."""
    # Escribimos el archivo.
    escribir_json(ruta or ARCHIVO_METAS, metas)


def cargar_memoria(ruta=None):
    """Devuelve las notas que guardó el asistente."""
    # Lista de notas.
    return _cargar_lista(ruta or ARCHIVO_MEMORIA, "memoria.json")


def guardar_memoria(notas, ruta=None):
    """Guarda las notas del asistente."""
    # Escribimos el archivo.
    escribir_json(ruta or ARCHIVO_MEMORIA, notas)


def cargar_claves(ruta=None):
    """Devuelve las claves del asistente, por ejemplo {"gemini": "AIza..."}."""
    # Leemos el archivo; si no existe, no hay claves.
    claves = leer_json(ruta or ARCHIVO_CLAVES, {})
    # Debe ser un objeto.
    if not isinstance(claves, dict):
        # Mensaje para el usuario.
        raise ErrorPlanificador("datos/claves.json está mal escrito. Bórralo y vuelve a poner tu clave.")
    # Devolvemos las claves.
    return claves


def guardar_clave(proveedor, clave, ruta=None):
    """Guarda (o borra, si `clave` está vacía) la clave de un proveedor del asistente."""
    # Solo conocemos dos proveedores.
    if proveedor not in PROVEEDORES:
        # Mensaje para el usuario.
        raise ErrorPlanificador(f'El asistente puede ser "claude" o "gemini", no "{proveedor}".')
    # Claves actuales.
    claves = cargar_claves(ruta)
    # Quitamos espacios que se cuelan al copiar y pegar.
    clave = (clave or "").strip()
    # Si hay clave, la guardamos.
    if clave:
        # Guardamos.
        claves[proveedor] = clave
    # Si no, la borramos.
    else:
        # Borramos (si estaba).
        claves.pop(proveedor, None)
    # Escribimos el archivo.
    escribir_json(ruta or ARCHIVO_CLAVES, claves)

"""Conexión con Google Calendar: crea y borra los eventos de las sesiones de estudio.

Cada sesión se crea como un evento con un aviso tipo "notificación". Si tienes la app
de Google Calendar en el teléfono con la misma cuenta, el aviso te llega ahí solo.

Todos los eventos que crea esta app llevan una marca oculta (una "propiedad privada").
Gracias a esa marca, la app puede encontrar y borrar SOLO sus eventos, sin tocar los tuyos.
"""

# Herramientas de fechas para armar los rangos de búsqueda.
from datetime import datetime, time, timedelta

# Rutas y tipo de error del módulo de datos.
from almacen import CARPETA_APP, ErrorPlanificador

# Permiso que pedimos a Google: ver y editar eventos (no puede leer tu correo ni nada más).
ALCANCES = ["https://www.googleapis.com/auth/calendar.events"]
# Archivo que descargas de Google Cloud con los datos de tu "cliente OAuth".
ARCHIVO_CREDENCIALES = CARPETA_APP / "credentials.json"
# Archivo que la app crea tras tu primer inicio de sesión, para no pedírtelo cada vez.
ARCHIVO_TOKEN = CARPETA_APP / "token.json"
# Nombre de la marca oculta que llevan los eventos de esta app.
MARCA = "planificador_estudio"
# Valor de la marca.
VALOR_MARCA = "si"
# Color de cada evento según la prioridad del tema (códigos de color de Google Calendar).
COLORES_POR_PRIORIDAD = {
    # Prioridad 5: rojo tomate.
    5: "11",
    # Prioridad 4: mandarina.
    4: "6",
    # Prioridad 3: amarillo plátano.
    3: "5",
    # Prioridad 2: verde salvia.
    2: "2",
    # Prioridad 1: gris grafito.
    1: "8",
}
# Consejos para los errores más habituales de Google, según su código.
PISTAS_DE_ERROR = {
    # 401: el permiso guardado ya no vale.
    401: "Borra el archivo token.json y vuelve a intentarlo para iniciar sesión de nuevo.",
    # 403: casi siempre, la API no está habilitada en el proyecto.
    403: "Revisa que la API de Google Calendar esté habilitada en tu proyecto de Google Cloud (ver README).",
    # 404: el calendario indicado no existe.
    404: 'Revisa "id_calendario" en config.json (usa "primary" para tu calendario principal).',
}


def credenciales_con_otro_nombre(carpeta):
    """Busca archivos que parecen credentials.json pero con otro nombre.

    Pasa mucho: Google lo descarga como "client_secret_....json", o Windows (que oculta las
    extensiones) lo deja como "credentials.json.json" al renombrarlo.
    """
    # El nombre con que lo descarga Google y las variantes de "credentials" (".json.json", " (1).json"...).
    parecidos = sorted(carpeta.glob("client_secret*.json")) + sorted(carpeta.glob("credentials*.json*"))
    # Quitamos el nombre correcto (si estuviera, no habría nada que avisar).
    return [ruta.name for ruta in parecidos if ruta.name != "credentials.json"]


def conectar(ruta_credenciales=None, ruta_token=None):
    """Inicia sesión en Google (abre el navegador la primera vez) y devuelve el servicio de Calendar."""
    # Importamos aquí las librerías de Google: así el resto de la app funciona aunque no estén instaladas.
    try:
        # Error que aparece cuando el permiso guardado caducó o se revocó.
        from google.auth.exceptions import RefreshError, TransportError
        # Objeto que hace peticiones web para renovar el permiso.
        from google.auth.transport.requests import Request
        # Clase que representa tu permiso (token) guardado.
        from google.oauth2.credentials import Credentials
        # Flujo de inicio de sesión para apps de escritorio.
        from google_auth_oauthlib.flow import InstalledAppFlow
        # Función que construye el "servicio" para hablar con la API.
        from googleapiclient.discovery import build
    # Si falta alguna librería...
    except ImportError as error:
        # ...explicamos cómo instalarlas.
        raise ErrorPlanificador(
            "Faltan las librerías de Google. Instálalas con:\n  python -m pip install -r requirements.txt"
        ) from error
    # Si no nos pasan rutas, usamos las de siempre (junto al programa).
    ruta_credenciales = ruta_credenciales or ARCHIVO_CREDENCIALES
    # Lo mismo para el token.
    ruta_token = ruta_token or ARCHIVO_TOKEN
    # De momento no tenemos permiso.
    credenciales = None
    # Si ya iniciaste sesión antes, el permiso está guardado en token.json.
    if ruta_token.exists():
        # Intentamos leerlo.
        try:
            # Cargamos el permiso guardado.
            credenciales = Credentials.from_authorized_user_file(str(ruta_token), ALCANCES)
        # Si el archivo está dañado, lo ignoramos y volvemos a pedir permiso.
        except ValueError:
            # Sin permiso válido.
            credenciales = None
    # Si el permiso caducó pero se puede renovar, lo renovamos sin molestarte.
    if credenciales and credenciales.expired and credenciales.refresh_token:
        # Intentamos renovarlo.
        try:
            # Pedimos a Google un permiso nuevo.
            credenciales.refresh(Request())
        # Si Google dice que ya no vale (pasa cada 7 días en modo "prueba")...
        except RefreshError:
            # ...lo descartamos y abajo se abrirá el navegador para iniciar sesión otra vez.
            credenciales = None
        # Si no hay internet...
        except TransportError as error:
            # ...avisamos.
            raise ErrorPlanificador("No se pudo conectar con Google. Revisa tu conexión a internet.") from error
    # Si seguimos sin un permiso válido, hay que iniciar sesión.
    if not credenciales or not credenciales.valid:
        # Para eso necesitamos credentials.json (ver README, sección "Conectar con Google Calendar").
        if not ruta_credenciales.exists():
            # Mensaje base: qué falta y dónde ponerlo.
            mensaje = f"No encuentro {ruta_credenciales.name} en la carpeta de la app ({ruta_credenciales.parent}).\n"
            # Miramos si está con otro nombre.
            parecidos = credenciales_con_otro_nombre(ruta_credenciales.parent)
            # Si lo encontramos, decimos exactamente qué renombrar.
            if parecidos:
                # Qué archivo renombrar.
                mensaje += f"Pero encontré «{parecidos[0]}»: cámbiale el nombre a {ruta_credenciales.name}."
                # Si es el caso de la extensión repetida, explicamos por qué no se ve.
                if parecidos[0].startswith("credentials"):
                    # Pista para Windows.
                    mensaje += (
                        "\nSi en el Explorador ya parece llamarse así, es que Windows oculta la extensión: "
                        "en el menú Ver del Explorador activa «Extensiones de nombre de archivo»."
                    )
            # Si no, explicamos cómo conseguirlo.
            else:
                # Dónde está explicado.
                mensaje += "Descárgalo de Google Cloud siguiendo GUIA_DE_INICIO.md (paso 4)."
            # Mostramos el mensaje.
            raise ErrorPlanificador(mensaje)
        # Preparamos el inicio de sesión con tus credenciales y el permiso que pedimos.
        flujo = InstalledAppFlow.from_client_secrets_file(str(ruta_credenciales), ALCANCES)
        # Abrimos el navegador; port=0 elige un puerto libre del ordenador automáticamente.
        credenciales = flujo.run_local_server(
            # Puerto libre cualquiera.
            port=0,
            # Mensaje que se muestra en la terminal ({url} se reemplaza por la dirección).
            authorization_prompt_message="Se abrirá el navegador para dar permiso. Si no se abre, entra a:\n{url}",
            # Mensaje que verás en el navegador al terminar.
            success_message="Listo. Ya puedes cerrar esta pestaña y volver al planificador.",
        )
    # Guardamos el permiso (nuevo o renovado) para la próxima vez.
    ruta_token.write_text(credenciales.to_json(), encoding="utf-8")
    # Construimos y devolvemos el servicio de Google Calendar (versión 3 de la API).
    return build("calendar", "v3", credentials=credenciales)


def ejecutar(peticion, ignorar=()):
    """Envía una petición a Google y traduce los errores a mensajes claros.

    `ignorar` es una lista de códigos de error que no importan (por ejemplo, 410 = "ya estaba borrado").
    """
    # httplib2 es la librería que hace las conexiones web (viene con las de Google).
    import httplib2
    # Tipo de error que devuelve la API de Google.
    from googleapiclient.errors import HttpError

    # Intentamos enviar la petición.
    try:
        # execute() la envía y devuelve la respuesta de Google.
        return peticion.execute()
    # Si Google responde con un error...
    except HttpError as error:
        # ...y es uno de los que no importan, seguimos como si nada.
        if error.resp.status in ignorar:
            # Sin respuesta.
            return None
        # Buscamos un consejo para ese código (texto vacío si no hay).
        pista = PISTAS_DE_ERROR.get(error.resp.status, "")
        # Si es otro error, lo mostramos de forma entendible, con el consejo debajo.
        raise ErrorPlanificador(
            f"Google Calendar respondió con un error ({error.resp.status}): {error.reason}\n{pista}".strip()
        ) from error
    # Si no hay conexión a internet...
    except (OSError, httplib2.HttpLib2Error) as error:
        # ...avisamos.
        raise ErrorPlanificador(f"No se pudo conectar con Google ({error}). Revisa tu conexión a internet.") from error


def con_zona_horaria(momento):
    """Convierte una fecha-hora local en texto con zona horaria, como "2026-10-26T18:00:00-03:00"."""
    # astimezone() le añade la zona horaria del ordenador (incluido el horario de verano de ese día).
    return momento.astimezone().isoformat()


def evento_desde_sesion(sesion, aviso_minutos):
    """Convierte una sesión en el formato de evento que espera Google Calendar."""
    # Armamos el evento como un diccionario.
    return {
        # Título del evento, por ejemplo "Estudiar: Matemáticas (2/5)".
        "summary": f"Estudiar: {sesion.tema} ({sesion.numero}/{sesion.total})",
        # Descripción con algo de contexto.
        "description": (
            f"Sesión corta de {sesion.minutos} minutos.\n"
            f"Prioridad del tema: {sesion.prioridad} de 5.\n"
            "Creada por el planificador de estudio."
        ),
        # Hora de inicio con zona horaria.
        "start": {"dateTime": con_zona_horaria(sesion.inicio)},
        # Hora de fin con zona horaria.
        "end": {"dateTime": con_zona_horaria(sesion.fin)},
        # Color según la prioridad (si la prioridad no está en la tabla, sin color especial).
        "colorId": COLORES_POR_PRIORIDAD.get(sesion.prioridad, "7"),
        # Avisos del evento.
        "reminders": {
            # No usamos los avisos por defecto de tu calendario...
            "useDefault": False,
            # ...sino una notificación ("popup") X minutos antes: es la que llega al teléfono.
            "overrides": [{"method": "popup", "minutes": aviso_minutos}],
        },
        # Marca oculta para reconocer los eventos de esta app.
        "extendedProperties": {"private": {MARCA: VALOR_MARCA}},
    }


def rango_del_dia(desde, hasta):
    """Devuelve (inicio, fin) en texto con zona horaria: desde las 00:00 de `desde` hasta el final de `hasta`."""
    # Medianoche del primer día.
    inicio = datetime.combine(desde, time.min)
    # Medianoche del día siguiente al último (es decir, el final del último día).
    fin = datetime.combine(hasta + timedelta(days=1), time.min)
    # Ambos con zona horaria.
    return con_zona_horaria(inicio), con_zona_horaria(fin)


def buscar_eventos_propios(servicio, id_calendario, desde, hasta):
    """Lista los eventos creados por esta app entre dos fechas (ambas incluidas)."""
    # Rango de búsqueda en el formato que pide Google.
    minimo, maximo = rango_del_dia(desde, hasta)
    # Aquí juntamos los eventos encontrados.
    eventos = []
    # Google devuelve los resultados por páginas; empezamos por la primera.
    pagina = None
    # Repetimos hasta que no haya más páginas.
    while True:
        # Pedimos una página de eventos...
        respuesta = ejecutar(
            servicio.events().list(
                # ...del calendario configurado...
                calendarId=id_calendario,
                # ...que terminen después del inicio del rango...
                timeMin=minimo,
                # ...y empiecen antes del final del rango...
                timeMax=maximo,
                # ...que tengan nuestra marca oculta...
                privateExtendedProperty=f"{MARCA}={VALOR_MARCA}",
                # ...con los eventos repetidos expandidos uno a uno...
                singleEvents=True,
                # ...hasta 250 por página...
                maxResults=250,
                # ...empezando por la página indicada (None = la primera).
                pageToken=pagina,
            )
        )
        # Añadimos los eventos de esta página.
        eventos.extend(respuesta.get("items", []))
        # Miramos si hay otra página.
        pagina = respuesta.get("nextPageToken")
        # Si no la hay, terminamos.
        if not pagina:
            # Salimos del bucle.
            break
    # Devolvemos todos los eventos encontrados.
    return eventos


def borrar_eventos(servicio, id_calendario, eventos):
    """Borra los eventos indicados y devuelve cuántos se borraron."""
    # Contador de borrados.
    borrados = 0
    # Recorremos cada evento.
    for evento in eventos:
        # Lo borramos; 404/410 significan que ya no existía, y no pasa nada.
        ejecutar(servicio.events().delete(calendarId=id_calendario, eventId=evento["id"]), ignorar=(404, 410))
        # Sumamos uno.
        borrados += 1
    # Devolvemos el total.
    return borrados


def subir_plan(servicio, id_calendario, plan, aviso_minutos, reemplazar=False):
    """Crea en Google Calendar un evento por cada sesión del plan.

    Si en esas fechas ya hay sesiones de esta app y `reemplazar` es False, se detiene
    (para no duplicarlas). Con `reemplazar=True` borra las viejas y crea las nuevas.
    Devuelve (creados, borrados).
    """
    # Buscamos sesiones de esta app que ya estén en el calendario en esas fechas.
    existentes = buscar_eventos_propios(servicio, id_calendario, plan["desde"], plan["hasta"])
    # Si hay y no nos pidieron reemplazarlas...
    if existentes and not reemplazar:
        # ...paramos y explicamos qué hacer.
        raise ErrorPlanificador(
            f"Ya hay {len(existentes)} sesiones del planificador en tu calendario entre el "
            f"{plan['desde']:%d/%m} y el {plan['hasta']:%d/%m}.\n"
            "Para borrarlas y subir el plan nuevo usa:  python planificador.py subir --reemplazar"
        )
    # Si hay que reemplazar, borramos las viejas (si no hay, borra 0).
    borrados = borrar_eventos(servicio, id_calendario, existentes)
    # Contador de eventos creados.
    creados = 0
    # Recorremos cada sesión del plan.
    for sesion in plan["sesiones"]:
        # Convertimos la sesión en evento.
        evento = evento_desde_sesion(sesion, aviso_minutos)
        # Lo creamos en el calendario.
        ejecutar(servicio.events().insert(calendarId=id_calendario, body=evento))
        # Sumamos uno.
        creados += 1
    # Devolvemos cuántos se crearon y cuántos se borraron.
    return creados, borrados


def quitar_plan(servicio, id_calendario, desde, hasta):
    """Borra del calendario las sesiones de esta app entre dos fechas. Devuelve cuántas borró."""
    # Buscamos los eventos de esta app en ese rango.
    existentes = buscar_eventos_propios(servicio, id_calendario, desde, hasta)
    # Los borramos y devolvemos el total.
    return borrar_eventos(servicio, id_calendario, existentes)

"""Lo que hiciste y lo que no, tus metas, y cómo se adapta el plan a todo eso.

  - Marcas cada sesión como "hecha" o "no hecha" (desde la ventana, los comandos o el asistente).
  - Lo que no hiciste queda pendiente: el siguiente plan añade ese tiempo para recuperarlo.
  - Una meta con fecha y tema (por ejemplo, "Examen de Química" el 13/11) hace que ese tema
    suba de prioridad las dos semanas anteriores y que sus sesiones vayan antes de esa fecha.

Todo se guarda en datos/registro.json y datos/metas.json (ver almacen.py).
"""

# copy duplica la lista de temas para ajustarla sin tocar la original.
import copy
# Herramientas de fechas.
from datetime import date, datetime, timedelta

# Módulo que guarda y lee los datos.
import almacen
# Módulo que reparte el tiempo en sesiones.
import repartidor
# Error pensado para el usuario y comparación de nombres sin tildes.
from almacen import ErrorPlanificador, quitar_tildes

# Días hacia atrás que se miran para el progreso y para lo pendiente de recuperar.
DIAS_RECUENTO = 14
# Estados posibles de una sesión marcada.
ESTADOS = ("hecha", "no_hecha")
# Texto para mostrar cada estado.
NOMBRES_ESTADO = {"hecha": "hecha", "no_hecha": "no hecha", None: "sin marcar"}


def minutos_a_texto(minutos):
    """Convierte 150 en "2 h 30 min", 45 en "45 min" y 120 en "2 h"."""
    # Horas completas y minutos sueltos.
    horas, resto = divmod(int(minutos), 60)
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


def leer_fecha(texto, que="la fecha"):
    """Convierte "2026-11-13" en una fecha; si no se puede, lanza un error claro."""
    # Intentamos interpretarla.
    try:
        # Formato AAAA-MM-DD.
        return date.fromisoformat(str(texto).strip())
    # Si no se puede, avisamos.
    except ValueError as error:
        # Mensaje para el usuario.
        raise ErrorPlanificador(f'{que.capitalize()} "{texto}" no es válida: usa AAAA-MM-DD, por ejemplo 2026-11-13.') from error


# ---------------------------------------------------------------------------------------------
# Sesiones hechas y no hechas
# ---------------------------------------------------------------------------------------------

def plan_guardado():
    """Plan guardado en datos/plan.json, o None si todavía no hay ninguno."""
    # Si no hay archivo de plan, no hay plan.
    if not almacen.ARCHIVO_PLAN.exists():
        # Sin plan.
        return None
    # Plan leído del disco (si está dañado, lanza un error claro).
    return repartidor.plan_desde_dict(almacen.cargar_plan())


def clave_sesion(sesion):
    """Identificador de una sesión en el registro, como "2026-10-26T18:00|Matemáticas"."""
    # Fecha y hora de inicio, y el tema.
    return f"{sesion.inicio:%Y-%m-%dT%H:%M}|{sesion.tema}"


def estado_de(registro, sesion):
    """Devuelve "hecha", "no_hecha" o None (sin marcar)."""
    # Buscamos la sesión en el registro.
    return registro["sesiones"].get(clave_sesion(sesion), {}).get("estado")


def marcar(registro, sesion, estado, ahora=None):
    """Marca una sesión como "hecha" o "no_hecha"; con estado None, la deja sin marcar."""
    # Solo aceptamos los estados conocidos.
    if estado is not None and estado not in ESTADOS:
        # Mensaje para el usuario.
        raise ErrorPlanificador('El estado de una sesión debe ser "hecha" o "no_hecha".')
    # Identificador de la sesión.
    clave = clave_sesion(sesion)
    # Sin estado: la quitamos del registro.
    if estado is None:
        # La borramos (si estaba).
        registro["sesiones"].pop(clave, None)
        # Terminamos.
        return
    # Guardamos sus datos (así el registro se entiende aunque el plan cambie).
    registro["sesiones"][clave] = {
        # Día de la sesión.
        "fecha": f"{sesion.inicio:%Y-%m-%d}",
        # Hora de inicio.
        "hora": f"{sesion.inicio:%H:%M}",
        # Tema.
        "tema": sesion.tema,
        # Duración.
        "minutos": sesion.minutos,
        # ¿Era una recuperación?
        "recuperacion": sesion.recuperacion,
        # Hecha o no hecha.
        "estado": estado,
        # Cuándo se marcó (sirve para "olvidar lo pendiente").
        "marcada": (ahora or datetime.now()).isoformat(timespec="seconds"),
    }


def sesiones_de(plan, fecha, tema, hora=None):
    """Sesiones del plan de ese tema ese día (y a esa hora, si se indica). Error si no hay ninguna."""
    # Sin plan no hay sesiones.
    if plan is None:
        # Mensaje para el usuario.
        raise ErrorPlanificador(f"Todavía no hay un plan. Créalo con:  {almacen.COMO_GENERAR}")
    # Tema buscado, sin tildes ni mayúsculas.
    buscado = quitar_tildes(tema)
    # Sesiones de ese día y de ese tema.
    candidatas = [s for s in repartidor.sesiones_del_dia(plan, fecha) if quitar_tildes(s.tema) == buscado]
    # Si se indicó hora, filtramos también por hora.
    if hora:
        # Solo las que empiezan a esa hora.
        candidatas = [s for s in candidatas if f"{s.inicio:%H:%M}" == str(hora).strip()]
    # Si no hay ninguna, lo explicamos.
    if not candidatas:
        # Mensaje para el usuario.
        raise ErrorPlanificador(f"En el plan no hay ninguna sesión de «{tema}» el {fecha:%d/%m}"
                                f"{' a las ' + str(hora) if hora else ''}.")
    # Devolvemos las encontradas.
    return candidatas


def marcar_por_tema(registro, plan, fecha, tema, estado, hora=None, ahora=None):
    """Marca una sesión de `tema` del día `fecha` y la devuelve.

    Si ese día hay varias sesiones del tema, marca la primera que todavía no tenga ese estado
    (así, marcar dos veces "hecha" marca las dos sesiones del día).
    """
    # Sesiones posibles.
    candidatas = sesiones_de(plan, fecha, tema, hora)
    # La primera que todavía no tiene ese estado; si todas lo tienen, la primera.
    elegida = next((s for s in candidatas if estado_de(registro, s) != estado), candidatas[0])
    # La marcamos.
    marcar(registro, elegida, estado, ahora)
    # La devolvemos (para decir cuál se marcó).
    return elegida


def _entradas(registro, desde, hasta):
    """Recorre las sesiones marcadas entre dos fechas (incluidas), ignorando las mal escritas."""
    # Cada sesión marcada.
    for entrada in registro["sesiones"].values():
        # Intentamos leer su fecha.
        try:
            # Fecha de la sesión.
            fecha = date.fromisoformat(entrada["fecha"])
        # Si está mal escrita, la saltamos.
        except (KeyError, TypeError, ValueError):
            # Siguiente.
            continue
        # Solo las del rango pedido.
        if desde <= fecha <= hasta:
            # La entregamos con su fecha.
            yield fecha, entrada


def pendiente_por_tema(registro, temas, hoy):
    """Minutos que quedan por recuperar de cada tema: {tema: minutos} (solo los que tienen algo).

    Cuenta las sesiones normales no hechas de los últimos 14 días y les resta las recuperaciones hechas.
    Nunca pasa de los minutos semanales del tema, y se ignora lo marcado antes de "olvidar lo pendiente".
    """
    # Primer día que se mira.
    inicio = hoy - timedelta(days=DIAS_RECUENTO)
    # Resultado.
    pendientes = {}
    # Cada tema.
    for tema in temas:
        # Nombre normalizado para comparar.
        buscado = quitar_tildes(tema["nombre"])
        # Momento en que se olvidó lo pendiente de este tema (si se hizo).
        olvidado = registro["perdonado"].get(buscado, "")
        # Minutos no hechos y minutos recuperados.
        no_hechos = recuperados = 0
        # Recorremos lo marcado en ese tiempo.
        for _fecha, entrada in _entradas(registro, inicio, hoy):
            # Solo este tema.
            if quitar_tildes(entrada.get("tema", "")) != buscado:
                # Siguiente.
                continue
            # Lo marcado antes de olvidar no cuenta.
            if olvidado and entrada.get("marcada", "") <= olvidado:
                # Siguiente.
                continue
            # Minutos de la sesión.
            minutos = int(entrada.get("minutos", 0))
            # Sesión normal no hecha: suma a lo pendiente.
            if entrada.get("estado") == "no_hecha" and not entrada.get("recuperacion"):
                # Suma.
                no_hechos += minutos
            # Recuperación hecha: resta.
            elif entrada.get("estado") == "hecha" and entrada.get("recuperacion"):
                # Resta.
                recuperados += minutos
        # Entre 0 y los minutos semanales del tema.
        minutos = max(0, min(no_hechos - recuperados, tema["minutos_semana"]))
        # Solo apuntamos los temas con algo pendiente.
        if minutos:
            # Apuntamos.
            pendientes[tema["nombre"]] = minutos
    # Devolvemos lo pendiente.
    return pendientes


def olvidar_pendiente(registro, tema, ahora=None):
    """Hace que lo pendiente de recuperar de `tema` deje de contar (lo que se marque después sí cuenta)."""
    # Guardamos el momento, con el nombre normalizado.
    registro["perdonado"][quitar_tildes(tema)] = (ahora or datetime.now()).isoformat(timespec="seconds")


def sin_marcar(plan, registro, ahora, desde=None):
    """Sesiones del plan que ya terminaron y siguen sin marcar (opcionalmente, solo desde una fecha)."""
    # Sin plan no hay nada.
    if plan is None:
        # Lista vacía.
        return []
    # Las que terminaron, no están marcadas y son del rango pedido.
    return [s for s in plan["sesiones"] if s.fin <= ahora and estado_de(registro, s) is None
            and (desde is None or s.inicio.date() >= desde)]


def resumen(registro, plan, temas, ahora):
    """Progreso de los últimos 14 días, por tema, y la racha de días seguidos estudiando.

    Devuelve {"temas": [ {tema, hechas, no_hechas, sin_marcar, minutos_hechos, cumplimiento, pendiente} ],
              "racha": días, "hechas": total, "no_hechas": total}.
    `cumplimiento` es el porcentaje de sesiones hechas entre las marcadas (None si no hay ninguna marcada).
    """
    # Fecha de hoy.
    hoy = ahora.date()
    # Primer día que se mira.
    inicio = hoy - timedelta(days=DIAS_RECUENTO - 1)
    # Una fila por tema actual (en el orden de prioridad).
    filas = {}
    # Temas de mayor a menor prioridad.
    for tema in sorted(temas, key=lambda t: (-t["prioridad"], t["nombre"].lower())):
        # Fila vacía.
        filas[quitar_tildes(tema["nombre"])] = {"tema": tema["nombre"], "hechas": 0, "no_hechas": 0,
                                                "sin_marcar": 0, "minutos_hechos": 0}
    # Días con al menos una sesión hecha (para la racha).
    dias_hechos = set()
    # Recorremos lo marcado.
    for fecha, entrada in _entradas(registro, inicio, hoy):
        # Nombre normalizado del tema.
        clave = quitar_tildes(entrada.get("tema", ""))
        # Si el tema ya no existe, también lo mostramos (con su nombre guardado).
        fila = filas.setdefault(clave, {"tema": entrada.get("tema", "?"), "hechas": 0, "no_hechas": 0,
                                        "sin_marcar": 0, "minutos_hechos": 0})
        # Hecha.
        if entrada.get("estado") == "hecha":
            # Contamos.
            fila["hechas"] += 1
            # Sumamos minutos.
            fila["minutos_hechos"] += int(entrada.get("minutos", 0))
            # Ese día cuenta para la racha.
            dias_hechos.add(fecha)
        # No hecha.
        elif entrada.get("estado") == "no_hecha":
            # Contamos.
            fila["no_hechas"] += 1
    # Sesiones del plan que ya pasaron y siguen sin marcar.
    for sesion in sin_marcar(plan, registro, ahora, inicio):
        # Fila de su tema.
        fila = filas.setdefault(quitar_tildes(sesion.tema), {"tema": sesion.tema, "hechas": 0, "no_hechas": 0,
                                                             "sin_marcar": 0, "minutos_hechos": 0})
        # Contamos.
        fila["sin_marcar"] += 1
    # Lo pendiente de recuperar.
    pendientes = {quitar_tildes(nombre): minutos for nombre, minutos in pendiente_por_tema(registro, temas, hoy).items()}
    # Completamos cada fila.
    for clave, fila in filas.items():
        # Sesiones marcadas.
        marcadas = fila["hechas"] + fila["no_hechas"]
        # Porcentaje de hechas (None si no hay marcadas).
        fila["cumplimiento"] = round(100 * fila["hechas"] / marcadas) if marcadas else None
        # Minutos pendientes de recuperar.
        fila["pendiente"] = pendientes.get(clave, 0)
    # Racha: días seguidos con alguna sesión hecha, terminando hoy (o ayer, si hoy todavía no hay).
    dia = hoy if hoy in dias_hechos else hoy - timedelta(days=1)
    # Contador.
    racha = 0
    # Mientras el día tenga algo hecho, seguimos hacia atrás.
    while dia in dias_hechos:
        # Un día más.
        racha += 1
        # Día anterior.
        dia -= timedelta(days=1)
    # Resultado.
    return {"temas": list(filas.values()), "racha": racha,
            "hechas": sum(f["hechas"] for f in filas.values()),
            "no_hechas": sum(f["no_hechas"] for f in filas.values())}


# ---------------------------------------------------------------------------------------------
# Metas
# ---------------------------------------------------------------------------------------------

def agregar_meta(metas, texto, tema=None, fecha=None, temas=None, hoy=None):
    """Agrega una meta (texto, y opcionalmente el tema y la fecha) y la devuelve."""
    # Quitamos espacios sobrantes.
    texto = str(texto or "").strip()
    # La meta necesita un texto.
    if not texto:
        # Mensaje para el usuario.
        raise ErrorPlanificador("Escribe la meta, por ejemplo: «Aprobar el examen de Química».")
    # Nombre exacto del tema (si se indicó).
    nombre_tema = None
    # Si se indicó un tema, tiene que existir.
    if tema and str(tema).strip():
        # Lo buscamos sin importar mayúsculas ni tildes.
        encontrado = almacen.buscar_tema(temas or [], str(tema))
        # Si no está, avisamos.
        if encontrado is None:
            # Mensaje para el usuario.
            raise ErrorPlanificador(f"No hay ningún tema llamado «{tema}». Agrégalo primero o deja la meta sin tema.")
        # Usamos su nombre exacto.
        nombre_tema = encontrado["nombre"]
    # Fecha (si se indicó).
    limite = leer_fecha(fecha, "la fecha de la meta") if fecha and str(fecha).strip() else None
    # Número nuevo: uno más que el mayor que haya.
    nuevo_id = max((m.get("id", 0) for m in metas), default=0) + 1
    # La meta.
    meta = {"id": nuevo_id, "texto": texto, "tema": nombre_tema, "fecha": limite.isoformat() if limite else None,
            "cumplida": False, "creada": (hoy or date.today()).isoformat()}
    # La añadimos.
    metas.append(meta)
    # La devolvemos.
    return meta


def buscar_meta(metas, identificador):
    """Devuelve la meta con ese número, o lanza un error si no existe."""
    # Buscamos.
    for meta in metas:
        # ¿Es esta?
        if str(meta.get("id")) == str(identificador).strip():
            # La devolvemos.
            return meta
    # No está.
    raise ErrorPlanificador(f"No hay ninguna meta con el número {identificador}.")


def cumplir_meta(metas, identificador, cumplida=True):
    """Marca una meta como cumplida (o pendiente otra vez) y la devuelve."""
    # La meta.
    meta = buscar_meta(metas, identificador)
    # Cambiamos su estado.
    meta["cumplida"] = bool(cumplida)
    # La devolvemos.
    return meta


def quitar_meta(metas, identificador):
    """Quita una meta y la devuelve."""
    # La meta.
    meta = buscar_meta(metas, identificador)
    # La quitamos.
    metas.remove(meta)
    # La devolvemos.
    return meta


def texto_meta(meta):
    """Describe una meta en una línea: "Examen de Química (Química) · 13/11"."""
    # Texto de la meta.
    partes = [meta["texto"]]
    # Tema entre paréntesis.
    if meta.get("tema"):
        # Lo añadimos.
        partes[0] += f" ({meta['tema']})"
    # Fecha.
    if meta.get("fecha"):
        # La añadimos con formato corto.
        partes.append(f"{date.fromisoformat(meta['fecha']):%d/%m/%Y}")
    # Cumplida.
    if meta.get("cumplida"):
        # Lo indicamos.
        partes.append("cumplida")
    # Todo junto.
    return " · ".join(partes)


# ---------------------------------------------------------------------------------------------
# Plan adaptado
# ---------------------------------------------------------------------------------------------

def ajustes_adaptativos(temas, config, registro, metas, desde, ahora):
    """Calcula cómo adaptar el plan que empieza en `desde`.

    Devuelve (temas_ajustados, recuperar, limites, notas):
      - temas_ajustados: copia de los temas, con más prioridad si tienen una meta cercana;
      - recuperar: {tema: minutos} de sesiones no hechas;
      - limites: {tema: fecha} de metas que caen dentro del plan;
      - notas: frases que explican cada cambio.
    """
    # Copia para no cambiar los temas guardados.
    ajustados = copy.deepcopy(temas)
    # Temas por nombre normalizado.
    por_nombre = {quitar_tildes(t["nombre"]): t for t in ajustados}
    # Último día del plan.
    hasta = desde + timedelta(days=6)
    # Resultados.
    limites, notas = {}, []
    # Metas pendientes con tema y fecha, de la más cercana a la más lejana.
    con_fecha = sorted((m for m in metas if not m.get("cumplida") and m.get("tema") and m.get("fecha")),
                       key=lambda m: m["fecha"])
    # Revisamos cada una.
    for meta in con_fecha:
        # Tema de la meta (si todavía existe).
        tema = por_nombre.get(quitar_tildes(meta["tema"]))
        # Fecha de la meta (si está mal escrita, la saltamos).
        try:
            # Fecha.
            fecha = date.fromisoformat(meta["fecha"])
        # Mal escrita.
        except ValueError:
            # Siguiente meta.
            continue
        # Sin tema, o con fecha en el pasado o el primer día del plan: no hay nada que adaptar.
        if tema is None or fecha <= desde:
            # Siguiente meta.
            continue
        # Días que faltan desde el inicio del plan.
        faltan = (fecha - desde).days
        # Solo las metas de las próximas dos semanas cambian el plan.
        if faltan > 14:
            # Siguiente meta.
            continue
        # Prioridad: la máxima si es esta semana; si no, un punto más.
        nueva = 5 if faltan <= 7 else min(5, tema["prioridad"] + 1)
        # Explicación.
        cambios = []
        # Si sube, lo aplicamos.
        if nueva > tema["prioridad"]:
            # Nueva prioridad.
            tema["prioridad"] = nueva
            # Lo explicamos.
            cambios.append(f"sube a prioridad {nueva}")
        # Si la fecha cae dentro de este plan, sus sesiones van antes (si no tenía ya un límite anterior).
        if fecha <= hasta + timedelta(days=1) and tema["nombre"] not in limites:
            # Límite.
            limites[tema["nombre"]] = fecha
            # Lo explicamos.
            cambios.append(f"sus sesiones van antes del {fecha:%d/%m}")
        # Si hubo cambios, añadimos la nota.
        if cambios:
            # Nota.
            notas.append(f"«{tema['nombre']}» {' y '.join(cambios)} por tu meta «{meta['texto']}» "
                         f"del {fecha:%d/%m}.")
    # Lo pendiente de recuperar (si está activado).
    recuperar = pendiente_por_tema(registro, temas, ahora.date()) if config["recuperar_no_hechas"] else {}
    # Una nota por tema con algo que recuperar.
    for nombre, minutos in recuperar.items():
        # Nota.
        notas.append(f"Se añaden {minutos_a_texto(minutos)} de «{nombre}» para recuperar sesiones que no hiciste.")
    # Devolvemos todo.
    return ajustados, recuperar, limites, notas


def planificar(temas, config, registro, metas, desde, ahora):
    """Genera el plan de 7 días adaptado a lo que hiciste y a tus metas (sin guardarlo)."""
    # Ajustes según lo hecho y las metas.
    ajustados, recuperar, limites, notas = ajustes_adaptativos(temas, config, registro, metas, desde, ahora)
    # Plan con esos ajustes.
    return repartidor.generar_plan(ajustados, config, desde, recuperar=recuperar, limites=limites, notas=notas)


def generar_y_guardar(desde=None, ahora=None):
    """Lee todo lo guardado, genera el plan adaptado, lo guarda en datos/plan.json y lo devuelve."""
    # Fecha y hora actuales.
    ahora = ahora or datetime.now()
    # Ajustes.
    config = almacen.cargar_config()
    # Temas.
    temas = almacen.cargar_temas()
    # Sin temas no hay nada que planificar.
    if not temas:
        # Explicamos cómo agregar uno.
        raise ErrorPlanificador(
            'No hay temas. Agrega uno, por ejemplo:\n  python planificador.py agregar "Matemáticas" --prioridad 5 --minutos 120'
        )
    # Fecha de inicio: la indicada o la automática (hoy, o mañana si ya pasó la hora).
    desde = desde or repartidor.primer_dia_por_defecto(config["horario"], ahora)
    # Plan adaptado.
    plan = planificar(temas, config, almacen.cargar_registro(), almacen.cargar_metas(), desde, ahora)
    # Lo guardamos.
    almacen.guardar_plan(repartidor.plan_a_dict(plan))
    # Lo devolvemos.
    return plan

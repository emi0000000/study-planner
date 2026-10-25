"""El "motor" del planificador: reparte el tiempo de cada tema en sesiones cortas.

Pasos que sigue generar_plan():
  1. Parte los minutos semanales de cada tema en bloques cortos (por ejemplo, de 25 min).
  2. Reparte los bloques entre los días de estudio de la semana:
       - primero los temas de mayor prioridad (si no entra todo, se quedan fuera los de menor prioridad);
       - un mismo tema va a días distintos y, si se puede, no seguidos (repasar con espacio ayuda a recordar);
       - cada día recibe una carga parecida, sin pasar del máximo diario;
       - las sesiones de un día terminan como muy tarde a medianoche.
  3. Ordena las sesiones de cada día: lo prioritario primero y sin repetir el mismo tema seguido.
  4. Les pone hora de inicio y fin, con descansos entre medias.

Para que el plan se adapte a lo que de verdad haces, generar_plan() acepta además:
  - minutos para recuperar sesiones que no hiciste (se colocan después de todo lo demás, si queda sitio);
  - fechas límite por tema (por ejemplo, un examen): sus sesiones prefieren los días anteriores.
El módulo progreso.py calcula esos datos a partir de lo que marcas y de tus metas.
"""

# dataclass crea clases sencillas para guardar datos sin escribir mucho código.
from dataclasses import dataclass
# Herramientas de fechas: date (día), datetime (día + hora), time (hora), timedelta (duración).
from datetime import date, datetime, time, timedelta

# El módulo de datos (de él sale, por ejemplo, cómo se genera un plan, para los mensajes).
import almacen
# Usamos la lista de días, el lector de horas y el tipo de error del módulo de datos.
from almacen import DIAS_SEMANA, ErrorPlanificador, leer_hora

# Si un tema ya tiene sesión un día, preferimos dejar al menos 2 días de distancia
# hasta la siguiente (lunes -> miércoles). Más distancia que eso ya no suma puntos.
DISTANCIA_IDEAL = 2


@dataclass
class Sesion:
    """Una sesión corta de estudio de un tema."""

    # Nombre del tema que se estudia.
    tema: str
    # Prioridad del tema (1 = baja, 5 = alta).
    prioridad: int
    # Duración de la sesión en minutos.
    minutos: int
    # Fecha y hora de comienzo (se rellena al armar el día).
    inicio: datetime | None = None
    # Fecha y hora de fin (se rellena al armar el día).
    fin: datetime | None = None
    # Número de esta sesión dentro del tema en la semana (1, 2, 3...).
    numero: int = 0
    # Cuántas sesiones tiene ese tema en total en la semana.
    total: int = 0
    # True si la sesión sirve para recuperar otra que no se hizo.
    recuperacion: bool = False

    def a_dict(self):
        """Convierte la sesión en un diccionario que se puede guardar en JSON."""
        # Devolvemos cada dato; las fechas se escriben como texto "2026-10-26T18:00".
        return {
            # Nombre del tema.
            "tema": self.tema,
            # Prioridad del tema.
            "prioridad": self.prioridad,
            # Duración en minutos.
            "minutos": self.minutos,
            # Inicio como texto (o None si todavía no tiene hora).
            "inicio": self.inicio.isoformat(timespec="minutes") if self.inicio else None,
            # Fin como texto (o None si todavía no tiene hora).
            "fin": self.fin.isoformat(timespec="minutes") if self.fin else None,
            # Número de sesión dentro del tema.
            "numero": self.numero,
            # Total de sesiones del tema.
            "total": self.total,
            # ¿Es para recuperar una sesión no hecha?
            "recuperacion": self.recuperacion,
        }

    @classmethod
    def desde_dict(cls, datos):
        """Crea una sesión a partir de un diccionario leído del JSON."""
        # Convertimos los textos de fecha otra vez en objetos datetime.
        return cls(
            # Nombre del tema.
            tema=datos["tema"],
            # Prioridad.
            prioridad=datos["prioridad"],
            # Duración.
            minutos=datos["minutos"],
            # Inicio: texto -> datetime (si lo hay).
            inicio=datetime.fromisoformat(datos["inicio"]) if datos.get("inicio") else None,
            # Fin: texto -> datetime (si lo hay).
            fin=datetime.fromisoformat(datos["fin"]) if datos.get("fin") else None,
            # Número de sesión (0 si no estaba guardado).
            numero=datos.get("numero", 0),
            # Total de sesiones (0 si no estaba guardado).
            total=datos.get("total", 0),
            # Recuperación (False si no estaba guardado).
            recuperacion=bool(datos.get("recuperacion", False)),
        )


def partir_en_bloques(minutos_semana, duracion, minima):
    """Divide los minutos semanales de un tema en bloques cortos.

    Ejemplos con sesiones de 25 min y mínimo de 10:
      100 -> [25, 25, 25, 25]
      110 -> [25, 25, 25, 25, 10]   (sobran 10: alcanza para una sesión corta más)
      105 -> [25, 25, 25, 30]       (sobran 5: se suman a la última sesión)
    """
    # Si no hay minutos, no hay sesiones.
    if minutos_semana <= 0:
        # Lista vacía.
        return []
    # divmod da cuántas sesiones completas caben y cuántos minutos sobran.
    completas, sobrante = divmod(minutos_semana, duracion)
    # Empezamos con todas las sesiones completas.
    bloques = [duracion] * completas
    # Si sobra lo suficiente (o no hay ninguna sesión completa), el sobrante es una sesión más.
    if sobrante >= minima or (sobrante > 0 and not bloques):
        # Añadimos la sesión corta del final.
        bloques.append(sobrante)
    # Si sobra muy poco, lo sumamos a la última sesión para no crear una de 2 o 3 minutos.
    elif sobrante > 0:
        # La última sesión queda un poco más larga.
        bloques[-1] += sobrante
    # Devolvemos la lista de duraciones.
    return bloques


def dias_del_plan(desde, horario):
    """Devuelve {fecha: "HH:MM"} con los días de estudio de los 7 días que empiezan en `desde`."""
    # Diccionario fecha -> hora de inicio.
    dias = {}
    # Recorremos los 7 días: desde, desde+1, ..., desde+6.
    for desplazamiento in range(7):
        # Calculamos la fecha de ese día.
        fecha = desde + timedelta(days=desplazamiento)
        # weekday() da 0 para lunes, 1 para martes... y lo pasamos a nombre.
        nombre = DIAS_SEMANA[fecha.weekday()]
        # Solo nos interesan los días que están en el horario de estudio.
        if nombre in horario:
            # Guardamos la fecha con su hora de inicio.
            dias[fecha] = horario[nombre]
    # Devolvemos los días de estudio.
    return dias


def minutos_hasta_medianoche(hora_inicio):
    """Minutos que hay desde la hora de inicio ("18:00") hasta las 00:00. Ejemplo: "22:30" -> 90."""
    # Convertimos "22:30" en números.
    horas, minutos = leer_hora(hora_inicio)
    # Un día tiene 24 * 60 = 1440 minutos; le restamos los que ya pasaron a esa hora.
    return 24 * 60 - (horas * 60 + minutos)


def duracion_con_descansos(duraciones, config):
    """Minutos desde que empieza la primera sesión del día hasta que acaba la última.

    Suma las sesiones y los descansos que hay entre ellas, igual que poner_horarios().
    Ejemplo con la configuración por defecto: [25, 25, 25, 25, 25] -> 125 + 5 + 5 + 5 + 15 = 155.
    """
    # Cada cuántas sesiones toca descanso largo.
    cada = config["sesiones_antes_de_descanso_largo"]
    # Descanso que va después de cada sesión, menos la última (después de la última ya no se estudia).
    descansos = sum(
        # Largo en las posiciones 4, 8, 12... (si está activado); corto en las demás.
        config["descanso_largo"] if cada > 0 and posicion % cada == 0 else config["descanso_corto"]
        # Posiciones 1, 2, ..., n-1.
        for posicion in range(1, len(duraciones))
    )
    # Minutos de estudio más minutos de descanso.
    return sum(duraciones) + descansos


def elegir_dia(tema, minutos, por_dia, config, disponibles, limite=None):
    """Elige el mejor día para una sesión de `tema`, o None si no cabe en ninguno.

    Un día sirve si, con esta sesión, no pasa del máximo diario y termina antes de medianoche
    (`disponibles` dice cuántos minutos hay en cada día desde la hora de inicio hasta las 00:00).

    Entre los días donde todavía cabe, prefiere (en este orden):
      0. si el tema tiene fecha `limite` (por ejemplo, un examen), los días anteriores a esa fecha;
      1. el que tenga menos sesiones de este mismo tema;
      2. el que no esté pegado a otro día que ya tiene este tema;
      3. el que tenga menos minutos ocupados;
      4. el más temprano.
    """
    # Máximo de minutos de estudio por día (0 = sin límite).
    maximo = config["maximo_minutos_por_dia"]
    # Días que ya tienen al menos una sesión de este tema.
    dias_con_tema = [fecha for fecha, lista in por_dia.items() if any(s.tema == tema for s in lista)]
    # Todavía no elegimos ningún día.
    mejor_dia = None
    # "Puntuación" del mejor día encontrado (cuanto más baja, mejor).
    mejor_clave = None
    # Probamos cada día de estudio.
    for fecha, lista in por_dia.items():
        # Minutos de estudio que ya tiene ese día.
        ocupados = sum(s.minutos for s in lista)
        # Si hay máximo diario (distinto de 0) y la sesión no cabe, saltamos el día.
        if maximo and ocupados + minutos > maximo:
            # Pasamos al siguiente día.
            continue
        # Si con esta sesión (y sus descansos) el día terminaría después de medianoche, también lo saltamos.
        if duracion_con_descansos([s.minutos for s in lista] + [minutos], config) > disponibles[fecha]:
            # Pasamos al siguiente día.
            continue
        # Cuántas sesiones de este tema tiene ya ese día.
        repeticiones = sum(1 for s in lista if s.tema == tema)
        # Distancia en días al día más cercano que ya tiene este tema (si no hay ninguno, la ideal).
        distancia = min((abs((fecha - otro).days) for otro in dias_con_tema), default=DISTANCIA_IDEAL)
        # 0 si el día va antes de la fecha límite del tema (o si no tiene); 1 si va después.
        despues_del_limite = 0 if limite is None or fecha < limite else 1
        # Armamos la puntuación: Python compara las tuplas elemento a elemento, en orden.
        clave = (despues_del_limite, repeticiones, -min(distancia, DISTANCIA_IDEAL), ocupados, fecha)
        # Si es el primer día que cabe, o es mejor que el anterior, lo guardamos.
        if mejor_clave is None or clave < mejor_clave:
            # Nuevo mejor día.
            mejor_dia, mejor_clave = fecha, clave
    # Devolvemos el día elegido (o None si no cupo en ninguno).
    return mejor_dia


def ordenar_dia(lista):
    """Ordena las sesiones de un día: lo más prioritario primero y, si se puede, sin repetir tema seguido."""
    # Ordenamos de mayor a menor prioridad (y por nombre si empatan, para que sea siempre igual).
    pendientes = sorted(lista, key=lambda s: (-s.prioridad, s.tema.lower()))
    # Aquí iremos poniendo las sesiones en su orden final.
    ordenadas = []
    # Mientras queden sesiones por colocar...
    while pendientes:
        # Tema de la última sesión colocada (None si todavía no hay ninguna).
        ultimo_tema = ordenadas[-1].tema if ordenadas else None
        # Buscamos la más prioritaria cuyo tema sea distinto del último; si no hay, la primera.
        siguiente = next((s for s in pendientes if s.tema != ultimo_tema), pendientes[0])
        # La quitamos de pendientes.
        pendientes.remove(siguiente)
        # Y la ponemos en el orden final.
        ordenadas.append(siguiente)
    # Devolvemos el día ordenado.
    return ordenadas


def poner_horarios(fecha, hora_inicio, sesiones, config):
    """Asigna hora de inicio y fin a cada sesión del día, dejando descansos entre medias."""
    # Convertimos "18:00" en números.
    horas, minutos = leer_hora(hora_inicio)
    # El "reloj" empieza a la hora de inicio de ese día.
    reloj = datetime.combine(fecha, time(horas, minutos))
    # Cada cuántas sesiones toca descanso largo.
    cada = config["sesiones_antes_de_descanso_largo"]
    # Recorremos las sesiones contando desde 1.
    for posicion, sesion in enumerate(sesiones, start=1):
        # La sesión empieza donde está el reloj.
        sesion.inicio = reloj
        # Y termina sus minutos después.
        sesion.fin = reloj + timedelta(minutes=sesion.minutos)
        # ¿Toca descanso largo? Solo si está activado y es la sesión número 4, 8, 12...
        toca_largo = cada > 0 and posicion % cada == 0
        # Elegimos la duración del descanso.
        descanso = config["descanso_largo"] if toca_largo else config["descanso_corto"]
        # Avanzamos el reloj: fin de la sesión + descanso.
        reloj = sesion.fin + timedelta(minutes=descanso)


def numerar(sesiones):
    """Pone a cada sesión su número dentro del tema (1/3, 2/3, 3/3) según el orden en el tiempo."""
    # Agrupamos las sesiones por tema.
    por_tema = {}
    # Las recorremos en orden cronológico.
    for sesion in sorted(sesiones, key=lambda s: s.inicio):
        # Añadimos la sesión a la lista de su tema (creándola si hace falta).
        por_tema.setdefault(sesion.tema, []).append(sesion)
    # Para cada tema...
    for lista in por_tema.values():
        # ...numeramos sus sesiones desde 1.
        for numero, sesion in enumerate(lista, start=1):
            # Número de esta sesión.
            sesion.numero = numero
            # Total de sesiones del tema.
            sesion.total = len(lista)


def generar_plan(temas, config, desde, recuperar=None, limites=None, notas=None):
    """Crea el plan de 7 días que empieza en `desde`.

    Opcionales (los calcula progreso.py para adaptar el plan):
      recuperar: {tema: minutos} que añadir para recuperar sesiones no hechas;
      limites:   {tema: fecha} antes de la cual conviene estudiar ese tema;
      notas:     frases que explican los cambios (se muestran con el plan).

    Devuelve un diccionario con:
      "desde" y "hasta": primera y última fecha del plan;
      "sesiones": lista de Sesion con hora, ordenada en el tiempo;
      "sin_lugar": sesiones que no entraron (por el máximo diario o porque el día llegaba a medianoche);
      "notas": explicaciones de cómo se adaptó el plan.
    """
    # Sin datos opcionales, diccionarios y listas vacíos.
    recuperar, limites, notas = recuperar or {}, limites or {}, list(notas or [])
    # Días de estudio de esta semana con su hora de inicio.
    dias = dias_del_plan(desde, config["horario"])
    # Minutos que hay en cada día desde la hora de inicio hasta medianoche.
    disponibles = {fecha: minutos_hasta_medianoche(hora) for fecha, hora in dias.items()}
    # Para cada día, la lista de sesiones que le vamos asignando (empieza vacía).
    por_dia = {fecha: [] for fecha in dias}
    # Sesiones que no caben en ningún día.
    sin_lugar = []
    # Ordenamos los temas: mayor prioridad primero; si empatan, por nombre.
    ordenados = sorted(temas, key=lambda t: (-t["prioridad"], t["nombre"].lower()))
    # Recorremos cada tema.
    for tema in ordenados:
        # Partimos sus minutos semanales en bloques cortos.
        bloques = partir_en_bloques(tema["minutos_semana"], config["duracion_sesion"], config["duracion_minima"])
        # Colocamos cada bloque.
        for minutos in bloques:
            # Creamos la sesión (todavía sin hora).
            sesion = Sesion(tema=tema["nombre"], prioridad=tema["prioridad"], minutos=minutos)
            # Buscamos el mejor día para ella.
            fecha = elegir_dia(sesion.tema, minutos, por_dia, config, disponibles, limites.get(sesion.tema))
            # Si no cabe en ningún día...
            if fecha is None:
                # ...la apuntamos como "sin lugar".
                sin_lugar.append(sesion)
            # Si cabe...
            else:
                # ...la añadimos a ese día.
                por_dia[fecha].append(sesion)
    # Después, con lo que quede libre, las recuperaciones (también por prioridad).
    for tema in ordenados:
        # Minutos a recuperar de este tema (0 si no hay).
        pendientes = recuperar.get(tema["nombre"], 0)
        # Minutos de recuperación que no caben.
        sin_sitio = 0
        # Partimos esos minutos en sesiones cortas.
        for minutos in partir_en_bloques(pendientes, config["duracion_sesion"], config["duracion_minima"]):
            # Sesión de recuperación.
            sesion = Sesion(tema=tema["nombre"], prioridad=tema["prioridad"], minutos=minutos, recuperacion=True)
            # Buscamos el mejor día para ella.
            fecha = elegir_dia(sesion.tema, minutos, por_dia, config, disponibles, limites.get(sesion.tema))
            # Si no cabe, lo apuntamos (no cuenta como "sin lugar": es tiempo extra).
            if fecha is None:
                # Suma a lo que no cupo.
                sin_sitio += minutos
            # Si cabe, la añadimos a ese día.
            else:
                # Al día elegido.
                por_dia[fecha].append(sesion)
        # Si algo no cupo, lo explicamos.
        if sin_sitio:
            # Nota para el usuario.
            notas.append(f"No cupieron {sin_sitio} min de recuperación de «{tema['nombre']}» en esta semana.")
    # Aquí juntaremos todas las sesiones ya con hora.
    todas = []
    # Armamos cada día.
    for fecha, lista in por_dia.items():
        # Ordenamos las sesiones del día.
        ordenadas = ordenar_dia(lista)
        # Les ponemos hora.
        poner_horarios(fecha, dias[fecha], ordenadas, config)
        # Las sumamos al total.
        todas.extend(ordenadas)
    # Numeramos las sesiones de cada tema (1/4, 2/4...).
    numerar(todas)
    # Ordenamos todo por fecha y hora.
    todas.sort(key=lambda s: s.inicio)
    # Devolvemos el plan completo.
    return {"desde": desde, "hasta": desde + timedelta(days=6), "sesiones": todas, "sin_lugar": sin_lugar,
            "notas": notas}


def primer_dia_por_defecto(horario, ahora):
    """Decide desde qué día planificar si el usuario no lo indica.

    Normalmente hoy. Pero si hoy es día de estudio y su hora de inicio ya pasó, mañana
    (así no se crean sesiones en el pasado).
    """
    # Fecha de hoy.
    hoy = ahora.date()
    # Nombre del día de hoy ("lunes", "martes"...).
    nombre = DIAS_SEMANA[hoy.weekday()]
    # Si hoy se estudia...
    if nombre in horario:
        # ...miramos a qué hora se empieza.
        horas, minutos = leer_hora(horario[nombre])
        # Si esa hora ya pasó...
        if ahora >= datetime.combine(hoy, time(horas, minutos)):
            # ...empezamos mañana.
            return hoy + timedelta(days=1)
    # En cualquier otro caso, empezamos hoy.
    return hoy


def sesiones_del_dia(plan, fecha):
    """Devuelve las sesiones del plan que empiezan en la fecha indicada."""
    # Filtramos por la fecha de inicio de cada sesión.
    return [s for s in plan["sesiones"] if s.inicio.date() == fecha]


def plan_a_dict(plan):
    """Convierte el plan en un diccionario apto para guardar en JSON."""
    # Las fechas pasan a texto y cada sesión a diccionario.
    return {
        # Primera fecha del plan.
        "desde": plan["desde"].isoformat(),
        # Última fecha del plan.
        "hasta": plan["hasta"].isoformat(),
        # Sesiones con hora.
        "sesiones": [s.a_dict() for s in plan["sesiones"]],
        # Sesiones que no entraron.
        "sin_lugar": [s.a_dict() for s in plan["sin_lugar"]],
        # Explicaciones de cómo se adaptó el plan.
        "notas": list(plan.get("notas", [])),
    }


def plan_desde_dict(datos):
    """Hace lo contrario de plan_a_dict: reconstruye el plan leído del JSON.

    Si el archivo del plan está incompleto o mal editado, lanza un error claro en vez de fallar a medias.
    """
    # Mensaje por si el archivo está dañado.
    danado = f"El plan guardado (datos/plan.json) está dañado. Vuelve a crearlo con:  {almacen.COMO_GENERAR}"
    # Intentamos reconstruir el plan.
    try:
        # Los textos vuelven a ser fechas y los diccionarios, sesiones.
        plan = {
            # Primera fecha.
            "desde": date.fromisoformat(datos["desde"]),
            # Última fecha.
            "hasta": date.fromisoformat(datos["hasta"]),
            # Sesiones con hora.
            "sesiones": [Sesion.desde_dict(d) for d in datos.get("sesiones", [])],
            # Sesiones sin lugar.
            "sin_lugar": [Sesion.desde_dict(d) for d in datos.get("sin_lugar", [])],
            # Notas (lista vacía en planes antiguos).
            "notas": [str(nota) for nota in datos.get("notas", [])],
        }
    # Falta un dato, hay algo de otro tipo o una fecha está mal escrita.
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        # Pedimos generar otro plan.
        raise ErrorPlanificador(danado) from error
    # Toda sesión del plan tiene que tener hora de inicio y de fin.
    if not all(s.inicio and s.fin for s in plan["sesiones"]):
        # Pedimos generar otro plan.
        raise ErrorPlanificador(danado)
    # Devolvemos el plan listo para usar.
    return plan

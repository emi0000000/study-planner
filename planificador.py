"""Planificador de estudio: reparte tu tiempo entre temas en sesiones cortas
y las crea en Google Calendar para que el teléfono te avise.

Uso básico (más detalles en el README):
  python planificador.py agregar "Matemáticas" --prioridad 5 --minutos 120
  python planificador.py temas
  python planificador.py generar
  python planificador.py hoy
  python planificador.py subir
"""

# argparse lee los comandos y opciones que escribes en la terminal.
import argparse
# json se usa para mostrar la configuración de forma ordenada.
import json
# sys da acceso a la salida de errores y al código de salida del programa.
import sys
# Herramientas de fechas.
from datetime import date, datetime, timedelta

# Módulo que guarda y lee los datos (temas, configuración, plan).
import almacen
# Módulo que habla con Google Calendar.
import calendario_google
# Módulo que reparte el tiempo en sesiones.
import repartidor

# Nombres de días con tilde para mostrarlos bonitos (los demás solo llevan mayúscula inicial).
NOMBRES_VISIBLES = {"miercoles": "Miércoles", "sabado": "Sábado"}


def leer_fecha(texto):
    """Convierte "2026-10-26" en una fecha. argparse la usa para validar --desde, --hasta y --fecha."""
    # Intentamos interpretar el texto como fecha AAAA-MM-DD.
    try:
        # fromisoformat entiende justo ese formato.
        return date.fromisoformat(texto)
    # Si no se puede...
    except ValueError as error:
        # ...argparse mostrará este mensaje.
        raise argparse.ArgumentTypeError(f'"{texto}" no es una fecha válida; usa AAAA-MM-DD, por ejemplo 2026-10-26.') from error


def nombre_dia(fecha):
    """Devuelve algo como "Miércoles 28/10"."""
    # Nombre interno del día ("miercoles").
    nombre = almacen.DIAS_SEMANA[fecha.weekday()]
    # Versión para mostrar ("Miércoles").
    visible = NOMBRES_VISIBLES.get(nombre, nombre.capitalize())
    # Le añadimos día y mes.
    return f"{visible} {fecha:%d/%m}"


def mostrar_sesiones(sesiones):
    """Imprime una lista de sesiones con su horario y el total de minutos."""
    # Una línea por sesión.
    for sesion in sesiones:
        # Por ejemplo: "  18:00-18:25  Matemáticas (1/5)".
        print(f"  {sesion.inicio:%H:%M}-{sesion.fin:%H:%M}  {sesion.tema} ({sesion.numero}/{sesion.total})")
    # Suma de minutos de estudio (sin descansos).
    total = sum(s.minutos for s in sesiones)
    # Mostramos el total.
    print(f"  = {total} min de estudio")


def mostrar_plan(plan):
    """Imprime el plan de la semana, un resumen por tema y lo que no entró."""
    # Encabezado con las fechas.
    print(f"Plan de estudio del {plan['desde']:%d/%m/%Y} al {plan['hasta']:%d/%m/%Y}\n")
    # Recorremos los 7 días del plan.
    for desplazamiento in range(7):
        # Fecha de ese día.
        fecha = plan["desde"] + timedelta(days=desplazamiento)
        # Sesiones de ese día.
        del_dia = repartidor.sesiones_del_dia(plan, fecha)
        # Si no hay sesiones, lo marcamos como libre en una sola línea.
        if not del_dia:
            # Día libre.
            print(f"{nombre_dia(fecha)}  (libre)\n")
            # Pasamos al siguiente día.
            continue
        # Nombre del día.
        print(nombre_dia(fecha))
        # Sus sesiones.
        mostrar_sesiones(del_dia)
        # Línea en blanco para separar días.
        print()
    # Minutos planificados por tema.
    planificados = {}
    # Minutos pedidos por tema (planificados + los que no entraron).
    pedidos = {}
    # Sumamos las sesiones que sí entraron.
    for sesion in plan["sesiones"]:
        # Suma a planificados.
        planificados[sesion.tema] = planificados.get(sesion.tema, 0) + sesion.minutos
        # Suma a pedidos.
        pedidos[sesion.tema] = pedidos.get(sesion.tema, 0) + sesion.minutos
    # Sumamos también las que no entraron (solo a pedidos).
    for sesion in plan["sin_lugar"]:
        # Suma a pedidos.
        pedidos[sesion.tema] = pedidos.get(sesion.tema, 0) + sesion.minutos
    # Título del resumen.
    print("Resumen por tema:")
    # Una línea por tema.
    for tema, minutos_pedidos in pedidos.items():
        # Por ejemplo: "  Matemáticas: 120 de 120 min".
        print(f"  {tema}: {planificados.get(tema, 0)} de {minutos_pedidos} min")
    # Si algo no entró, lo explicamos.
    if plan["sin_lugar"]:
        # Total de minutos que no entraron.
        faltan = sum(s.minutos for s in plan["sin_lugar"])
        # Aviso.
        print(f"\nAtención: no entraron {len(plan['sin_lugar'])} sesiones ({faltan} min) por el máximo diario.")
        # Qué se puede hacer.
        print('Para que entren: sube "maximo_minutos_por_dia" o agrega días en "horario" (config.json),')
        # Continuación del consejo.
        print("o baja los minutos de algún tema. Siempre se quedan fuera primero los de menor prioridad.")


def comando_agregar(args):
    """Agrega un tema (o lo actualiza si ya existía)."""
    # Leemos los temas guardados.
    temas = almacen.cargar_temas()
    # Agregamos o actualizamos el tema.
    es_nuevo = almacen.agregar_tema(temas, args.nombre, args.prioridad, args.minutos)
    # Guardamos la lista.
    almacen.guardar_temas(temas)
    # Palabra según el caso.
    accion = "Agregado" if es_nuevo else "Actualizado"
    # Confirmamos al usuario.
    print(f'{accion}: "{args.nombre.strip()}" con prioridad {args.prioridad} y {args.minutos} min por semana.')


def comando_temas(args):
    """Muestra los temas guardados."""
    # Leemos los temas.
    temas = almacen.cargar_temas()
    # Si no hay, explicamos cómo agregar uno.
    if not temas:
        # Mensaje con ejemplo.
        print('No hay temas todavía. Agrega uno con:\n  python planificador.py agregar "Matemáticas" --prioridad 5 --minutos 120')
        # Terminamos.
        return
    # Encabezado de la tabla.
    print(f"{'Prioridad':>9}  {'Min/semana':>10}  Tema")
    # Una fila por tema, de mayor a menor prioridad.
    for tema in sorted(temas, key=lambda t: (-t["prioridad"], t["nombre"].lower())):
        # Fila con columnas alineadas.
        print(f"{tema['prioridad']:>9}  {tema['minutos_semana']:>10}  {tema['nombre']}")
    # Total de minutos pedidos.
    total = sum(t["minutos_semana"] for t in temas)
    # Lo mostramos también en horas.
    print(f"\nTotal: {total} min por semana (unas {total / 60:.1f} horas).")


def comando_quitar(args):
    """Quita un tema."""
    # Leemos los temas.
    temas = almacen.cargar_temas()
    # Quitamos el indicado (da error si no existe).
    quitado = almacen.quitar_tema(temas, args.nombre)
    # Guardamos la lista sin él.
    almacen.guardar_temas(temas)
    # Confirmamos.
    print(f'Quitado: "{quitado["nombre"]}". Vuelve a ejecutar "generar" para actualizar el plan.')


def comando_generar(args):
    """Genera el plan de 7 días, lo guarda y lo muestra."""
    # Leemos la configuración.
    config = almacen.cargar_config()
    # Leemos los temas.
    temas = almacen.cargar_temas()
    # Sin temas no hay nada que planificar.
    if not temas:
        # Explicamos cómo agregar uno.
        raise almacen.ErrorPlanificador(
            'No hay temas. Agrega uno, por ejemplo:\n  python planificador.py agregar "Matemáticas" --prioridad 5 --minutos 120'
        )
    # Fecha de inicio: la que indicó el usuario o la automática (hoy o mañana).
    desde = args.desde or repartidor.primer_dia_por_defecto(config["horario"], datetime.now())
    # Creamos el plan.
    plan = repartidor.generar_plan(temas, config, desde)
    # Lo guardamos en datos/plan.json.
    almacen.guardar_plan(repartidor.plan_a_dict(plan))
    # Lo mostramos.
    mostrar_plan(plan)
    # Siguiente paso sugerido.
    print("\nPlan guardado. Para crear estas sesiones en Google Calendar:  python planificador.py subir")


def comando_hoy(args):
    """Muestra las sesiones de hoy (o de la fecha indicada) según el plan guardado."""
    # Leemos el plan guardado.
    plan = repartidor.plan_desde_dict(almacen.cargar_plan())
    # Fecha a mostrar: la indicada o hoy.
    fecha = args.fecha or date.today()
    # Si la fecha no está dentro del plan, lo decimos.
    if not plan["desde"] <= fecha <= plan["hasta"]:
        # Explicación con las fechas del plan.
        print(f"El plan guardado va del {plan['desde']:%d/%m} al {plan['hasta']:%d/%m} y no incluye el {fecha:%d/%m}.")
        # Cómo arreglarlo.
        print("Genera uno nuevo con:  python planificador.py generar")
        # Terminamos.
        return
    # Sesiones de ese día.
    del_dia = repartidor.sesiones_del_dia(plan, fecha)
    # Nombre del día.
    print(nombre_dia(fecha))
    # Si no hay sesiones, es día libre.
    if not del_dia:
        # Mensaje.
        print("  Día libre: no hay sesiones.")
        # Terminamos.
        return
    # Mostramos las sesiones.
    mostrar_sesiones(del_dia)


def comando_subir(args):
    """Crea las sesiones del plan guardado en Google Calendar."""
    # Leemos la configuración (calendario y minutos de aviso).
    config = almacen.cargar_config()
    # Leemos el plan guardado.
    plan = repartidor.plan_desde_dict(almacen.cargar_plan())
    # Si el plan no tiene sesiones, no hay nada que subir.
    if not plan["sesiones"]:
        # Explicamos.
        raise almacen.ErrorPlanificador("El plan guardado no tiene sesiones. Agrega temas y vuelve a ejecutar «generar».")
    # Si el plan ya terminó, subirlo no sirve de nada.
    if plan["hasta"] < date.today():
        # Explicamos.
        raise almacen.ErrorPlanificador(
            f"El plan guardado terminó el {plan['hasta']:%d/%m}. Genera uno nuevo con:  python planificador.py generar"
        )
    # Minutos de aviso antes de cada sesión.
    aviso = config["aviso_minutos_antes"]
    # Calendario donde se crean.
    id_calendario = config["id_calendario"]
    # Modo simulación: mostramos lo que se crearía, sin conectar con Google.
    if args.simular:
        # Encabezado.
        print(f'Simulación: se crearían {len(plan["sesiones"])} eventos en el calendario "{id_calendario}",')
        # Continuación.
        print(f"cada uno con aviso {aviso} min antes:")
        # Un evento por línea.
        for sesion in plan["sesiones"]:
            # Convertimos la sesión en evento, igual que al subir de verdad.
            evento = calendario_google.evento_desde_sesion(sesion, aviso)
            # Mostramos día, hora y título.
            print(f"  {nombre_dia(sesion.inicio.date())}  {sesion.inicio:%H:%M}-{sesion.fin:%H:%M}  {evento['summary']}")
        # No seguimos.
        return
    # Conectamos (la primera vez se abre el navegador para dar permiso).
    print("Conectando con Google Calendar...")
    # Obtenemos el servicio.
    servicio = calendario_google.conectar()
    # Avisamos de lo que vamos a hacer.
    print(f"Subiendo {len(plan['sesiones'])} sesiones...")
    # Subimos el plan.
    creados, borrados = calendario_google.subir_plan(servicio, id_calendario, plan, aviso, args.reemplazar)
    # Si se reemplazaron sesiones viejas, lo decimos.
    if borrados:
        # Mensaje.
        print(f"Se borraron {borrados} sesiones anteriores del planificador en esas fechas.")
    # Resultado final.
    print(f"Listo: {creados} sesiones creadas en Google Calendar.")
    # Recordatorio sobre el teléfono.
    print(f"Cada una avisará {aviso} min antes en el teléfono (app Google Calendar con notificaciones activadas).")


def comando_limpiar(args):
    """Borra del calendario las sesiones creadas por esta app (solo esas)."""
    # Leemos la configuración (para saber qué calendario usar).
    config = almacen.cargar_config()
    # Si el usuario indicó --desde, usamos sus fechas.
    if args.desde:
        # Primer día.
        desde = args.desde
        # Último día: el indicado o 6 días después.
        hasta = args.hasta or desde + timedelta(days=6)
    # Si no, usamos las fechas del plan guardado.
    else:
        # Leemos el plan.
        plan = repartidor.plan_desde_dict(almacen.cargar_plan())
        # Fechas del plan.
        desde, hasta = plan["desde"], plan["hasta"]
    # Conectamos con Google.
    print("Conectando con Google Calendar...")
    # Obtenemos el servicio.
    servicio = calendario_google.conectar()
    # Borramos las sesiones de la app en ese rango.
    borrados = calendario_google.quitar_plan(servicio, config["id_calendario"], desde, hasta)
    # Informamos.
    print(f"Se borraron {borrados} sesiones del planificador entre el {desde:%d/%m} y el {hasta:%d/%m}.")


def comando_config(args):
    """Muestra la configuración actual y dónde está el archivo."""
    # Leemos (y validamos) la configuración.
    config = almacen.cargar_config()
    # Dónde está el archivo para editarlo.
    print(f"Archivo de configuración: {almacen.ARCHIVO_CONFIG}\n")
    # Contenido, ordenado y con tildes.
    print(json.dumps(config, indent=2, ensure_ascii=False))
    # Máximo diario.
    maximo = config["maximo_minutos_por_dia"]
    # Si hay límite, mostramos cuánto cabe por semana.
    if maximo:
        # Capacidad semanal = máximo diario × días de estudio.
        capacidad = maximo * len(config["horario"])
        # Mensaje.
        print(f"\nCon este horario caben hasta {capacidad} min de estudio por semana.")


class FormatoAyuda(argparse.HelpFormatter):
    """Igual que el formato de ayuda normal, pero empieza con "Uso:" en vez de "usage:"."""

    def add_usage(self, usage, actions, groups, prefix=None):
        # Solo cambiamos el prefijo cuando no viene ninguno (argparse a veces pasa "" a propósito).
        if prefix is None:
            # Prefijo en español.
            prefix = "Uso: "
        # Llamamos al método original con ese prefijo.
        return super().add_usage(usage, actions, groups, prefix)


def en_espanol(parser):
    """Traduce los títulos de la ayuda y añade -h/--help con texto en español."""
    # Título de los argumentos obligatorios.
    parser._positionals.title = "argumentos"
    # Título de las opciones.
    parser._optionals.title = "opciones"
    # Opción de ayuda (la normal viene en inglés, así que la desactivamos y ponemos esta).
    parser.add_argument("-h", "--help", action="help", help="muestra esta ayuda y termina")


def nuevo_comando(sub, nombre, ayuda, funcion):
    """Crea un subcomando con su ayuda en español y la función que lo ejecuta."""
    # Creamos el subcomando (add_help=False porque la ayuda la añade en_espanol).
    parser = sub.add_parser(nombre, help=ayuda, description=ayuda, formatter_class=FormatoAyuda, add_help=False)
    # Ayuda en español.
    en_espanol(parser)
    # Función que se ejecuta con este comando.
    parser.set_defaults(funcion=funcion)
    # Devolvemos el subcomando para poder añadirle opciones.
    return parser


def crear_parser():
    """Define los comandos y opciones que entiende el programa."""
    # Parser principal con una descripción.
    parser = argparse.ArgumentParser(
        # Nombre que aparece en la ayuda.
        prog="python planificador.py",
        # Descripción general.
        description="Reparte tu tiempo de estudio en sesiones cortas y las crea en Google Calendar.",
        # Formato con "Uso:" en español.
        formatter_class=FormatoAyuda,
        # La ayuda la añadimos en español con en_espanol().
        add_help=False,
    )
    # Ayuda en español.
    en_espanol(parser)
    # Contenedor de subcomandos (agregar, temas, generar...).
    sub = parser.add_subparsers(title="comandos", metavar="COMANDO")

    # --- agregar ---
    # Comando para agregar o actualizar un tema.
    p = nuevo_comando(sub, "agregar", "agrega un tema (o lo actualiza si ya existe)", comando_agregar)
    # Nombre del tema (obligatorio).
    p.add_argument("nombre", help='nombre del tema, entre comillas si tiene espacios: "Historia del arte"')
    # Prioridad del 1 al 5 (por defecto 3).
    p.add_argument("-p", "--prioridad", type=int, default=3, choices=range(1, 6), metavar="1-5",
                   help="1 = baja, 5 = alta (por defecto 3)")
    # Minutos por semana (obligatorio).
    p.add_argument("-m", "--minutos", type=int, required=True, help="minutos por semana para este tema")

    # --- temas ---
    # Comando para listar los temas.
    nuevo_comando(sub, "temas", "muestra los temas guardados", comando_temas)

    # --- quitar ---
    # Comando para quitar un tema.
    p = nuevo_comando(sub, "quitar", "quita un tema", comando_quitar)
    # Nombre del tema a quitar.
    p.add_argument("nombre", help="nombre del tema (no importan mayúsculas ni tildes)")

    # --- generar ---
    # Comando para generar el plan.
    p = nuevo_comando(sub, "generar", "reparte los temas en sesiones cortas para los próximos 7 días", comando_generar)
    # Fecha de inicio opcional.
    p.add_argument("--desde", type=leer_fecha, metavar="AAAA-MM-DD",
                   help="primer día del plan (por defecto hoy, o mañana si ya pasó tu hora de inicio)")

    # --- hoy ---
    # Comando para ver las sesiones del día.
    p = nuevo_comando(sub, "hoy", "muestra las sesiones de hoy según el plan guardado", comando_hoy)
    # Otra fecha opcional.
    p.add_argument("--fecha", type=leer_fecha, metavar="AAAA-MM-DD", help="ver otro día en lugar de hoy")

    # --- subir ---
    # Comando para crear las sesiones en Google Calendar.
    p = nuevo_comando(sub, "subir", "crea las sesiones del plan en Google Calendar (con aviso al teléfono)", comando_subir)
    # Opción para reemplazar sesiones ya subidas en esas fechas.
    p.add_argument("--reemplazar", action="store_true",
                   help="si ya subiste sesiones en esas fechas, las borra y sube las nuevas")
    # Opción para probar sin conectar.
    p.add_argument("--simular", action="store_true", help="muestra lo que se crearía, sin conectar con Google")

    # --- limpiar ---
    # Comando para borrar del calendario las sesiones de esta app.
    p = nuevo_comando(sub, "limpiar", "borra del calendario las sesiones que creó esta app (solo esas)", comando_limpiar)
    # Fecha de inicio opcional.
    p.add_argument("--desde", type=leer_fecha, metavar="AAAA-MM-DD", help="primer día (por defecto, el del plan guardado)")
    # Fecha de fin opcional.
    p.add_argument("--hasta", type=leer_fecha, metavar="AAAA-MM-DD", help="último día (por defecto, 6 días después de --desde)")

    # --- config ---
    # Comando para ver la configuración.
    nuevo_comando(sub, "config", "muestra la configuración actual (config.json)", comando_config)

    # Devolvemos el parser listo.
    return parser


def main(argv=None):
    """Punto de entrada: lee el comando y lo ejecuta. Devuelve 0 si todo fue bien."""
    # Creamos el parser.
    parser = crear_parser()
    # Leemos lo que escribió el usuario (argv=None significa "lo de la terminal").
    args = parser.parse_args(argv)
    # Si no escribió ningún comando, mostramos la ayuda.
    if not hasattr(args, "funcion"):
        # Ayuda completa.
        parser.print_help()
        # Terminamos sin error.
        return 0
    # Ejecutamos el comando, atrapando los errores "conocidos".
    try:
        # Llamamos a la función del comando.
        args.funcion(args)
    # Errores pensados para el usuario: mostramos solo el mensaje.
    except almacen.ErrorPlanificador as error:
        # Lo escribimos en la salida de errores.
        print(f"Error: {error}", file=sys.stderr)
        # Código 1 = terminó con error.
        return 1
    # Si el usuario pulsa Ctrl+C, salimos con calma.
    except KeyboardInterrupt:
        # Mensaje breve.
        print("\nCancelado.", file=sys.stderr)
        # Código habitual para "interrumpido".
        return 130
    # Todo fue bien.
    return 0


# Esto solo se ejecuta si lanzas el archivo directamente (no si otro módulo lo importa).
if __name__ == "__main__":
    # Ejecutamos main() y usamos su resultado como código de salida.
    sys.exit(main())

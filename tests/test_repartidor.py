"""Pruebas del repartidor de sesiones (no necesitan internet ni cuenta de Google)."""

# copy duplica la configuración por defecto para modificarla en cada prueba.
import copy
# sys nos deja añadir la carpeta de la app a la ruta de búsqueda de módulos.
import sys
# unittest es el sistema de pruebas que trae Python.
import unittest
# Herramientas de fechas.
from datetime import date, datetime, timedelta
# Path para calcular la carpeta de la app.
from pathlib import Path

# Añadimos la carpeta de la app (la de arriba de "tests") para poder importar sus módulos.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Módulos de la app que vamos a probar.
import almacen  # noqa: E402
import repartidor  # noqa: E402

# Un lunes cualquiera para que las pruebas den siempre lo mismo.
LUNES = date(2026, 10, 26)


def config_base(**cambios):
    """Configuración por defecto con los cambios indicados."""
    # Copiamos la configuración por defecto.
    config = copy.deepcopy(almacen.CONFIG_POR_DEFECTO)
    # Aplicamos los cambios.
    config.update(cambios)
    # La devolvemos.
    return config


def tema(nombre, prioridad, minutos):
    """Atajo para crear un tema."""
    # Mismo formato que guarda la app.
    return {"nombre": nombre, "prioridad": prioridad, "minutos_semana": minutos}


class PartirEnBloques(unittest.TestCase):
    """Pruebas de cómo se trocean los minutos semanales."""

    def test_ejemplos_del_docstring(self):
        # Cabe justo: 4 sesiones de 25.
        self.assertEqual(repartidor.partir_en_bloques(100, 25, 10), [25, 25, 25, 25])
        # Sobran 10: una sesión corta más.
        self.assertEqual(repartidor.partir_en_bloques(110, 25, 10), [25, 25, 25, 25, 10])
        # Sobran 5: se suman a la última.
        self.assertEqual(repartidor.partir_en_bloques(105, 25, 10), [25, 25, 25, 30])
        # Menos que una sesión: una única sesión corta.
        self.assertEqual(repartidor.partir_en_bloques(5, 25, 10), [5])
        # Cero minutos: ninguna sesión.
        self.assertEqual(repartidor.partir_en_bloques(0, 25, 10), [])


class GenerarPlan(unittest.TestCase):
    """Pruebas del plan semanal completo."""

    def test_reparte_todos_los_minutos_si_caben(self):
        # Tres temas que en total caben de sobra en la semana.
        temas = [tema("Matemáticas", 5, 120), tema("Inglés", 3, 75), tema("Historia", 1, 60)]
        # Generamos el plan.
        plan = repartidor.generar_plan(temas, config_base(), LUNES)
        # No debe quedar nada fuera.
        self.assertEqual(plan["sin_lugar"], [])
        # Cada tema recibe exactamente sus minutos.
        for t in temas:
            # Suma de minutos de ese tema.
            total = sum(s.minutos for s in plan["sesiones"] if s.tema == t["nombre"])
            # Debe coincidir con lo pedido.
            self.assertEqual(total, t["minutos_semana"], t["nombre"])

    def test_no_pasa_del_maximo_diario(self):
        # Pedimos mucho más de lo que cabe (6 días × 120 min = 720).
        temas = [tema("A", 5, 500), tema("B", 3, 500)]
        # Generamos el plan.
        plan = repartidor.generar_plan(temas, config_base(), LUNES)
        # Revisamos cada día de la semana.
        for i in range(7):
            # Minutos de ese día.
            minutos = sum(s.minutos for s in repartidor.sesiones_del_dia(plan, LUNES + timedelta(days=i)))
            # No deben pasar de 120.
            self.assertLessEqual(minutos, 120)
        # Lo que no cupo queda apuntado.
        self.assertTrue(plan["sin_lugar"])

    def test_sesiones_no_se_solapan_y_respetan_descansos(self):
        # Varios temas para llenar los días.
        temas = [tema("A", 5, 200), tema("B", 4, 150), tema("C", 2, 100)]
        # Generamos el plan.
        plan = repartidor.generar_plan(temas, config_base(), LUNES)
        # Comparamos cada sesión con la siguiente.
        for anterior, siguiente in zip(plan["sesiones"], plan["sesiones"][1:]):
            # Solo nos importan las del mismo día.
            if anterior.inicio.date() == siguiente.inicio.date():
                # Entre una y otra hay al menos el descanso corto (5 min).
                self.assertGreaterEqual(siguiente.inicio, anterior.fin + timedelta(minutes=5))

    def test_mismo_tema_en_dias_no_seguidos(self):
        # Un tema con 2 sesiones en una semana de 6 días de estudio.
        plan = repartidor.generar_plan([tema("Química", 3, 50)], config_base(), LUNES)
        # Fechas de sus dos sesiones.
        dias = [s.inicio.date() for s in plan["sesiones"]]
        # Son 2 sesiones.
        self.assertEqual(len(dias), 2)
        # Separadas al menos 2 días (por ejemplo, lunes y miércoles).
        self.assertGreaterEqual((dias[1] - dias[0]).days, 2)

    def test_prioridad_alta_va_primero_en_el_dia(self):
        # Solo se estudia el lunes.
        config = config_base(horario={"lunes": "18:00"}, maximo_minutos_por_dia=0)
        # Dos temas con distinta prioridad.
        plan = repartidor.generar_plan([tema("Baja", 1, 25), tema("Alta", 5, 25)], config, LUNES)
        # La primera sesión del día es la de prioridad alta.
        self.assertEqual(plan["sesiones"][0].tema, "Alta")
        # Y empieza a la hora de inicio.
        self.assertEqual(plan["sesiones"][0].inicio, datetime(2026, 10, 26, 18, 0))

    def test_no_repite_tema_seguido_si_puede(self):
        # Solo lunes y sin límite diario: todo cae el mismo día.
        config = config_base(horario={"lunes": "18:00"}, maximo_minutos_por_dia=0)
        # Dos temas con dos sesiones cada uno.
        plan = repartidor.generar_plan([tema("A", 5, 50), tema("B", 3, 50)], config, LUNES)
        # Se intercalan en vez de ir A A B B.
        self.assertEqual([s.tema for s in plan["sesiones"]], ["A", "B", "A", "B"])

    def test_si_no_entra_queda_fuera_la_menor_prioridad(self):
        # Solo lunes con 50 minutos como máximo.
        config = config_base(horario={"lunes": "18:00"}, maximo_minutos_por_dia=50)
        # Piden 75 minutos en total.
        plan = repartidor.generar_plan([tema("Importante", 5, 50), tema("Opcional", 1, 25)], config, LUNES)
        # Entra todo lo importante.
        self.assertEqual({s.tema for s in plan["sesiones"]}, {"Importante"})
        # Queda fuera lo opcional.
        self.assertEqual([s.tema for s in plan["sin_lugar"]], ["Opcional"])

    def test_descanso_largo_cada_cuatro_sesiones(self):
        # Solo lunes, sin límite, descanso corto 5 y largo 15 cada 4.
        config = config_base(horario={"lunes": "18:00"}, maximo_minutos_por_dia=0)
        # Un tema con 5 sesiones de 25.
        plan = repartidor.generar_plan([tema("A", 3, 125)], config, LUNES)
        # Horas de inicio de cada sesión.
        horas = [f"{s.inicio:%H:%M}" for s in plan["sesiones"]]
        # 18:00, +30, +30, +30 y, tras la cuarta (termina 19:55), 15 min de descanso: 20:10.
        self.assertEqual(horas, ["18:00", "18:30", "19:00", "19:30", "20:10"])

    def test_numeracion_por_tema(self):
        # Un tema con 4 sesiones.
        plan = repartidor.generar_plan([tema("A", 3, 100)], config_base(), LUNES)
        # Números en orden cronológico.
        self.assertEqual([s.numero for s in plan["sesiones"]], [1, 2, 3, 4])
        # Todas saben que son 4 en total.
        self.assertTrue(all(s.total == 4 for s in plan["sesiones"]))

    def test_plan_se_guarda_y_se_lee_igual(self):
        # Plan cualquiera.
        plan = repartidor.generar_plan([tema("A", 3, 60), tema("B", 2, 1000)], config_base(), LUNES)
        # Lo convertimos a diccionario y de vuelta.
        recuperado = repartidor.plan_desde_dict(repartidor.plan_a_dict(plan))
        # Debe quedar idéntico.
        self.assertEqual(recuperado, plan)

    def test_recuperacion_solo_ocupa_el_sitio_que_sobra(self):
        # Solo lunes, con 75 minutos como máximo.
        config = config_base(horario={"lunes": "18:00"}, maximo_minutos_por_dia=75)
        # Un tema de 50 min y 50 min para recuperar: solo cabe una recuperación de 25.
        plan = repartidor.generar_plan([tema("A", 3, 50)], config, LUNES, recuperar={"A": 50})
        # Dos sesiones normales y una de recuperación (al final).
        self.assertEqual([s.recuperacion for s in plan["sesiones"]], [False, False, True])
        # Lo que no cupo no cuenta como "sin lugar"...
        self.assertEqual(plan["sin_lugar"], [])
        # ...pero se explica en las notas.
        self.assertTrue(any("No cupieron 25 min" in nota for nota in plan["notas"]))

    def test_fecha_limite_prefiere_los_dias_anteriores(self):
        # Un tema con 2 sesiones y fecha límite el miércoles.
        plan = repartidor.generar_plan([tema("A", 3, 50)], config_base(), LUNES,
                                       limites={"A": LUNES + timedelta(days=2)})
        # Las dos van lunes y martes.
        self.assertEqual([s.inicio.date() for s in plan["sesiones"]], [LUNES, LUNES + timedelta(days=1)])

    def test_plan_con_recuperacion_y_notas_se_guarda_igual(self):
        # Plan con recuperación y una nota.
        plan = repartidor.generar_plan([tema("A", 3, 50)], config_base(), LUNES, recuperar={"A": 25}, notas=["Hola"])
        # Ida y vuelta.
        self.assertEqual(repartidor.plan_desde_dict(repartidor.plan_a_dict(plan)), plan)

    def test_plan_danado_da_error_claro(self):
        # Le falta la fecha de inicio.
        with self.assertRaisesRegex(almacen.ErrorPlanificador, "dañado"):
            # Intento de lectura.
            repartidor.plan_desde_dict({"hasta": "2026-11-01", "sesiones": []})
        # Una sesión sin hora.
        with self.assertRaisesRegex(almacen.ErrorPlanificador, "dañado"):
            # Intento de lectura.
            repartidor.plan_desde_dict(
                {"desde": "2026-10-26", "hasta": "2026-11-01", "sesiones": [{"tema": "A", "prioridad": 3, "minutos": 25}]}
            )
        # Una lista en lugar de un objeto.
        with self.assertRaisesRegex(almacen.ErrorPlanificador, "dañado"):
            # Intento de lectura.
            repartidor.plan_desde_dict([])

    def test_no_pasa_de_medianoche(self):
        # Se empieza a las 23:00 y sin límite diario: solo caben 2 sesiones de 25 antes de las 00:00.
        config = config_base(horario={"lunes": "23:00"}, maximo_minutos_por_dia=0)
        # Pedimos 150 minutos (6 sesiones).
        plan = repartidor.generar_plan([tema("A", 3, 150)], config, LUNES)
        # Entran 23:00-23:25 y 23:30-23:55.
        self.assertEqual([f"{s.inicio:%H:%M}-{s.fin:%H:%M}" for s in plan["sesiones"]], ["23:00-23:25", "23:30-23:55"])
        # Las otras 4 quedan fuera (y no pasan al martes de madrugada).
        self.assertEqual(len(plan["sin_lugar"]), 4)

    def test_duracion_con_descansos_coincide_con_los_horarios(self):
        # Solo lunes y sin límite, para que todo caiga el mismo día.
        config = config_base(horario={"lunes": "18:00"}, maximo_minutos_por_dia=0)
        # Varios temas, con sesiones de distinta duración.
        plan = repartidor.generar_plan([tema("A", 5, 110), tema("B", 3, 85), tema("C", 1, 40)], config, LUNES)
        # Lo que calcula la función...
        calculado = repartidor.duracion_con_descansos([s.minutos for s in plan["sesiones"]], config)
        # ...debe ser igual a lo que hay de verdad entre el inicio de la primera y el fin de la última.
        real = (plan["sesiones"][-1].fin - plan["sesiones"][0].inicio).total_seconds() / 60
        # Comprobamos.
        self.assertEqual(calculado, real)


class PrimerDiaPorDefecto(unittest.TestCase):
    """Pruebas de qué día empieza el plan si no se indica --desde."""

    def test_hoy_si_todavia_no_es_la_hora(self):
        # Lunes a las 17:00, se empieza a las 18:00: empieza hoy.
        ahora = datetime(2026, 10, 26, 17, 0)
        # Comprobamos.
        self.assertEqual(repartidor.primer_dia_por_defecto({"lunes": "18:00"}, ahora), LUNES)

    def test_manana_si_ya_paso_la_hora(self):
        # Lunes a las 19:00, la hora de inicio ya pasó: empieza el martes.
        ahora = datetime(2026, 10, 26, 19, 0)
        # Comprobamos.
        self.assertEqual(repartidor.primer_dia_por_defecto({"lunes": "18:00"}, ahora), LUNES + timedelta(days=1))

    def test_hoy_si_hoy_no_se_estudia(self):
        # Domingo por la noche, el domingo no está en el horario: empieza hoy (no hay sesiones hoy igualmente).
        ahora = datetime(2026, 11, 1, 22, 0)
        # Comprobamos.
        self.assertEqual(repartidor.primer_dia_por_defecto({"lunes": "18:00"}, ahora), date(2026, 11, 1))


# Permite ejecutar este archivo directamente.
if __name__ == "__main__":
    # Lanza las pruebas.
    unittest.main()

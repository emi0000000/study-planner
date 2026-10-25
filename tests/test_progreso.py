"""Pruebas de lo hecho, las metas y el plan adaptado (no necesitan internet)."""

# copy duplica la configuración por defecto para modificarla.
import copy
# sys para añadir la carpeta de la app a la ruta de módulos.
import sys
# unittest es el sistema de pruebas de Python.
import unittest
# Herramientas de fechas.
from datetime import date, datetime, timedelta
# Path para manejar rutas.
from pathlib import Path

# Añadimos la carpeta de la app para poder importar sus módulos.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Módulos de la app.
import almacen  # noqa: E402
import progreso  # noqa: E402
import repartidor  # noqa: E402

# Un lunes cualquiera para que las pruebas den siempre lo mismo.
LUNES = date(2026, 10, 19)


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


def registro_vacio():
    """Registro sin nada marcado."""
    # Mismo formato que guarda la app.
    return {"sesiones": {}, "perdonado": {}}


class MarcarSesiones(unittest.TestCase):
    """Marcar sesiones y calcular lo pendiente."""

    def setUp(self):
        # Plan de una semana con Química (4 sesiones) y Matemáticas (2).
        self.temas = [tema("Química", 3, 100), tema("Matemáticas", 5, 50)]
        # Plan.
        self.plan = repartidor.generar_plan(self.temas, config_base(), LUNES)
        # Registro vacío.
        self.registro = registro_vacio()
        # Momento en que se marca (el domingo de esa semana).
        self.ahora = datetime(2026, 10, 25, 20, 0)

    def quimica(self):
        """Sesiones de Química del plan, en orden."""
        # Solo las de Química.
        return [s for s in self.plan["sesiones"] if s.tema == "Química"]

    def test_marcar_y_desmarcar(self):
        # Primera sesión de Química.
        sesion = self.quimica()[0]
        # Al principio no está marcada.
        self.assertIsNone(progreso.estado_de(self.registro, sesion))
        # La marcamos como hecha.
        progreso.marcar(self.registro, sesion, "hecha", self.ahora)
        # Ahora lo está.
        self.assertEqual(progreso.estado_de(self.registro, sesion), "hecha")
        # Le quitamos la marca.
        progreso.marcar(self.registro, sesion, None)
        # Vuelve a estar sin marcar.
        self.assertIsNone(progreso.estado_de(self.registro, sesion))
        # Un estado inventado da error.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento.
            progreso.marcar(self.registro, sesion, "a medias")

    def test_marcar_por_tema_sin_importar_tildes(self):
        # Día de la primera sesión de Química.
        dia = self.quimica()[0].inicio.date()
        # Marcamos escribiendo el tema sin tilde.
        sesion = progreso.marcar_por_tema(self.registro, self.plan, dia, "quimica", "no_hecha", ahora=self.ahora)
        # Se marcó la de Química.
        self.assertEqual(sesion.tema, "Química")
        # Un tema que ese día no tiene sesiones da error.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento.
            progreso.marcar_por_tema(self.registro, self.plan, dia, "Historia", "hecha")

    def test_lo_no_hecho_queda_pendiente_y_se_recupera(self):
        # Dos sesiones de Química no hechas (50 min).
        for sesion in self.quimica()[:2]:
            # Marcamos.
            progreso.marcar(self.registro, sesion, "no_hecha", self.ahora)
        # Quedan 50 min pendientes de Química.
        self.assertEqual(progreso.pendiente_por_tema(self.registro, self.temas, self.ahora.date()), {"Química": 50})
        # Una recuperación hecha resta 25.
        recuperacion = repartidor.Sesion("Química", 3, 25, datetime(2026, 10, 25, 10, 0), datetime(2026, 10, 25, 10, 25),
                                         recuperacion=True)
        # La marcamos.
        progreso.marcar(self.registro, recuperacion, "hecha", self.ahora)
        # Quedan 25.
        self.assertEqual(progreso.pendiente_por_tema(self.registro, self.temas, self.ahora.date()), {"Química": 25})
        # Si se olvida lo pendiente, ya no queda nada.
        progreso.olvidar_pendiente(self.registro, "Química", self.ahora + timedelta(minutes=1))
        # Nada pendiente.
        self.assertEqual(progreso.pendiente_por_tema(self.registro, self.temas, self.ahora.date()), {})

    def test_lo_pendiente_nunca_pasa_de_los_minutos_semanales(self):
        # Marcamos como no hechas sesiones de Matemáticas de dos semanas seguidas (100 min).
        for semana in (0, 7):
            # Plan de esa semana.
            plan = repartidor.generar_plan(self.temas, config_base(), LUNES - timedelta(days=semana))
            # Sus sesiones de Matemáticas.
            for sesion in (s for s in plan["sesiones"] if s.tema == "Matemáticas"):
                # Marcamos.
                progreso.marcar(self.registro, sesion, "no_hecha", self.ahora)
        # Matemáticas pide 50 min por semana: como mucho se recuperan 50.
        self.assertEqual(progreso.pendiente_por_tema(self.registro, self.temas, self.ahora.date())["Matemáticas"], 50)

    def test_resumen_y_racha(self):
        # Sesiones ordenadas por fecha.
        sesiones = sorted(self.plan["sesiones"], key=lambda s: s.inicio)
        # Marcamos como hechas todas las del viernes y el sábado; la primera del lunes, no hecha.
        for sesion in sesiones:
            # Viernes (4) o sábado (5).
            if sesion.inicio.weekday() in (4, 5):
                # Hecha.
                progreso.marcar(self.registro, sesion, "hecha", self.ahora)
        # Primera sesión del lunes.
        progreso.marcar(self.registro, sesiones[0], "no_hecha", self.ahora)
        # Resumen el domingo por la noche.
        datos = progreso.resumen(self.registro, self.plan, self.temas, self.ahora)
        # Racha: sábado y viernes (hoy domingo todavía no hay nada hecho).
        self.assertEqual(datos["racha"], 2)
        # Totales.
        self.assertEqual(datos["hechas"] + datos["no_hechas"], 1 + sum(1 for s in sesiones if s.inicio.weekday() in (4, 5)))
        # Las sesiones pasadas sin marcar se cuentan.
        sin_marcar = sum(fila["sin_marcar"] for fila in datos["temas"])
        # Son todas menos las marcadas.
        self.assertEqual(sin_marcar, len(sesiones) - datos["hechas"] - datos["no_hechas"])
        # El primer tema de la lista es el de mayor prioridad.
        self.assertEqual(datos["temas"][0]["tema"], "Matemáticas")


class Metas(unittest.TestCase):
    """Agregar, cumplir y quitar metas."""

    def test_agregar_cumplir_y_quitar(self):
        # Lista vacía.
        metas = []
        # Meta con tema (escrito sin tilde) y fecha.
        meta = progreso.agregar_meta(metas, "Examen de Química", "quimica", "2026-10-29", [tema("Química", 3, 100)])
        # Se guardó con el nombre exacto del tema y número 1.
        self.assertEqual((meta["id"], meta["tema"], meta["fecha"]), (1, "Química", "2026-10-29"))
        # Otra meta sin tema ni fecha: número 2.
        self.assertEqual(progreso.agregar_meta(metas, "Leer más")["id"], 2)
        # La marcamos como cumplida.
        progreso.cumplir_meta(metas, 1)
        # Lo está.
        self.assertTrue(metas[0]["cumplida"])
        # La quitamos.
        progreso.quitar_meta(metas, 1)
        # Solo queda la otra.
        self.assertEqual([m["id"] for m in metas], [2])

    def test_datos_invalidos(self):
        # Texto vacío.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento.
            progreso.agregar_meta([], "   ")
        # Tema que no existe.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento.
            progreso.agregar_meta([], "Examen", "Física", None, [tema("Química", 3, 100)])
        # Fecha mal escrita.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento.
            progreso.agregar_meta([], "Examen", None, "29/10/2026")
        # Número que no existe.
        with self.assertRaises(almacen.ErrorPlanificador):
            # Intento.
            progreso.quitar_meta([], 7)


class PlanAdaptado(unittest.TestCase):
    """El plan cambia según lo no hecho y las metas."""

    def setUp(self):
        # Temas: Química con prioridad baja.
        self.temas = [tema("Matemáticas", 5, 100), tema("Química", 2, 100), tema("Inglés", 3, 50)]
        # Configuración por defecto.
        self.config = config_base()
        # Momento: domingo por la noche, antes del plan del lunes 26.
        self.ahora = datetime(2026, 10, 25, 20, 0)
        # Primer día del plan nuevo.
        self.desde = date(2026, 10, 26)

    def test_sin_nada_que_adaptar_es_el_plan_normal(self):
        # Plan adaptado sin registro ni metas.
        plan = progreso.planificar(self.temas, self.config, registro_vacio(), [], self.desde, self.ahora)
        # Igual que el plan normal.
        self.assertEqual(plan, repartidor.generar_plan(self.temas, self.config, self.desde))
        # Sin notas.
        self.assertEqual(plan["notas"], [])

    def test_recupera_lo_no_hecho_despues_de_lo_normal(self):
        # Registro con dos sesiones de Química no hechas la semana anterior.
        registro = registro_vacio()
        # Plan de la semana anterior.
        anterior = repartidor.generar_plan(self.temas, self.config, LUNES)
        # Marcamos dos de Química.
        for sesion in [s for s in anterior["sesiones"] if s.tema == "Química"][:2]:
            # No hecha.
            progreso.marcar(registro, sesion, "no_hecha", self.ahora)
        # Plan adaptado.
        plan = progreso.planificar(self.temas, self.config, registro, [], self.desde, self.ahora)
        # Sesiones de recuperación.
        recuperaciones = [s for s in plan["sesiones"] if s.recuperacion]
        # Son 50 min de Química.
        self.assertEqual(([s.tema for s in recuperaciones], sum(s.minutos for s in recuperaciones)),
                         (["Química", "Química"], 50))
        # Lo normal sigue entero.
        self.assertEqual(sum(s.minutos for s in plan["sesiones"] if not s.recuperacion), 250)
        # Hay una nota que lo explica.
        self.assertTrue(any("recuperar" in nota for nota in plan["notas"]))
        # Con la opción desactivada no se recupera nada.
        sin_recuperar = progreso.planificar(self.temas, config_base(recuperar_no_hechas=False), registro, [],
                                            self.desde, self.ahora)
        # Ninguna recuperación.
        self.assertFalse(any(s.recuperacion for s in sin_recuperar["sesiones"]))

    def test_una_meta_cercana_sube_la_prioridad_y_adelanta_las_sesiones(self):
        # Examen de Química el jueves 29.
        metas = [{"id": 1, "texto": "Examen de Química", "tema": "Química", "fecha": "2026-10-29", "cumplida": False}]
        # Plan adaptado.
        plan = progreso.planificar(self.temas, self.config, registro_vacio(), metas, self.desde, self.ahora)
        # Sesiones de Química.
        quimica = [s for s in plan["sesiones"] if s.tema == "Química"]
        # Todas antes del jueves.
        self.assertTrue(all(s.inicio.date() < date(2026, 10, 29) for s in quimica))
        # Con prioridad 5 esta semana.
        self.assertTrue(all(s.prioridad == 5 for s in quimica))
        # Hay una nota que lo explica.
        self.assertTrue(any("Examen de Química" in nota for nota in plan["notas"]))

    def test_metas_lejanas_cumplidas_o_pasadas_no_cambian_nada(self):
        # Una lejana, una cumplida y una pasada.
        metas = [
            {"id": 1, "texto": "Lejana", "tema": "Química", "fecha": "2026-12-20", "cumplida": False},
            {"id": 2, "texto": "Cumplida", "tema": "Química", "fecha": "2026-10-28", "cumplida": True},
            {"id": 3, "texto": "Pasada", "tema": "Química", "fecha": "2026-10-20", "cumplida": False},
        ]
        # Plan adaptado.
        plan = progreso.planificar(self.temas, self.config, registro_vacio(), metas, self.desde, self.ahora)
        # Igual que el normal.
        self.assertEqual(plan["sesiones"], repartidor.generar_plan(self.temas, self.config, self.desde)["sesiones"])


# Permite ejecutar este archivo directamente.
if __name__ == "__main__":
    # Lanza las pruebas.
    unittest.main()

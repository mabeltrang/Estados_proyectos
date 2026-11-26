from config.constantes import Hito
from config.flujos import FLUJOS, nombres_etapas, validar_flujos

ETAPAS_ESPERADAS = {
    "CORPOCESAR": 8, "CARSUCRE": 8, "CRA": 9, "CORPAMAG": 8, "CORPOGUAJIRA": 7, "CORTOLIMA": 6,
    "CORPOCALDAS": 7, "CDMB": 8, "CAS": 7, "CSB": 7, "CORPOMOJANA": 8, "CVS": 7, "CORPOBOYACA": 6,
}


def test_configuracion_valida():
    assert validar_flujos() == []


def test_numero_de_etapas_por_car():
    assert {car: len(f) for car, f in FLUJOS.items()} == ETAPAS_ESPERADAS


def test_acta_solo_en_corpocesar():
    con_acta = [car for car, f in FLUJOS.items() if any(e.nombre == "Acta" for e in f)]
    assert con_acta == ["CORPOCESAR"]


def test_desplegable_solo_muestra_etapas_de_su_car():
    assert nombres_etapas("CORTOLIMA") == ["Inventario", "Informes", "Pago evaluación", "Auto", "Visita", "Resolución"]
    assert "Acta" not in nombres_etapas("CARSUCRE")
    assert nombres_etapas("NO_EXISTE") == []


def test_todas_terminan_en_resolucion():
    assert all(f[-1].hito == Hito.RESOLUCION for f in FLUJOS.values())


def test_nombre_de_car_con_tilde():
    from config.flujos import obtener_flujo
    assert obtener_flujo("CORPOBOYACÁ") is FLUJOS["CORPOBOYACA"]

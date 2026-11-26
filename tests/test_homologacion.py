from config.flujos import FLUJOS, avance
from config.homologacion import ESTADOS_UNERGY, estado_canonico, estado_tsf, etapa_desde_tsf, homologar


def test_toda_etapa_de_todo_flujo_tiene_estado_tsf_valido():
    for car, flujo in FLUJOS.items():
        for etapa in flujo:
            assert estado_tsf(car, etapa.nombre) in ESTADOS_UNERGY, (car, etapa.nombre)


def test_ejemplos():
    assert estado_tsf("CORPOCESAR", "Inventario") == "Programado"
    assert estado_tsf("CORPOCESAR", "Informes") == "Por radicar"
    assert estado_tsf("CORPOCESAR", "Llega auto") == "Solicitud radicada"
    assert estado_tsf("CARSUCRE", "Pago tasa de aprovechamiento") == "Liquidación"
    assert estado_tsf("CORPOCESAR", "Acta") == "Visita"
    assert estado_tsf("CAS", "Resolución") == "Solicitud aprobada"
    assert estado_tsf("CAS", "") == ""


def test_reconoce_estados_tsf():
    assert estado_canonico("respuesta a requerimiento") == "Respuesta a requerimientos"
    assert estado_canonico("Licencia de aprovechamiento forestal") is None


def test_avance():
    assert avance("CORPOCESAR", "Inventario") == 0
    assert avance("CORPOCESAR", "Resolución") == 1
    assert avance("CORTOLIMA", "Auto") == 3 / 5
    assert avance("CORPOCESAR", None) is None


def test_etapa_desde_tsf_solo_si_es_clara():
    assert etapa_desde_tsf("CORPOCESAR", "Programado") == "Inventario"
    assert etapa_desde_tsf("CDMB", "Por radicar") == "Informes"
    assert etapa_desde_tsf("CAS", "Solicitud aprobada") == "Resolución"
    assert etapa_desde_tsf("CARSUCRE", "Visita") == "Visita técnica"
    assert etapa_desde_tsf("CVS", "Liquidación") == "Liquidación servicios"
    assert etapa_desde_tsf("CARSUCRE", "Liquidación") is None       # evaluación o tasa
    assert etapa_desde_tsf("CORPOCESAR", "Solicitud radicada") is None  # radicado o auto
    assert etapa_desde_tsf("CORPOCESAR", "Visita") is None           # visita o acta
    assert etapa_desde_tsf("CORPOCESAR", "Respuesta a requerimientos") is None
    assert etapa_desde_tsf("CORPOCESAR", "Licencia de aprovechamiento forestal") is None
    assert etapa_desde_tsf(None, "Programado") is None


def test_homologar_da_rango_de_avance_cuando_hay_varias():
    h = homologar("CORPOCESAR", "Solicitud radicada")
    assert h.etapas == ("Radicado", "Llega auto") and not h.clara
    assert round(h.avance_min * 100) == 29 and round(h.avance_max * 100) == 43
    h = homologar("CORPOCESAR", "Programado")
    assert h.clara and h.avance_min == 0
    assert homologar("CORPOCESAR", "Requerimientos").etapas == ()

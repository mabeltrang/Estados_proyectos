from config.flujos import FLUJOS
from config.homologacion import ESTADOS_UNERGY, POR_CAR, homologar


def test_radicada_va_a_la_etapa_de_radicado_de_cada_car():
    assert homologar("CORPOCESAR", "Solicitud radicada").etapa == "Radicado"
    assert homologar("CVS", "Solicitud radicada").etapa == "Radicación"
    assert homologar("CRA", "solicitud RADICADA").etapa == "Radicación"
    assert homologar("CORTOLIMA", "Solicitud radicada").etapa is None  # su flujo no tiene radicado


def test_otras_equivalencias():
    assert homologar("CARSUCRE", "Visita").etapa == "Visita técnica"
    assert homologar("CAS", "Solicitud aprobada").etapa == "Resolución"
    assert homologar("CDMB", "Por radicar").etapa == "Informes"
    assert homologar("CVS", "Liquidacion").etapa == "Liquidación servicios"
    assert homologar("CORPOCESAR", "Liquidación").etapa is None


def test_estados_sin_equivalencia_dan_aviso():
    h = homologar("CORPOCESAR", "Respuesta a requerimiento")
    assert h.estado == "Respuesta a requerimientos" and h.etapa is None and h.nota
    assert homologar("CORPOCESAR", "Algo raro").estado == ""
    assert homologar("CORPOCESAR", "").nota == ""


def test_todos_los_estados_estan_clasificados_y_las_etapas_existen():
    for estado in ESTADOS_UNERGY:
        assert homologar("CORPOCESAR", estado).estado == estado
    for estado, por_car in POR_CAR.items():
        for car, etapa in por_car.items():
            assert etapa in [e.nombre for e in FLUJOS[car]], (estado, car)

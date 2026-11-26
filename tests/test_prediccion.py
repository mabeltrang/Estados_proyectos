from datetime import date, timedelta

import pandas as pd
import pytest

from config.constantes import EstadoPrediccion, FuentePrediccion, Semaforo, UnidadDias
from core.estadisticas import BaseTiempos
from core.prediccion import predecir, validar_fechas

HOY = date(2026, 11, 26)
CAL = UnidadDias.CALENDARIO


@pytest.fixture(scope="module")
def base():
    filas = []
    inicio = pd.Timestamp("2024-01-01")
    for d_auto, d_res in zip([10, 20, 30, 40, 50], [100, 120, 140, 160, 180]):
        auto = inicio + pd.Timedelta(days=d_auto)
        filas.append({"car": "CORPOCESAR", "solicitud_liquidacion": pd.NaT, "radicado": inicio, "auto": auto,
                      "visita": pd.NaT, "resolucion": auto + pd.Timedelta(days=d_res), "hitos_dudosos": ""})
    return BaseTiempos(pd.DataFrame(filas), CAL)


def p(base, etapa, fechas, car="CORPOCESAR"):
    return predecir(car, etapa, fechas, HOY, base, 5, CAL)


def hace(dias):
    return HOY - timedelta(days=dias)


def test_verde_y_cuenta_regresiva(base):
    r = p(base, "Radicado", {"Radicado": hace(15)})
    assert r.estado == EstadoPrediccion.OK
    assert r.semaforo == Semaforo.VERDE
    assert r.dias_restantes == 15
    assert r.fecha_siguiente_hito == hace(15) + timedelta(days=30)
    assert r.fuente_tramo == FuentePrediccion.PROPIO
    assert r.siguiente_etapa == "Llega auto"


@pytest.mark.parametrize("dias,esperado", [(20, Semaforo.VERDE), (25, Semaforo.AMARILLO), (35, Semaforo.NARANJA), (41, Semaforo.ROJO)])
def test_umbrales_semaforo(base, dias, esperado):
    assert p(base, "Radicado", {"Radicado": hace(dias)}).semaforo == esperado


def test_retraso_respecto_a_mediana(base):
    r = p(base, "Radicado", {"Radicado": hace(60)})
    assert r.dias_restantes == -30
    assert r.semaforo == Semaforo.ROJO


def test_resolucion_descuenta_tiempo_transcurrido(base):
    # Desde el auto: 100..180 días. Lleva 110 → quedan 10, 30, 50, 70 → mediana 40.
    r = p(base, "Pago visita y publicación auto", {"Radicado": hace(140), "Llega auto": hace(110)})
    assert r.etapa_reloj == "Llega auto"
    assert r.etapa_objetivo == "Visita"
    assert r.semaforo == Semaforo.SIN_DATO  # no hay visitas en el histórico
    assert r.resolucion.probable == HOY + timedelta(days=40)
    assert r.fuente_resolucion == FuentePrediccion.PROPIO
    assert r.n_resolucion_condicional == 4


def test_resolucion_superada(base):
    r = p(base, "Visita", {"Llega auto": hace(400)})
    assert r.resolucion is None
    assert any("superó" in a for a in r.avisos)


def test_antes_de_hitos(base):
    assert p(base, "Inventario", {}).estado == EstadoPrediccion.ANTES_DE_HITOS


def test_falta_fecha(base):
    assert p(base, "Llega auto", {}).estado == EstadoPrediccion.FALTA_FECHA


def test_usa_hito_anterior_con_aviso(base):
    r = p(base, "Llega auto", {"Radicado": hace(30)})
    assert r.etapa_reloj == "Radicado"
    assert r.avisos


def test_resuelto(base):
    assert p(base, "Resolución", {"Resolución": hace(1)}).estado == EstadoPrediccion.RESUELTO


def test_referencia_general_para_car_sin_historico(base):
    r = p(base, "Radicación", {"Radicación": hace(15)}, car="CORPOGUAJIRA")
    assert r.fuente_tramo == FuentePrediccion.GENERAL


def test_avance_administrativo_no_depende_del_tiempo(base):
    a = p(base, "Radicado", {"Radicado": hace(5)})
    b = p(base, "Radicado", {"Radicado": hace(500)})
    assert a.avance_administrativo == b.avance_administrativo == pytest.approx(2 / 7)
    assert b.avance_temporal > a.avance_temporal


def test_sin_flujo(base):
    assert p(base, "Radicado", {}, car="CORANTIOQUIA").estado == EstadoPrediccion.SIN_FLUJO


def test_validar_fechas():
    errores = validar_fechas(
        "CORPOCESAR", "Llega auto",
        {"Radicado": date(2026, 3, 1), "Llega auto": date(2026, 2, 1), "Visita": date(2026, 4, 1),
         "Informes": HOY + timedelta(days=1)},
        HOY,
    )
    texto = " ".join(errores)
    assert "futura" in texto and "posterior a la etapa actual" in texto and "anterior a «Radicado»" in texto

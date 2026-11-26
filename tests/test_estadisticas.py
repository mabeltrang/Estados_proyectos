import numpy as np
import pandas as pd

from config.constantes import FuentePrediccion, Hito, UnidadDias
from core.estadisticas import BaseTiempos, resumir


def tramites(car, pares):
    filas = []
    for rad, auto in pares:
        filas.append({"car": car, "radicado": pd.Timestamp(rad), "auto": pd.Timestamp(auto) if auto else pd.NaT,
                      "solicitud_liquidacion": pd.NaT, "visita": pd.NaT, "resolucion": pd.NaT, "hitos_dudosos": ""})
    return pd.DataFrame(filas)


def test_resumir_percentiles():
    est = resumir(np.array([10, 20, 30, 40, 50], dtype=float))
    assert (est.n, est.minimo, est.p25, est.p50, est.p75, est.maximo) == (5, 10, 20, 30, 40, 50)


def test_resumir_vacio():
    assert resumir(np.array([])) is None


def test_duraciones_y_exclusion_de_negativos_y_dudosos():
    df = tramites("CORPOCESAR", [("2025-01-01", "2025-01-11"), ("2025-01-01", "2024-12-01"), ("2025-01-01", None)])
    df.loc[3] = {**df.loc[0].to_dict(), "auto": pd.Timestamp("2025-03-01"), "hitos_dudosos": "auto,radicado"}
    base = BaseTiempos(df, UnidadDias.CALENDARIO)
    assert list(base.valores("CORPOCESAR", Hito.RADICADO, Hito.AUTO)) == [10.0]


def test_dias_habiles():
    df = tramites("X", [("2025-01-06", "2025-01-13")])  # lunes a lunes
    assert list(BaseTiempos(df, UnidadDias.HABILES).valores("X", Hito.RADICADO, Hito.AUTO)) == [5.0]


def test_eleccion_de_fuente():
    pares = [("2025-01-01", f"2025-02-{d:02d}") for d in range(1, 7)]
    df = pd.concat([tramites("A", pares), tramites("B", pares[:2])], ignore_index=True)
    base = BaseTiempos(df, UnidadDias.CALENDARIO)
    assert base.muestra("A", Hito.RADICADO, Hito.AUTO, 5).fuente == FuentePrediccion.PROPIO
    assert base.muestra("B", Hito.RADICADO, Hito.AUTO, 5).fuente == FuentePrediccion.LIMITADO
    general = base.muestra("C", Hito.RADICADO, Hito.AUTO, 5)
    assert general.fuente == FuentePrediccion.GENERAL and general.n == 8
    assert base.muestra("C", Hito.RADICADO, Hito.AUTO, 50).fuente == FuentePrediccion.SIN_DATOS

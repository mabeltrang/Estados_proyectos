"""Tiempos históricos entre hitos, por CAR.

Solo se comparan hitos equivalentes (radicado, auto, visita, resolución...). Un tramo se calcula
únicamente con expedientes que tienen las dos fechas y que no estén marcadas como dudosas.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.constantes import NOMBRE_HITO, ORDEN_HITOS, Columna, FuentePrediccion, Hito, UnidadDias
from config.flujos import FLUJOS
from core.historico import COLUMNA_DUDOSOS


@dataclass(frozen=True)
class Estadistica:
    n: int
    minimo: float
    p25: float
    p50: float
    p75: float
    maximo: float


def resumir(valores: np.ndarray) -> Estadistica | None:
    if len(valores) == 0:
        return None
    p25, p50, p75 = np.percentile(valores, [25, 50, 75])
    return Estadistica(
        n=int(len(valores)),
        minimo=float(np.min(valores)),
        p25=float(p25),
        p50=float(p50),
        p75=float(p75),
        maximo=float(np.max(valores)),
    )


@dataclass(frozen=True)
class Muestra:
    valores: np.ndarray
    fuente: FuentePrediccion

    @property
    def n(self) -> int:
        return int(len(self.valores))


class BaseTiempos:
    """Duraciones (en días) de todos los tramos posibles entre hitos, calculadas una sola vez."""

    def __init__(self, tramites: pd.DataFrame, unidad: UnidadDias) -> None:
        self.unidad = unidad
        self._duraciones: dict[tuple[Hito, Hito], pd.DataFrame] = {}
        if tramites.empty:
            return
        dudosos = tramites.get(COLUMNA_DUDOSOS, pd.Series("", index=tramites.index)).fillna("")
        for i, desde in enumerate(ORDEN_HITOS):
            for hasta in ORDEN_HITOS[i + 1 :]:
                ok = (
                    tramites[desde.value].notna()
                    & tramites[hasta.value].notna()
                    & ~dudosos.str.contains(desde.value, regex=False)
                    & ~dudosos.str.contains(hasta.value, regex=False)
                )
                sub = tramites[ok]
                if sub.empty:
                    continue
                inicio = sub[desde.value].values.astype("datetime64[D]")
                fin = sub[hasta.value].values.astype("datetime64[D]")
                if unidad == UnidadDias.HABILES:
                    dias = np.busday_count(inicio, fin)
                else:
                    dias = (fin - inicio).astype(int)
                tabla = pd.DataFrame({"car": sub[Columna.CAR.value].values, "dias": dias})
                self._duraciones[(desde, hasta)] = tabla[tabla["dias"] >= 0]

    def valores(self, car: str, desde: Hito, hasta: Hito) -> np.ndarray:
        tabla = self._duraciones.get((desde, hasta))
        if tabla is None:
            return np.array([], dtype=float)
        return tabla.loc[tabla["car"] == car, "dias"].to_numpy(dtype=float)

    def valores_generales(self, desde: Hito, hasta: Hito) -> np.ndarray:
        tabla = self._duraciones.get((desde, hasta))
        if tabla is None:
            return np.array([], dtype=float)
        return tabla["dias"].to_numpy(dtype=float)

    def muestra(self, car: str, desde: Hito, hasta: Hito, min_antecedentes: int) -> Muestra:
        """Elige qué antecedentes usar: los de la CAR si hay suficientes, los pocos que tenga con
        advertencia, o la referencia general de otras CAR si la CAR no tiene ninguno."""
        propios = self.valores(car, desde, hasta)
        if len(propios) >= min_antecedentes:
            return Muestra(propios, FuentePrediccion.PROPIO)
        if len(propios) > 0:
            return Muestra(propios, FuentePrediccion.LIMITADO)
        generales = self.valores_generales(desde, hasta)
        if len(generales) >= min_antecedentes:
            return Muestra(generales, FuentePrediccion.GENERAL)
        return Muestra(np.array([], dtype=float), FuentePrediccion.SIN_DATOS)

    def tabla(self) -> pd.DataFrame:
        """Tabla interna de P25/P50/P75 por CAR y tramo (solo tramos que existen en el flujo de la CAR)."""
        filas: list[dict[str, object]] = []
        cars = sorted(set(FLUJOS) | {c for t in self._duraciones.values() for c in t["car"].unique()})
        for car in cars:
            flujo = FLUJOS.get(car)
            hitos_car = [e.hito for e in flujo if e.hito] if flujo else list(ORDEN_HITOS)
            for i, desde in enumerate(hitos_car):
                for hasta in hitos_car[i + 1 :]:
                    est = resumir(self.valores(car, desde, hasta))
                    if est is None:
                        continue
                    filas.append(
                        {
                            "CAR": car,
                            "Tramo": f"{NOMBRE_HITO[desde]} → {NOMBRE_HITO[hasta]}",
                            "Antecedentes": est.n,
                            "Mínimo": est.minimo,
                            "P25": est.p25,
                            "Mediana": est.p50,
                            "P75": est.p75,
                            "Máximo": est.maximo,
                        }
                    )
        return pd.DataFrame(filas)

"""Cuenta regresiva, semáforo y proyección de resolución de un proyecto.

Idea central
------------
1. El reloj corre desde el último HITO alcanzado que tenga fecha registrada (radicado, auto,
   visita...). Las etapas sin histórico (pagos, publicaciones, acta) no reinician el reloj.
2. Siguiente hito: se compara el tiempo transcurrido desde ese hito con los antecedentes del
   tramo hasta el próximo hito → semáforo y días restantes hasta la mediana.
3. Resolución: se usan los antecedentes del tramo "último hito → resolución", pero SOLO los
   expedientes que tardaron más de lo que este proyecto ya lleva esperando, y se les resta ese
   tiempo. Así no se suman otra vez etapas ya cumplidas ni se ignora el tiempo transcurrido.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from config.constantes import EstadoPrediccion, FuentePrediccion, Hito, Semaforo, UnidadDias
from config.flujos import Etapa, indice_etapa, obtener_flujo
from core.estadisticas import BaseTiempos, Estadistica, resumir
from core.fechas import dias_entre, sumar_dias


@dataclass(frozen=True)
class Intervalo:
    temprano: date
    probable: date
    tardio: date


@dataclass(frozen=True)
class Prediccion:
    estado: EstadoPrediccion
    mensaje: str = ""
    etapa_actual: str | None = None
    siguiente_etapa: str | None = None
    etapa_reloj: str | None = None
    fecha_reloj: date | None = None
    etapa_objetivo: str | None = None
    dias_transcurridos: int | None = None
    dias_restantes: int | None = None
    fecha_siguiente_hito: date | None = None
    semaforo: Semaforo = Semaforo.SIN_DATO
    fuente_tramo: FuentePrediccion = FuentePrediccion.SIN_DATOS
    estadistica_tramo: Estadistica | None = None
    avance_administrativo: float | None = None
    avance_temporal: float | None = None
    resolucion: Intervalo | None = None
    fuente_resolucion: FuentePrediccion = FuentePrediccion.SIN_DATOS
    n_resolucion: int = 0
    n_resolucion_condicional: int = 0
    avisos: list[str] = field(default_factory=list)


def clasificar_semaforo(dias: float, est: Estadistica | None) -> Semaforo:
    if est is None:
        return Semaforo.SIN_DATO
    if dias <= est.p25:
        return Semaforo.VERDE
    if dias <= est.p50:
        return Semaforo.AMARILLO
    if dias <= est.p75:
        return Semaforo.NARANJA
    return Semaforo.ROJO


def _residuales(valores: np.ndarray, transcurridos: int) -> np.ndarray:
    """Tiempo que les faltó a los expedientes que ya llevaban `transcurridos` días sin terminar."""
    return valores[valores > transcurridos] - transcurridos


def predecir(
    car: str | None,
    etapa_actual: str | None,
    fechas: dict[str, date],
    hoy: date,
    base: BaseTiempos,
    min_antecedentes: int,
    unidad: UnidadDias,
) -> Prediccion:
    flujo = obtener_flujo(car)
    if not flujo or not car:
        return Prediccion(EstadoPrediccion.SIN_FLUJO, "La CAR no tiene un flujo configurado.")
    car = car.strip().upper()

    idx = indice_etapa(flujo, etapa_actual)
    if idx is None:
        return Prediccion(EstadoPrediccion.SIN_ESTADO, "Aún no se ha registrado la etapa actual.")

    avance_admin = idx / (len(flujo) - 1)
    actual = flujo[idx]
    if actual.hito == Hito.RESOLUCION:
        return Prediccion(
            EstadoPrediccion.RESUELTO,
            "Resolución expedida.",
            etapa_actual=actual.nombre,
            avance_administrativo=1.0,
            fecha_reloj=fechas.get(actual.nombre),
        )

    siguiente = flujo[idx + 1]
    base_pred = {"etapa_actual": actual.nombre, "siguiente_etapa": siguiente.nombre,
                 "avance_administrativo": avance_admin}

    alcanzadas: list[Etapa] = [e for e in flujo[: idx + 1] if e.hito]
    if not alcanzadas:
        primera = next(e for e in flujo if e.hito)
        return Prediccion(
            EstadoPrediccion.ANTES_DE_HITOS,
            f"La cuenta regresiva empieza en «{primera.nombre}».",
            **base_pred,
        )

    con_fecha = [e for e in alcanzadas if fechas.get(e.nombre)]
    if not con_fecha:
        return Prediccion(
            EstadoPrediccion.FALTA_FECHA,
            f"Registra la fecha de «{alcanzadas[-1].nombre}» para calcular los tiempos.",
            **base_pred,
        )

    avisos: list[str] = []
    reloj = con_fecha[-1]
    if reloj != alcanzadas[-1]:
        avisos.append(
            f"Falta la fecha de «{alcanzadas[-1].nombre}»; el reloj se cuenta desde «{reloj.nombre}». "
            "Regístrala para una estimación más precisa."
        )
    assert reloj.hito is not None
    fecha_reloj = fechas[reloj.nombre]
    transcurridos = max(0, dias_entre(fecha_reloj, hoy, unidad))
    objetivo = next(e for e in flujo[idx + 1 :] if e.hito)
    assert objetivo.hito is not None

    # ── Siguiente hito ──────────────────────────────────────────────────────
    muestra_tramo = base.muestra(car, reloj.hito, objetivo.hito, min_antecedentes)
    est = resumir(muestra_tramo.valores)
    dias_restantes: int | None = None
    fecha_siguiente: date | None = None
    avance_temporal: float | None = None
    if est is not None:
        dias_restantes = int(round(est.p50 - transcurridos))
        if transcurridos <= est.p50:
            fecha_siguiente = sumar_dias(fecha_reloj, est.p50, unidad)
        else:
            resto = _residuales(muestra_tramo.valores, transcurridos)
            if len(resto):
                fecha_siguiente = sumar_dias(hoy, float(np.median(resto)), unidad)
        avance_temporal = transcurridos / est.p50 if est.p50 > 0 else None
    else:
        avisos.append(f"No hay antecedentes del tramo «{reloj.nombre}» → «{objetivo.nombre}».")

    # ── Resolución ──────────────────────────────────────────────────────────
    if objetivo.hito == Hito.RESOLUCION:
        muestra_res = muestra_tramo
    else:
        muestra_res = base.muestra(car, reloj.hito, Hito.RESOLUCION, min_antecedentes)
    resto_res = _residuales(muestra_res.valores, transcurridos)
    intervalo: Intervalo | None = None
    if muestra_res.n == 0:
        avisos.append("No hay antecedentes para proyectar la resolución.")
    elif len(resto_res) == 0:
        avisos.append(
            f"El trámite ya superó el mayor tiempo registrado ({int(muestra_res.valores.max())} días "
            f"desde «{reloj.nombre}»); no hay antecedentes para proyectar la resolución."
        )
    else:
        q25, q50, q75 = np.percentile(resto_res, [25, 50, 75])
        fechas_res = [sumar_dias(hoy, q, unidad) for q in (q25, q50, q75)]
        if fecha_siguiente is not None and objetivo.hito != Hito.RESOLUCION:
            # la resolución no puede ser antes del siguiente hito estimado
            fechas_res = [max(f, fecha_siguiente) for f in fechas_res]
        intervalo = Intervalo(*fechas_res)
        if len(resto_res) < 3:
            avisos.append(
                f"La proyección de resolución se basa en solo {len(resto_res)} expediente(s) que "
                "tardaron más que este; tómala como orientativa."
            )

    return Prediccion(
        EstadoPrediccion.OK,
        **base_pred,
        etapa_reloj=reloj.nombre,
        fecha_reloj=fecha_reloj,
        etapa_objetivo=objetivo.nombre,
        dias_transcurridos=transcurridos,
        dias_restantes=dias_restantes,
        fecha_siguiente_hito=fecha_siguiente,
        semaforo=clasificar_semaforo(transcurridos, est),
        fuente_tramo=muestra_tramo.fuente,
        estadistica_tramo=est,
        avance_temporal=avance_temporal,
        resolucion=intervalo,
        fuente_resolucion=muestra_res.fuente,
        n_resolucion=muestra_res.n,
        n_resolucion_condicional=int(len(resto_res)),
        avisos=avisos,
    )


def validar_fechas(car: str | None, etapa_actual: str | None, fechas: dict[str, date], hoy: date) -> list[str]:
    """Errores que impiden guardar: fechas futuras, posteriores a la etapa actual o desordenadas."""
    flujo = obtener_flujo(car)
    if not flujo:
        return []
    errores: list[str] = []
    idx = indice_etapa(flujo, etapa_actual)
    anterior: tuple[str, date] | None = None
    for i, etapa in enumerate(flujo):
        f = fechas.get(etapa.nombre)
        if f is None:
            continue
        if f > hoy:
            errores.append(f"«{etapa.nombre}» tiene una fecha futura ({f}).")
        if idx is not None and i > idx:
            errores.append(f"«{etapa.nombre}» tiene fecha pero es posterior a la etapa actual.")
        if anterior and f < anterior[1]:
            errores.append(f"«{etapa.nombre}» ({f}) es anterior a «{anterior[0]}» ({anterior[1]}).")
        anterior = (etapa.nombre, f)
    return errores

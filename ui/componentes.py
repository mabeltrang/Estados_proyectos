"""Piezas visuales reutilizables: estilos, semáforo, cuenta regresiva y proyección."""

from __future__ import annotations

from html import escape

import streamlit as st

from config.constantes import (
    SEMAFORO_COLOR,
    SEMAFORO_EMOJI,
    SEMAFORO_TEXTO,
    EstadoPrediccion,
    FuentePrediccion,
    Semaforo,
    UnidadDias,
)
from config import ajustes
from core.fechas import formato_fecha, formato_mes
from core.prediccion import Prediccion

UNIDAD = "días hábiles" if ajustes.UNIDAD_DIAS == UnidadDias.HABILES else "días"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="st-"], .stMarkdown, .stMetric { font-family: 'Public Sans', sans-serif; }
.sf-pill { display:inline-flex; align-items:center; gap:.45rem; padding:.2rem .7rem; border-radius:999px;
           font-size:.85rem; font-weight:600; border:1px solid currentColor; }
.sf-pill i { width:.6rem; height:.6rem; border-radius:50%; display:inline-block; }
.sf-cifra { font-size:2.6rem; font-weight:700; line-height:1; font-variant-numeric: tabular-nums; }
.sf-cifra small { font-size:1rem; font-weight:500; margin-left:.3rem; opacity:.75; }
.sf-sub { font-size:.9rem; opacity:.75; margin-top:.35rem; }
.sf-fuente { font-size:.78rem; opacity:.6; margin-top:.6rem; }
.sf-barra { height:.5rem; border-radius:.25rem; background: rgba(127,127,127,.18); overflow:hidden; margin:.25rem 0 .6rem; }
.sf-barra > span { display:block; height:100%; }
.sf-rango { display:flex; justify-content:space-between; font-size:.85rem; margin-top:.5rem;
            font-variant-numeric: tabular-nums; }
.sf-rango b { display:block; font-size:1.05rem; }
</style>
"""


def aplicar_estilos() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def pastilla_semaforo(semaforo: Semaforo) -> str:
    color = SEMAFORO_COLOR[semaforo]
    return (
        f'<span class="sf-pill" style="color:{color}"><i style="background:{color}"></i>'
        f"{escape(SEMAFORO_TEXTO[semaforo])}</span>"
    )


def texto_semaforo(semaforo: Semaforo) -> str:
    return f"{SEMAFORO_EMOJI[semaforo]} {SEMAFORO_TEXTO[semaforo]}"


def _barra(valor: float, color: str) -> str:
    ancho = max(0.0, min(1.0, valor)) * 100
    return f'<div class="sf-barra"><span style="width:{ancho:.0f}%;background:{color}"></span></div>'


def _nota_fuente(fuente: FuentePrediccion, n: int) -> str:
    if fuente == FuentePrediccion.SIN_DATOS:
        return "Sin antecedentes comparables."
    aviso = " · tómalo con cautela" if fuente in (FuentePrediccion.LIMITADO, FuentePrediccion.GENERAL) else ""
    return f"Basado en: {fuente.value} ({n} expedientes){aviso}"


def tarjeta_cuenta_regresiva(pred: Prediccion) -> None:
    with st.container(border=True):
        st.markdown("**Siguiente hito**")
        if pred.estado == EstadoPrediccion.RESUELTO:
            fecha = f" el {formato_fecha(pred.fecha_reloj)}" if pred.fecha_reloj else ""
            st.success(f"Resolución expedida{fecha}.", icon="✅")
            return
        if pred.estado != EstadoPrediccion.OK:
            st.info(pred.mensaje, icon="🕒")
            return
        objetivo = pred.etapa_objetivo or ""
        if pred.dias_restantes is None:
            st.markdown(f"Hacia «{escape(objetivo)}»")
            st.caption("No hay antecedentes de este tramo para estimar el tiempo.")
        elif pred.dias_restantes >= 0:
            st.markdown(
                f'<div class="sf-cifra">{pred.dias_restantes}<small>{UNIDAD}</small></div>'
                f'<div class="sf-sub">restantes para «{escape(objetivo)}» según la mediana histórica</div>',
                unsafe_allow_html=True,
            )
        else:
            color = SEMAFORO_COLOR[Semaforo.ROJO]
            st.markdown(
                f'<div class="sf-cifra" style="color:{color}">{-pred.dias_restantes}<small>{UNIDAD} de retraso</small></div>'
                f'<div class="sf-sub">frente a la mediana histórica para «{escape(objetivo)}»</div>',
                unsafe_allow_html=True,
            )
        st.markdown(pastilla_semaforo(pred.semaforo), unsafe_allow_html=True)
        detalle = [f"{pred.dias_transcurridos} {UNIDAD} desde «{pred.etapa_reloj}» ({formato_fecha(pred.fecha_reloj)})"]
        if pred.siguiente_etapa and pred.siguiente_etapa != objetivo:
            detalle.append(f"Etapa siguiente: «{pred.siguiente_etapa}» (sin histórico propio; se cuenta hasta «{objetivo}»)")
        if pred.fecha_siguiente_hito:
            detalle.append(f"Fecha estimada de «{objetivo}»: {formato_fecha(pred.fecha_siguiente_hito)}")
        st.markdown("<br>".join(f'<div class="sf-sub">{escape(d)}</div>' for d in detalle), unsafe_allow_html=True)
        n = pred.estadistica_tramo.n if pred.estadistica_tramo else 0
        st.markdown(f'<div class="sf-fuente">{escape(_nota_fuente(pred.fuente_tramo, n))}</div>', unsafe_allow_html=True)


def tarjeta_resolucion(pred: Prediccion) -> None:
    with st.container(border=True):
        st.markdown("**Resolución probable**")
        if pred.estado == EstadoPrediccion.RESUELTO:
            st.success("El trámite ya tiene resolución.", icon="✅")
            return
        if pred.estado != EstadoPrediccion.OK:
            st.info(pred.mensaje, icon="🕒")
            return
        if pred.resolucion is None:
            st.caption("No es posible proyectar la resolución con los antecedentes disponibles.")
        else:
            r = pred.resolucion
            st.markdown(
                f'<div class="sf-cifra" style="font-size:2rem">{escape(formato_mes(r.probable))}</div>'
                f'<div class="sf-rango"><span>Escenario rápido<b>{escape(formato_fecha(r.temprano))}</b></span>'
                f'<span style="text-align:right">Escenario lento<b>{escape(formato_fecha(r.tardio))}</b></span></div>',
                unsafe_allow_html=True,
            )
        nota = _nota_fuente(pred.fuente_resolucion, pred.n_resolucion)
        if pred.n_resolucion_condicional:
            nota += f" · {pred.n_resolucion_condicional} siguen siendo comparables con el tiempo ya transcurrido"
        st.markdown(f'<div class="sf-fuente">{escape(nota)}</div>', unsafe_allow_html=True)


def avances(pred: Prediccion) -> None:
    with st.container(border=True):
        st.markdown("**Avance**")
        admin = pred.avance_administrativo or 0.0
        st.markdown(
            f'<div class="sf-sub">Administrativo (etapas cumplidas): {admin:.0%}</div>{_barra(admin, "#2E6B4F")}',
            unsafe_allow_html=True,
        )
        if pred.avance_temporal is not None:
            color = SEMAFORO_COLOR[pred.semaforo]
            st.markdown(
                f'<div class="sf-sub">Tiempo del tramo actual frente a lo típico: {pred.avance_temporal:.0%}</div>'
                f"{_barra(pred.avance_temporal, color)}",
                unsafe_allow_html=True,
            )
            st.caption("El tiempo de espera no aumenta el avance administrativo.")

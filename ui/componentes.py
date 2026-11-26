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

# ── Marca Unergy (mismos colores de las apps Hotspots y Compensación Biótica) ──
PURPLE = "#7B4CC9"
PURPLE_DARK = "#2D1B4E"
PURPLE_MID = "#9B6FE8"
PURPLE_LIGHT = "#D9CEEF"
LAVANDA_TEXTO = "#C5B3F0"
BORDE = "#B8A9E0"
TEXTO = "#1A1A2E"
TEXTO_SUAVE = "#5A5A72"

# Colores de las etiquetas de «Estado forestal», parecidos a los de la plataforma Unergy: (fondo, texto)
COLOR_ESTADO_UNERGY: dict[str, tuple[str, str]] = {
    "Solicitud aprobada": ("#DFF5D8", "#3E8E2F"),
    "Solicitud rechazada": ("#FDE3D3", "#C2571A"),
    "Visita": ("#FBF1C7", "#9A7A00"),
    "Liquidación": ("#F2DDF7", "#9B2FB5"),
    "Programado": ("#FBDCD6", "#C2412D"),
    "Exonerado": ("#DFF5D8", "#3E8E2F"),
    "Requerimientos": ("#D7EEFA", "#1F7FB0"),
    "Pausado": ("#FDE3D3", "#C2571A"),
    "Respuesta radicado": ("#FAD9E6", "#C2185B"),
    "Solicitud radicada": ("#D7EEFA", "#1F7FB0"),
    "Respuesta a requerimientos": ("#FBF6C7", "#9A8A00"),
    "Por radicar": ("#FBDCD6", "#C2412D"),
}

CSS = f"""
<style>
  .stApp h1, .stApp h2, .stApp h3 {{ color: {TEXTO}; }}
  .unergy-header {{ background: {PURPLE_DARK}; padding: 18px 28px 14px; border-radius: 12px;
    margin-bottom: 18px; display: flex; align-items: center; gap: 16px; }}
  .unergy-header h1 {{ color: #FFFFFF !important; font-size: 1.55rem; font-weight: 700; margin: 0; padding: 0; }}
  .unergy-header p {{ color: {LAVANDA_TEXTO} !important; font-size: 0.82rem; margin: 2px 0 0; }}
  .unergy-logo {{ font-size: 2.2rem; line-height: 1; }}
  [data-testid="stMetric"] {{ background: #FFFFFF; border: 2px solid {PURPLE_LIGHT}; border-left: 5px solid {PURPLE};
    border-radius: 10px; padding: 12px 18px; box-shadow: 0 1px 4px rgba(123,76,201,0.08); }}
  [data-testid="stMetricLabel"] p {{ font-size: 0.8rem; color: {TEXTO_SUAVE}; font-weight: 700; }}
  [data-testid="stMetricValue"] {{ font-weight: 800; color: {PURPLE_DARK}; }}
  [data-testid="stExpander"] {{ border: 1.5px solid {BORDE} !important; border-radius: 8px !important; }}
  [data-testid="stDataFrame"] {{ border: 1.5px solid {BORDE}; border-radius: 8px; overflow: hidden; }}
  [data-testid="stSidebar"] {{ background: {PURPLE_DARK} !important; border-right: 3px solid {PURPLE}; }}
  [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] small {{ color: #FFFFFF !important; }}
  [data-testid="stSidebarNav"] a:hover, [data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: rgba(155,111,232,0.35) !important; }}
  [data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.2) !important; }}
  .sf-pill {{ display:inline-flex; align-items:center; gap:.45rem; padding:.2rem .7rem; border-radius:999px;
    font-size:.85rem; font-weight:600; border:1px solid currentColor; }}
  .sf-pill i {{ width:.6rem; height:.6rem; border-radius:50%; display:inline-block; }}
  .sf-estado {{ display:inline-block; padding:.15rem .65rem; border-radius:999px; font-size:.85rem; font-weight:600; }}
  .sf-cifra {{ font-size:2.6rem; font-weight:800; line-height:1; color:{PURPLE_DARK}; font-variant-numeric: tabular-nums; }}
  .sf-cifra small {{ font-size:1rem; font-weight:500; margin-left:.3rem; opacity:.75; }}
  .sf-sub {{ font-size:.9rem; color:{TEXTO_SUAVE}; margin-top:.35rem; }}
  .sf-fuente {{ font-size:.78rem; color:{TEXTO_SUAVE}; opacity:.8; margin-top:.6rem; }}
  .sf-barra {{ height:.5rem; border-radius:.25rem; background:{PURPLE_LIGHT}; overflow:hidden; margin:.25rem 0 .6rem; }}
  .sf-barra > span {{ display:block; height:100%; }}
  .sf-rango {{ display:flex; justify-content:space-between; font-size:.85rem; margin-top:.5rem;
    font-variant-numeric: tabular-nums; }}
  .sf-rango b {{ display:block; font-size:1.05rem; color:{PURPLE_DARK}; }}
</style>
"""


def aplicar_estilos() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def encabezado(titulo: str, subtitulo: str = "", icono: str = "🌳") -> None:
    """Encabezado corporativo Unergy (franja morada), igual al de Hotspots y Compensación."""
    sub = f"<p>{escape(subtitulo)}</p>" if subtitulo else ""
    st.markdown(
        f'<div class="unergy-header"><div class="unergy-logo">{icono}</div><div>'
        f"<h1>{escape(titulo)}</h1>{sub}</div></div>",
        unsafe_allow_html=True,
    )


def etiqueta_estado_unergy(estado: str) -> str:
    if not estado:
        return '<span class="sf-estado" style="background:#EEE;color:#666">Sin estado</span>'
    fondo, texto = COLOR_ESTADO_UNERGY.get(estado, ("#EEE", "#555"))
    return f'<span class="sf-estado" style="background:{fondo};color:{texto}">{escape(estado)}</span>'


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
            f'<div class="sf-sub">Administrativo (etapas cumplidas): {admin:.0%}</div>{_barra(admin, PURPLE)}',
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

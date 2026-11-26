"""Piezas visuales reutilizables: estilos de Unergy, encabezado, etiquetas y avance."""

from __future__ import annotations

from html import escape

import streamlit as st


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
  .sf-etapa {{ padding:.25rem 0; color:{TEXTO_SUAVE}; }}
  .sf-hecha {{ color:{PURPLE_DARK}; }}
  .sf-actual {{ color:{PURPLE}; font-weight:700; }}
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


def barra_avance(valor: float | None, texto: str) -> str:
    ancho = 0 if valor is None else max(0.0, min(1.0, valor)) * 100
    return (
        f'<div class="sf-sub">{escape(texto)}</div>'
        f'<div class="sf-barra"><span style="width:{ancho:.0f}%;background:{PURPLE}"></span></div>'
    )


def linea_de_etapas(etapas: list[str], posibles: tuple[str, ...]) -> str:
    """Flujo de la CAR: ✓ etapas ya pasadas, ● la etapa homologada (o las posibles), ○ las que faltan."""
    if not posibles:
        return "".join(f'<div class="sf-etapa">○ {escape(e)}</div>' for e in etapas)
    primera = etapas.index(posibles[0])
    filas = []
    for i, e in enumerate(etapas):
        if e in posibles:
            filas.append(f'<div class="sf-etapa sf-actual">● {escape(e)}</div>')
        elif i < primera:
            filas.append(f'<div class="sf-etapa sf-hecha">✓ {escape(e)}</div>')
        else:
            filas.append(f'<div class="sf-etapa">○ {escape(e)}</div>')
    return "".join(filas)

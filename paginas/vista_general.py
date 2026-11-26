"""Resumen de todos los proyectos: estado TSF, etapa homologada y avance (solo lectura)."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from config.constantes import Columna, TipoHomologacion
from core.api_unergy import ErrorApiUnergy
from core.proyectos import agregar_homologacion, asignar_car
from ui.componentes import PURPLE, encabezado
from ui.datos import proyectos_api

CLAVE_CARGAR = "_resumen_cargado"

encabezado(
    "Trámites de aprovechamiento forestal",
    "Unergy · Equipo forestal · Resumen de todos los proyectos según su estado en TSF.",
)

if not st.session_state.get(CLAVE_CARGAR):
    st.info(
        "El resumen consulta todos los terrenos de la API y puede tardar varios minutos la primera vez "
        "(después queda guardado una hora). Para un proyecto puntual usa «Proyectos»."
    )
    if st.button("Cargar resumen", type="primary"):
        st.session_state[CLAVE_CARGAR] = True
        st.rerun()
    st.stop()

try:
    carga = proyectos_api()
except ErrorApiUnergy as exc:
    st.error(f"No fue posible leer los proyectos: {exc.mensaje}")
    st.stop()

df = agregar_homologacion(asignar_car(carga.tabla, {}))
if df.empty:
    st.info("La API no devolvió proyectos.")
    st.stop()

claras = df[df[Columna.HOMOLOGACION] == TipoHomologacion.CLARA]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Proyectos", len(df))
c2.metric("Con homologación clara", len(claras))
c3.metric("Avance promedio", f"{claras[Columna.AVANCE].mean():.0f} %" if not claras.empty else "—",
          help="Solo proyectos con homologación clara.")
c4.metric("Sin CAR identificada", int(df[Columna.CAR].isna().sum() + (df[Columna.CAR] == "").sum()))

izq, der = st.columns(2)
with izq:
    st.subheader("Proyectos por estado TSF")
    por_estado = (
        df[Columna.ESTADO_FORESTAL].replace("", "No encontrado").value_counts()
        .rename_axis("Estado TSF").reset_index(name="Proyectos")
    )
    st.altair_chart(
        alt.Chart(por_estado).mark_bar(color=PURPLE).encode(
            x="Proyectos:Q", y=alt.Y("Estado TSF:N", sort="-x", title=None), tooltip=["Estado TSF", "Proyectos"]
        ),
        width="stretch",
    )
with der:
    st.subheader("Proyectos por CAR")
    por_car = df[Columna.CAR].fillna("Sin identificar").replace("", "Sin identificar").value_counts()
    por_car = por_car.rename_axis("CAR").reset_index(name="Proyectos")
    st.altair_chart(
        alt.Chart(por_car).mark_bar(color=PURPLE).encode(
            x="Proyectos:Q", y=alt.Y("CAR:N", sort="-x", title=None), tooltip=["CAR", "Proyectos"]
        ),
        width="stretch",
    )

st.subheader("Etapa homologada por CAR")
resumen = (
    df.assign(
        CAR=df[Columna.CAR].fillna("Sin identificar").replace("", "Sin identificar"),
        Etapa=df[Columna.ETAPA_HOMOLOGADA].replace("", "Sin homologación"),
    )
    .groupby(["CAR", "Etapa"])
    .size()
    .reset_index(name="Proyectos")
)
st.dataframe(resumen, hide_index=True, width="stretch")

with st.expander("Todos los proyectos"):
    st.dataframe(
        pd.DataFrame(
            {
                "Proyecto": df[Columna.NOMBRE],
                "Terreno": df[Columna.TERRENO_NOMBRE],
                "CAR": df[Columna.CAR],
                "Estado TSF": df[Columna.ESTADO_FORESTAL].replace("", "No encontrado"),
                "Etapa homologada": df[Columna.ETAPA_HOMOLOGADA].replace("", "Sin homologación"),
                "Avance": df[Columna.AVANCE_TEXTO],
            }
        ),
        hide_index=True,
        width="stretch",
    )
if carga.errores:
    with st.expander(f"Errores al consultar ({len(carga.errores)})"):
        for e in carga.errores:
            st.caption(e)

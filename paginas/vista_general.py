"""Vista general del portafolio de trámites."""

from __future__ import annotations

from datetime import timedelta

import altair as alt
import pandas as pd
import streamlit as st

from config import ajustes
from config.constantes import SEMAFORO_COLOR, SEMAFORO_TEXTO, Columna, Semaforo
from core.fechas import formato_fecha, hoy_colombia
from ui.componentes import texto_semaforo
from ui.datos import aviso_almacen, tablero

st.title("Trámites de aprovechamiento forestal")
st.caption("Estado de cada proyecto ante su CAR y cuándo se espera el siguiente paso.")

t = tablero()
if t.error_api:
    st.error(f"No fue posible leer los proyectos: {t.error_api}")
    st.info("Revisa la página «Explorar API» y los Secrets de la app.")
    st.stop()
aviso_almacen()

df = t.tabla
if df.empty:
    st.info("La API no devolvió proyectos (Minifarms).")
    st.stop()

hoy = hoy_colombia()
limite = hoy + timedelta(days=ajustes.DIAS_PROXIMO_A_RESOLUCION)
en_alerta = df[df["semaforo"] == Semaforo.ROJO]
proximos = df[df["resolucion_probable"].map(lambda f: f is not None and f <= limite)]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Proyectos", len(df))
c2.metric("Con CAR y flujo", int(df["car_con_flujo"].sum()))
c3.metric("En alerta", len(en_alerta), help="Superaron el P75 histórico del tramo en que están.")
c4.metric(
    "Próximos a resolución",
    len(proximos),
    help=f"Fecha probable de resolución antes del {formato_fecha(limite)}.",
)

izq, der = st.columns(2)
with izq:
    st.subheader("Proyectos por CAR")
    por_car = df[Columna.CAR].fillna("Sin identificar").value_counts().rename_axis("CAR").reset_index(name="Proyectos")
    st.altair_chart(
        alt.Chart(por_car).mark_bar(color="#2E6B4F").encode(
            x="Proyectos:Q", y=alt.Y("CAR:N", sort="-x", title=None), tooltip=["CAR", "Proyectos"]
        ),
        width="stretch",
    )
with der:
    st.subheader("Semáforo")
    orden = list(Semaforo)
    sem = df["semaforo"].value_counts().reindex(orden, fill_value=0).rename_axis("s").reset_index(name="Proyectos")
    sem["Estado"] = sem["s"].map(lambda s: SEMAFORO_TEXTO[Semaforo(s)])
    st.altair_chart(
        alt.Chart(sem).mark_bar().encode(
            x="Proyectos:Q",
            y=alt.Y("Estado:N", sort=[SEMAFORO_TEXTO[s] for s in orden], title=None),
            color=alt.Color(
                "Estado:N",
                scale=alt.Scale(domain=[SEMAFORO_TEXTO[s] for s in orden], range=[SEMAFORO_COLOR[s] for s in orden]),
                legend=None,
            ),
            tooltip=["Estado", "Proyectos"],
        ),
        width="stretch",
    )

st.subheader("Proyectos por etapa")
etapas = (
    df.assign(etapa=df["etapa_actual"].replace("", "Sin registrar"))
    .groupby([Columna.CAR, "etapa"], dropna=False)
    .size()
    .reset_index(name="Proyectos")
    .rename(columns={Columna.CAR: "CAR", "etapa": "Etapa"})
)
st.dataframe(etapas, hide_index=True, width="stretch")


def tabla_corta(sub: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Semáforo": sub["semaforo"].map(lambda s: texto_semaforo(Semaforo(s))),
            "Proyecto": sub[Columna.NOMBRE],
            "CAR": sub[Columna.CAR],
            "Etapa actual": sub["etapa_actual"],
            "Resolución probable": sub["resolucion_probable"].map(formato_fecha),
        }
    )


if not en_alerta.empty:
    st.subheader("En alerta")
    st.dataframe(tabla_corta(en_alerta), hide_index=True, width="stretch")
if not proximos.empty:
    st.subheader("Próximos a resolución")
    st.dataframe(
        tabla_corta(proximos.sort_values("resolucion_probable")), hide_index=True, width="stretch"
    )

if t.carga and (t.carga.errores or t.carga.terrenos_sin_minifarms):
    with st.expander("Detalles de la consulta a la API"):
        st.write(f"Terrenos consultados: {t.carga.terrenos}")
        st.write(f"Terrenos sin Minifarms: {t.carga.terrenos_sin_minifarms}")
        for e in t.carga.errores:
            st.write(f"- {e}")

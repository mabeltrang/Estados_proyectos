"""Reporte de calidad del Excel histórico, tiempos internos y flujos configurados."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import ajustes
from config.constantes import NOMBRE_HITO, Hito
from config.flujos import FLUJOS
from ui.componentes import encabezado
from ui.datos import base_tiempos, historico_actual

encabezado(
    "Histórico y calidad de datos",
    f"Fuente: {ajustes.RUTA_HISTORICO.name} (solo lectura; el archivo original no se modifica).",
    "📚",
)

h = historico_actual()
base = base_tiempos()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Filas leídas", h.filas_leidas)
c2.metric("Trámites usados", len(h.tramites), help="Después de unir actos del mismo trámite.")
c3.metric("Actos unidos (duplicados)", h.actos_unidos)
c4.metric("Problemas detectados", len(h.problemas))

st.markdown(
    f"- Hojas del libro: {', '.join(h.hojas)} · usadas: {', '.join(h.hojas_usadas) or 'ninguna'}\n"
    f"- Filas de otras categorías (no se usan): {h.filas_otras_categorias}\n"
    f"- Filas de CAR excluidas por ahora ({', '.join(sorted(ajustes.CARS_HISTORICO_EXCLUIDAS))}): "
    f"{h.filas_cars_excluidas}\n"
    f"- Unidad de tiempo: días {ajustes.UNIDAD_DIAS.value} · mínimo de antecedentes por tramo: "
    f"{ajustes.MIN_ANTECEDENTES}"
)
if h.columnas_faltantes:
    st.warning("Columnas no encontradas en el Excel: " + ", ".join(h.columnas_faltantes))
with st.expander("Encabezados reconocidos"):
    st.dataframe(
        pd.DataFrame({"Dato": list(h.columnas_encontradas), "Encabezado en el Excel": list(h.columnas_encontradas.values())}),
        hide_index=True,
        width="stretch",
    )

if not h.tramites.empty:
    st.subheader("Fechas disponibles por CAR")
    cols = [hito.value for hito in Hito]
    disp = h.tramites.groupby("car")[cols].count().rename(columns={hito.value: NOMBRE_HITO[hito] for hito in Hito})
    disp.insert(0, "Trámites", h.tramites.groupby("car").size())
    st.dataframe(disp, width="stretch")

st.subheader("Reporte de calidad")
if h.problemas.empty:
    st.success("No se detectaron problemas.")
else:
    tipos = st.multiselect("Tipo de problema", sorted(h.problemas["Problema"].unique()))
    vista = h.problemas[h.problemas["Problema"].isin(tipos)] if tipos else h.problemas
    st.dataframe(vista, hide_index=True, width="stretch")
    st.caption(
        "Las fechas imposibles no se usan. En fechas invertidas no se sabe cuál está mal, así que ningún "
        "tramo que use esas fechas entra en los cálculos. Corrige el Excel en su repositorio de origen y "
        "vuelve a copiarlo a data/."
    )

with st.expander("Tiempos históricos por tramo (uso interno)"):
    tabla = base.tabla()
    if tabla.empty:
        st.info("No hay tramos con datos.")
    else:
        st.dataframe(tabla.round(1), hide_index=True, width="stretch")

with st.expander("Flujos configurados por CAR"):
    st.caption("⏱ = etapa con fecha en el histórico. Para editar, ver config/flujos.py.")
    for car, flujo in FLUJOS.items():
        etapas = " → ".join(f"{'⏱ ' if e.hito else ''}{e.nombre}" for e in flujo)
        n = int((h.tramites["car"] == car).sum()) if not h.tramites.empty else 0
        st.markdown(f"**{car}** · {n} trámites en el histórico  \n{etapas}")

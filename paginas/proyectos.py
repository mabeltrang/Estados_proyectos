"""Buscar proyectos y ver su estado en TSF, la etapa homologada de su CAR y el % de avance.

Solo lectura: esta página no cambia estados ni guarda nada.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import ajustes
from config.constantes import Columna, TipoHomologacion
from config.flujos import FLUJOS, nombres_etapas
from config.homologacion import homologar
from core.api_unergy import ErrorApiUnergy
from core.proyectos import identificar_car
from ui.componentes import barra_avance, encabezado, etiqueta_estado_unergy, linea_de_etapas
from ui.datos import minifarms_terreno, proyectos_busqueda

CLAVE_TERRENO = "_terreno_seleccionado"
CLAVE_MINIFARM = "_minifarm_seleccionada"
CLAVE_BUSQUEDA = "_texto_busqueda"                    # widget (Streamlit lo borra al salir de la pantalla)
CLAVE_BUSQUEDA_GUARDADA = "_texto_busqueda_guardado"  # copia que sobrevive para poder volver
CLAVE_VERSION = "_version_tablas"                     # cambia al volver, para que la tabla olvide la fila marcada

COLUMNA_AVANCE = st.column_config.ProgressColumn("Avance", min_value=0, max_value=100, format="%.0f%%")


def abrir(terreno_id: str, minifarm_id: str) -> None:
    st.session_state[CLAVE_TERRENO] = str(terreno_id)
    st.session_state[CLAVE_MINIFARM] = str(minifarm_id)


def volver() -> None:
    st.session_state[CLAVE_BUSQUEDA] = st.session_state.get(CLAVE_BUSQUEDA_GUARDADA, "")
    st.session_state[CLAVE_TERRENO] = None
    st.session_state[CLAVE_MINIFARM] = None
    st.session_state[CLAVE_VERSION] = st.session_state.get(CLAVE_VERSION, 0) + 1


def vista(tabla: pd.DataFrame) -> pd.DataFrame:
    """Tabla para mostrar: el % en barra solo si la homologación es clara; si hay varias etapas
    posibles, el rango va junto a ellas."""
    etapa = [
        f"{e} ({t})" if h == TipoHomologacion.VARIAS else (e or "Sin homologación")
        for e, h, t in zip(tabla[Columna.ETAPA_HOMOLOGADA.value], tabla[Columna.HOMOLOGACION.value],
                           tabla[Columna.AVANCE_TEXTO.value])
    ]
    return pd.DataFrame(
        {
            "Proyecto": tabla[Columna.NOMBRE.value],
            "Terreno": tabla[Columna.TERRENO_NOMBRE.value],
            "CAR": tabla[Columna.CAR.value].fillna("Sin identificar").replace("", "Sin identificar"),
            "Estado TSF": tabla[Columna.ESTADO_FORESTAL.value].replace("", "No encontrado"),
            "Etapa homologada": etapa,
            "Avance": tabla[Columna.AVANCE.value],
        }
    )


# ── Pantalla 1: búsqueda ─────────────────────────────────────────────────────
def pantalla_busqueda() -> None:
    encabezado("Proyectos", "Estado en TSF, etapa homologada de su CAR y % de avance.")
    texto = st.text_input(
        "Buscar proyecto", key=CLAVE_BUSQUEDA, placeholder="Nombre comercial, nombre del proyecto o del terreno"
    ).strip()
    st.session_state[CLAVE_BUSQUEDA_GUARDADA] = texto
    if len(texto) < 2:
        st.info("Escribe al menos dos letras para buscar (ej. COLCEST193 o AGUACHICA).")
        return
    try:
        resultados, n_terrenos, errores = proyectos_busqueda(texto)
    except ErrorApiUnergy as exc:
        st.error(f"No fue posible buscar: {exc.mensaje}")
        return
    if resultados.empty:
        st.info("No se encontraron proyectos con ese texto.")
        return
    extra = (
        f" Se muestran los primeros {ajustes.BUSQUEDA_MAX_TERRENOS} terrenos; escribe algo más específico."
        if n_terrenos > ajustes.BUSQUEDA_MAX_TERRENOS
        else ""
    )
    st.caption(
        f"{len(resultados)} proyecto(s) en {min(n_terrenos, ajustes.BUSQUEDA_MAX_TERRENOS)} terreno(s). "
        f"Selecciona uno para ver el detalle.{extra}"
    )
    evento = st.dataframe(
        vista(resultados), hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        column_config={"Avance": COLUMNA_AVANCE}, key=f"tabla_busqueda_{st.session_state.get(CLAVE_VERSION, 0)}",
    )
    for e in errores:
        st.caption(f"⚠️ {e}")
    filas = getattr(getattr(evento, "selection", None), "rows", None)
    if filas:
        f = resultados.iloc[filas[0]]
        abrir(f[Columna.TERRENO_ID.value], f[Columna.MINIFARM_ID.value])
        st.rerun()


# ── Pantalla 2: detalle ──────────────────────────────────────────────────────
def pantalla_detalle(terreno_id: str, mid: str) -> None:
    st.button("← Volver a la búsqueda", on_click=volver)
    try:
        tabla = minifarms_terreno(terreno_id)
    except ErrorApiUnergy as exc:
        st.error(f"No fue posible leer el terreno: {exc.mensaje}")
        return
    coincide = tabla[tabla[Columna.MINIFARM_ID.value] == mid]
    if coincide.empty:
        st.warning("Este proyecto ya no aparece en el terreno consultado.")
        return
    fila = coincide.iloc[0]
    car = fila[Columna.CAR.value] if isinstance(fila[Columna.CAR.value], str) else None
    estado = str(fila[Columna.ESTADO_FORESTAL.value] or "")
    h = homologar(car, estado)

    encabezado(str(fila[Columna.NOMBRE.value]), f"Terreno {fila[Columna.TERRENO_NOMBRE.value]} · {fila[Columna.UBICACION.value]}")

    izq, der = st.columns([1, 1.2])
    with izq:
        with st.container(border=True):
            st.markdown("**Estado**")
            st.markdown("TSF: " + etiqueta_estado_unergy(estado), unsafe_allow_html=True)
            if h.clara:
                st.markdown(f"Etapa en {car}: **{h.etapas[0]}**")
                st.markdown(barra_avance(h.avance_min, f"Avance: {h.avance_min:.0%}"), unsafe_allow_html=True)
            elif h.etapas:
                posibles = " o ".join(f"«{e}»" for e in h.etapas)
                st.markdown(f"Etapa en {car}: puede ser {posibles}")
                st.caption(f"Avance entre {h.avance_min:.0%} y {h.avance_max:.0%}: TSF no permite distinguirlas.")
            elif not car:
                _, mensaje = identificar_car(str(fila[Columna.MUNICIPIO.value]), str(fila[Columna.DEPARTAMENTO.value]))
                st.caption(f"Sin CAR identificada, no se puede homologar. {mensaje}")
            elif car not in FLUJOS:
                st.caption(f"{car} no tiene flujo configurado en config/flujos.py.")
            elif not estado:
                st.caption("La API no trae un estado TSF reconocible para este proyecto.")
            else:
                st.caption(f"«{estado}» no tiene equivalente en las etapas de {car}.")
        with st.container(border=True):
            st.markdown("**Proyecto**")
            datos = {
                "CAR": car or "Sin identificar",
                "Estado general": fila[Columna.ETAPA_API.value],
                "Tipo de permiso": fila[Columna.TIPO_PERMISO.value],
                "Árboles": fila[Columna.ARBOLES.value],
                "Operador de red": fila[Columna.OPERADOR_RED.value],
                "Minifarm (id)": fila[Columna.MINIFARM_ID.value],
                "Terreno (id)": fila[Columna.TERRENO_ID.value],
            }
            st.markdown("\n".join(f"- {k}: {v or '—'}" for k, v in datos.items()))
    with der:
        with st.container(border=True):
            st.markdown(f"**Etapas de {car}**" if car in FLUJOS else "**Etapas**")
            etapas = nombres_etapas(car)
            if etapas:
                st.markdown(linea_de_etapas(etapas, h.etapas), unsafe_allow_html=True)
            else:
                st.caption("Sin flujo para mostrar.")


terreno = st.session_state.get(CLAVE_TERRENO)
minifarm = st.session_state.get(CLAVE_MINIFARM)
if terreno and minifarm:
    pantalla_detalle(terreno, minifarm)
else:
    pantalla_busqueda()

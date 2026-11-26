"""Exploración de la API de Unergy (solo GET) para confirmar campos, estados y ubicaciones."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import ajustes
from config.constantes import Columna, FuenteCar
from core.api_unergy import ClienteUnergy, ErrorApiUnergy, JsonObj
from core.proyectos import a_texto, asignar_car, minifarms_de_terreno, textos_anidados
from ui.componentes import encabezado
from ui.datos import crear_cliente, proyectos_api

encabezado(
    "Explorar API",
    "Todas las consultas son de solo lectura (GET). La API Key se toma de los Secrets y nunca se muestra.",
    "🔌",
)


def cliente_o_error() -> ClienteUnergy | None:
    try:
        return crear_cliente()
    except ErrorApiUnergy as exc:
        st.error(exc.mensaje)
        return None


def campos(obj: JsonObj) -> pd.DataFrame:
    return pd.DataFrame(
        [{"Campo": k, "Tipo": type(v).__name__, "Ejemplo": a_texto(v)[:80]} for k, v in obj.items()]
    )


cliente = cliente_o_error()
if cliente is None:
    st.stop()

# 1. Conexión
st.subheader("1. Conexión")
if st.button("Probar conexión"):
    try:
        st.success(f"Conexión correcta. Terrenos forestales: {cliente.probar_conexion()}")
    except ErrorApiUnergy as exc:
        st.error(exc.mensaje)

# 2. Lista forestal
st.subheader("2. Lista de terrenos forestales (página 1)")
if st.button("Consultar página 1"):
    try:
        pagina = cliente.listar_forestal(pagina=1, page_size=20)
        items = [i for i in pagina.get("results", []) if isinstance(i, dict)]  # type: ignore[union-attr]
        st.write(f"Total: {pagina.get('count')} · siguiente página: {'sí' if pagina.get('next') else 'no'}")
        if items:
            st.markdown("Campos del primer terreno")
            st.dataframe(campos(items[0]), hide_index=True, width="stretch")
            visibles = [c for c in ("id", "name", "location", "tree_count") if c in items[0]]
            st.dataframe(pd.DataFrame(items)[visibles], hide_index=True, width="stretch")
    except ErrorApiUnergy as exc:
        st.error(exc.mensaje)

# 3. Detalle
st.subheader("3. Detalle de un terreno")
c1, c2 = st.columns(2)
terreno = c1.text_input("Id del terreno")
buscado = c2.text_input("Texto a ubicar (opcional)", placeholder="Ej. Respuesta a requerimientos, 16913")
if st.button("Consultar detalle", disabled=not terreno):
    try:
        detalle = cliente.detalle_forestal(terreno)
        if buscado.strip():
            aguja = buscado.strip().lower()
            hallazgos = [
                {"Campo": ruta, "Valor": texto[:120]}
                for ruta, texto in textos_anidados(detalle, "detalle")
                if aguja in texto.lower()
            ]
            if hallazgos:
                st.success(f"«{buscado}» aparece en estos campos del detalle forestal:")
                st.dataframe(pd.DataFrame(hallazgos), hide_index=True, width="stretch")
            else:
                st.warning(f"«{buscado}» no aparece en el detalle forestal de este terreno.")
        st.markdown("Campos del detalle forestal")
        st.dataframe(campos(detalle), hide_index=True, width="stretch")
        mfs = detalle.get("minifarms")
        if isinstance(mfs, list) and mfs and isinstance(mfs[0], dict):
            st.markdown("Campos de la primera Minifarm (así viene `stage`)")
            st.dataframe(campos(mfs[0]), hide_index=True, width="stretch")
            st.markdown("Minifarms del terreno y estado forestal detectado")
            mf_tabla = pd.DataFrame(minifarms_de_terreno(detalle))
            st.dataframe(
                mf_tabla[[Columna.NOMBRE, Columna.ESTADO_FORESTAL, Columna.CAMPO_ESTADO, Columna.TIPO_PERMISO, Columna.ETAPA_API]]
                .rename(columns={Columna.NOMBRE: "Proyecto", Columna.ESTADO_FORESTAL: "Estado forestal detectado",
                                 Columna.CAMPO_ESTADO: "Campo de la API", Columna.TIPO_PERMISO: "forestry_licence",
                                 Columna.ETAPA_API: "stage"}),
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("Este terreno no trae Minifarms.")
        try:
            ambiental = cliente.detalle_ambiental(terreno)
            with st.expander("Campos del detalle ambiental (mismo id de terreno)"):
                st.dataframe(campos(ambiental), hide_index=True, width="stretch")
        except ErrorApiUnergy as exc:
            st.caption(f"Detalle ambiental: {exc.mensaje}")
    except ErrorApiUnergy as exc:
        st.error(exc.mensaje)

# 4. Conteo por estado forestal del terreno
st.subheader("4. Terrenos por estado forestal")
st.caption("Es el estado del terreno (la etiqueta junto al nombre en la plataforma), no el de cada proyecto.")
if st.button("Consultar conteo"):
    try:
        conteo = cliente.conteo_forestal()
        if isinstance(conteo, dict):
            st.dataframe(
                pd.DataFrame([{"Estado": k, "Terrenos": a_texto(v)} for k, v in conteo.items()]),
                hide_index=True,
                width="stretch",
            )
        elif isinstance(conteo, list):
            st.dataframe(pd.DataFrame(conteo), hide_index=True, width="stretch")
        else:
            st.write(a_texto(conteo))
    except ErrorApiUnergy as exc:
        st.error(exc.mensaje)

# 5. Todos los proyectos vs. información territorial
st.subheader("5. Todos los proyectos frente a la tabla de municipios por CAR")
st.caption(f"Recorre todas las páginas ({ajustes.API_PAGE_SIZE} por página) y el detalle de cada terreno.")
if st.button("Analizar todos los proyectos (puede tardar varios minutos)"):
    try:
        carga = proyectos_api()
    except ErrorApiUnergy as exc:
        st.error(exc.mensaje)
        st.stop()
    tabla = asignar_car(carga.tabla, {})
    st.write(
        f"Terrenos: {carga.terrenos} · Minifarms: {len(tabla)} · terrenos sin Minifarms: "
        f"{carga.terrenos_sin_minifarms} · errores: {len(carga.errores)}"
    )
    a, b = st.columns(2)
    with a:
        st.markdown("Valores de estado forestal en la API")
        st.dataframe(
            tabla[Columna.ESTADO_FORESTAL].replace("", "(vacío)").value_counts().rename_axis("Estado forestal").reset_index(name="Minifarms"),
            hide_index=True,
            width="stretch",
        )
    with b:
        st.markdown("CAR identificada")
        st.dataframe(
            tabla[Columna.CAR].fillna("Sin identificar").value_counts().rename_axis("CAR").reset_index(name="Minifarms"),
            hide_index=True,
            width="stretch",
        )
    sin_car = tabla[tabla[Columna.CAR_FUENTE] == FuenteCar.NO_IDENTIFICADA]
    if not sin_car.empty:
        st.markdown("Ubicaciones sin CAR automática (requieren selección manual)")
        st.dataframe(
            sin_car[Columna.UBICACION].value_counts().rename_axis("Ubicación").reset_index(name="Minifarms"),
            hide_index=True,
            width="stretch",
        )
    sin_flujo = tabla[tabla[Columna.CAR].notna() & ~tabla["car_con_flujo"]]
    if not sin_flujo.empty:
        st.markdown("CAR identificadas sin flujo configurado")
        st.dataframe(
            sin_flujo[Columna.CAR].value_counts().rename_axis("CAR").reset_index(name="Minifarms"),
            hide_index=True,
            width="stretch",
        )
    for e in carga.errores:
        st.caption(e)

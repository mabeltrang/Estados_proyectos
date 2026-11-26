"""Listado de proyectos con filtros y detalle editable de cada Minifarm."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from config.constantes import Columna, FuenteCar, Semaforo
from config.flujos import FLUJOS, cars_con_flujo, obtener_flujo
from core.almacenamiento import Seguimiento, ahora_texto, calcular_cambios
from core.fechas import dias_entre, formato_fecha, hoy_colombia
from core.prediccion import validar_fechas
from core.proyectos import identificar_car
from config import ajustes
from ui.componentes import avances, tarjeta_cuenta_regresiva, tarjeta_resolucion, texto_semaforo
from ui.datos import CLAVE_SEGUIMIENTOS, almacen, aviso_almacen, seguimientos, tablero

CLAVE_SELECCION = "_minifarm_seleccionada"

st.title("Proyectos")
t = tablero()
if t.error_api:
    st.error(f"No fue posible leer los proyectos: {t.error_api}")
    st.stop()
aviso_almacen()
df = t.tabla
if df.empty:
    st.info("La API no devolvió proyectos.")
    st.stop()

# ── Filtros ──────────────────────────────────────────────────────────────────
f1, f2, f3, f4 = st.columns([1, 1, 1, 1.3])
sel_car = f1.multiselect("CAR", sorted(df[Columna.CAR].fillna("Sin identificar").unique()))
sel_mun = f2.multiselect("Municipio", sorted(df[Columna.MUNICIPIO].fillna("").unique()))
sel_etapa = f3.multiselect("Estado", sorted(df["etapa_actual"].replace("", "Sin registrar").unique()))
buscar = f4.text_input("Proyecto", placeholder="Buscar por nombre comercial")

vista = df.copy()
if sel_car:
    vista = vista[vista[Columna.CAR].fillna("Sin identificar").isin(sel_car)]
if sel_mun:
    vista = vista[vista[Columna.MUNICIPIO].isin(sel_mun)]
if sel_etapa:
    vista = vista[vista["etapa_actual"].replace("", "Sin registrar").isin(sel_etapa)]
if buscar:
    vista = vista[vista[Columna.NOMBRE].str.contains(buscar, case=False, na=False, regex=False)]

listado = pd.DataFrame(
    {
        "Semáforo": vista["semaforo"].map(lambda s: texto_semaforo(Semaforo(s))),
        "Proyecto": vista[Columna.NOMBRE],
        "Municipio": vista[Columna.MUNICIPIO],
        "CAR": vista[Columna.CAR].fillna("—"),
        "Estado actual": vista["etapa_actual"].replace("", "Sin registrar"),
        "Siguiente hito": vista["siguiente_etapa"],
        "Resolución probable": vista["resolucion_probable"],
    }
)
evento = st.dataframe(
    listado,
    hide_index=True,
    width="stretch",
    on_select="rerun",
    selection_mode="single-row",
    column_config={"Resolución probable": st.column_config.DateColumn(format="DD/MM/YYYY")},
)
st.caption(f"{len(vista)} de {len(df)} proyectos. Selecciona una fila para ver el detalle.")

filas = evento.selection.rows if evento and evento.selection else []
if filas:
    st.session_state[CLAVE_SELECCION] = str(vista.iloc[filas[0]][Columna.MINIFARM_ID])
mid = st.session_state.get(CLAVE_SELECCION)
if not mid or mid not in set(df[Columna.MINIFARM_ID].astype(str)):
    st.stop()

# ── Detalle ──────────────────────────────────────────────────────────────────
fila = df[df[Columna.MINIFARM_ID].astype(str) == mid].iloc[0]
seg_actual = seguimientos().get(mid)
hoy = hoy_colombia()

st.divider()
st.header(str(fila[Columna.NOMBRE]))
st.caption(f"Terreno {fila[Columna.TERRENO_NOMBRE]} · {fila[Columna.UBICACION]}")

info, car_col = st.columns([1.2, 1])
with info:
    with st.container(border=True):
        st.markdown("**Proyecto**")
        datos = {
            "Minifarm": fila[Columna.MINIFARM_ID],
            "Project id": fila[Columna.PROJECT_ID],
            "Terreno (id)": f"{fila[Columna.TERRENO_NOMBRE]} ({fila[Columna.TERRENO_ID]})",
            "Árboles": fila[Columna.ARBOLES],
            "Etapa en la API": fila[Columna.ETAPA_API],
            "Licencia forestal": fila[Columna.LICENCIA],
            "Resolución de licencia": fila[Columna.RESOLUCION_LICENCIA],
            "Operador de red": fila[Columna.OPERADOR_RED],
        }
        st.markdown("\n".join(f"- {k}: {v or '—'}" for k, v in datos.items()))

with car_col:
    with st.container(border=True):
        st.markdown("**Autoridad ambiental**")
        car_auto, mensaje = identificar_car(str(fila[Columna.MUNICIPIO]), str(fila[Columna.DEPARTAMENTO]))
        st.caption(mensaje)
        if car_auto and car_auto not in FLUJOS:
            st.warning(f"{car_auto} no tiene flujo configurado en config/flujos.py.")
        opcion_auto = f"Automática ({car_auto})" if car_auto else "Sin identificar"
        opciones = [opcion_auto, *cars_con_flujo()]
        manual = seg_actual.car_manual if seg_actual else ""
        indice = opciones.index(manual) if manual in opciones else 0
        eleccion = st.selectbox("CAR del trámite", opciones, index=indice, key=f"car_{mid}")
        car_manual = "" if eleccion == opcion_auto else eleccion
        car = car_manual or car_auto
        if fila[Columna.CAR_FUENTE] == FuenteCar.NO_IDENTIFICADA and not car_manual:
            st.info("Selecciona la CAR para poder hacer el seguimiento.")

flujo = obtener_flujo(car)
if not flujo:
    st.stop()

# ── Estado y fechas (se guardan en Google Sheets, nunca en la API) ───────────
nombres = [e.nombre for e in flujo]
fechas_previas = {k: v for k, v in (seg_actual.fechas if seg_actual else {}).items() if k in nombres}
with st.form(f"form_{mid}_{car}"):
    st.markdown("**Estado del trámite**")
    etapa_previa = seg_actual.etapa_actual if seg_actual and seg_actual.etapa_actual in nombres else None
    etapa = st.selectbox(
        "Etapa actual (la última que ya ocurrió)",
        nombres,
        index=nombres.index(etapa_previa) if etapa_previa else None,
        placeholder="Selecciona la etapa",
    )
    st.caption(
        "Fechas en que ocurrió cada etapa. Llena solo las que conozcas; la fecha de hoy no se asume. "
        "Las marcadas con ⏱ tienen histórico y mueven la cuenta regresiva."
    )
    columnas = st.columns(3)
    nuevas: dict[str, date] = {}
    for i, e in enumerate(flujo):
        valor = columnas[i % 3].date_input(
            f"{'⏱ ' if e.hito else ''}{e.nombre}",
            value=fechas_previas.get(e.nombre),
            max_value=hoy,
            format="DD/MM/YYYY",
            key=f"f_{mid}_{car}_{i}",
        )
        if isinstance(valor, date):
            nuevas[e.nombre] = valor
    guardar = st.form_submit_button("Guardar", type="primary")

if guardar:
    errores = [] if etapa else ["Selecciona la etapa actual."]
    errores += validar_fechas(car, etapa, nuevas, hoy)
    if errores:
        st.error("No se guardó:\n\n" + "\n".join(f"- {e}" for e in errores))
    else:
        nuevo = Seguimiento(
            minifarm_id=mid,
            nombre=str(fila[Columna.NOMBRE]),
            car_manual=car_manual,
            etapa_actual=etapa or "",
            fechas=nuevas,
            actualizado_en=ahora_texto(),
        )
        cambios = calcular_cambios(seg_actual, nuevo)
        if not cambios:
            st.info("No hay cambios para guardar.")
        else:
            try:
                almacen().guardar(nuevo, car or "", cambios)
            except Exception as exc:
                st.error(f"No se pudo guardar ({type(exc).__name__}). Intenta de nuevo.")
            else:
                st.session_state[CLAVE_SEGUIMIENTOS][mid] = nuevo
                st.toast("Seguimiento guardado", icon="✅")
                st.rerun()

# ── Proyección ───────────────────────────────────────────────────────────────
pred = t.predicciones.get(mid)
car_guardada = seg_actual.car_manual if seg_actual else ""
if pred is not None and car_guardada == car_manual:
    a, b = st.columns(2)
    with a:
        tarjeta_cuenta_regresiva(pred)
    with b:
        tarjeta_resolucion(pred)
    avances(pred)
    for aviso in pred.avisos:
        st.caption(f"ℹ️ {aviso}")
else:
    st.info("Guarda la CAR elegida para recalcular la proyección.")

if fechas_previas:
    st.markdown("**Historial de etapas**")
    filas_hist = []
    anterior: date | None = None
    for e in flujo:
        f = fechas_previas.get(e.nombre)
        if f is None:
            continue
        filas_hist.append(
            {
                "Etapa": e.nombre,
                "Fecha": formato_fecha(f),
                "Días desde la anterior": dias_entre(anterior, f, ajustes.UNIDAD_DIAS) if anterior else None,
            }
        )
        anterior = f
    st.dataframe(pd.DataFrame(filas_hist), hide_index=True, width="stretch")
if seg_actual and seg_actual.actualizado_en:
    st.caption(f"Última actualización: {seg_actual.actualizado_en}")

"""Buscar un proyecto, ver su estado y volver a buscar otro.

La API solo se consulta cuando buscas (unas pocas consultas) y cuando abres un terreno (una consulta).
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from config import ajustes
from config.constantes import Columna
from config.flujos import FLUJOS, avance, cars_con_flujo, nombres_etapas, obtener_flujo
from core.almacenamiento import Seguimiento, ahora_texto, calcular_cambios
from core.api_unergy import ErrorApiUnergy
from core.fechas import dias_entre, formato_fecha, hoy_colombia
from core.prediccion import validar_fechas
from core.proyectos import identificar_car
from config.homologacion import estado_tsf, etapa_desde_tsf
from ui.componentes import (
    avances,
    encabezado,
    etiqueta_estado_unergy,
    tarjeta_cuenta_regresiva,
    tarjeta_resolucion,
)
from ui.datos import (
    CLAVE_SEGUIMIENTOS,
    almacen,
    aviso_almacen,
    proyectos_busqueda,
    minifarms_terreno,
    prediccion_de,
    seguimientos,
    tabla_seguimiento,
)

CLAVE_TERRENO = "_terreno_seleccionado"
CLAVE_MINIFARM = "_minifarm_seleccionada"
CLAVE_BUSQUEDA = "_texto_busqueda"        # widget (Streamlit lo borra al salir de la pantalla)
CLAVE_BUSQUEDA_GUARDADA = "_texto_busqueda_guardado"  # copia que sobrevive para poder volver
CLAVE_VERSION = "_version_tablas"  # cambia al volver, para que las tablas olviden la fila marcada


def abrir(terreno_id: str, minifarm_id: str | None = None) -> None:
    st.session_state[CLAVE_TERRENO] = str(terreno_id)
    st.session_state[CLAVE_MINIFARM] = str(minifarm_id) if minifarm_id else None


def ver_terreno(terreno_id: str) -> None:
    abrir(terreno_id)
    st.session_state[CLAVE_VERSION] = st.session_state.get(CLAVE_VERSION, 0) + 1


def volver() -> None:
    st.session_state[CLAVE_BUSQUEDA] = st.session_state.get(CLAVE_BUSQUEDA_GUARDADA, "")
    st.session_state[CLAVE_TERRENO] = None
    st.session_state[CLAVE_MINIFARM] = None
    st.session_state[CLAVE_VERSION] = st.session_state.get(CLAVE_VERSION, 0) + 1


def version() -> int:
    return int(st.session_state.get(CLAVE_VERSION, 0))


COLUMNA_AVANCE = st.column_config.ProgressColumn("Avance", min_value=0, max_value=100, format="%.0f%%")


class Origen:
    TSF = "TSF"
    MANUAL = "Manual"


def estado_de(mid: str, car_api: object, estado_api: str = "") -> tuple[str, str, str]:
    """(CAR efectiva, etapa, origen). La etapa sale de TSF si su homologación es clara;
    si no, de lo registrado a mano; si no hay ninguna, queda vacía."""
    seg = seguimientos().get(mid)
    car = (seg.car_manual or seg.car) if seg else ""
    car = car or (car_api if isinstance(car_api, str) else "")
    desde_tsf = etapa_desde_tsf(car, estado_api)
    if desde_tsf:
        return car, desde_tsf, Origen.TSF
    if seg and seg.etapa_actual in nombres_etapas(car):
        return car, seg.etapa_actual, Origen.MANUAL
    return car, "", ""


def vista_estados(tabla: pd.DataFrame, con_tsf_api: bool) -> pd.DataFrame:
    filas = []
    for _, f in tabla.iterrows():
        estado_api = str(f.get(Columna.ESTADO_FORESTAL.value, "") or "") if con_tsf_api else ""
        car, etapa, origen = estado_de(str(f[Columna.MINIFARM_ID.value]), f.get(Columna.CAR.value), estado_api)
        av = avance(car, etapa)
        fila = {"Proyecto": f[Columna.NOMBRE.value], "Terreno": f[Columna.TERRENO_NOMBRE.value],
                "CAR": car or "Sin identificar"}
        if con_tsf_api:
            fila["Estado TSF"] = estado_api or "No encontrado"
        fila.update(
            {
                "Estado homologado": etapa or "Sin homologación",
                "Origen": (origen if con_tsf_api else "Guardado") if etapa else "—",
                "Avance": None if av is None else round(av * 100),
            }
        )
        filas.append(fila)
    return pd.DataFrame(filas)


def fila_elegida(evento: object) -> int | None:
    filas = getattr(getattr(evento, "selection", None), "rows", None)
    return filas[0] if filas else None


# ── Pantalla 1: buscador y proyectos en seguimiento ──────────────────────────
def pantalla_busqueda() -> None:
    encabezado("Proyectos", "Busca un proyecto para ver o actualizar su estado ante la CAR.")
    aviso_almacen()
    texto = st.text_input(
        "Buscar proyecto",
        key=CLAVE_BUSQUEDA,
        placeholder="Nombre comercial, nombre del proyecto o del terreno",
    ).strip()
    st.session_state[CLAVE_BUSQUEDA_GUARDADA] = texto

    if len(texto) >= 2:
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
        st.caption(f"{len(resultados)} proyecto(s) en {min(n_terrenos, ajustes.BUSQUEDA_MAX_TERRENOS)} terreno(s). "
                   f"Selecciona uno para actualizar su estado.{extra}")
        evento = st.dataframe(
            vista_estados(resultados, con_tsf_api=True), hide_index=True, width="stretch", on_select="rerun",
            selection_mode="single-row", column_config={"Avance": COLUMNA_AVANCE},
            key=f"tabla_busqueda_{version()}",
        )
        for e in errores:
            st.caption(f"⚠️ {e}")
        i = fila_elegida(evento)
        if i is not None:
            f = resultados.iloc[i]
            abrir(f[Columna.TERRENO_ID.value], f[Columna.MINIFARM_ID.value])
            st.rerun()
        return

    st.subheader("Proyectos en seguimiento")
    tabla, _ = tabla_seguimiento()
    if tabla.empty:
        st.info("Busca un proyecto arriba para empezar su seguimiento.")
        return
    f1, f2 = st.columns(2)
    sel_car = f1.multiselect("CAR", sorted(tabla[Columna.CAR.value].replace("", "Sin identificar").unique()))
    sel_etapa = f2.multiselect("Estado", sorted(tabla["etapa_actual"].replace("", "Sin registrar").unique()))
    if sel_car:
        tabla = tabla[tabla[Columna.CAR.value].replace("", "Sin identificar").isin(sel_car)]
    if sel_etapa:
        tabla = tabla[tabla["etapa_actual"].replace("", "Sin registrar").isin(sel_etapa)]
    evento = st.dataframe(
        vista_estados(tabla, con_tsf_api=False), hide_index=True, width="stretch", on_select="rerun",
        selection_mode="single-row", column_config={"Avance": COLUMNA_AVANCE},
        key=f"tabla_seguimiento_{version()}",
    )
    st.caption("Selecciona una fila para ver el detalle, o escribe arriba para buscar otro proyecto.")
    i = fila_elegida(evento)
    if i is not None:
        fila = tabla.iloc[i]
        if not fila[Columna.TERRENO_ID.value]:
            st.warning("Este registro no tiene terreno guardado. Búscalo por nombre y guárdalo de nuevo.")
            return
        abrir(fila[Columna.TERRENO_ID.value], fila[Columna.MINIFARM_ID.value])
        st.rerun()


# ── Pantalla 2: proyectos (Minifarms) de un terreno ──────────────────────────
def cargar_terreno(terreno_id: str) -> pd.DataFrame | None:
    try:
        return minifarms_terreno(terreno_id)
    except ErrorApiUnergy as exc:
        st.error(f"No fue posible leer el terreno: {exc.mensaje}")
        return None


def pantalla_terreno(terreno_id: str) -> None:
    st.button("← Volver a la búsqueda", on_click=volver)
    tabla = cargar_terreno(terreno_id)
    if tabla is None:
        return
    if tabla.empty:
        st.info("Este terreno no tiene proyectos (Minifarms) en la API.")
        return
    if len(tabla) == 1:
        abrir(terreno_id, tabla.iloc[0][Columna.MINIFARM_ID.value])
        st.rerun()
    encabezado(
        str(tabla.iloc[0][Columna.TERRENO_NOMBRE.value]),
        f"{tabla.iloc[0][Columna.UBICACION.value]} · {len(tabla)} proyectos. Selecciona uno.",
        "🗺️",
    )
    vista = vista_estados(tabla, con_tsf_api=True).drop(columns=["Terreno"])
    evento = st.dataframe(
        vista, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        column_config={"Avance": COLUMNA_AVANCE},
        key=f"tabla_terreno_{terreno_id}_{version()}",
    )
    i = fila_elegida(evento)
    if i is not None:
        abrir(terreno_id, tabla.iloc[i][Columna.MINIFARM_ID.value])
        st.rerun()


# ── Pantalla 3: detalle editable de un proyecto ──────────────────────────────
def pantalla_detalle(terreno_id: str, mid: str) -> None:
    st.button("← Volver a la búsqueda", on_click=volver)
    tabla = cargar_terreno(terreno_id)
    if tabla is None:
        return
    coincide = tabla[tabla[Columna.MINIFARM_ID.value] == mid]
    if coincide.empty:
        st.warning("Este proyecto ya no aparece en el terreno consultado.")
        return
    fila = coincide.iloc[0]
    if len(tabla) > 1:
        st.button("← Otros proyectos de este terreno", on_click=ver_terreno, args=(terreno_id,))

    seg_actual = seguimientos().get(mid)
    hoy = hoy_colombia()

    encabezado(str(fila[Columna.NOMBRE.value]), f"Terreno {fila[Columna.TERRENO_NOMBRE.value]} · {fila[Columna.UBICACION.value]}")

    info, car_col = st.columns([1.2, 1])
    with info:
        with st.container(border=True):
            st.markdown("**Proyecto**")
            st.markdown(
                "Estado forestal (Unergy): " + etiqueta_estado_unergy(str(fila[Columna.ESTADO_FORESTAL.value])),
                unsafe_allow_html=True,
            )
            if fila[Columna.CAMPO_ESTADO.value]:
                st.caption(f"Leído del campo `{fila[Columna.CAMPO_ESTADO.value]}` de la API.")
            else:
                st.caption(
                    "La API no trae un estado forestal reconocible para este proyecto. "
                    "Usa «Explorar API → 3» para ubicar dónde viene."
                )
            datos = {
                "Minifarm": fila[Columna.MINIFARM_ID.value],
                "Project id": fila[Columna.PROJECT_ID.value],
                "Terreno (id)": f"{fila[Columna.TERRENO_NOMBRE.value]} ({fila[Columna.TERRENO_ID.value]})",
                "Árboles": fila[Columna.ARBOLES.value],
                "Estado general": fila[Columna.ETAPA_API.value],
                "Tipo de permiso": fila[Columna.TIPO_PERMISO.value],
                "Resolución de licencia": fila[Columna.RESOLUCION_LICENCIA.value],
                "Operador de red": fila[Columna.OPERADOR_RED.value],
            }
            st.markdown("\n".join(f"- {k}: {v or '—'}" for k, v in datos.items()))

    with car_col:
        with st.container(border=True):
            st.markdown("**Autoridad ambiental**")
            car_auto, mensaje = identificar_car(
                str(fila[Columna.MUNICIPIO.value]), str(fila[Columna.DEPARTAMENTO.value])
            )
            st.caption(mensaje)
            if car_auto and car_auto not in FLUJOS:
                st.warning(f"{car_auto} no tiene flujo configurado en config/flujos.py.")
            opcion_auto = f"Automática ({car_auto})" if car_auto else "Sin identificar"
            opciones = [opcion_auto, *cars_con_flujo()]
            manual = seg_actual.car_manual if seg_actual else ""
            eleccion = st.selectbox(
                "CAR del trámite", opciones, index=opciones.index(manual) if manual in opciones else 0,
                key=f"car_{mid}",
            )
            car_manual = "" if eleccion == opcion_auto else eleccion
            car = car_manual or car_auto
            if not car:
                st.info("Selecciona la CAR para poder hacer el seguimiento.")

    flujo = obtener_flujo(car)
    if not flujo:
        return

    nombres = [e.nombre for e in flujo]
    fechas_previas = {k: v for k, v in (seg_actual.fechas if seg_actual else {}).items() if k in nombres}
    with st.form(f"form_{mid}_{car}"):
        st.markdown("**Estado del trámite**")
        estado_api = str(fila[Columna.ESTADO_FORESTAL.value] or "")
        desde_tsf = etapa_desde_tsf(car, estado_api)
        etapa_previa = seg_actual.etapa_actual if seg_actual and seg_actual.etapa_actual in nombres else None
        etapa_mostrada = desde_tsf or etapa_previa
        etapa = st.selectbox(
            "Etapa actual (la última que ya ocurrió)", nombres,
            index=nombres.index(etapa_mostrada) if etapa_mostrada else None, placeholder="Selecciona la etapa",
            disabled=bool(desde_tsf),
        )
        if desde_tsf:
            st.caption(f"Tomada de TSF: «{estado_api}» equivale a «{desde_tsf}» en {car}. Se actualiza desde la plataforma.")
        else:
            if estado_api:
                st.caption(f"TSF: «{estado_api}» no tiene una homologación clara en {car}; registra la etapa a mano.")
            if etapa_previa:
                st.caption(f"En TSF corresponde a «{estado_tsf(car, etapa_previa)}».")
        st.caption(
            "Fechas en que ocurrió cada etapa. Llena solo las que conozcas; la fecha de hoy no se asume. "
            "Las marcadas con ⏱ tienen histórico y mueven la cuenta regresiva."
        )
        columnas = st.columns(3)
        nuevas: dict[str, date] = {}
        for i, e in enumerate(flujo):
            valor = columnas[i % 3].date_input(
                f"{'⏱ ' if e.hito else ''}{e.nombre}", value=fechas_previas.get(e.nombre),
                max_value=hoy, format="DD/MM/YYYY", key=f"f_{mid}_{car}_{i}",
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
                minifarm_id=mid, nombre=str(fila[Columna.NOMBRE.value]), car_manual=car_manual,
                etapa_actual=etapa or "", fechas=nuevas, actualizado_en=ahora_texto(), car=car or "",
                terreno_id=str(terreno_id), terreno_nombre=str(fila[Columna.TERRENO_NOMBRE.value]),
                ubicacion=str(fila[Columna.UBICACION.value]),
            )
            cambios = calcular_cambios(seg_actual, nuevo)
            if not cambios and seg_actual and seg_actual.terreno_id:
                st.info("No hay cambios para guardar.")
            else:
                try:
                    almacen().guardar(nuevo, cambios)
                except Exception as exc:
                    st.error(f"No se pudo guardar ({type(exc).__name__}). Intenta de nuevo.")
                else:
                    st.session_state[CLAVE_SEGUIMIENTOS][mid] = nuevo
                    st.toast("Seguimiento guardado", icon="✅")
                    st.rerun()

    if desde_tsf:  # la etapa de TSF manda; las fechas siguen siendo las registradas
        seg_pred = Seguimiento(mid, etapa_actual=desde_tsf, fechas=seg_actual.fechas if seg_actual else {})
    else:
        seg_pred = seg_actual
    pred = prediccion_de(car, seg_pred)
    avances(pred)
    with st.expander("Tiempos estimados (cuenta regresiva y resolución)"):
        a, b = st.columns(2)
        with a:
            tarjeta_cuenta_regresiva(pred)
        with b:
            tarjeta_resolucion(pred)
        for aviso in pred.avisos:
            st.caption(f"ℹ️ {aviso}")

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


# ── Enrutador de la página ───────────────────────────────────────────────────
terreno = st.session_state.get(CLAVE_TERRENO)
minifarm = st.session_state.get(CLAVE_MINIFARM)
if terreno and minifarm:
    pantalla_detalle(terreno, minifarm)
elif terreno:
    pantalla_terreno(terreno)
else:
    pantalla_busqueda()

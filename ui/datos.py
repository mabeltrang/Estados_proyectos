"""Une todo para la interfaz: API (con caché), histórico, seguimiento guardado y predicciones."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import streamlit as st

from config import ajustes
from config.constantes import Columna, SecretKey
from config.flujos import FLUJOS
from core.almacenamiento import Almacen, GoogleSheetsAlmacen, MemoriaAlmacen, Seguimiento
from core.api_unergy import ClienteUnergy, ErrorApiUnergy
from core.estadisticas import BaseTiempos
from core.fechas import hoy_colombia
from core.historico import HistoricoCargado, cargar_historico
from core.prediccion import Prediccion, predecir
from core.proyectos import (
    COLUMNAS_PROYECTO,
    ProyectosCargados,
    a_texto,
    asignar_car,
    cargar_proyectos,
    identificar_car,
    minifarms_de_terreno,
    separar_ubicacion,
)

CLAVE_ALMACEN_MEMORIA = "_almacen_memoria"
CLAVE_SEGUIMIENTOS = "_seguimientos"
CLAVE_ERROR_ALMACEN = "_error_almacen"


# ── Secrets ──────────────────────────────────────────────────────────────────
def leer_seccion(seccion: SecretKey) -> dict[str, object]:
    try:
        valor = st.secrets.get(seccion.value)
    except Exception:  # no existe secrets.toml
        return {}
    return dict(valor) if valor else {}


def crear_cliente() -> ClienteUnergy:
    conf = leer_seccion(SecretKey.SECCION_UNERGY)
    return ClienteUnergy(
        base_url=str(conf.get(SecretKey.BASE_URL.value) or ajustes.API_BASE_URL_POR_DEFECTO),
        api_key=str(conf.get(SecretKey.API_KEY.value) or ""),
        timeout=ajustes.API_TIMEOUT_SEGUNDOS,
        reintentos=ajustes.API_REINTENTOS,
    )


# ── API (todo bajo demanda: nada se descarga hasta que se busca) ────────────
# Cambia cuando cambian las columnas de las tablas. Al ser parte de la llave de la caché, una
# actualización del código nunca reutiliza tablas guardadas con el formato anterior.
ESQUEMA = "|".join(str(c) for c in COLUMNAS_PROYECTO)


def buscar_terrenos(texto: str) -> pd.DataFrame:
    return _buscar_terrenos(texto, ESQUEMA)


def minifarms_terreno(terreno_id: str) -> pd.DataFrame:
    tabla = _minifarms_terreno(terreno_id, ESQUEMA)
    faltan = [str(c) for c in COLUMNAS_PROYECTO if str(c) not in tabla.columns]
    return tabla.assign(**{c: "" for c in faltan}) if faltan else tabla


def proyectos_busqueda(texto: str) -> tuple[pd.DataFrame, int, list[str]]:
    """Proyectos (Minifarms) de los terrenos que coinciden con la búsqueda.
    Devuelve (tabla, terrenos encontrados, errores)."""
    return _proyectos_busqueda(texto, ESQUEMA)


@st.cache_data(ttl=ajustes.CACHE_BUSQUEDA_SEGUNDOS, show_spinner="Cargando los proyectos encontrados…")
def _proyectos_busqueda(texto: str, esquema: str) -> tuple[pd.DataFrame, int, list[str]]:
    terrenos = _buscar_terrenos(texto, esquema)
    ids = list(terrenos[Columna.TERRENO_ID.value])[: ajustes.BUSQUEDA_MAX_TERRENOS]
    cliente = crear_cliente()
    errores: list[str] = []

    def traer(terreno_id: str) -> list[dict[str, object]]:
        try:
            return minifarms_de_terreno(cliente.detalle_forestal(terreno_id))
        except ErrorApiUnergy as exc:
            errores.append(f"Terreno {terreno_id}: {exc.mensaje}")
            return []

    filas: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=ajustes.API_HILOS_DETALLE) as pool:
        for resultado in pool.map(traer, ids):
            filas.extend(resultado)
    tabla = pd.DataFrame(filas, columns=COLUMNAS_PROYECTO)
    tabla.columns = [str(c) for c in tabla.columns]
    return asignar_car(tabla, {}), len(terrenos), errores


@st.cache_data(ttl=ajustes.CACHE_BUSQUEDA_SEGUNDOS, show_spinner="Buscando en la API de Unergy…")
def _buscar_terrenos(texto: str, esquema: str) -> pd.DataFrame:
    """Busca por nombre comercial (Minifarm), nombre de proyecto o terreno. Pocas consultas."""
    cliente = crear_cliente()
    filas: list[dict[str, object]] = []
    for pagina in range(1, ajustes.BUSQUEDA_MAX_PAGINAS + 1):
        datos = cliente.listar_forestal(pagina=pagina, page_size=ajustes.API_PAGE_SIZE, buscar=texto)
        for t in datos.get("results", []):  # type: ignore[union-attr]
            if not isinstance(t, dict) or t.get("id") is None:
                continue
            ubicacion = a_texto(t.get("location"))
            municipio, departamento = separar_ubicacion(ubicacion)
            car, _ = identificar_car(municipio, departamento)
            filas.append(
                {
                    Columna.TERRENO_ID.value: str(t.get("id")),
                    Columna.TERRENO_NOMBRE.value: a_texto(t.get("name")),
                    Columna.UBICACION.value: ubicacion,
                    Columna.CAR.value: car or "",
                }
            )
        if not datos.get("next"):
            break
    return pd.DataFrame(
        filas, columns=[Columna.TERRENO_ID.value, Columna.TERRENO_NOMBRE.value, Columna.UBICACION.value, Columna.CAR.value]
    )


@st.cache_data(ttl=ajustes.CACHE_BUSQUEDA_SEGUNDOS, show_spinner="Cargando proyectos del terreno…")
def _minifarms_terreno(terreno_id: str, esquema: str) -> pd.DataFrame:
    detalle = crear_cliente().detalle_forestal(terreno_id)
    tabla = pd.DataFrame(minifarms_de_terreno(detalle), columns=COLUMNAS_PROYECTO)
    tabla.columns = [str(c) for c in tabla.columns]
    return asignar_car(tabla, {})


@st.cache_data(ttl=ajustes.CACHE_API_SEGUNDOS, show_spinner="Consultando todos los terrenos (puede tardar varios minutos)…")
def proyectos_api() -> ProyectosCargados:
    """Recorre TODOS los terrenos y su detalle. Solo se usa en «Explorar API»."""
    return cargar_proyectos(
        crear_cliente(), ajustes.API_PAGE_SIZE, ajustes.API_MAX_PAGINAS, ajustes.API_HILOS_DETALLE
    )


# ── Histórico ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Leyendo histórico de las CAR…")
def historico(marca_archivo: float, hoy_iso: str) -> HistoricoCargado:
    from datetime import date

    return cargar_historico(
        ajustes.RUTA_HISTORICO,
        ajustes.COLUMNAS_FECHA_HISTORICO,
        ajustes.COLUMNAS_TEXTO_HISTORICO,
        ajustes.CATEGORIAS_HISTORICO,
        ajustes.CARS_HISTORICO_EXCLUIDAS,
        ajustes.FECHA_MINIMA_VALIDA,
        date.fromisoformat(hoy_iso),
    )


def historico_actual() -> HistoricoCargado:
    return historico(ajustes.RUTA_HISTORICO.stat().st_mtime, hoy_colombia().isoformat())


@st.cache_resource(show_spinner=False)
def _base_tiempos(marca: float, hoy_iso: str, unidad: str) -> BaseTiempos:
    return BaseTiempos(historico_actual().tramites, ajustes.UNIDAD_DIAS)


def base_tiempos() -> BaseTiempos:
    return _base_tiempos(ajustes.RUTA_HISTORICO.stat().st_mtime, hoy_colombia().isoformat(), ajustes.UNIDAD_DIAS)


# ── Almacenamiento del seguimiento ───────────────────────────────────────────
@st.cache_resource(show_spinner="Conectando con Google Sheets…")
def _almacen_sheets(url: str) -> GoogleSheetsAlmacen:
    return GoogleSheetsAlmacen(leer_seccion(SecretKey.SECCION_CUENTA_SERVICIO), url)


def almacen() -> Almacen:
    url = str(leer_seccion(SecretKey.SECCION_GSHEETS).get(SecretKey.SPREADSHEET_URL.value) or "")
    if url and leer_seccion(SecretKey.SECCION_CUENTA_SERVICIO):
        try:
            return _almacen_sheets(url)
        except Exception as exc:  # credenciales mal pegadas, hoja no compartida, etc.
            st.session_state[CLAVE_ERROR_ALMACEN] = (
                f"No se pudo abrir el Google Sheet ({type(exc).__name__}). Revisa que la hoja esté "
                "compartida con el correo de la cuenta de servicio y que los Secrets estén completos."
            )
    if CLAVE_ALMACEN_MEMORIA not in st.session_state:
        st.session_state[CLAVE_ALMACEN_MEMORIA] = MemoriaAlmacen()
    return st.session_state[CLAVE_ALMACEN_MEMORIA]


def seguimientos(recargar: bool = False) -> dict[str, Seguimiento]:
    if recargar or CLAVE_SEGUIMIENTOS not in st.session_state:
        st.session_state[CLAVE_SEGUIMIENTOS] = almacen().cargar()
    return st.session_state[CLAVE_SEGUIMIENTOS]


def aviso_almacen() -> None:
    error = st.session_state.get(CLAVE_ERROR_ALMACEN)
    if error:
        st.error(error, icon="⚠️")
    if not almacen().persistente:
        st.warning(
            "Google Sheets no está configurado: los estados y fechas que registres se perderán al "
            "reiniciar la app. Ver README → «Guardar el seguimiento».",
            icon="💾",
        )


# ── Predicción y tabla de proyectos en seguimiento ───────────────────────────
def car_de(seg: Seguimiento) -> str | None:
    car = seg.car_manual or seg.car
    return car if car in FLUJOS else None


def prediccion_de(car: str | None, seg: Seguimiento | None) -> Prediccion:
    return predecir(
        car,
        seg.etapa_actual if seg and seg.etapa_actual else None,
        seg.fechas if seg else {},
        hoy_colombia(),
        base_tiempos(),
        ajustes.MIN_ANTECEDENTES,
        ajustes.UNIDAD_DIAS,
    )


def tabla_seguimiento() -> tuple[pd.DataFrame, dict[str, Prediccion]]:
    """Proyectos que ya tienen seguimiento guardado. No consulta la API."""
    filas: list[dict[str, object]] = []
    predicciones: dict[str, Prediccion] = {}
    for mid, seg in seguimientos().items():
        car = car_de(seg)
        pred = prediccion_de(car, seg)
        predicciones[mid] = pred
        municipio, _ = separar_ubicacion(seg.ubicacion)
        filas.append(
            {
                Columna.MINIFARM_ID.value: mid,
                Columna.NOMBRE.value: seg.nombre,
                Columna.TERRENO_ID.value: seg.terreno_id,
                Columna.TERRENO_NOMBRE.value: seg.terreno_nombre,
                Columna.UBICACION.value: seg.ubicacion,
                Columna.MUNICIPIO.value: municipio,
                Columna.CAR.value: car or "",
                "etapa_actual": seg.etapa_actual,
                "siguiente_etapa": pred.siguiente_etapa or "",
                "semaforo": pred.semaforo,
                "resolucion_probable": pred.resolucion.probable if pred.resolucion else None,
            }
        )
    columnas = [
        Columna.MINIFARM_ID.value, Columna.NOMBRE.value, Columna.TERRENO_ID.value, Columna.TERRENO_NOMBRE.value,
        Columna.UBICACION.value, Columna.MUNICIPIO.value, Columna.CAR.value, "etapa_actual", "siguiente_etapa",
        "semaforo", "resolucion_probable",
    ]
    return pd.DataFrame(filas, columns=columnas), predicciones

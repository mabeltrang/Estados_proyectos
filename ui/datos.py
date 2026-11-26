"""Une todo para la interfaz: API (con caché), histórico, seguimiento guardado y predicciones."""

from __future__ import annotations

from dataclasses import dataclass

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
from core.proyectos import ProyectosCargados, asignar_car, cargar_proyectos

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


# ── API ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=ajustes.CACHE_API_SEGUNDOS, show_spinner="Consultando proyectos en la API de Unergy…")
def proyectos_api() -> ProyectosCargados:
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


# ── Tabla combinada ──────────────────────────────────────────────────────────
@dataclass
class Tablero:
    tabla: pd.DataFrame          # una fila por Minifarm
    predicciones: dict[str, Prediccion]
    carga: ProyectosCargados | None
    error_api: str | None


def tablero() -> Tablero:
    try:
        carga = proyectos_api()
    except ErrorApiUnergy as exc:
        return Tablero(pd.DataFrame(), {}, None, exc.mensaje)

    seg = seguimientos()
    tabla = asignar_car(carga.tabla, {k: v.car_manual for k, v in seg.items() if v.car_manual})
    base = base_tiempos()
    hoy = hoy_colombia()
    predicciones: dict[str, Prediccion] = {}
    etapas: list[str] = []
    for _, fila in tabla.iterrows():
        mid = str(fila[Columna.MINIFARM_ID])
        s = seg.get(mid)
        etapa = s.etapa_actual if s else ""
        car = fila[Columna.CAR] if isinstance(fila[Columna.CAR], str) else None
        if car not in FLUJOS:
            etapa = ""
        etapas.append(etapa)
        predicciones[mid] = predecir(
            car, etapa or None, s.fechas if s else {}, hoy, base, ajustes.MIN_ANTECEDENTES, ajustes.UNIDAD_DIAS
        )
    tabla["etapa_actual"] = etapas
    tabla["semaforo"] = [predicciones[str(m)].semaforo for m in tabla[Columna.MINIFARM_ID]]
    tabla["siguiente_etapa"] = [predicciones[str(m)].siguiente_etapa or "" for m in tabla[Columna.MINIFARM_ID]]
    tabla["resolucion_probable"] = [
        p.resolucion.probable if (p := predicciones[str(m)]).resolucion else None for m in tabla[Columna.MINIFARM_ID]
    ]
    return Tablero(tabla, predicciones, carga, None)

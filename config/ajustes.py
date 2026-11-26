"""Ajustes que se pueden cambiar sin tocar la lógica."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from config.constantes import Columna, Hito, UnidadDias

RAIZ = Path(__file__).resolve().parent.parent

# ── Histórico ────────────────────────────────────────────────────────────────
RUTA_HISTORICO = RAIZ / "data" / "Fechas_CARS.xlsx"

# Cuántos expedientes mínimos debe tener una CAR en un tramo para usar su propio histórico.
# Por debajo de esto se usa con advertencia ("histórico limitado").
MIN_ANTECEDENTES = 5

# Días calendario por defecto. Cambiar a UnidadDias.HABILES para lunes a viernes (sin festivos).
UNIDAD_DIAS = UnidadDias.CALENDARIO

# Solo se usan estos trámites del Excel para calcular tiempos.
CATEGORIAS_HISTORICO: tuple[str, ...] = ("Aprovechamiento forestal",)

# CAR que están en el Excel pero no se usan por ahora (ni propias ni en la referencia general).
CARS_HISTORICO_EXCLUIDAS: frozenset[str] = frozenset({"CORPOBOYACA", "CAR"})

# Fechas por fuera de este rango se reportan como imposibles y no se usan.
FECHA_MINIMA_VALIDA = date(2000, 1, 1)

# Encabezados del Excel aceptados para cada dato. La comparación ignora tildes, mayúsculas y
# espacios sobrantes, así que "Solicitud liquidacion " y "Solicitud liquidación" valen igual.
# Si cambias un encabezado en el Excel, agrégalo aquí; no hace falta tocar el resto del código.
COLUMNAS_FECHA_HISTORICO: dict[Hito, tuple[str, ...]] = {
    Hito.SOLICITUD_LIQUIDACION: ("Solicitud liquidacion", "Solicitud de liquidacion"),
    Hito.RADICADO: ("Fecha radicado inicio tramite", "Fecha radicado", "Fecha radicacion"),
    Hito.AUTO: ("Fecha auto",),
    Hito.VISITA: ("Fecha visita",),
    Hito.RESOLUCION: ("Fecha resolucion",),
}

COLUMNAS_TEXTO_HISTORICO: dict[Columna, tuple[str, ...]] = {
    Columna.CAR: ("CAR", "Autoridad ambiental"),
    Columna.CATEGORIA: ("Categoria Tramite", "Categoria"),
    Columna.TITULAR: ("Titular",),
    Columna.ARCHIVO: ("Archivo",),
    Columna.TIPO_ACTO: ("Tipo",),
}

# ── API de Unergy ────────────────────────────────────────────────────────────
# Campo de cada Minifarm de donde se lee el «Estado forestal» de TSF (columna A. FORESTAL).
# Solo se muestra si el valor es un estado de TSF; si no, aparece «No encontrado».
# `forestry_licence` NO es el estado: es el tipo de permiso ("Licencia de aprovechamiento forestal").
CAMPOS_ESTADO_FORESTAL: tuple[str, ...] = ("forestry_license_resolution",)
API_BASE_URL_POR_DEFECTO = "https://originabot.uner.gy"
API_PAGE_SIZE = 100
API_TIMEOUT_SEGUNDOS = 20
API_REINTENTOS = 1
API_MAX_PAGINAS = 500
API_HILOS_DETALLE = 6

# Páginas máximas que se traen en una búsqueda (100 terrenos por página).
BUSQUEDA_MAX_PAGINAS = 3
# Máximo de terrenos de una búsqueda cuyos proyectos se cargan de una vez (una consulta por terreno).
BUSQUEDA_MAX_TERRENOS = 25

# Cada cuánto se vuelven a pedir los datos a la API (segundos).
CACHE_API_SEGUNDOS = 60 * 60
CACHE_BUSQUEDA_SEGUNDOS = 10 * 60

# ── Dashboard ────────────────────────────────────────────────────────────────
# "Próximo a resolución": la fecha probable de resolución cae dentro de estos días.
DIAS_PROXIMO_A_RESOLUCION = 45

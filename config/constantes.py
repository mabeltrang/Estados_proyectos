"""Valores fijos del proyecto: hitos, semáforo, fuentes de predicción, rutas de la API y claves de Secrets.

Todo valor que se repita en el código vive aquí para no escribirlo a mano en varios sitios.
"""

from __future__ import annotations

from enum import StrEnum


class Hito(StrEnum):
    """Hitos que tienen fecha en el histórico (Excel). Son los únicos con los que se pueden
    calcular tiempos. Cada etapa de un flujo puede apuntar a uno de estos hitos o a ninguno."""

    SOLICITUD_LIQUIDACION = "solicitud_liquidacion"
    RADICADO = "radicado"
    AUTO = "auto"
    VISITA = "visita"
    RESOLUCION = "resolucion"


# Orden natural de los hitos dentro de un trámite.
ORDEN_HITOS: tuple[Hito, ...] = (
    Hito.SOLICITUD_LIQUIDACION,
    Hito.RADICADO,
    Hito.AUTO,
    Hito.VISITA,
    Hito.RESOLUCION,
)

NOMBRE_HITO: dict[Hito, str] = {
    Hito.SOLICITUD_LIQUIDACION: "Solicitud de liquidación",
    Hito.RADICADO: "Radicado",
    Hito.AUTO: "Auto",
    Hito.VISITA: "Visita",
    Hito.RESOLUCION: "Resolución",
}


class Semaforo(StrEnum):
    VERDE = "verde"
    AMARILLO = "amarillo"
    NARANJA = "naranja"
    ROJO = "rojo"
    SIN_DATO = "sin_dato"


SEMAFORO_EMOJI: dict[Semaforo, str] = {
    Semaforo.VERDE: "🟢",
    Semaforo.AMARILLO: "🟡",
    Semaforo.NARANJA: "🟠",
    Semaforo.ROJO: "🔴",
    Semaforo.SIN_DATO: "⚪",
}

SEMAFORO_COLOR: dict[Semaforo, str] = {
    Semaforo.VERDE: "#2E9E5B",
    Semaforo.AMARILLO: "#D9A400",
    Semaforo.NARANJA: "#E07A1F",
    Semaforo.ROJO: "#C8372D",
    Semaforo.SIN_DATO: "#9AA5A0",
}

SEMAFORO_TEXTO: dict[Semaforo, str] = {
    Semaforo.VERDE: "Dentro del escenario optimista",
    Semaforo.AMARILLO: "Dentro del tiempo típico",
    Semaforo.NARANJA: "Más lento que lo típico",
    Semaforo.ROJO: "Atrasado frente al histórico",
    Semaforo.SIN_DATO: "Sin datos para comparar",
}


class FuentePrediccion(StrEnum):
    PROPIO = "Histórico propio de la CAR"
    LIMITADO = "Histórico limitado de la CAR"
    GENERAL = "Referencia general (otras CAR)"
    SIN_DATOS = "Sin antecedentes"


class UnidadDias(StrEnum):
    CALENDARIO = "calendario"
    HABILES = "habiles"


class EstadoPrediccion(StrEnum):
    OK = "ok"
    SIN_ESTADO = "sin_estado"          # todavía no se ha registrado la etapa actual
    SIN_FLUJO = "sin_flujo"            # la CAR no tiene flujo configurado
    ANTES_DE_HITOS = "antes_de_hitos"  # aún no ha llegado al primer hito con histórico
    FALTA_FECHA = "falta_fecha"        # llegó a un hito pero no hay ninguna fecha registrada
    RESUELTO = "resuelto"


class Endpoint(StrEnum):
    """Rutas de SOLO LECTURA de la API de Unergy. `{id}` se reemplaza por el id del terreno."""

    FORESTAL_LISTA = "/api/roles/forest/"
    FORESTAL_DETALLE = "/api/roles/forest/{id}/"
    FORESTAL_ANEXOS = "/api/roles/forest/{id}/annexes/"
    AMBIENTAL_LISTA = "/api/roles/environmental/"
    AMBIENTAL_DETALLE = "/api/roles/environmental/{id}/"


# Prefijos a los que el cliente tiene permitido hacer GET. Cualquier otra ruta se rechaza.
PREFIJOS_API_PERMITIDOS: tuple[str, ...] = ("/api/roles/forest/", "/api/roles/environmental/")


class SecretKey(StrEnum):
    """Nombres de las secciones y claves en .streamlit/secrets.toml (o en Secrets de Streamlit Cloud)."""

    SECCION_UNERGY = "unergy"
    API_KEY = "api_key"
    BASE_URL = "base_url"
    SECCION_GSHEETS = "gsheets"
    SPREADSHEET_URL = "spreadsheet_url"
    SECCION_CUENTA_SERVICIO = "gcp_service_account"
    SECCION_APP = "app"
    PASSWORD = "password"


class Hoja(StrEnum):
    """Pestañas del Google Sheet donde se guarda el seguimiento manual."""

    SEGUIMIENTO = "seguimiento"
    FECHAS = "fechas_etapas"
    HISTORIAL = "historial_cambios"


class Columna(StrEnum):
    """Columnas internas (canónicas) de las tablas de proyectos y del histórico."""

    MINIFARM_ID = "minifarm_id"
    PROJECT_ID = "project_id"
    NOMBRE = "nombre"
    TERRENO_ID = "terreno_id"
    TERRENO_NOMBRE = "terreno_nombre"
    UBICACION = "ubicacion"
    MUNICIPIO = "municipio"
    DEPARTAMENTO = "departamento"
    CAR = "car"
    CAR_FUENTE = "car_fuente"
    ETAPA_API = "etapa_api"
    ARBOLES = "arboles"
    ESTADO_FORESTAL = "estado_forestal"
    CAMPO_ESTADO = "campo_estado_forestal"   # de qué campo de la API salió el estado
    TIPO_PERMISO = "tipo_permiso"            # forestry_licence (ej. "Licencia de aprovechamiento forestal")
    RESOLUCION_LICENCIA = "resolucion_licencia"
    OPERADOR_RED = "operador_red"
    # histórico
    HOJA = "hoja"
    FILA_EXCEL = "fila_excel"
    TITULAR = "titular"
    TITULAR_CLAVE = "titular_clave"
    CATEGORIA = "categoria"
    ARCHIVO = "archivo"
    TIPO_ACTO = "tipo_acto"


class FuenteCar(StrEnum):
    MANUAL = "manual"
    AUTOMATICA = "automatica"
    NO_IDENTIFICADA = "no_identificada"

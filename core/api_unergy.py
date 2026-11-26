"""Cliente de SOLO LECTURA para la API de Unergy (/api/roles/).

Garantías de seguridad:
- Solo existe un método de red: `_get`. No hay POST, PUT, PATCH ni DELETE en ningún lugar.
- La sesión HTTP se envuelve en `_SesionSoloLectura`, que únicamente expone `get`.
- Solo se aceptan rutas que empiecen por los prefijos de PREFIJOS_API_PERMITIDOS.
- La API Key viaja solo en el header; nunca se incluye en mensajes de error ni en logs.
"""

from __future__ import annotations

import re
import time
from typing import Protocol

import requests

from config.constantes import PREFIJOS_API_PERMITIDOS, Endpoint

JsonObj = dict[str, object]


class ErrorApiUnergy(Exception):
    """Error con un mensaje apto para mostrar al usuario (sin datos sensibles)."""

    def __init__(self, mensaje: str, status: int | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status = status


class _RespuestaHttp(Protocol):
    status_code: int

    def json(self) -> object: ...


class _ClienteHttp(Protocol):
    def get(self, url: str, *, headers: dict[str, str], params: dict[str, object] | None,
            timeout: float) -> _RespuestaHttp: ...


class _SesionSoloLectura:
    """Expone únicamente GET sobre una sesión de requests."""

    def __init__(self, sesion: requests.Session | None = None) -> None:
        self.__sesion = sesion or requests.Session()

    def get(self, url: str, *, headers: dict[str, str], params: dict[str, object] | None,
            timeout: float) -> requests.Response:
        return self.__sesion.get(url, headers=headers, params=params, timeout=timeout)


MENSAJES_ERROR: dict[int, str] = {
    401: "La API Key es inválida o no está configurada (401).",
    403: "La API Key no tiene permiso para esta ruta (403). Pide acceso a /api/roles/forest/ y /api/roles/environmental/.",
    404: "No se encontró el recurso solicitado (404).",
}


class ClienteUnergy:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 25,
        reintentos: int = 2,
        http: _ClienteHttp | None = None,
    ) -> None:
        if not api_key:
            raise ErrorApiUnergy("No hay API Key configurada en los Secrets de Streamlit.")
        self._base = base_url.rstrip("/")
        self._headers = {"X-API-Key": api_key, "Accept": "application/json"}
        self._timeout = timeout
        self._reintentos = reintentos
        self._http: _ClienteHttp = http or _SesionSoloLectura()

    # ── único punto de acceso a la red ──────────────────────────────────────
    def _get(self, ruta: str, params: dict[str, object] | None = None) -> object:
        if ".." in ruta or not ruta.startswith(PREFIJOS_API_PERMITIDOS):
            raise ErrorApiUnergy(f"Ruta no permitida para esta aplicación: {ruta}")
        url = f"{self._base}{ruta}"
        ultimo_error = "Error desconocido"
        for intento in range(self._reintentos + 1):
            try:
                resp = self._http.get(url, headers=self._headers, params=params, timeout=self._timeout)
            except requests.Timeout:
                ultimo_error = f"La API no respondió a tiempo ({self._timeout:.0f} s)."
            except requests.ConnectionError:
                ultimo_error = "No fue posible conectarse con la API de Unergy."
            else:
                if resp.status_code in MENSAJES_ERROR:
                    raise ErrorApiUnergy(MENSAJES_ERROR[resp.status_code], resp.status_code)
                if resp.status_code >= 500:
                    ultimo_error = f"Error interno del servidor de Unergy ({resp.status_code})."
                elif resp.status_code != 200:
                    raise ErrorApiUnergy(f"Respuesta inesperada de la API ({resp.status_code}).", resp.status_code)
                else:
                    try:
                        return resp.json()
                    except ValueError as exc:
                        raise ErrorApiUnergy("La API devolvió una respuesta que no es JSON.") from exc
            if intento < self._reintentos:
                time.sleep(1 + intento)
        raise ErrorApiUnergy(ultimo_error)

    # ── forestal ────────────────────────────────────────────────────────────
    def listar_forestal(self, pagina: int = 1, page_size: int = 100, buscar: str | None = None) -> JsonObj:
        params: dict[str, object] = {"page": pagina, "page_size": page_size}
        if buscar:
            params["search"] = buscar
        return _como_pagina(self._get(Endpoint.FORESTAL_LISTA.value, params))

    def listar_forestal_todo(self, page_size: int = 100, max_paginas: int = 500) -> list[JsonObj]:
        return self._recorrer(self.listar_forestal, page_size, max_paginas)

    def detalle_forestal(self, terreno_id: int | str) -> JsonObj:
        return _como_objeto(self._get(Endpoint.FORESTAL_DETALLE.value.format(id=_id_seguro(terreno_id))))

    def anexos_forestal(self, terreno_id: int | str) -> object:
        return self._get(Endpoint.FORESTAL_ANEXOS.value.format(id=_id_seguro(terreno_id)))

    # ── ambiental ───────────────────────────────────────────────────────────
    def listar_ambiental(self, pagina: int = 1, page_size: int = 100, buscar: str | None = None) -> JsonObj:
        params: dict[str, object] = {"page": pagina, "page_size": page_size}
        if buscar:
            params["search"] = buscar
        return _como_pagina(self._get(Endpoint.AMBIENTAL_LISTA.value, params))

    def detalle_ambiental(self, terreno_id: int | str) -> JsonObj:
        return _como_objeto(self._get(Endpoint.AMBIENTAL_DETALLE.value.format(id=_id_seguro(terreno_id))))

    def probar_conexion(self) -> int:
        """Devuelve el número de terrenos forestales si la conexión funciona."""
        pagina = self.listar_forestal(pagina=1, page_size=1)
        conteo = pagina.get("count")
        return int(conteo) if isinstance(conteo, int) else 0

    # ── utilidades ──────────────────────────────────────────────────────────
    @staticmethod
    def _recorrer(listar: object, page_size: int, max_paginas: int) -> list[JsonObj]:
        assert callable(listar)
        resultados: list[JsonObj] = []
        for pagina in range(1, max_paginas + 1):
            datos = listar(pagina=pagina, page_size=page_size)
            items = datos.get("results")
            if not isinstance(items, list):
                raise ErrorApiUnergy("La lista no trae el campo 'results' esperado.")
            resultados.extend(i for i in items if isinstance(i, dict))
            if not datos.get("next"):
                return resultados
        raise ErrorApiUnergy(f"Se alcanzó el límite de {max_paginas} páginas; revisa la paginación.")


def _id_seguro(valor: int | str) -> str:
    texto = str(valor).strip()
    if not re.fullmatch(r"[A-Za-z0-9-]+", texto):
        raise ErrorApiUnergy(f"Id de terreno no válido: {texto!r}")
    return texto


def _como_objeto(datos: object) -> JsonObj:
    if not isinstance(datos, dict):
        raise ErrorApiUnergy("La API devolvió un formato inesperado (se esperaba un objeto).")
    return datos


def _como_pagina(datos: object) -> JsonObj:
    obj = _como_objeto(datos)
    if "results" not in obj:
        raise ErrorApiUnergy(
            "La API no devolvió una lista paginada. Recuerda que sin 'page' devuelve solo un conteo."
        )
    return obj

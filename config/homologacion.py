"""Equivalencia entre las etapas de cada CAR (las de esta app) y los estados forestales de TSF
(la plataforma de donde la API toma los datos).

La app lee el estado de TSF (API) y lo traduce a la etapa del flujo de la CAR del proyecto:
- Si el estado corresponde a UNA sola etapa, la homologación es clara: esa etapa y su % de avance.
- Si corresponde a varias (ej. «Liquidación» en CARSUCRE: evaluación o tasa), no se elige ninguna:
  se muestran las posibles y el rango de avance.
- Si no corresponde a ninguna (ej. «Requerimientos»), queda «Sin homologación».

CÓMO EDITAR: cambia el estado TSF de una etapa en ETAPA_A_TSF. Si una CAR necesita algo distinto,
agrégalo en ETAPA_A_TSF_POR_CAR. Toda etapa de config/flujos.py debe tener equivalencia
(las pruebas lo verifican).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from config.flujos import avance, obtener_flujo

def normalizar_texto(valor: str) -> str:
    texto = "".join(c for c in unicodedata.normalize("NFKD", str(valor)) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


# Estados forestales de TSF, con el nombre exacto de la plataforma.
ESTADOS_UNERGY: tuple[str, ...] = (
    "Por radicar",
    "Solicitud radicada",
    "Liquidación",
    "Programado",
    "Visita",
    "Solicitud aprobada",
    "Requerimientos",
    "Respuesta a requerimientos",
    "Respuesta radicado",
    "Solicitud rechazada",
    "Exonerado",
    "Pausado",
)

ETAPA_A_TSF: dict[str, str] = {
    # «Programado» en TSF = el proyecto se mandó a inventario.
    "Inventario": "Programado",
    "Informes": "Por radicar",
    "Radicado": "Solicitud radicada",
    "Radicación": "Solicitud radicada",
    # Pagos: en TSF todos son «Liquidación» (puede ser la de evaluación/auto o la de la tasa).
    "Solicitud de liquidación": "Liquidación",
    "Liquidación servicios": "Liquidación",
    "Pago evaluación": "Liquidación",
    "Pagar la evaluación": "Liquidación",
    "Auto cobro": "Liquidación",
    "Pago visita y publicación auto": "Liquidación",
    "Pago tasa de aprovechamiento": "Liquidación",
    # TSF no tiene estado para autos ni publicaciones: el trámite sigue como radicado.
    "Llega auto": "Solicitud radicada",
    "Auto": "Solicitud radicada",
    "Auto inicio": "Solicitud radicada",
    "Publicación auto": "Solicitud radicada",
    "Publicación auto alcaldía": "Solicitud radicada",
    "Visita": "Visita",
    "Visita técnica": "Visita",
    "Acta": "Visita",
    "Resolución": "Solicitud aprobada",
}

# Excepciones por CAR: {"CAR": {"Etapa": "Estado TSF"}}
ETAPA_A_TSF_POR_CAR: dict[str, dict[str, str]] = {}

ALIAS: dict[str, str] = {
    "respuesta a requerimiento": "Respuesta a requerimientos",
    "liquidacion": "Liquidación",
}

_CANONICOS = {normalizar_texto(e): e for e in ESTADOS_UNERGY}


def estado_canonico(texto: str) -> str | None:
    clave = normalizar_texto(texto)
    return _CANONICOS.get(clave) or ALIAS.get(clave)


def estado_tsf(car: str | None, etapa: str | None) -> str:
    """Estado que debería tener el proyecto en TSF según la etapa registrada aquí."""
    if not etapa:
        return ""
    propio = ETAPA_A_TSF_POR_CAR.get(str(car or "").upper(), {})
    return propio.get(etapa) or ETAPA_A_TSF.get(etapa, "")


@dataclass(frozen=True)
class Homologacion:
    estado: str                # estado TSF reconocido ("" si no es un estado de TSF)
    etapas: tuple[str, ...]    # etapas posibles en el flujo de la CAR (1 = homologación clara)
    avance_min: float | None   # avance (0 a 1) de la primera etapa posible
    avance_max: float | None   # avance (0 a 1) de la última etapa posible

    @property
    def clara(self) -> bool:
        return len(self.etapas) == 1


def homologar(car: str | None, estado_api: str) -> Homologacion:
    estado = estado_canonico(estado_api) if estado_api else None
    flujo = obtener_flujo(car)
    if not estado or not flujo:
        return Homologacion(estado or "", (), None, None)
    etapas = tuple(e.nombre for e in flujo if estado_tsf(car, e.nombre) == estado)
    if not etapas:
        return Homologacion(estado, (), None, None)
    return Homologacion(estado, etapas, avance(car, etapas[0]), avance(car, etapas[-1]))


def etapa_desde_tsf(car: str | None, estado_api: str) -> str | None:
    """Etapa que corresponde al estado TSF, solo si la homologación es clara."""
    h = homologar(car, estado_api)
    return h.etapas[0] if h.clara else None

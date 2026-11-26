"""Equivalencia entre las etapas de cada CAR (las de esta app) y los estados forestales de TSF
(la plataforma de donde la API toma los datos).

Se usa en los dos sentidos, SOLO cuando la equivalencia es clara:
- TSF → etapa: si el estado que trae la API corresponde a UNA sola etapa del flujo de esa CAR, esa
  es la etapa del proyecto (origen «TSF»). Si corresponde a varias (ej. «Liquidación» en CARSUCRE
  puede ser la evaluación o la tasa) o a ninguna, la etapa la registras tú (origen «Manual»).
- Etapa → TSF: para lo registrado a mano, la app muestra qué estado le corresponde en TSF.

CÓMO EDITAR: cambia el estado TSF de una etapa en ETAPA_A_TSF. Si una CAR necesita algo distinto,
agrégalo en ETAPA_A_TSF_POR_CAR. Toda etapa de config/flujos.py debe tener equivalencia
(las pruebas lo verifican).
"""

from __future__ import annotations

import re
import unicodedata

from config.flujos import obtener_flujo

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


def etapa_desde_tsf(car: str | None, estado_api: str) -> str | None:
    """Etapa del flujo de la CAR que corresponde al estado TSF, solo si es una sola. Si no, None."""
    estado = estado_canonico(estado_api) if estado_api else None
    flujo = obtener_flujo(car)
    if not estado or not flujo:
        return None
    candidatas = [e.nombre for e in flujo if estado_tsf(car, e.nombre) == estado]
    return candidatas[0] if len(candidatas) == 1 else None

"""Equivalencia provisional entre el «Estado forestal» de la plataforma Unergy y las etapas de cada CAR.

Es temporal: sirve para que la app sugiera la etapa mientras la plataforma no tenga los flujos por CAR.
La etapa sugerida NUNCA se guarda sola: el usuario la revisa y pulsa Guardar.

CÓMO EDITAR
-----------
- POR_HITO: estados que equivalen a un hito. Se traducen a la etapa de cada CAR que tiene ese hito
  (ej. «Solicitud radicada» → «Radicado» en CORPOCESAR, «Radicación» en CVS).
- POR_ETAPA: estados que equivalen a una etapa con el mismo nombre en todos los flujos.
- POR_CAR: equivalencias que dependen de la CAR (ej. «Liquidación»). Si una CAR no aparece, no se sugiere nada.
- SIN_EQUIVALENCIA: estados que se muestran como aviso pero no mueven la etapa.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from config.constantes import Hito
from config.flujos import obtener_flujo

def normalizar_texto(valor: str) -> str:
    texto = "".join(c for c in unicodedata.normalize("NFKD", str(valor)) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


# Orden y nombres tal como aparecen en la plataforma Unergy.
ESTADOS_UNERGY: tuple[str, ...] = (
    "Por radicar",
    "Solicitud radicada",
    "Liquidación",
    "Requerimientos",
    "Respuesta a requerimientos",
    "Respuesta radicado",
    "Programado",
    "Visita",
    "Solicitud aprobada",
    "Solicitud rechazada",
    "Exonerado",
    "Pausado",
)

POR_HITO: dict[str, Hito] = {
    "Solicitud radicada": Hito.RADICADO,
    "Visita": Hito.VISITA,
    "Solicitud aprobada": Hito.RESOLUCION,
}

POR_ETAPA: dict[str, str] = {
    "Por radicar": "Informes",
}

POR_CAR: dict[str, dict[str, str]] = {
    "Liquidación": {
        "CARSUCRE": "Pagar la evaluación",
        "CORPOMOJANA": "Pagar la evaluación",
        "CORPAMAG": "Liquidación servicios",
        "CVS": "Liquidación servicios",
        "CORTOLIMA": "Pago evaluación",
        "CORPOCALDAS": "Pago evaluación",
        "CDMB": "Pago evaluación",
        "CAS": "Pago evaluación",
        "CSB": "Pago evaluación",
    },
}

SIN_EQUIVALENCIA: dict[str, str] = {
    "Requerimientos": "La CAR hizo requerimientos. El trámite sigue en su etapa; el histórico ya incluye esas esperas.",
    "Respuesta a requerimientos": "Se respondieron requerimientos de la CAR. El trámite sigue en su etapa.",
    "Respuesta radicado": "Hay una respuesta radicada ante la CAR. Revisa en qué etapa quedó el trámite.",
    "Programado": "Actuación programada. Revisa si es la visita u otra etapa.",
    "Pausado": "Trámite pausado en Unergy. La cuenta regresiva sigue corriendo con el histórico de la CAR.",
    "Solicitud rechazada": "La CAR rechazó la solicitud. La proyección no aplica.",
    "Exonerado": "El proyecto quedó exonerado del permiso. La proyección no aplica.",
}

# Escrituras alternativas que se aceptan (sin tildes ni mayúsculas).
ALIAS: dict[str, str] = {
    "respuesta a requerimiento": "Respuesta a requerimientos",
    "liquidacion": "Liquidación",
}

_CANONICOS = {normalizar_texto(e): e for e in ESTADOS_UNERGY}


@dataclass(frozen=True)
class Homologacion:
    estado: str           # estado tal como se reconoció ("" si no se reconoció)
    etapa: str | None     # etapa sugerida del flujo de la CAR
    nota: str             # explicación para mostrar


def estado_canonico(texto: str) -> str | None:
    clave = normalizar_texto(texto)
    return _CANONICOS.get(clave) or ALIAS.get(clave)


def homologar(car: str | None, estado_unergy: str) -> Homologacion:
    if not estado_unergy.strip():
        return Homologacion("", None, "")
    estado = estado_canonico(estado_unergy)
    if estado is None:
        return Homologacion("", None, f"Estado «{estado_unergy}» no reconocido; agrégalo en config/homologacion.py.")
    flujo = obtener_flujo(car)
    if estado in SIN_EQUIVALENCIA:
        return Homologacion(estado, None, SIN_EQUIVALENCIA[estado])
    if not flujo:
        return Homologacion(estado, None, "Sin CAR con flujo: no se puede traducir a una etapa.")
    nombres = [e.nombre for e in flujo]
    if estado in POR_HITO:
        etapa = next((e.nombre for e in flujo if e.hito == POR_HITO[estado]), None)
    elif estado in POR_ETAPA:
        etapa = POR_ETAPA[estado] if POR_ETAPA[estado] in nombres else None
    elif estado in POR_CAR:
        etapa = POR_CAR[estado].get(str(car).upper())
        etapa = etapa if etapa in nombres else None
    else:
        etapa = None
    if etapa is None:
        return Homologacion(estado, None, f"«{estado}» no tiene una etapa equivalente en el flujo de {car}.")
    return Homologacion(estado, etapa, f"«{estado}» en Unergy equivale a «{etapa}» en {car}.")

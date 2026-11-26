"""Secuencia de etapas de cada CAR.

CÓMO EDITAR
-----------
- Cada CAR es una lista ordenada de `Etapa(nombre, hito)`.
- `nombre` es el texto exacto que aparece en el desplegable.
- `hito` solo se pone cuando esa etapa corresponde a una fecha que existe en el Excel
  histórico (radicado, auto, visita, resolución, solicitud de liquidación). Las etapas sin
  hito se muestran y guardan su fecha, pero no tienen tiempos históricos propios: el reloj
  sigue corriendo desde el último hito.
- Para agregar una CAR o una etapa basta con editar este archivo. El motor estadístico no cambia.

Supuestos que puedes cambiar aquí mismo:
- CRA y CORPOGUAJIRA tienen "Radicado" y "Radicación". Se asume que la fecha de radicado del
  Excel corresponde a "Radicación" (la formal). Para cambiarlo, mueve `Hito.RADICADO` a la otra.
- En CRA, la fecha de auto del Excel se asume como "Auto inicio" (no "Auto cobro").
"""

from __future__ import annotations

from dataclasses import dataclass

from config.constantes import ORDEN_HITOS, Hito


@dataclass(frozen=True)
class Etapa:
    nombre: str
    hito: Hito | None = None


INVENTARIO = Etapa("Inventario")
INFORMES = Etapa("Informes")
RESOLUCION = Etapa("Resolución", Hito.RESOLUCION)

FLUJOS: dict[str, tuple[Etapa, ...]] = {
    "CORPOCESAR": (
        INVENTARIO,
        INFORMES,
        Etapa("Radicado", Hito.RADICADO),
        Etapa("Llega auto", Hito.AUTO),
        Etapa("Pago visita y publicación auto"),
        Etapa("Visita", Hito.VISITA),
        Etapa("Acta"),
        RESOLUCION,
    ),
    "CARSUCRE": (
        INVENTARIO,
        INFORMES,
        Etapa("Radicado", Hito.RADICADO),
        Etapa("Pagar la evaluación"),
        Etapa("Auto", Hito.AUTO),
        Etapa("Visita técnica", Hito.VISITA),
        Etapa("Pago tasa de aprovechamiento"),
        RESOLUCION,
    ),
    "CRA": (
        INVENTARIO,
        INFORMES,
        Etapa("Radicado"),
        Etapa("Auto cobro"),
        Etapa("Radicación", Hito.RADICADO),
        Etapa("Auto inicio", Hito.AUTO),
        Etapa("Publicación auto"),
        Etapa("Visita", Hito.VISITA),
        RESOLUCION,
    ),
    "CORPAMAG": (
        INVENTARIO,
        INFORMES,
        Etapa("Liquidación servicios"),
        Etapa("Solicitud de liquidación", Hito.SOLICITUD_LIQUIDACION),
        Etapa("Radicación", Hito.RADICADO),
        Etapa("Auto", Hito.AUTO),
        Etapa("Visita", Hito.VISITA),
        RESOLUCION,
    ),
    "CORPOGUAJIRA": (
        INVENTARIO,
        INFORMES,
        Etapa("Radicado"),
        Etapa("Radicación", Hito.RADICADO),
        Etapa("Auto", Hito.AUTO),
        Etapa("Visita", Hito.VISITA),
        RESOLUCION,
    ),
    "CORTOLIMA": (
        INVENTARIO,
        INFORMES,
        Etapa("Pago evaluación"),
        Etapa("Auto", Hito.AUTO),
        Etapa("Visita", Hito.VISITA),
        RESOLUCION,
    ),
    "CORPOCALDAS": (
        INVENTARIO,
        INFORMES,
        Etapa("Radicado", Hito.RADICADO),
        Etapa("Pago evaluación"),
        Etapa("Auto", Hito.AUTO),
        Etapa("Visita", Hito.VISITA),
        RESOLUCION,
    ),
    "CDMB": (
        INVENTARIO,
        INFORMES,
        Etapa("Radicado", Hito.RADICADO),
        Etapa("Pago evaluación"),
        Etapa("Auto", Hito.AUTO),
        Etapa("Publicación auto alcaldía"),
        Etapa("Visita", Hito.VISITA),
        RESOLUCION,
    ),
    "CAS": (
        INVENTARIO,
        INFORMES,
        Etapa("Radicado", Hito.RADICADO),
        Etapa("Pago evaluación"),
        Etapa("Auto", Hito.AUTO),
        Etapa("Visita", Hito.VISITA),
        RESOLUCION,
    ),
    "CSB": (
        INVENTARIO,
        INFORMES,
        Etapa("Radicado", Hito.RADICADO),
        Etapa("Pago evaluación"),
        Etapa("Auto", Hito.AUTO),
        Etapa("Visita", Hito.VISITA),
        RESOLUCION,
    ),
    "CORPOMOJANA": (
        INVENTARIO,
        INFORMES,
        Etapa("Radicado", Hito.RADICADO),
        Etapa("Pagar la evaluación"),
        Etapa("Auto", Hito.AUTO),
        Etapa("Visita técnica", Hito.VISITA),
        Etapa("Pago tasa de aprovechamiento"),
        RESOLUCION,
    ),
    "CVS": (
        INVENTARIO,
        INFORMES,
        Etapa("Radicación", Hito.RADICADO),
        Etapa("Liquidación servicios"),
        Etapa("Auto", Hito.AUTO),
        Etapa("Visita", Hito.VISITA),
        RESOLUCION,
    ),
}


def cars_con_flujo() -> list[str]:
    return sorted(FLUJOS)


def obtener_flujo(car: object) -> tuple[Etapa, ...] | None:
    if not isinstance(car, str) or not car:
        return None
    return FLUJOS.get(car.strip().upper())


def nombres_etapas(car: str | None) -> list[str]:
    flujo = obtener_flujo(car)
    return [e.nombre for e in flujo] if flujo else []


def indice_etapa(flujo: tuple[Etapa, ...], nombre: str | None) -> int | None:
    for i, etapa in enumerate(flujo):
        if etapa.nombre == nombre:
            return i
    return None


def validar_flujos() -> list[str]:
    """Revisa que la configuración sea coherente. Devuelve una lista de errores (vacía si todo está bien)."""
    errores: list[str] = []
    for car, flujo in FLUJOS.items():
        nombres = [e.nombre for e in flujo]
        if len(set(nombres)) != len(nombres):
            errores.append(f"{car}: hay etapas con el mismo nombre.")
        if not flujo or flujo[-1].hito != Hito.RESOLUCION:
            errores.append(f"{car}: la última etapa debe ser la resolución.")
        hitos = [e.hito for e in flujo if e.hito]
        if len(set(hitos)) != len(hitos):
            errores.append(f"{car}: un mismo hito está asignado a dos etapas.")
        posiciones = [ORDEN_HITOS.index(h) for h in hitos]
        if posiciones != sorted(posiciones):
            errores.append(f"{car}: los hitos no siguen el orden radicado → auto → visita → resolución.")
    return errores

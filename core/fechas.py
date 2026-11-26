"""Conteo de días en calendario o en días hábiles (lunes a viernes, sin festivos)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from config.constantes import UnidadDias

ZONA_COLOMBIA = ZoneInfo("America/Bogota")

MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def hoy_colombia() -> date:
    """Streamlit Cloud corre en UTC; la fecha de "hoy" se toma en hora de Colombia."""
    return datetime.now(ZONA_COLOMBIA).date()


def dias_entre(inicio: date, fin: date, unidad: UnidadDias) -> int:
    if unidad == UnidadDias.HABILES:
        return int(np.busday_count(inicio, fin))
    return (fin - inicio).days


def sumar_dias(inicio: date, dias: float, unidad: UnidadDias) -> date:
    n = int(round(dias))
    if unidad == UnidadDias.HABILES:
        return np.busday_offset(inicio, n, roll="forward").astype(date)
    return inicio + timedelta(days=n)


def formato_fecha(valor: date | None) -> str:
    if valor is None:
        return "—"
    return f"{valor.day} {MESES_CORTOS[valor.month - 1]} {valor.year}"


def formato_mes(valor: date | None) -> str:
    """Para fechas lejanas: 'mediados de mar 2027' evita una falsa precisión."""
    if valor is None:
        return "—"
    tercio = "inicios" if valor.day <= 10 else "mediados" if valor.day <= 20 else "finales"
    return f"{tercio} de {MESES_CORTOS[valor.month - 1]} {valor.year}"

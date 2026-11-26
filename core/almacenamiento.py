"""Dónde se guardan los estados y fechas que el usuario registra a mano.

- GoogleSheetsAlmacen: persistente. Usa una hoja de Google Sheets con tres pestañas
  (seguimiento, fechas_etapas, historial_cambios). Se puede abrir y revisar a mano.
- MemoriaAlmacen: solo para probar sin configurar Sheets. Se pierde al reiniciar la app.

Este módulo nunca escribe en la API de Unergy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from config.constantes import Hoja
from core.fechas import ZONA_COLOMBIA

ENCABEZADOS: dict[Hoja, list[str]] = {
    Hoja.SEGUIMIENTO: ["minifarm_id", "nombre", "car_manual", "etapa_actual", "actualizado_en"],
    Hoja.FECHAS: ["minifarm_id", "nombre", "car", "etapa", "fecha", "registrado_en"],
    Hoja.HISTORIAL: ["fecha_cambio", "minifarm_id", "nombre", "campo", "antes", "despues"],
}


@dataclass
class Seguimiento:
    minifarm_id: str
    nombre: str = ""
    car_manual: str = ""
    etapa_actual: str = ""
    fechas: dict[str, date] = field(default_factory=dict)
    actualizado_en: str = ""


@dataclass(frozen=True)
class Cambio:
    campo: str
    antes: str
    despues: str


def ahora_texto() -> str:
    return datetime.now(ZONA_COLOMBIA).strftime("%Y-%m-%d %H:%M")


def calcular_cambios(anterior: Seguimiento | None, nuevo: Seguimiento) -> list[Cambio]:
    previo = anterior or Seguimiento(minifarm_id=nuevo.minifarm_id)
    cambios: list[Cambio] = []
    if previo.car_manual != nuevo.car_manual:
        cambios.append(Cambio("CAR", previo.car_manual, nuevo.car_manual))
    if previo.etapa_actual != nuevo.etapa_actual:
        cambios.append(Cambio("Etapa actual", previo.etapa_actual, nuevo.etapa_actual))
    for etapa in sorted(set(previo.fechas) | set(nuevo.fechas)):
        a, d = previo.fechas.get(etapa), nuevo.fechas.get(etapa)
        if a != d:
            cambios.append(Cambio(f"Fecha {etapa}", a.isoformat() if a else "", d.isoformat() if d else ""))
    return cambios


class Almacen(Protocol):
    persistente: bool
    descripcion: str

    def cargar(self) -> dict[str, Seguimiento]: ...

    def guardar(self, seguimiento: Seguimiento, car_efectiva: str, cambios: list[Cambio]) -> None: ...


class MemoriaAlmacen:
    persistente = False
    descripcion = "Memoria temporal (se pierde al reiniciar)"

    def __init__(self) -> None:
        self._datos: dict[str, Seguimiento] = {}

    def cargar(self) -> dict[str, Seguimiento]:
        return dict(self._datos)

    def guardar(self, seguimiento: Seguimiento, car_efectiva: str, cambios: list[Cambio]) -> None:
        self._datos[seguimiento.minifarm_id] = seguimiento


def _fecha_desde_texto(texto: str) -> date | None:
    try:
        return date.fromisoformat(texto.strip()[:10])
    except ValueError:
        return None


class GoogleSheetsAlmacen:
    persistente = True
    descripcion = "Google Sheets"

    def __init__(self, credenciales: dict[str, object], url_hoja: str) -> None:
        import gspread  # import aquí para que la app funcione sin gspread en modo memoria

        cliente = gspread.service_account_from_dict(credenciales)
        self._libro = cliente.open_by_url(url_hoja)
        existentes = {ws.title: ws for ws in self._libro.worksheets()}
        self._hojas = {}
        for hoja, encabezado in ENCABEZADOS.items():
            ws = existentes.get(hoja.value)
            if ws is None:
                ws = self._libro.add_worksheet(title=hoja.value, rows=200, cols=len(encabezado))
                ws.update(values=[encabezado], range_name="A1")
            self._hojas[hoja] = ws

    def cargar(self) -> dict[str, Seguimiento]:
        datos: dict[str, Seguimiento] = {}
        for fila in self._hojas[Hoja.SEGUIMIENTO].get_all_values()[1:]:
            fila = (fila + [""] * 5)[:5]
            if not fila[0].strip():
                continue
            datos[fila[0].strip()] = Seguimiento(
                minifarm_id=fila[0].strip(), nombre=fila[1], car_manual=fila[2].strip(),
                etapa_actual=fila[3].strip(), actualizado_en=fila[4],
            )
        for fila in self._hojas[Hoja.FECHAS].get_all_values()[1:]:
            fila = (fila + [""] * 6)[:6]
            mid, etapa, fecha = fila[0].strip(), fila[3].strip(), _fecha_desde_texto(fila[4])
            if not mid or not etapa or fecha is None:
                continue
            datos.setdefault(mid, Seguimiento(minifarm_id=mid, nombre=fila[1])).fechas[etapa] = fecha
        return datos

    def guardar(self, seguimiento: Seguimiento, car_efectiva: str, cambios: list[Cambio]) -> None:
        mid = seguimiento.minifarm_id
        # 1) fila del proyecto en «seguimiento»
        ws = self._hojas[Hoja.SEGUIMIENTO]
        valores = ws.get_all_values()
        fila_nueva = [mid, seguimiento.nombre, seguimiento.car_manual, seguimiento.etapa_actual,
                      seguimiento.actualizado_en]
        numero = next((i + 1 for i, f in enumerate(valores) if i > 0 and f and f[0].strip() == mid), None)
        if numero:
            ws.update(values=[fila_nueva], range_name=f"A{numero}:E{numero}")
        else:
            ws.append_row(fila_nueva, value_input_option="RAW")

        # 2) fechas de etapas: se reemplazan las de este proyecto, las demás se conservan
        ws = self._hojas[Hoja.FECHAS]
        viejas = ws.get_all_values()
        otras = [f for f in viejas[1:] if f and f[0].strip() != mid]
        previas = {f[3]: f[5] for f in viejas[1:] if len(f) >= 6 and f[0].strip() == mid}
        propias = [
            [mid, seguimiento.nombre, car_efectiva, etapa, fecha.isoformat(),
             previas.get(etapa, seguimiento.actualizado_en)]
            for etapa, fecha in seguimiento.fechas.items()
        ]
        nuevas = [ENCABEZADOS[Hoja.FECHAS], *otras, *propias]
        if len(nuevas) > ws.row_count:
            ws.add_rows(len(nuevas) - ws.row_count + 100)
        ws.update(values=nuevas, range_name="A1", value_input_option="RAW")
        if len(viejas) > len(nuevas):
            ws.batch_clear([f"A{len(nuevas) + 1}:F{len(viejas)}"])

        # 3) bitácora de cambios (solo se agregan filas)
        if cambios:
            self._hojas[Hoja.HISTORIAL].append_rows(
                [[seguimiento.actualizado_en, mid, seguimiento.nombre, c.campo, c.antes, c.despues] for c in cambios],
                value_input_option="RAW",
            )

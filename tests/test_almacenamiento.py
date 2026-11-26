"""Prueba de ida y vuelta del almacenamiento en Google Sheets usando una hoja falsa en memoria."""

import sys
import types
from datetime import date

from core.almacenamiento import Cambio, GoogleSheetsAlmacen, Seguimiento, calcular_cambios


class HojaFalsa:
    def __init__(self, titulo, rows=200):
        self.title, self.row_count, self.celdas = titulo, rows, []

    def get_all_values(self):
        return [list(f) for f in self.celdas]

    def _poner(self, fila0, valores):
        while len(self.celdas) < fila0 + len(valores):
            self.celdas.append([])
        for i, v in enumerate(valores):
            self.celdas[fila0 + i] = list(v)

    def update(self, values, range_name, value_input_option="RAW"):
        fila = int("".join(c for c in range_name.split(":")[0] if c.isdigit()))
        self._poner(fila - 1, values)

    def append_row(self, valores, value_input_option="RAW"):
        self.celdas.append(list(valores))

    def append_rows(self, filas, value_input_option="RAW"):
        self.celdas.extend(list(f) for f in filas)

    def batch_clear(self, rangos):
        desde = int("".join(c for c in rangos[0].split(":")[0] if c.isdigit()))
        self.celdas = self.celdas[: desde - 1]

    def add_rows(self, n):
        self.row_count += n


class LibroFalso:
    def __init__(self):
        self.hojas = {}

    def worksheets(self):
        return list(self.hojas.values())

    def add_worksheet(self, title, rows, cols):
        self.hojas[title] = HojaFalsa(title, rows)
        return self.hojas[title]


def almacen(monkeypatch):
    libro = LibroFalso()
    falso = types.SimpleNamespace(
        service_account_from_dict=lambda cred: types.SimpleNamespace(open_by_url=lambda url: libro)
    )
    monkeypatch.setitem(sys.modules, "gspread", falso)
    return GoogleSheetsAlmacen({"type": "service_account"}, "https://docs.google.com/x"), libro


def test_guardar_y_cargar(monkeypatch):
    a, libro = almacen(monkeypatch)
    s1 = Seguimiento("11", "Solar A", "", "Llega auto", {"Radicado": date(2026, 6, 1), "Llega auto": date(2026, 8, 20)}, "t1")
    s2 = Seguimiento("12", "Solar B", "CSB", "Radicado", {"Radicado": date(2026, 7, 1)}, "t1")
    a.guardar(s1, "CORPOCESAR", calcular_cambios(None, s1))
    a.guardar(s2, "CSB", calcular_cambios(None, s2))
    # actualizar s1 quitando una fecha
    s1b = Seguimiento("11", "Solar A", "", "Radicado", {"Radicado": date(2026, 6, 1)}, "t2")
    a.guardar(s1b, "CORPOCESAR", calcular_cambios(s1, s1b))

    datos = a.cargar()
    assert datos["11"].etapa_actual == "Radicado"
    assert datos["11"].fechas == {"Radicado": date(2026, 6, 1)}
    assert datos["12"].car_manual == "CSB" and datos["12"].fechas == {"Radicado": date(2026, 7, 1)}
    assert len(libro.hojas["seguimiento"].celdas) == 3  # encabezado + 2 proyectos
    historial = libro.hojas["historial_cambios"].celdas
    assert ["t2", "11", "Solar A", "Etapa actual", "Llega auto", "Radicado"] in historial


def test_calcular_cambios():
    antes = Seguimiento("1", etapa_actual="Radicado", fechas={"Radicado": date(2026, 1, 1)})
    despues = Seguimiento("1", etapa_actual="Auto", fechas={"Radicado": date(2026, 1, 1), "Auto": date(2026, 2, 1)})
    assert calcular_cambios(antes, despues) == [
        Cambio("Etapa actual", "Radicado", "Auto"), Cambio("Fecha Auto", "", "2026-02-01")
    ]

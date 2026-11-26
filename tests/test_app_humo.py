"""Prueba de humo: levanta una API falsa local y recorre todas las páginas de la app."""

import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
TERRENOS = {
    1: ("Finca A", "Valledupar, Cesar", [(11, "Solar Cesar")]),
    2: ("Finca B", "Cartagena, Bolívar", [(21, "Solar Bolívar")]),
}


class ApiFalsa(BaseHTTPRequestHandler):
    metodos_no_get: list[str] = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta == "/api/roles/forest/":
            cuerpo = {"count": 2, "next": None, "results": [{"id": i, "name": t[0], "location": t[1]} for i, t in TERRENOS.items()]}
        else:
            i = int(ruta.strip("/").split("/")[-1])
            n, loc, mfs = TERRENOS[i]
            cuerpo = {"id": i, "name": n, "location": loc,
                      "minifarms": [{"id": m, "name": nombre, "stage": "Radicado"} for m, nombre in mfs]}
        datos = json.dumps(cuerpo).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(datos)

    def _no_permitido(self):
        ApiFalsa.metodos_no_get.append(self.command)
        self.send_response(405)
        self.end_headers()

    do_POST = do_PUT = do_PATCH = do_DELETE = _no_permitido


@pytest.fixture(scope="module")
def api():
    servidor = HTTPServer(("127.0.0.1", 0), ApiFalsa)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{servidor.server_port}"
    servidor.shutdown()


def app(api):
    st.cache_data.clear()
    st.cache_resource.clear()
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets["unergy"] = {"api_key": "k", "base_url": api}
    return at


def test_todas_las_paginas_cargan(api):
    at = app(api)
    at.run()
    assert not at.exception and not at.error
    assert [m.value for m in at.metric][0] == "2"
    for pagina in ("paginas/proyectos.py", "paginas/historico.py", "paginas/explorar_api.py"):
        at.switch_page(pagina)
        at.run()
        assert not at.exception, pagina


def test_guardar_estado_y_ver_proyeccion(api):
    at = app(api)
    at.switch_page("paginas/proyectos.py")
    at.session_state["_minifarm_seleccionada"] = "11"
    at.run()
    etapa = next(s for s in at.selectbox if s.label.startswith("Etapa actual"))
    assert "Acta" in etapa.options
    etapa.select("Llega auto")
    for d in at.date_input:
        if d.label == "⏱ Radicado":
            d.set_value(date(2026, 6, 1))
        if d.label == "⏱ Llega auto":
            d.set_value(date(2026, 8, 20))
    next(b for b in at.button if b.label == "Guardar").click()
    at.run()
    assert not at.exception and not at.error
    assert any("sf-cifra" in m.value for m in at.markdown)
    assert ApiFalsa.metodos_no_get == []


def test_car_no_identificada_pide_seleccion(api):
    at = app(api)
    at.switch_page("paginas/proyectos.py")
    at.session_state["_minifarm_seleccionada"] = "21"
    at.run()
    assert any("Selecciona la CAR" in i.value for i in at.info)


def test_sin_secretos_muestra_aviso():
    st.cache_data.clear()
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    assert any("API Key" in e.value for e in at.error)

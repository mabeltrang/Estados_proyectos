"""Prueba de humo: levanta una API falsa local y recorre todas las páginas de la app."""

import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
TERRENOS = {
    1: ("Finca A", "Valledupar, Cesar", [(11, "Solar Cesar")]),
    2: ("Finca B", "Cartagena, Bolívar", [(21, "Solar Bolívar")]),
    3: ("Finca C", "Valledupar, Cesar", [(31, "Solar Programado")]),
}
ESTADO_TSF = {11: "Solicitud radicada", 21: "Solicitud radicada", 31: "Programado"}


class ApiFalsa(BaseHTTPRequestHandler):
    metodos_no_get: list[str] = []
    consultas: list[str] = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        ruta, _, consulta = self.path.partition("?")
        ApiFalsa.consultas.append(self.path)
        if ruta == "/api/roles/forest/":
            buscar = parse_qs(consulta).get("search", [""])[0].lower()
            ids = [i for i, t in TERRENOS.items()
                   if buscar in t[0].lower() or any(buscar in n.lower() for _, n in t[2])]
            cuerpo = {"count": len(ids), "next": None,
                      "results": [{"id": i, "name": TERRENOS[i][0], "location": TERRENOS[i][1]} for i in ids]}
        else:
            i = int(ruta.strip("/").split("/")[-1])
            n, loc, mfs = TERRENOS[i]
            cuerpo = {"id": i, "name": n, "location": loc,
                      "minifarms": [{"id": m, "name": nombre, "stage": "UCI",
                                    "forestry_licence": "Licencia de aprovechamiento forestal",
                                    "forestry_license_resolution": {"id": 2, "name": ESTADO_TSF[m]}} for m, nombre in mfs]}
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


def test_todas_las_paginas_cargan_sin_consultar_toda_la_api(api):
    ApiFalsa.consultas.clear()
    at = app(api)
    at.run()
    assert not at.exception and not at.error
    for pagina in ("paginas/proyectos.py", "paginas/historico.py", "paginas/explorar_api.py"):
        at.switch_page(pagina)
        at.run()
        assert not at.exception, pagina
    assert ApiFalsa.consultas == []  # nada se descarga hasta que el usuario busca


def test_buscar_abrir_guardar_y_volver(api):
    at = app(api)
    at.switch_page("paginas/proyectos.py")
    at.run()
    at.text_input[0].input("solar cesar")
    at.run()
    assert not at.exception
    resultado = at.dataframe[0].value
    assert list(resultado["Proyecto"]) == ["Solar Cesar"]
    assert list(resultado["Estado TSF"]) == ["Solicitud radicada"]
    assert list(resultado["Estado homologado"]) == ["Sin homologación"]  # en CORPOCESAR puede ser Radicado o Llega auto
    # simula seleccionar la fila (abre el detalle del proyecto)
    at.session_state["_terreno_seleccionado"] = "1"
    at.session_state["_minifarm_seleccionada"] = "11"
    at.run()
    assert any("unergy-header" in m.value and "Solar Cesar" in m.value for m in at.markdown)
    assert any("Solicitud radicada" in m.value for m in at.markdown)
    etapa = next(s for s in at.selectbox if s.label.startswith("Etapa actual"))
    assert "Acta" in etapa.options
    assert etapa.value is None and not etapa.disabled  # sin homologación clara: se registra a mano
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
    # volver: regresa al buscador con el texto conservado
    next(b for b in at.button if b.label.startswith("← Volver")).click()
    at.run()
    assert at.text_input[0].value == "solar cesar"
    fila = at.dataframe[0].value.iloc[0]
    assert fila["Estado homologado"] == "Llega auto" and fila["Origen"] == "Manual" and fila["Avance"] == 43
    # sin texto aparece la tabla de seguimiento con el proyecto guardado
    at.text_input[0].input("")
    at.run()
    assert "Solar Cesar" in list(at.dataframe[0].value["Proyecto"])
    # la vista general ya muestra el proyecto
    at.switch_page("paginas/vista_general.py")
    at.run()
    assert at.metric[0].value == "1"
    assert ApiFalsa.metodos_no_get == []


def test_estado_tsf_con_homologacion_clara_se_usa_directo(api):
    at = app(api)
    at.switch_page("paginas/proyectos.py")
    at.run()
    at.text_input[0].input("programado")
    at.run()
    fila = at.dataframe[0].value.iloc[0]
    assert (fila["Estado TSF"], fila["Estado homologado"], fila["Origen"], fila["Avance"]) == (
        "Programado", "Inventario", "TSF", 0)
    at.session_state["_terreno_seleccionado"] = "3"
    at.session_state["_minifarm_seleccionada"] = "31"
    at.run()
    etapa = next(s for s in at.selectbox if s.label.startswith("Etapa actual"))
    assert etapa.value == "Inventario" and etapa.disabled


def test_car_no_identificada_pide_seleccion(api):
    at = app(api)
    at.switch_page("paginas/proyectos.py")
    at.session_state["_terreno_seleccionado"] = "2"
    at.run()
    assert any("Selecciona la CAR" in i.value for i in at.info)


def test_sin_secretos_al_buscar_muestra_aviso():
    st.cache_data.clear()
    at = AppTest.from_file(APP, default_timeout=60)
    at.switch_page("paginas/proyectos.py")
    at.run()
    at.text_input[0].input("algo")
    at.run()
    assert not at.exception
    assert any("API Key" in e.value for e in at.error)

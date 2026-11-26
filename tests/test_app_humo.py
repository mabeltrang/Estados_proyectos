"""Prueba de humo: levanta una API falsa local y recorre todas las páginas de la app."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
TERRENOS = {
    1: ("Finca A", "Valledupar, Cesar", [(11, "Solar Cesar")]),
    2: ("Finca B", "Cartagena, Bolívar", [(21, "Solar Bolívar")]),
    3: ("Finca C", "Valledupar, Cesar", [(31, "Solar Programado"), (32, "Solar Aprobado")]),
}
ESTADO_TSF = {11: "Visita", 21: "Solicitud radicada", 31: "Programado", 32: "Solicitud aprobada"}


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
    for pagina in ("paginas/vista_general.py", "paginas/historico.py", "paginas/explorar_api.py"):
        at.switch_page(pagina)
        at.run()
        assert not at.exception, pagina
    assert ApiFalsa.consultas == []  # nada se descarga hasta que el usuario busca o pide el resumen


def buscar(at, texto):
    at.text_input[0].input(texto)
    at.run()
    assert not at.exception
    return at.dataframe[0].value


def test_busqueda_muestra_estado_tsf_homologado_y_avance(api):
    at = app(api)
    at.run()
    tabla = buscar(at, "finca c").set_index("Proyecto")
    assert tabla.loc["Solar Programado", "Estado TSF"] == "Programado"
    assert tabla.loc["Solar Programado", "Etapa homologada"] == "Inventario"
    assert tabla.loc["Solar Programado", "Avance"] == 0
    assert tabla.loc["Solar Aprobado", "Etapa homologada"] == "Resolución"
    assert tabla.loc["Solar Aprobado", "Avance"] == 100


def test_homologacion_ambigua_no_elige(api):
    at = app(api)
    at.run()
    fila = buscar(at, "solar cesar").iloc[0]
    assert fila["Etapa homologada"] == "Visita / Acta (71–86 %)"
    assert pd.isna(fila["Avance"])


def test_detalle_es_solo_lectura_y_volver_conserva_busqueda(api):
    at = app(api)
    at.run()
    buscar(at, "finca c")
    at.session_state["_terreno_seleccionado"] = "3"
    at.session_state["_minifarm_seleccionada"] = "31"
    at.run()
    assert not at.exception
    assert any("unergy-header" in m.value and "Solar Programado" in m.value for m in at.markdown)
    assert any("sf-actual" in m.value and "Inventario" in m.value for m in at.markdown)
    assert not at.selectbox and not at.date_input  # nada que editar
    assert not any(b.label == "Guardar" for b in at.button)
    next(b for b in at.button if b.label.startswith("← Volver")).click()
    at.run()
    assert at.text_input[0].value == "finca c"
    assert ApiFalsa.metodos_no_get == []


def test_sin_car_no_se_homologa(api):
    at = app(api)
    at.session_state["_terreno_seleccionado"] = "2"
    at.session_state["_minifarm_seleccionada"] = "21"
    at.run()
    assert any("Sin CAR identificada" in c.value for c in at.caption)


def test_resumen_general_bajo_demanda(api):
    at = app(api)
    at.switch_page("paginas/vista_general.py")
    at.run()
    assert not at.metric
    next(b for b in at.button if b.label == "Cargar resumen").click()
    at.run()
    assert not at.exception
    assert at.metric[0].value == "4"
    assert at.metric[1].value == "2"  # Programado e Inventario/Resolución son claros


def test_sin_secretos_al_buscar_muestra_aviso():
    st.cache_data.clear()
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.text_input[0].input("algo")
    at.run()
    assert not at.exception
    assert any("API Key" in e.value for e in at.error)

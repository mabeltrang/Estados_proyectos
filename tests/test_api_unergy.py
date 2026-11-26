import pytest
import requests

from core.api_unergy import ClienteUnergy, ErrorApiUnergy, _SesionSoloLectura
from core.proyectos import minifarms_de_terreno, separar_ubicacion


class Resp:
    def __init__(self, status, datos=None):
        self.status_code = status
        self._datos = datos

    def json(self):
        if self._datos is None:
            raise ValueError("no json")
        return self._datos


class HttpFalso:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def get(self, url, *, headers, params, timeout):
        self.llamadas.append((url, params, headers))
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def cliente(respuestas):
    http = HttpFalso(respuestas)
    return ClienteUnergy("https://api.test", "SECRETA", reintentos=1, http=http), http


def test_recorre_todas_las_paginas():
    c, http = cliente([
        Resp(200, {"count": 3, "next": "x", "results": [{"id": 1}, {"id": 2}]}),
        Resp(200, {"count": 3, "next": None, "results": [{"id": 3}]}),
    ])
    assert [t["id"] for t in c.listar_forestal_todo(page_size=2)] == [1, 2, 3]
    assert http.llamadas[1][1] == {"page": 2, "page_size": 2}
    assert http.llamadas[0][2]["X-API-Key"] == "SECRETA"


@pytest.mark.parametrize("status", [401, 403, 404])
def test_errores_claros_sin_api_key(status):
    c, _ = cliente([Resp(status, {"error": "x"})])
    with pytest.raises(ErrorApiUnergy) as e:
        c.detalle_forestal(5)
    assert e.value.status == status and "SECRETA" not in e.value.mensaje


def test_reintenta_en_500_y_timeout(monkeypatch):
    monkeypatch.setattr("core.api_unergy.time.sleep", lambda s: None)
    c, _ = cliente([requests.Timeout(), Resp(200, {"id": 1})])
    assert c.detalle_forestal(1) == {"id": 1}
    c, _ = cliente([Resp(500), Resp(502)])
    with pytest.raises(ErrorApiUnergy, match="servidor"):
        c.detalle_forestal(1)


def test_respuesta_no_json():
    c, _ = cliente([Resp(200, None)])
    with pytest.raises(ErrorApiUnergy, match="JSON"):
        c.detalle_forestal(1)


def test_lista_sin_page_es_rechazada():
    c, _ = cliente([Resp(200, {"Activo": 4})])
    with pytest.raises(ErrorApiUnergy, match="conteo"):
        c.listar_forestal()


def test_solo_lectura():
    c, _ = cliente([])
    with pytest.raises(ErrorApiUnergy):
        c._get("/api/otra-cosa/")
    with pytest.raises(ErrorApiUnergy):
        c.detalle_forestal("1/../../admin")
    for metodo in ("post", "put", "patch", "delete", "request"):
        assert not hasattr(_SesionSoloLectura(), metodo)
        assert not hasattr(c, metodo)


def test_sin_api_key():
    with pytest.raises(ErrorApiUnergy):
        ClienteUnergy("https://api.test", "")


def test_extraer_minifarms():
    detalle = {"id": 7, "name": "T1", "location": "Valledupar, Cesar",
               "minifarms": [{"id": 11, "project_id": 3, "name": "Solar A", "stage": {"name": "Radicado"}},
                             {"id": 12, "name": "Solar B", "stage": None}]}
    filas = minifarms_de_terreno(detalle)
    assert [f["nombre"] for f in filas] == ["Solar A", "Solar B"]
    assert filas[0]["etapa_api"] == "Radicado" and filas[0]["departamento"] == "Cesar"
    assert separar_ubicacion("San Juan de Betulia, Sucre") == ("San Juan de Betulia", "Sucre")
    assert separar_ubicacion("Bogotá") == ("Bogotá", "")

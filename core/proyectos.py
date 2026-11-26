"""Convierte la respuesta de la API forestal en una tabla con una fila por Minifarm (proyecto).

Solo se leen los campos documentados de la API. Si un campo no viene, queda vacío.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import pandas as pd

from config.ajustes import CAMPOS_ESTADO_FORESTAL
from config.car_lookup import obtener_car
from config.constantes import Columna, FuenteCar, TipoHomologacion
from config.flujos import FLUJOS
from config.homologacion import estado_canonico, homologar
from core.api_unergy import ClienteUnergy, ErrorApiUnergy, JsonObj

COLUMNAS_PROYECTO: list[str] = [
    Columna.MINIFARM_ID, Columna.PROJECT_ID, Columna.NOMBRE, Columna.TERRENO_ID, Columna.TERRENO_NOMBRE,
    Columna.UBICACION, Columna.MUNICIPIO, Columna.DEPARTAMENTO, Columna.ETAPA_API, Columna.ARBOLES,
    Columna.ESTADO_FORESTAL, Columna.CAMPO_ESTADO, Columna.TIPO_PERMISO, Columna.RESOLUCION_LICENCIA,
    Columna.OPERADOR_RED,
]


@dataclass
class ProyectosCargados:
    tabla: pd.DataFrame
    terrenos: int = 0
    terrenos_sin_minifarms: int = 0
    errores: list[str] = field(default_factory=list)


def a_texto(valor: object) -> str:
    """Representa cualquier valor de la API como texto legible (la forma exacta de algunos campos,
    como `stage`, se confirma en la página «Explorar API»)."""
    if valor is None:
        return ""
    if isinstance(valor, dict):
        for clave in ("name", "label", "value", "display"):
            if isinstance(valor.get(clave), (str, int, float)):
                return str(valor[clave])
        return ", ".join(f"{k}: {v}" for k, v in valor.items())
    if isinstance(valor, list):
        return ", ".join(a_texto(v) for v in valor)
    return str(valor)


def textos_anidados(valor: object, ruta: str, profundidad: int = 0):
    """Recorre un valor de la API y devuelve (ruta, texto) de cada texto que contiene."""
    if isinstance(valor, str):
        yield ruta, valor
    elif isinstance(valor, dict) and profundidad < 3:
        for clave, v in valor.items():
            yield from textos_anidados(v, f"{ruta}.{clave}", profundidad + 1)
    elif isinstance(valor, list) and profundidad < 3:
        for i, v in enumerate(valor):
            yield from textos_anidados(v, f"{ruta}[{i}]", profundidad + 1)


def detectar_estado_forestal(minifarm: dict[str, object]) -> tuple[str, str]:
    """Lee el estado TSF solo de los campos configurados en ajustes.CAMPOS_ESTADO_FORESTAL.
    Devuelve (estado, campo) o ("", "") si el valor no es un estado de TSF. No revisa otros campos."""
    for campo in [c for c in CAMPOS_ESTADO_FORESTAL if c in minifarm]:
        for ruta, texto in textos_anidados(minifarm.get(campo), campo):
            estado = estado_canonico(texto)
            if estado:
                return estado, ruta
    return "", ""


def separar_ubicacion(ubicacion: str) -> tuple[str, str]:
    """'Ciudad, Región' → ('Ciudad', 'Región'). Si no hay coma, el departamento queda vacío."""
    texto = (ubicacion or "").strip()
    if "," not in texto:
        return texto, ""
    municipio, departamento = texto.rsplit(",", 1)
    return municipio.strip(), departamento.strip()


def minifarms_de_terreno(detalle: JsonObj) -> list[dict[str, object]]:
    ubicacion = a_texto(detalle.get("location"))
    municipio, departamento = separar_ubicacion(ubicacion)
    filas: list[dict[str, object]] = []
    minifarms = detalle.get("minifarms")
    if not isinstance(minifarms, list):
        return filas
    for mf in minifarms:
        if not isinstance(mf, dict) or mf.get("id") is None:
            continue
        estado, campo = detectar_estado_forestal(mf)
        filas.append(
            {
                Columna.MINIFARM_ID: str(mf.get("id")),
                Columna.PROJECT_ID: a_texto(mf.get("project_id")),
                Columna.NOMBRE: a_texto(mf.get("name")) or f"Minifarm {mf.get('id')}",
                Columna.TERRENO_ID: a_texto(detalle.get("id")),
                Columna.TERRENO_NOMBRE: a_texto(detalle.get("name")),
                Columna.UBICACION: ubicacion,
                Columna.MUNICIPIO: municipio,
                Columna.DEPARTAMENTO: departamento,
                Columna.ETAPA_API: a_texto(mf.get("stage")),
                Columna.ARBOLES: a_texto(mf.get("tree_count")),
                Columna.ESTADO_FORESTAL: estado,
                Columna.CAMPO_ESTADO: campo,
                Columna.TIPO_PERMISO: a_texto(mf.get("forestry_licence")),
                Columna.RESOLUCION_LICENCIA: a_texto(mf.get("forestry_license_resolution")),
                Columna.OPERADOR_RED: a_texto(mf.get("grid_operator")),
            }
        )
    return filas


def cargar_proyectos(cliente: ClienteUnergy, page_size: int, max_paginas: int, hilos: int) -> ProyectosCargados:
    terrenos = cliente.listar_forestal_todo(page_size=page_size, max_paginas=max_paginas)
    ids = [t.get("id") for t in terrenos if t.get("id") is not None]
    resultado = ProyectosCargados(tabla=pd.DataFrame(columns=COLUMNAS_PROYECTO), terrenos=len(ids))

    def traer(terreno_id: object) -> tuple[object, JsonObj | None, str | None]:
        try:
            return terreno_id, cliente.detalle_forestal(str(terreno_id)), None
        except ErrorApiUnergy as exc:
            return terreno_id, None, exc.mensaje

    filas: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=hilos) as pool:
        for terreno_id, detalle, error in pool.map(traer, ids):
            if error:
                resultado.errores.append(f"Terreno {terreno_id}: {error}")
                continue
            assert detalle is not None
            nuevas = minifarms_de_terreno(detalle)
            if not nuevas:
                resultado.terrenos_sin_minifarms += 1
            filas.extend(nuevas)
    if filas:
        resultado.tabla = pd.DataFrame(filas, columns=COLUMNAS_PROYECTO)
    return resultado


def identificar_car(municipio: str, departamento: str) -> tuple[str | None, str]:
    """Usa la tabla de municipios por CAR. Devuelve (CAR o None, mensaje)."""
    if not departamento:
        return None, "La ubicación no trae departamento; selecciona la CAR manualmente."
    info = obtener_car(municipio, departamento)
    car = info.get("car")
    return (str(car).upper() if car else None), str(info.get("mensaje", ""))


def asignar_car(tabla: pd.DataFrame, cars_manuales: dict[str, str]) -> pd.DataFrame:
    """Agrega las columnas CAR, origen de la CAR y si la CAR tiene flujo configurado.
    La CAR elegida a mano por el usuario siempre manda sobre la automática."""
    tabla = tabla.copy()
    cars: list[str | None] = []
    fuentes: list[str] = []
    for _, fila in tabla.iterrows():
        manual = cars_manuales.get(str(fila[Columna.MINIFARM_ID]))
        if manual:
            cars.append(manual)
            fuentes.append(FuenteCar.MANUAL)
            continue
        car, _ = identificar_car(str(fila[Columna.MUNICIPIO]), str(fila[Columna.DEPARTAMENTO]))
        cars.append(car)
        fuentes.append(FuenteCar.AUTOMATICA if car else FuenteCar.NO_IDENTIFICADA)
    tabla[Columna.CAR] = cars
    tabla[Columna.CAR_FUENTE] = fuentes
    tabla["car_con_flujo"] = tabla[Columna.CAR].map(lambda c: isinstance(c, str) and c in FLUJOS)
    return tabla


def _porcentaje(valor: float | None) -> str:
    return "—" if valor is None else f"{valor * 100:.0f} %"


def agregar_homologacion(tabla: pd.DataFrame) -> pd.DataFrame:
    """Traduce el estado TSF de cada proyecto a la etapa de su CAR y calcula el avance.
    Solo lectura: nada se guarda ni se elige por el usuario."""
    tabla = tabla.copy()
    etapas, tipos, avances, textos = [], [], [], []
    for _, fila in tabla.iterrows():
        car = fila[Columna.CAR] if isinstance(fila[Columna.CAR], str) else None
        h = homologar(car, str(fila[Columna.ESTADO_FORESTAL] or ""))
        if h.clara:
            etapas.append(h.etapas[0])
            tipos.append(TipoHomologacion.CLARA)
            avances.append(round(h.avance_min * 100))
            textos.append(_porcentaje(h.avance_min))
        elif h.etapas:
            etapas.append(" / ".join(h.etapas))
            tipos.append(TipoHomologacion.VARIAS)
            avances.append(None)
            textos.append(f"{h.avance_min * 100:.0f}–{h.avance_max * 100:.0f} %")
        else:
            etapas.append("")
            tipos.append(TipoHomologacion.SIN)
            avances.append(None)
            textos.append("—")
    tabla[Columna.ETAPA_HOMOLOGADA] = etapas
    tabla[Columna.HOMOLOGACION] = tipos
    tabla[Columna.AVANCE] = avances
    tabla[Columna.AVANCE_TEXTO] = textos
    return tabla

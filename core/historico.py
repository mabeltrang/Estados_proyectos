"""Lectura del Excel histórico de fechas de las CAR y reporte de calidad.

El Excel original nunca se modifica: se lee, se normaliza en memoria y se reportan los problemas.
Ninguna fecha se inventa ni se completa. Las fechas imposibles se descartan (y se reportan);
las fechas invertidas se dejan, pero el tramo afectado no entra en las estadísticas.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from config.constantes import NOMBRE_HITO, ORDEN_HITOS, Columna, Hito

COLUMNAS_FECHA: list[str] = [h.value for h in ORDEN_HITOS]
COLUMNA_DUDOSOS = "hitos_dudosos"
TITULARES_GENERICOS = {"PERSONA NATURAL", "ALCALDIA", "NAN", ""}
EXCEL_ORIGEN = pd.Timestamp("1899-12-30")


@dataclass
class HistoricoCargado:
    tramites: pd.DataFrame
    problemas: pd.DataFrame
    hojas: list[str] = field(default_factory=list)
    hojas_usadas: list[str] = field(default_factory=list)
    columnas_encontradas: dict[str, str] = field(default_factory=dict)
    columnas_faltantes: list[str] = field(default_factory=list)
    filas_leidas: int = 0
    filas_otras_categorias: int = 0
    filas_cars_excluidas: int = 0
    actos_unidos: int = 0


def normalizar_texto(valor: object) -> str:
    """Quita tildes, pasa a minúsculas y colapsa espacios. Sirve para comparar encabezados y nombres."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    texto = "".join(
        c for c in unicodedata.normalize("NFKD", str(valor)) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", texto).strip().lower()


def _clave_titular(titular: object) -> str:
    """Misma normalización que usa CARS_nuevo para reconocer al mismo titular escrito distinto."""
    texto = normalizar_texto(titular).upper()
    texto = re.sub(r"\b(?:[A-Z]\.){1,}[A-Z]?\.?", lambda m: m.group(0).replace(".", ""), texto)
    texto = re.sub(r"[.,]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _mapa_encabezados(
    columnas: list[str],
    columnas_fecha: dict[Hito, tuple[str, ...]],
    columnas_texto: dict[Columna, tuple[str, ...]],
) -> dict[str, str]:
    """Devuelve {encabezado original: nombre canónico}."""
    buscados: dict[str, str] = {}
    for hito, alias in columnas_fecha.items():
        for a in alias:
            buscados[normalizar_texto(a)] = hito.value
    for col, alias in columnas_texto.items():
        for a in alias:
            buscados[normalizar_texto(a)] = col.value
    mapa: dict[str, str] = {}
    for original in columnas:
        canonico = buscados.get(normalizar_texto(original))
        if canonico and canonico not in mapa.values():
            mapa[original] = canonico
    return mapa


def _a_fecha(valor: object) -> tuple[pd.Timestamp | None, bool]:
    """Convierte una celda a fecha. Devuelve (fecha, formato_no_reconocido)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or valor is pd.NaT:
        return None, False
    if isinstance(valor, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(valor).normalize(), False
    if isinstance(valor, (int, float)):
        # número de serie de Excel
        if 20000 < float(valor) < 80000:
            return (EXCEL_ORIGEN + pd.Timedelta(days=float(valor))).normalize(), False
        return None, True
    texto = str(valor).strip()
    if not texto:
        return None, False
    convertido = pd.to_datetime(texto, dayfirst=True, errors="coerce")
    if pd.isna(convertido):
        return None, True
    return pd.Timestamp(convertido).normalize(), False


def _unir_actos_en_tramites(df: pd.DataFrame) -> pd.DataFrame:
    """Adaptado de CARS_nuevo/app.py (unir_actos_en_tramites).

    El Excel tiene una fila por ACTO (auto, resolución...), así que un mismo trámite puede
    aparecer varias veces. Para no contarlo doble:
    1. Si "Archivo" trae número de expediente, todos sus actos son un solo trámite.
    2. Filas del mismo titular y categoría con las mismas fechas son el mismo trámite.
    3. Un auto sin resolución cuyo radicado y fecha de auto coinciden con un trámite ya
       resuelto es el auto de ESE trámite: se quita (uno por cada resolución).
    Titulares genéricos ("Persona natural", "Alcaldía", vacío) nunca se unen entre sí.
    """
    df = df.copy()
    fechas = [c for c in COLUMNAS_FECHA if c in df.columns]
    archivo = df[Columna.ARCHIVO.value] if Columna.ARCHIVO.value in df else pd.Series("", index=df.index)
    exp = archivo.astype(str).str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
    es_exp = archivo.notna() & ~archivo.astype(str).str.lower().str.endswith(".pdf") & exp.str.match(
        r"^[A-Z]{2,6}\d{3,}"
    )
    df["_expediente"] = (df[Columna.CAR.value] + "|" + exp).where(es_exp)
    if es_exp.any():
        con_exp = df[es_exp]
        agg: dict[str, object] = {c: "first" for c in con_exp.columns if c != "_expediente"}
        agg.update({c: "min" for c in fechas})
        con_exp = con_exp.groupby("_expediente", as_index=False).agg(agg)
        df = pd.concat([df[~es_exp], con_exp], ignore_index=True)

    clave_tit = df[Columna.TITULAR_CLAVE.value].fillna("")
    individual = clave_tit.isin(TITULARES_GENERICOS) | df["_expediente"].notna()
    df["_unico"] = ""
    df.loc[individual, "_unico"] = [f"f{i}" for i in range(int(individual.sum()))]
    df["_k"] = (
        df[Columna.CAR.value] + "|" + clave_tit + "|" + df[Columna.CATEGORIA.value].fillna("") + "|" + df["_unico"]
    )
    clave_completa = ["_k", *fechas]
    if Columna.TIPO_ACTO.value in df:
        es_resolucion = df[Columna.TIPO_ACTO.value].astype(str).str.lower().str.startswith("resol")
        df["_revisar"] = es_resolucion & df[Hito.RESOLUCION.value].isna()
    else:
        df["_revisar"] = False
    unidos = df.drop_duplicates(subset=clave_completa).copy()

    resueltos = unidos[unidos[Hito.RESOLUCION.value].notna()]
    clave_auto = ["_k", Hito.RADICADO.value, Hito.AUTO.value]
    cupo = resueltos.groupby(clave_auto, dropna=True).size().to_dict()
    quitar: list[int] = []
    for i, fila in unidos[unidos[Hito.RESOLUCION.value].isna() & ~unidos["_revisar"]].iterrows():
        k = tuple(fila[c] for c in clave_auto)
        if cupo.get(k, 0) > 0:
            cupo[k] -= 1
            quitar.append(i)
    unidos = unidos.drop(index=quitar)
    return unidos.drop(columns=["_k", "_unico", "_revisar", "_expediente"]).reset_index(drop=True)


def _problema(fila: pd.Series, problema: str, detalle: str) -> dict[str, object]:
    return {
        "Hoja": fila.get(Columna.HOJA.value, ""),
        "Fila Excel": fila.get(Columna.FILA_EXCEL.value, ""),
        "CAR": fila.get(Columna.CAR.value, ""),
        "Titular": fila.get(Columna.TITULAR.value, ""),
        "Problema": problema,
        "Detalle": detalle,
    }


def cargar_historico(
    ruta: Path,
    columnas_fecha: dict[Hito, tuple[str, ...]],
    columnas_texto: dict[Columna, tuple[str, ...]],
    categorias: tuple[str, ...],
    cars_excluidas: frozenset[str],
    fecha_minima: date,
    hoy: date,
) -> HistoricoCargado:
    libro = pd.ExcelFile(ruta)
    resultado = HistoricoCargado(tramites=pd.DataFrame(), problemas=pd.DataFrame(), hojas=list(libro.sheet_names))

    partes: list[pd.DataFrame] = []
    for hoja in libro.sheet_names:
        crudo = pd.read_excel(libro, sheet_name=hoja, dtype=object)
        mapa = _mapa_encabezados([str(c) for c in crudo.columns], columnas_fecha, columnas_texto)
        tiene_fechas = any(v in COLUMNAS_FECHA for v in mapa.values())
        if Columna.CAR.value not in mapa.values() or not tiene_fechas:
            continue
        resultado.hojas_usadas.append(hoja)
        for original, canonico in mapa.items():
            resultado.columnas_encontradas.setdefault(canonico, original)
        parte = crudo[list(mapa)].rename(columns=mapa)
        parte[Columna.HOJA.value] = hoja
        parte[Columna.FILA_EXCEL.value] = parte.index + 2  # fila 1 = encabezados
        partes.append(parte)

    esperadas = [h.value for h in columnas_fecha] + [c.value for c in columnas_texto]
    resultado.columnas_faltantes = [c for c in esperadas if c not in resultado.columnas_encontradas]
    if not partes:
        resultado.problemas = pd.DataFrame([{"Problema": "No se encontró ninguna hoja con columna CAR y fechas"}])
        return resultado

    df = pd.concat(partes, ignore_index=True)
    for col in [*COLUMNAS_FECHA, *(c.value for c in columnas_texto)]:
        if col not in df.columns:
            df[col] = None
    resultado.filas_leidas = len(df)
    problemas: list[dict[str, object]] = []

    # Texto
    df[Columna.CAR.value] = df[Columna.CAR.value].map(lambda v: normalizar_texto(v).upper().replace(" ", ""))
    df[Columna.TITULAR.value] = df[Columna.TITULAR.value].map(
        lambda v: None if pd.isna(v) else re.sub(r"\s+", " ", str(v)).strip().rstrip(",")
    )
    df[Columna.TITULAR_CLAVE.value] = df[Columna.TITULAR.value].map(_clave_titular)
    df[Columna.CATEGORIA.value] = df[Columna.CATEGORIA.value].map(
        lambda v: None if pd.isna(v) else re.sub(r"\s+", " ", str(v)).strip()
    )

    # Filtros: categoría y CAR excluidas
    categorias_norm = {normalizar_texto(c) for c in categorias}
    en_categoria = df[Columna.CATEGORIA.value].map(normalizar_texto).isin(categorias_norm)
    resultado.filas_otras_categorias = int((~en_categoria).sum())
    df = df[en_categoria]
    excluida = df[Columna.CAR.value].isin(cars_excluidas)
    resultado.filas_cars_excluidas = int(excluida.sum())
    df = df[~excluida].copy()

    sin_car = df[Columna.CAR.value] == ""
    for _, fila in df[sin_car].iterrows():
        problemas.append(_problema(fila, "Sin CAR", "La fila no indica la autoridad ambiental; no se usa."))
    df = df[~sin_car].copy()

    # Fechas: formato, fechas imposibles
    minimo = pd.Timestamp(fecha_minima)
    maximo = pd.Timestamp(hoy)
    for hito in ORDEN_HITOS:
        col = hito.value
        convertidas: list[pd.Timestamp | None] = []
        for idx, valor in df[col].items():
            fecha, no_reconocida = _a_fecha(valor)
            fila = df.loc[idx]
            if no_reconocida:
                problemas.append(
                    _problema(fila, "Formato de fecha no reconocido", f"{NOMBRE_HITO[hito]}: «{valor}»")
                )
            if fecha is not None and not (minimo <= fecha <= maximo):
                problemas.append(
                    _problema(fila, "Fecha imposible", f"{NOMBRE_HITO[hito]}: {fecha.date()} (fuera de rango)")
                )
                fecha = None
            convertidas.append(fecha)
        df[col] = pd.to_datetime(pd.Series(convertidas, index=df.index, dtype="object"))

    # Registros vacíos o incompletos
    n_fechas = df[COLUMNAS_FECHA].notna().sum(axis=1)
    for _, fila in df[n_fechas == 0].iterrows():
        problemas.append(_problema(fila, "Fechas vacías", "La fila no tiene ninguna fecha; no se usa."))
    for _, fila in df[n_fechas == 1].iterrows():
        problemas.append(
            _problema(fila, "Registro incompleto", "Solo tiene una fecha; no permite calcular ningún tiempo.")
        )
    df = df[n_fechas > 0].copy()

    # Fechas invertidas (cualquier hito posterior con fecha anterior a uno previo).
    # No se sabe cuál de las dos fechas está mal, así que ambas quedan marcadas como dudosas
    # y ningún tramo que las use entra en las estadísticas.
    dudosos: dict[int, set[str]] = {i: set() for i in df.index}
    for i, desde in enumerate(ORDEN_HITOS):
        for hasta in ORDEN_HITOS[i + 1 :]:
            invertidas = df[desde.value].notna() & df[hasta.value].notna() & (df[hasta.value] < df[desde.value])
            for idx_fila, fila in df[invertidas].iterrows():
                dudosos[idx_fila].update({desde.value, hasta.value})
                dias = (fila[desde.value] - fila[hasta.value]).days
                problemas.append(
                    _problema(
                        fila,
                        "Fechas invertidas",
                        f"{NOMBRE_HITO[hasta]} ({fila[hasta.value].date()}) es {dias} días anterior a "
                        f"{NOMBRE_HITO[desde]} ({fila[desde.value].date()}). Ese tramo no se usa.",
                    )
                )

    df[COLUMNA_DUDOSOS] = pd.Series({i: ",".join(sorted(v)) for i, v in dudosos.items()})

    antes = len(df)
    df = _unir_actos_en_tramites(df)
    resultado.actos_unidos = antes - len(df)

    resultado.tramites = df.reset_index(drop=True)
    resultado.problemas = pd.DataFrame(
        problemas, columns=["Hoja", "Fila Excel", "CAR", "Titular", "Problema", "Detalle"]
    )
    return resultado

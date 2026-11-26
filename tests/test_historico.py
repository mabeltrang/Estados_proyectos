from datetime import date

from config import ajustes
from core.historico import cargar_historico


def cargar():
    return cargar_historico(ajustes.RUTA_HISTORICO, ajustes.COLUMNAS_FECHA_HISTORICO, ajustes.COLUMNAS_TEXTO_HISTORICO,
                            ajustes.CATEGORIAS_HISTORICO, ajustes.CARS_HISTORICO_EXCLUIDAS,
                            ajustes.FECHA_MINIMA_VALIDA, date(2026, 11, 26))


def test_lee_excel_real_sin_columnas_faltantes():
    h = cargar()
    assert h.hojas_usadas and not h.columnas_faltantes
    assert set(h.tramites["car"]) <= {"CORPOCESAR", "CORPOGUAJIRA"}
    assert len(h.tramites) > 0


def test_reporta_fechas_invertidas_y_no_las_usa():
    from config.constantes import Hito
    from core.estadisticas import BaseTiempos
    h = cargar()
    assert (h.problemas["Problema"] == "Fechas invertidas").any()
    base = BaseTiempos(h.tramites, ajustes.UNIDAD_DIAS)
    assert (base.valores_generales(Hito.RADICADO, Hito.AUTO) >= 0).all()
    assert base.valores_generales(Hito.VISITA, Hito.RESOLUCION).max() < 3000

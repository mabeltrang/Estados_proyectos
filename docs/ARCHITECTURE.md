# Arquitectura

## Qué es y qué no hace
Tablero interno de solo lectura: lee el estado forestal de cada proyecto en TSF (API de Unergy),
lo homologa a la etapa del flujo de su CAR y muestra el % de avance. No escribe en la API, no guarda
datos y no modifica el Excel histórico. El motor de tiempos (core/prediccion.py) existe pero no se
muestra por ahora.

## Stack
Python 3.12 + Streamlit (Community Cloud). Sin persistencia propia.
Ver `docs/adr/0001-streamlit-y-google-sheets.md`.

## Capas y dependencias
`paginas/` → `ui/` → `core/` → `config/`. `core/` no importa Streamlit.
- `core/api_unergy.py`: único módulo con acceso HTTP (solo GET).
- `core/historico.py`: lectura y calidad del Excel.
- `core/estadisticas.py`: duraciones por tramo y elección de antecedentes.
- `core/prediccion.py`: reglas de negocio (reloj, semáforo, resolución).
- `config/homologacion.py`: equivalencia etapa ↔ estado TSF.
- `ui/datos.py`: caché de Streamlit y unión de todo para las páginas. La API se consulta bajo
  demanda (búsqueda con `?search=` y detalle de un terreno); la vista general sale del Google Sheet.

## Modelo de datos
- Proyecto = Minifarm (`minifarms[]` del detalle forestal). Se identifica por `minifarm_id`.
- Estado TSF: campo configurado en `ajustes.CAMPOS_ESTADO_FORESTAL`.
- No hay datos propios guardados.

## Glosario
- **Etapa:** paso del flujo de una CAR (texto del desplegable).
- **Hito (⏱):** etapa con fecha en el histórico; `config.constantes.Hito`.
- **Tramo:** par de hitos (ej. Radicado → Auto).
- **Reloj:** último hito alcanzado con fecha registrada.

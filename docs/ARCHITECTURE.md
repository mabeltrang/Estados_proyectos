# Arquitectura

## Qué es y qué no hace
Tablero interno para estimar tiempos de trámites de aprovechamiento forestal por CAR.
No escribe en la API de Unergy, no usa modelos de IA para predecir y no modifica el Excel histórico.

## Stack
Python 3.12 + Streamlit (Community Cloud). Persistencia en Google Sheets vía `gspread`.
Ver `docs/adr/0001-streamlit-y-google-sheets.md`.

## Capas y dependencias
`paginas/` → `ui/` → `core/` → `config/`. `core/` no importa Streamlit.
- `core/api_unergy.py`: único módulo con acceso HTTP (solo GET).
- `core/historico.py`: lectura y calidad del Excel.
- `core/estadisticas.py`: duraciones por tramo y elección de antecedentes.
- `core/prediccion.py`: reglas de negocio (reloj, semáforo, resolución).
- `core/almacenamiento.py`: Google Sheets o memoria.
- `ui/datos.py`: caché de Streamlit y unión de todo para las páginas. La API se consulta bajo
  demanda (búsqueda con `?search=` y detalle de un terreno); la vista general sale del Google Sheet.

## Modelo de datos
- Proyecto = Minifarm (`minifarms[]` del detalle forestal). Se identifica por `minifarm_id`.
- Seguimiento (Google Sheets): `seguimiento` (CAR manual y efectiva, etapa actual, terreno, ubicación), `fechas_etapas`
  (fecha por etapa), `historial_cambios` (bitácora solo de agregar).

## Glosario
- **Etapa:** paso del flujo de una CAR (texto del desplegable).
- **Hito (⏱):** etapa con fecha en el histórico; `config.constantes.Hito`.
- **Tramo:** par de hitos (ej. Radicado → Auto).
- **Reloj:** último hito alcanzado con fecha registrada.

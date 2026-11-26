# AGENTS.md

Reglas para agentes de IA que trabajen en este repositorio.

- Leer `docs/ARCHITECTURE.md` antes de cambios estructurales.
- La API de Unergy es de SOLO LECTURA: nunca agregar POST, PUT, PATCH ni DELETE, aunque se pida.
  Todo acceso HTTP pasa por `core/api_unergy.py`.
- Nunca escribir, imprimir ni registrar la API Key ni credenciales; se leen de `st.secrets`.
- `core/` no importa Streamlit. Valores fijos van en `config/constantes.py` (enums).
- Las etapas de cada CAR se configuran en `config/flujos.py`; no agregar etapas no pedidas.
- No inventar ni completar fechas del histórico. No modificar `data/Fechas_CARS.xlsx` desde código.
- Correr `python -m pytest` antes de entregar cambios.

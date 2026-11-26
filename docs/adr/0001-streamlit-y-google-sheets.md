# ADR 0001 — Streamlit y Google Sheets

**Estado:** aceptado · 2026-11

## Contexto
El estándar de Unergy (ADR-0001 de calidad) indica Nuxt + Supabase para herramientas nuevas.
Esta herramienta la mantiene una persona no desarrolladora, reutiliza código Python existente
(`CARS_nuevo`, `analisis-compensacion-forestal`) y es de uso interno de un equipo pequeño.

## Decisión
- Streamlit en Community Cloud, en repositorio privado y con acceso restringido por invitación.
- Google Sheets para el seguimiento manual: el responsable puede revisarlo y corregirlo a mano.
- El almacenamiento está aislado en `core/almacenamiento.py`; migrar a Supabase solo cambia ese módulo.

## Desviaciones del estándar
Sin Nuxt, sin Supabase, sin RLS. Si la herramienta pasa a uso amplio o a datos de personas,
revisar con tecnología y migrar.

## Actualización (2026-11)
La app pasó a ser de solo lectura (estado TSF → etapa homologada → % de avance). Se eliminó Google
Sheets: no hay datos propios que guardar.

# Seguimiento forestal · Unergy

Tablero de **solo lectura** en Streamlit. Lee de la API de Unergy el estado forestal de cada
proyecto en TSF, lo homologa a la etapa del flujo de su CAR y muestra el % de avance.
La app no cambia estados ni guarda nada.

- La API se usa **solo con GET** (nunca escribe en ella).
- La CAR se identifica por municipio con la tabla de `analisis-compensacion-forestal`.

## Cómo se usa

- **Proyectos** (página principal): escribe parte del nombre comercial, del proyecto o del terreno.
  Aparecen todos sus proyectos con: CAR, Estado TSF, Etapa homologada y Avance. Selecciona uno para
  ver el detalle (estado, avance y el flujo de etapas de su CAR). «← Volver» regresa a la búsqueda.
- **Resumen general:** con el botón «Cargar resumen» consulta todos los terrenos (tarda varios
  minutos la primera vez; luego queda guardado una hora) y muestra totales por estado y por CAR.
- **Histórico y calidad de datos:** revisión del Excel de tiempos de las CAR.
- **Explorar API:** probar conexión, ver campos y ubicar en qué campo viene un dato.

## Homologación TSF → etapa de la CAR

El estado se lee del campo `forestry_license_resolution` de cada proyecto (configurable en
`config/ajustes.py`). Si el valor no es un estado de TSF, aparece «No encontrado».
`forestry_licence` no es el estado: es el tipo de permiso.

La tabla `ETAPA_A_TSF` de `config/homologacion.py` dice qué estado de TSF corresponde a cada etapa:

| Etapas | Estado TSF |
|---|---|
| Inventario | Programado (se mandó a inventario) |
| Informes | Por radicar |
| Radicado, Radicación, autos y publicaciones | Solicitud radicada |
| Pagos y liquidaciones (del auto/evaluación o de la tasa) | Liquidación |
| Visita, Visita técnica, Acta | Visita |
| Resolución | Solicitud aprobada |

Con eso, para cada proyecto:

- **Una sola etapa posible** en el flujo de su CAR → esa etapa y su % de avance.
- **Varias posibles** (ej. «Solicitud radicada» en CORPOCESAR: Radicado o Llega auto) → la app no
  elige: muestra las posibles y el rango de avance (29–43 %).
- **Ninguna** (Requerimientos, Respuesta a requerimientos, Respuesta radicado, Pausado, Solicitud
  rechazada, Exonerado) → «Sin homologación».

**Avance** = etapas cumplidas sobre el total de etapas del flujo de esa CAR
(Inventario = 0 %, Resolución = 100 %).

## Qué hay en cada carpeta

| Ruta | Contenido |
|---|---|
| `app.py` | Arranque: contraseña opcional y menú de páginas |
| `paginas/` | Proyectos, resumen general, histórico y explorar API |
| `config/flujos.py` | Etapas de cada CAR |
| `config/homologacion.py` | Equivalencia entre etapas y estados de TSF |
| `config/ajustes.py` | Campo del estado TSF, parámetros de la API y del histórico |
| `config/car_lookup.py`, `config/municipios_car.csv` | Copia de la tabla municipio → CAR |
| `data/Fechas_CARS.xlsx` | Copia del histórico de tiempos (solo lectura) |
| `core/` | Lógica: API, proyectos, homologación, histórico y motor de tiempos |
| `ui/` | Estilos Unergy y datos para las páginas |
| `tests/` | Pruebas automáticas |

El motor de cuenta regresiva y proyección de resolución (`core/prediccion.py`,
`core/estadisticas.py`) sigue en el repositorio con sus pruebas, pero no se muestra por ahora.

## 1. Crear el repositorio en GitHub

1. **New repository** → marca **Private** → Create.
2. **Add file → Upload files** y arrastra *el contenido* de la carpeta (incluida `.streamlit`).
   Sube todo en una sola carga y un solo commit.
3. No subas `secrets.toml`.

## 2. Publicar en Streamlit Community Cloud

1. share.streamlit.io → **Create app** → repo, rama `main`, archivo `app.py`.
2. **Advanced settings** → Python 3.12 o superior.
3. **Secrets**:

   ```toml
   [unergy]
   api_key = "TU_API_KEY"
   base_url = "https://originabot.uner.gy"
   ```

   Opcional, para pedir contraseña al entrar:

   ```toml
   [app]
   password = "una-clave"
   ```
4. En **Settings → Sharing** confirma que solo las personas invitadas pueden verla.

## 3. Correr en tu computador (opcional)

```bash
pip install -r requirements-dev.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # y pon tu api_key
streamlit run app.py
python -m pytest
```

## Tareas frecuentes

- **Cambiar una equivalencia:** edita `ETAPA_A_TSF` en `config/homologacion.py`.
- **Agregar o cambiar etapas de una CAR:** edita `config/flujos.py` y su equivalencia en
  `config/homologacion.py` (las pruebas verifican que toda etapa tenga estado TSF).
- **Si el estado TSF viene en otro campo:** cambia `CAMPOS_ESTADO_FORESTAL` en `config/ajustes.py`.
  Para ubicarlo, usa «Explorar API → 3» y escribe el estado en «Texto a ubicar».

## Seguridad

- El cliente de la API (`core/api_unergy.py`) solo tiene GET y solo acepta rutas
  `/api/roles/forest/` y `/api/roles/environmental/`. Hay pruebas que lo verifican.
- La API Key vive solo en Secrets; no aparece en el código, en pantalla ni en errores.

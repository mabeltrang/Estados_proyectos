# Seguimiento forestal · Unergy

Tablero en Streamlit para seguir los trámites de aprovechamiento forestal de cada proyecto
(Minifarm) ante su CAR. Estima cuándo llega el siguiente paso y cuándo saldría la resolución,
usando los tiempos de expedientes anteriores.

- Lee los proyectos de la API de Unergy **solo con GET** (nunca escribe en ella).
- Identifica la CAR por municipio con la tabla de `analisis-compensacion-forestal`.
- Usa el Excel histórico de `CARS_nuevo` para calcular los tiempos.
- Guarda los estados y fechas que registras en una hoja de Google Sheets.

## Cómo se usa

- **Proyectos:** escribe parte del nombre comercial, del proyecto o del terreno. Eliges el terreno,
  luego el proyecto (si el terreno tiene varios), y ves su estado. «← Volver a la búsqueda» te
  regresa con el mismo texto para abrir otro. Sin texto, la página muestra los proyectos que ya
  tienen seguimiento guardado.
- **Vista general:** resumen de los proyectos en seguimiento. No consulta la API, así que carga rápido.
- La API solo se consulta al buscar (unas pocas llamadas) y al abrir un terreno (una llamada).
  Recorrer todos los terrenos solo ocurre en «Explorar API → Analizar todos», y puede tardar minutos.

## Qué hay en cada carpeta

| Ruta | Contenido |
|---|---|
| `app.py` | Arranque: contraseña opcional y menú de páginas |
| `paginas/` | Las cuatro pantallas: vista general, proyectos, histórico, explorar API |
| `config/flujos.py` | **Etapas de cada CAR.** Aquí se agregan o cambian etapas |
| `config/ajustes.py` | Mínimo de antecedentes, días calendario/hábiles, CAR excluidas, encabezados del Excel |
| `config/car_lookup.py`, `config/municipios_car.csv` | Copia de la tabla municipio → CAR |
| `data/Fechas_CARS.xlsx` | Copia del histórico (solo lectura) |
| `core/` | Lógica: API, histórico, estadísticas, predicción, almacenamiento |
| `ui/` | Estilos, tarjetas y unión de datos para las páginas |
| `tests/` | Pruebas automáticas |

## 1. Crear el repositorio en GitHub

1. En GitHub: **New repository** → nombre `seguimiento-forestal` → marca **Private** → Create.
2. Descomprime el zip en tu computador.
3. En la página del repositorio: **Add file → Upload files** y arrastra *el contenido* de la carpeta
   (incluidas las carpetas `.streamlit`, `config`, etc.). Si no ves `.streamlit` por estar oculta,
   súbela aparte o usa GitHub Desktop.
4. **No subas** un archivo `secrets.toml` ni el JSON de Google. El `.gitignore` los bloquea si usas git.

## 2. Publicar en Streamlit Community Cloud

1. En share.streamlit.io → **Create app** → elige el repo, rama `main`, archivo `app.py`.
2. En **Advanced settings** elige Python **3.12** (la app necesita 3.11 o superior).
3. En **Secrets** pega el contenido de `.streamlit/secrets.toml.example` con tus valores
   (como mínimo la `api_key`).
4. Deploy. Luego en **Settings → Sharing** confirma que solo las personas invitadas pueden verla:
   la app muestra datos internos de Unergy.

## 3. Guardar el seguimiento (Google Sheets)

Streamlit Cloud reinicia la app de vez en cuando y borra cualquier archivo que la app haya escrito.
Por eso los estados y fechas se guardan en una hoja de Google. Sin esto la app funciona, pero
avisa que los cambios se perderán.

1. Entra a console.cloud.google.com y crea un proyecto (ej. `seguimiento-forestal`).
2. **APIs y servicios → Biblioteca**: habilita *Google Sheets API* y *Google Drive API*.
3. **APIs y servicios → Credenciales → Crear credenciales → Cuenta de servicio**. Ponle un nombre y termina.
4. Abre la cuenta creada → pestaña **Claves → Agregar clave → JSON**. Se descarga un archivo.
   Guárdalo en un lugar seguro; no lo subas a GitHub ni lo compartas por chat.
5. Crea una hoja de Google vacía (ej. "Seguimiento forestal"). **Compartir** → pega el
   `client_email` del JSON → permiso **Editor**.
6. En los Secrets de Streamlit:
   - `[gsheets] spreadsheet_url` = URL de la hoja.
   - `[gcp_service_account]` = copia cada valor del JSON en su línea. La `private_key` va completa,
     entre comillas, tal como aparece en el JSON (con los `\n`).

La app crea sola tres pestañas en la hoja:
`seguimiento` (etapa actual por proyecto), `fechas_etapas` (fecha de cada etapa) e
`historial_cambios` (quién cambió qué y cuándo). Puedes abrirlas y revisarlas; si corriges algo a
mano, pulsa "Rerun" o recarga la página.

> Si Google no te deja crear la clave (política de la organización), pide a tecnología que
> cree la cuenta de servicio y cargue los Secrets.

## 4. Correr en tu computador (opcional)

```bash
pip install -r requirements-dev.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # y llena tus valores
streamlit run app.py
python -m pytest                                              # pruebas
```

## Cómo se calcula la predicción

- Cada CAR tiene su propia secuencia de etapas (`config/flujos.py`). Las etapas marcadas con ⏱
  corresponden a una fecha del Excel (radicado, auto, visita, resolución) y son las únicas con
  tiempos históricos. Las demás (pagos, publicaciones, acta) se registran, pero el reloj sigue
  corriendo desde el último ⏱.
- **Siguiente hito:** días desde el último ⏱ frente a los antecedentes del tramo hasta el próximo ⏱.
  La cuenta regresiva va hasta la mediana; si la pasó, muestra los días de retraso.
- **Semáforo:** verde hasta el P25, amarillo hasta la mediana, naranja hasta el P75, rojo después.
- **Resolución:** toma los expedientes que, desde ese mismo ⏱, tardaron más de lo que este
  proyecto ya lleva, y les resta ese tiempo. Muestra un rango (escenario rápido, probable, lento).
- **Origen del dato:** histórico propio (≥ `MIN_ANTECEDENTES` expedientes), histórico limitado
  (menos, con advertencia) o referencia general (otras CAR, solo si la CAR no tiene ninguno).
- La fecha de guardado no se usa como fecha de la etapa: cada fecha se registra a mano.

## Tareas frecuentes

- **Actualizar el histórico:** reemplaza `data/Fechas_CARS.xlsx` por la versión nueva de
  `CARS_nuevo` (mismo nombre). Si cambian los encabezados, agrégalos en `config/ajustes.py`.
- **Agregar o cambiar etapas:** edita `config/flujos.py`. Las pruebas (`tests/test_flujos.py`)
  verifican el número de etapas; actualízalo ahí también.
- **Incluir CORPOBOYACÁ o CAR:** agrega su flujo y quítala de `CARS_HISTORICO_EXCLUIDAS`.
- **Días hábiles:** cambia `UNIDAD_DIAS` en `config/ajustes.py` (no descuenta festivos).

## Seguridad

- El cliente de la API (`core/api_unergy.py`) solo tiene GET y solo acepta rutas
  `/api/roles/forest/` y `/api/roles/environmental/`. Hay pruebas que lo verifican.
- La API Key vive solo en Secrets; no aparece en el código, en pantalla ni en mensajes de error.
- Opcional: `[app] password` en Secrets agrega una contraseña a la entrada.

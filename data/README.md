# Datos y procedencia

El procedimiento completo, las decisiones y las limitaciones están en
[`docs/05_data_calibration.md`](../docs/05_data_calibration.md).

## Clasificación de fuentes

Todo valor publicado lleva una de estas etiquetas:

| Etiqueta | Significado |
|---|---|
| `observed_public` | Observado en una fuente pública (registros individuales de NHAMCS; no se versionan) |
| `derived_from_public` | Calculado a partir de datos públicos |
| `estimated_assumption` | Supuesto o estimación del equipo |
| `synthetic_simulation` | Generado por el modelo |

| Recurso | Categoría | Uso |
|---|---|---|
| `raw/ed2022.zip`, `raw/eddict2022.dct` | `observed_public` | Entrada del pipeline; no se versionan |
| `processed/nhamcs_2022_hourly_profile.csv` | `derived_from_public` | Forma del perfil horario de llegadas |
| `processed/nhamcs_2022_triage_profile.csv` | `derived_from_public` | Probabilidades de triaje 1–5 |
| `processed/nhamcs_2022_reference_volume.csv` | `derived_from_public` | Volumen diario del departamento de referencia |
| `processed/nhamcs_2022_reference_metrics.csv` | `derived_from_public` | Referencia de validación de `WAITTIME`; no se usa para ajustar |
| `processed/nhamcs_2022_service_proxy.csv` | `derived_from_public` | Cota superior de ocupación (`LOV − WAITTIME − BOARDED`) |
| `processed/calibration_metadata.json` | metadatos | Checksums, validaciones, códigos especiales y supuestos |
| `processed/default_hourly_profile.csv` | `estimated_assumption` | Perfil de demostración de las Partes 3 y 4 |
| Llegadas, esperas y colas simuladas | `synthetic_simulation` | Evaluación de escenarios |

Las columnas y unidades de cada CSV están descritas en la sección 7 de
`docs/05_data_calibration.md` y en el campo `outputs` del archivo de metadatos.
Cada CSV incluye las columnas `unit` y `source_category`.

## Regenerar los datos procesados

Desde la raíz del repositorio, con el entorno instalado:

```powershell
python scripts/download_nhamcs.py      # descarga a data/raw/ y verifica SHA-256
python scripts/prepare_nhamcs.py       # escribe data/processed/nhamcs_2022_*
pytest tests/test_calibration.py
```

Si la descarga automática falla, se pueden descargar manualmente estos archivos
en `data/raw/` y verificarlos con
`python scripts/download_nhamcs.py --verify-only`:

- https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHAMCS/ed2022.zip
- https://ftp.cdc.gov/pub/Health_Statistics/NCHS/dataset_documentation/NHAMCS/stata/eddict2022.dct
- https://ftp.cdc.gov/pub/Health_Statistics/NCHS/dataset_documentation/NHAMCS/doc22-ed-508.pdf
  (opcional; libro de códigos)

## Variables utilizadas

| Variable | Contenido | Uso |
|---|---|---|
| `ARRTIME` | Hora de llegada (HHMM) | Perfil horario y bloque de llegada |
| `WAITTIME` | Minutos hasta el primer contacto con médico/APRN/PA | Validación |
| `LOV` | Duración de la visita, en minutos | Proxy de servicio (solo referencia) |
| `BOARDED` | Minutos de *boarding* | Proxy de servicio |
| `IMMEDR` | Nivel de triaje 1–5 | Probabilidades de triaje y subgrupos |
| `LWBS`, `LBTC`, `LEFTAMA` | Salida antes de la atención o contra consejo médico | Exclusión del proxy |
| `PATWT` | Peso de la visita | Todas las estimaciones |
| `EDWT`, `HOSPCODE` | Peso y código del departamento | Volumen por departamento |
| `CSTRATM`, `CPSUM` | Estrato y conglomerado enmascarados | Errores estándar |
| `YEAR` | Año de la encuesta | Validación del archivo |

## Reglas

- `raw/` no se versiona y contiene únicamente archivos obtenidos de la fuente.
  El readme oficial restringe el uso a fines estadísticos y prohíbe intentar
  identificar personas o establecimientos.
- `processed/` contiene únicamente agregados pequeños y reproducibles. No se
  editan a mano.
- Cada archivo procesado indica si sus valores son observados, derivados,
  estimados o sintéticos.
- No se almacenan credenciales ni información personal.
- NHAMCS describe departamentos de emergencias de Estados Unidos; no representa
  a un hospital guatemalteco específico.

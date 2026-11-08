# Parte 5a. Datos públicos y calibración con NHAMCS 2022

Este documento describe cómo se obtiene, valida, limpia y resume el archivo
público NHAMCS 2022 para calibrar el modelo, y qué valores del modelo son
observados, derivados, estimados o sintéticos. Todo lo descrito se regenera con
dos comandos (sección 3); ninguna tabla procesada se edita a mano.

## 1. Objetivo y alcance

La calibración tiene tres fines:

1. reemplazar el perfil horario estimado por uno derivado de `ARRTIME`;
2. reemplazar las probabilidades de triaje estimadas por las derivadas de `IMMEDR`;
3. reservar la distribución observada de `WAITTIME` como **referencia de
   validación**, sin usarla para ajustar parámetros.

La duración de la atención (`service_medians_minutes`) **no** se calibra con
NHAMCS por la razón explicada en la sección 8.4.

## 2. Fuente

| Campo | Valor |
|---|---|
| Conjunto | NHAMCS 2022 Emergency Department Public Use File |
| Publicador | National Center for Health Statistics (NCHS), CDC |
| Periodo | Año calendario 2022; cada hospital muestreado reporta durante un periodo de 4 semanas asignado al azar |
| Población | Visitas a departamentos de emergencias de hospitales generales y de estancia corta no institucionales, excluidos hospitales federales, militares y de la VA, en los 50 estados y DC |
| Muestra | 16,025 visitas en 188 departamentos; 8 estratos y 122 conglomerados de diseño |
| Total ponderado | 155,397,747 visitas (suma de `PATWT`, verificada por código) |
| Datos | `ed2022.zip`, https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHAMCS/ed2022.zip |
| Diccionario de columnas | `eddict2022.dct`, https://ftp.cdc.gov/pub/Health_Statistics/NCHS/dataset_documentation/NHAMCS/stata/eddict2022.dct |
| Documentación | `doc22-ed-508.pdf`, https://ftp.cdc.gov/pub/Health_Statistics/NCHS/dataset_documentation/NHAMCS/doc22-ed-508.pdf |
| Fecha de acceso | 2026-11-08 |

Tamaño y SHA-256 de cada archivo están fijados en
`src/ed_simulation/calibration.py` (`NHAMCS_2022_FILES`) y se copian a
`data/processed/calibration_metadata.json`.

**Condiciones de uso.** El readme oficial de 2022 restringe el uso a fines
estadísticos y prohíbe intentar identificar personas o establecimientos. Por eso
el archivo crudo no se versiona (`data/raw/` está en `.gitignore`) y el
repositorio solo publica agregados.

## 3. Obtención reproducible

```powershell
python scripts/download_nhamcs.py          # descarga y verifica SHA-256
python scripts/download_nhamcs.py --verify-only
python scripts/prepare_nhamcs.py           # genera data/processed/nhamcs_2022_*
pytest tests/test_calibration.py
```

`download_nhamcs.py` escribe `data/raw/download_manifest.json` con URL, fecha de
acceso, tamaño y checksum. Si un archivo no coincide con el checksum esperado,
el proceso se detiene. Esto detecta descargas truncadas, años equivocados o una
versión republicada por CDC. Si CDC publica una nueva versión, se debe
actualizar `NHAMCS_2022_FILES` y documentar el cambio antes de recalibrar.

La transformación es determinista: dos ejecuciones sobre los mismos archivos
producen salidas idénticas byte a byte (no se escriben marcas de tiempo). La
prueba `test_official_file_reproduces_versioned_outputs` lo comprueba cuando el
archivo oficial está descargado.

## 4. Lectura y validación del archivo

El archivo de datos es texto de ancho fijo (2,382 caracteres por registro). Las
posiciones de cada variable se leen del diccionario oficial de Stata en lugar de
copiarlas a mano. Antes de calcular nada se comprueba que:

- todos los registros tengan la longitud que implica el diccionario;
- existan exactamente 16,025 registros;
- `YEAR` sea 2022 en todos los registros;
- la suma de `PATWT` coincida con 155,397,747 (tolerancia de 5 visitas por
  redondeo de los pesos a 5 decimales);
- `PATWT` sea positivo en todos los registros.

El marcador `.` (faltante de Stata, presente en `EDWT` fuera del primer registro
de cada departamento) se convierte en faltante y nunca en cero.

## 5. Códigos especiales y faltantes

Los códigos provienen del libro de códigos (sección II.A de la documentación).
Ningún código especial se interpreta como cantidad clínica: se convierte en
faltante y el registro se excluye únicamente de las estimaciones que requieren
esa variable. Un valor negativo no documentado detiene el proceso.

| Variable | Código | Significado | Registros |
|---|---:|---|---:|
| `ARRTIME` | -9 | En blanco | 243 |
| `WAITTIME` | -9 | En blanco | 2,173 |
| `WAITTIME` | -7 | No aplica: no fue visto por médico/APRN/PA | 580 |
| `LOV` | -9 | En blanco | 697 |
| `IMMEDR` | -9 | En blanco | 364 |
| `IMMEDR` | -8 | Desconocido | 3,788 |
| `IMMEDR` | 0 | Sin triaje en un área que sí realiza triaje | 587 |
| `IMMEDR` | 7 | Área que no realiza triaje de enfermería | 1,079 |
| `BOARDED` | -9 | Faltante | 443 |
| `BOARDED` | -7 | No aplica (no ingresado) | 13,909 |

Registros utilizables: 15,782 con hora de llegada válida, 10,207 con triaje 1–5,
13,272 con `WAITTIME` válido y 12,754 con el proxy de servicio de la sección 8.4.

**Supuesto de faltantes.** Se analiza el caso completo por variable, suponiendo
que, después de ponderar, los registros excluidos se parecen a los incluidos. La
documentación informa una no respuesta de 27.8 % para `IMMEDR` y de 14.1 % para
`WAITTIME`, por lo que este supuesto es una limitación relevante (sección 10).

## 6. Ponderación, incertidumbre y fiabilidad

- **Ponderación.** Proporciones, medias y cuantiles usan `PATWT`. El volumen por
  departamento usa `EDWT`. Las tablas reportan también el tamaño de muestra sin
  ponderar (`n_unweighted`).
- **Cuantiles ponderados.** Se usa la inversa de la función de distribución
  ponderada: el menor valor cuya proporción acumulada de peso es al menos `q`.
- **Errores estándar.** Se calculan por linealización de Taylor con las
  variables de diseño enmascaradas `CSTRATM` (estrato) y `CPSUM` (conglomerado),
  bajo muestreo con reemplazo de conglomerados últimos. Las estimaciones por
  subgrupo conservan todos los conglomerados (estimación por dominio). Los
  intervalos de 95 % usan aproximación normal (`±1.96 SE`). Los cuantiles se
  reportan sin error estándar.
- **Fiabilidad.** La columna `reliable` aplica un criterio simplificado: al
  menos 30 registros y error estándar relativo de 30 % o menos. No reproduce los
  criterios completos de NCHS para proporciones [@parker2017standards]; solo
  sirve como alerta. El único valor marcado como no fiable es la proporción de
  esperas mayores de 60 minutos en el triaje 1.

## 7. Archivos procesados

Todos están en `data/processed/`, usan UTF-8 y tienen columnas `unit` y
`source_category`.

### 7.1 `nhamcs_2022_hourly_profile.csv`

Proporción de visitas del día que llegan en cada hora (`ARRTIME`). Suma 1.

| Columna | Unidad | Descripción |
|---|---|---|
| `hour` | hora 0–23 | Hora de llegada |
| `n_unweighted` | registros | Visitas de la muestra en esa hora |
| `weighted_visits` | visitas/año | Suma de `PATWT` |
| `share`, `share_se`, `share_ci95_low`, `share_ci95_high` | proporción | Estimación, error estándar e intervalo de 95 % |
| `reliable` | booleano | Criterio de la sección 6 |

### 7.2 `nhamcs_2022_triage_profile.csv`

Distribución de `IMMEDR` 1–5 entre visitas con triaje. Columnas análogas, más
`triage_level` y `label` (Immediate, Emergent, Urgent, Semi-urgent, Nonurgent).

### 7.3 `nhamcs_2022_reference_volume.csv`

Visitas anuales y diarias por departamento: la media nacional
(`sum(PATWT)/sum(EDWT)`) y los cuantiles 25, 50 y 75 ponderados por `EDWT` del
volumen de cada departamento (`sum(PATWT del departamento)/EDWT`).

### 7.4 `nhamcs_2022_reference_metrics.csv`

Distribución observada de `WAITTIME` en formato largo (`group_type`, `group`,
`metric`, `unit`, `value`, `se`, `ci95_low`, `ci95_high`, `n_unweighted`,
`reliable`). Incluye la media, la mediana, el percentil 90 y la proporción de
esperas mayores de 60 minutos, para el total, para cada nivel de triaje y para
cada bloque de llegada de 4 horas, que son los mismos bloques del horario del
modelo. **Uso exclusivo: validación.**

### 7.5 `nhamcs_2022_service_proxy.csv`

Tiempo posterior al primer contacto, `LOV − WAITTIME − BOARDED`, por triaje:
percentiles 25, 50, 75 y 90 y una `sigma` lognormal ajustada con el rango
intercuartílico de los logaritmos (`(ln q75 − ln q25)/1.349`). Se interpreta
como **cota superior** de la ocupación de un equipo (sección 8.4).

### 7.6 `calibration_metadata.json`

Archivos fuente con checksums, comprobaciones de validación, tamaños de muestra,
conteo de códigos especiales, supuestos, método de varianza, regla de fiabilidad,
descripción de cada salida y clasificación de cada entrada del modelo.

`default_hourly_profile.csv` se conserva sin cambios como perfil
`estimated_assumption` de las Partes 3 y 4.

## 8. Decisiones de modelación

### 8.1 Perfil horario de llegadas

La tasa de la hora `h` se define como:

$$
\lambda_h = V \cdot p_h,
$$

donde `p_h` es la proporción ponderada de llegadas en la hora `h` (derivada de
NHAMCS) y `V` es el volumen diario del departamento de referencia (sección 8.3).
El perfil nacional describe **cuándo** llegan los pacientes, pero no **cuántos**
llegan a un hospital concreto. Por eso `V` es una decisión separada.

### 8.2 Probabilidades de triaje

Se toman como la distribución ponderada de `IMMEDR` 1–5 entre las visitas con
triaje. Se excluyen las visitas sin triaje (códigos 0 y 7) y las que tienen
triaje desconocido o en blanco (−8 y −9). El modelo supone que todo paciente
recibe un nivel de triaje.

### 8.3 Escala del departamento de referencia

| Estadístico | Visitas/día |
|---|---:|
| Media nacional por departamento | 90.8 |
| Percentil 25 por departamento | 27.7 |
| **Mediana por departamento (elegida)** | **64.0** |
| Percentil 75 por departamento | 126.1 |

Valores exactos en `nhamcs_2022_reference_volume.csv`.

Se elige la **mediana ponderada por `EDWT`** como departamento de referencia
(`DEFAULT_REFERENCE_VOLUME = "median_ed"`). La media está dominada por
departamentos muy grandes y no describe a un departamento típico. La elección es
un supuesto del equipo (`estimated_assumption`) aplicado a un valor derivado.

El volumen por departamento `sum(PATWT)/EDWT` es una aproximación: supone que
`PATWT` y `EDWT` comparten las etapas de selección de unidad primaria y hospital,
de modo que el cociente estima las visitas anuales del departamento. Se basa en
188 departamentos.

Con el horario base (23 unidades, 92 horas-equipo) y las medianas de servicio
supuestas, la media nacional satura el sistema en una exploración preliminar. El
escenario de la mediana, en cambio, permanece estable. Esa exploración es
sintética, no constituye evidencia final y puede repetirse así:

```python
from ed_simulation.calibration import load_calibrated_config
from ed_simulation.simulation import simulate
simulate(load_calibrated_config("data/processed", "mean_per_ed", seed=1)).metrics
```

Los multiplicadores de demanda del diseño experimental (0.80, 1.00 y 1.20) se
aplican sobre `V` mediante `demand_multiplier`.

### 8.4 `WAITTIME` y `LOV`

- `WAITTIME` mide los minutos desde la llegada hasta el primer contacto con un
  médico, APRN o PA. Es la magnitud más cercana a la métrica del modelo (espera
  hasta el inicio de atención de un equipo). Los valores 0 son válidos y se
  conservan; los extremos (hasta 1,280 min) también, porque están dentro del
  rango documentado. Los cuantiles y la mediana no se ven afectados por ellos.
- `LOV` mide la duración total de la visita, desde la llegada hasta el egreso del
  departamento. Incluye la espera, la atención, pruebas, espera de resultados,
  esperas internas y, en pacientes ingresados, el tiempo de *boarding*.

El proxy `LOV − WAITTIME − BOARDED` elimina la espera inicial y el *boarding*
documentado. Además excluye a quienes se fueron sin ser vistos, antes de
completar la atención o contra consejo médico (`LWBS`, `LBTC`, `LEFTAMA`) y los
valores no positivos. Aun así, contiene tiempo en el que el equipo no está
ocupado con ese paciente. Sus medianas, entre 69 y 232 minutos según el triaje,
son de 1.8 a 2.5 veces las medianas supuestas del modelo (de 35 a 120 minutos).
Usarlo como tiempo de servicio sobredimensionaría la ocupación.

**Decisión.** `service_medians_minutes` y `service_sigma` se mantienen como
`estimated_assumption`. El proxy se publica como cota superior para la discusión
y el análisis de sensibilidad. Cualquier valor de servicio que se adopte debe
justificarse con una fuente identificable y registrarse en
`report/references.bib`.

### 8.5 Separación entre calibración y validación

| Uso | Variables de NHAMCS |
|---|---|
| Calibración | `ARRTIME` (perfil), `IMMEDR` (triaje), `PATWT`/`EDWT` (volumen) |
| Validación | `WAITTIME` (media, mediana, p90, proporción > 60 min) |
| Solo referencia | `LOV`, `BOARDED` (proxy de servicio) |

`WAITTIME` no se usa para elegir ningún parámetro. Si el equipo decidiera
ajustar algún parámetro para reproducir `WAITTIME`, la validación dejaría de ser
independiente y debería declararse como calibración.

## 9. Clasificación de las entradas del modelo calibrado

| Entrada | Valor | Categoría |
|---|---|---|
| Forma del perfil horario `p_h` | `nhamcs_2022_hourly_profile.csv` | `derived_from_public` |
| Volumen diario `V` | Mediana por departamento | `derived_from_public` (valor) y `estimated_assumption` (elección) |
| Probabilidades de triaje | `nhamcs_2022_triage_profile.csv` | `derived_from_public` |
| Medianas y sigma de servicio | `config.py` | `estimated_assumption` |
| Horario de capacidad y presupuesto | `config.py` | `estimated_assumption` |
| Esperas de referencia | `nhamcs_2022_reference_metrics.csv` | `derived_from_public` |
| Llegadas, esperas y colas simuladas | Salida de `simulate` | `synthetic_simulation` |

Los registros individuales del archivo son `observed_public`. Ninguna tabla
procesada los publica sin agregar.

## 10. Limitaciones

- **No representa a Guatemala.** NHAMCS es una referencia nacional de Estados
  Unidos. No describe un hospital guatemalteco específico, no permite afirmar que
  una intervención se aplicó y no demuestra mejoras reales. Trasladar el modelo a
  un hospital concreto requiere sus propios datos de llegadas, triaje, servicio y
  personal.
- **Perfil nacional agregado.** El perfil horario mezcla departamentos de
  distintos tamaños. El de un departamento individual puede diferir.
- **No respuesta.** La no respuesta de `IMMEDR` (27.8 %) y de `WAITTIME` (14.1 %)
  podría sesgar el triaje y la referencia de espera si los faltantes no son
  aleatorios.
- **Control de divulgación.** NCHS enmascara o top-codifica algunas variables.
  Las estimaciones por subgrupo pueden diferir ligeramente de las tablas
  oficiales.
- **Incertidumbre parcial.** Los cuantiles no tienen error estándar y la regla
  de fiabilidad es simplificada.
- **Volumen aproximado.** El volumen por departamento depende de la aproximación
  `sum(PATWT)/EDWT` y de 188 departamentos.
- **Métrica no idéntica.** El modelo mide la espera hasta que un equipo inicia la
  atención; `WAITTIME` mide la espera hasta el primer contacto con un proveedor.
  La comparación es razonable, pero no exacta.

## 11. Uso desde el código

```python
from ed_simulation.calibration import load_calibrated_config
from ed_simulation.simulation import simulate

config = load_calibrated_config(
    "data/processed",
    reference_volume="median_ed",   # o "mean_per_ed", "p25_ed", "p75_ed"
    demand_multiplier=1.0,
    seed=2026,
)
result = simulate(config)
```

`load_calibrated_config` no modifica los valores por defecto de `config.py`, de
modo que la CLI y Streamlit siguen funcionando con el perfil estimado hasta que
el equipo integre el calibrado de forma coordinada.

## 12. Entregas para las siguientes líneas de trabajo

- **Experimentos y validación (Adrián).** Usar `load_calibrated_config` y
  comparar las mismas métricas y unidades de `nhamcs_2022_reference_metrics.csv`
  (total, triaje y bloque). Con la media nacional, la utilización observada
  supera 1, lo que confirma el riesgo D del handoff.
- **Interfaz (Andrés).** Leer `source_category` y `unit` de los CSV para mostrar
  etiquetas de procedencia sin duplicar lógica.
- **Informe (Javier).** Citar las fuentes `nhamcs2022doc`, `nhamcs2022data` y
  `nhamcs2022dictionary` de `report/references.bib`, e importar las tablas desde
  `data/processed/`.

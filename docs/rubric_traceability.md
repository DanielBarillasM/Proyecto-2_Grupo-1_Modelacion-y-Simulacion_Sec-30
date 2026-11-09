# Trazabilidad con la rúbrica

Este documento relaciona cada requisito del Proyecto 2 con evidencia concreta del
repositorio. Se actualizará en cada parte y antes de la entrega.

| Parte | Requisito | Evidencia | Estado |
|---|---|---|---|
| 1 | Contexto y actores | `docs/01_problem_definition.md`, secciones 1 y 2 | Completo |
| 1 | Entradas y salidas | `docs/01_problem_definition.md`, sección 3 | Completo |
| 1 | Pregunta concreta | README y sección 4 | Completo |
| 1 | Métrica principal con unidades y sentido | Sección 6 | Completo |
| 1 | Alcance, restricciones y supuestos | Secciones 7 a 10 | Completo |
| 1 | Fuente verificable | Sección 11 | Completo |
| 2 | Objetivo, representación y procedimiento | `docs/02_technical_research.md`, secciones 4.1 a 4.9 | Completo |
| 2 | Tres o más fuentes técnicas | Sección 9 y `report/references.bib` | Completo |
| 2 | Justificación frente a alternativas | Sección 5 | Completo |
| 2 | Limitaciones y condiciones de fallo | Sección 8 | Completo |
| 2 | División biblioteca/equipo | Sección 7 | Completo |
| 3 | Diagrama y relación de componentes | `docs/03_model_and_simulation.md`, sección 1 | Completo |
| 3 | Variables, parámetros, unidades y fuentes | Secciones 2 a 5 y `config.py` | Completo |
| 3 | Reglas, fórmulas y pseudocódigo | Secciones 3 a 8 | Completo |
| 3 | Simulación funcional y parametrizable | `src/ed_simulation/` y `app.py` | Completo |
| 3 | Separación de responsabilidades | Sección 9 y estructura de paquetes | Completo |
| 3 | Reproducción desde entorno limpio | README y sección 10 | Completo |
| 4 | Función objetivo y restricciones | `docs/04_improvement_implementation.md`, secciones 2 y 3 | Completo |
| 4 | Integración con la simulación | Sección 1 y `optimization/genetic_algorithm.py` | Completo |
| 4 | Parámetros y justificación | Sección 5 y `GAConfig` | Completo |
| 4 | Candidato y factibilidad por código | Secciones 7 y 8, pruebas y `evidence/part4_candidate.json` | Completo |
| 4 | Alternativa base conservada | `OptimizationResult.baseline` y elitismo | Completo |
| 3 | Procedencia y unidades de parámetros calibrados | `docs/05_data_calibration.md`, secciones 7 a 9; columnas `unit` y `source_category` | Completo |
| 5 | Fuente real verificable: fecha, periodo, muestra y condiciones | `docs/05_data_calibration.md`, sección 2; `data/processed/calibration_metadata.json` | Completo |
| 5 | Obtención y transformación reproducibles | `scripts/download_nhamcs.py`, `scripts/prepare_nhamcs.py`, `tests/test_calibration.py` | Completo |
| 5 | Parámetros calibrados con datos públicos | `src/ed_simulation/calibration.py` (`load_calibrated_config`), `data/processed/nhamcs_2022_*` | Completo para llegadas y triaje; servicio sigue como supuesto |
| 5 | Diseño experimental y validación | `docs/06_experimental_design.md`, `scripts/generate_evidence.py`, `evidence/final/` | Completo |
| 6 | Métrica real de referencia con incertidumbre | `data/processed/nhamcs_2022_reference_metrics.csv`, `evidence/final/validation_comparison.csv` | Completo |
| 6 | Comparación con escenario real | `docs/07_validation_results.md`, sección 5; figura de validación | Completo con alcance explícito |
| 7 | Resultados y conclusiones | `docs/07_validation_results.md`, `evidence/final/summary.csv`, `evidence/final/figures/` | Evidencia técnica completa; informe/presentación final pendientes |

## Criterios de aceptación de la Parte 1

- [x] El problema corresponde a un sistema real documentado.
- [x] La pregunta de investigación es cuantificable.
- [x] La métrica principal tiene unidades y sentido de mejora.
- [x] Se diferencian alcance y exclusiones.
- [x] Los supuestos y restricciones están declarados.
- [x] Existe una fuente pública identificable.

## Criterios de aceptación de la Parte 2

- [x] La técnica adicional tiene objetivo y representación definidos.
- [x] Se describen selección, cruce, mutación, reemplazo y terminación.
- [x] Se justifican las restricciones y el control de ruido.
- [x] La elección se compara con alternativas razonables.
- [x] Se documentan al menos dos limitaciones.
- [x] Existen tres o más fuentes técnicas identificables.
- [x] Se diferencia el trabajo de las bibliotecas y el trabajo del equipo.

## Criterios de aceptación de la Parte 3

- [x] El sistema tiene diagrama y flujo documentado.
- [x] Variables importantes incluyen unidad y procedencia.
- [x] Las distribuciones y reglas tienen ecuaciones o pseudocódigo.
- [x] La simulación acepta parámetros y una semilla explícita.
- [x] Modelo, interfaz y CLI están separados.
- [x] La ejecución registra el corte y drena la cohorte para completar esperas
  sin mezclar el drenaje con utilización o cola de la ventana.
- [x] Existen pruebas de consistencia y reproducibilidad.
- [x] El README permite reproducir la instalación y ejecución.

## Criterios de aceptación de la Parte 4

- [x] La función objetivo está expresada formalmente.
- [x] Presupuesto, límites, integralidad y transiciones se validan por código.
- [x] La técnica adicional utiliza el simulador como función de evaluación.
- [x] Los parámetros del método son visibles y configurables.
- [x] La asignación base siempre forma parte de la población.
- [x] La solución final se rechaza si no es factible.
- [x] Se guardan historial, semillas, restricciones y métricas.
- [x] Streamlit y CLI ejecutan la optimización.

## Criterios de aceptación de datos y calibración (NHAMCS 2022)

- [x] El proceso parte de los archivos oficiales y detecta archivos erróneos
  (SHA-256, longitud de registro, número de registros, año y total de `PATWT`).
- [x] Los códigos especiales y faltantes se tratan según el libro de códigos
  oficial; un negativo no documentado detiene el proceso.
- [x] Las proporciones, medias y cuantiles usan `PATWT`; el volumen por
  departamento usa `EDWT`; los errores estándar usan `CSTRATM` y `CPSUM`.
- [x] Cada salida identifica su unidad y su clasificación de procedencia.
- [x] Las probabilidades horarias y de triaje suman 1 con una tolerancia de
  `1e-4` en los CSV y de forma exacta tras normalizar en `calibrated_inputs`.
- [x] La transformación es determinista y está probada (`tests/test_calibration.py`).
- [x] No se versionan datos crudos, credenciales ni binarios (`data/raw/` ignorado).
- [x] Se explica por qué la referencia no equivale a un hospital guatemalteco
  (`docs/05_data_calibration.md`, sección 10).
- [x] `WAITTIME` queda reservado para validación y no se usa para ajustar.
- [ ] Tiempo de servicio calibrado con una fuente identificable: sigue como
  `estimated_assumption` (sección 8.4).

## Criterios de aceptación de experimentación y validación

- [x] La candidata se selecciona con semillas 10000–10009 y se congela antes de
  las semillas finales 30000–30029.
- [x] Existen seis condiciones: dos horarios por tres niveles de demanda.
- [x] Cada condición tiene 30 réplicas; base y candidata comparten semilla en
  cada pareja.
- [x] `runs.csv` registra entradas, semillas, métricas, drenaje y runtime.
- [x] `summary.csv` reporta media, desviación, intervalo del 95 % y cuantiles.
- [x] `paired_differences.csv` y `paired_summary.csv` cuantifican cambios
  absolutos, porcentuales y su incertidumbre.
- [x] La cola física conserva el arrastre del calentamiento y la utilización usa
  exposición efectiva de capacidad.
- [x] La referencia, base y candidata usan las mismas cuatro métricas y unidades.
- [x] Existen sensibilidad, limitaciones y riesgo de extrapolación documentados.
- [x] Las tres figuras y todas las tablas se regeneran por comando.
- [x] La mejora se describe como simulada, no observada en un hospital real.

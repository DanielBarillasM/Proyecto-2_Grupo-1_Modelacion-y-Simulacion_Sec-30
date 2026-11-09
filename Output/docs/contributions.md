# Registro de contribuciones

El registro se actualizará con evidencia verificable a medida que avance el
proyecto. Una responsabilidad planificada no se considerará automáticamente una
contribución completada.

| Integrante | Responsabilidades planificadas | Evidencia completada |
|---|---|---|
| Pablo Daniel Barillas Moreno | Coordinación, integración y reproducibilidad | Por registrar |
| Jorge Palacios | Investigación técnica y formulación matemática; datos y calibración NHAMCS | Pipeline reproducible de NHAMCS 2022: `scripts/download_nhamcs.py`, `scripts/prepare_nhamcs.py`, `src/ed_simulation/calibration.py`, `tests/test_calibration.py`, `data/processed/nhamcs_2022_*`, `data/processed/calibration_metadata.json`, `docs/05_data_calibration.md`, `data/README.md` y entradas NHAMCS de `report/references.bib` |
| Adrián Ricardo González Muralles | Correcciones del simulador, experimentación y validación | Cola física tras calentamiento, drenaje terminal, capacidad efectiva, diseño factorial, candidata congelada, 180 ejecuciones, validación NHAMCS, figuras y pruebas en `simulation.py`, `experiments.py`, `validation.py`, `evidence.py`, `scripts/generate_evidence.py`, `scripts/run_experiments.py`, `tests/test_simulation.py`, `tests/test_experiments.py`, `tests/test_validation.py`, `evidence/final/`, `docs/06_experimental_design.md` y `docs/07_validation_results.md` |
| Andrés Rafael Chivalán | Interfaz, visualización y demostración | Por registrar |
| Javier Andrés Chen | Informe, presentación, guion y auditoría final | Informe técnico en LaTeX (`report/main.tex`, `report/sections/`, `report/main.pdf`) y generador de tablas, macros y figuras desde la evidencia (`scripts/build_report_assets.py`, `report/generated/`, `report/figures/`). Presentación, guion y auditoría final: pendientes |

## Convención de registro

Cada aporte deberá indicar archivo, actividad, revisión o experimento. El historial
de Git complementa, pero no reemplaza, esta explicación.

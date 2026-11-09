# Registro final de contribuciones

Este registro vincula cada aporte con evidencia verificable del repositorio. El historial de Git complementa esta descripción.

| Integrante | Responsabilidades y aportes completados | Evidencia principal |
|---|---|---|
| Pablo Daniel Barillas Moreno | Coordinación e integración del proyecto; definición del problema; investigación del algoritmo genético; implementación inicial del simulador configurable, la CLI y la optimización restringida; revisión de reproducibilidad y cierre de la entrega. | `docs/01_problem_definition.md`, `docs/02_technical_research.md`, `docs/03_model_and_simulation.md`, `docs/04_improvement_implementation.md`, `src/ed_simulation/config.py`, `src/ed_simulation/simulation.py`, `src/ed_simulation/cli.py`, `src/ed_simulation/optimization/`, `tests/test_config.py`, `tests/test_optimization.py` |
| Jorge Palacios | Pipeline reproducible de NHAMCS 2022: descarga, verificación, preparación, calibración, agregados públicos, documentación de procedencia y pruebas de datos. | `scripts/download_nhamcs.py`, `scripts/prepare_nhamcs.py`, `src/ed_simulation/calibration.py`, `tests/test_calibration.py`, `data/processed/`, `data/README.md`, `docs/05_data_calibration.md` |
| Adrián Ricardo González Muralles | Correcciones del simulador para calentamiento, drenaje terminal y capacidad efectiva; diseño factorial; candidata congelada; 180 ejecuciones; sensibilidad; validación contra NHAMCS; figuras y pruebas. | `src/ed_simulation/simulation.py`, `src/ed_simulation/experiments.py`, `src/ed_simulation/validation.py`, `src/ed_simulation/evidence.py`, `scripts/generate_evidence.py`, `scripts/run_experiments.py`, `tests/test_simulation.py`, `tests/test_experiments.py`, `tests/test_validation.py`, `evidence/final/`, `docs/06_experimental_design.md`, `docs/07_validation_results.md` |
| Andrés Rafael Chivalán | Refactor de la interfaz Streamlit en cinco páginas; formularios de ejecución controlada; visualizaciones; carga de evidencia precomputada; descargas; etiquetas de procedencia; manejo de estado y pruebas de interfaz. | `app.py`, `.streamlit/config.toml`, `app_pages/`, `src/ed_simulation/ui/`, `tests/test_app.py` |
| Javier Andrés Chen | Informe técnico en LaTeX; generación reproducible de tablas, macros y figuras; presentación; guion cronometrado de 15 minutos y materiales de respaldo. | `Output/report/`, `Output/scripts/build_report_assets.py`, `presentation/index.html`, `presentation/styles.css`, `presentation/script/` |

## Verificación común

Todo el equipo debe poder explicar el modelo, ejecutar la demostración y defender las limitaciones. La entrega final se verificó con 64 pruebas aprobadas y una prueba omitida porque requiere descargar el archivo crudo oficial de NHAMCS.

# Declaración de uso de inteligencia artificial

## Herramienta

Se utilizó OpenAI Codex como apoyo durante la planificación, estructuración del
repositorio, revisión de código y redacción inicial de documentación.

Se utilizó Claude Code como apoyo para documentar el
pipeline de datos y calibración NHAMCS 2022 (`calibration.py`, scripts de
descarga y preparación, pruebas y `docs/05_data_calibration.md`). Los códigos
especiales, posiciones de columnas y totales de control se tomaron de la
documentación oficial de NCHS, no de la herramienta.

Se utilizó OpenAI Codex para revisar la rúbrica y el handoff, corregir el
seguimiento de cola, drenaje y utilización, y apoyar la implementación del
pipeline experimental, sus pruebas y la documentación de reproducibilidad. Las
cifras publicadas proceden exclusivamente de los scripts versionados y de los
datos procesados de NHAMCS; no fueron generadas ni editadas manualmente por la
herramienta.

## Alcance

La herramienta se usa para:

- proponer estructura modular y casos de prueba;
- detectar inconsistencias entre código, documentación y rúbrica;
- producir borradores que luego son revisados por el equipo;
- apoyar la documentación técnica y los comentarios del código.

No se utiliza como fuente de datos, evidencia experimental ni autoridad
bibliográfica. Las afirmaciones técnicas deben quedar respaldadas por las fuentes
identificables de `report/references.bib`.

## Responsabilidad del equipo

Los integrantes son responsables de ejecutar el código, revisar ecuaciones,
verificar resultados, confirmar fuentes y poder explicar cada decisión durante la
defensa. Las salidas generadas por IA no se consideran evidencia si no pueden
reproducirse desde el repositorio.

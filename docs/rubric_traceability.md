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
| 5 | Diseño experimental y validación | Etapa posterior | Pendiente |
| 6 | Comparación con escenario real | Etapa posterior | Pendiente |
| 7 | Resultados y conclusiones | Etapa posterior | Pendiente |

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
- [x] La ejecución reporta pacientes censurados en lugar de ocultarlos.
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

# Proyecto 2 - Optimización de recursos en un departamento de emergencias

Proyecto del curso **CC3074 - Modelización y Simulación**, sección 30, de la
Universidad del Valle de Guatemala.

El proyecto estudia un departamento de emergencias de referencia mediante
simulación de eventos discretos. El objetivo es determinar si una redistribución
horaria de la misma cantidad total de recursos puede reducir el tiempo de espera
de los pacientes. La propuesta integra un proceso de llegadas dependiente de la
hora, una cola con prioridad clínica y un algoritmo genético con restricciones.

> Estado actual: implementación de las Partes 1 a 4 de la guía del Proyecto 2.

## Pregunta de investigación

¿Cuánto puede reducirse el tiempo de espera de los pacientes al redistribuir una
cantidad fija de equipos de atención entre seis bloques de cuatro horas, sin
aumentar las horas-recurso totales?

## Objetivo principal

Minimizar el tiempo medio de espera hasta el inicio de la atención. Como métricas
secundarias se emplean la mediana, el percentil 90, la proporción de pacientes con
espera superior a 60 minutos, la longitud máxima de la cola y la utilización de
los recursos.

## Escenario real de referencia

La calibración y la validación utilizarán el archivo público de visitas a
departamentos de emergencias **NHAMCS 2022**, publicado por el National Center for
Health Statistics de los CDC. El conjunto contiene 16,025 registros y variables
como hora de llegada (`ARRTIME`), espera hasta el primer proveedor (`WAITTIME`),
duración de la visita (`LOV`) y nivel de triaje (`IMMEDR`).

El modelo representa un departamento de emergencias estadounidense de referencia;
no representa ni pretende predecir el desempeño de un hospital guatemalteco
específico.

## Componentes técnicos

- Simulación de eventos discretos con Python y SimPy.
- Llegadas mediante un proceso de Poisson no homogéneo por hora.
- Cola prioritaria según nivel de triaje.
- Duraciones de atención empíricas o ajustadas a partir de NHAMCS.
- Algoritmo genético restringido para distribuir recursos por bloque horario.
- Aplicación interactiva en Streamlit y comandos reproducibles por consola.
- Pruebas automatizadas, registro de semillas y resultados tabulados.

## Estructura prevista

```text
.
|-- app.py                         # Aplicación Streamlit
|-- src/ed_simulation/             # Modelo, simulación y optimización
|-- data/                          # Datos, metadatos y procedimiento de obtención
|-- scripts/                       # Preparación y ejecución reproducible
|-- tests/                         # Pruebas unitarias y de integración
|-- evidence/                      # Semillas, configuraciones y resultados
|-- docs/                          # Problema, técnica, trazabilidad y contribuciones
|-- report/                        # Informe LaTeX y PDF
`-- presentation/                  # Presentación HTML y guion
```

## Partes del proyecto

1. **Selección y delimitación:** problema, actores, entradas, salidas, métricas,
   alcance y restricciones.
2. **Investigación técnica:** fundamentos y justificación de la simulación y del
   algoritmo genético restringido.
3. **Formulación y simulación:** modelo parametrizable, ecuaciones, diagrama,
   implementación base y reproducción desde un entorno limpio.
4. **Implementación de la mejora:** función objetivo, restricciones, integración
   del algoritmo genético y comprobación automática de factibilidad.
5. **Experimentación y validación:** se implementará en la siguiente etapa.
6. **Comparación con la vida real:** se completará con los experimentos finales.
7. **Resultados y conclusiones:** se completará después de ejecutar la batería
   experimental.

## Documentación disponible

- [Definición del problema](docs/01_problem_definition.md)
- [Investigación técnica](docs/02_technical_research.md)
- [Modelo y simulación](docs/03_model_and_simulation.md)
- [Trazabilidad de la rúbrica](docs/rubric_traceability.md)
- [Registro de contribuciones](docs/contributions.md)
- [Uso de inteligencia artificial](docs/ai_usage.md)

## Instalación

Desde PowerShell, en la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

La instalación editable incluye las dependencias declaradas en `pyproject.toml`.
También se mantiene `requirements.txt` para herramientas que esperan ese formato:

```powershell
python -m pip install -r requirements.txt
```

## Ejecución

Aplicación interactiva:

```powershell
streamlit run app.py
```

Simulación reproducible por consola:

```powershell
python -m ed_simulation.cli --seed 2026 --summary-only
```

Guardar una ejecución completa:

```powershell
python -m ed_simulation.cli --seed 2026 --output evidence/results/base_seed_2026.json
```

## Pruebas

```powershell
pytest
```

Las pruebas verifican configuración, reproducibilidad, conservación de pacientes,
ausencia de esperas negativas y el caso sin llegadas.

## Integrantes

- Pablo Daniel Barillas Moreno
- Jorge Palacios
- Adrián Ricardo González Muralles
- Andrés Rafael Chivalán
- Javier Andrés Chen

## Fuentes iniciales

- National Center for Health Statistics. *NHAMCS 2022 Emergency Department
  Public Use Data File Documentation*.
- National Center for Health Statistics. *NHAMCS 2022 Emergency Department
  Summary Tables*.

La bibliografía técnica completa se encuentra en
[`report/references.bib`](report/references.bib).

## Licencia

Consulte [LICENSE](LICENSE).

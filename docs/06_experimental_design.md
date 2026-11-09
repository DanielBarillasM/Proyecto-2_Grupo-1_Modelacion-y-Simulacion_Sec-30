# Parte 5. Diseño experimental, verificación y reproducibilidad

## 1. Pregunta experimental

El experimento estima si redistribuir las mismas 23 unidades de capacidad entre
seis bloques de cuatro horas reduce la espera hasta el inicio de atención, sin
aumentar las 92 horas-equipo diarias. El resultado describe una mejora simulada,
no una intervención observada en un hospital.

## 2. Entradas y procedencia

- Perfil horario, probabilidades de triaje y volumen del departamento de
  referencia: derivados de NHAMCS 2022 mediante `load_calibrated_config`.
- Volumen nominal: mediana ponderada por `EDWT`, 63.9814 visitas diarias.
- Duración de servicio, capacidad y forma de la distribución: supuestos
  estimados documentados en `docs/05_data_calibration.md`.
- Esperas NHAMCS (`WAITTIME`): reservadas para validación; no seleccionan la
  candidata ni ajustan parámetros.

Las cuatro categorías de procedencia son `observed_public`,
`derived_from_public`, `estimated_assumption` y `synthetic_simulation`.

## 3. Correcciones previas a la evaluación

La medición usa la cola física completa. Los pacientes que llegaron durante el
calentamiento y siguen esperando al iniciar la ventana contribuyen al nivel,
máximo y área de cola desde ese instante. Solo se reinician los acumuladores
estadísticos.

Al final de la ventana se detienen nuevas llegadas y se drena la cohorte medida
hasta que todos comienzan servicio. Por tanto, las métricas de espera no excluyen
los casos más largos. El drenaje queda registrado, pero no se mezcla con cola,
capacidad ni utilización dentro de la ventana.

La utilización se define como:

$$
U=\frac{\text{minutos-equipo ocupados en la ventana}}
        {\text{minutos-equipo efectivos disponibles en la ventana}}.
$$

La capacidad efectiva considera que, ante un descenso de horario, una atención
en curso termina antes de bloquear el espacio. También se publica la utilización
contra capacidad nominal para auditar esa transición.

## 4. Selección y congelamiento de la candidata

La candidata se obtiene con el algoritmo genético restringido y demanda nominal.
El conjunto de optimización comienza en la semilla 10000 y usa diez réplicas por
candidata. La semilla del algoritmo es 9101. La candidata debe cumplir:

- seis bloques enteros;
- suma diaria igual a 23 unidades;
- entre 1 y 8 equipos por bloque;
- cambio máximo de 3 entre bloques consecutivos, incluida la transición del
  último al primero.

`evidence/final/frozen_candidate.json` se escribe antes de evaluar las semillas
finales. Las semillas de evaluación comienzan en 30000 y no se usan para buscar,
seleccionar ni modificar la candidata.

## 5. Diseño factorial

Se cruzan dos horarios con tres niveles de demanda:

| Factor | Niveles |
|---|---|
| Horario | base, candidata congelada |
| Demanda | 0.80, 1.00, 1.20 veces el volumen de referencia |

El diseño contiene seis condiciones. Cada una usa 30 réplicas independientes,
para 180 ejecuciones finales. Dentro de cada nivel de demanda, la réplica de base
y la de candidata comparten semilla; esto implementa números aleatorios comunes
y permite analizar diferencias pareadas. Réplicas distintas usan semillas
distintas.

La demanda de 0.80 y 1.20 funciona además como prueba de sensibilidad alrededor
de la condición nominal.

## 6. Métricas y estadísticos

Cada fila de `runs.csv` conserva condición, horario, multiplicador, réplica,
semilla, llegadas, estados de servicio, esperas, colas, utilización, drenaje y
tiempo de ejecución. `summary.csv` calcula por condición y métrica:

- número de réplicas, media y desviación estándar muestral;
- intervalo normal del 95 % para la media;
- mediana, percentiles 10 y 90, mínimo y máximo.

`paired_differences.csv` usa la convención `base - candidata`: un valor positivo
indica reducción bajo la candidata. Reporta cambio absoluto y porcentual por
semilla. No se usa la palabra “significativo” sin una prueba inferencial; el
análisis es descriptivo y presenta magnitud e incertidumbre.

## 7. Validación con referencia pública

La condición nominal se compara con las cuatro métricas generales de NHAMCS:

- espera media, mediana y percentil 90, en minutos;
- proporción con espera superior a 60 minutos.

`validation_comparison.csv` presenta referencia, simulación base, candidata,
error absoluto y relativo de la base, y cambio simulado. El MAE en minutos se
calcula únicamente entre las tres métricas con unidad de tiempo; la proporción se
mantiene separada para no mezclar unidades.

NHAMCS mide espera hasta el primer contacto con médico/APRN/PA, mientras el modelo
mide espera hasta que un equipo inicia atención. La comparación es informativa,
pero no prueba correspondencia con un hospital guatemalteco ni mejora real.

## 8. Verificación automatizada

Las pruebas cubren:

- conservación de la cohorte y esperas/colas no negativas;
- reproducibilidad con la misma semilla e independencia con semillas distintas;
- cero demanda produce cero llegadas;
- la capacidad no cambia la secuencia exógena de llegadas con semilla común;
- arrastre de cola desde el calentamiento;
- drenaje sin esperas censuradas;
- utilización efectiva acotada durante descensos de capacidad;
- factibilidad de la candidata;
- emparejamiento de semillas y recomputación de resúmenes desde réplicas;
- compatibilidad de métricas y unidades frente a la referencia.

## 9. Reproducción

Comprobación rápida, sin tocar la evidencia final:

```powershell
python scripts/generate_evidence.py --smoke
```

Generación completa, incluida optimización y congelamiento:

```powershell
python scripts/generate_evidence.py
```

Repetición de la evaluación con una candidata ya congelada:

```powershell
python scripts/run_experiments.py `
  --candidate evidence/final/frozen_candidate.json
```

Las tablas, las tres figuras SVG y el manifiesto se regeneran por estos comandos;
no se editan manualmente.

## 10. Riesgo de extrapolación

Los resultados solo aplican a las distribuciones, volumen, capacidad y horizonte
probados. La sensibilidad 0.80–1.20 no cubre crisis, cambios clínicos, abandono,
preempción, múltiples etapas de atención ni un hospital particular. El tiempo de
servicio continúa siendo un supuesto y es la principal amenaza para la validez.

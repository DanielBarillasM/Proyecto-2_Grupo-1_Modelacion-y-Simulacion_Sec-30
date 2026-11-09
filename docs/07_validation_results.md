# Partes 5 y 6. Resultados de experimentación y validación

## 1. Alcance de la afirmación

Los resultados son **simulaciones sintéticas** de un departamento de referencia
con perfil de llegadas y triaje derivados de NHAMCS 2022. No se implementó la
redistribución en un hospital ni se observó una mejora clínica real. La candidata
solo estima qué podría ocurrir bajo los supuestos documentados.

La evidencia se generó con el commit registrado en
`evidence/final/manifest.json`. Cada una de las seis condiciones contiene 30
réplicas y base/candidata comparten semilla dentro de cada pareja.

## 2. Horarios comparados

| Bloque | 00–04 | 04–08 | 08–12 | 12–16 | 16–20 | 20–24 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| Base | 3 | 3 | 4 | 4 | 5 | 4 | 23 |
| Candidata congelada | 1 | 2 | 5 | 5 | 6 | 4 | 23 |

La candidata conserva 92 horas-equipo diarias y satisface límites, integralidad y
cambio máximo entre bloques. Fue seleccionada con las semillas 10000–10009 y
congelada antes de usar las semillas finales 30000–30029.

## 3. Métrica principal y sensibilidad

La tabla usa la diferencia pareada `base - candidata`; valores positivos indican
menor espera con la candidata. El intervalo es normal del 95 % para la media de
las 30 diferencias pareadas.

| Demanda | Base (min) | Candidata (min) | Reducción (min) | Reducción sobre media base | IC 95 % pareado (min) | Pares favorables |
|---:|---:|---:|---:|---:|---:|---:|
| 80 % | 22.87 | 21.05 | 1.81 | 7.9 % | [-6.96, 10.59] | 12/30 |
| 100 % | 74.52 | 53.60 | 20.92 | 28.1 % | [9.11, 32.73] | 21/30 |
| 120 % | 228.09 | 177.32 | 50.76 | 22.3 % | [37.02, 64.50] | 26/30 |

La redistribución tiene su mayor efecto absoluto cuando el sistema está más
exigido. Bajo demanda baja, el intervalo incluye cero y menos de la mitad de las
parejas favorece a la candidata; por tanto, no se afirma una mejora consistente
en esa condición. Bajo demanda nominal y alta, la reducción media pareada es
positiva, aunque la variabilidad entre días simulados sigue siendo amplia.

## 4. Otras métricas bajo demanda nominal

| Métrica | Base | Candidata | Cambio simulado |
|---|---:|---:|---:|
| Mediana de espera | 27.54 min | 15.90 min | -11.64 min (-42.3 %) |
| Percentil 90 de espera | 236.69 min | 158.84 min | -77.86 min (-32.9 %) |
| Proporción con espera > 60 min | 0.2715 | 0.2249 | -0.0466 (4.66 puntos porcentuales) |
| Cola media | 3.72 pacientes | 2.63 pacientes | -1.09 (-29.4 %) |
| Utilización efectiva | 0.8489 | 0.8343 | -0.0146 |

El resultado no se obtiene aumentando recursos: ambos horarios usan el mismo
presupuesto. La menor utilización efectiva de la candidata refleja una mejor
coincidencia temporal entre demanda y capacidad, no capacidad adicional.

## 5. Comparación con NHAMCS 2022

`WAITTIME` es una referencia independiente: no se usó para ajustar parámetros ni
seleccionar la candidata.

| Métrica | Referencia NHAMCS | Simulación base | Simulación candidata |
|---|---:|---:|---:|
| Espera media | 38.15 min | 74.52 min | 53.60 min |
| Mediana | 16.00 min | 27.54 min | 15.90 min |
| Percentil 90 | 98.00 min | 236.69 min | 158.84 min |
| Proporción > 60 min | 0.1770 | 0.2715 | 0.2249 |

El modelo base sobreestima las cuatro métricas. Su MAE entre media, mediana y p90
es 62.20 minutos; para la candidata es 25.46 minutos. La candidata queda más
cerca de la referencia, pero esto no convierte la intervención en validada: el
objetivo del algoritmo fue reducir esperas simuladas, no ajustar `WAITTIME`.

La similitud de la mediana candidata (15.90 min) con la referencia (16.00 min) no
compensa la discrepancia de la cola superior: el p90 candidato todavía es 60.84
minutos mayor que NHAMCS. La correspondencia del modelo es parcial.

## 6. Incertidumbre y congestión terminal

La desviación estándar de la espera media nominal es 60.59 min en base y 49.94
min en candidata. Sus intervalos marginales del 95 % son [52.84, 96.20] y
[35.73, 71.47] min, respectivamente. El análisis pareado es el adecuado para el
efecto porque elimina parte de la variación compartida entre escenarios.

El drenaje medio después del corte es 83.83 min en base y 89.80 min en candidata
bajo demanda nominal. Con demanda 120 % sube a 382.32 y 372.78 min. Las esperas
se reportan completas, pero esos drenajes prolongados muestran saturación y
limitan la extrapolación del escenario de alta demanda.

## 7. Conclusión técnica de esta fase

Bajo la demanda nominal calibrada, la redistribución estima una reducción media
de 20.92 minutos (28.1 %) sin aumentar el presupuesto; también reduce p90, cola
media y proporción sobre 60 minutos. El beneficio no es uniforme: es débil e
incierto con demanda al 80 % y mayor bajo demanda al 120 %.

La recomendación limitada es conservar la candidata como escenario de análisis
y demostración, no como política clínica lista para aplicar. Antes de trasladarla
a un hospital concreto se necesitan datos locales de llegada, capacidad y tiempo
de ocupación del equipo, una calibración del servicio y una validación externa.

## 8. Evidencia reproducible

- `evidence/final/runs.csv`: 180 ejecuciones y semillas.
- `evidence/final/summary.csv`: estadísticos por condición.
- `evidence/final/paired_differences.csv`: diferencias por pareja.
- `evidence/final/paired_summary.csv`: efectos, dispersión e intervalos pareados.
- `evidence/final/validation_comparison.csv`: referencia/base/candidata.
- `evidence/final/figures/`: condición, variabilidad pareada y validación.
- `evidence/final/manifest.json`: hashes, versiones, parámetros y comandos.

Todo el directorio se regenera con:

```powershell
python scripts/generate_evidence.py
```

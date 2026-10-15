# Datos y procedencia

## Clasificación de fuentes

| Recurso | Categoría | Uso actual |
|---|---|---|
| NHAMCS 2022 | Datos públicos reales | Fuente prevista para calibración y validación en las Partes 5 y 6 |
| `processed/default_hourly_profile.csv` | Perfil estimado | Demostración funcional de las Partes 3 y 4 |
| Llegadas generadas por la simulación | Datos sintéticos | Evaluación de escenarios bajo parámetros controlados |

El perfil estimado no constituye validación contra la realidad. Su finalidad es
permitir ejecutar, probar y explicar el modelo antes de incorporar el proceso
reproducible de preparación de NHAMCS.

## Archivo NHAMCS previsto

Fuente oficial:

https://www.cdc.gov/nchs/nhamcs/documentation/index.html

Variables previstas:

- `ARRTIME`: hora de llegada;
- `WAITTIME`: espera al primer proveedor, en minutos;
- `LOV`: duración de la visita, en minutos;
- `IMMEDR`: nivel de urgencia recomendado;
- `PATWT`: ponderación de la visita.

## Reglas

- `raw/` no se versiona y debe contener únicamente archivos obtenidos de la fuente.
- `processed/` contiene conjuntos pequeños y reproducibles utilizados por el
  programa.
- Cada archivo procesado debe indicar si sus valores son observados, derivados,
  estimados o sintéticos.
- No se almacenan credenciales ni información personal.

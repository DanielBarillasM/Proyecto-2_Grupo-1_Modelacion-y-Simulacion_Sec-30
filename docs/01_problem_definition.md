# Parte 1. Selección y delimitación del problema

## 1. Contexto

Los departamentos de emergencias operan con demanda variable y recursos
limitados. La llegada de pacientes cambia según la hora, mientras que los equipos
de atención suelen asignarse por turnos. Una distribución uniforme de capacidad
puede producir ociosidad durante períodos tranquilos y colas durante períodos de
alta demanda.

Este proyecto estudia un departamento de emergencias estadounidense de referencia
con datos públicos de NHAMCS 2022. La finalidad no es recomendar cambios clínicos,
sino evaluar mediante simulación si una redistribución de capacidad, manteniendo
constante el total de horas-recurso, mejora métricas operativas.

## 2. Actores y componentes

| Elemento | Papel dentro del sistema |
|---|---|
| Pacientes | Llegan, reciben una prioridad de triaje, esperan y son atendidos. |
| Personal de triaje | Clasifica la urgencia clínica. Se abstrae como una etapa sin cuello de botella en la primera versión. |
| Equipos de atención | Recurso compuesto que representa capacidad simultánea de atención. |
| Administración | Decide cuántos equipos asignar a cada bloque horario. |
| Investigadores | Calibran, ejecutan, verifican y comparan los escenarios. |

## 3. Entradas y salidas

### Entradas

- Intensidad de llegadas por hora, en pacientes/hora.
- Distribución de niveles de triaje.
- Distribución de duración efectiva de atención, en minutos.
- Número de equipos disponibles por bloque de cuatro horas.
- Duración de la simulación y período de calentamiento.
- Semilla del generador pseudoaleatorio.

### Salidas

- Tiempo medio, mediano y percentil 90 de espera, en minutos.
- Proporción de pacientes con espera superior a 60 minutos.
- Longitud media y máxima de la cola, en pacientes.
- Utilización de equipos de atención, en porcentaje.
- Pacientes que llegan, comienzan atención, terminan y permanecen en el sistema.

## 4. Pregunta de investigación

¿Cuánto puede reducirse el tiempo de espera de los pacientes al redistribuir una
cantidad fija de equipos de atención entre seis bloques de cuatro horas, sin
aumentar las horas-recurso totales?

## 5. Objetivos

### Objetivo general

Diseñar, implementar y evaluar una simulación de eventos discretos que compare una
asignación base contra una asignación optimizada de recursos de atención.

### Objetivos específicos

1. Estimar perfiles horarios de llegada y características de atención con datos
   públicos NHAMCS 2022.
2. Construir un modelo parametrizable con llegadas aleatorias, prioridades de
   triaje y capacidad variable.
3. Implementar un algoritmo genético que redistribuya recursos sin aumentar el
   total disponible.
4. Verificar que cada solución propuesta satisfaga las restricciones operativas.
5. Comparar escenarios mediante métricas comunes y experimentos reproducibles.

## 6. Métricas

La métrica principal es el **tiempo medio de espera hasta el inicio de la
atención**, expresado en minutos y sujeto a minimización.

Métricas secundarias:

- percentil 90 de espera;
- porcentaje de esperas mayores a 60 minutos;
- utilización de recursos;
- longitud máxima de la cola;
- pacientes completados durante el horizonte.

La optimización combinará media y percentil 90 para evitar una solución que
mejore el promedio mientras conserva esperas extremas.

## 7. Alcance

- Horizonte de 24 horas dividido en seis bloques de cuatro horas.
- Llegadas dependientes de la hora.
- Priorización por triaje.
- Capacidad de atención variable por bloque.
- Comparación bajo la misma demanda, semillas y total de horas-recurso.
- Aplicación educativa y de apoyo al análisis, no de decisión clínica.

## 8. Supuestos

- Cada paciente requiere un único equipo de atención a la vez.
- El nivel de triaje no cambia durante la espera.
- La disciplina de cola respeta prioridad clínica y orden de llegada dentro de
  cada prioridad.
- La capacidad cambia únicamente al inicio de cada bloque horario.
- Las distribuciones estimadas de NHAMCS son una referencia agregada y no una
  caracterización de una institución específica.
- La duración efectiva de servicio es una abstracción de ocupación del sistema,
  no tiempo continuo de contacto con un médico.

## 9. Restricciones

- La asignación utiliza números enteros de equipos.
- Debe existir al menos un equipo en cada bloque.
- No se supera un máximo configurable por bloque.
- El total de horas-recurso es igual en el escenario base y el optimizado.
- Los cambios entre bloques consecutivos se limitan para evitar horarios
  operacionalmente abruptos.

## 10. Fuera del modelo

- Diagnóstico, tratamiento y resultados clínicos.
- Traslados entre hospitales.
- Disponibilidad individual de médicos o enfermeros.
- Restricciones laborales detalladas por persona.
- Ocupación de camas de hospitalización después del departamento de emergencias.
- Predicciones aplicables directamente a Guatemala.

## 11. Fuente verificable

National Center for Health Statistics, *2022 National Hospital Ambulatory Medical
Care Survey Emergency Department Public Use Data File Documentation*:

https://ftp.cdc.gov/pub/health_statistics/nchs/dataset_documentation/NHAMCS/doc22-ed-508.pdf

La fuente identifica 16,025 registros y documenta las variables utilizadas. Los
datos reales, parámetros derivados, estimaciones y datos sintéticos se etiquetarán
por separado en todos los resultados.

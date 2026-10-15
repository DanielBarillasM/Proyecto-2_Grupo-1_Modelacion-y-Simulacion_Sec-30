# Parte 2. Investigación técnica

## 1. Técnicas seleccionadas

El proyecto combina dos componentes diferentes:

1. **Simulación de eventos discretos (DES):** representa llegadas, espera,
   prioridad, ocupación de recursos y salidas sin avanzar el reloj en intervalos
   innecesarios.
2. **Algoritmo genético restringido (GA):** busca una distribución discreta de
   recursos entre bloques horarios utilizando como evaluación una simulación
   estocástica.

La simulación es el modelo evaluador. El algoritmo genético no reemplaza el
modelo: propone configuraciones, solicita su evaluación y utiliza las métricas
resultantes para producir nuevas candidatas.

## 2. Simulación de eventos discretos

La DES representa el sistema como una secuencia ordenada de eventos. Para un
paciente, los eventos principales son:

1. llegada;
2. ingreso a la cola prioritaria;
3. adquisición de un equipo de atención;
4. inicio del servicio;
5. finalización y liberación del recurso.

SimPy administra el reloj de simulación, la agenda de eventos, los procesos y las
solicitudes de recursos. El equipo desarrolla la lógica del dominio: generador de
llegadas, prioridades, capacidad por horario, distribuciones, métricas,
verificaciones y escenarios.

### Por qué DES

- El estado cambia en instantes discretos, no continuamente.
- La congestión surge de la interacción entre llegadas y capacidad limitada.
- Permite registrar cada espera y cada transición.
- Es apropiada para comparar políticas bajo las mismas secuencias aleatorias.

## 3. Proceso de llegadas

Las llegadas se modelan mediante un proceso de Poisson no homogéneo aproximado por
tramos horarios. En una hora con tasa constante \(\lambda_h\), el tiempo entre
llegadas se genera como:

$$
T_h = -\frac{\ln(U)}{\lambda_h}, \qquad U\sim\mathrm{Uniforme}(0,1).
$$

La tasa cambia al cruzar cada frontera horaria. Los valores definitivos se
estimarán con `ARRTIME` de NHAMCS. Mientras se prepara el conjunto real, el perfil
incluido en la aplicación se identifica explícitamente como **estimado**.

## 4. Formulación del algoritmo genético

### 4.1 Representación

Un individuo es un vector entero de seis elementos:

$$
x=(x_0,x_1,\ldots,x_5), \qquad x_i\in\mathbb{Z}.
$$

Cada gen indica los equipos disponibles en un bloque de cuatro horas:

| Gen | Horario |
|---:|---|
| 0 | 00:00-03:59 |
| 1 | 04:00-07:59 |
| 2 | 08:00-11:59 |
| 3 | 12:00-15:59 |
| 4 | 16:00-19:59 |
| 5 | 20:00-23:59 |

### 4.2 Función objetivo

Para las esperas observadas en una simulación se minimiza:

$$
J(x)=0.7\,\overline{W}(x)+0.3\,Q_{0.90}(W(x)),
$$

donde ambos términos se expresan en minutos. La media representa desempeño
general y el percentil 90 penaliza esperas extremas. Los pesos serán objeto de
análisis de sensibilidad en la Parte 5.

### 4.3 Restricciones

$$
\begin{aligned}
x_i &\in \mathbb{Z}, \\
x_{\min} \leq x_i &\leq x_{\max}, \\
\sum_{i=0}^{5}x_i &= B, \\
|x_{i+1}-x_i| &\leq \Delta_{\max}.
\end{aligned}
$$

`B` es el número total de unidades asignadas a los seis bloques. Como cada bloque
tiene igual duración, conservar `B` conserva las horas-recurso. La última
restricción evita cambios operativamente abruptos.

### 4.4 Población inicial

La población combina:

- la asignación base;
- perturbaciones factibles de la base;
- composiciones aleatorias reparadas hasta sumar `B`.

Incluir la base garantiza que el optimizador nunca pierda la alternativa de
referencia.

### 4.5 Selección

Se utiliza torneo de tamaño tres. Primero se aplica la regla de factibilidad de
Deb:

1. una solución factible domina a una no factible;
2. entre soluciones factibles gana la de menor objetivo;
3. entre soluciones no factibles gana la de menor violación total.

### 4.6 Cruce

El cruce uniforme intercambia genes de dos progenitores. Como el intercambio puede
alterar la suma o las transiciones máximas, ambos descendientes pasan por una
función de reparación determinista.

### 4.7 Mutación

La mutación principal transfiere una unidad desde un bloque donante hacia un
bloque receptor. Esta operación conserva `B` antes de aplicar límites y reparación.

### 4.8 Reemplazo y elitismo

Los mejores individuos factibles pasan directamente a la siguiente generación.
El resto se completa con descendientes seleccionados, cruzados y mutados. Las
evaluaciones se almacenan en caché por asignación y conjunto de semillas.

### 4.9 Terminación

El algoritmo termina al cumplirse la primera condición:

- alcanzar el máximo de generaciones;
- no mejorar durante un número configurable de generaciones;
- alcanzar un objetivo de espera definido por el usuario.

Los valores iniciales previstos son 36 individuos, 40 generaciones, probabilidad
de cruce 0.80, probabilidad de mutación 0.25, dos élites y paciencia de diez
generaciones. Son parámetros configurables, no constantes ocultas.

## 5. Comparación con alternativas

| Alternativa | Ventaja | Motivo para no seleccionarla como técnica principal |
|---|---|---|
| Enumeración exhaustiva | Puede encontrar el mejor valor dentro del espacio evaluado | El costo crece con límites, bloques, réplicas y restricciones; cada candidato requiere simulaciones estocásticas. |
| Programación lineal entera | Ofrece garantías cuando el problema es lineal | La espera y los percentiles emergen de una simulación no lineal y estocástica. |
| Búsqueda aleatoria | Es sencilla y útil como referencia | No reutiliza información de soluciones prometedoras. |
| Enjambre de partículas | Tiene buen desempeño en espacios continuos | La representación es entera, restringida y requiere reparación frecuente. |
| Algoritmo genético | Maneja vectores enteros, operadores personalizados y restricciones | No garantiza el óptimo global y requiere controlar ruido y convergencia. |

La búsqueda aleatoria se conservará como comparador con el mismo presupuesto de
evaluaciones. Así se comprobará si la estructura evolutiva aporta valor frente a
probar configuraciones sin aprendizaje.

## 6. Control del ruido estocástico

- Cada candidato de una generación se evalúa con las mismas semillas.
- La función objetivo utiliza el promedio de varias réplicas configurables.
- La asignación final se reevalúa con un conjunto de semillas no usado durante la
  búsqueda.
- Se reportan dispersión e intervalos de confianza, no solo el mejor promedio.

## 7. División entre bibliotecas y trabajo del equipo

| Componente | Biblioteca | Desarrollo del equipo |
|---|---|---|
| Agenda de eventos y recursos | SimPy | Procesos de pacientes, cambio de capacidad, cola clínica y métricas |
| Números aleatorios y estadística básica | NumPy | Muestreo por hora, semillas comunes y validaciones |
| Tablas y preparación | pandas | Limpieza, reglas de inclusión y procedencia de variables |
| Gráficas | Plotly | Selección de métricas, narrativa y comparación de escenarios |
| Interfaz | Streamlit | Flujo, controles, validación y explicación de resultados |
| Algoritmo genético | Ninguna biblioteca de GA | Representación, selección, cruce, mutación, reparación, elitismo y terminación |

## 8. Limitaciones y condiciones de fallo

1. Un algoritmo genético no demuestra optimalidad global y puede converger
   prematuramente.
2. Una evaluación con pocas réplicas puede seleccionar una configuración por
   ruido aleatorio y no por desempeño verdadero.
3. NHAMCS es una muestra agregada de Estados Unidos; no contiene la configuración
   completa de personal de una institución concreta.
4. El recurso compuesto simplifica interacciones reales entre médicos,
   enfermería, diagnóstico y camas.
5. Una solución calibrada con demanda habitual puede degradarse ante eventos
   extremos; por ello se requiere sensibilidad.

## 9. Fuentes técnicas

La bibliografía identificable se mantiene en `report/references.bib`. Las fuentes
centrales son:

- Eiben y Smith (2015), fundamentos de computación evolutiva.
- Deb (2000), tratamiento de restricciones en algoritmos genéticos.
- Wang et al. (2025), optimización de personal de emergencias basada en simulación.
- Documentación oficial de SimPy 4.1.
- Documentación técnica y tablas de NHAMCS 2022.

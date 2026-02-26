# CrossFit Coach

Aplicación de entrenamiento de CrossFit que genera entrenamientos personalizados basados en la metodología de las certificaciones **CrossFit L1 y L2**. Funciona 100% local, sin APIs externas ni suscripciones.

## Características

- **Adaptado a tu material**: Solo programa movimientos que puedes hacer con tu equipamiento
- **Adaptado a tu nivel**: Escala automáticamente según tu experiencia (beginner -> elite)
- **Adaptado a tu tiempo**: Ajusta la sesión a los minutos que tengas disponibles
- **Periodización inteligente**: Macrociclo de 12 semanas (Foundation -> Accumulation -> Intensification -> Realization)
- **Feedback y adaptación**: Registra tus entrenamientos y el motor ajusta la programación según tu RPE, sueño, energía y agujetas
- **Basado en L1/L2**: Las 3 modalidades (M/G/W), varianza en dominios de tiempo, escalado, estructura de clase
- **Sin dependencias externas**: No necesitas API key, internet, ni suscripciones. Todo corre en local

## Arquitectura

```
Python + FastAPI + SQLite (100% offline)
```

- **knowledge.py**: 40+ movimientos CrossFit, benchmarks, principios L1/L2, sustituciones por equipamiento
- **models.py**: Modelos de datos (atleta, equipamiento, entrenamientos, historial, periodización)
- **periodization.py**: Lógica de mesociclos, fases, auto-regulación por feedback
- **engine.py**: Motor de reglas inteligente - selección de movimientos, generación de WODs, balance de modalidades, adaptación por feedback
- **api.py**: API REST con FastAPI
- **cli.py**: Interfaz de terminal con Rich

## Instalación

```bash
pip install -e .
```

## Uso (CLI)

### 1. Configurar perfil

```bash
cfc setup
```

Te preguntará: nombre, nivel, días/semana, duración, equipamiento disponible.

### 2. Generar entrenamiento de hoy

```bash
cfc workout                          # Entrenamiento del día
cfc workout --minutes 30             # Solo tengo 30 min
cfc workout --focus "heavy deadlift" # Quiero trabajar peso muerto pesado
```

### 3. Generar plan semanal

```bash
cfc week
```

### 4. Registrar entrenamiento (feedback)

```bash
cfc log --rpe 7 --score "5 rounds + 3 reps" --rx --energy 4 --sleep 3
cfc log --rpe 9 --score "18:35" --notes "Me costaron mucho los pull-ups" --soreness "shoulders,legs"
```

### 5. Ver progreso

```bash
cfc progress
```

### 6. Registrar benchmark

```bash
cfc benchmark --name "Fran" --value "4:23"
cfc benchmark --name "Back Squat 1RM" --value "120kg"
```

## Uso (API)

```bash
uvicorn crossfit_coach.api:app --reload
```

Endpoints en `http://localhost:8000/docs`:

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/athletes` | Crear perfil de atleta |
| GET | `/athletes/{id}` | Ver perfil |
| POST | `/workouts/generate` | Generar entrenamiento |
| POST | `/workouts/week` | Generar plan semanal |
| POST | `/logs` | Registrar entrenamiento + feedback |
| POST | `/benchmarks` | Registrar benchmark |
| GET | `/benchmarks/{id}` | Ver benchmarks |
| GET | `/progress/{id}` | Ver progreso + evaluación |
| POST | `/training/advance-week` | Avanzar semana de entrenamiento |

## Cómo funciona la periodización

```
Semanas 1-3:  FOUNDATION      (base aeróbica, mecánica, aprender movimientos)
Semana 4:     DELOAD           (recuperación activa)
Semanas 5-7:  ACCUMULATION     (más volumen, más complejidad)
Semana 8:     DELOAD           (recuperación)
Semanas 9-11: INTENSIFICATION  (más carga, más intensidad)
Semana 12:    REALIZATION      (test de benchmarks, ver progreso)
```

Auto-regulación: si tu RPE promedio > 8, baja la intensidad automáticamente.

## Cómo funciona el motor

El motor de reglas en `engine.py` hace todo lo que haría un coach L2:

1. **Filtra movimientos** por tu equipamiento y nivel (dificultad 1-10)
2. **Balancea modalidades** (M/G/W) a lo largo de la semana usando templates pre-diseñados
3. **Varía dominios de tiempo** (corto <7min, medio 7-15min, largo 15+min) y tipos de WOD (AMRAP, For Time, EMOM, Tabata, Chipper, Ladder)
4. **Programa fuerza** con esquemas por fase (5x5 en base, 5x3 en intensificación, 1RM test en realización)
5. **Genera warm-up** específico a los movimientos del WOD
6. **Adapta según feedback**: RPE alto -> baja intensidad, mal sueño -> sesión ligera, agujetas -> evita esa zona
7. **Sugiere cambio de nivel** cuando tu Rx rate y RPE indican que estás listo (o necesitas bajar)

Determinismo: el mismo día genera el mismo entrenamiento (seed basado en fecha), pero cada día es diferente.

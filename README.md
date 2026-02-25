# CrossFit Coach - AI-Powered Training

Aplicación de entrenamiento de CrossFit con IA que genera entrenamientos personalizados basados en la metodología de las certificaciones **CrossFit L1 y L2**.

## Características

- **Adaptado a tu material**: Solo programa movimientos que puedes hacer con tu equipamiento
- **Adaptado a tu nivel**: Escala automáticamente según tu experiencia (beginner → elite)
- **Adaptado a tu tiempo**: Ajusta la sesión a los minutos que tengas disponibles
- **Periodización inteligente**: Macrociclo de 12 semanas (Foundation → Accumulation → Intensification → Realization)
- **Feedback y adaptación**: Registra tus entrenamientos y la IA ajusta la programación según tu RPE, sueño, energía y agujetas
- **Basado en L1/L2**: Las 3 modalidades (M/G/W), varianza en dominios de tiempo, escalado, estructura de clase

## Arquitectura

```
Python + FastAPI + SQLite + Claude AI (Anthropic)
```

- **knowledge.py**: Base de datos de movimientos, benchmarks, principios L1/L2, sustituciones por equipamiento
- **models.py**: Modelos de datos (atleta, equipamiento, entrenamientos, historial, periodización)
- **periodization.py**: Lógica de mesociclos, fases, auto-regulación por feedback
- **engine.py**: Motor de generación con Claude AI - construye prompts contextuales para entrenamientos inteligentes
- **api.py**: API REST con FastAPI
- **cli.py**: Interfaz de terminal con Rich

## Instalación

```bash
pip install -e .
```

## Configuración

```bash
export ANTHROPIC_API_KEY=tu-api-key
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

Endpoints disponibles en `http://localhost:8000/docs`:

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/athletes` | Crear perfil de atleta |
| GET | `/athletes/{id}` | Ver perfil |
| POST | `/workouts/generate` | Generar entrenamiento |
| POST | `/workouts/week` | Generar plan semanal |
| POST | `/logs` | Registrar entrenamiento + feedback IA |
| POST | `/benchmarks` | Registrar benchmark |
| GET | `/benchmarks/{id}` | Ver benchmarks |
| GET | `/progress/{id}` | Ver progreso + evaluación IA |
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

La IA auto-regula: si tu RPE promedio > 8, baja la intensidad automáticamente.

## Cómo funciona la IA

Claude recibe como contexto:
1. Tu perfil completo (nivel, equipamiento, limitaciones)
2. La base de conocimiento L1/L2 (movimientos, escalados, principios)
3. Tu fase actual de entrenamiento y foco de la semana
4. Tu historial reciente (RPE, scores, modalidades usadas)
5. Sustituciones disponibles si te falta equipamiento

Con esto genera entrenamientos que:
- Respetan la varianza (tiempo, modalidad, carga)
- Siguen la progresión de la fase actual
- Se adaptan a cómo te sentiste en sesiones anteriores
- Solo usan movimientos que puedes hacer con tu material

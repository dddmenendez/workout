# Plan de Desarrollo — CrossFit Coach App

## Estado actual

Las **Fases 1, 2, 3, 4 y 5 están completadas**. App completa con frontend web.
Siguiente: **Fase 6 — Extras opcionales**.

---

## Fase 1 — Persistencia de entrenamientos generados ✅ COMPLETADA

> Los WODs generados se guardaban solo si se logueaban manualmente. Ahora se persisten automáticamente.

- [x] Guardar automáticamente cada workout generado en la tabla `PlannedWorkout`
- [x] Guardar los planes semanales completos en `TrainingWeek` + `PlannedWorkout`
- [x] Endpoint `GET /workouts/{athlete_id}/history` — listar entrenamientos pasados (paginado)
- [x] Endpoint `GET /workouts/detail/{workout_id}` — ver detalle de un entrenamiento guardado
- [x] Vincular `WorkoutLog` con `PlannedWorkout` al registrar resultado (`--workout-id` en CLI, `planned_workout_id` en API)
- [x] Comando CLI `cfc history` — ver historial de entrenamientos en tabla
- [x] Comando CLI `cfc show <id>` — ver detalle completo de un workout guardado
- [x] Modelo `PlannedWorkout` ampliado: `athlete_id`, `coaches_notes`, `target_time_domain`, `created_at`; `week_id` ahora es nullable para workouts sueltos
- [x] Fix: campo `date` → `workout_date` en `WorkoutRequest` (conflicto con Pydantic v2)

---

## Fase 2 — Soporte multiusuario real ✅ COMPLETADA

> Ahora la app soporta múltiples atletas con gestión completa desde API y CLI.

- [x] Endpoint `GET /athletes` — listar todos los atletas
- [x] Endpoint `PUT /athletes/{id}` — editar perfil parcial (equipo, nivel, objetivos)
- [x] Endpoint `DELETE /athletes/{id}` — eliminar atleta con cascade
- [x] CLI `cfc athletes` — listar atletas con indicador de activo
- [x] CLI `cfc switch <id>` — cambiar atleta activo
- [x] Persistir atleta activo en config local (`~/.crossfit_coach/config.json`)
- [x] Todos los comandos CLI respetan el atleta activo; `--athlete-id` sigue como override
- [x] `cfc setup` ya no reemplaza el primer atleta; crea uno nuevo y lo establece como activo
- [x] Schema `AthleteUpdate` para actualizaciones parciales
- [x] Nuevo módulo `crossfit_coach/config.py` para config local

---

## Fase 3 — Progreso y analíticas mejoradas ✅ COMPLETADA

> Tracking completo con tendencias, PRs, leaderboard y distribución real de modalidades.

- [x] Corregir cálculo de `rx_percentage` (ahora se calcula desde la BD real)
- [x] Endpoint `GET /progress/{id}/trends` — evolución semanal de RPE, volumen, Rx%, modalidades
- [x] Endpoint `GET /progress/{id}/benchmarks` — evolución temporal de cada benchmark agrupada
- [x] Comparativa entre atletas: `GET /leaderboard?benchmark=Fran`
- [x] Endpoint `GET /progress/{id}/prs` — records personales con fechas
- [x] CLI `cfc trends` — gráfica de RPE, Rx%, modalidades en terminal con barras
- [x] CLI `cfc prs` — tabla de PRs + historial de evolución por benchmark
- [x] `cfc progress` muestra Rx% real y distribución M/G/W con porcentajes
- [x] Schemas: `WeeklyStats`, `TrendsResponse`, `BenchmarkHistory`, `LeaderboardEntry`, `PersonalRecord`, etc.

---

## Fase 4 — Frontend web ✅ COMPLETADA

> SPA completa servida desde FastAPI con diseño dark glassmorphism, timer integrado, y feed social.

- [x] SPA vanilla HTML/CSS/JS servida desde `crossfit_coach/static/` (sin build step)
- [x] Diseño dark mode moderno con gradientes, glassmorphism, responsive mobile-first
- [x] Selector de atleta + modal de creación de atleta con equipamiento
- [x] **Dashboard**: hero card con stats (entrenamientos, Rx%, RPE, semana), donut de modalidades, benchmarks, evaluación
- [x] **WOD**: generador con selector de foco, display completo (warmup, fuerza, WOD, scaling, cooldown, notas coach)
- [x] **Timer**: cronómetro en vivo con estados visual (running/paused), se auto-pausa al loguear, duración se guarda en DB
- [x] **Log de resultado**: selector RPE visual (1-10 con colores), estrellas energía/sueño, checkbox Rx, score, notas
- [x] **Historial**: lista paginada de workouts con tipo, preview WOD, estado de log
- [x] **Progreso**: 4 gráficas Chart.js (RPE semanal, Rx%, volumen, modalidades stacked) + grid de PRs
- [x] **Feed Social**: feed público de entrenamientos de todos los atletas con avatar, tiempo relativo, stats
- [x] Campo `duration_seconds` añadido a WorkoutLog (modelo + schema + API)
- [x] Endpoint `GET /feed` — entrenamientos recientes de todos los atletas
- [x] 38 tests pasando (3 nuevos: feed empty, feed entries, log with duration)

---

## Fase 5 — Testing y robustez ✅ COMPLETADA

> Suite de tests completa con 38 tests pasando, más CI con GitHub Actions.

- [x] Tests unitarios para `periodization.py` — contexto de entrenamiento, auto-regulación, avance de semana, sugerencia de nivel, helpers
- [x] Tests de integración para la API — todos los endpoints (CRUD atletas, benchmarks, progreso, trends, leaderboard, PRs, logging, historial, avance semana)
- [x] Tests flujo completo: crear atleta → generar WOD → guardar → loguear → benchmarks → progreso → trends → PRs → advance week
- [x] Test aislamiento multiusuario: datos de un atleta no contaminan otro
- [x] Test generación de plan semanal completo
- [x] CI con GitHub Actions: ruff lint + pytest en Python 3.11/3.12 en push y PR
- [x] Fixture compartido: BD SQLite in-memory con `StaticPool` + `TestClient` de Starlette
- [x] `tests/conftest.py`, `tests/test_periodization.py`, `tests/test_api.py`, `tests/test_full_flow.py`

---

## Fase 6 — Mejoras opcionales (pendiente)

> Nice-to-have para una experiencia más completa. Todas opcionales.

- [ ] **Autenticación (JWT)** — proteger API con tokens, login/registro en frontend
- [ ] **Exportar a PDF** — descargar WOD del día o plan semanal en PDF
- [ ] **Notificaciones** — recordatorios de entrenamiento (email o push)
- [ ] **Vídeos demostrativos** — enlace a vídeo por cada movimiento del WOD
- [ ] **Integración wearables** — importar FC, calorías desde Garmin/Apple Watch
- [ ] **PWA** — service worker + manifest para instalar como app en móvil
- [ ] **Modo Box/Gimnasio** — gestión de clases grupales, horarios, coach asigna WODs

---

## Resumen de fases

| Fase | Estado | Descripción |
|------|--------|-------------|
| 1 — Persistencia | ✅ Completada | WODs se guardan automáticamente en BD |
| 2 — Multiusuario | ✅ Completada | CRUD atletas, switch activo, perfiles independientes |
| 3 — Progreso | ✅ Completada | Trends, PRs, leaderboard, Rx%, modalidades |
| 4 — Frontend | ✅ Completada | SPA dark mode, timer, feed social, gráficas |
| 5 — Testing | ✅ Completada | 38 tests, CI GitHub Actions (lint + pytest) |
| 6 — Extras | Pendiente | JWT, PDF, PWA, wearables, modo box |

---

## Base de datos

| Aspecto | Detalle |
|---------|---------|
| Motor | **SQLite** (sin servidor, sin configuración) |
| Archivo | `~/.crossfit_coach/coach.db` |
| ORM | SQLAlchemy 2.0 (modelos declarativos) |
| Migraciones | Alembic (disponible, auto-create en startup) |
| Tests | SQLite in-memory con `StaticPool` |

### Tablas principales

| Tabla | Guarda |
|-------|--------|
| `athletes` | Perfil: nombre, nivel, días/semana, duración sesión, objetivos, lesiones |
| `equipment` | Equipamiento por atleta (barra, anillas, remo, kettlebell, etc.) |
| `planned_workouts` | WODs generados: warmup, fuerza, WOD, cooldown, scaling, notas coach |
| `workout_logs` | Resultados: score, RPE, Rx, duración (timer), energía, sueño, agujetas |
| `training_weeks` | Semanas de periodización: fase, foco, intensidad objetivo |
| `benchmarks` | PRs y benchmarks: Fran, Cindy, 1RM Back Squat, etc. con fecha |
| `movements` | Librería de movimientos CrossFit (categoría, dificultad, scaling) |

Todo funciona offline en local. No se necesita cuenta en ningún servicio externo.

---

## Stack

| Componente | Tecnología |
|-----------|-----------|
| Backend | FastAPI + Uvicorn |
| BD | SQLite → `~/.crossfit_coach/coach.db` |
| ORM | SQLAlchemy 2.0 |
| CLI | Typer + Rich |
| Validación | Pydantic 2.0 |
| Frontend | HTML/CSS/JS vanilla + Chart.js |
| Tests | Pytest + Starlette TestClient |
| CI | GitHub Actions (ruff + pytest, Python 3.11/3.12) |
| Python | 3.11+ |

# Plan de Desarrollo — CrossFit Coach App

## Estado actual

Las **Fases 1, 2, 3 y 5 están completadas**. Persistencia, multiusuario, analíticas, y testing completos.
Siguiente: **Fase 4 — Frontend web**.

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

## Fase 4 — Frontend web

> Sin UI web, la app solo es accesible por terminal o cliente API (Postman, curl).

- [ ] Elegir framework frontend (React / Vue / Svelte)
- [ ] Pantalla de login/selección de atleta
- [ ] Dashboard principal: WOD del día + resumen de progreso
- [ ] Vista de calendario con entrenamientos pasados y planificados
- [ ] Formulario para registrar resultados (score, RPE, notas)
- [ ] Página de perfil: editar equipo, nivel, objetivos, frecuencia
- [ ] Página de progreso: gráficas de RPE, benchmarks, volumen, Rx%
- [ ] Leaderboard entre atletas
- [ ] Diseño responsive (móvil primero)

---

## Fase 5 — Testing y robustez ✅ COMPLETADA

> Suite de tests completa con 35 tests pasando, más CI con GitHub Actions.

- [x] Tests unitarios para `periodization.py` — contexto de entrenamiento, auto-regulación, avance de semana, sugerencia de nivel, helpers
- [x] Tests de integración para la API — todos los endpoints (CRUD atletas, benchmarks, progreso, trends, leaderboard, PRs, logging, historial, avance semana)
- [x] Tests flujo completo: crear atleta → generar WOD → guardar → loguear → benchmarks → progreso → trends → PRs → advance week
- [x] Test aislamiento multiusuario: datos de un atleta no contaminan otro
- [x] Test generación de plan semanal completo
- [x] CI con GitHub Actions: ruff lint + pytest en Python 3.11/3.12 en push y PR
- [x] Fixture compartido: BD SQLite in-memory con `StaticPool` + `TestClient` de Starlette
- [x] `tests/conftest.py`, `tests/test_periodization.py`, `tests/test_api.py`, `tests/test_full_flow.py`

---

## Fase 6 — Mejoras opcionales

> Nice-to-have para una experiencia más completa.

- [ ] Autenticación (JWT o similar) para la API
- [ ] Exportar entrenamientos a PDF
- [ ] Notificaciones/recordatorios de entrenamiento
- [ ] Enlaces a vídeos demostrativos por movimiento
- [ ] Integración con wearables (Garmin, Apple Watch) para importar métricas
- [ ] PWA para instalar como app en el móvil
- [ ] Modo "box/gimnasio": gestión de clases grupales y horarios

---

## Prioridad recomendada

```
Fase 1 (Persistencia)  ████████████ → Sin esto los datos se pierden
Fase 2 (Multiusuario)  ███████████  → Necesario para varios atletas
Fase 3 (Progreso)      ██████████   → Da sentido al tracking
Fase 5 (Tests)         █████████    → Seguridad antes de crecer
Fase 4 (Frontend)      ████████     → Accesibilidad para no-técnicos
Fase 6 (Extras)        █████        → Cuando todo lo anterior funcione
```

---

## Stack actual

| Componente | Tecnología |
|-----------|-----------|
| Backend | FastAPI + Uvicorn |
| BD | SQLite (local, sin servidor) |
| ORM | SQLAlchemy 2.0 |
| CLI | Typer + Rich |
| Validación | Pydantic 2.0 |
| Python | 3.11+ |

No se necesita cuenta en ningún servicio externo. Todo funciona offline en local.

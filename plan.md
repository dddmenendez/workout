# Plan de Desarrollo — CrossFit Coach App

## Estado actual

El backend (FastAPI + SQLite + CLI) está funcional como MVP.
La **Fase 1 está completada**: los entrenamientos se guardan automáticamente en BD.
El soporte multiusuario existe en el esquema de BD pero **no está expuesto** correctamente en CLI ni API.

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

## Fase 2 — Soporte multiusuario real

> La BD soporta varios atletas pero la API y CLI asumen uno solo.

- [ ] Endpoint `GET /athletes` — listar todos los atletas
- [ ] Endpoint `PUT /athletes/{id}` — editar perfil (equipo, nivel, objetivos)
- [ ] Endpoint `DELETE /athletes/{id}` — eliminar atleta
- [ ] CLI `cfc athletes` — listar atletas registrados
- [ ] CLI `cfc switch {id|nombre}` — cambiar atleta activo
- [ ] Persistir atleta activo en config local (`~/.crossfit_coach/config.json`)
- [ ] Todos los comandos CLI deben respetar el atleta activo sin necesidad de pasar `--athlete-id`

---

## Fase 3 — Progreso y analíticas mejoradas

> Existe tracking básico (RPE, benchmarks) pero falta visibilidad real del progreso.

- [ ] Corregir cálculo de `rx_percentage` (actualmente hardcodeado a `0.0` en `api.py`)
- [ ] Endpoint `GET /progress/{id}/trends` — evolución semanal de RPE, volumen, Rx%
- [ ] Endpoint `GET /progress/{id}/benchmarks` — evolución temporal de cada benchmark
- [ ] Comparativa entre atletas: `GET /leaderboard?benchmark=Fran`
- [ ] CLI `cfc trends` — mostrar gráfica de progreso en terminal (con Rich)
- [ ] Histórico de PRs (records personales) con fechas
- [ ] Distribución de modalidades (M/G/W) por semana/mes con porcentajes reales

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

## Fase 5 — Testing y robustez

> No hay tests. Cualquier cambio puede romper algo sin aviso.

- [ ] Tests unitarios para `engine.py` (generación de WODs, selección de movimientos, escalado)
- [ ] Tests unitarios para `periodization.py` (fases, semanas, deload)
- [ ] Tests de integración para la API (todos los endpoints)
- [ ] Tests para el flujo completo: crear atleta → generar WOD → guardar → loguear → ver progreso
- [ ] CI con GitHub Actions: lint + tests en cada push

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

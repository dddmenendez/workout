"""FastAPI endpoints for the CrossFit Coach application."""

from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from crossfit_coach.auth import (
    TokenResponse,
    UserLogin,
    UserRegister,
    get_current_user,
    get_db,
    login_user,
    register_user,
)
from crossfit_coach.database import Base, get_engine
from crossfit_coach.engine import (
    generate_adaptation_feedback,
    generate_progress_assessment,
    generate_week_plan,
    generate_workout,
)
from crossfit_coach.models import Athlete, Benchmark, Equipment, Follow, PlannedWorkout, TrainingWeek, User, WorkoutLog
from crossfit_coach.periodization import (
    advance_week,
    get_current_training_context,
    should_suggest_level_change,
)
from crossfit_coach.schemas import (
    AthleteCreate,
    AthleteResponse,
    AthleteUpdate,
    BenchmarkCreate,
    BenchmarkEntry,
    BenchmarkHistory,
    BenchmarkHistoryResponse,
    BenchmarkResponse,
    FeedEntry,
    FeedResponse,
    FollowListResponse,
    FollowRequest,
    FollowResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    PersonalRecord,
    PersonalRecordsResponse,
    PlannedWorkoutResponse,
    ProgressSummary,
    TeamLogEntry,
    TeamMemberSummary,
    TrendsResponse,
    WeekPlanResponse,
    WeeklyStats,
    WorkoutHistoryResponse,
    WorkoutLogCreate,
    WorkoutLogResponse,
    WorkoutRequest,
    WorkoutResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="CrossFit Coach",
    description="CrossFit training app based on L1/L2 methodology. Regístrate y entrena!",
    version="0.4.0",
    lifespan=lifespan,
)


def _athlete_to_profile(athlete: Athlete) -> dict:
    return {
        "name": athlete.name,
        "level": athlete.level.value,
        "training_days_per_week": athlete.training_days_per_week,
        "session_duration_minutes": athlete.session_duration_minutes,
        "goals": athlete.goals,
        "injuries_limitations": athlete.injuries_limitations,
        "equipment": [eq.name for eq in athlete.equipment],
    }


def _get_user_athlete(db: Session, user: User) -> Athlete:
    """Get the athlete profile for the current user."""
    athlete = db.query(Athlete).filter(Athlete.user_id == user.id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="No tenés perfil de atleta. Creá uno primero con POST /athletes")
    return athlete


def _save_workout(db, athlete_id: int, workout: WorkoutResponse, day_of_week: int, week_id: int | None = None) -> PlannedWorkout:
    """Persist a generated workout to the database."""
    pw = PlannedWorkout(
        athlete_id=athlete_id,
        week_id=week_id,
        day_of_week=day_of_week,
        workout_type=workout.wod_type,
        description=workout.wod,
        warmup=workout.warmup,
        strength=workout.strength_or_skill,
        wod=workout.wod,
        cooldown=workout.cooldown,
        modalities=",".join(workout.modalities),
        scaling_notes=workout.scaling_notes,
        coaches_notes=workout.coaches_notes,
        target_time_domain=workout.target_time_domain,
    )
    db.add(pw)
    return pw


# --- Auth endpoints ---


@app.post("/auth/register", response_model=TokenResponse, tags=["auth"])
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Registrar nuevo usuario."""
    return register_user(data, db)


@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Iniciar sesión."""
    return login_user(data, db)


# --- Athlete endpoints ---


@app.post("/athletes", response_model=AthleteResponse, tags=["athlete"])
def create_athlete(data: AthleteCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(Athlete).filter(Athlete.user_id == user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya tenés un perfil de atleta")

    athlete = Athlete(
        user_id=user.id,
        name=data.name,
        level=data.level,
        training_days_per_week=data.training_days_per_week,
        session_duration_minutes=data.session_duration_minutes,
        goals=data.goals,
        injuries_limitations=data.injuries_limitations,
    )
    db.add(athlete)
    db.flush()

    for eq_name in data.equipment:
        db.add(Equipment(athlete_id=athlete.id, name=eq_name))

    db.commit()
    db.refresh(athlete)

    return AthleteResponse(
        id=athlete.id,
        name=athlete.name,
        level=athlete.level,
        training_days_per_week=athlete.training_days_per_week,
        session_duration_minutes=athlete.session_duration_minutes,
        goals=athlete.goals,
        injuries_limitations=athlete.injuries_limitations,
        equipment=[eq.name for eq in athlete.equipment],
    )


@app.get("/athletes/me", response_model=AthleteResponse, tags=["athlete"])
def get_my_athlete(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    athlete = _get_user_athlete(db, user)
    return AthleteResponse(
        id=athlete.id,
        name=athlete.name,
        level=athlete.level,
        training_days_per_week=athlete.training_days_per_week,
        session_duration_minutes=athlete.session_duration_minutes,
        goals=athlete.goals,
        injuries_limitations=athlete.injuries_limitations,
        equipment=[eq.name for eq in athlete.equipment],
    )


@app.get("/athletes", response_model=list[AthleteResponse], tags=["athlete"])
def list_athletes(db: Session = Depends(get_db)):
    athletes = db.query(Athlete).order_by(Athlete.id).all()
    return [
        AthleteResponse(
            id=a.id,
            name=a.name,
            level=a.level,
            training_days_per_week=a.training_days_per_week,
            session_duration_minutes=a.session_duration_minutes,
            goals=a.goals,
            injuries_limitations=a.injuries_limitations,
            equipment=[eq.name for eq in a.equipment],
        )
        for a in athletes
    ]


@app.get("/athletes/{athlete_id}", response_model=AthleteResponse, tags=["athlete"])
def get_athlete(athlete_id: int, db: Session = Depends(get_db)):
    athlete = db.get(Athlete, athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return AthleteResponse(
        id=athlete.id,
        name=athlete.name,
        level=athlete.level,
        training_days_per_week=athlete.training_days_per_week,
        session_duration_minutes=athlete.session_duration_minutes,
        goals=athlete.goals,
        injuries_limitations=athlete.injuries_limitations,
        equipment=[eq.name for eq in athlete.equipment],
    )


@app.put("/athletes/{athlete_id}", response_model=AthleteResponse, tags=["athlete"])
def update_athlete(athlete_id: int, data: AthleteUpdate, db: Session = Depends(get_db)):
    athlete = db.get(Athlete, athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    if data.name is not None:
        athlete.name = data.name
    if data.level is not None:
        athlete.level = data.level
    if data.training_days_per_week is not None:
        athlete.training_days_per_week = data.training_days_per_week
    if data.session_duration_minutes is not None:
        athlete.session_duration_minutes = data.session_duration_minutes
    if data.goals is not None:
        athlete.goals = data.goals
    if data.injuries_limitations is not None:
        athlete.injuries_limitations = data.injuries_limitations
    if data.equipment is not None:
        db.query(Equipment).filter(Equipment.athlete_id == athlete.id).delete()
        for eq_name in data.equipment:
            db.add(Equipment(athlete_id=athlete.id, name=eq_name))

    db.commit()
    db.refresh(athlete)

    return AthleteResponse(
        id=athlete.id,
        name=athlete.name,
        level=athlete.level,
        training_days_per_week=athlete.training_days_per_week,
        session_duration_minutes=athlete.session_duration_minutes,
        goals=athlete.goals,
        injuries_limitations=athlete.injuries_limitations,
        equipment=[eq.name for eq in athlete.equipment],
    )


@app.delete("/athletes/{athlete_id}", tags=["athlete"])
def delete_athlete(athlete_id: int, db: Session = Depends(get_db)):
    athlete = db.get(Athlete, athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    db.delete(athlete)
    db.commit()
    return {"detail": f"Athlete '{athlete.name}' deleted"}


# --- Workout generation ---


@app.post("/workouts/generate", response_model=WorkoutResponse, tags=["workouts"])
def generate_single_workout(
    req: WorkoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athlete = _get_user_athlete(db, user)
    profile = _athlete_to_profile(athlete)

    if req.available_minutes:
        profile["available_minutes"] = req.available_minutes

    training_ctx = get_current_training_context(db, athlete)

    if req.focus:
        training_ctx["requested_focus"] = req.focus
    if req.exclude_movements:
        training_ctx["exclude_movements"] = req.exclude_movements

    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    training_ctx["day_of_week"] = days[req.workout_date.weekday()]

    result = generate_workout(profile, training_ctx)

    _save_workout(db, athlete.id, result, req.workout_date.isoweekday())
    db.commit()

    return result


@app.post("/workouts/week", response_model=WeekPlanResponse, tags=["workouts"])
def generate_weekly_plan(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athlete = _get_user_athlete(db, user)
    profile = _athlete_to_profile(athlete)
    training_ctx = get_current_training_context(db, athlete)

    plan = generate_week_plan(profile, training_ctx)

    # Persist the training week and each workout
    tw = TrainingWeek(
        athlete_id=athlete.id,
        week_number=plan.week_number,
        phase=plan.phase,
        focus=plan.focus,
        target_intensity=training_ctx.get("target_intensity", "moderate"),
    )
    db.add(tw)
    db.flush()

    day_map = {"Lunes": 1, "Martes": 2, "Miércoles": 3, "Jueves": 4, "Viernes": 5, "Sábado": 6, "Domingo": 7}
    for day_plan in plan.days:
        if not day_plan.rest_day and day_plan.workout:
            _save_workout(db, athlete.id, day_plan.workout, day_map.get(day_plan.day, 1), tw.id)

    db.commit()

    return plan


# --- Workout history ---


@app.get("/workouts/history", response_model=WorkoutHistoryResponse, tags=["workouts"])
def get_workout_history(
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athlete = _get_user_athlete(db, user)

    total = db.query(PlannedWorkout).filter(PlannedWorkout.athlete_id == athlete.id).count()
    workouts = (
        db.query(PlannedWorkout)
        .filter(PlannedWorkout.athlete_id == athlete.id)
        .order_by(PlannedWorkout.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return WorkoutHistoryResponse(
        workouts=[
            PlannedWorkoutResponse(
                id=w.id,
                athlete_id=w.athlete_id,
                day_of_week=w.day_of_week,
                workout_type=w.workout_type,
                warmup=w.warmup,
                strength=w.strength,
                wod=w.wod,
                cooldown=w.cooldown,
                modalities=w.modalities,
                scaling_notes=w.scaling_notes,
                coaches_notes=w.coaches_notes,
                target_time_domain=w.target_time_domain,
                created_at=w.created_at,
                has_log=w.log is not None,
            )
            for w in workouts
        ],
        total=total,
    )


@app.get("/workouts/detail/{workout_id}", response_model=PlannedWorkoutResponse, tags=["workouts"])
def get_workout_detail(workout_id: int, db: Session = Depends(get_db)):
    workout = db.get(PlannedWorkout, workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    return PlannedWorkoutResponse(
        id=workout.id,
        athlete_id=workout.athlete_id,
        day_of_week=workout.day_of_week,
        workout_type=workout.workout_type,
        warmup=workout.warmup,
        strength=workout.strength,
        wod=workout.wod,
        cooldown=workout.cooldown,
        modalities=workout.modalities,
        scaling_notes=workout.scaling_notes,
        coaches_notes=workout.coaches_notes,
        target_time_domain=workout.target_time_domain,
        created_at=workout.created_at,
        has_log=workout.log is not None,
    )


# --- Logging ---


@app.post("/logs", response_model=WorkoutLogResponse, tags=["logs"])
def log_workout(
    data: WorkoutLogCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athlete = _get_user_athlete(db, user)

    log = WorkoutLog(
        athlete_id=athlete.id,
        planned_workout_id=data.planned_workout_id,
        score=data.score,
        rpe=data.rpe,
        went_rx=data.went_rx,
        notes=data.notes,
        energy_level=data.energy_level,
        sleep_quality=data.sleep_quality,
        muscle_soreness=data.muscle_soreness,
        duration_seconds=data.duration_seconds,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    recent = (
        db.query(WorkoutLog)
        .filter(WorkoutLog.athlete_id == athlete.id)
        .order_by(WorkoutLog.completed_at.desc())
        .limit(7)
        .all()
    )
    recent_dicts = [
        {"score": r.score, "rpe": r.rpe, "went_rx": r.went_rx, "notes": r.notes}
        for r in recent
    ]

    feedback = generate_adaptation_feedback(data.model_dump(), recent_dicts)

    return WorkoutLogResponse(
        id=log.id,
        completed_at=log.completed_at,
        score=log.score,
        rpe=log.rpe,
        went_rx=log.went_rx,
        notes=log.notes,
        duration_seconds=log.duration_seconds,
        adaptation_feedback=feedback,
    )


# --- Benchmarks ---


@app.post("/benchmarks", response_model=BenchmarkResponse, tags=["benchmarks"])
def add_benchmark(
    data: BenchmarkCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athlete = _get_user_athlete(db, user)
    bm = Benchmark(athlete_id=athlete.id, name=data.name, value=data.value)
    db.add(bm)
    db.commit()
    db.refresh(bm)
    return BenchmarkResponse(name=bm.name, value=bm.value, recorded_at=bm.recorded_at)


@app.get("/benchmarks", response_model=list[BenchmarkResponse], tags=["benchmarks"])
def get_benchmarks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    athlete = _get_user_athlete(db, user)
    benchmarks = db.query(Benchmark).filter(Benchmark.athlete_id == athlete.id).all()
    return [BenchmarkResponse(name=b.name, value=b.value, recorded_at=b.recorded_at) for b in benchmarks]


# --- Progress ---


@app.get("/progress", response_model=ProgressSummary, tags=["progress"])
def get_progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    athlete = _get_user_athlete(db, user)
    ctx = get_current_training_context(db, athlete)
    profile = _athlete_to_profile(athlete)

    assessment = generate_progress_assessment(profile, ctx)
    level_suggestion = should_suggest_level_change(db, athlete)

    if level_suggestion:
        assessment += f"\n\n{level_suggestion}"

    recent_benchmarks = (
        db.query(Benchmark)
        .filter(Benchmark.athlete_id == athlete.id)
        .order_by(Benchmark.recorded_at.desc())
        .limit(5)
        .all()
    )

    total_logs = db.query(WorkoutLog).filter(WorkoutLog.athlete_id == athlete.id).count()
    rx_count = db.query(WorkoutLog).filter(WorkoutLog.athlete_id == athlete.id, WorkoutLog.went_rx.is_(True)).count()
    rx_pct = (rx_count / total_logs * 100) if total_logs > 0 else 0.0

    return ProgressSummary(
        total_workouts=ctx["total_workouts"],
        current_phase=ctx["phase"],
        current_week=ctx["week_number"],
        avg_rpe_last_week=ctx["avg_rpe"],
        rx_percentage=round(rx_pct, 1),
        modality_distribution=ctx["modality_distribution"],
        recent_benchmarks=[
            BenchmarkResponse(name=b.name, value=b.value, recorded_at=b.recorded_at)
            for b in recent_benchmarks
        ],
        assessment=assessment,
    )


# --- Trends ---


def _week_start(dt: datetime) -> date:
    """Return the Monday of the week containing dt."""
    d = dt.date() if isinstance(dt, datetime) else dt
    return d - timedelta(days=d.weekday())


@app.get("/progress/{athlete_id}/trends", response_model=TrendsResponse, tags=["progress"])
def get_trends(athlete_id: int, weeks: int = 8, db: Session = Depends(get_db)):
    athlete = db.get(Athlete, athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    logs = (
        db.query(WorkoutLog)
        .filter(WorkoutLog.athlete_id == athlete_id)
        .order_by(WorkoutLog.completed_at.asc())
        .all()
    )

    weekly: dict[date, list[WorkoutLog]] = defaultdict(list)
    for log in logs:
        ws = _week_start(log.completed_at)
        weekly[ws].append(log)

    sorted_weeks = sorted(weekly.keys(), reverse=True)[:weeks]
    sorted_weeks.reverse()

    result = []
    for ws in sorted_weeks:
        week_logs = weekly[ws]
        rpes = [l.rpe for l in week_logs if l.rpe is not None]
        rx_count = sum(1 for l in week_logs if l.went_rx)
        rx_pct = (rx_count / len(week_logs) * 100) if week_logs else 0.0

        mod_counts: dict[str, int] = {"monostructural": 0, "gymnastics": 0, "weightlifting": 0}
        for l in week_logs:
            if l.planned_workout and l.planned_workout.modalities:
                for mod in l.planned_workout.modalities.split(","):
                    mod = mod.strip()
                    if mod in mod_counts:
                        mod_counts[mod] += 1

        result.append(WeeklyStats(
            week_start=ws,
            total_workouts=len(week_logs),
            avg_rpe=round(sum(rpes) / len(rpes), 1) if rpes else None,
            rx_percentage=round(rx_pct, 1),
            modality_distribution=mod_counts,
        ))

    return TrendsResponse(athlete_id=athlete_id, weeks=result)


# --- Benchmark history ---


@app.get("/progress/{athlete_id}/benchmarks", response_model=BenchmarkHistoryResponse, tags=["progress"])
def get_benchmark_history(athlete_id: int, db: Session = Depends(get_db)):
    athlete = db.get(Athlete, athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    benchmarks = (
        db.query(Benchmark)
        .filter(Benchmark.athlete_id == athlete_id)
        .order_by(Benchmark.name, Benchmark.recorded_at.asc())
        .all()
    )

    grouped: dict[str, list[BenchmarkEntry]] = defaultdict(list)
    for bm in benchmarks:
        grouped[bm.name].append(BenchmarkEntry(value=bm.value, recorded_at=bm.recorded_at))

    return BenchmarkHistoryResponse(
        athlete_id=athlete_id,
        benchmarks=[BenchmarkHistory(name=name, entries=entries) for name, entries in grouped.items()],
    )


# --- Leaderboard ---


@app.get("/leaderboard", response_model=LeaderboardResponse, tags=["community"])
def get_leaderboard(benchmark: str, db: Session = Depends(get_db)):
    subquery = (
        db.query(
            Benchmark.athlete_id,
            func.max(Benchmark.recorded_at).label("latest"),
        )
        .filter(Benchmark.name == benchmark)
        .group_by(Benchmark.athlete_id)
        .subquery()
    )

    results = (
        db.query(Benchmark, Athlete.name)
        .join(Athlete, Athlete.id == Benchmark.athlete_id)
        .join(
            subquery,
            (Benchmark.athlete_id == subquery.c.athlete_id)
            & (Benchmark.recorded_at == subquery.c.latest)
            & (Benchmark.name == benchmark),
        )
        .all()
    )

    entries = [
        LeaderboardEntry(
            athlete_id=bm.athlete_id,
            athlete_name=athlete_name,
            value=bm.value,
            recorded_at=bm.recorded_at,
        )
        for bm, athlete_name in results
    ]

    return LeaderboardResponse(benchmark_name=benchmark, entries=entries)


# --- Personal Records ---


@app.get("/progress/{athlete_id}/prs", response_model=PersonalRecordsResponse, tags=["progress"])
def get_personal_records(athlete_id: int, db: Session = Depends(get_db)):
    athlete = db.get(Athlete, athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    subquery = (
        db.query(
            Benchmark.name,
            func.max(Benchmark.recorded_at).label("latest"),
        )
        .filter(Benchmark.athlete_id == athlete_id)
        .group_by(Benchmark.name)
        .subquery()
    )

    results = (
        db.query(Benchmark)
        .join(
            subquery,
            (Benchmark.name == subquery.c.name)
            & (Benchmark.recorded_at == subquery.c.latest)
            & (Benchmark.athlete_id == athlete_id),
        )
        .order_by(Benchmark.name)
        .all()
    )

    return PersonalRecordsResponse(
        athlete_id=athlete_id,
        records=[PersonalRecord(name=bm.name, value=bm.value, recorded_at=bm.recorded_at) for bm in results],
    )


# --- Advance week ---


@app.post("/training/advance-week", tags=["training"])
def advance_training_week(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    athlete = _get_user_athlete(db, user)
    week = advance_week(db, athlete)
    return {
        "week_number": week.week_number,
        "phase": week.phase.value,
        "focus": week.focus,
        "target_intensity": week.target_intensity,
    }


# --- Community endpoints (everyone sees everyone) ---


@app.get("/community/team", response_model=list[TeamMemberSummary], tags=["community"])
def get_team(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ver todos los atletas del grupo."""
    athletes = db.query(Athlete).join(User, Athlete.user_id == User.id).all()
    result = []
    for athlete in athletes:
        ctx = get_current_training_context(db, athlete)
        last_log = (
            db.query(WorkoutLog)
            .filter(WorkoutLog.athlete_id == athlete.id)
            .order_by(WorkoutLog.completed_at.desc())
            .first()
        )
        result.append(TeamMemberSummary(
            username=athlete.user.username,
            athlete_name=athlete.name,
            level=athlete.level,
            total_workouts=ctx["total_workouts"],
            avg_rpe_last_week=ctx["avg_rpe"],
            current_phase=ctx["phase"],
            current_week=ctx["week_number"],
            last_workout_date=last_log.completed_at if last_log else None,
        ))
    return result


@app.get("/community/{username}/progress", response_model=ProgressSummary, tags=["community"])
def get_member_progress(username: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ver el progreso de un compañero."""
    target_user = db.query(User).filter(User.username == username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    athlete = db.query(Athlete).filter(Athlete.user_id == target_user.id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Ese usuario no tiene perfil de atleta")

    ctx = get_current_training_context(db, athlete)
    profile = _athlete_to_profile(athlete)
    assessment = generate_progress_assessment(profile, ctx)
    level_suggestion = should_suggest_level_change(db, athlete)
    if level_suggestion:
        assessment += f"\n\n{level_suggestion}"

    recent_benchmarks = (
        db.query(Benchmark)
        .filter(Benchmark.athlete_id == athlete.id)
        .order_by(Benchmark.recorded_at.desc())
        .limit(5)
        .all()
    )

    return ProgressSummary(
        total_workouts=ctx["total_workouts"],
        current_phase=ctx["phase"],
        current_week=ctx["week_number"],
        avg_rpe_last_week=ctx["avg_rpe"],
        rx_percentage=0.0,
        modality_distribution=ctx["modality_distribution"],
        recent_benchmarks=[
            BenchmarkResponse(name=b.name, value=b.value, recorded_at=b.recorded_at)
            for b in recent_benchmarks
        ],
        assessment=assessment,
    )


@app.get("/community/logs", response_model=list[TeamLogEntry], tags=["community"])
def get_community_logs(limit: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ver los últimos entrenamientos de todo el grupo."""
    logs = (
        db.query(WorkoutLog)
        .join(Athlete, WorkoutLog.athlete_id == Athlete.id)
        .order_by(WorkoutLog.completed_at.desc())
        .limit(limit)
        .all()
    )
    return [
        TeamLogEntry(
            athlete_name=log.athlete.name,
            completed_at=log.completed_at,
            score=log.score,
            rpe=log.rpe,
            went_rx=log.went_rx,
            notes=log.notes,
        )
        for log in logs
    ]


# --- Social Feed ---


def _build_feed_entry(log: WorkoutLog, athlete: Athlete) -> FeedEntry:
    wod_summary = None
    wtype = None
    pw = log.planned_workout
    warmup = strength = wod_full = cooldown = scaling = coaches = None
    workout_id = None

    if pw:
        wod_summary = (pw.wod or "")[:120]
        wtype = pw.workout_type.value if pw.workout_type else None
        workout_id = pw.id
        warmup = pw.warmup
        strength = pw.strength
        wod_full = pw.wod
        cooldown = pw.cooldown
        scaling = pw.scaling_notes
        coaches = pw.coaches_notes

    return FeedEntry(
        athlete_id=log.athlete_id,
        athlete_name=athlete.name if athlete else "Unknown",
        workout_type=wtype,
        wod_summary=wod_summary,
        score=log.score,
        rpe=log.rpe,
        went_rx=log.went_rx,
        duration_seconds=log.duration_seconds,
        completed_at=log.completed_at,
        notes=log.notes,
        workout_id=workout_id,
        warmup=warmup,
        strength=strength,
        wod_full=wod_full,
        cooldown=cooldown,
        scaling=scaling,
        coaches_notes=coaches,
    )


@app.get("/feed", response_model=FeedResponse, tags=["community"])
def get_feed(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """Public feed: recent workouts from all athletes."""
    total = db.query(WorkoutLog).count()
    logs = (
        db.query(WorkoutLog)
        .order_by(WorkoutLog.completed_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    entries = []
    for log in logs:
        athlete = db.get(Athlete, log.athlete_id)
        entries.append(_build_feed_entry(log, athlete))

    return FeedResponse(entries=entries, total=total)


@app.get("/feed/{athlete_id}/following", response_model=FeedResponse, tags=["community"])
def get_following_feed(athlete_id: int, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """Feed filtered to athletes that athlete_id follows."""
    followed_ids = [
        f.followed_id
        for f in db.query(Follow).filter(Follow.follower_id == athlete_id).all()
    ]
    if not followed_ids:
        return FeedResponse(entries=[], total=0)

    query = db.query(WorkoutLog).filter(WorkoutLog.athlete_id.in_(followed_ids))
    total = query.count()
    logs = query.order_by(WorkoutLog.completed_at.desc()).offset(offset).limit(limit).all()

    entries = []
    for log in logs:
        athlete = db.get(Athlete, log.athlete_id)
        entries.append(_build_feed_entry(log, athlete))

    return FeedResponse(entries=entries, total=total)


# --- Follow ---


@app.post("/athletes/{athlete_id}/follow", response_model=FollowResponse, tags=["community"])
def follow_athlete(athlete_id: int, data: FollowRequest, db: Session = Depends(get_db)):
    """Athlete follows another athlete."""
    if data.follower_id == data.followed_id:
        raise HTTPException(status_code=400, detail="No puedes seguirte a ti mismo")

    if not db.get(Athlete, data.follower_id) or not db.get(Athlete, data.followed_id):
        raise HTTPException(status_code=404, detail="Atleta no encontrado")

    existing = db.query(Follow).filter(
        Follow.follower_id == data.follower_id,
        Follow.followed_id == data.followed_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya sigues a este atleta")

    follow = Follow(follower_id=data.follower_id, followed_id=data.followed_id)
    db.add(follow)
    db.commit()
    db.refresh(follow)

    followed = db.get(Athlete, data.followed_id)
    return FollowResponse(
        id=follow.id,
        follower_id=follow.follower_id,
        followed_id=follow.followed_id,
        followed_name=followed.name,
    )


@app.delete("/athletes/{athlete_id}/follow/{followed_id}", tags=["community"])
def unfollow_athlete(athlete_id: int, followed_id: int, db: Session = Depends(get_db)):
    follow = db.query(Follow).filter(
        Follow.follower_id == athlete_id,
        Follow.followed_id == followed_id,
    ).first()
    if not follow:
        raise HTTPException(status_code=404, detail="No sigues a ese atleta")
    db.delete(follow)
    db.commit()
    return {"ok": True}


@app.get("/athletes/{athlete_id}/follows", response_model=FollowListResponse, tags=["community"])
def get_follows(athlete_id: int, db: Session = Depends(get_db)):
    following = db.query(Follow).filter(Follow.follower_id == athlete_id).all()
    followers = db.query(Follow).filter(Follow.followed_id == athlete_id).all()

    return FollowListResponse(
        following=[
            FollowResponse(
                id=f.id, follower_id=f.follower_id, followed_id=f.followed_id,
                followed_name=db.get(Athlete, f.followed_id).name,
            ) for f in following
        ],
        followers=[
            FollowResponse(
                id=f.id, follower_id=f.follower_id, followed_id=f.followed_id,
                followed_name=db.get(Athlete, f.follower_id).name,
            ) for f in followers
        ],
    )


# --- Static frontend ---

_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")

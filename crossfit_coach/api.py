"""FastAPI endpoints for the CrossFit Coach application."""

from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
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
from crossfit_coach.models import Athlete, Benchmark, Equipment, User, WorkoutLog
from crossfit_coach.periodization import (
    advance_week,
    get_current_training_context,
    should_suggest_level_change,
)
from crossfit_coach.schemas import (
    AthleteCreate,
    AthleteResponse,
    BenchmarkCreate,
    BenchmarkResponse,
    ProgressSummary,
    WeekPlanResponse,
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
    version="0.3.0",
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

    return generate_workout(profile, training_ctx)


@app.post("/workouts/week", response_model=WeekPlanResponse, tags=["workouts"])
def generate_weekly_plan(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athlete = _get_user_athlete(db, user)
    profile = _athlete_to_profile(athlete)
    training_ctx = get_current_training_context(db, athlete)
    return generate_week_plan(profile, training_ctx)


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

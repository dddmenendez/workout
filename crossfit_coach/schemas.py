"""Pydantic schemas for API request/response validation."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from crossfit_coach.models import FitnessLevel, RPE, TrainingPhase, WorkoutType


# --- Athlete ---


class AthleteCreate(BaseModel):
    name: str
    level: FitnessLevel = FitnessLevel.BEGINNER
    training_days_per_week: int = Field(default=3, ge=1, le=7)
    session_duration_minutes: int = Field(default=60, ge=20, le=120)
    goals: str | None = None
    injuries_limitations: str | None = None
    equipment: list[str] = Field(default_factory=list)


class AthleteUpdate(BaseModel):
    name: str | None = None
    level: FitnessLevel | None = None
    training_days_per_week: int | None = Field(default=None, ge=1, le=7)
    session_duration_minutes: int | None = Field(default=None, ge=20, le=120)
    goals: str | None = None
    injuries_limitations: str | None = None
    equipment: list[str] | None = None


class AthleteResponse(BaseModel):
    id: int
    name: str
    level: FitnessLevel
    training_days_per_week: int
    session_duration_minutes: int
    goals: str | None
    injuries_limitations: str | None
    equipment: list[str]

    model_config = {"from_attributes": True}


# --- Workout ---


class WorkoutRequest(BaseModel):
    """Request a single workout or a full week."""
    athlete_id: int
    workout_date: date = Field(default_factory=date.today)
    available_minutes: int | None = None  # Override session duration
    focus: str | None = None  # e.g. "gymnastics pulling" or "heavy deadlift"
    exclude_movements: list[str] = Field(default_factory=list)


class WorkoutResponse(BaseModel):
    warmup: str
    strength_or_skill: str | None = None
    wod: str
    wod_type: WorkoutType
    target_time_domain: str
    modalities: list[str]
    scaling_notes: str
    cooldown: str
    coaches_notes: str  # Explanation of stimulus/intent


# --- Week Plan ---


class WeekPlanRequest(BaseModel):
    athlete_id: int
    week_start: date = Field(default_factory=date.today)


class DayPlan(BaseModel):
    day: str  # "Monday", "Tuesday", etc.
    rest_day: bool = False
    workout: WorkoutResponse | None = None


class WeekPlanResponse(BaseModel):
    week_number: int
    phase: TrainingPhase
    focus: str
    days: list[DayPlan]
    programming_notes: str


# --- Feedback / Log ---


class WorkoutLogCreate(BaseModel):
    athlete_id: int
    planned_workout_id: int | None = None
    score: str | None = None  # "5 rounds + 3 reps", "12:35", "100kg"
    rpe: int = Field(ge=1, le=10)
    went_rx: bool = False
    notes: str | None = None
    energy_level: int | None = Field(default=None, ge=1, le=5)
    sleep_quality: int | None = Field(default=None, ge=1, le=5)
    muscle_soreness: str | None = None


class WorkoutLogResponse(BaseModel):
    id: int
    completed_at: datetime
    score: str | None
    rpe: int | None
    went_rx: bool
    notes: str | None
    adaptation_feedback: str  # AI-generated insight on how this affects future programming

    model_config = {"from_attributes": True}


# --- Benchmark ---


class BenchmarkCreate(BaseModel):
    athlete_id: int
    name: str
    value: str


class BenchmarkResponse(BaseModel):
    name: str
    value: str
    recorded_at: date

    model_config = {"from_attributes": True}


# --- Progress ---


# --- Planned Workout (persisted) ---


class PlannedWorkoutResponse(BaseModel):
    id: int
    athlete_id: int
    day_of_week: int
    workout_type: WorkoutType
    warmup: str | None
    strength: str | None
    wod: str | None
    cooldown: str | None
    modalities: str
    scaling_notes: str | None
    coaches_notes: str | None
    target_time_domain: str | None
    created_at: datetime
    has_log: bool = False

    model_config = {"from_attributes": True}


class WorkoutHistoryResponse(BaseModel):
    workouts: list[PlannedWorkoutResponse]
    total: int


# --- Progress ---


class ProgressSummary(BaseModel):
    total_workouts: int
    current_phase: TrainingPhase
    current_week: int
    avg_rpe_last_week: float | None
    rx_percentage: float
    modality_distribution: dict[str, int]
    recent_benchmarks: list[BenchmarkResponse]
    assessment: str  # Progress summary and recommendations

"""Pydantic schemas for API request/response validation."""

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from crossfit_coach.models import FitnessLevel, RPE, TrainingPhase, WorkoutType


# --- Auth ---


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5)
    password: str = Field(min_length=6)
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: int
    email: str
    display_name: str
    athlete_id: int | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    athlete_id: int | None = None

    model_config = {"from_attributes": True}


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
    duration_seconds: int | None = None


class WorkoutLogResponse(BaseModel):
    id: int
    completed_at: datetime
    score: str | None
    rpe: int | None
    went_rx: bool
    notes: str | None
    duration_seconds: int | None = None
    adaptation_feedback: str

    model_config = {"from_attributes": True}


# --- Feed Social ---


class FeedEntry(BaseModel):
    athlete_id: int
    athlete_name: str
    workout_type: str | None = None
    wod_summary: str | None = None
    score: str | None = None
    rpe: int | None = None
    went_rx: bool = False
    duration_seconds: int | None = None
    completed_at: datetime
    notes: str | None = None
    # Full workout details (for expandable view)
    workout_id: int | None = None
    warmup: str | None = None
    strength: str | None = None
    wod_full: str | None = None
    cooldown: str | None = None
    scaling: str | None = None
    coaches_notes: str | None = None


class FeedResponse(BaseModel):
    entries: list[FeedEntry]
    total: int


# --- Follow ---


class FollowRequest(BaseModel):
    follower_id: int
    followed_id: int


class FollowResponse(BaseModel):
    id: int
    follower_id: int
    followed_id: int
    followed_name: str


class FollowListResponse(BaseModel):
    following: list[FollowResponse]
    followers: list[FollowResponse]


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


# --- Trends ---


class WeeklyStats(BaseModel):
    week_start: date
    total_workouts: int
    avg_rpe: float | None
    rx_percentage: float
    modality_distribution: dict[str, int]


class TrendsResponse(BaseModel):
    athlete_id: int
    weeks: list[WeeklyStats]


# --- Benchmark history ---


class BenchmarkEntry(BaseModel):
    value: str
    recorded_at: date


class BenchmarkHistory(BaseModel):
    name: str
    entries: list[BenchmarkEntry]


class BenchmarkHistoryResponse(BaseModel):
    athlete_id: int
    benchmarks: list[BenchmarkHistory]


# --- Leaderboard ---


class LeaderboardEntry(BaseModel):
    athlete_id: int
    athlete_name: str
    value: str
    recorded_at: date


class LeaderboardResponse(BaseModel):
    benchmark_name: str
    entries: list[LeaderboardEntry]


# --- Personal Records ---


class PersonalRecord(BaseModel):
    name: str
    value: str
    recorded_at: date


class PersonalRecordsResponse(BaseModel):
    athlete_id: int
    records: list[PersonalRecord]

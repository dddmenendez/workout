"""Data models for athlete profile, equipment, workouts, and training history."""

import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crossfit_coach.database import Base


# --- Enums ---


class FitnessLevel(str, enum.Enum):
    BEGINNER = "beginner"  # < 6 months training
    INTERMEDIATE = "intermediate"  # 6-24 months
    ADVANCED = "advanced"  # 2-5 years
    ELITE = "elite"  # 5+ years / competitive


class MovementCategory(str, enum.Enum):
    """CrossFit L1: 3 modalities."""
    MONOSTRUCTURAL = "monostructural"  # cardio: run, row, bike, jump rope
    GYMNASTICS = "gymnastics"  # bodyweight: pull-ups, push-ups, HSPU, muscle-ups
    WEIGHTLIFTING = "weightlifting"  # external load: clean, snatch, deadlift, press


class WorkoutType(str, enum.Enum):
    """CrossFit L1 workout structures."""
    AMRAP = "amrap"  # As Many Rounds As Possible
    FOR_TIME = "for_time"  # Complete work ASAP
    EMOM = "emom"  # Every Minute On the Minute
    TABATA = "tabata"  # 20s on / 10s off
    STRENGTH = "strength"  # Percentage-based lifting
    SKILL = "skill"  # Practice / progression work
    CHIPPER = "chipper"  # Long list, one pass through
    LADDER = "ladder"  # Ascending/descending reps


class TrainingPhase(str, enum.Enum):
    """Periodization phases (L2 programming concepts)."""
    FOUNDATION = "foundation"  # Build base, learn movements
    ACCUMULATION = "accumulation"  # Volume increase
    INTENSIFICATION = "intensification"  # Intensity increase
    REALIZATION = "realization"  # Peak / test
    DELOAD = "deload"  # Active recovery


class RPE(int, enum.Enum):
    """Rate of Perceived Exertion (1-10)."""
    VERY_LIGHT = 1
    LIGHT = 2
    MODERATE = 3
    SOMEWHAT_HARD = 4
    HARD = 5
    HARDER = 6
    VERY_HARD = 7
    EXTREMELY_HARD = 8
    MAX_EFFORT = 9
    ABSOLUTE_MAX = 10


# --- Models ---


class Athlete(Base):
    __tablename__ = "athletes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    level: Mapped[FitnessLevel] = mapped_column(Enum(FitnessLevel), default=FitnessLevel.BEGINNER)
    training_days_per_week: Mapped[int] = mapped_column(Integer, default=3)
    session_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    injuries_limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    equipment: Mapped[list["Equipment"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")
    benchmarks: Mapped[list["Benchmark"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")
    workout_logs: Mapped[list["WorkoutLog"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")
    training_plan: Mapped[list["TrainingWeek"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")
    planned_workouts: Mapped[list["PlannedWorkout"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    name: Mapped[str] = mapped_column(String(100))  # e.g. "barbell", "pull_up_bar"
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. "up to 100kg plates"

    athlete: Mapped["Athlete"] = relationship(back_populates="equipment")


class Movement(Base):
    """Movement library - CrossFit L1/L2 movements."""
    __tablename__ = "movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[MovementCategory] = mapped_column(Enum(MovementCategory))
    equipment_needed: Mapped[str] = mapped_column(Text, default="none")  # comma-separated
    scaling_options: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-like scaling
    points_of_performance: Mapped[str | None] = mapped_column(Text, nullable=True)  # L1 key points
    l2_progressions: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)  # 1-10


class Benchmark(Base):
    """Track benchmark WODs and strength PRs."""
    __tablename__ = "benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    name: Mapped[str] = mapped_column(String(100))  # "Fran", "Back Squat 1RM", etc.
    value: Mapped[str] = mapped_column(String(50))  # "3:45", "120kg"
    recorded_at: Mapped[date] = mapped_column(Date, default=date.today)

    athlete: Mapped["Athlete"] = relationship(back_populates="benchmarks")


class TrainingWeek(Base):
    """Planned training week within a mesocycle."""
    __tablename__ = "training_weeks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    week_number: Mapped[int] = mapped_column(Integer)
    phase: Mapped[TrainingPhase] = mapped_column(Enum(TrainingPhase))
    focus: Mapped[str] = mapped_column(Text)  # e.g. "squat strength + gymnastics pulling"
    target_intensity: Mapped[str] = mapped_column(String(20))  # "low", "moderate", "high"
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    athlete: Mapped["Athlete"] = relationship(back_populates="training_plan")
    workouts: Mapped[list["PlannedWorkout"]] = relationship(back_populates="week", cascade="all, delete-orphan")


class PlannedWorkout(Base):
    """A specific planned workout within a training week."""
    __tablename__ = "planned_workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    week_id: Mapped[int | None] = mapped_column(ForeignKey("training_weeks.id"), nullable=True)
    day_of_week: Mapped[int] = mapped_column(Integer)  # 1=Monday, 7=Sunday
    workout_type: Mapped[WorkoutType] = mapped_column(Enum(WorkoutType))
    description: Mapped[str] = mapped_column(Text)  # Full workout description
    warmup: Mapped[str | None] = mapped_column(Text, nullable=True)
    strength: Mapped[str | None] = mapped_column(Text, nullable=True)
    wod: Mapped[str | None] = mapped_column(Text, nullable=True)
    cooldown: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    modalities: Mapped[str] = mapped_column(Text)  # comma-separated: "gymnastics,weightlifting"
    scaling_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    coaches_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_time_domain: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    athlete: Mapped["Athlete"] = relationship(back_populates="planned_workouts")
    week: Mapped["TrainingWeek | None"] = relationship(back_populates="workouts")
    log: Mapped["WorkoutLog | None"] = relationship(back_populates="planned_workout", uselist=False)


class WorkoutLog(Base):
    """Completed workout log with feedback for adaptation."""
    __tablename__ = "workout_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    planned_workout_id: Mapped[int | None] = mapped_column(ForeignKey("planned_workouts.id"), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    score: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "5 rounds + 3 reps", "12:35"
    rpe: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-10
    went_rx: Mapped[bool] = mapped_column(default=False)  # Did prescribed weight/movements
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    energy_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5 pre-workout
    sleep_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    muscle_soreness: Mapped[str | None] = mapped_column(Text, nullable=True)  # body areas

    athlete: Mapped["Athlete"] = relationship(back_populates="workout_logs")
    planned_workout: Mapped["PlannedWorkout | None"] = relationship(back_populates="log")

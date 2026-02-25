"""Periodization logic - manages mesocycles, phases, and training week progression.

Based on CrossFit L2 programming concepts:
- Mesocycle: 4 weeks (3 loading + 1 deload)
- Macrocycle: 3 mesocycles (~12 weeks)
- Phases: Foundation -> Accumulation -> Intensification -> Realization
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from crossfit_coach.models import (
    Athlete,
    FitnessLevel,
    TrainingPhase,
    TrainingWeek,
    WorkoutLog,
)


# Phase configuration
PHASE_CONFIG = {
    TrainingPhase.FOUNDATION: {
        "duration_weeks": 4,
        "intensity": "low-moderate",
        "volume": "moderate",
        "focus_areas": [
            "Movement quality and mechanics",
            "Aerobic base building",
            "Learn/refine fundamental movements",
            "Establish baseline benchmarks",
        ],
        "weekly_pattern": [
            {"focus": "Squat pattern + monostructural", "intensity": "low"},
            {"focus": "Press/push pattern + gymnastics", "intensity": "moderate"},
            {"focus": "Hinge pattern + mixed modal", "intensity": "moderate"},
            {"focus": "Deload - movement practice + light conditioning", "intensity": "low"},
        ],
    },
    TrainingPhase.ACCUMULATION: {
        "duration_weeks": 4,
        "intensity": "moderate",
        "volume": "high",
        "focus_areas": [
            "Increase training volume",
            "Add movement complexity",
            "Longer time domain WODs",
            "Build work capacity",
        ],
        "weekly_pattern": [
            {"focus": "Heavy squat + medium WOD (G+W)", "intensity": "moderate"},
            {"focus": "Gymnastics skill + long chipper (M+G+W)", "intensity": "moderate"},
            {"focus": "Olympic lifting technique + short sprint (W)", "intensity": "high"},
            {"focus": "Deload - technique + light mixed modal", "intensity": "low"},
        ],
    },
    TrainingPhase.INTENSIFICATION: {
        "duration_weeks": 3,
        "intensity": "high",
        "volume": "moderate",
        "focus_areas": [
            "Increase load and intensity",
            "Reduce volume slightly",
            "Short-medium time domains",
            "Competition-style WODs",
        ],
        "weekly_pattern": [
            {"focus": "Heavy strength + short intense WOD", "intensity": "high"},
            {"focus": "Skills under fatigue + medium WOD", "intensity": "high"},
            {"focus": "Moderate - active recovery + technique", "intensity": "moderate"},
        ],
    },
    TrainingPhase.REALIZATION: {
        "duration_weeks": 1,
        "intensity": "max",
        "volume": "low",
        "focus_areas": [
            "Test benchmarks",
            "1RM testing",
            "Benchmark WODs",
            "Celebrate progress",
        ],
        "weekly_pattern": [
            {"focus": "Benchmark testing week", "intensity": "high"},
        ],
    },
    TrainingPhase.DELOAD: {
        "duration_weeks": 1,
        "intensity": "low",
        "volume": "low",
        "focus_areas": [
            "Active recovery",
            "Mobility work",
            "Light movement practice",
            "Mental recovery",
        ],
        "weekly_pattern": [
            {"focus": "Recovery and mobility", "intensity": "low"},
        ],
    },
}

# Full macrocycle progression (12 weeks)
MACROCYCLE = [
    # Mesocycle 1: Foundation
    (TrainingPhase.FOUNDATION, 1),
    (TrainingPhase.FOUNDATION, 2),
    (TrainingPhase.FOUNDATION, 3),
    (TrainingPhase.DELOAD, 4),
    # Mesocycle 2: Accumulation
    (TrainingPhase.ACCUMULATION, 5),
    (TrainingPhase.ACCUMULATION, 6),
    (TrainingPhase.ACCUMULATION, 7),
    (TrainingPhase.DELOAD, 8),
    # Mesocycle 3: Intensification + Realization
    (TrainingPhase.INTENSIFICATION, 9),
    (TrainingPhase.INTENSIFICATION, 10),
    (TrainingPhase.INTENSIFICATION, 11),
    (TrainingPhase.REALIZATION, 12),
]


def get_current_training_context(db: Session, athlete: Athlete) -> dict:
    """Determine where the athlete is in their training cycle and build context."""

    # Count completed workouts
    total_logs = db.query(WorkoutLog).filter(WorkoutLog.athlete_id == athlete.id).count()

    # Get latest training week
    latest_week = (
        db.query(TrainingWeek)
        .filter(TrainingWeek.athlete_id == athlete.id)
        .order_by(TrainingWeek.week_number.desc())
        .first()
    )

    # Determine current week in macrocycle
    if latest_week:
        current_week_num = latest_week.week_number
    else:
        current_week_num = 1

    # Get phase and focus from macrocycle
    cycle_index = (current_week_num - 1) % len(MACROCYCLE)
    phase, week_num = MACROCYCLE[cycle_index]
    phase_config = PHASE_CONFIG[phase]

    # Get weekly pattern index within phase
    pattern_index = (current_week_num - 1) % len(phase_config["weekly_pattern"])
    week_pattern = phase_config["weekly_pattern"][pattern_index]

    # Get recent logs for feedback
    recent_logs = (
        db.query(WorkoutLog)
        .filter(WorkoutLog.athlete_id == athlete.id)
        .order_by(WorkoutLog.completed_at.desc())
        .limit(7)
        .all()
    )

    # Calculate recent stats
    avg_rpe = None
    recent_modalities = []
    recent_types = []
    last_rpe = None
    last_soreness = None

    if recent_logs:
        rpes = [log.rpe for log in recent_logs if log.rpe is not None]
        avg_rpe = sum(rpes) / len(rpes) if rpes else None
        last_rpe = recent_logs[0].rpe if recent_logs[0].rpe else None
        last_soreness = recent_logs[0].muscle_soreness

        for log in recent_logs:
            if log.planned_workout:
                recent_modalities.append(log.planned_workout.modalities)
                recent_types.append(log.planned_workout.workout_type.value)

    # Auto-regulate: adjust intensity based on feedback
    target_intensity = week_pattern["intensity"]
    if avg_rpe is not None:
        if avg_rpe > 8:
            target_intensity = "low"  # Athlete is overtrained, back off
        elif avg_rpe > 7:
            target_intensity = _lower_intensity(target_intensity)

    # Get benchmarks
    benchmarks = {}
    for bm in athlete.benchmarks:
        benchmarks[bm.name] = bm.value

    return {
        "phase": phase.value,
        "week_number": week_num,
        "focus": week_pattern["focus"],
        "target_intensity": target_intensity,
        "avg_rpe": avg_rpe,
        "last_rpe": last_rpe,
        "last_soreness": last_soreness,
        "recent_modalities": ", ".join(recent_modalities[-5:]) if recent_modalities else "None",
        "recent_workout_types": ", ".join(recent_types[-5:]) if recent_types else "None",
        "total_workouts": total_logs,
        "benchmarks": benchmarks,
        "modality_distribution": _count_modalities(recent_logs),
    }


def advance_week(db: Session, athlete: Athlete) -> TrainingWeek:
    """Advance to the next training week in the macrocycle."""

    latest_week = (
        db.query(TrainingWeek)
        .filter(TrainingWeek.athlete_id == athlete.id)
        .order_by(TrainingWeek.week_number.desc())
        .first()
    )

    next_week_num = (latest_week.week_number + 1) if latest_week else 1
    cycle_index = (next_week_num - 1) % len(MACROCYCLE)
    phase, _ = MACROCYCLE[cycle_index]
    phase_config = PHASE_CONFIG[phase]
    pattern_index = (next_week_num - 1) % len(phase_config["weekly_pattern"])
    week_pattern = phase_config["weekly_pattern"][pattern_index]

    new_week = TrainingWeek(
        athlete_id=athlete.id,
        week_number=next_week_num,
        phase=phase,
        focus=week_pattern["focus"],
        target_intensity=week_pattern["intensity"],
    )

    db.add(new_week)
    db.commit()
    db.refresh(new_week)

    return new_week


def should_suggest_level_change(db: Session, athlete: Athlete) -> str | None:
    """Check if athlete should move up or down a level based on performance data."""

    recent_logs = (
        db.query(WorkoutLog)
        .filter(WorkoutLog.athlete_id == athlete.id)
        .order_by(WorkoutLog.completed_at.desc())
        .limit(20)
        .all()
    )

    if len(recent_logs) < 10:
        return None

    rx_rate = sum(1 for log in recent_logs if log.went_rx) / len(recent_logs)
    avg_rpe = sum(log.rpe for log in recent_logs if log.rpe) / max(
        sum(1 for log in recent_logs if log.rpe), 1
    )

    current_level = athlete.level

    # Suggest level up: consistently doing Rx and RPE is manageable
    if rx_rate > 0.8 and avg_rpe < 6 and current_level != FitnessLevel.ELITE:
        levels = list(FitnessLevel)
        next_level = levels[levels.index(current_level) + 1]
        return f"Suggested level up to {next_level.value}: Rx rate {rx_rate:.0%}, avg RPE {avg_rpe:.1f}"

    # Suggest level down: struggling with Rx and RPE is very high
    if rx_rate < 0.2 and avg_rpe > 8 and current_level != FitnessLevel.BEGINNER:
        levels = list(FitnessLevel)
        prev_level = levels[levels.index(current_level) - 1]
        return f"Suggested level down to {prev_level.value}: Rx rate {rx_rate:.0%}, avg RPE {avg_rpe:.1f}"

    return None


def _lower_intensity(intensity: str) -> str:
    mapping = {"high": "moderate", "moderate": "low", "low": "low", "max": "high"}
    return mapping.get(intensity, intensity)


def _count_modalities(logs: list) -> dict[str, int]:
    counts = {"monostructural": 0, "gymnastics": 0, "weightlifting": 0}
    for log in logs:
        if log.planned_workout and log.planned_workout.modalities:
            for mod in log.planned_workout.modalities.split(","):
                mod = mod.strip()
                if mod in counts:
                    counts[mod] += 1
    return counts

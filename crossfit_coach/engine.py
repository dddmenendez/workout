"""Rule-based workout generation engine - no external API needed.

Generates CrossFit workouts using deterministic logic based on L1/L2 methodology:
- Movement selection filtered by equipment + level
- Modality balancing (M/G/W combinations)
- Time domain variance (short/medium/long)
- Workout type rotation (AMRAP, For Time, EMOM, etc.)
- Warm-up generation specific to movements in the WOD
- Scaling notes based on knowledge base
- Periodization-aware intensity/volume adjustments
- Feedback-based adaptation
"""

import hashlib
import random
from datetime import date

from crossfit_coach.knowledge import MOVEMENTS, MOVEMENT_SUBSTITUTIONS
from crossfit_coach.models import FitnessLevel, MovementCategory, TrainingPhase, WorkoutType
from crossfit_coach.schemas import (
    DayPlan,
    WeekPlanResponse,
    WorkoutResponse,
)


# --- Rep schemes by workout type and time domain ---

REP_SCHEMES = {
    WorkoutType.AMRAP: {
        "short": {"minutes": [7, 8, 10], "rounds_movements": [2, 3], "reps_range": (5, 15)},
        "medium": {"minutes": [12, 14, 15], "rounds_movements": [3, 4], "reps_range": (8, 20)},
        "long": {"minutes": [18, 20, 25], "rounds_movements": [4, 5], "reps_range": (10, 25)},
    },
    WorkoutType.FOR_TIME: {
        "short": {"rounds": [3, 5], "movements": [2, 3], "reps_range": (5, 15)},
        "medium": {"rounds": [3, 4, 5], "movements": [3, 4], "reps_range": (10, 21)},
        "long": {"rounds": [4, 5], "movements": [4, 5, 6], "reps_range": (15, 30)},
    },
    WorkoutType.EMOM: {
        "short": {"minutes": [8, 10], "movements_per_minute": [1, 2], "reps_range": (3, 8)},
        "medium": {"minutes": [12, 14, 16], "movements_per_minute": [1, 2], "reps_range": (5, 12)},
        "long": {"minutes": [20, 24, 30], "movements_per_minute": [1, 2], "reps_range": (6, 15)},
    },
    WorkoutType.TABATA: {
        "short": {"rounds": [4, 6], "movements": [2, 3], "reps_range": (0, 0)},
        "medium": {"rounds": [6, 8], "movements": [3, 4], "reps_range": (0, 0)},
        "long": {"rounds": [8, 10], "movements": [4, 5], "reps_range": (0, 0)},
    },
    WorkoutType.CHIPPER: {
        "medium": {"movements": [4, 5, 6], "reps_range": (15, 30)},
        "long": {"movements": [6, 7, 8], "reps_range": (20, 50)},
    },
    WorkoutType.LADDER: {
        "short": {"start": 2, "increment": 2, "rounds": 5, "movements": [1, 2]},
        "medium": {"start": 3, "increment": 3, "rounds": 7, "movements": [2, 3]},
    },
}

# Strength programming by phase
STRENGTH_TEMPLATES = {
    TrainingPhase.FOUNDATION: [
        {"scheme": "5x5", "intensity": "60-70%", "rest": "2-3 min", "description": "5 series de 5 repeticiones al {intensity} de tu 1RM. Descanso: {rest}"},
        {"scheme": "3x8", "intensity": "55-65%", "rest": "90s-2 min", "description": "3 series de 8 repeticiones al {intensity}. Foco en técnica perfecta. Descanso: {rest}"},
        {"scheme": "4x6", "intensity": "60-70%", "rest": "2 min", "description": "4 series de 6 repeticiones al {intensity}. Descanso: {rest}"},
    ],
    TrainingPhase.ACCUMULATION: [
        {"scheme": "5x5", "intensity": "70-80%", "rest": "2-3 min", "description": "5x5 al {intensity} de tu 1RM. Descanso: {rest}"},
        {"scheme": "4x6", "intensity": "70-75%", "rest": "2 min", "description": "4x6 al {intensity}. Descanso: {rest}"},
        {"scheme": "6x3", "intensity": "75-85%", "rest": "2-3 min", "description": "6x3 al {intensity}. Foco en velocidad de ejecución. Descanso: {rest}"},
    ],
    TrainingPhase.INTENSIFICATION: [
        {"scheme": "5x3", "intensity": "80-90%", "rest": "3 min", "description": "5x3 al {intensity} de tu 1RM. Descanso: {rest}"},
        {"scheme": "7x2", "intensity": "85-90%", "rest": "3 min", "description": "7x2 al {intensity}. Foco en potencia máxima. Descanso: {rest}"},
        {"scheme": "3-3-3-1-1-1", "intensity": "80-95%", "rest": "3 min", "description": "3-3-3-1-1-1 subiendo peso. Empieza al 80% y sube hasta el 90-95%. Descanso: {rest}"},
    ],
    TrainingPhase.REALIZATION: [
        {"scheme": "1RM test", "intensity": "trabajo hasta max", "rest": "3-5 min", "description": "Test de 1RM: series de calentamiento (5-3-2-1-1) subiendo peso progresivamente hasta tu máximo del día. Descanso: {rest}"},
    ],
    TrainingPhase.DELOAD: [
        {"scheme": "3x5", "intensity": "50-60%", "rest": "2 min", "description": "3x5 al {intensity}. Trabajo ligero, foco en movilidad y posiciones. Descanso: {rest}"},
    ],
}

# Warm-up components
WARMUP_GENERAL = [
    "2 min de movilidad articular (cuello, hombros, caderas, tobillos)",
    "200m trote suave o 1 min de saltos",
    "10 shoulder pass-throughs con PVC/banda",
    "10 hip circles por lado",
    "10 cat-cow stretches",
    "2 rondas: 5 inchworms + 10 air squats + 5 push-ups",
]

WARMUP_BY_CATEGORY = {
    MovementCategory.MONOSTRUCTURAL: [
        "3 min de cardio progresivo (empezar suave, subir ritmo)",
        "Drills de técnica de carrera: high knees, butt kicks, skipping",
    ],
    MovementCategory.GYMNASTICS: [
        "30s dead hang + 30s support hold (o escápulas activas)",
        "10 scap pull-ups o scap push-ups",
        "5 kip swings (si hay barra)",
        "3x5 strict press con peso ligero para activar hombros",
    ],
    MovementCategory.WEIGHTLIFTING: [
        "Barbell warm-up: 5 deadlifts + 5 front squats + 5 press + 5 push press (barra vacía)",
        "3 series de 3 reps del movimiento principal subiendo peso gradualmente",
        "Burgener warm-up (si hay snatch/clean): down-under + muscle snatch/clean + tall snatch/clean",
    ],
}

COOLDOWN_TEMPLATES = [
    "3-5 min de movilidad: 1 min pigeon stretch por lado + 1 min couch stretch por lado + 1 min child's pose",
    "Foam rolling 5 min: cuádriceps, glúteos, dorsal. 1 min estiramiento de hombros por lado",
    "3 min caminata + 2 min estiramientos: isquiotibiales, flexores de cadera, pecho contra pared",
    "5 min yoga flow: down dog → cobra → pigeon → forward fold. Respiración diafragmática",
]

# Intensity multipliers for volume
INTENSITY_VOLUME_FACTOR = {
    "low": 0.65,
    "moderate": 0.85,
    "high": 1.0,
    "max": 1.1,
}

# Day-level modality targets for a week (ensures balance)
WEEK_MODALITY_TEMPLATES = {
    3: [  # 3 training days
        ["gymnastics", "weightlifting"],         # Day 1: G+W
        ["monostructural", "gymnastics"],         # Day 2: M+G
        ["monostructural", "weightlifting", "gymnastics"],  # Day 3: M+G+W
    ],
    4: [
        ["weightlifting"],                        # Day 1: W (strength focus)
        ["monostructural", "gymnastics"],         # Day 2: M+G
        ["gymnastics", "weightlifting"],           # Day 3: G+W
        ["monostructural", "weightlifting", "gymnastics"],  # Day 4: M+G+W
    ],
    5: [
        ["weightlifting"],                        # Day 1: W (strength)
        ["monostructural", "gymnastics"],         # Day 2: M+G
        ["gymnastics", "weightlifting"],           # Day 3: G+W
        ["monostructural"],                       # Day 4: M (conditioning)
        ["monostructural", "weightlifting", "gymnastics"],  # Day 5: M+G+W
    ],
    6: [
        ["weightlifting"],                        # Day 1: W
        ["monostructural", "gymnastics"],         # Day 2: M+G
        ["gymnastics", "weightlifting"],           # Day 3: G+W
        ["monostructural"],                       # Day 4: M
        ["monostructural", "weightlifting", "gymnastics"],  # Day 5: M+G+W
        ["gymnastics"],                           # Day 6: G (skill)
    ],
}

# Time domain rotation per week
TIME_DOMAIN_ROTATION = {
    3: ["medium", "short", "long"],
    4: ["medium", "short", "long", "medium"],
    5: ["medium", "short", "long", "short", "medium"],
    6: ["medium", "short", "long", "short", "medium", "long"],
}

# Workout type rotation
WORKOUT_TYPE_ROTATION = {
    3: [WorkoutType.FOR_TIME, WorkoutType.AMRAP, WorkoutType.EMOM],
    4: [WorkoutType.FOR_TIME, WorkoutType.AMRAP, WorkoutType.EMOM, WorkoutType.FOR_TIME],
    5: [WorkoutType.FOR_TIME, WorkoutType.AMRAP, WorkoutType.EMOM, WorkoutType.TABATA, WorkoutType.CHIPPER],
    6: [WorkoutType.FOR_TIME, WorkoutType.AMRAP, WorkoutType.EMOM, WorkoutType.TABATA, WorkoutType.FOR_TIME, WorkoutType.LADDER],
}

# Strength movement categories
STRENGTH_MOVEMENTS = {
    "squat": ["Back Squat", "Front Squat", "Overhead Squat", "Goblet Squat"],
    "press": ["Press (Shoulder Press)", "Push Press", "Push Jerk"],
    "hinge": ["Deadlift"],
    "olympic": ["Clean (Power)", "Clean (Squat)", "Snatch (Power)", "Snatch (Squat)", "Clean & Jerk"],
}

# Days of the week in Spanish
DAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _seed_for_date(d: date, salt: str = "") -> int:
    """Create a deterministic seed from a date so the same day gives the same workout."""
    h = hashlib.md5(f"{d.isoformat()}{salt}".encode()).hexdigest()
    return int(h[:8], 16)


def _get_available_movements(equipment: list[str], level: FitnessLevel) -> list[dict]:
    """Filter movements by available equipment and skill level."""
    max_difficulty = {
        FitnessLevel.BEGINNER: 4,
        FitnessLevel.INTERMEDIATE: 6,
        FitnessLevel.ADVANCED: 8,
        FitnessLevel.ELITE: 10,
    }[level]

    available = []
    for mov in MOVEMENTS:
        needed = mov["equipment_needed"].split(",")
        if all(eq.strip() in equipment or eq.strip() == "none" for eq in needed):
            if mov["difficulty"] <= max_difficulty:
                available.append(mov)
    return available


# Default Rx weights (kg) for WOD context by level
_RX_WEIGHTS = {
    # movement_name: {level: (male_kg, female_kg)} - we use a single value for simplicity
    "Back Squat": {FitnessLevel.BEGINNER: 30, FitnessLevel.INTERMEDIATE: 50, FitnessLevel.ADVANCED: 80, FitnessLevel.ELITE: 100},
    "Front Squat": {FitnessLevel.BEGINNER: 25, FitnessLevel.INTERMEDIATE: 43, FitnessLevel.ADVANCED: 70, FitnessLevel.ELITE: 90},
    "Overhead Squat": {FitnessLevel.BEGINNER: 20, FitnessLevel.INTERMEDIATE: 35, FitnessLevel.ADVANCED: 52, FitnessLevel.ELITE: 70},
    "Deadlift": {FitnessLevel.BEGINNER: 40, FitnessLevel.INTERMEDIATE: 60, FitnessLevel.ADVANCED: 100, FitnessLevel.ELITE: 120},
    "Press (Shoulder Press)": {FitnessLevel.BEGINNER: 15, FitnessLevel.INTERMEDIATE: 25, FitnessLevel.ADVANCED: 40, FitnessLevel.ELITE: 55},
    "Push Press": {FitnessLevel.BEGINNER: 20, FitnessLevel.INTERMEDIATE: 30, FitnessLevel.ADVANCED: 50, FitnessLevel.ELITE: 65},
    "Push Jerk": {FitnessLevel.BEGINNER: 20, FitnessLevel.INTERMEDIATE: 35, FitnessLevel.ADVANCED: 52, FitnessLevel.ELITE: 70},
    "Clean (Power)": {FitnessLevel.BEGINNER: 25, FitnessLevel.INTERMEDIATE: 40, FitnessLevel.ADVANCED: 60, FitnessLevel.ELITE: 80},
    "Clean (Squat)": {FitnessLevel.BEGINNER: 25, FitnessLevel.INTERMEDIATE: 40, FitnessLevel.ADVANCED: 65, FitnessLevel.ELITE: 85},
    "Snatch (Power)": {FitnessLevel.BEGINNER: 15, FitnessLevel.INTERMEDIATE: 30, FitnessLevel.ADVANCED: 45, FitnessLevel.ELITE: 65},
    "Snatch (Squat)": {FitnessLevel.BEGINNER: 15, FitnessLevel.INTERMEDIATE: 30, FitnessLevel.ADVANCED: 48, FitnessLevel.ELITE: 70},
    "Thruster": {FitnessLevel.BEGINNER: 20, FitnessLevel.INTERMEDIATE: 35, FitnessLevel.ADVANCED: 52, FitnessLevel.ELITE: 70},
    "Sumo Deadlift High Pull": {FitnessLevel.BEGINNER: 20, FitnessLevel.INTERMEDIATE: 30, FitnessLevel.ADVANCED: 45, FitnessLevel.ELITE: 55},
    "Clean & Jerk": {FitnessLevel.BEGINNER: 25, FitnessLevel.INTERMEDIATE: 40, FitnessLevel.ADVANCED: 60, FitnessLevel.ELITE: 85},
    "Cluster": {FitnessLevel.BEGINNER: 20, FitnessLevel.INTERMEDIATE: 35, FitnessLevel.ADVANCED: 52, FitnessLevel.ELITE: 70},
    "KB Swing": {FitnessLevel.BEGINNER: 12, FitnessLevel.INTERMEDIATE: 16, FitnessLevel.ADVANCED: 24, FitnessLevel.ELITE: 32},
    "Wall Ball Shots": {FitnessLevel.BEGINNER: 4, FitnessLevel.INTERMEDIATE: 6, FitnessLevel.ADVANCED: 9, FitnessLevel.ELITE: 9},
    "DB Snatch": {FitnessLevel.BEGINNER: 10, FitnessLevel.INTERMEDIATE: 15, FitnessLevel.ADVANCED: 22, FitnessLevel.ELITE: 30},
}

# Intensity multipliers for WOD weight vs max capacity
_WOD_INTENSITY_FACTOR = {
    "low": 0.55,
    "moderate": 0.65,
    "high": 0.75,
    "max_effort": 0.85,
}


def _get_weight_for_movement(
    mov: dict,
    level: FitnessLevel,
    equipment_details: dict,
    intensity: str,
) -> str | None:
    """Get a weight prescription for a movement based on equipment and level."""
    if mov["category"] != MovementCategory.WEIGHTLIFTING:
        return None

    name = mov["name"]
    base_weight = _RX_WEIGHTS.get(name, {}).get(level)
    if base_weight is None:
        return None

    # Check if user has weight limits from equipment_details
    max_available = None
    eq_needed = mov["equipment_needed"].split(",")
    for eq in eq_needed:
        eq = eq.strip()
        if eq in equipment_details:
            detail = equipment_details[eq]
            # Try to extract max weight from details like "barra 20kg + discos hasta 100kg"
            import re
            numbers = re.findall(r'(\d+)\s*kg', detail)
            if numbers:
                max_available = max(int(n) for n in numbers)

    # Apply intensity factor for WOD context
    factor = _WOD_INTENSITY_FACTOR.get(intensity, 0.65)
    suggested = int(base_weight * factor)

    # Cap at available weight
    if max_available is not None and suggested > max_available:
        suggested = max_available

    # Round to nearest 2.5
    suggested = round(suggested / 2.5) * 2.5
    if suggested < 5:
        suggested = 5

    # Format nicely
    if suggested == int(suggested):
        return f"{int(suggested)}kg"
    return f"{suggested}kg"


def _inject_weights(
    text: str,
    movements: list[dict],
    level: FitnessLevel,
    equipment_details: dict,
    intensity: str,
) -> str:
    """Inject weight prescriptions into WOD/strength text for weightlifting movements."""
    for mov in movements:
        weight = _get_weight_for_movement(mov, level, equipment_details, intensity)
        if weight and mov["name"] in text:
            # Append weight after movement name (e.g., "- 15 Thruster" -> "- 15 Thruster (52kg)")
            # Only if weight isn't already mentioned
            if "kg" not in text.split(mov["name"])[0].split("\n")[-1]:
                text = text.replace(mov["name"], f"{mov['name']} ({weight})")
    return text


def _pick_movements(
    available: list[dict],
    target_modalities: list[str],
    count: int,
    rng: random.Random,
    exclude: list[str] | None = None,
) -> list[dict]:
    """Pick movements matching target modalities, ensuring variety."""
    exclude = exclude or []
    candidates = [
        m for m in available
        if m["category"].value in target_modalities and m["name"] not in exclude
    ]

    if not candidates:
        candidates = [m for m in available if m["name"] not in exclude]

    if len(candidates) <= count:
        return candidates

    # Try to pick from different modalities
    picked = []
    for mod in target_modalities:
        mod_candidates = [m for m in candidates if m["category"].value == mod and m not in picked]
        if mod_candidates:
            picked.append(rng.choice(mod_candidates))

    # Fill remaining
    remaining = [m for m in candidates if m not in picked]
    while len(picked) < count and remaining:
        choice = rng.choice(remaining)
        remaining.remove(choice)
        picked.append(choice)

    return picked[:count]


def _build_warmup(movements: list[dict], rng: random.Random) -> str:
    """Generate warm-up specific to the workout movements."""
    parts = []

    # Always start with general
    general = rng.sample(WARMUP_GENERAL, min(3, len(WARMUP_GENERAL)))
    parts.extend(general)

    # Add category-specific
    categories_used = set(m["category"] for m in movements)
    for cat in categories_used:
        specific = WARMUP_BY_CATEGORY.get(cat, [])
        if specific:
            parts.append(rng.choice(specific))

    # Add specific movement prep
    for mov in movements[:2]:
        parts.append(f"5 reps de {mov['name']} con peso ligero o sin peso (activación)")

    return "\n".join(f"- {p}" for p in parts)


def _build_strength(
    available: list[dict],
    phase: TrainingPhase,
    focus: str,
    rng: random.Random,
    benchmarks: dict | None = None,
) -> str | None:
    """Build strength/skill portion based on phase and focus."""
    templates = STRENGTH_TEMPLATES.get(phase, STRENGTH_TEMPLATES[TrainingPhase.FOUNDATION])
    template = rng.choice(templates)

    # Pick a strength movement based on focus
    focus_lower = focus.lower()
    strength_category = "squat"  # default
    for cat, keywords in [("squat", ["squat", "sentadilla"]), ("press", ["press", "push", "empuje"]),
                          ("hinge", ["hinge", "deadlift", "peso muerto"]), ("olympic", ["olympic", "clean", "snatch", "arranque", "cargada"])]:
        if any(kw in focus_lower for kw in keywords):
            strength_category = cat
            break

    # Find available movement in that category
    strength_names = STRENGTH_MOVEMENTS.get(strength_category, STRENGTH_MOVEMENTS["squat"])
    chosen = None
    for name in strength_names:
        for mov in available:
            if mov["name"] == name:
                chosen = mov
                break
        if chosen:
            break

    if not chosen:
        # Fallback: any weightlifting movement
        wl_movs = [m for m in available if m["category"] == MovementCategory.WEIGHTLIFTING]
        if wl_movs:
            chosen = rng.choice(wl_movs)
        else:
            return None

    desc = template["description"].format(intensity=template["intensity"], rest=template["rest"])
    result = f"{chosen['name']}: {desc}"

    # Add benchmark reference if available
    bm_key = f"{chosen['name']} 1RM"
    if benchmarks and bm_key in benchmarks:
        result += f"\n(Tu 1RM registrado: {benchmarks[bm_key]})"

    return result


def _build_wod(
    movements: list[dict],
    wod_type: WorkoutType,
    time_domain: str,
    intensity: str,
    rng: random.Random,
) -> str:
    """Build the WOD description."""
    vol_factor = INTENSITY_VOLUME_FACTOR.get(intensity, 0.85)

    if wod_type == WorkoutType.AMRAP:
        return _build_amrap(movements, time_domain, vol_factor, rng)
    elif wod_type == WorkoutType.FOR_TIME:
        return _build_for_time(movements, time_domain, vol_factor, rng)
    elif wod_type == WorkoutType.EMOM:
        return _build_emom(movements, time_domain, vol_factor, rng)
    elif wod_type == WorkoutType.TABATA:
        return _build_tabata(movements, time_domain, rng)
    elif wod_type == WorkoutType.CHIPPER:
        return _build_chipper(movements, time_domain, vol_factor, rng)
    elif wod_type == WorkoutType.LADDER:
        return _build_ladder(movements, time_domain, rng)
    else:
        return _build_for_time(movements, time_domain, vol_factor, rng)


def _build_amrap(movements: list[dict], time_domain: str, vol_factor: float, rng: random.Random) -> str:
    config = REP_SCHEMES[WorkoutType.AMRAP].get(time_domain, REP_SCHEMES[WorkoutType.AMRAP]["medium"])
    minutes = rng.choice(config["minutes"])
    low, high = config["reps_range"]

    lines = [f"AMRAP {minutes} minutos:"]
    for mov in movements:
        reps = rng.choice(range(low, high + 1, max(1, (high - low) // 4)))
        reps = max(3, int(reps * vol_factor))
        if mov["category"] == MovementCategory.MONOSTRUCTURAL:
            if "run" in mov["name"].lower():
                lines.append(f"- {rng.choice([200, 400])}m {mov['name']}")
            elif "row" in mov["name"].lower() or "bike" in mov["name"].lower():
                lines.append(f"- {rng.choice([12, 15, 20])} cal {mov['name']}")
            else:
                lines.append(f"- {reps * 2} {mov['name']}")
        else:
            lines.append(f"- {reps} {mov['name']}")

    return "\n".join(lines)


def _build_for_time(movements: list[dict], time_domain: str, vol_factor: float, rng: random.Random) -> str:
    config = REP_SCHEMES[WorkoutType.FOR_TIME].get(time_domain, REP_SCHEMES[WorkoutType.FOR_TIME]["medium"])
    rounds = rng.choice(config["rounds"])
    low, high = config["reps_range"]

    # Classic descending rep scheme for short/medium
    use_descending = rng.random() > 0.5 and len(movements) <= 3 and time_domain != "long"

    if use_descending:
        scheme = rng.choice(["21-15-9", "15-12-9", "10-8-6", "15-9-6"])
        lines = [f"For Time ({scheme}):"]
        for mov in movements:
            if mov["category"] == MovementCategory.MONOSTRUCTURAL and "run" in mov["name"].lower():
                lines.append(f"- {rng.choice([200, 400])}m {mov['name']}")
            else:
                lines.append(f"- {mov['name']}")
    else:
        lines = [f"For Time - {rounds} rondas:"]
        for mov in movements:
            reps = rng.choice(range(low, high + 1, max(1, (high - low) // 4)))
            reps = max(3, int(reps * vol_factor))
            if mov["category"] == MovementCategory.MONOSTRUCTURAL:
                if "run" in mov["name"].lower():
                    lines.append(f"- {rng.choice([200, 400])}m {mov['name']}")
                elif "row" in mov["name"].lower() or "bike" in mov["name"].lower():
                    lines.append(f"- {rng.choice([12, 15, 20])} cal {mov['name']}")
                else:
                    lines.append(f"- {reps * 2} {mov['name']}")
            else:
                lines.append(f"- {reps} {mov['name']}")

    return "\n".join(lines)


def _build_emom(movements: list[dict], time_domain: str, vol_factor: float, rng: random.Random) -> str:
    config = REP_SCHEMES[WorkoutType.EMOM].get(time_domain, REP_SCHEMES[WorkoutType.EMOM]["medium"])
    minutes = rng.choice(config["minutes"])
    low, high = config["reps_range"]

    if len(movements) == 1:
        reps = rng.choice(range(low, high + 1))
        reps = max(2, int(reps * vol_factor))
        return f"EMOM {minutes} minutos:\n- {reps} {movements[0]['name']} cada minuto"

    lines = [f"EMOM {minutes} minutos (alternando):"]
    for i, mov in enumerate(movements):
        reps = rng.choice(range(low, high + 1))
        reps = max(2, int(reps * vol_factor))
        minute_label = f"Min {i + 1}" if len(movements) <= 3 else f"Min {i + 1}"
        if mov["category"] == MovementCategory.MONOSTRUCTURAL:
            if "run" in mov["name"].lower():
                lines.append(f"- {minute_label}: {rng.choice([100, 200])}m {mov['name']}")
            elif "row" in mov["name"].lower() or "bike" in mov["name"].lower():
                lines.append(f"- {minute_label}: {rng.choice([10, 12, 15])} cal {mov['name']}")
            else:
                lines.append(f"- {minute_label}: {reps * 2} {mov['name']}")
        else:
            lines.append(f"- {minute_label}: {reps} {mov['name']}")

    return "\n".join(lines)


def _build_tabata(movements: list[dict], time_domain: str, rng: random.Random) -> str:
    config = REP_SCHEMES[WorkoutType.TABATA].get(time_domain, REP_SCHEMES[WorkoutType.TABATA]["short"])
    rounds = rng.choice(config["rounds"])

    lines = [f"Tabata - {rounds} rondas por ejercicio (20s trabajo / 10s descanso):"]
    for mov in movements:
        lines.append(f"- {mov['name']}")
    lines.append(f"\n1 min descanso entre ejercicios. Total: ~{len(movements) * (rounds * 0.5 + 1):.0f} min")

    return "\n".join(lines)


def _build_chipper(movements: list[dict], time_domain: str, vol_factor: float, rng: random.Random) -> str:
    td = time_domain if time_domain in ("medium", "long") else "medium"
    config = REP_SCHEMES[WorkoutType.CHIPPER].get(td, REP_SCHEMES[WorkoutType.CHIPPER]["medium"])
    low, high = config["reps_range"]

    lines = ["For Time (Chipper - una pasada):"]
    for mov in movements:
        reps = rng.choice(range(low, high + 1, 5))
        reps = max(5, int(reps * vol_factor))
        if mov["category"] == MovementCategory.MONOSTRUCTURAL:
            if "run" in mov["name"].lower():
                lines.append(f"- {rng.choice([400, 800])}m {mov['name']}")
            elif "row" in mov["name"].lower() or "bike" in mov["name"].lower():
                lines.append(f"- {rng.choice([20, 25, 30])} cal {mov['name']}")
            else:
                lines.append(f"- {reps * 2} {mov['name']}")
        else:
            lines.append(f"- {reps} {mov['name']}")

    return "\n".join(lines)


def _build_ladder(movements: list[dict], time_domain: str, rng: random.Random) -> str:
    td = time_domain if time_domain in ("short", "medium") else "medium"
    config = REP_SCHEMES[WorkoutType.LADDER].get(td, REP_SCHEMES[WorkoutType.LADDER]["medium"])

    start = config["start"]
    inc = config["increment"]
    rounds = config["rounds"]
    reps_list = [start + i * inc for i in range(rounds)]

    lines = [f"For Time - Escalera ascendente ({'-'.join(str(r) for r in reps_list)}):"]
    for mov in movements[:2]:
        lines.append(f"- {mov['name']}")

    return "\n".join(lines)


def _build_scaling(movements: list[dict], level: FitnessLevel) -> str:
    """Build scaling notes for the workout."""
    lines = []
    for mov in movements:
        scaling = mov.get("scaling_options", "")
        if scaling:
            lines.append(f"- {mov['name']}: {scaling}")

    if level == FitnessLevel.BEGINNER:
        lines.append("- Reduce el volumen un 30% si es necesario. Prioriza movimiento correcto sobre velocidad")
    elif level == FitnessLevel.INTERMEDIATE:
        lines.append("- Usa peso que permita mantener buena técnica durante todo el WOD")
    elif level in (FitnessLevel.ADVANCED, FitnessLevel.ELITE):
        lines.append("- Para subir: añade peso o usa la versión más difícil del movimiento")

    return "\n".join(lines)


def _build_coaches_notes(
    movements: list[dict],
    wod_type: WorkoutType,
    time_domain: str,
    phase: str,
    intensity: str,
) -> str:
    """Build coach's notes explaining stimulus and intent."""
    modalities = list(set(m["category"].value for m in movements))
    modality_str = " + ".join(m.capitalize() for m in modalities)

    stimulus = {
        "short": "potencia y velocidad. Busca máximo esfuerzo en poco tiempo. No dosifiques, ve fuerte desde el inicio",
        "medium": "capacidad de trabajo. Mantén un ritmo sostenible pero incómodo. Intenta no romper los sets largos",
        "long": "resistencia y gestión del esfuerzo. El ritmo es clave: empieza conservador y sube si te ves bien al final",
    }

    phase_note = {
        "foundation": "Fase de base: prioriza la técnica sobre la velocidad. Cada repetición debe ser limpia",
        "accumulation": "Fase de acumulación: el volumen es el estímulo principal. Intenta completar todo el trabajo",
        "intensification": "Fase de intensificación: el objetivo es la intensidad. Empuja tus límites de forma inteligente",
        "realization": "Semana de test: da tu máximo esfuerzo. Es momento de ver tu progreso",
        "deload": "Semana de descarga: mantén el movimiento activo pero sin forzar. RPE objetivo: 5-6/10",
    }

    parts = [
        f"Estímulo: {stimulus.get(time_domain, stimulus['medium'])}.",
        f"Modalidades: {modality_str}.",
        f"Tipo: {wod_type.value.upper()} - dominio de tiempo {time_domain}.",
        phase_note.get(phase, ""),
        f"Intensidad objetivo: {intensity}.",
    ]

    return " ".join(p for p in parts if p)


def generate_workout(
    athlete_profile: dict,
    training_context: dict,
) -> WorkoutResponse:
    """Generate a single workout adapted to athlete, equipment, and training phase."""
    equipment = athlete_profile["equipment"]
    level = FitnessLevel(athlete_profile["level"])
    phase = training_context.get("phase", "foundation")
    intensity = training_context.get("target_intensity", "moderate")
    focus = training_context.get("focus", "General fitness")
    day_of_week = training_context.get("day_of_week", "Lunes")

    # Deterministic randomness based on date
    today = date.today()
    rng = random.Random(_seed_for_date(today, athlete_profile.get("name", "")))

    available = _get_available_movements(equipment, level)
    if not available:
        return WorkoutResponse(
            warmup="Movilidad general: 10 min",
            wod="No hay movimientos disponibles con tu equipamiento y nivel. Añade más equipamiento o ajusta tu nivel.",
            wod_type=WorkoutType.AMRAP,
            target_time_domain="medium",
            modalities=[],
            scaling_notes="N/A",
            cooldown="Estiramientos generales: 5 min",
            coaches_notes="Revisa tu equipamiento en el perfil.",
        )

    # Determine modality target based on focus and recent history
    recent_mods_str = training_context.get("recent_modalities", "None")
    all_modalities = ["monostructural", "gymnastics", "weightlifting"]

    # Try to balance: pick least-used modalities or from focus
    target_modalities = _parse_modalities_from_focus(focus, all_modalities, rng)

    # Pick time domain avoiding recent ones
    recent_types_str = training_context.get("recent_workout_types", "None")
    time_domain = rng.choice(["short", "medium", "long"])

    # Adjust for phase
    if phase == "deload":
        time_domain = rng.choice(["short", "medium"])
        intensity = "low"
    elif phase == "intensification":
        time_domain = rng.choice(["short", "medium"])

    # Pick workout type
    available_types = [WorkoutType.AMRAP, WorkoutType.FOR_TIME, WorkoutType.EMOM]
    if time_domain != "short":
        available_types.append(WorkoutType.CHIPPER)
    if time_domain in ("short", "medium"):
        available_types.append(WorkoutType.TABATA)
        available_types.append(WorkoutType.LADDER)

    wod_type = rng.choice(available_types)

    # Handle time constraint
    available_minutes = athlete_profile.get("available_minutes", athlete_profile.get("session_duration_minutes", 60))
    if available_minutes <= 30:
        time_domain = "short"
    elif available_minutes <= 45:
        time_domain = rng.choice(["short", "medium"])

    # Pick movements
    exclude = training_context.get("exclude_movements", [])
    num_movements = {
        "short": rng.choice([2, 3]),
        "medium": rng.choice([3, 4]),
        "long": rng.choice([3, 4, 5]),
    }[time_domain]

    wod_movements = _pick_movements(available, target_modalities, num_movements, rng, exclude)

    # Build strength portion (not on deload short days)
    phase_enum = TrainingPhase(phase)
    strength = None
    has_time_for_strength = available_minutes >= 45
    wl_available = [m for m in available if m["category"] == MovementCategory.WEIGHTLIFTING]
    if has_time_for_strength and wl_available and phase != "deload":
        strength = _build_strength(
            available, phase_enum, focus, rng,
            training_context.get("benchmarks"),
        )

    equipment_details = athlete_profile.get("equipment_details", {})

    warmup = _build_warmup(wod_movements, rng)
    wod = _build_wod(wod_movements, wod_type, time_domain, intensity, rng)

    # Inject weight prescriptions into the WOD text
    wod = _inject_weights(wod, wod_movements, level, equipment_details, intensity)

    # Also add weight to strength portion
    if strength:
        strength = _inject_weights(strength, wl_available, level, equipment_details, "moderate")

    scaling = _build_scaling(wod_movements, level)
    cooldown = rng.choice(COOLDOWN_TEMPLATES)
    modalities = list(set(m["category"].value for m in wod_movements))
    coaches_notes = _build_coaches_notes(wod_movements, wod_type, time_domain, phase, intensity)

    return WorkoutResponse(
        warmup=warmup,
        strength_or_skill=strength,
        wod=wod,
        wod_type=wod_type,
        target_time_domain=time_domain,
        modalities=modalities,
        scaling_notes=scaling,
        cooldown=cooldown,
        coaches_notes=coaches_notes,
    )


def generate_week_plan(
    athlete_profile: dict,
    training_context: dict,
) -> WeekPlanResponse:
    """Generate a full week training plan."""
    equipment = athlete_profile["equipment"]
    level = FitnessLevel(athlete_profile["level"])
    phase = training_context.get("phase", "foundation")
    intensity = training_context.get("target_intensity", "moderate")
    focus = training_context.get("focus", "General fitness")
    week_number = training_context.get("week_number", 1)
    training_days = athlete_profile.get("training_days_per_week", 3)
    available_minutes = athlete_profile.get("session_duration_minutes", 60)

    today = date.today()
    rng = random.Random(_seed_for_date(today, f"week{week_number}"))

    available = _get_available_movements(equipment, level)

    # Determine which days are training vs rest
    clamped_days = max(3, min(training_days, 6))
    modality_schedule = WEEK_MODALITY_TEMPLATES.get(clamped_days, WEEK_MODALITY_TEMPLATES[3])
    time_domains = TIME_DOMAIN_ROTATION.get(clamped_days, TIME_DOMAIN_ROTATION[3])
    wod_types = WORKOUT_TYPE_ROTATION.get(clamped_days, WORKOUT_TYPE_ROTATION[3])

    # Distribute training days across the week
    if clamped_days <= 3:
        training_day_indices = [0, 2, 4][:clamped_days]  # Mon, Wed, Fri
    elif clamped_days == 4:
        training_day_indices = [0, 1, 3, 4]  # Mon, Tue, Thu, Fri
    elif clamped_days == 5:
        training_day_indices = [0, 1, 2, 3, 4]  # Mon-Fri
    else:
        training_day_indices = [0, 1, 2, 3, 4, 5]  # Mon-Sat

    days: list[DayPlan] = []
    training_day_counter = 0

    for day_idx in range(7):
        day_name = DAYS_ES[day_idx]

        if day_idx not in training_day_indices:
            days.append(DayPlan(day=day_name, rest_day=True, workout=None))
            continue

        # Training day
        sched_idx = training_day_counter % len(modality_schedule)
        target_mods = modality_schedule[sched_idx]
        td = time_domains[training_day_counter % len(time_domains)]
        wt = wod_types[training_day_counter % len(wod_types)]

        # Deload adjustments
        day_intensity = intensity
        if phase == "deload":
            td = rng.choice(["short", "medium"])
            day_intensity = "low"

        if available_minutes <= 30:
            td = "short"
        elif available_minutes <= 45:
            td = rng.choice(["short", "medium"])

        # Pick movements
        num_mov = {"short": rng.choice([2, 3]), "medium": rng.choice([3, 4]), "long": rng.choice([3, 4, 5])}[td]
        wod_movements = _pick_movements(available, target_mods, num_mov, rng)

        # Strength on first 1-2 days of the week
        phase_enum = TrainingPhase(phase)
        strength = None
        wl_available = [m for m in available if m["category"] == MovementCategory.WEIGHTLIFTING]
        if training_day_counter < 2 and available_minutes >= 45 and wl_available and phase != "deload":
            strength = _build_strength(available, phase_enum, focus, rng, training_context.get("benchmarks"))

        equipment_details = athlete_profile.get("equipment_details", {})

        warmup = _build_warmup(wod_movements, rng)
        wod = _build_wod(wod_movements, wt, td, day_intensity, rng)
        wod = _inject_weights(wod, wod_movements, level, equipment_details, day_intensity)
        if strength:
            strength = _inject_weights(strength, wl_available, level, equipment_details, "moderate")
        scaling = _build_scaling(wod_movements, level)
        cooldown = rng.choice(COOLDOWN_TEMPLATES)
        modalities = list(set(m["category"].value for m in wod_movements))
        coaches_notes = _build_coaches_notes(wod_movements, wt, td, phase, day_intensity)

        workout = WorkoutResponse(
            warmup=warmup,
            strength_or_skill=strength,
            wod=wod,
            wod_type=wt,
            target_time_domain=td,
            modalities=modalities,
            scaling_notes=scaling,
            cooldown=cooldown,
            coaches_notes=coaches_notes,
        )

        days.append(DayPlan(day=day_name, rest_day=False, workout=workout))
        training_day_counter += 1

    # Programming notes
    mod_counts = {"M": 0, "G": 0, "W": 0}
    td_counts = {"short": 0, "medium": 0, "long": 0}
    for day in days:
        if day.workout:
            for m in day.workout.modalities:
                if m == "monostructural":
                    mod_counts["M"] += 1
                elif m == "gymnastics":
                    mod_counts["G"] += 1
                elif m == "weightlifting":
                    mod_counts["W"] += 1
            td_counts[day.workout.target_time_domain] += 1

    phase_notes = {
        "foundation": "Semana de base: foco en mecánica correcta y desarrollo de capacidad aeróbica.",
        "accumulation": "Semana de acumulación: volumen aumentado para construir capacidad de trabajo.",
        "intensification": "Semana de intensificación: menos volumen, más carga. Preparando para test.",
        "realization": "Semana de test: momento de medir progreso con los benchmarks.",
        "deload": "Semana de descarga: recuperación activa. Volumen y carga reducidos un 40-50%.",
    }

    notes = (
        f"{phase_notes.get(phase, '')} "
        f"Distribución de modalidades: M={mod_counts['M']}, G={mod_counts['G']}, W={mod_counts['W']}. "
        f"Dominios de tiempo: corto={td_counts['short']}, medio={td_counts['medium']}, largo={td_counts['long']}. "
        f"Foco de la semana: {focus}."
    )

    return WeekPlanResponse(
        week_number=week_number,
        phase=phase,
        focus=focus,
        days=days,
        programming_notes=notes,
    )


def generate_adaptation_feedback(
    workout_log: dict,
    recent_logs: list[dict],
) -> str:
    """Analyze workout feedback and provide rule-based adaptation recommendations."""
    rpe = workout_log.get("rpe")
    sleep = workout_log.get("sleep_quality")
    energy = workout_log.get("energy_level")
    soreness = workout_log.get("muscle_soreness")
    went_rx = workout_log.get("went_rx", False)

    feedback_parts = []

    # RPE assessment
    if rpe is not None:
        if rpe <= 4:
            feedback_parts.append("RPE bajo: el entrenamiento fue ligero. Puedes aumentar la intensidad o el peso en la próxima sesión.")
        elif rpe <= 6:
            feedback_parts.append("RPE moderado: buen nivel de esfuerzo para la mayoría de sesiones de entrenamiento.")
        elif rpe <= 8:
            feedback_parts.append("RPE alto: sesión exigente. Asegúrate de recuperar bien antes de la próxima sesión intensa.")
        else:
            feedback_parts.append("RPE muy alto: esfuerzo máximo. Próxima sesión debería ser de menor intensidad para recuperar.")

    # Recovery signals
    recovery_score = 0
    if sleep is not None:
        if sleep <= 2:
            feedback_parts.append("Sueño deficiente: prioriza descanso. Reduce intensidad hasta que mejore.")
            recovery_score -= 2
        elif sleep >= 4:
            recovery_score += 1

    if energy is not None:
        if energy <= 2:
            feedback_parts.append("Energía baja pre-entreno: tu cuerpo necesita más recuperación. Considera sesión ligera o descanso activo.")
            recovery_score -= 2
        elif energy >= 4:
            recovery_score += 1

    if soreness:
        feedback_parts.append(f"Agujetas en: {soreness}. Evita cargar esas zonas mañana. Trabaja otras áreas o haz movilidad específica.")
        recovery_score -= 1

    # Rx assessment
    if went_rx:
        feedback_parts.append("Completaste Rx: buen indicador de progreso.")
    else:
        feedback_parts.append("Escalado: sigue trabajando con la versión escalada hasta dominarla consistentemente.")

    # Trend analysis
    if recent_logs and len(recent_logs) >= 3:
        recent_rpes = [l.get("rpe") for l in recent_logs if l.get("rpe") is not None]
        if recent_rpes:
            avg = sum(recent_rpes) / len(recent_rpes)
            if avg > 8:
                feedback_parts.append("ALERTA: tu RPE promedio reciente es muy alto (>{:.1f}). Señales de fatiga acumulada. Reduce carga los próximos 2-3 días.".format(avg))
            elif avg < 4:
                feedback_parts.append("Tu RPE promedio es bajo ({:.1f}). Puedes subir la intensidad general de tus entrenamientos.".format(avg))

    # Next session recommendation
    if recovery_score <= -3:
        feedback_parts.append("Recomendación: día de descanso activo o movilidad mañana.")
    elif recovery_score <= -1:
        feedback_parts.append("Recomendación: sesión de intensidad baja-moderada mañana.")
    else:
        feedback_parts.append("Recomendación: puedes entrenar con normalidad mañana.")

    return " ".join(feedback_parts)


def generate_progress_assessment(
    athlete_profile: dict,
    progress_data: dict,
) -> str:
    """Generate rule-based progress assessment."""
    total = progress_data.get("total_workouts", 0)
    phase = progress_data.get("phase", "foundation")
    avg_rpe = progress_data.get("avg_rpe")
    mod_dist = progress_data.get("modality_distribution", {})
    benchmarks = progress_data.get("benchmarks", {})

    parts = []

    # Volume assessment
    if total == 0:
        parts.append("Aún no hay entrenamientos registrados. Empieza con el comando 'cfc workout' para generar tu primera sesión.")
        return " ".join(parts)
    elif total < 10:
        parts.append(f"Llevas {total} entrenamientos. Estás empezando: foco en aprender los movimientos y crear el hábito.")
    elif total < 30:
        parts.append(f"{total} entrenamientos completados. Buena consistencia. Ya puedes empezar a medir benchmarks si no lo has hecho.")
    else:
        parts.append(f"{total} entrenamientos completados. Tienes una base sólida de entrenamiento.")

    # Phase context
    phase_advice = {
        "foundation": "Estás en fase de base. Sigue priorizando técnica y no tengas prisa por subir peso.",
        "accumulation": "Fase de acumulación: el volumen está subiendo. Escucha a tu cuerpo y descansa lo necesario.",
        "intensification": "Fase de intensificación: es normal sentir más fatiga. El descanso es parte del entrenamiento.",
        "realization": "Semana de test: es tu momento para brillar. Da lo mejor en los benchmarks.",
        "deload": "Semana de descarga: recupera bien. Volverás más fuerte.",
    }
    parts.append(phase_advice.get(phase, ""))

    # RPE trend
    if avg_rpe is not None:
        if avg_rpe > 8:
            parts.append(f"Tu RPE promedio ({avg_rpe:.1f}) es alto. Podrías estar sobreentrenando. Considera reducir intensidad.")
        elif avg_rpe < 4:
            parts.append(f"Tu RPE promedio ({avg_rpe:.1f}) es bajo. Puedes exigirte más en los entrenamientos.")
        else:
            parts.append(f"Tu RPE promedio ({avg_rpe:.1f}) está en buena zona.")

    # Modality balance
    m = mod_dist.get("monostructural", 0)
    g = mod_dist.get("gymnastics", 0)
    w = mod_dist.get("weightlifting", 0)
    total_mod = m + g + w
    if total_mod > 0:
        imbalances = []
        for name, count in [("Monostructural", m), ("Gymnastics", g), ("Weightlifting", w)]:
            pct = count / total_mod
            if pct < 0.2:
                imbalances.append(f"{name} ({pct:.0%})")
        if imbalances:
            parts.append(f"Modalidades con poca presencia: {', '.join(imbalances)}. Intenta equilibrar en las próximas semanas.")
        else:
            parts.append("Buena distribución de modalidades.")

    # Benchmarks
    if benchmarks:
        parts.append(f"Tienes {len(benchmarks)} benchmarks registrados. Úsalos como referencia para medir progreso.")
    else:
        parts.append("No tienes benchmarks registrados aún. Registra tu primer Fran, Cindy o 1RM para trackear progreso.")

    return " ".join(parts)


def _parse_modalities_from_focus(focus: str, all_mods: list[str], rng: random.Random) -> list[str]:
    """Parse focus string to determine target modalities."""
    focus_lower = focus.lower()

    mapping = {
        "squat": ["weightlifting", "gymnastics"],
        "sentadilla": ["weightlifting", "gymnastics"],
        "press": ["weightlifting"],
        "push": ["weightlifting", "gymnastics"],
        "hinge": ["weightlifting"],
        "deadlift": ["weightlifting"],
        "peso muerto": ["weightlifting"],
        "olympic": ["weightlifting"],
        "clean": ["weightlifting"],
        "snatch": ["weightlifting"],
        "gymnastics": ["gymnastics"],
        "gimnasia": ["gymnastics"],
        "pulling": ["gymnastics"],
        "push-up": ["gymnastics"],
        "cardio": ["monostructural"],
        "monostructural": ["monostructural"],
        "run": ["monostructural"],
        "carrera": ["monostructural"],
        "mixed": all_mods,
    }

    for keyword, mods in mapping.items():
        if keyword in focus_lower:
            return mods

    # Default: pick 2-3 modalities for variety
    return rng.sample(all_mods, rng.choice([2, 3]))

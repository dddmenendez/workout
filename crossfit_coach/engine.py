"""AI-powered workout generation engine using Claude for intelligent programming."""

import json
from datetime import date, timedelta

import anthropic

from crossfit_coach.knowledge import (
    BENCHMARK_WODS,
    EQUIPMENT_CATALOG,
    MOVEMENT_SUBSTITUTIONS,
    MOVEMENTS,
    PROGRAMMING_PRINCIPLES,
)
from crossfit_coach.models import FitnessLevel, TrainingPhase, WorkoutType
from crossfit_coach.schemas import (
    DayPlan,
    ProgressSummary,
    WeekPlanResponse,
    WorkoutLogCreate,
    WorkoutLogResponse,
    WorkoutResponse,
)

SYSTEM_PROMPT = """\
You are an expert CrossFit coach with L1 and L2 certifications. You design training programs \
following CrossFit methodology strictly.

## Core Principles (from L1 & L2 Training Guide):
{principles}

## Available Movements:
{movements}

## Equipment Substitutions (when athlete lacks equipment):
{substitutions}

## Benchmark WODs for reference:
{benchmarks}

## Rules:
1. ONLY use movements the athlete can do with their available equipment
2. Scale movements to the athlete's level (beginner/intermediate/advanced/elite)
3. Follow the current training phase and week focus
4. Vary time domains, modalities, and rep schemes across the week
5. Include warm-up specific to the workout, not generic
6. Always explain the intended STIMULUS of the WOD
7. Keep sessions within the athlete's time limit
8. For strength work, use percentage-based programming when benchmarks are available
9. Respond ONLY with valid JSON matching the requested schema
10. Use Spanish for workout descriptions and coach notes (the athlete speaks Spanish)
"""


def _build_system_prompt() -> str:
    movements_text = "\n".join(
        f"- {m['name']} ({m['category'].value}) [equipment: {m['equipment_needed']}] "
        f"difficulty: {m['difficulty']}/10 | scaling: {m.get('scaling_options', 'N/A')}"
        for m in MOVEMENTS
    )
    subs_text = json.dumps(MOVEMENT_SUBSTITUTIONS, indent=2, ensure_ascii=False)
    benchmarks_text = "\n".join(
        f"- {name}: {data['description']}" for name, data in BENCHMARK_WODS.items()
    )
    principles_text = "\n".join(
        f"- {k}: {v}" if isinstance(v, str) else f"- {k}: {json.dumps(v, ensure_ascii=False)}"
        for k, v in PROGRAMMING_PRINCIPLES.items()
    )

    return SYSTEM_PROMPT.format(
        principles=principles_text,
        movements=movements_text,
        substitutions=subs_text,
        benchmarks=benchmarks_text,
    )


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


def generate_workout(
    client: anthropic.Anthropic,
    athlete_profile: dict,
    training_context: dict,
    model: str = "claude-sonnet-4-20250514",
) -> WorkoutResponse:
    """Generate a single workout adapted to athlete, equipment, and training phase."""

    available_movements = _get_available_movements(
        athlete_profile["equipment"],
        FitnessLevel(athlete_profile["level"]),
    )

    user_prompt = f"""\
Generate a single workout for today.

## Athlete Profile:
- Name: {athlete_profile['name']}
- Level: {athlete_profile['level']}
- Available time: {athlete_profile.get('available_minutes', athlete_profile['session_duration_minutes'])} minutes
- Goals: {athlete_profile.get('goals', 'General fitness')}
- Injuries/Limitations: {athlete_profile.get('injuries_limitations', 'None')}
- Equipment: {', '.join(athlete_profile['equipment'])}

## Available movements for this athlete (filtered by equipment & level):
{chr(10).join(f"- {m['name']} ({m['category'].value})" for m in available_movements)}

## Training Context:
- Phase: {training_context.get('phase', 'foundation')}
- Week focus: {training_context.get('focus', 'General fitness')}
- Target intensity: {training_context.get('target_intensity', 'moderate')}
- Day of week: {training_context.get('day_of_week', 'Monday')}
- Recent modalities used: {training_context.get('recent_modalities', 'None')}
- Recent workout types: {training_context.get('recent_workout_types', 'None')}
- Athlete feedback (last session): RPE={training_context.get('last_rpe', 'N/A')}, \
Soreness={training_context.get('last_soreness', 'N/A')}

{f"- Specific focus requested: {training_context['requested_focus']}" if training_context.get('requested_focus') else ""}
{f"- Exclude these movements: {', '.join(training_context['exclude_movements'])}" if training_context.get('exclude_movements') else ""}

## Response Format (JSON):
{{
    "warmup": "string - detailed warm-up (in Spanish)",
    "strength_or_skill": "string or null - strength/skill portion (in Spanish)",
    "wod": "string - the WOD description (in Spanish)",
    "wod_type": "amrap|for_time|emom|tabata|strength|skill|chipper|ladder",
    "target_time_domain": "short|medium|long",
    "modalities": ["list of modalities used"],
    "scaling_notes": "string - how to scale up/down (in Spanish)",
    "cooldown": "string - cool-down specific to workout (in Spanish)",
    "coaches_notes": "string - explain stimulus and intent (in Spanish)"
}}

Return ONLY valid JSON, no markdown code blocks.
"""

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=_build_system_prompt(),
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    # Handle potential markdown code block wrapping
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    data = json.loads(raw)
    return WorkoutResponse(**data)


def generate_week_plan(
    client: anthropic.Anthropic,
    athlete_profile: dict,
    training_context: dict,
    model: str = "claude-sonnet-4-20250514",
) -> WeekPlanResponse:
    """Generate a full week training plan."""

    available_movements = _get_available_movements(
        athlete_profile["equipment"],
        FitnessLevel(athlete_profile["level"]),
    )

    user_prompt = f"""\
Generate a complete training week plan.

## Athlete Profile:
- Name: {athlete_profile['name']}
- Level: {athlete_profile['level']}
- Training days/week: {athlete_profile['training_days_per_week']}
- Session duration: {athlete_profile['session_duration_minutes']} minutes
- Goals: {athlete_profile.get('goals', 'General fitness')}
- Injuries/Limitations: {athlete_profile.get('injuries_limitations', 'None')}
- Equipment: {', '.join(athlete_profile['equipment'])}

## Available movements:
{chr(10).join(f"- {m['name']} ({m['category'].value})" for m in available_movements)}

## Training Context:
- Current phase: {training_context.get('phase', 'foundation')}
- Week number in mesocycle: {training_context.get('week_number', 1)}
- Week focus: {training_context.get('focus', 'General fitness')}
- Target intensity: {training_context.get('target_intensity', 'moderate')}
- Recent benchmarks: {json.dumps(training_context.get('benchmarks', {}), ensure_ascii=False)}
- Last week avg RPE: {training_context.get('avg_rpe', 'N/A')}
- Last week modality distribution: {json.dumps(training_context.get('modality_distribution', {}), ensure_ascii=False)}

## L2 Programming Requirements:
1. Distribute modalities (M/G/W) across all combinations over the week
2. Vary time domains: include at least 1 short, 1 medium, 1 long WOD
3. Don't program heavy weightlifting on consecutive days
4. Include 1-2 strength/skill sessions
5. Plan rest days according to athlete's schedule
6. If deload week: reduce volume 40-50%, keep movement quality
7. Each day should have: warm-up, strength/skill (optional), WOD, cool-down

## Response Format (JSON):
{{
    "week_number": {training_context.get('week_number', 1)},
    "phase": "{training_context.get('phase', 'foundation')}",
    "focus": "string - week focus description (in Spanish)",
    "days": [
        {{
            "day": "Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo",
            "rest_day": false,
            "workout": {{
                "warmup": "string (in Spanish)",
                "strength_or_skill": "string or null (in Spanish)",
                "wod": "string (in Spanish)",
                "wod_type": "amrap|for_time|emom|tabata|strength|skill|chipper|ladder",
                "target_time_domain": "short|medium|long",
                "modalities": ["list"],
                "scaling_notes": "string (in Spanish)",
                "cooldown": "string (in Spanish)",
                "coaches_notes": "string (in Spanish)"
            }}
        }},
        {{
            "day": "...",
            "rest_day": true,
            "workout": null
        }}
    ],
    "programming_notes": "string - overall week reasoning and progression logic (in Spanish)"
}}

Return ONLY valid JSON, no markdown code blocks. Include all 7 days (Mon-Sun).
"""

    response = client.messages.create(
        model=model,
        max_tokens=8000,
        system=_build_system_prompt(),
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    data = json.loads(raw)
    return WeekPlanResponse(**data)


def generate_adaptation_feedback(
    client: anthropic.Anthropic,
    athlete_profile: dict,
    workout_log: dict,
    recent_logs: list[dict],
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """Analyze workout feedback and provide adaptation recommendations."""

    user_prompt = f"""\
Analyze the following workout log and recent training history to provide adaptation feedback.

## Athlete: {athlete_profile['name']} (Level: {athlete_profile['level']})

## Today's log:
- Score: {workout_log.get('score', 'N/A')}
- RPE: {workout_log.get('rpe', 'N/A')}/10
- Went Rx: {workout_log.get('went_rx', False)}
- Energy level: {workout_log.get('energy_level', 'N/A')}/5
- Sleep quality: {workout_log.get('sleep_quality', 'N/A')}/5
- Soreness: {workout_log.get('muscle_soreness', 'None')}
- Notes: {workout_log.get('notes', 'None')}

## Recent training history (last 7 sessions):
{json.dumps(recent_logs, indent=2, ensure_ascii=False, default=str)}

## Provide (in Spanish):
1. Assessment of today's performance relative to expected stimulus
2. Recovery recommendations
3. How this should influence the next 2-3 sessions (intensity, volume, movement selection)
4. Flag any concerning patterns (overtraining, imbalance, stagnation)

Keep it concise (3-5 sentences). Respond in plain text, no JSON.
"""

    response = client.messages.create(
        model=model,
        max_tokens=500,
        system=_build_system_prompt(),
        messages=[{"role": "user", "content": user_prompt}],
    )

    return response.content[0].text.strip()


def generate_progress_assessment(
    client: anthropic.Anthropic,
    athlete_profile: dict,
    progress_data: dict,
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """Generate overall progress assessment and recommendations."""

    user_prompt = f"""\
Provide a progress assessment for this athlete.

## Athlete: {athlete_profile['name']} (Level: {athlete_profile['level']})
## Goals: {athlete_profile.get('goals', 'General fitness')}

## Progress data:
- Total workouts completed: {progress_data.get('total_workouts', 0)}
- Current phase: {progress_data.get('current_phase', 'foundation')}
- Current week: {progress_data.get('current_week', 1)}
- Average RPE last week: {progress_data.get('avg_rpe', 'N/A')}
- Rx rate: {progress_data.get('rx_percentage', 0)}%
- Modality distribution: {json.dumps(progress_data.get('modality_distribution', {}), ensure_ascii=False)}
- Recent benchmarks: {json.dumps(progress_data.get('benchmarks', []), ensure_ascii=False, default=str)}

## Provide (in Spanish):
1. Overall progress assessment
2. Strengths identified
3. Areas needing improvement
4. Recommendation for next mesocycle phase
5. Should the athlete's level be adjusted?

Keep it concise (5-8 sentences). Respond in plain text, no JSON.
"""

    response = client.messages.create(
        model=model,
        max_tokens=600,
        system=_build_system_prompt(),
        messages=[{"role": "user", "content": user_prompt}],
    )

    return response.content[0].text.strip()

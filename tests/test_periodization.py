"""Unit tests for periodization logic."""

from crossfit_coach.models import Athlete, FitnessLevel, TrainingWeek, WorkoutLog, TrainingPhase
from crossfit_coach.periodization import (
    MACROCYCLE,
    PHASE_CONFIG,
    advance_week,
    get_current_training_context,
    should_suggest_level_change,
    _count_modalities,
    _lower_intensity,
)


def _make_athlete(db, **kwargs):
    defaults = dict(name="Test", level=FitnessLevel.INTERMEDIATE, training_days_per_week=3, session_duration_minutes=60)
    defaults.update(kwargs)
    athlete = Athlete(**defaults)
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    return athlete


class TestGetCurrentTrainingContext:

    def test_fresh_athlete_returns_week_1(self, db_session):
        athlete = _make_athlete(db_session)
        ctx = get_current_training_context(db_session, athlete)

        assert ctx["week_number"] == 1
        assert ctx["phase"] == TrainingPhase.FOUNDATION.value
        assert ctx["total_workouts"] == 0
        assert ctx["avg_rpe"] is None

    def test_context_includes_modality_distribution(self, db_session):
        athlete = _make_athlete(db_session)
        ctx = get_current_training_context(db_session, athlete)

        assert "modality_distribution" in ctx
        assert set(ctx["modality_distribution"].keys()) == {"monostructural", "gymnastics", "weightlifting"}

    def test_auto_regulation_high_rpe(self, db_session):
        """If average RPE > 8, intensity should be lowered to 'low'."""
        athlete = _make_athlete(db_session)
        for _ in range(5):
            db_session.add(WorkoutLog(athlete_id=athlete.id, rpe=9, went_rx=True))
        db_session.commit()

        ctx = get_current_training_context(db_session, athlete)
        assert ctx["target_intensity"] == "low"

    def test_auto_regulation_moderate_rpe(self, db_session):
        """If average RPE between 7-8, intensity should be lowered one step."""
        athlete = _make_athlete(db_session)
        # Add a training week so we know the base intensity
        tw = TrainingWeek(athlete_id=athlete.id, week_number=1, phase=TrainingPhase.FOUNDATION, focus="test", target_intensity="moderate")
        db_session.add(tw)
        for _ in range(5):
            db_session.add(WorkoutLog(athlete_id=athlete.id, rpe=7, went_rx=True))
        db_session.commit()

        ctx = get_current_training_context(db_session, athlete)
        # Should be lowered from whatever the base is
        assert ctx["target_intensity"] in ("low", "moderate")


class TestAdvanceWeek:

    def test_advance_from_empty(self, db_session):
        athlete = _make_athlete(db_session)
        week = advance_week(db_session, athlete)

        assert week.week_number == 1
        assert week.phase == TrainingPhase.FOUNDATION

    def test_advance_increments_week(self, db_session):
        athlete = _make_athlete(db_session)
        w1 = advance_week(db_session, athlete)
        w2 = advance_week(db_session, athlete)

        assert w2.week_number == w1.week_number + 1

    def test_macrocycle_wraps_around(self, db_session):
        athlete = _make_athlete(db_session)
        # Advance through entire macrocycle
        for _ in range(len(MACROCYCLE)):
            advance_week(db_session, athlete)

        # Next should wrap to week 13 but cycle phase from index 0
        next_week = advance_week(db_session, athlete)
        expected_phase, _ = MACROCYCLE[len(MACROCYCLE) % len(MACROCYCLE)]
        assert next_week.phase == expected_phase


class TestShouldSuggestLevelChange:

    def test_not_enough_data(self, db_session):
        athlete = _make_athlete(db_session)
        # Less than 10 logs → no suggestion
        for _ in range(5):
            db_session.add(WorkoutLog(athlete_id=athlete.id, rpe=5, went_rx=True))
        db_session.commit()

        assert should_suggest_level_change(db_session, athlete) is None

    def test_suggest_level_up(self, db_session):
        athlete = _make_athlete(db_session, level=FitnessLevel.BEGINNER)
        for _ in range(15):
            db_session.add(WorkoutLog(athlete_id=athlete.id, rpe=4, went_rx=True))
        db_session.commit()

        result = should_suggest_level_change(db_session, athlete)
        assert result is not None
        assert "intermediate" in result.lower()

    def test_suggest_level_down(self, db_session):
        athlete = _make_athlete(db_session, level=FitnessLevel.ADVANCED)
        for _ in range(15):
            db_session.add(WorkoutLog(athlete_id=athlete.id, rpe=9, went_rx=False))
        db_session.commit()

        result = should_suggest_level_change(db_session, athlete)
        assert result is not None
        assert "intermediate" in result.lower()

    def test_no_suggestion_for_elite_up(self, db_session):
        athlete = _make_athlete(db_session, level=FitnessLevel.ELITE)
        for _ in range(15):
            db_session.add(WorkoutLog(athlete_id=athlete.id, rpe=4, went_rx=True))
        db_session.commit()

        assert should_suggest_level_change(db_session, athlete) is None


class TestHelpers:

    def test_lower_intensity(self):
        assert _lower_intensity("high") == "moderate"
        assert _lower_intensity("moderate") == "low"
        assert _lower_intensity("low") == "low"
        assert _lower_intensity("max") == "high"

    def test_count_modalities_empty(self):
        assert _count_modalities([]) == {"monostructural": 0, "gymnastics": 0, "weightlifting": 0}

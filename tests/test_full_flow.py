"""End-to-end test: create athlete → generate WOD → log → check progress."""


ATHLETE_DATA = {
    "name": "Flow Test Athlete",
    "level": "beginner",
    "training_days_per_week": 3,
    "session_duration_minutes": 60,
    "goals": "General fitness",
    "equipment": ["barbell", "pull_up_bar"],
}


class TestFullFlow:

    def test_complete_training_cycle(self, client):
        # 1. Create athlete
        r = client.post("/athletes", json=ATHLETE_DATA)
        assert r.status_code == 200
        athlete = r.json()
        aid = athlete["id"]
        assert athlete["name"] == "Flow Test Athlete"

        # 2. Check initial progress — 0 workouts
        r = client.get(f"/progress/{aid}")
        assert r.status_code == 200
        assert r.json()["total_workouts"] == 0

        # 3. Generate a workout
        r = client.post("/workouts/generate", json={"athlete_id": aid})
        assert r.status_code == 200
        workout = r.json()
        assert workout["warmup"]
        assert workout["wod"]
        assert workout["wod_type"]
        assert len(workout["modalities"]) > 0

        # 4. Check history — now has 1 planned workout
        r = client.get(f"/workouts/{aid}/history")
        assert r.status_code == 200
        history = r.json()
        assert history["total"] == 1
        pw_id = history["workouts"][0]["id"]

        # 5. View workout detail
        r = client.get(f"/workouts/detail/{pw_id}")
        assert r.status_code == 200
        assert r.json()["wod"] is not None

        # 6. Log the workout
        r = client.post("/logs", json={
            "athlete_id": aid,
            "planned_workout_id": pw_id,
            "rpe": 7,
            "went_rx": False,
            "score": "3 rounds + 5 reps",
            "notes": "Felt good",
            "energy_level": 4,
            "sleep_quality": 4,
        })
        assert r.status_code == 200
        log = r.json()
        assert log["rpe"] == 7
        assert "adaptation_feedback" in log
        assert len(log["adaptation_feedback"]) > 0

        # 7. Add a benchmark
        r = client.post("/benchmarks", json={"athlete_id": aid, "name": "Fran", "value": "6:30"})
        assert r.status_code == 200

        # 8. Check progress — now has 1 workout, Rx%=0
        r = client.get(f"/progress/{aid}")
        assert r.status_code == 200
        progress = r.json()
        assert progress["total_workouts"] == 1
        assert progress["rx_percentage"] == 0.0
        assert len(progress["assessment"]) > 0

        # 9. Check trends
        r = client.get(f"/progress/{aid}/trends")
        assert r.status_code == 200
        assert len(r.json()["weeks"]) >= 1

        # 10. Check PRs
        r = client.get(f"/progress/{aid}/prs")
        assert r.status_code == 200
        assert r.json()["records"][0]["name"] == "Fran"

        # 11. Advance training week
        r = client.post("/training/advance-week", params={"athlete_id": aid})
        assert r.status_code == 200
        assert r.json()["week_number"] == 1

    def test_multi_athlete_isolation(self, client):
        """Two athletes should have independent data."""
        a1 = client.post("/athletes", json={**ATHLETE_DATA, "name": "Athlete A"}).json()["id"]
        a2 = client.post("/athletes", json={**ATHLETE_DATA, "name": "Athlete B"}).json()["id"]

        # Log for athlete A only
        client.post("/logs", json={"athlete_id": a1, "rpe": 7, "went_rx": True})
        client.post("/logs", json={"athlete_id": a1, "rpe": 6, "went_rx": True})

        # Athlete A has 2 workouts, B has 0
        r = client.get(f"/progress/{a1}")
        assert r.json()["total_workouts"] == 2

        r = client.get(f"/progress/{a2}")
        assert r.json()["total_workouts"] == 0

    def test_generate_week_plan(self, client):
        """Generate a full week plan and verify structure."""
        aid = client.post("/athletes", json=ATHLETE_DATA).json()["id"]

        r = client.post("/workouts/week", json={"athlete_id": aid})
        assert r.status_code == 200
        plan = r.json()

        assert len(plan["days"]) == 7
        assert plan["phase"] is not None
        assert plan["programming_notes"]

        training_days = [d for d in plan["days"] if not d["rest_day"]]
        rest_days = [d for d in plan["days"] if d["rest_day"]]
        assert len(training_days) >= 3
        assert len(rest_days) >= 1

        # Each training day has a workout
        for td in training_days:
            assert td["workout"] is not None
            assert td["workout"]["wod"]

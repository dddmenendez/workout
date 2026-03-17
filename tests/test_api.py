"""Integration tests for all API endpoints."""

import pytest


ATHLETE_DATA = {
    "name": "María",
    "level": "intermediate",
    "training_days_per_week": 4,
    "session_duration_minutes": 60,
    "goals": "Muscle-ups y mejorar Fran",
    "injuries_limitations": None,
    "equipment": ["barbell", "pull_up_bar", "rings", "rower"],
}


class TestAthleteEndpoints:

    def test_create_athlete(self, client):
        r = client.post("/athletes", json=ATHLETE_DATA)
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "María"
        assert data["id"] >= 1
        assert data["equipment"] == ATHLETE_DATA["equipment"]

    def test_get_athlete(self, client):
        r = client.post("/athletes", json=ATHLETE_DATA)
        aid = r.json()["id"]

        r = client.get(f"/athletes/{aid}")
        assert r.status_code == 200
        assert r.json()["name"] == "María"

    def test_get_athlete_not_found(self, client):
        r = client.get("/athletes/9999")
        assert r.status_code == 404

    def test_list_athletes(self, client):
        client.post("/athletes", json=ATHLETE_DATA)
        client.post("/athletes", json={**ATHLETE_DATA, "name": "Carlos"})

        r = client.get("/athletes")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_update_athlete(self, client):
        r = client.post("/athletes", json=ATHLETE_DATA)
        aid = r.json()["id"]

        r = client.put(f"/athletes/{aid}", json={"name": "María García", "training_days_per_week": 5})
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "María García"
        assert data["training_days_per_week"] == 5
        # Unchanged fields preserved
        assert data["level"] == "intermediate"

    def test_update_equipment(self, client):
        r = client.post("/athletes", json=ATHLETE_DATA)
        aid = r.json()["id"]

        r = client.put(f"/athletes/{aid}", json={"equipment": ["barbell", "kettlebell"]})
        assert r.status_code == 200
        assert set(r.json()["equipment"]) == {"barbell", "kettlebell"}

    def test_delete_athlete(self, client):
        r = client.post("/athletes", json=ATHLETE_DATA)
        aid = r.json()["id"]

        r = client.delete(f"/athletes/{aid}")
        assert r.status_code == 200

        r = client.get(f"/athletes/{aid}")
        assert r.status_code == 404


class TestBenchmarkEndpoints:

    def _create_athlete(self, client):
        return client.post("/athletes", json=ATHLETE_DATA).json()["id"]

    def test_add_benchmark(self, client):
        aid = self._create_athlete(client)
        r = client.post("/benchmarks", json={"athlete_id": aid, "name": "Fran", "value": "4:30"})
        assert r.status_code == 200
        assert r.json()["name"] == "Fran"

    def test_get_benchmarks(self, client):
        aid = self._create_athlete(client)
        client.post("/benchmarks", json={"athlete_id": aid, "name": "Fran", "value": "4:30"})
        client.post("/benchmarks", json={"athlete_id": aid, "name": "Back Squat 1RM", "value": "100kg"})

        r = client.get(f"/benchmarks/{aid}")
        assert r.status_code == 200
        assert len(r.json()) == 2


class TestProgressEndpoints:

    def _create_athlete(self, client):
        return client.post("/athletes", json=ATHLETE_DATA).json()["id"]

    def test_get_progress(self, client):
        aid = self._create_athlete(client)
        r = client.get(f"/progress/{aid}")
        assert r.status_code == 200
        data = r.json()
        assert data["total_workouts"] == 0
        assert data["rx_percentage"] == 0.0

    def test_rx_percentage_calculated(self, client):
        aid = self._create_athlete(client)
        # Log 3 workouts: 2 Rx, 1 not
        client.post("/logs", json={"athlete_id": aid, "rpe": 7, "went_rx": True})
        client.post("/logs", json={"athlete_id": aid, "rpe": 6, "went_rx": True})
        client.post("/logs", json={"athlete_id": aid, "rpe": 8, "went_rx": False})

        r = client.get(f"/progress/{aid}")
        data = r.json()
        assert data["total_workouts"] == 3
        assert 60 < data["rx_percentage"] < 70  # 66.7%

    def test_trends_empty(self, client):
        aid = self._create_athlete(client)
        r = client.get(f"/progress/{aid}/trends")
        assert r.status_code == 200
        assert r.json()["weeks"] == []

    def test_trends_with_logs(self, client):
        aid = self._create_athlete(client)
        client.post("/logs", json={"athlete_id": aid, "rpe": 7, "went_rx": True})
        client.post("/logs", json={"athlete_id": aid, "rpe": 5, "went_rx": False})

        r = client.get(f"/progress/{aid}/trends?weeks=4")
        assert r.status_code == 200
        weeks = r.json()["weeks"]
        assert len(weeks) >= 1
        assert weeks[0]["total_workouts"] >= 1

    def test_benchmark_history(self, client):
        aid = self._create_athlete(client)
        client.post("/benchmarks", json={"athlete_id": aid, "name": "Fran", "value": "5:00"})
        client.post("/benchmarks", json={"athlete_id": aid, "name": "Fran", "value": "4:30"})
        client.post("/benchmarks", json={"athlete_id": aid, "name": "Cindy", "value": "15 rounds"})

        r = client.get(f"/progress/{aid}/benchmarks")
        assert r.status_code == 200
        data = r.json()
        assert len(data["benchmarks"]) == 2  # Fran and Cindy

        fran = next(b for b in data["benchmarks"] if b["name"] == "Fran")
        assert len(fran["entries"]) == 2

    def test_personal_records(self, client):
        aid = self._create_athlete(client)
        client.post("/benchmarks", json={"athlete_id": aid, "name": "Fran", "value": "5:00"})
        client.post("/benchmarks", json={"athlete_id": aid, "name": "Back Squat 1RM", "value": "100kg"})

        r = client.get(f"/progress/{aid}/prs")
        assert r.status_code == 200
        records = r.json()["records"]
        assert len(records) == 2
        names = {r["name"] for r in records}
        assert names == {"Fran", "Back Squat 1RM"}

    def test_leaderboard(self, client):
        a1 = client.post("/athletes", json={**ATHLETE_DATA, "name": "María"}).json()["id"]
        a2 = client.post("/athletes", json={**ATHLETE_DATA, "name": "Carlos"}).json()["id"]

        client.post("/benchmarks", json={"athlete_id": a1, "name": "Fran", "value": "3:45"})
        client.post("/benchmarks", json={"athlete_id": a2, "name": "Fran", "value": "4:10"})

        r = client.get("/leaderboard", params={"benchmark": "Fran"})
        assert r.status_code == 200
        data = r.json()
        assert data["benchmark_name"] == "Fran"
        assert len(data["entries"]) == 2


class TestLoggingEndpoints:

    def _create_athlete(self, client):
        return client.post("/athletes", json=ATHLETE_DATA).json()["id"]

    def test_log_workout(self, client):
        aid = self._create_athlete(client)
        r = client.post("/logs", json={"athlete_id": aid, "rpe": 7, "went_rx": True, "score": "5 rounds"})
        assert r.status_code == 200
        data = r.json()
        assert data["rpe"] == 7
        assert data["went_rx"] is True
        assert "adaptation_feedback" in data


class TestWorkoutHistory:

    def _create_athlete(self, client):
        return client.post("/athletes", json=ATHLETE_DATA).json()["id"]

    def test_history_empty(self, client):
        aid = self._create_athlete(client)
        r = client.get(f"/workouts/{aid}/history")
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["workouts"] == []


class TestAdvanceWeek:

    def _create_athlete(self, client):
        return client.post("/athletes", json=ATHLETE_DATA).json()["id"]

    def test_advance_week(self, client):
        aid = self._create_athlete(client)
        r = client.post("/training/advance-week", params={"athlete_id": aid})
        assert r.status_code == 200
        data = r.json()
        assert "week_number" in data
        assert "phase" in data

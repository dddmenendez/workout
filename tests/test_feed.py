"""Tests for follow system and enhanced feed."""


class TestFollow:

    def _create_athlete(self, client, name):
        r = client.post("/athletes", json={
            "name": name, "level": "intermediate",
            "training_days_per_week": 4, "session_duration_minutes": 60,
            "equipment": ["barbell"],
        })
        return r.json()["id"]

    def test_follow_athlete(self, client):
        a1 = self._create_athlete(client, "Alice")
        a2 = self._create_athlete(client, "Bob")

        r = client.post(f"/athletes/{a1}/follow", json={
            "follower_id": a1, "followed_id": a2,
        })
        assert r.status_code == 200
        assert r.json()["followed_name"] == "Bob"

    def test_follow_self_rejected(self, client):
        a1 = self._create_athlete(client, "Solo")
        r = client.post(f"/athletes/{a1}/follow", json={
            "follower_id": a1, "followed_id": a1,
        })
        assert r.status_code == 400

    def test_follow_duplicate_rejected(self, client):
        a1 = self._create_athlete(client, "Alice")
        a2 = self._create_athlete(client, "Bob")
        client.post(f"/athletes/{a1}/follow", json={
            "follower_id": a1, "followed_id": a2,
        })
        r = client.post(f"/athletes/{a1}/follow", json={
            "follower_id": a1, "followed_id": a2,
        })
        assert r.status_code == 400

    def test_unfollow(self, client):
        a1 = self._create_athlete(client, "Alice")
        a2 = self._create_athlete(client, "Bob")
        client.post(f"/athletes/{a1}/follow", json={
            "follower_id": a1, "followed_id": a2,
        })
        r = client.delete(f"/athletes/{a1}/follow/{a2}")
        assert r.status_code == 200

        # Verify unfollowed
        r = client.get(f"/athletes/{a1}/follows")
        assert len(r.json()["following"]) == 0

    def test_get_follows(self, client):
        a1 = self._create_athlete(client, "Alice")
        a2 = self._create_athlete(client, "Bob")
        a3 = self._create_athlete(client, "Charlie")

        client.post(f"/athletes/{a1}/follow", json={"follower_id": a1, "followed_id": a2})
        client.post(f"/athletes/{a1}/follow", json={"follower_id": a1, "followed_id": a3})
        client.post(f"/athletes/{a2}/follow", json={"follower_id": a2, "followed_id": a1})

        r = client.get(f"/athletes/{a1}/follows")
        data = r.json()
        assert len(data["following"]) == 2
        assert len(data["followers"]) == 1


def _log_workout(client, athlete_id):
    """Generate a workout and log it. Returns feed entry data."""
    # Generate stores in DB automatically
    client.post("/workouts/generate", json={"athlete_id": athlete_id})

    # Get the planned_workout_id from history
    hist = client.get(f"/workouts/{athlete_id}/history?limit=1").json()
    pw_id = hist["workouts"][0]["id"]

    # Log result
    client.post("/logs", json={
        "athlete_id": athlete_id,
        "score": "5 rounds",
        "rpe": 7,
        "went_rx": True,
        "planned_workout_id": pw_id,
    })
    return pw_id


class TestFollowingFeed:

    def _setup_athletes(self, client):
        """Create 2 athletes, A follows B."""
        a1 = client.post("/athletes", json={
            "name": "Viewer", "level": "intermediate",
            "training_days_per_week": 4, "session_duration_minutes": 60,
            "equipment": ["barbell"],
        }).json()["id"]
        a2 = client.post("/athletes", json={
            "name": "Coach", "level": "advanced",
            "training_days_per_week": 5, "session_duration_minutes": 75,
            "equipment": ["barbell"],
        }).json()["id"]
        client.post(f"/athletes/{a1}/follow", json={"follower_id": a1, "followed_id": a2})
        return a1, a2

    def test_following_feed_empty(self, client):
        a1, a2 = self._setup_athletes(client)
        r = client.get(f"/feed/{a1}/following")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_following_feed_shows_followed_workouts(self, client):
        a1, a2 = self._setup_athletes(client)
        _log_workout(client, a2)

        r = client.get(f"/feed/{a1}/following")
        data = r.json()
        assert data["total"] == 1
        assert data["entries"][0]["athlete_name"] == "Coach"
        assert data["entries"][0]["score"] == "5 rounds"

    def test_following_feed_excludes_non_followed(self, client):
        a1, a2 = self._setup_athletes(client)

        a3 = client.post("/athletes", json={
            "name": "Stranger", "level": "beginner",
            "training_days_per_week": 3, "session_duration_minutes": 45,
            "equipment": ["barbell"],
        }).json()["id"]

        _log_workout(client, a2)
        _log_workout(client, a3)

        # a1's following feed: only a2
        r = client.get(f"/feed/{a1}/following")
        data = r.json()
        assert data["total"] == 1
        assert data["entries"][0]["athlete_name"] == "Coach"

        # Global feed: both
        r = client.get("/feed")
        assert r.json()["total"] == 2


class TestFeedExpandedDetails:

    def test_feed_includes_full_workout(self, client):
        aid = client.post("/athletes", json={
            "name": "Tester", "level": "intermediate",
            "training_days_per_week": 4, "session_duration_minutes": 60,
            "equipment": ["barbell"],
        }).json()["id"]

        _log_workout(client, aid)

        r = client.get("/feed")
        entry = r.json()["entries"][0]
        assert entry["workout_id"] is not None
        assert entry["wod_full"] is not None
        assert entry["warmup"] is not None

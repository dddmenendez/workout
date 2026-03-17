"""Tests for JWT authentication: register, login, protected endpoints."""


class TestRegister:

    def test_register_success(self, client):
        r = client.post("/auth/register", json={
            "email": "test@example.com",
            "password": "secret123",
            "display_name": "Test User",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "test@example.com"
        assert data["display_name"] == "Test User"
        assert "token" in data
        assert data["athlete_id"] is not None  # auto-created athlete

    def test_register_duplicate_email(self, client):
        client.post("/auth/register", json={
            "email": "dup@example.com",
            "password": "secret123",
            "display_name": "First",
        })
        r = client.post("/auth/register", json={
            "email": "dup@example.com",
            "password": "other456",
            "display_name": "Second",
        })
        assert r.status_code == 400
        assert "ya está registrado" in r.json()["detail"]

    def test_register_short_password(self, client):
        r = client.post("/auth/register", json={
            "email": "short@example.com",
            "password": "12345",
            "display_name": "Short",
        })
        assert r.status_code == 422  # Pydantic validation


class TestLogin:

    def _register(self, client):
        return client.post("/auth/register", json={
            "email": "login@example.com",
            "password": "mypassword",
            "display_name": "Login User",
        }).json()

    def test_login_success(self, client):
        self._register(client)
        r = client.post("/auth/login", json={
            "email": "login@example.com",
            "password": "mypassword",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "login@example.com"
        assert "token" in data

    def test_login_wrong_password(self, client):
        self._register(client)
        r = client.post("/auth/login", json={
            "email": "login@example.com",
            "password": "wrongpassword",
        })
        assert r.status_code == 401

    def test_login_nonexistent_email(self, client):
        r = client.post("/auth/login", json={
            "email": "nobody@example.com",
            "password": "whatever",
        })
        assert r.status_code == 401


class TestProtectedEndpoints:

    def _get_token(self, client):
        data = client.post("/auth/register", json={
            "email": "auth@example.com",
            "password": "secret123",
            "display_name": "Auth User",
        }).json()
        return data["token"], data["athlete_id"]

    def test_me_with_token(self, client):
        token, _ = self._get_token(client)
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == "auth@example.com"

    def test_me_without_token(self, client):
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_me_with_invalid_token(self, client):
        r = client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
        assert r.status_code == 401

    def test_existing_endpoints_still_work_without_token(self, client):
        """Backward compatibility: existing endpoints don't require auth."""
        # Create athlete via public endpoint
        r = client.post("/athletes", json={
            "name": "Public",
            "level": "beginner",
            "training_days_per_week": 3,
            "session_duration_minutes": 60,
            "equipment": ["barbell"],
        })
        assert r.status_code == 200
        aid = r.json()["id"]

        # These should all work without auth
        assert client.get("/athletes").status_code == 200
        assert client.get(f"/athletes/{aid}").status_code == 200
        assert client.get(f"/progress/{aid}").status_code == 200
        assert client.get("/feed").status_code == 200

    def test_token_carries_across_requests(self, client):
        """Register, get token, use it for multiple requests."""
        token, athlete_id = self._get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        # /auth/me works
        r = client.get("/auth/me", headers=headers)
        assert r.status_code == 200

        # Can generate a workout using the auto-created athlete
        r = client.post("/workouts/generate", json={"athlete_id": athlete_id}, headers=headers)
        assert r.status_code == 200
        assert r.json()["wod"]

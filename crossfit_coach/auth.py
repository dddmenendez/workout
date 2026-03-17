"""JWT authentication: token creation, password hashing, and FastAPI dependency.

Uses only stdlib (no external crypto deps) for maximum portability.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from crossfit_coach.models import User

# --- Config ---

SECRET_KEY = os.environ.get("CFC_SECRET_KEY", "dev-secret-change-in-production")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# --- Password hashing (pbkdf2, stdlib) ---


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${h}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split("$", 1)
        check = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 100_000).hex()
        return hmac.compare_digest(check, h)
    except Exception:
        return False


# --- JWT (HS256, pure stdlib) ---


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_access_token(user_id: int, email: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    exp = int((datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp())
    payload = {"sub": str(user_id), "email": email, "exp": exp}

    segments = [
        _b64url_encode(json.dumps(header).encode()),
        _b64url_encode(json.dumps(payload).encode()),
    ]
    signing_input = f"{segments[0]}.{segments[1]}"
    signature = hmac.new(SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest()
    segments.append(_b64url_encode(signature))

    return ".".join(segments)


def decode_token(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Token inválido")

        # Verify signature
        signing_input = f"{parts[0]}.{parts[1]}"
        expected_sig = hmac.new(SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest()
        actual_sig = _b64url_decode(parts[2])

        if not hmac.compare_digest(expected_sig, actual_sig):
            raise HTTPException(status_code=401, detail="Token inválido")

        payload = json.loads(_b64url_decode(parts[1]))

        # Check expiration
        exp = payload.get("exp")
        if exp and time.time() > exp:
            raise HTTPException(status_code=401, detail="Token expirado")

        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")

        return {"user_id": int(user_id), "email": payload.get("email")}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")


# --- FastAPI dependency ---

security = HTTPBearer(auto_error=False)

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from config import settings

_ALGORITHM = "HS256"


def _secret() -> str:
    if not settings.jwt_secret:
        raise RuntimeError("CONCEPTSCAPE_JWT_SECRET must be configured before authentication is enabled.")
    return settings.jwt_secret


def hash_password(password: str) -> str:
    # Use bcrypt directly. Passlib 1.7.4's bcrypt backend probe is not
    # compatible with bcrypt 5.x, which is allowed by the old dependency
    # constraint and can fail before hashing a valid password.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_minutes)
    return jwt.encode({"sub": user_id, "exp": expires}, _secret(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Token subject missing")
        return str(user_id)
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid or expired access token") from exc

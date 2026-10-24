from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings


_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALGORITHM = "HS256"


def _secret() -> str:
    if not settings.jwt_secret:
        raise RuntimeError("CONCEPTSCAPE_JWT_SECRET must be configured before authentication is enabled.")
    return settings.jwt_secret


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd.verify(password, password_hash)


def create_access_token(user_id: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_minutes)
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

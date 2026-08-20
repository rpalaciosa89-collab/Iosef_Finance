from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.core.security import SECRET_KEY, ALGORITHM
from app.config import settings
import redis as redis_lib
import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def _is_blacklisted(token: str) -> bool:
    try:
        r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        return r.exists(f"blacklist:jwt:{token}") > 0
    except redis_lib.ConnectionError:
        return False


def _resolve_token(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
) -> str | None:
    token = bearer_token
    if not token:
        cookie_name = settings.JWT_COOKIE_NAME
        token = (request.cookies or {}).get(cookie_name)
    return token


def get_current_user(
    token: str | None = Depends(_resolve_token),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    if _is_blacklisted(token):
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

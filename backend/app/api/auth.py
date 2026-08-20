from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime, timezone
from typing import Optional

from app.db.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, Token
from app.core.security import (
    get_password_hash, verify_password, create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM,
)
from app.core.deps import get_current_user
from app.config import settings
from jose import JWTError, jwt
import redis as redis_lib
import os

router = APIRouter()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

def _get_redis():
    try:
        r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        r.ping()
        return r
    except redis_lib.ConnectionError:
        return None


def _rate_limit(request: Request, prefix: str, max_requests: int, window: int):
    client_ip = request.client.host if request.client else "unknown"
    r = _get_redis()
    if r is None:
        return
    key = f"ratelimit:{prefix}:{client_ip}"
    current = r.get(key)
    if current is None:
        r.setex(key, window, 1)
    elif int(current) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait and try again.",
            headers={"Retry-After": str(r.ttl(key))},
        )
    else:
        r.incr(key)


def _set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key=settings.JWT_COOKIE_NAME,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.JWT_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserResponse)
def register(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    _rate_limit(request, "register", settings.AUTH_RATE_LIMIT_REQUESTS, settings.AUTH_RATE_LIMIT_WINDOW)

    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    new_user = User(email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/token", response_model=Token)
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    _rate_limit(request, "login", settings.AUTH_RATE_LIMIT_REQUESTS, settings.AUTH_RATE_LIMIT_WINDOW)

    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.email, "iat": datetime.now(timezone.utc).timestamp()},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    _set_auth_cookie(response, access_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout(request: Request, response: Response):
    token: Optional[str] = None

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif settings.JWT_COOKIE_NAME in request.cookies:
        token = request.cookies[settings.JWT_COOKIE_NAME]

    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            exp = payload.get("exp", 0)
            ttl = max(0, int(exp - datetime.now(timezone.utc).timestamp()))
            if ttl > 0:
                r = _get_redis()
                if r:
                    r.setex(f"blacklist:jwt:{token}", ttl, "1")
        except (JWTError, Exception):
            pass

    response.delete_cookie(
        key=settings.JWT_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.JWT_COOKIE_SECURE,
        samesite="lax",
    )
    return {"detail": "Logged out"}


@router.get("/status")
def auth_status(current_user: User = Depends(get_current_user)):
    return {"authenticated": True, "email": current_user.email}

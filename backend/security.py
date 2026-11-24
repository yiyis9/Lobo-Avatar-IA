import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario


password_hasher = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    if encoded_hash.startswith("hash_secret_"):
        return False
    try:
        return password_hasher.verify(password, encoded_hash)
    except (UnknownHashError, ValueError, TypeError):
        return False


def is_principal_admin(user: Usuario) -> bool:
    configured_email = os.getenv("PRINCIPAL_ADMIN_EMAIL", "").strip().casefold()
    return bool(
        configured_email
        and user.rol == "admin"
        and hmac.compare_digest(user.correo.casefold(), configured_email)
    )


def create_access_token(user: Usuario) -> tuple[str, int]:
    secret = os.getenv("ADMIN_TOKEN_SECRET")
    if not secret or len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El backend no tiene configurada una clave segura para tokens.",
        )
    expires_in = max(5, int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))) * 60
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user.id), "role": user.rol, "iat": now, "exp": now + timedelta(seconds=expires_in)},
        secret,
        algorithm="HS256",
    )
    return token, expires_in


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Se requiere una sesión administrativa válida.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    secret = os.getenv("ADMIN_TOKEN_SECRET")
    if not secret or credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, secret, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise unauthorized from None

    user = db.get(Usuario, user_id)
    if user is None or not user.activo or user.papelera_en is not None or user.rol != "admin" or payload.get("role") != "admin":
        raise unauthorized
    return user


def require_content_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Authorize the content administrator and the general administrator."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Se requiere una sesión administrativa válida.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    secret = os.getenv("ADMIN_TOKEN_SECRET")
    if not secret or credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, secret, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise unauthorized from None

    user = db.get(Usuario, user_id)
    if (
        user is None
        or not user.activo
        or user.papelera_en is not None
        or user.rol not in {"admin", "admin_contenido"}
        or payload.get("role") != user.rol
    ):
        raise unauthorized
    return user


def require_principal_admin(user: Usuario = Depends(require_admin)) -> Usuario:
    if not is_principal_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta acción requiere la cuenta del administrador principal.",
        )
    return user

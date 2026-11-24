import hmac
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import set_key, unset_key
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import CodigoRecuperacionContrasena, EstadoRelevoAdmin, Usuario
from schemas import (
    LoginRequest,
    PerfilUpdate,
    RecuperarContrasenaRequest,
    RegistroPendienteResponse,
    RegistroRequest,
    RestablecerContrasenaRequest,
    TokenResponse,
    UsuarioResponse,
)
from services.email import is_email_configured, send_password_reset_code
from security import create_access_token, hash_password, require_content_admin, verify_password


router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación administrativa"])
RESET_CODE_MESSAGE = "Si el correo corresponde a una cuenta administrativa activa, enviaremos un código de recuperación."


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(Usuario).where(Usuario.correo == request.correo))
    if (
        user is None
        or not user.activo
        or user.papelera_en is not None
        or user.estado_solicitud != "aprobada"
        or user.rol not in {"admin", "admin_contenido"}
        or not verify_password(request.contrasena, user.password_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Correo o contraseña incorrectos.")
    token, expires_in = create_access_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post("/register", response_model=RegistroPendienteResponse, status_code=status.HTTP_202_ACCEPTED)
def register(request: RegistroRequest, db: Session = Depends(get_db)) -> RegistroPendienteResponse:
    recovery_key = (request.clave_relevo or "").strip()
    emergency_handoff = request.rol == "admin" and bool(recovery_key)
    if emergency_handoff:
        configured_recovery_key = os.getenv("PRINCIPAL_ADMIN_RECOVERY_KEY", "")
        if not configured_recovery_key or not hmac.compare_digest(
            recovery_key.encode("utf-8"), configured_recovery_key.encode("utf-8")
        ):
            raise HTTPException(status_code=403, detail="La clave de relevo no es válida.")

        principal_email = os.getenv("PRINCIPAL_ADMIN_EMAIL", "").strip().casefold()
        current_principal = db.scalar(select(Usuario).where(Usuario.correo == principal_email)) if principal_email else None
        if current_principal and current_principal.rol == "admin" and current_principal.activo \
                and current_principal.estado_solicitud == "aprobada" and current_principal.papelera_en is None:
            raise HTTPException(status_code=409, detail="El administrador principal sigue activo; envía la solicitud normal para que la apruebe.")

        handoff_state = db.scalar(
            select(EstadoRelevoAdmin).where(EstadoRelevoAdmin.id == 1).with_for_update()
        )
        if handoff_state is None:
            raise HTTPException(status_code=503, detail="Falta aplicar la migración de relevo del administrador principal.")
        if handoff_state.usada_en is not None:
            raise HTTPException(status_code=409, detail="La clave de relevo ya fue utilizada. La persona responsable debe emitir una nueva.")
    else:
        authorization_key = os.getenv("REGISTRATION_AUTHORIZATION_KEY", "")
        if not authorization_key:
            raise HTTPException(status_code=503, detail="El registro administrativo no está habilitado.")
        supplied_authorization_key = (request.clave_autorizacion or "").encode("utf-8")
        if not hmac.compare_digest(supplied_authorization_key, authorization_key.encode("utf-8")):
            raise HTTPException(status_code=403, detail="La clave de autorización no es válida.")

    user = Usuario(
        nombre=request.nombre,
        correo=request.correo,
        password_hash=hash_password(request.contrasena),
        rol=request.rol,
        carrera=request.carrera,
        activo=emergency_handoff,
        estado_solicitud="aprobada" if emergency_handoff else "pendiente",
    )
    db.add(user)
    previous_principal_email = os.getenv("PRINCIPAL_ADMIN_EMAIL", "")
    env_path = Path(__file__).resolve().parents[1] / ".env"
    env_changed = False
    try:
        if emergency_handoff:
            if not env_path.is_file():
                raise HTTPException(status_code=503, detail="No se encontró backend/.env para guardar el relevo. Contacta a soporte técnico.")
            db.flush()
            handoff_state.usada_en = datetime.now(timezone.utc).replace(tzinfo=None)
            handoff_state.usada_por_id = user.id
            changed, _, _ = set_key(str(env_path), "PRINCIPAL_ADMIN_EMAIL", user.correo, quote_mode="always")
            if not changed:
                raise OSError("No se pudo actualizar la configuración local.")
            env_changed = True
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if env_changed:
            _restore_principal_email(env_path, previous_principal_email)
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo.") from error
    except HTTPException:
        db.rollback()
        raise
    except OSError as error:
        db.rollback()
        if env_changed:
            _restore_principal_email(env_path, previous_principal_email)
        raise HTTPException(status_code=503, detail="No se pudo guardar el nuevo administrador principal en backend/.env.") from error
    except Exception:
        db.rollback()
        if env_changed:
            _restore_principal_email(env_path, previous_principal_email)
        logging.exception("Falló el registro administrativo; se revirtió el relevo configurado")
        raise
    if emergency_handoff:
        os.environ["PRINCIPAL_ADMIN_EMAIL"] = user.correo
        return RegistroPendienteResponse(
            id=user.id,
            estado="aprobada",
            mensaje="Relevo completado. Tu cuenta es el nuevo administrador principal; ya puedes iniciar sesión.",
        )
    return RegistroPendienteResponse(id=user.id)


def _restore_principal_email(env_path: Path, previous_email: str) -> None:
    try:
        if previous_email:
            set_key(str(env_path), "PRINCIPAL_ADMIN_EMAIL", previous_email, quote_mode="always")
        else:
            unset_key(str(env_path), "PRINCIPAL_ADMIN_EMAIL")
    except OSError:
        logging.exception("No se pudo restaurar la configuración del administrador principal tras un fallo de registro")


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(request: RecuperarContrasenaRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    if not is_email_configured():
        raise HTTPException(status_code=503, detail="El correo de recuperación no está configurado en el backend.")

    user = db.scalar(
        select(Usuario).where(
            Usuario.correo == request.correo,
            Usuario.rol.in_(("admin", "admin_contenido")),
            Usuario.activo.is_(True),
            Usuario.papelera_en.is_(None),
            Usuario.estado_solicitud == "aprobada",
        )
    )
    if user is None:
        return {"mensaje": RESET_CODE_MESSAGE}

    now = datetime.now()
    latest = db.scalar(
        select(CodigoRecuperacionContrasena)
        .where(CodigoRecuperacionContrasena.usuario_id == user.id)
        .order_by(CodigoRecuperacionContrasena.creado_en.desc())
        .limit(1)
    )
    if latest and latest.creado_en and (now - latest.creado_en).total_seconds() < 60:
        return {"mensaje": RESET_CODE_MESSAGE}

    code = f"{secrets.randbelow(1_000_000):06d}"
    record = CodigoRecuperacionContrasena(
        usuario_id=user.id,
        codigo_hash=hashlib.sha256(code.encode("ascii")).hexdigest(),
        expira_en=now + timedelta(minutes=10),
    )
    db.add(record)
    db.commit()
    try:
        send_password_reset_code(user.correo, code)
    except Exception as error:
        logging.exception("No se pudo enviar el código de recuperación")
        record.usado_en = datetime.now()
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="No se pudo enviar el código. Revisa la configuración de correo SMTP del backend.",
        ) from error
    return {"mensaje": RESET_CODE_MESSAGE}


@router.post("/reset-password")
def reset_password(request: RestablecerContrasenaRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user = db.scalar(
        select(Usuario).where(
            Usuario.correo == request.correo,
            Usuario.rol.in_(("admin", "admin_contenido")),
            Usuario.activo.is_(True),
            Usuario.papelera_en.is_(None),
            Usuario.estado_solicitud == "aprobada",
        )
    )
    now = datetime.now()
    record = (
        db.scalar(
            select(CodigoRecuperacionContrasena)
            .where(
                CodigoRecuperacionContrasena.usuario_id == (user.id if user else -1),
                CodigoRecuperacionContrasena.usado_en.is_(None),
            )
            .order_by(CodigoRecuperacionContrasena.creado_en.desc())
            .limit(1)
        )
        if user
        else None
    )
    if record is None or record.intentos >= 5 or record.expira_en <= now:
        raise HTTPException(status_code=400, detail="El código no es válido o venció. Solicita uno nuevo.")

    submitted_hash = hashlib.sha256(request.codigo.encode("ascii")).hexdigest()
    if not hmac.compare_digest(submitted_hash, record.codigo_hash):
        record.intentos += 1
        db.commit()
        raise HTTPException(status_code=400, detail="El código no es válido o venció. Solicita uno nuevo.")

    user.password_hash = hash_password(request.contrasena_nueva)
    active_codes = db.scalars(
        select(CodigoRecuperacionContrasena).where(
            CodigoRecuperacionContrasena.usuario_id == user.id,
            CodigoRecuperacionContrasena.usado_en.is_(None),
        )
    ).all()
    for active_code in active_codes:
        active_code.usado_en = now
    db.commit()
    return {"mensaje": "Contraseña actualizada. Ya puedes iniciar sesión."}


@router.get("/me", response_model=UsuarioResponse)
def current_admin(user: Usuario = Depends(require_content_admin)) -> Usuario:
    return user


@router.patch("/me", response_model=UsuarioResponse)
def update_profile(
    request: PerfilUpdate,
    user: Usuario = Depends(require_content_admin),
    db: Session = Depends(get_db),
) -> Usuario:
    if request.nombre is not None:
        user.nombre = request.nombre
    if request.contrasena_nueva is not None:
        if not request.contrasena_actual or not verify_password(request.contrasena_actual, user.password_hash):
            raise HTTPException(status_code=400, detail="La contraseña actual no coincide.")
        user.password_hash = hash_password(request.contrasena_nueva)
    db.commit()
    db.refresh(user)
    return user

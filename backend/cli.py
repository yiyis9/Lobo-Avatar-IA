import getpass
import hmac
import os
import sys
from pathlib import Path

from dotenv import set_key, unset_key
from sqlalchemy import select

from database import SessionLocal
from models import DocumentoInstitucional, InformacionInstitucional, Usuario
from security import hash_password, verify_password
from services.institutional_documents import UPLOAD_DIRECTORY, DocumentValidationError, extract_pdf_text
from services.gemini_import import analyze_pdf_for_search


def create_admin() -> None:
    correo = input("Correo del administrador: ").strip().lower()
    nombre = input("Nombre completo: ").strip()
    password = getpass.getpass("Contraseña (mínimo 10 caracteres): ")
    confirmation = getpass.getpass("Confirma la contraseña: ")
    if not correo or not nombre or len(password) < 10 or password != confirmation:
        raise SystemExit("Datos incompletos o contraseñas inválidas.")

    with SessionLocal() as db:
        user = db.scalar(select(Usuario).where(Usuario.correo == correo))
        if user is not None:
            if user.rol != "admin" or not user.password_hash.startswith("hash_secret_"):
                raise SystemExit("El correo ya pertenece a una cuenta configurada; no se modificó.")
            user.nombre = nombre
            user.password_hash = hash_password(password)
            user.activo = True
            user.estado_solicitud = "aprobada"
        else:
            user = Usuario(
                nombre=nombre,
                correo=correo,
                password_hash=hash_password(password),
                rol="admin",
                activo=True,
                estado_solicitud="aprobada",
            )
            db.add(user)
        db.commit()
    print("Cuenta administradora lista.")


def assign_principal_admin() -> None:
    expected_key = os.getenv("PRINCIPAL_ADMIN_SETUP_KEY", "")
    if not expected_key:
        raise SystemExit("Configura una clave local de inicialización antes de continuar.")

    setup_key = getpass.getpass("Clave de inicialización del administrador principal: ")
    if not hmac.compare_digest(setup_key.encode("utf-8"), expected_key.encode("utf-8")):
        raise SystemExit("La clave de inicialización no es válida.")

    correo = input("Correo de la cuenta administradora existente: ").strip().lower()
    with SessionLocal() as db:
        user = db.scalar(select(Usuario).where(Usuario.correo == correo))
        if user is None or user.rol != "admin" or not user.activo or user.estado_solicitud != "aprobada":
            raise SystemExit("La cuenta debe existir y ser un administrador activo y aprobado. No se cambió la configuración.")

    env_path = Path(__file__).with_name(".env")
    set_key(str(env_path), "PRINCIPAL_ADMIN_EMAIL", correo, quote_mode="always")
    unset_key(str(env_path), "PRINCIPAL_ADMIN_SETUP_KEY")
    print("Administrador principal asignado. Reinicia FastAPI para aplicar los permisos.")


def reset_principal_admin_password() -> None:
    correo = os.getenv("PRINCIPAL_ADMIN_EMAIL", "").strip().lower()
    if not correo:
        raise SystemExit("No hay un administrador principal configurado en backend/.env.")

    password = getpass.getpass("Nueva contraseña (mínimo 10 caracteres): ")
    confirmation = getpass.getpass("Confirma la nueva contraseña: ")
    if len(password) < 10 or password != confirmation:
        raise SystemExit("Las contraseñas no coinciden o no cumplen la longitud mínima. No se cambió la cuenta.")

    with SessionLocal() as db:
        user = db.scalar(select(Usuario).where(Usuario.correo == correo))
        if user is None or user.rol != "admin":
            raise SystemExit("La cuenta principal no existe o no tiene rol de administrador. No se cambió la cuenta.")
        user.password_hash = hash_password(password)
        db.commit()

    print("Contraseña del administrador principal actualizada.")


def check_principal_admin_password() -> None:
    correo = os.getenv("PRINCIPAL_ADMIN_EMAIL", "").strip().lower()
    if not correo:
        raise SystemExit("No hay un administrador principal configurado en backend/.env.")

    password = getpass.getpass("Contraseña a comprobar: ")
    with SessionLocal() as db:
        user = db.scalar(select(Usuario).where(Usuario.correo == correo))
        if user is None:
            raise SystemExit("La cuenta principal no se encontró en la base configurada.")
        if user.rol != "admin" or not user.activo or user.estado_solicitud != "aprobada":
            raise SystemExit("La cuenta existe, pero no cumple las condiciones de acceso administrativo.")
        if not verify_password(password, user.password_hash):
            raise SystemExit("La contraseña no coincide con la guardada para la cuenta principal.")

    print("La contraseña coincide y la cuenta está habilitada para iniciar sesión.")


def reindex_documents() -> None:
    indexed = 0
    skipped = 0
    with SessionLocal() as db:
        documents = db.scalars(
            select(DocumentoInstitucional)
            .join(InformacionInstitucional)
            .where(DocumentoInstitucional.activo.is_(True), InformacionInstitucional.activo.is_(True))
        ).all()
        for document in documents:
            path = (UPLOAD_DIRECTORY / f"{document.archivo_key}.pdf").resolve()
            if path.parent != UPLOAD_DIRECTORY.resolve() or not path.is_file():
                skipped += 1
                continue
            try:
                document.contenido_extraido = extract_pdf_text(path.read_bytes())
                if document.contenido_extraido:
                    indexed += 1
                else:
                    skipped += 1
            except DocumentValidationError:
                skipped += 1
        db.commit()
    print(f"Documentos con texto indexado: {indexed}. Sin texto utilizable o no encontrados: {skipped}.")


def analyze_document_with_gemini() -> None:
    if len(sys.argv) != 3 or not sys.argv[2].isdigit():
        raise SystemExit("Uso: python cli.py analyze-document <id-documento>")

    document_id = int(sys.argv[2])
    with SessionLocal() as db:
        document = db.get(DocumentoInstitucional, document_id)
        if document is None:
            raise SystemExit("No se encontró el documento solicitado.")
        path = (UPLOAD_DIRECTORY / f"{document.archivo_key}.pdf").resolve()
        if path.parent != UPLOAD_DIRECTORY.resolve() or not path.is_file():
            raise SystemExit("No se encontró el PDF original almacenado.")
        content = path.read_bytes()
        native_text = extract_pdf_text(content)
        context_lines = [f"Archivo: {document.nombre_archivo}"]
        information = db.get(InformacionInstitucional, document.informacion_id) if document.informacion_id else None
        faq = db.get(PreguntaFrecuente, document.pregunta_frecuente_id) if document.pregunta_frecuente_id else None
        if information is not None:
            context_lines.extend((f"Título: {information.titulo}", f"Categoría: {information.categoria}"))
        if faq is not None:
            context_lines.extend((
                f"Pregunta asociada: {faq.pregunta}",
                f"Categoría: {faq.categoria}",
                f"Palabras clave existentes: {faq.palabras_clave or ''}",
            ))
        document.contenido_extraido = analyze_pdf_for_search(
            content,
            native_text,
            associated_context="\n".join(context_lines),
        )
        db.commit()
        filename = document.nombre_archivo
        indexed_chars = len(document.contenido_extraido)
    print(f"Documento {document_id} ({filename}) analizado por Gemini y actualizado: {indexed_chars} caracteres indexados.")


if __name__ == "__main__":
    commands = {
        "create-admin": create_admin,
        "assign-principal-admin": assign_principal_admin,
        "reset-principal-admin-password": reset_principal_admin_password,
        "check-principal-admin-password": check_principal_admin_password,
        "reindex-documents": reindex_documents,
        "analyze-document": analyze_document_with_gemini,
    }
    if len(sys.argv) < 2 or sys.argv[1] not in commands or (sys.argv[1] != "analyze-document" and len(sys.argv) != 2):
        raise SystemExit(
            "Uso: python cli.py create-admin | assign-principal-admin | reset-principal-admin-password "
            "| check-principal-admin-password | reindex-documents | analyze-document <id-documento>"
        )
    commands[sys.argv[1]]()

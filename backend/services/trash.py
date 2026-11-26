from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from models import DocumentoInstitucional, HistorialConsulta, InformacionInstitucional, MensajeContacto, PreguntaFrecuente, Usuario
from services.institutional_documents import discard_pdf


RETENTION_DAYS = 30


def move_document_to_trash(document: DocumentoInstitucional, now: datetime | None = None) -> None:
    document.activo = False
    if document.papelera_en is None:
        document.papelera_en = now or datetime.now(timezone.utc).replace(tzinfo=None)


def move_information_to_trash(
    item: InformacionInstitucional,
    db: Session,
    now: datetime | None = None,
) -> None:
    deleted_at = now or datetime.now(timezone.utc).replace(tzinfo=None)
    item.activo = False
    item.papelera_en = deleted_at
    for document in db.scalars(
        select(DocumentoInstitucional).where(DocumentoInstitucional.informacion_id == item.id)
    ):
        move_document_to_trash(document, deleted_at)


def restore_document(document: DocumentoInstitucional) -> None:
    document.papelera_en = None
    document.activo = True


def restore_information(item: InformacionInstitucional, db: Session) -> None:
    deleted_at = item.papelera_en
    item.papelera_en = None
    item.activo = False
    if deleted_at is not None:
        for document in db.scalars(select(DocumentoInstitucional).where(
            DocumentoInstitucional.informacion_id == item.id,
            DocumentoInstitucional.papelera_en == deleted_at,
        )):
            restore_document(document)


def move_user_to_trash(user: Usuario, now: datetime | None = None) -> None:
    if user.rol == "admin":
        raise ValueError("Las cuentas de administrador general no se pueden enviar a la papelera.")
    if user.papelera_en is None:
        user.papelera_en = now or datetime.now(timezone.utc).replace(tzinfo=None)


def restore_user(user: Usuario) -> None:
    user.papelera_en = None


def purge_expired_trash(db: Session, now: datetime | None = None) -> int:
    current_time = now or datetime.now(timezone.utc).replace(tzinfo=None)
    expires_before = current_time - timedelta(days=RETENTION_DAYS)
    expired_information = list(db.scalars(
        select(InformacionInstitucional).where(InformacionInstitucional.papelera_en <= expires_before)
    ))
    expired_information_ids = [item.id for item in expired_information]
    expired_questions = list(db.scalars(
        select(PreguntaFrecuente).where(PreguntaFrecuente.papelera_en <= expires_before)
    ))
    expired_question_ids = [item.id for item in expired_questions]
    # Recupera cuentas generales que pudieran estar en papelera desde antes
    # de esta protección, y excluye su purga permanente.
    protected_admins = list(db.scalars(select(Usuario).where(
        Usuario.rol == "admin",
        Usuario.papelera_en.is_not(None),
    )))
    for user in protected_admins:
        user.papelera_en = None
    expired_users = list(db.scalars(select(Usuario).where(
        Usuario.papelera_en <= expires_before,
        Usuario.rol != "admin",
    )))
    expired_contact_messages = list(db.scalars(
        select(MensajeContacto).where(MensajeContacto.papelera_en <= expires_before)
    ))
    expired_user_ids = [user.id for user in expired_users]
    expired_documents = list(db.scalars(
        select(DocumentoInstitucional).where(
            (DocumentoInstitucional.papelera_en <= expires_before)
            | (DocumentoInstitucional.informacion_id.in_(expired_information_ids) if expired_information_ids else False)
            | (DocumentoInstitucional.pregunta_frecuente_id.in_(expired_question_ids) if expired_question_ids else False)
        )
    ))
    file_keys = [document.archivo_key for document in expired_documents]
    for document in expired_documents:
        db.delete(document)
    for item in expired_information:
        db.delete(item)
    for question in expired_questions:
        db.delete(question)
    if expired_user_ids:
        db.execute(
            update(HistorialConsulta)
            .where(HistorialConsulta.usuario_id.in_(expired_user_ids))
            .values(usuario_id=None)
        )
    for user in expired_users:
        db.delete(user)
    for message in expired_contact_messages:
        db.delete(message)
    db.commit()
    for file_key in file_keys:
        discard_pdf(file_key)
    return len(expired_documents) + len(expired_information) + len(expired_questions) + len(expired_users) + len(expired_contact_messages)

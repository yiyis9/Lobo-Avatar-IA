import base64
import binascii
import asyncio
import logging
import mimetypes
import queue
import smtplib
from io import BytesIO
from datetime import datetime
from datetime import date, timedelta, timezone
from pathlib import Path
from starlette.background import BackgroundTask

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models import DocumentoInstitucional, HistorialConsulta, InformacionInstitucional, MensajeContacto, PreguntaFrecuente, Usuario
from schemas import (
    ImportarInformacionRequest,
    ImportarInformacionResponse,
    DecisionSolicitud,
    ContactoLeidoRequest,
    ContactoRespuestaRequest,
    ContactoResponse,
    EstadoUsuario,
    GenerarAccionAvatarRequest,
    GenerarAccionAvatarResponse,
    HistorialResponse,
    InformacionCreate,
    InformacionConDocumentoRequest,
    InformacionResponse,
    PreguntaCreate,
    PreguntaConDocumentoRequest,
    PreguntasPaginadasResponse,
    PreguntaResponse,
    PreguntaUpdate,
    RolUsuarioUpdate,
    UsuarioResponse,
)
from security import require_admin, require_content_admin, require_principal_admin
from services.institutional_documents import (
    DocumentValidationError,
    discard_pdf,
    store_pdf,
    store_institutional_file,
)
from services.gemini_import import (
    GeminiConfigurationError,
    GeminiServiceError,
    ImportValidationError,
    analyze_pdf_for_search,
    extract_source_text,
    _stable_key,
    suggest_information,
    suggest_information_from_pdf,
)
from services.database_backup import BackupConfigurationError, create_database_backup
from services.trash import (
    move_document_to_trash,
    move_information_to_trash,
    move_user_to_trash,
    restore_document,
    restore_information,
    restore_user,
)
from services.document_indexer import enrich_document_index
from services.email import is_email_configured, send_contact_reply
from services.gemini_avatar import (
    AvatarActionConfigurationError,
    AvatarActionServiceError,
    suggest_avatar_action,
)
from services.chat import default_avatar_action, default_avatar_animation
from services.contact_events import subscribe_contact_events, unsubscribe_contact_events


router = APIRouter(prefix="/api/v1/admin", tags=["Administración"])
logger = logging.getLogger(__name__)
ATTACHMENT_FIELDS = {"archivo_nombre", "archivo_base64", "archivos_nombres", "archivos_base64", "contenido_publico_confirmado"}
MAX_ATTACHMENT_COUNT = 20
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENT_TOTAL_BYTES = 20 * 1024 * 1024
MAX_EMAIL_ATTACHMENT_BYTES = 17 * 1024 * 1024


@router.get("/mensajes-contacto", response_model=list[ContactoResponse])
def contact_messages(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> list[MensajeContacto]:
    return list(db.scalars(
        select(MensajeContacto)
        .where(MensajeContacto.papelera_en.is_(None))
        .order_by(MensajeContacto.creado_en.desc())
        .limit(500)
    ))


@router.get("/mensajes-contacto/eventos")
async def contact_message_events(
    request: Request,
    _: Usuario = Depends(require_content_admin),
) -> StreamingResponse:
    subscriber = subscribe_contact_events()

    async def event_stream():
        try:
            yield "retry: 2000\n\n"
            while not await request.is_disconnected():
                try:
                    event = await asyncio.to_thread(subscriber.get, True, 15)
                    yield f"event: contact-message\ndata: {event}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            unsubscribe_contact_events(subscriber)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.patch("/mensajes-contacto/{message_id}/leido", response_model=ContactoResponse)
def set_contact_message_read(
    message_id: int,
    request: ContactoLeidoRequest,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_content_admin),
) -> MensajeContacto:
    if current.rol == "admin_contenido" and not request.leido:
        raise HTTPException(status_code=403, detail="El administrador de contenido solo puede marcar mensajes como leídos.")
    item = db.get(MensajeContacto, message_id)
    if item is None or item.papelera_en is not None:
        raise HTTPException(status_code=404, detail="Mensaje de contacto no encontrado.")
    item.leido = request.leido
    db.commit()
    db.refresh(item)
    return item


@router.post("/mensajes-contacto/{message_id}/responder", status_code=status.HTTP_204_NO_CONTENT)
def reply_to_contact_message(
    message_id: int,
    request: ContactoRespuestaRequest,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> Response:
    item = db.get(MensajeContacto, message_id)
    if item is None or item.papelera_en is not None:
        raise HTTPException(status_code=404, detail="Mensaje de contacto no encontrado.")
    if not is_email_configured():
        raise HTTPException(status_code=503, detail="El envío de correo no está configurado en el backend.")
    attachments: list[tuple[str, bytes]] = []
    total_bytes = 0
    for attachment in request.adjuntos:
        try:
            content = base64.b64decode(attachment.contenido_base64, validate=True)
        except (ValueError, binascii.Error) as error:
            raise HTTPException(status_code=422, detail="Uno de los archivos adjuntos no tiene un formato válido.") from error
        total_bytes += len(content)
        if total_bytes > MAX_EMAIL_ATTACHMENT_BYTES:
            raise HTTPException(status_code=413, detail="Los adjuntos no pueden superar 17 MB en conjunto para el envío por correo.")
        attachments.append((attachment.nombre, content))
    try:
        send_contact_reply(item.correo, f"Re: {item.asunto}", request.mensaje.strip(), attachments)
    except (OSError, smtplib.SMTPException, ValueError) as error:
        logger.warning("No se pudo enviar la respuesta al mensaje de contacto %s (%s).", item.id, type(error).__name__)
        raise HTTPException(status_code=502, detail="No se pudo enviar el correo. Revisa la configuración SMTP del backend.") from error
    if not item.leido:
        item.leido = True
    item.contestado = True
    item.contestado_en = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/mensajes-contacto/{message_id}/papelera", status_code=status.HTTP_204_NO_CONTENT)
def trash_contact_message(
    message_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> Response:
    item = db.get(MensajeContacto, message_id)
    if item is None or item.papelera_en is not None:
        raise HTTPException(status_code=404, detail="Mensaje de contacto disponible no encontrado.")
    item.papelera_en = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/mensajes-contacto/{message_id}/restaurar", status_code=status.HTTP_204_NO_CONTENT)
def restore_contact_message(
    message_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> Response:
    item = db.get(MensajeContacto, message_id)
    if item is None or item.papelera_en is None:
        raise HTTPException(status_code=404, detail="Mensaje de contacto no encontrado en la papelera.")
    item.papelera_en = None
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _decode_request_attachments(request: PreguntaConDocumentoRequest | InformacionConDocumentoRequest) -> list[tuple[str, bytes]]:
    names = request.archivos_nombres
    encoded_files = request.archivos_base64
    legacy_name = request.archivo_nombre
    legacy_content = request.archivo_base64
    if names or encoded_files:
        if legacy_name or legacy_content:
            raise HTTPException(status_code=422, detail="Envía los archivos en un solo formato.")
        if len(names) != len(encoded_files):
            raise HTTPException(status_code=422, detail="Cada archivo debe tener un nombre y contenido completos.")
    elif bool(legacy_name) != bool(legacy_content):
        raise HTTPException(status_code=422, detail="Selecciona archivos completos o deja los adjuntos vacíos.")
    else:
        names = [legacy_name] if legacy_name else []
        encoded_files = [legacy_content] if legacy_content else []

    if len(names) > MAX_ATTACHMENT_COUNT:
        raise HTTPException(status_code=422, detail="Puedes adjuntar hasta 20 archivos por guardado.")
    if names and not request.contenido_publico_confirmado:
        raise HTTPException(status_code=400, detail="Confirma que los archivos contienen únicamente información pública.")

    decoded: list[tuple[str, bytes]] = []
    total_bytes = 0
    for filename, encoded in zip(names, encoded_files):
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise HTTPException(status_code=422, detail="Uno de los archivos adjuntos no tiene un formato válido.") from error
        total_bytes += len(content)
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise HTTPException(status_code=422, detail=f"Cada archivo adjunto debe pesar como máximo {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB.")
        if total_bytes > MAX_ATTACHMENT_TOTAL_BYTES:
            raise HTTPException(status_code=422, detail=f"El tamaño conjunto de los archivos no puede superar {MAX_ATTACHMENT_TOTAL_BYTES // (1024 * 1024)} MB por guardado.")
        decoded.append((filename, content))
    return decoded


def _store_request_attachments(
    files: list[tuple[str, bytes]],
    db: Session,
    *,
    faq_id: int | None = None,
    information_id: int | None = None,
) -> tuple[list[DocumentoInstitucional], list[str]]:
    documents: list[DocumentoInstitucional] = []
    stored_keys: list[str] = []
    try:
        for filename, content in files:
            stored_key, safe_name, mime_type, extracted_text = store_institutional_file(filename, content)
            stored_keys.append(stored_key)
            document = DocumentoInstitucional(
                pregunta_frecuente_id=faq_id,
                informacion_id=information_id,
                nombre_archivo=safe_name,
                archivo_key=stored_key,
                mime_type=mime_type,
                tamano_bytes=len(content),
                contenido_extraido=extracted_text,
                activo=True,
                estado_indice="pendiente" if mime_type == "application/pdf" else "listo",
            )
            db.add(document)
            documents.append(document)
    except Exception:
        for key in stored_keys:
            discard_pdf(key)
        raise
    return documents, stored_keys


@router.get("/respaldo")
def download_database_backup(_: Usuario = Depends(require_admin)) -> FileResponse:
    try:
        backup_path = create_database_backup()
    except BackupConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    filename = f"lobo_upvt_db_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    return FileResponse(
        backup_path,
        media_type="application/sql",
        filename=filename,
        background=BackgroundTask(backup_path.unlink, missing_ok=True),
    )


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), current: Usuario = Depends(require_content_admin)) -> dict:
    faq_count = db.scalar(select(func.count()).select_from(PreguntaFrecuente).where(
        PreguntaFrecuente.activo.is_(True), PreguntaFrecuente.papelera_en.is_(None)
    )) or 0
    if current.rol == "admin_contenido":
        return {
            "respuestas_registradas": faq_count,
            "atenciones_totales": db.scalar(select(func.count()).select_from(HistorialConsulta)) or 0,
            "preguntas_frecuentes": [dict(row) for row in db.execute(
                select(PreguntaFrecuente.pregunta, func.count(HistorialConsulta.id).label("consultas"))
                .outerjoin(HistorialConsulta, HistorialConsulta.pregunta_frecuente_id == PreguntaFrecuente.id)
                .where(PreguntaFrecuente.activo.is_(True), PreguntaFrecuente.papelera_en.is_(None))
                .group_by(PreguntaFrecuente.id, PreguntaFrecuente.pregunta)
                .order_by(func.count(HistorialConsulta.id).desc())
                .limit(5)
            ).mappings().all()],
        }
    return {
        "respuestas_registradas": faq_count,
        "solicitudes_pendientes": db.scalar(select(func.count()).select_from(Usuario).where(Usuario.estado_solicitud == "pendiente")) or 0,
        "consultas_hoy": db.scalar(select(func.count()).select_from(HistorialConsulta).where(HistorialConsulta.fecha_consulta >= date.today())) or 0,
        "atenciones_totales": db.scalar(select(func.count()).select_from(HistorialConsulta)) or 0,
        "preguntas_frecuentes": [dict(row) for row in db.execute(
            select(PreguntaFrecuente.pregunta, func.count(HistorialConsulta.id).label("consultas"))
            .outerjoin(HistorialConsulta, HistorialConsulta.pregunta_frecuente_id == PreguntaFrecuente.id)
            .where(PreguntaFrecuente.activo.is_(True), PreguntaFrecuente.papelera_en.is_(None))
            .group_by(PreguntaFrecuente.id, PreguntaFrecuente.pregunta)
            .order_by(func.count(HistorialConsulta.id).desc())
            .limit(5)
        ).mappings().all()],
    }


@router.get("/dashboard/reporte.xlsx")
def dashboard_report(db: Session = Depends(get_db), current: Usuario = Depends(require_content_admin)) -> StreamingResponse:
    today = date.today()
    since = today - timedelta(days=29)
    daily_rows = db.execute(
        select(func.date(HistorialConsulta.fecha_consulta).label("fecha"), func.count().label("consultas"))
        .where(HistorialConsulta.fecha_consulta >= since)
        .group_by(func.date(HistorialConsulta.fecha_consulta))
        .order_by(func.date(HistorialConsulta.fecha_consulta))
    ).mappings().all()
    daily_counts = {str(row["fecha"]): row["consultas"] for row in daily_rows}
    faq_count = db.scalar(select(func.count()).select_from(PreguntaFrecuente).where(
        PreguntaFrecuente.activo.is_(True), PreguntaFrecuente.papelera_en.is_(None)
    )) or 0
    total_queries = db.scalar(select(func.count()).select_from(HistorialConsulta)) or 0
    popular = db.execute(
        select(PreguntaFrecuente.pregunta, func.count(HistorialConsulta.id).label("consultas"))
        .outerjoin(HistorialConsulta, HistorialConsulta.pregunta_frecuente_id == PreguntaFrecuente.id)
        .where(PreguntaFrecuente.activo.is_(True), PreguntaFrecuente.papelera_en.is_(None))
        .group_by(PreguntaFrecuente.id, PreguntaFrecuente.pregunta)
        .order_by(func.count(HistorialConsulta.id).desc())
        .limit(10)
    ).mappings().all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Resumen"
    sheet.append(["Reporte del resumen · Lobo UPVT"])
    sheet.append(["Generado", datetime.now().strftime("%d/%m/%Y %H:%M")])
    sheet.append(["Indicador", "Valor"])
    sheet.append(["Respuestas activas", faq_count])
    sheet.append(["Consultas atendidas", total_queries])
    if current.rol != "admin_contenido":
        pending = db.scalar(select(func.count()).select_from(Usuario).where(Usuario.estado_solicitud == "pendiente")) or 0
        today_count = db.scalar(select(func.count()).select_from(HistorialConsulta).where(
            HistorialConsulta.fecha_consulta >= today
        )) or 0
        sheet.append(["Consultas de hoy", today_count])
        sheet.append(["Solicitudes pendientes", pending])

    daily_col = 4
    sheet.cell(row=1, column=daily_col, value="Consultas por día · últimos 30 días")
    sheet.cell(row=2, column=daily_col, value="Fecha")
    sheet.cell(row=2, column=daily_col + 1, value="Consultas")
    for offset in range(30):
        day = since + timedelta(days=offset)
        row_num = 3 + offset
        sheet.cell(row=row_num, column=daily_col, value=day)
        sheet.cell(row=row_num, column=daily_col).number_format = "dd/mm/yyyy"
        sheet.cell(row=row_num, column=daily_col + 1, value=daily_counts.get(day.isoformat(), 0))

    popular_col = 7
    sheet.cell(row=1, column=popular_col, value="Preguntas más consultadas")
    sheet.cell(row=2, column=popular_col, value="Pregunta")
    sheet.cell(row=2, column=popular_col + 1, value="Consultas")
    for row_num, item in enumerate(popular, start=3):
        sheet.cell(row=row_num, column=popular_col, value=item["pregunta"])
        sheet.cell(row=row_num, column=popular_col + 1, value=item["consultas"])

    header_fill = PatternFill("solid", fgColor="A61F43")
    for row in (1, 2, 3):
        for cell in sheet[row]:
            if cell.value is not None:
                cell.font = Font(color="FFFFFF", bold=True, size=14 if row == 1 else 11)
                cell.fill = header_fill
                cell.alignment = Alignment(vertical="center", wrap_text=True)
    for column, width in {1: 30, 2: 20, 4: 16, 5: 14, 7: 48, 8: 14}.items():
        sheet.column_dimensions[chr(64 + column)].width = width
    sheet.freeze_panes = "A4"

    line = LineChart()
    line.title = "Actividad diaria (30 días)"
    line.y_axis.title = "Consultas"
    line.x_axis.title = "Fecha"
    line.height, line.width = 8, 16
    line.add_data(Reference(sheet, min_col=daily_col + 1, min_row=2, max_row=32), titles_from_data=True)
    line.set_categories(Reference(sheet, min_col=daily_col, min_row=3, max_row=32))
    sheet.add_chart(line, "A11")

    if popular:
        bar = BarChart()
        bar.type = "bar"
        bar.style = 10
        bar.title = "Preguntas más consultadas"
        bar.x_axis.title = "Consultas"
        bar.y_axis.title = "Pregunta"
        bar.height, bar.width = 9, 18
        bar.add_data(Reference(sheet, min_col=popular_col + 1, min_row=2, max_row=2 + len(popular)), titles_from_data=True)
        bar.set_categories(Reference(sheet, min_col=popular_col, min_row=3, max_row=2 + len(popular)))
        sheet.add_chart(bar, "J11")

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = f"reporte-resumen-lobo-upvt-{today.isoformat()}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/metricas")
def metrics(
    dias: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> dict:
    since = date.today() - timedelta(days=dias - 1)
    records = [dict(row) for row in db.execute(
        select(func.date(HistorialConsulta.fecha_consulta).label("fecha"), func.count().label("consultas"))
        .where(HistorialConsulta.fecha_consulta >= since)
        .group_by(func.date(HistorialConsulta.fecha_consulta))
        .order_by(func.date(HistorialConsulta.fecha_consulta))
    ).mappings().all()]
    total = db.scalar(select(func.count()).select_from(HistorialConsulta).where(HistorialConsulta.fecha_consulta >= since)) or 0
    return {"desde": since, "dias": dias, "atenciones": total, "series": records}


@router.get("/usuarios", response_model=list[UsuarioResponse])
def users(
    estado: str | None = Query(default=None, pattern="^(pendiente|aprobada|rechazada)$"),
    limite: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_admin),
) -> list[Usuario]:
    statement = select(Usuario).where(Usuario.papelera_en.is_(None)).order_by(Usuario.creado_en.desc()).limit(limite)
    if estado:
        statement = statement.where(Usuario.estado_solicitud == estado)
    return list(db.scalars(statement))


@router.post("/usuarios/{user_id}/papelera", status_code=status.HTTP_204_NO_CONTENT)
def trash_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_principal_admin),
) -> Response:
    user = db.get(Usuario, user_id)
    if user is None or user.papelera_en is not None:
        raise HTTPException(status_code=404, detail="Usuario activo no encontrado.")
    if user.id == current.id or user.es_admin_principal:
        raise HTTPException(status_code=409, detail="No puedes mover a la papelera la cuenta administradora principal ni tu propia cuenta.")
    if user.rol == "admin":
        raise HTTPException(status_code=409, detail="Las cuentas de administrador general están protegidas y no se pueden eliminar.")
    move_user_to_trash(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/usuarios/{user_id}/restaurar", status_code=status.HTTP_204_NO_CONTENT)
def restore_trashed_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_principal_admin),
) -> Response:
    user = db.get(Usuario, user_id)
    if user is None or user.papelera_en is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en la papelera.")
    restore_user(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/solicitudes", response_model=list[UsuarioResponse])
def pending_requests(db: Session = Depends(get_db), _: Usuario = Depends(require_admin)) -> list[Usuario]:
    return list(db.scalars(select(Usuario).where(
        Usuario.estado_solicitud == "pendiente",
        Usuario.papelera_en.is_(None),
    ).order_by(Usuario.creado_en)))


@router.put("/solicitudes/{user_id}", response_model=UsuarioResponse)
def decide_request(
    user_id: int,
    request: DecisionSolicitud,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_principal_admin),
) -> Usuario:
    user = db.get(Usuario, user_id)
    if user is None or user.papelera_en is not None or user.estado_solicitud != "pendiente":
        raise HTTPException(status_code=404, detail="No existe una solicitud pendiente con ese ID.")
    user.estado_solicitud = "aprobada" if request.decision == "aprobar" else "rechazada"
    user.activo = request.decision == "aprobar"
    db.commit()
    db.refresh(user)
    return user


@router.patch("/usuarios/{user_id}/estado", response_model=UsuarioResponse)
def set_user_status(
    user_id: int,
    request: EstadoUsuario,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_principal_admin),
) -> Usuario:
    user = db.get(Usuario, user_id)
    if user is None or user.papelera_en is not None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if user.id == current.id and not request.activo:
        raise HTTPException(status_code=409, detail="No puedes desactivar tu propia sesión administrativa.")
    if user.rol == "admin" and not request.activo:
        raise HTTPException(status_code=409, detail="Las cuentas de administrador general están protegidas y no se pueden desactivar.")
    user.activo = request.activo
    db.commit()
    db.refresh(user)
    return user


@router.patch("/usuarios/{user_id}/rol", response_model=UsuarioResponse)
def set_user_role(
    user_id: int,
    request: RolUsuarioUpdate,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_principal_admin),
) -> Usuario:
    user = db.get(Usuario, user_id)
    if user is None or user.papelera_en is not None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if user.id == current.id and request.rol != user.rol:
        raise HTTPException(status_code=409, detail="No puedes cambiar tu propio rol de administrador.")
    if user.rol == "admin" and request.rol != "admin":
        raise HTTPException(status_code=409, detail="El rol de administrador general está protegido y no se puede cambiar.")
    user.rol = request.rol
    db.commit()
    db.refresh(user)
    return user


@router.get("/preguntas", response_model=list[PreguntaResponse])
def questions(
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> list[PreguntaFrecuente]:
    statement = select(PreguntaFrecuente).where(PreguntaFrecuente.papelera_en.is_(None)).order_by(PreguntaFrecuente.id.desc()).limit(500)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            PreguntaFrecuente.pregunta.like(pattern)
            | PreguntaFrecuente.respuesta.like(pattern)
            | PreguntaFrecuente.categoria.like(pattern)
            | PreguntaFrecuente.palabras_clave.like(pattern)
        )
    return list(db.scalars(statement))


@router.get("/categorias", response_model=list[str])
def categories(db: Session = Depends(get_db), _: Usuario = Depends(require_content_admin)) -> list[str]:
    return list(db.scalars(select(PreguntaFrecuente.categoria).distinct().order_by(PreguntaFrecuente.categoria)))


@router.get("/preguntas/paginadas", response_model=PreguntasPaginadasResponse)
def paginated_questions(
    q: str | None = Query(default=None, max_length=100),
    categoria: str | None = Query(default=None, max_length=50),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> dict[str, object]:
    statement = select(PreguntaFrecuente).where(PreguntaFrecuente.papelera_en.is_(None))
    count_statement = select(func.count()).select_from(PreguntaFrecuente).where(PreguntaFrecuente.papelera_en.is_(None))
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        condition = (
            PreguntaFrecuente.pregunta.like(pattern)
            | PreguntaFrecuente.respuesta.like(pattern)
            | PreguntaFrecuente.categoria.like(pattern)
            | PreguntaFrecuente.palabras_clave.like(pattern)
        )
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    if categoria and categoria.strip():
        condition = func.lower(PreguntaFrecuente.categoria) == categoria.strip().lower()
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    total = int(db.scalar(count_statement) or 0)
    items = list(db.scalars(
        statement.order_by(PreguntaFrecuente.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ))
    category_list = list(db.scalars(
        select(PreguntaFrecuente.categoria).distinct().order_by(PreguntaFrecuente.categoria)
    ))
    return {
        "items": items,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "paginas": (total + por_pagina - 1) // por_pagina,
        "categorias": category_list,
    }


@router.post("/preguntas", response_model=PreguntaResponse, status_code=status.HTTP_201_CREATED)
def create_question(
    request: PreguntaConDocumentoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> PreguntaFrecuente:
    attachments = _decode_request_attachments(request)
    values = request.model_dump(exclude=ATTACHMENT_FIELDS)
    faq = PreguntaFrecuente(**values)
    db.add(faq)
    stored_keys: list[str] = []
    documents: list[DocumentoInstitucional] = []
    try:
        db.flush()
        documents, stored_keys = _store_request_attachments(attachments, db, faq_id=faq.id)
        db.commit()
    except DocumentValidationError as error:
        db.rollback()
        for key in stored_keys:
            discard_pdf(key)
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception:
        db.rollback()
        for key in stored_keys:
            discard_pdf(key)
        raise
    db.refresh(faq)
    for document in documents:
        if document.mime_type == "application/pdf":
            background_tasks.add_task(enrich_document_index, document.id)
    return faq


@router.put("/preguntas/{faq_id}", response_model=PreguntaResponse)
def update_question(
    faq_id: int,
    request: PreguntaConDocumentoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> PreguntaFrecuente:
    faq = db.get(PreguntaFrecuente, faq_id)
    if faq is None or faq.papelera_en is not None:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada.")
    attachments = _decode_request_attachments(request)
    values = request.model_dump(exclude=ATTACHMENT_FIELDS)
    for key, value in values.items():
        setattr(faq, key, value)
    stored_keys: list[str] = []
    documents: list[DocumentoInstitucional] = []
    try:
        documents, stored_keys = _store_request_attachments(attachments, db, faq_id=faq.id)
        db.commit()
    except DocumentValidationError as error:
        db.rollback()
        for key in stored_keys:
            discard_pdf(key)
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception:
        db.rollback()
        for key in stored_keys:
            discard_pdf(key)
        raise
    db.refresh(faq)
    for document in documents:
        if document.mime_type == "application/pdf":
            background_tasks.add_task(enrich_document_index, document.id)
    return faq


@router.delete("/preguntas/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_question(faq_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_content_admin)) -> Response:
    faq = db.get(PreguntaFrecuente, faq_id)
    if faq is None or faq.papelera_en is not None:
        raise HTTPException(status_code=404, detail="Pregunta disponible no encontrada.")
    deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    faq.activo = False
    faq.papelera_en = deleted_at
    for document in faq.documentos:
        move_document_to_trash(document, deleted_at)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/avatar/accion/generar", response_model=GenerarAccionAvatarResponse)
def generate_avatar_action(
    request: GenerarAccionAvatarRequest,
    _: Usuario = Depends(require_content_admin),
) -> dict[str, str]:
    try:
        result = suggest_avatar_action(
            tipo=request.tipo,
            titulo=request.titulo,
            categoria=request.categoria,
            contenido=request.contenido,
            palabras_clave=request.palabras_clave,
            archivos=request.archivos,
        )
        return {**result, "metodo": "gemini"}
    except AvatarActionConfigurationError as error:
        logger.warning("Gemini no está disponible para sugerir animaciones; se usará la clasificación local (%s)", type(error).__name__)
    except AvatarActionServiceError as error:
        logger.warning("Gemini no respondió a la sugerencia de animación; se usará la clasificación local (%s)", type(error).__name__)
    content = f"{request.titulo} {request.categoria} {request.contenido[:12000]}"
    animation = default_avatar_animation(content)
    return {
        "accion_avatar": default_avatar_action(content),
        "animacion": animation,
        "emocion": "happy" if animation in {"Saludo", "Celebrar"} else "neutral",
        "metodo": "local",
    }


@router.get("/informacion", response_model=list[InformacionResponse])
def institutional_information(
    db: Session = Depends(get_db), _: Usuario = Depends(require_content_admin)
) -> list[InformacionInstitucional]:
    return list(db.scalars(
        select(InformacionInstitucional)
        .where(InformacionInstitucional.papelera_en.is_(None))
        .order_by(InformacionInstitucional.categoria, InformacionInstitucional.titulo)
    ))


@router.get("/papelera")
def list_trash(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_content_admin),
) -> dict[str, list[dict[str, object]]]:
    questions = list(db.scalars(
        select(PreguntaFrecuente)
        .where(PreguntaFrecuente.papelera_en.is_not(None))
        .order_by(PreguntaFrecuente.papelera_en.desc())
    ))
    information = list(db.scalars(
        select(InformacionInstitucional)
        .where(InformacionInstitucional.papelera_en.is_not(None))
        .order_by(InformacionInstitucional.papelera_en.desc())
    ))
    documents = db.execute(
        select(DocumentoInstitucional, InformacionInstitucional.titulo)
        .join(InformacionInstitucional, DocumentoInstitucional.informacion_id == InformacionInstitucional.id)
        .where(
            DocumentoInstitucional.papelera_en.is_not(None),
            InformacionInstitucional.papelera_en.is_(None),
        )
        .order_by(DocumentoInstitucional.papelera_en.desc())
    ).all()
    faq_documents = db.execute(
        select(DocumentoInstitucional, PreguntaFrecuente.pregunta)
        .join(PreguntaFrecuente, DocumentoInstitucional.pregunta_frecuente_id == PreguntaFrecuente.id)
        .where(
            DocumentoInstitucional.papelera_en.is_not(None),
            PreguntaFrecuente.papelera_en.is_(None),
        )
        .order_by(DocumentoInstitucional.papelera_en.desc())
    ).all()
    users = list(db.scalars(
        select(Usuario)
        .where(Usuario.papelera_en.is_not(None))
        .order_by(Usuario.papelera_en.desc())
    )) if current is not None and current.es_admin_principal else []
    contact_messages = list(db.scalars(
        select(MensajeContacto)
        .where(MensajeContacto.papelera_en.is_not(None))
        .order_by(MensajeContacto.papelera_en.desc())
    ))
    return {
        "preguntas": [{
            "id": item.id,
            "pregunta": item.pregunta,
            "categoria": item.categoria,
            "papelera_en": item.papelera_en,
        } for item in questions],
        "informacion": [{
            "id": item.id,
            "titulo": item.titulo,
            "categoria": item.categoria,
            "papelera_en": item.papelera_en,
            "tipo": "informacion",
        } for item in information],
        "documentos": [{
            "id": document.id,
            "nombre_archivo": document.nombre_archivo,
            "informacion_titulo": title,
            "papelera_en": document.papelera_en,
            "tipo": "documento",
        } for document, title in documents] + [{
            "id": document.id,
            "nombre_archivo": document.nombre_archivo,
            "informacion_titulo": question,
            "papelera_en": document.papelera_en,
            "tipo": "documento_pregunta",
        } for document, question in faq_documents],
        "usuarios": [{
            "id": user.id,
            "nombre": user.nombre,
            "correo": user.correo,
            "rol": user.rol,
            "activo": user.activo,
            "papelera_en": user.papelera_en,
        } for user in users],
        "mensajes_contacto": [{
            "id": item.id,
            "nombre": item.nombre,
            "correo": item.correo,
            "asunto": item.asunto,
            "papelera_en": item.papelera_en,
        } for item in contact_messages],
    }


@router.post("/preguntas/{faq_id}/papelera", status_code=status.HTTP_204_NO_CONTENT)
def trash_question(faq_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_content_admin)) -> Response:
    faq = db.get(PreguntaFrecuente, faq_id)
    if faq is None or faq.papelera_en is not None:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada.")
    deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    faq.activo = False
    faq.papelera_en = deleted_at
    for document in faq.documentos:
        move_document_to_trash(document, deleted_at)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/preguntas/{faq_id}/restaurar", status_code=status.HTTP_204_NO_CONTENT)
def restore_question(faq_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_content_admin)) -> Response:
    faq = db.get(PreguntaFrecuente, faq_id)
    if faq is None or faq.papelera_en is None:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada en la papelera.")
    deleted_at = faq.papelera_en
    faq.papelera_en = None
    faq.activo = True
    for document in faq.documentos:
        if document.papelera_en == deleted_at:
            document.papelera_en = None
            document.activo = True
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/informacion/{item_id}/papelera", status_code=status.HTTP_204_NO_CONTENT)
def trash_information(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_content_admin)) -> Response:
    item = db.get(InformacionInstitucional, item_id)
    if item is None or item.papelera_en is not None:
        raise HTTPException(status_code=404, detail="Información disponible no encontrada.")
    move_information_to_trash(item, db)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/informacion/{item_id}/restaurar", status_code=status.HTTP_204_NO_CONTENT)
def restore_trashed_information(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_content_admin)) -> Response:
    item = db.get(InformacionInstitucional, item_id)
    if item is None or item.papelera_en is None:
        raise HTTPException(status_code=404, detail="Información no encontrada en la papelera.")
    restore_information(item, db)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documentos/{document_id}/papelera", status_code=status.HTTP_204_NO_CONTENT)
def trash_document(document_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_content_admin)) -> Response:
    document = db.get(DocumentoInstitucional, document_id)
    if document is None or document.papelera_en is not None:
        raise HTTPException(status_code=404, detail="Documento disponible no encontrado.")
    move_document_to_trash(document)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documentos/{document_id}/restaurar", status_code=status.HTTP_204_NO_CONTENT)
def restore_trashed_document(document_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_content_admin)) -> Response:
    document = db.get(DocumentoInstitucional, document_id)
    if document is None or document.papelera_en is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado en la papelera.")
    if document.informacion_id is not None:
        parent = db.get(InformacionInstitucional, document.informacion_id)
        if parent is None or parent.papelera_en is not None:
            raise HTTPException(status_code=409, detail="Restaura primero la información institucional que contiene este archivo.")
    if document.pregunta_frecuente_id is not None:
        parent_question = db.get(PreguntaFrecuente, document.pregunta_frecuente_id)
        if parent_question is None or parent_question.papelera_en is not None:
            raise HTTPException(status_code=409, detail="Restaura primero la pregunta frecuente que contiene este archivo.")
    restore_document(document)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/informacion/analizar", response_model=ImportarInformacionResponse)
def analyze_information_document(
    request: ImportarInformacionRequest,
    _: Usuario = Depends(require_content_admin),
) -> dict[str, object]:
    if not request.contenido_publico_confirmado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirma que el documento contiene únicamente información pública y no sensible.",
        )
    try:
        filename = Path(request.nombre_archivo.replace("\\", "/")).name
        is_pdf = filename.lower().endswith(".pdf")
        source = extract_source_text(
            filename,
            request.texto,
            request.archivo_base64,
            allow_short_pdf=is_pdf,
        )
        title = filename.rsplit(".", 1)[0][:180] or "Documento institucional"
        drafts: list[dict[str, str]] = []
        analysis_warning = None
        analysis_completed = False

        def fallback_draft() -> dict[str, str] | None:
            content = source.strip()[:20_000]
            if len(content) < 40:
                return None
            fallback_title = title or "Información institucional"
            return {
                "clave": _stable_key(fallback_title, content),
                "titulo": fallback_title,
                "contenido": content,
                "categoria": "Información institucional",
                "animacion": "Explicar",
                "accion_avatar": "El lobo adopta una pose tranquila de explicación y acompaña la información con gestos suaves.",
                "emocion": "neutral",
            }

        try:
            if is_pdf and len(source) < 200 and request.archivo_base64:
                pdf_content = base64.b64decode(request.archivo_base64, validate=True)
                drafts = suggest_information_from_pdf(pdf_content)
                analysis_completed = True
            elif len(source) < 40:
                analysis_warning = "El documento contiene muy poco texto para proponer fichas."
            else:
                drafts = suggest_information(source)
                analysis_completed = True
            if analysis_completed and not drafts:
                fallback = fallback_draft()
                if fallback:
                    drafts = [fallback]
                    analysis_warning = "Se completó un borrador con el texto extraído; revisa el contenido antes de guardarlo."
                else:
                    analysis_warning = "No se encontró texto legible en el documento."
        except (GeminiConfigurationError, GeminiServiceError, ImportValidationError) as error:
            fallback = fallback_draft()
            if fallback:
                drafts = [fallback]
                analysis_warning = "La IA no respondió; se completó el borrador con el texto extraído. Revisa la información."
            else:
                analysis_warning = str(error)
        return {
            "borradores": drafts,
            "fuente_guardada": False,
            "fuente_ya_existia": False,
            "fuente_activa": False,
            "fuente_titulo": title,
            "aviso_analisis": analysis_warning,
            "analisis_gemini": analysis_completed,
            "analisis_visual_gemini": False,
            "analisis_visual_pendiente": False,
        }
    except ImportValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except (DocumentValidationError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.post("/informacion/importar", response_model=ImportarInformacionResponse)
def draft_information_from_document(
    request: ImportarInformacionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> dict[str, object]:
    if not request.contenido_publico_confirmado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirma que el documento contiene únicamente información pública y no sensible.",
        )
    try:
        filename = Path(request.nombre_archivo.replace("\\", "/")).name
        is_pdf = filename.lower().endswith(".pdf")
        source = extract_source_text(
            request.nombre_archivo,
            request.texto,
            request.archivo_base64,
            allow_short_pdf=is_pdf,
        )
        key = _stable_key(f"fuente-{filename}", source)
        analysis_warning = None
        analysis_completed = False
        pending_visual_analysis = False
        if is_pdf:
            pdf_content = base64.b64decode(request.archivo_base64, validate=True)
            pending_visual_analysis = True

        title = filename.rsplit(".", 1)[0][:180] or "Documento institucional"
        existing = db.scalar(select(InformacionInstitucional).where(InformacionInstitucional.clave == key))
        was_existing = existing is not None
        is_active = existing.activo if existing is not None else True
        document_for_indexing = None
        if existing is not None and is_pdf:
            existing_document = db.scalar(
                select(DocumentoInstitucional).where(
                    DocumentoInstitucional.informacion_id == existing.id,
                    DocumentoInstitucional.nombre_archivo == filename,
                    DocumentoInstitucional.activo.is_(True),
                )
            )
            if existing_document is not None:
                existing_document.contenido_extraido = source
                existing_document.estado_indice = "pendiente"
                document_for_indexing = existing_document.id
                db.commit()
        if existing is None:
            item = InformacionInstitucional(
                clave=key,
                titulo=title,
                contenido=(
                    f"Documento público adjunto: {filename}. El contenido íntegro está disponible para consultas."
                    if is_pdf else source
                ),
                categoria="Documentos institucionales",
                activo=True,
            )
            stored_key = None
            try:
                db.add(item)
                db.flush()
                if is_pdf:
                    stored_key, safe_name = store_pdf(filename, pdf_content)
                    indexed_document = DocumentoInstitucional(
                        informacion_id=item.id,
                        nombre_archivo=safe_name,
                        archivo_key=stored_key,
                        mime_type="application/pdf",
                        tamano_bytes=len(pdf_content),
                        contenido_extraido=source,
                        activo=True,
                        estado_indice="pendiente",
                    )
                    db.add(indexed_document)
                db.commit()
                if is_pdf:
                    db.refresh(indexed_document)
                    document_for_indexing = indexed_document.id
            except Exception:
                db.rollback()
                if stored_key:
                    discard_pdf(stored_key)
                raise

        if document_for_indexing is not None:
            background_tasks.add_task(enrich_document_index, document_for_indexing)

        drafts = []
        if len(source) >= 40:
            try:
                drafts = suggest_information(source)
            except (GeminiConfigurationError, GeminiServiceError) as error:
                analysis_warning = "; ".join(filter(None, [analysis_warning, str(error)]))
        return {
            "borradores": drafts,
            "fuente_guardada": is_active,
            "fuente_ya_existia": was_existing,
            "fuente_activa": is_active,
            "fuente_titulo": existing.titulo if existing is not None else title,
            "aviso_analisis": analysis_warning,
            "analisis_gemini": analysis_completed,
            "analisis_visual_gemini": analysis_completed and is_pdf,
            "analisis_visual_pendiente": pending_visual_analysis and document_for_indexing is not None,
        }
    except ImportValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except (DocumentValidationError, ValueError) as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.post("/informacion", response_model=InformacionResponse, status_code=status.HTTP_201_CREATED)
def create_information(
    request: InformacionCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> InformacionInstitucional:
    item = InformacionInstitucional(**request.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe información con esa clave.") from error
    db.refresh(item)
    return item


@router.post("/informacion/con-documento", response_model=InformacionResponse, status_code=status.HTTP_201_CREATED)
def create_information_with_optional_pdf(
    request: InformacionConDocumentoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> InformacionInstitucional:
    attachments = _decode_request_attachments(request)
    analysis_completed = False
    item = InformacionInstitucional(**request.model_dump(exclude=ATTACHMENT_FIELDS))
    stored_keys: list[str] = []
    documents: list[DocumentoInstitucional] = []
    try:
        db.add(item)
        db.flush()
        documents, stored_keys = _store_request_attachments(attachments, db, information_id=item.id)
        db.commit()
    except DocumentValidationError as error:
        db.rollback()
        for key in stored_keys:
            discard_pdf(key)
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        db.rollback()
        for key in stored_keys:
            discard_pdf(key)
        raise HTTPException(status_code=409, detail="Ya existe información con esa clave.") from error
    except Exception:
        db.rollback()
        for key in stored_keys:
            discard_pdf(key)
        raise
    db.refresh(item)
    for document in documents:
        if document.mime_type == "application/pdf":
            background_tasks.add_task(enrich_document_index, document.id)
    return InformacionResponse.model_validate(item).model_copy(update={"analisis_gemini": analysis_completed})


@router.delete("/documentos/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_institutional_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> Response:
    document = db.get(DocumentoInstitucional, document_id)
    if document is None or not document.activo:
        raise HTTPException(status_code=404, detail="Documento activo no encontrado.")
    document.activo = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/documentos/{document_id}/permanente", status_code=status.HTTP_204_NO_CONTENT)
def delete_institutional_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> Response:
    document = db.get(DocumentoInstitucional, document_id)
    if document is None or document.papelera_en is not None:
        raise HTTPException(status_code=404, detail="Documento disponible no encontrado.")
    move_document_to_trash(document)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/informacion/{item_id}", response_model=InformacionResponse)
def update_information(
    item_id: int,
    request: InformacionConDocumentoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> InformacionInstitucional:
    item = db.get(InformacionInstitucional, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Información institucional no encontrada.")
    attachments = _decode_request_attachments(request)
    fields = request.model_dump(exclude=ATTACHMENT_FIELDS)
    for key, value in fields.items():
        setattr(item, key, value)
    stored_keys: list[str] = []
    documents: list[DocumentoInstitucional] = []
    try:
        documents, stored_keys = _store_request_attachments(attachments, db, information_id=item.id)
        db.commit()
    except DocumentValidationError as error:
        db.rollback()
        for key in stored_keys:
            discard_pdf(key)
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        db.rollback()
        for key in stored_keys:
            discard_pdf(key)
        raise HTTPException(status_code=409, detail="Ya existe información con esa clave.") from error
    except Exception:
        db.rollback()
        for key in stored_keys:
            discard_pdf(key)
        raise
    db.refresh(item)
    for document in documents:
        if document.mime_type == "application/pdf":
            background_tasks.add_task(enrich_document_index, document.id)
    return item


@router.delete("/informacion/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_information(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_content_admin)) -> Response:
    item = db.get(InformacionInstitucional, item_id)
    if item is None or not item.activo:
        raise HTTPException(status_code=404, detail="Información activa no encontrada.")
    item.activo = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/historial", response_model=list[HistorialResponse])
def interaction_history(
    limite: int = Query(default=100, ge=1, le=500),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_content_admin),
) -> list[HistorialConsulta]:
    statement = select(HistorialConsulta)
    if desde:
        statement = statement.where(func.date(HistorialConsulta.fecha_consulta) >= desde)
    if hasta:
        statement = statement.where(func.date(HistorialConsulta.fecha_consulta) <= hasta)
    return list(db.scalars(statement.order_by(HistorialConsulta.fecha_consulta.desc()).limit(limite)))


@router.delete("/historial")
def purge_interaction_history(
    desde: date = Query(...),
    hasta: date = Query(...),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_admin),
) -> dict[str, int]:
    if desde > hasta:
        raise HTTPException(status_code=422, detail="La fecha inicial no puede ser posterior a la fecha final.")
    result = db.execute(delete(HistorialConsulta).where(
        func.date(HistorialConsulta.fecha_consulta) >= desde,
        func.date(HistorialConsulta.fecha_consulta) <= hasta,
    ))
    db.commit()
    return {"eliminados": int(result.rowcount or 0)}

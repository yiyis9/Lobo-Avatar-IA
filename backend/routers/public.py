import logging

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from models import DocumentoInstitucional, HistorialConsulta, InformacionInstitucional, MensajeContacto, PreguntaFrecuente
from schemas import (
    ChatRequest,
    ChatResponse,
    ContactoCreate,
    DocumentoPublicoResponse,
    InformacionPublicaResponse,
    PreguntaResponse,
    VoiceSynthesisRequest,
    VoiceTranscriptionResponse,
)
from services.institutional_documents import UPLOAD_DIRECTORY
from services.chat import answer_and_record, relevant_document_excerpt
from services.gemini_voice import (
    MAX_TRANSCRIPTION_BYTES,
    VoiceConfigurationError,
    VoiceServiceError,
    synthesize_speech,
    synthesize_speech_stream,
    transcribe_wav,
)
from services.contact_events import publish_new_contact


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Kiosko público"])


@router.post("/contacto", status_code=status.HTTP_201_CREATED)
def create_contact_message(request: ContactoCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    # Campo trampa para reducir envíos automatizados; las personas no lo ven.
    if request.website:
        return {"mensaje": "Gracias por contactar a la UPVT. Tu mensaje fue recibido."}
    item = MensajeContacto(
        nombre=request.nombre,
        correo=request.correo,
        asunto=request.asunto,
        mensaje=request.mensaje,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    publish_new_contact(item.id, item.nombre)
    return {"mensaje": "Gracias por contactar a la UPVT. Tu mensaje fue recibido."}


@router.post("/voz/transcribir", response_model=VoiceTranscriptionResponse)
async def transcribe_public_voice(request: Request) -> VoiceTranscriptionResponse:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"audio/wav", "audio/x-wav"}:
        raise HTTPException(status_code=415, detail="Envía una grabación WAV.")
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_TRANSCRIPTION_BYTES:
        raise HTTPException(status_code=413, detail="La grabación supera el límite permitido.")
    audio = await request.body()
    if len(audio) > MAX_TRANSCRIPTION_BYTES:
        raise HTTPException(status_code=413, detail="La grabación supera el límite permitido.")
    try:
        transcript = transcribe_wav(audio)
        return VoiceTranscriptionResponse(transcripcion=transcript)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except VoiceConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except VoiceServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/voz/sintetizar")
def synthesize_public_voice(request: VoiceSynthesisRequest) -> Response:
    try:
        audio = synthesize_speech(request.texto)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except VoiceConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except VoiceServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/voz/sintetizar/stream")
def stream_public_voice(request: VoiceSynthesisRequest) -> StreamingResponse:
    try:
        chunks = synthesize_speech_stream(request.texto)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except VoiceConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except VoiceServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return StreamingResponse(
        chunks,
        media_type="audio/l16; rate=24000; channels=1",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/informacion", response_model=list[InformacionPublicaResponse])
def list_public_information(
    q: str | None = Query(default=None, max_length=100),
    categoria: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
) -> list[InformacionInstitucional]:
    statement = select(InformacionInstitucional).where(InformacionInstitucional.activo.is_(True))
    if categoria and categoria.strip():
        statement = statement.where(func.lower(InformacionInstitucional.categoria) == categoria.strip().lower())
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(InformacionInstitucional.titulo.like(pattern), InformacionInstitucional.contenido.like(pattern),
                InformacionInstitucional.categoria.like(pattern), InformacionInstitucional.clave.like(pattern))
        )
    return list(db.scalars(statement.order_by(InformacionInstitucional.categoria, InformacionInstitucional.titulo).limit(200)))


@router.get("/preguntas", response_model=list[PreguntaResponse])
def list_public_questions(
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
) -> list[PreguntaFrecuente]:
    statement = select(PreguntaFrecuente).where(
        PreguntaFrecuente.activo.is_(True),
        PreguntaFrecuente.papelera_en.is_(None),
        PreguntaFrecuente.dirigido_a == "todos",
    )
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(PreguntaFrecuente.pregunta.like(pattern), PreguntaFrecuente.palabras_clave.like(pattern),
                PreguntaFrecuente.categoria.like(pattern))
        )
    items = list(db.scalars(statement.order_by(PreguntaFrecuente.categoria, PreguntaFrecuente.id).limit(200)))
    return [{
        "id": item.id,
        "categoria": item.categoria,
        "pregunta": item.pregunta,
        "respuesta": item.respuesta,
        "palabras_clave": item.palabras_clave,
        "accion_avatar": item.accion_avatar,
        "dirigido_a": item.dirigido_a,
        "animacion": item.animacion,
        "emocion": item.emocion,
        "activo": item.activo,
        "creado_en": item.creado_en,
        "documentos": [document for document in item.documentos if document.activo and document.papelera_en is None],
    } for item in items]


@router.get("/documentos", response_model=list[DocumentoPublicoResponse])
def list_public_documents(
    q: str = Query(min_length=2, max_length=100),
    db: Session = Depends(get_db),
) -> list[dict[str, str | int]]:
    rows = db.execute(
        select(DocumentoInstitucional, InformacionInstitucional)
        .join(InformacionInstitucional, DocumentoInstitucional.informacion_id == InformacionInstitucional.id)
        .where(DocumentoInstitucional.activo.is_(True), InformacionInstitucional.activo.is_(True))
        .order_by(InformacionInstitucional.categoria, InformacionInstitucional.titulo, DocumentoInstitucional.nombre_archivo)
        .limit(200)
    ).all()
    matching = []
    for document, information in rows:
        score, _ = relevant_document_excerpt(
            q,
            f"{information.titulo}\n{document.nombre_archivo}\n{information.categoria}\n{document.contenido_extraido or ''}",
        )
        if score < 10:
            continue
        matching.append({
            "id": document.id,
            "nombre_archivo": document.nombre_archivo,
            "mime_type": document.mime_type,
            "tamano_bytes": document.tamano_bytes,
            "titulo_informacion": information.titulo,
            "categoria": information.categoria,
            "url": document.url,
        })
    return matching[:10]


@router.get("/documentos/{document_id}/archivo")
def get_public_document(document_id: int, db: Session = Depends(get_db)) -> FileResponse:
    document = db.scalar(
        select(DocumentoInstitucional)
        .outerjoin(InformacionInstitucional, DocumentoInstitucional.informacion_id == InformacionInstitucional.id)
        .outerjoin(PreguntaFrecuente, DocumentoInstitucional.pregunta_frecuente_id == PreguntaFrecuente.id)
        .where(
            DocumentoInstitucional.id == document_id,
            DocumentoInstitucional.activo.is_(True),
            or_(
                and_(
                    DocumentoInstitucional.informacion_id.is_not(None),
                    InformacionInstitucional.activo.is_(True),
                    InformacionInstitucional.papelera_en.is_(None),
                ),
                and_(
                    DocumentoInstitucional.pregunta_frecuente_id.is_not(None),
                    PreguntaFrecuente.activo.is_(True),
                    PreguntaFrecuente.papelera_en.is_(None),
                ),
            ),
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Documento público no encontrado.")
    extension = Path(document.nombre_archivo).suffix.lower()
    if extension not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=404, detail="El archivo no está disponible.")
    file_path = UPLOAD_DIRECTORY / f"{document.archivo_key}{extension}"
    if not file_path.is_file() or file_path.parent != UPLOAD_DIRECTORY:
        raise HTTPException(status_code=404, detail="El archivo no está disponible.")
    return FileResponse(
        path=file_path,
        media_type=document.mime_type,
        filename=document.nombre_archivo,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    try:
        return answer_and_record(db, request.mensaje, request.contexto, request.request_id)
    except IntegrityError as error:
        db.rollback()
        if request.request_id:
            existing = db.scalar(select(HistorialConsulta).where(HistorialConsulta.clave_solicitud == request.request_id))
            if existing is not None:
                return ChatResponse(
                    respuesta=existing.respuesta,
                    accion_avatar=existing.accion_avatar,
                    animacion=existing.animacion,
                    emocion=existing.emocion,
                    consulta_id=existing.id,
                )
        logger.exception("No se pudo guardar la consulta pública")
        raise HTTPException(status_code=503, detail="El servicio de consultas no está disponible temporalmente.") from error
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("No se pudo resolver o registrar la consulta pública")
        raise HTTPException(status_code=503, detail="El servicio de consultas no está disponible temporalmente.") from error

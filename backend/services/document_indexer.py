import logging

from sqlalchemy import select

from database import SessionLocal
from models import DocumentoInstitucional, InformacionInstitucional, PreguntaFrecuente
from services.gemini_import import GeminiConfigurationError, GeminiServiceError, analyze_pdf_for_search
from services.institutional_documents import UPLOAD_DIRECTORY


logger = logging.getLogger(__name__)


def enrich_document_index(document_id: int) -> None:
    """Enhance the already searchable native PDF text after the upload response."""
    with SessionLocal() as db:
        document = db.get(DocumentoInstitucional, document_id)
        if document is None or document.papelera_en is not None:
            return
        pdf_path = UPLOAD_DIRECTORY / f"{document.archivo_key}.pdf"
        if not pdf_path.is_file() or pdf_path.parent != UPLOAD_DIRECTORY:
            document.estado_indice = "error"
            db.commit()
            return
        native_text = (document.contenido_extraido or "").strip()
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
        try:
            enriched_text = analyze_pdf_for_search(
                pdf_path.read_bytes(),
                native_text,
                associated_context="\n".join(context_lines),
            )
            document.contenido_extraido = enriched_text
            document.estado_indice = "listo"
        except (GeminiConfigurationError, GeminiServiceError):
            logger.exception("No se pudo enriquecer en segundo plano el índice del documento %s", document.id)
            document.estado_indice = "listo" if len(native_text) >= 40 else "error"
        except Exception:
            logger.exception("Error al indexar en segundo plano el documento %s", document.id)
            document.estado_indice = "listo" if len(native_text) >= 40 else "error"
        db.commit()

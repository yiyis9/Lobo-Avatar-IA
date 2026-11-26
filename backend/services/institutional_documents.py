import re
import io
from pathlib import Path
from uuid import uuid4


MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 1000
MAX_EXTRACTED_CHARS = 120_000
UPLOAD_DIRECTORY = Path(__file__).resolve().parents[1] / "uploads" / "institutional"
ALLOWED_IMAGE_TYPES = {
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".webp": ("image/webp", lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"),
}


class DocumentValidationError(ValueError):
    pass


def extract_pdf_text(content: bytes) -> str:
    if len(content) > MAX_PDF_BYTES or not content.startswith(b"%PDF-"):
        raise DocumentValidationError("El archivo no parece ser un PDF válido o supera el límite de 10 MB.")
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise DocumentValidationError("El PDF está protegido y no se puede indexar.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise DocumentValidationError("El PDF supera el límite de 1000 páginas admitido por Gemini.")
        parts = []
        total = 0
        for page in reader.pages:
            page_text = (page.extract_text() or "").strip()
            if not page_text:
                continue
            remaining = MAX_EXTRACTED_CHARS - total
            if remaining <= 0:
                break
            parts.append(page_text[:remaining])
            total += min(len(page_text), remaining)
        return "\n\n".join(parts).strip()
    except DocumentValidationError:
        raise
    except ImportError as error:
        raise DocumentValidationError("Falta instalar pypdf. Ejecuta pip install -r requirements.txt.") from error
    except Exception as error:
        raise DocumentValidationError("No se pudo extraer el texto del PDF.") from error


def store_pdf(filename: str | None, content: bytes) -> tuple[str, str]:
    safe_name = Path(filename or "").name
    safe_name = re.sub(r"[\x00-\x1f\x7f]", "", safe_name).strip()
    if not safe_name or len(safe_name) > 255 or Path(safe_name).suffix.lower() != ".pdf":
        raise DocumentValidationError("Adjunta un archivo PDF válido.")
    if len(content) > MAX_PDF_BYTES:
        raise DocumentValidationError("El PDF supera el límite de 10 MB.")
    if not content.startswith(b"%PDF-"):
        raise DocumentValidationError("El archivo no parece ser un PDF válido.")

    key = str(uuid4())
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIRECTORY / f"{key}.pdf").write_bytes(content)
    return key, safe_name


def store_institutional_file(filename: str | None, content: bytes) -> tuple[str, str, str, str | None]:
    safe_name = Path(filename or "").name
    safe_name = re.sub(r"[\x00-\x1f\x7f]", "", safe_name).strip()
    extension = Path(safe_name).suffix.lower()
    if not safe_name or len(safe_name) > 255:
        raise DocumentValidationError("El nombre del archivo no es válido.")
    if len(content) > MAX_PDF_BYTES:
        raise DocumentValidationError("El archivo supera el límite de 10 MB.")

    extracted_text = None
    if extension == ".pdf":
        extracted_text = extract_pdf_text(content)
        mime_type = "application/pdf"
    elif extension in ALLOWED_IMAGE_TYPES:
        mime_type, validate_signature = ALLOWED_IMAGE_TYPES[extension]
        if not validate_signature(content):
            raise DocumentValidationError("El contenido del archivo no coincide con el tipo de imagen declarado.")
    else:
        raise DocumentValidationError("Formato no admitido. Adjunta un PDF, PNG, JPG o WEBP.")

    key = str(uuid4())
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIRECTORY / f"{key}{extension}").write_bytes(content)
    return key, safe_name, mime_type, extracted_text


def discard_pdf(key: str) -> None:
    for extension in (".pdf", *ALLOWED_IMAGE_TYPES.keys()):
        path = UPLOAD_DIRECTORY / f"{key}{extension}"
        if path.parent == UPLOAD_DIRECTORY and path.exists():
            path.unlink()

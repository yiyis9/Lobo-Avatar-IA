"""Analyze and persist avatar animation metadata for current content."""

import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import select

from database import SessionLocal
from models import DocumentoInstitucional, InformacionInstitucional, PreguntaFrecuente
from services.chat import default_avatar_action, default_avatar_animation
from services.gemini_avatar import (
    AvatarActionConfigurationError,
    AvatarActionServiceError,
    suggest_avatar_action,
)


PRIVATE_DETAIL_TITLES = re.compile(r"directorio|padr[oó]n|resguardatario|financier|privacidad|matriz", re.I)
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
CURP = re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b", re.I)
RFC = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b", re.I)
LONG_ID = re.compile(r"\b(?=[A-Z0-9-]{8,24}\b)(?=[A-Z0-9-]*\d)[A-Z0-9-]+\b", re.I)
PHONE = re.compile(r"(?<!\w)(?:\+?52[\s().-]?)?(?:\d[\s().-]?){10,13}(?!\w)")


def redact(value: str) -> tuple[str, int]:
    substitutions = 0
    for pattern, replacement in (
        (EMAIL, "[correo omitido]"),
        (PHONE, "[teléfono omitido]"),
        (CURP, "[identificador omitido]"),
        (RFC, "[identificador omitido]"),
        (LONG_ID, "[identificador omitido]"),
    ):
        value, count = pattern.subn(replacement, value)
        substitutions += count
    return value, substitutions


def make_payload(kind: str, title: str, category: str, content: str) -> tuple[dict[str, str], int, bool]:
    safe_title, redactions = redact(title[:255])
    safe_category, count = redact(category[:80])
    redactions += count
    restricted = bool(PRIVATE_DETAIL_TITLES.search(f"{title} {category}"))
    if restricted:
        safe_content = "Contenido omitido por privacidad; determina el tipo de interacción usando solo el título y la categoría."
    else:
        safe_content, count = redact(content[:3500])
        redactions += count
    payload = {
        "tipo": kind,
        "titulo": safe_title,
        "categoria": safe_category,
        "contenido": safe_content[:3500],
    }
    return payload, redactions, restricted


def validate_payloads(payloads: list[dict[str, str]]) -> None:
    for index, payload in enumerate(payloads, start=1):
        if len(payload["contenido"]) > 3500:
            raise RuntimeError(f"El fragmento {index} excede el máximo autorizado.")
        if "@" in payload["titulo"] or "@" in payload["categoria"] or "@" in payload["contenido"]:
            raise RuntimeError(f"El fragmento {index} conserva un posible correo electrónico.")
        if EMAIL.search(payload["titulo"] + payload["categoria"] + payload["contenido"]):
            raise RuntimeError(f"El fragmento {index} conserva un correo electrónico.")
        if CURP.search(payload["titulo"] + payload["categoria"] + payload["contenido"]):
            raise RuntimeError(f"El fragmento {index} conserva una CURP.")
        if RFC.search(payload["titulo"] + payload["categoria"] + payload["contenido"]):
            raise RuntimeError(f"El fragmento {index} conserva un RFC.")
        if PHONE.search(payload["titulo"] + payload["categoria"] + payload["contenido"]):
            raise RuntimeError(f"El fragmento {index} conserva un posible teléfono.")
        if LONG_ID.search(payload["titulo"] + payload["categoria"] + payload["contenido"]):
            raise RuntimeError(f"El fragmento {index} conserva un posible identificador.")


def fallback(title: str, category: str, content: str) -> dict[str, str]:
    material = f"{title} {category} {content}"
    animation = default_avatar_animation(material)
    return {
        "accion_avatar": default_avatar_action(material),
        "animacion": animation,
        "emocion": "happy" if animation in {"Saludo", "Celebrar"} else "neutral",
    }


def main() -> None:
    with SessionLocal() as db:
        information = list(db.scalars(select(InformacionInstitucional).order_by(InformacionInstitucional.id)))
        questions = list(db.scalars(select(PreguntaFrecuente).order_by(PreguntaFrecuente.id)))
        information_ids = [item.id for item in information]
        question_ids = [item.id for item in questions]
        info_documents: dict[int, list[DocumentoInstitucional]] = {}
        question_documents: dict[int, list[DocumentoInstitucional]] = {}
        if information_ids:
            for document in db.scalars(select(DocumentoInstitucional).where(
                DocumentoInstitucional.informacion_id.in_(information_ids)
            ).order_by(DocumentoInstitucional.id)):
                info_documents.setdefault(int(document.informacion_id), []).append(document)
        if question_ids:
            for document in db.scalars(select(DocumentoInstitucional).where(
                DocumentoInstitucional.pregunta_frecuente_id.in_(question_ids)
            ).order_by(DocumentoInstitucional.id)):
                question_documents.setdefault(int(document.pregunta_frecuente_id), []).append(document)

        records = []
        for item in information:
            source = "\n".join([item.contenido, *[
                document.contenido_extraido or "" for document in info_documents.get(item.id, [])[:3]
            ]])
            payload, redactions, restricted = make_payload("informacion", item.titulo, item.categoria, source)
            records.append((item, payload, redactions, restricted))
        for item in questions:
            source = "\n".join([item.respuesta, *[
                document.contenido_extraido or "" for document in question_documents.get(item.id, [])[:3]
            ]])
            payload, redactions, restricted = make_payload("pregunta", item.pregunta, item.categoria, source)
            records.append((item, payload, redactions, restricted))

        payloads = [record[1] for record in records]
        validate_payloads(payloads)
        redaction_count = sum(record[2] for record in records)
        restricted_count = sum(1 for record in records if record[3])
        max_content_chars = max((len(payload["contenido"]) for payload in payloads), default=0)
        print(
            f"Preflight verificado: {len(records)} fichas; máximo {max_content_chars} caracteres; "
            f"{redaction_count} redacciones; {restricted_count} fichas solo con título/categoría.",
            flush=True,
        )
        if "--preflight" in sys.argv:
            return

        if "--local-only" in sys.argv:
            results = {
                index: (fallback(payload["titulo"], payload["categoria"], payload["contenido"]), "local")
                for index, (_, payload, _, _) in enumerate(records)
            }
            print("Asignando clips con el clasificador local; no se contactará a Gemini.", flush=True)
        else:
            results = None

        def analyze(index: int, record: tuple) -> tuple[int, dict[str, str], str]:
            item, payload, _, _ = record
            try:
                result = suggest_avatar_action(
                    tipo=payload["tipo"],
                    titulo=payload["titulo"],
                    categoria=payload["categoria"],
                    contenido=payload["contenido"],
                    palabras_clave="",
                    archivos=[],
                )
                return index, result, "Gemini"
            except (AvatarActionConfigurationError, AvatarActionServiceError) as error:
                print(f"Gemini falló en ficha #{item.id} ({type(error).__name__}); se usará clasificación local.", flush=True)
                return index, fallback(payload["titulo"], payload["categoria"], payload["contenido"]), "local"

        if results is None:
            results = {}
            with ThreadPoolExecutor(max_workers=4) as executor:
                pending = {
                    executor.submit(analyze, index, record): index
                    for index, record in enumerate(records)
                }
                for completed, future in enumerate(as_completed(pending), start=1):
                    index, suggestion, method = future.result()
                    results[index] = (suggestion, method)
                    item = records[index][0]
                    print(f"Análisis {completed}/{len(records)}: ficha #{item.id} ({method})", flush=True)

        gemini_count = sum(method == "Gemini" for _, method in results.values())
        local_count = len(results) - gemini_count
        with SessionLocal() as write_db:
            for index, (item, _, _, _) in enumerate(records):
                model = InformacionInstitucional if index < len(information) else PreguntaFrecuente
                target = write_db.get(model, item.id)
                if target is None:
                    continue
                suggestion, _ = results[index]
                target.animacion = suggestion["animacion"]
                target.accion_avatar = suggestion["accion_avatar"]
                target.emocion = suggestion["emocion"]
            write_db.commit()

        print(f"Finalizado: {gemini_count} análisis de Gemini, {local_count} asignaciones locales.", flush=True)


if __name__ == "__main__":
    main()

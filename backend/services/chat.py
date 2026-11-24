import logging
import re
import unicodedata
from urllib.parse import urlsplit

from sqlalchemy import or_, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from models import DocumentoInstitucional, HistorialConsulta, InformacionInstitucional, PreguntaFrecuente
from schemas import ChatResponse, ChatTurn, PreguntaAdjuntoResponse
from services.gemini_chat import generate_grounded_answer


logger = logging.getLogger(__name__)


STOP_WORDS = {"como", "cuando", "donde", "cual", "cuales", "que", "hay", "para", "por", "una", "uno", "del", "los", "las", "con", "esta", "este", "son", "ser", "de", "la", "el", "en", "se", "me", "mi", "su"}
TOKEN_ALIASES = {
    "cuatri": "cuatrimestre",
    "cuatrimestres": "cuatrimestre",
    "cia": "comercio",
    "ti": "tecnologia",
    "tic": "tecnologia",
    "tics": "tecnologia",
    "tecnologias": "tecnologia",
    "materias": "materia",
    "asignatura": "materia",
    "asignaturas": "materia",
    "primero": "1", "primer": "1", "primera": "1",
    "segundo": "2", "segunda": "2",
    "tercero": "3", "tercer": "3", "tercera": "3",
    "cuarto": "4", "cuarta": "4",
    "quinto": "5", "quinta": "5",
    "sexto": "6", "sexta": "6",
    "septimo": "7", "septima": "7",
    "octavo": "8", "octava": "8",
    "noveno": "9", "novena": "9",
    "decimo": "10", "decima": "10",
    "curriculas": "curricular", "curriculum": "curricular",
    "malla": "curricular", "mallas": "curricular",
    "reticula": "curricular", "reticulas": "curricular", "pensum": "curricular",
}
PROGRAM_TERMS = {
    "tecnologia", "informacion", "software", "industrial", "mecatronica", "biotecnologia",
    "automotriz", "energia", "sostenible", "comercio", "aduanas", "logistica", "procesos",
    "productivos", "multiplataforma", "innovacion", "digital",
}
GENERIC_PROGRAM_TERMS = {
    "mapa", "curricular", "carrera", "carreras", "programa", "programas", "ingenieria",
    "licenciatura", "estudio", "estudios", "materia", "cuatrimestre", "tsu",
}
CURRICULUM_TERMS = {"mapa", "curricular", "cuatrimestre", "materia", "asignatura", "plan", "estudio"}
CURRICULUM_METADATA_TERMS = ("mapa", "curricular", "malla", "reticula", "plan de estudio", "pensum")
LOCATION_QUERY_TERMS = {"ubicacion", "direccion", "llegar", "maps", "campus", "sede", "localizacion"}
LOCATION_METADATA_TERMS = {
    "ubicacion", "direccion", "llegar", "mapa", "maps", "campus", "sede",
    "donde", "esta", "ubica", "ubican", "ubicado", "ubicada", "encuentra", "encuentran",
}
NO_ANSWER = "¡Con gusto te ayudo! Aún no encuentro ese dato en la información de la UPVT. Puedes preguntarme por carreras, inscripciones, servicios o ubicación."
KEYWORD_SECTION_LABEL = "palabras clave para busqueda"


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def tokens(value: str) -> set[str]:
    words = normalize(value).split()
    normalized = {TOKEN_ALIASES.get(word, word) for word in words}
    return {word for word in normalized if (len(word) > 2 or word.isdigit()) and word not in STOP_WORDS}


def expanded_search_terms(value: str) -> set[str]:
    """Keep user-entered acronyms alongside their normalized aliases for SQL retrieval."""
    raw_words = set(normalize(value).split())
    normalized_words = tokens(value)
    aliases_used = {
        word for word in raw_words
        if TOKEN_ALIASES.get(word) in normalized_words and len(word) > 2
    }
    return normalized_words | aliases_used


def casual_response(message: str) -> tuple[str, str, str] | None:
    """Handle common social turns without treating them as failed knowledge searches."""
    text_value = normalize(message)
    # Edge speech recognition sometimes transcribes "hola" as "hoña";
    # NFKD removes the tilde, so normalize that common ASR variation too.
    text_value = re.sub(r"\bhona\b", "hola", text_value)
    text_value = re.sub(r"\bq\b", "que", text_value)
    if text_value in {"el visitante saludo con la mano", "el visitante saludo", "saludo detectado por camara"}:
        return "¡Hola! Vi tu saludo. ¿En qué te puedo ayudar?", "greeting", "happy"
    command = re.sub(r"[^a-z0-9 ]", " ", text_value)
    command = re.sub(r"\s+", " ", command).strip()
    if len(command.split()) <= 12 and (
        re.search(r"\b(lobo|avatar)\b", command)
        or re.fullmatch(r"(por favor )?(puedes )?(saluda|saludar|salude|saludame|baila|bailar|celebra|celebrar|piensa|pensar)( por favor)?", command)
    ):
        if re.search(r"\b(saluda|saludar|salude|saludame|di hola|manda un saludo)\b", command):
            return "¡Claro! Te mando un saludo.", "greeting", "happy"
        if re.search(r"\b(baila|bailar|celebra|celebrar|festeja|festejar)\b", command):
            return "¡Vamos a celebrar!", "celebrate", "happy"
        if re.search(r"\b(piensa|pensar|piense|medita|meditar)\b", command):
            return "Déjame pensarlo un momento.", "thinking", "neutral"
    greeting_prefix = (
        r"^(?:(?:hola|ola|holi|oli|hey|ey|saludos|buenas tardes|buenas noches|"
        r"buenos dias|buen dia|buenas)(?: lobo)?\s*)+"
    )
    social_text = re.sub(greeting_prefix, "", text_value).strip()
    has_greeting_prefix = social_text != text_value
    social_text = social_text or text_value
    if re.fullmatch(
        r"(?:como estas|como esta|como te encuentras|como te va|como andas|"
        r"que tal(?: estas)?|que tal como estas|que onda|todo bien|"
        r"bien y tu(?: como estas)?)",
        social_text,
    ):
        return "¡Muy bien, gracias por preguntar! Estoy aquí para ayudarte con información de la UPVT. ¿Qué te gustaría saber?", "greeting", "happy"
    if re.fullmatch(r"(?:quien eres|como te llamas)", social_text):
        return "Soy Lobo, el asistente virtual de la UPVT. Puedo ayudarte a encontrar información de la universidad.", "greeting", "happy"
    if social_text in {"gracias", "muchas gracias", "te lo agradezco", "gracias lobo"}:
        return "¡Con gusto! Aquí estoy si necesitas algo más.", "greeting", "happy"
    if social_text in {"adios", "hasta luego", "nos vemos", "bye", "adios lobo"}:
        return "¡Hasta luego! Que tengas un excelente día. Si necesitas información de la UPVT, aquí estaré.", "greeting", "happy"
    if social_text in {"que haces", "que cuentas", "como va todo", "todo tranquilo", "estoy bien", "bien y tu", "bien y tu lobo", "aqui andamos", "todo bien gracias"}:
        return "¡Qué bueno! Yo estoy listo para ayudarte con lo que necesites de la UPVT. ¿Qué te gustaría consultar?", "greeting", "happy"
    if has_greeting_prefix and social_text == text_value:
        return "¡Hola! Qué gusto saludarte. Soy Lobo, el asistente de la UPVT. ¿En qué te puedo ayudar?", "greeting", "happy"
    if social_text in {"que tal", "que onda", "que onda lobo"}:
        return "¡Hola! Qué gusto saludarte. Soy Lobo, el asistente de la UPVT. ¿En qué te puedo ayudar?", "greeting", "happy"
    return None


def has_location_intent(query: str) -> bool:
    query_words = tokens(query)
    normalized = normalize(query)
    if query_words & LOCATION_QUERY_TERMS or "donde" in normalized.split() or "como llegar" in normalized:
        return True
    return "mapa" in query_words and not query_words & {"curricular", "materia", "cuatrimestre", "plan", "estudio"}


def contextual_search_query(message: str, context: list[ChatTurn]) -> str:
    current_words = tokens(message)
    previous_user = next((turn.content for turn in reversed(context) if turn.role == "user"), "")
    previous_assistant = next((turn.content for turn in reversed(context) if turn.role == "assistant"), "")
    previous_words = tokens(previous_user)
    assistant_words = tokens(previous_assistant)
    is_short_follow_up = len(current_words) <= 3
    refers_to_previous_topic = bool(previous_words & {"mapa", "curricular", "carrera", "cuatrimestre"})
    assistant_asked_to_clarify = bool(assistant_words & {"carrera", "programa"}) and "?" in previous_assistant
    if is_short_follow_up and previous_user and (refers_to_previous_topic or assistant_asked_to_clarify):
        return f"{previous_user} {message}".strip()
    return message


def curriculum_clarification(query: str, sources: list[dict[str, str | int | None]]) -> str | None:
    query_words = tokens(query)
    if not query_words & {"mapa", "curricular", "plan", "materia", "cuatrimestre"}:
        return None

    maps = [
        item for item in sources
        if item["tipo"] == "documento institucional"
        and is_curriculum_source(item)
    ]
    if len({item.get("fuente_documental") for item in maps}) < 2:
        return None

    title_tokens = [tokens(str(item["titulo"])) for item in maps]
    common_terms = set.intersection(*title_tokens) if title_tokens else set()
    distinguishing_terms = (set.union(*title_tokens) - common_terms) & PROGRAM_TERMS
    if query_words & distinguishing_terms:
        return None
    return "Encontré mapas curriculares de varias carreras. ¿De cuál necesitas información? Escribe el nombre de la carrera o sus siglas, por ejemplo: Industrial o TICS."


def is_curriculum_source(source: dict[str, str | int | None]) -> bool:
    content = normalize(f"{source.get('titulo', '')} {source.get('contenido', '')}")
    return any(phrase in content for phrase in (
        "mapa curricular", "malla curricular", "plan curricular", "plan de estudios",
        "reticula", "pensum", "mapa de asignaturas", "materias que conforman", "materias del programa",
    ))


def relevance(query: str, content: str) -> int:
    query_words = tokens(query)
    content_words = tokens(content)
    if not query_words or not content_words:
        return 0
    score = len(query_words & content_words) * 10
    if query_words <= content_words:
        score += 50
    normalized_query, normalized_content = normalize(query), normalize(content)
    if len(normalized_query) >= 5 and (
        f" {normalized_query} " in f" {normalized_content} "
        or f" {normalized_content} " in f" {normalized_query} "
    ):
        score += 30
    return score


def default_avatar_action(content: str) -> str:
    normalized = normalize(content)
    if re.search(r"\b(bienvenida|bienvenido|bienvenidos|saluda|saludo)\b", normalized):
        return "Da la bienvenida con un saludo breve y una postura abierta."
    if re.search(r"\b(mapas? curricular|curriculum|malla curricular|reticula|plan de estudios|materias|carrera|cuatrimestre)\b", normalized):
        return "Explica la información con gestos suaves de ambas manos y una postura abierta."
    if re.search(r"\b(ubicacion|direccion|como llegar|campus|edificio|oficina)\b", normalized):
        return "Orienta con una postura amable y gestos tranquilos mientras explica la información."
    if re.search(r"\b(celebr\w*|festej\w*|festival|concurso|premiacion|premio|medalla|ceremonia|aniversario)\b", normalized):
        return "Acompaña el anuncio con un gesto breve de celebración y entusiasmo."
    return "Explica la información con movimientos suaves de brazos y manos y una actitud amable."


def default_avatar_animation(content: str) -> str:
    normalized = normalize(content)
    if re.search(r"\b(bienvenida|bienvenido|bienvenidos|saluda|saludo)\b", normalized):
        return "Saludo"
    if re.search(r"\b(celebr\w*|festej\w*|festival|concurso|premiacion|premio|medalla|ceremonia|aniversario)\b", normalized):
        return "Celebrar"
    if re.search(r"\b(duda|comparar|comparacion|evaluar|reflex\w*)\b", normalized):
        return "Pensar"
    if re.search(
        r"\b(mapa curricular|malla curricular|plan de estudios|reticula|pensum|"
        r"carrera|cuatrimestre|materia|asignatura|inscripcion|requisito|beca|"
        r"servicios escolares|ubicacion|direccion|como llegar|horario|tramite|oficina)\b",
        normalized,
    ):
        return "Explicar"
    return "Hablar"


def is_location_source(source: dict[str, object]) -> bool:
    metadata = tokens(f"{source.get('titulo', '')} {source.get('categoria', '')}")
    return (
        bool(metadata & LOCATION_METADATA_TERMS)
        or bool(source.get("mapa_url"))
        or extract_google_maps_url(str(source.get("contenido", ""))) is not None
    )


def extract_google_maps_url(value: str) -> str | None:
    for candidate in re.findall(r"https?://[^\s<>\"']+", value, flags=re.IGNORECASE):
        candidate = candidate.rstrip("),.;!?")
        try:
            parsed = urlsplit(candidate)
        except ValueError:
            continue
        host = (parsed.hostname or "").lower()
        valid_google_domain = re.fullmatch(r"(?:www\.)?google\.(?:com|com\.[a-z]{2}|[a-z]{2,3})", host)
        if (
            host in {"maps.app.goo.gl", "maps.google.com"}
            or (host == "goo.gl" and parsed.path.startswith("/maps"))
            or (valid_google_domain and parsed.path.startswith("/maps"))
        ):
            return candidate
    return None


def extract_youtube_url(value: str) -> str | None:
    for candidate in re.findall(r"https?://[^\s<>\"']+", value, flags=re.IGNORECASE):
        candidate = candidate.rstrip("),.;!?")
        try:
            parsed = urlsplit(candidate)
        except ValueError:
            continue
        host = (parsed.hostname or "").lower()
        if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "youtube-nocookie.com", "www.youtube-nocookie.com"}:
            return candidate
    return None


def extract_document_keywords(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        normalized_line = normalize(line)
        if KEYWORD_SECTION_LABEL not in normalized_line:
            continue
        tail = re.split(r":", line, maxsplit=1)
        values = [tail[1].strip()] if len(tail) == 2 and tail[1].strip() else []
        for following in lines[index + 1:index + 4]:
            if not following.strip():
                break
            if following.lstrip().startswith("#"):
                break
            values.append(following.strip().lstrip("-*• "))
        return " ".join(values)
    return ""


def text_without_document_keywords(text: str) -> str:
    output = []
    skipping = False
    for line in text.splitlines():
        if KEYWORD_SECTION_LABEL in normalize(line):
            tail = re.split(r":", line, maxsplit=1)
            skipping = len(tail) == 1 or not tail[1].strip()
            continue
        if skipping:
            if not line.strip() or line.lstrip().startswith("#"):
                skipping = False
            else:
                continue
        output.append(line)
    return "\n".join(output).strip()


def clean_document_answer(text: str) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    while len(paragraphs) > 1:
        heading = normalize(paragraphs[0])
        following = normalize(paragraphs[1])
        if len(heading.split()) <= 4 and following.startswith(heading):
            paragraphs.pop(0)
            continue
        break
    cleaned = []
    seen = set()
    for index, paragraph in enumerate(paragraphs):
        key = normalize(paragraph)
        if index < 4 and paragraph.isupper() and 1 <= len(key.split()) <= 5:
            neighbors = paragraphs[max(0, index - 2):index] + paragraphs[index + 1:index + 3]
            if any(key in normalize(neighbor) and normalize(neighbor) != key for neighbor in neighbors):
                continue
        if key and key not in seen:
            cleaned.append(paragraph)
            seen.add(key)
    return "\n\n".join(cleaned)


def relevant_document_excerpt(query: str, text: str, limit: int = 2500) -> tuple[int, str]:
    query_words = tokens(query)
    keyword_matches = len(query_words & tokens(extract_document_keywords(text)))
    searchable_text = text_without_document_keywords(text)
    requested_periods = query_words & {str(number) for number in range(1, 11)}
    if "cuatrimestre" in query_words and requested_periods:
        lines = searchable_text.splitlines()
        sections = []
        for index, line in enumerate(lines):
            if not line.lstrip().startswith("#"):
                continue
            heading_words = tokens(line)
            if "cuatrimestre" not in heading_words or not (heading_words & requested_periods):
                continue
            heading_level = len(line) - len(line.lstrip("#"))
            end = index + 1
            while end < len(lines):
                next_line = lines[end]
                next_level = len(next_line) - len(next_line.lstrip("#"))
                if next_line.lstrip().startswith("#") and next_level <= heading_level:
                    break
                end += 1
            section = "\n".join(part.strip() for part in lines[index:end] if part.strip())
            if section:
                sections.append(section[:limit])
        if sections:
            excerpt = "\n\n".join(sections)
            return max(relevance(query, section) for section in sections) + 40, excerpt[:limit]

    chunks = []
    for paragraph in searchable_text.splitlines():
        paragraph = paragraph.strip()
        while len(paragraph) > 1000:
            chunks.append(paragraph[:1000])
            paragraph = paragraph[850:]
        if paragraph:
            chunks.append(paragraph)
    ranked = sorted(((relevance(query, chunk), chunk) for chunk in chunks), reverse=True)
    selected = []
    total = 0
    for score, chunk in ranked:
        if score <= 0 or total + len(chunk) > limit:
            continue
        selected.append((score, chunk))
        total += len(chunk)
        if len(selected) >= 3:
            break
    if not selected and keyword_matches:
        fallback_chunks = [line.strip() for line in searchable_text.splitlines() if line.strip()]
        excerpt = "\n\n".join(fallback_chunks[:3])[:limit]
        return min(60, keyword_matches * 20), excerpt
    if not selected:
        return relevance(query, searchable_text[:limit]), searchable_text[:limit]
    return max(score for score, _ in selected) + min(40, keyword_matches * 15), "\n\n".join(chunk for _, chunk in selected)


def _find_knowledge_sources(
    db: Session,
    query: str,
    *,
    use_fulltext: bool = True,
) -> list[dict[str, object]]:
    mysql_search = db.get_bind().dialect.name == "mysql" and use_fulltext
    query_words = tokens(query)
    curriculum_intent = bool(query_words & CURRICULUM_TERMS)
    fulltext_terms = sorted(expanded_search_terms(query))
    fulltext_query = " ".join(f"{term}*" for term in fulltext_terms)
    question_statement = select(PreguntaFrecuente).where(
        PreguntaFrecuente.activo.is_(True),
        PreguntaFrecuente.papelera_en.is_(None),
        PreguntaFrecuente.dirigido_a == "todos",
    )
    if mysql_search:
        if fulltext_query:
            question_filter = text("MATCH(pregunta, palabras_clave) AGAINST (:fts_query IN BOOLEAN MODE) > 0")
            question_score = text("MATCH(pregunta, palabras_clave) AGAINST (:fts_query IN BOOLEAN MODE) DESC")
            question_statement = (
                question_statement.where(question_filter)
                .order_by(question_score, PreguntaFrecuente.id.desc())
                .limit(500)
                .params(fts_query=fulltext_query)
            )
        else:
            question_statement = question_statement.limit(0)
    else:
        question_statement = question_statement.order_by(PreguntaFrecuente.id.desc()).limit(500)
    questions = db.scalars(question_statement).all()
    faq_ids = [faq.id for faq in questions]
    faq_documents: dict[int, list[DocumentoInstitucional]] = {}
    if faq_ids:
        for document in db.scalars(select(DocumentoInstitucional).where(
            DocumentoInstitucional.pregunta_frecuente_id.in_(faq_ids),
            DocumentoInstitucional.activo.is_(True),
            DocumentoInstitucional.papelera_en.is_(None),
        )):
            faq_documents.setdefault(int(document.pregunta_frecuente_id), []).append(document)
    candidates: list[dict[str, object]] = []
    for faq in questions:
        score = relevance(query, f"{faq.pregunta} {faq.palabras_clave or ''} {faq.categoria}")
        if score >= 10:
            candidates.append({
                "score": score,
                "tipo": "pregunta frecuente",
                "titulo": faq.pregunta,
                "categoria": faq.categoria,
                "contenido": faq.respuesta,
                "accion_avatar": faq.accion_avatar or default_avatar_action(f"{query} {faq.pregunta} {faq.respuesta[:4000]} {faq.categoria}"),
                "animacion": faq.animacion or default_avatar_animation(f"{query} {faq.pregunta} {faq.respuesta[:4000]} {faq.categoria}"),
                "emocion": faq.emocion,
                "pregunta_frecuente_id": faq.id,
                "documentos": faq_documents.get(faq.id, []),
                    "mapa_url": extract_google_maps_url(faq.respuesta),
                    "video_url": extract_youtube_url(faq.respuesta),
            })
        for document in faq_documents.get(faq.id, []):
            extracted = (document.contenido_extraido or "").strip()
            document_score, excerpt = relevant_document_excerpt(
                query,
                f"{faq.pregunta}\n{faq.categoria}\n{document.nombre_archivo}\n{extracted}",
            )
            if document_score >= 10:
                candidates.append({
                    "score": score + document_score,
                    "tipo": "documento de pregunta frecuente",
                    "titulo": f"{faq.pregunta} ({document.nombre_archivo})",
                    "categoria": faq.categoria,
                    "contenido": excerpt if extracted else faq.respuesta,
                    "accion_avatar": faq.accion_avatar or default_avatar_action(f"{faq.pregunta} {excerpt} {faq.categoria}"),
                    "animacion": faq.animacion or default_avatar_animation(f"{faq.pregunta} {excerpt} {faq.categoria}"),
                    "emocion": faq.emocion,
                    "pregunta_frecuente_id": faq.id,
                    "fuente_documental": document.nombre_archivo,
                    "url_documento": document.url,
                    "documentos": faq_documents.get(int(faq.id), [document]),
                    "mapa_url": extract_google_maps_url(faq.respuesta),
                    "video_url": extract_youtube_url(faq.respuesta),
                })

    # Let terms present only in an FAQ attachment find that attachment even
    # when the FAQ question itself does not contain the visitor's wording.
    indexed_faq_document_ids = {
        int(document.id)
        for attached_documents in faq_documents.values()
        for document in attached_documents
    }
    faq_document_statement = (
        select(DocumentoInstitucional, PreguntaFrecuente)
        .join(PreguntaFrecuente, DocumentoInstitucional.pregunta_frecuente_id == PreguntaFrecuente.id)
        .where(
            DocumentoInstitucional.activo.is_(True),
            DocumentoInstitucional.papelera_en.is_(None),
            PreguntaFrecuente.activo.is_(True),
            PreguntaFrecuente.papelera_en.is_(None),
            PreguntaFrecuente.dirigido_a == "todos",
        )
    )
    faq_curriculum_filters = []
    if curriculum_intent:
        for term in CURRICULUM_METADATA_TERMS:
            pattern = f"%{term}%"
            faq_curriculum_filters.extend((
                DocumentoInstitucional.nombre_archivo.ilike(pattern),
                PreguntaFrecuente.pregunta.ilike(pattern),
                PreguntaFrecuente.categoria.ilike(pattern),
                PreguntaFrecuente.palabras_clave.ilike(pattern),
            ))
    if mysql_search and fulltext_query:
        faq_fulltext_filter = text(
            "MATCH(documentos_institucionales.nombre_archivo, documentos_institucionales.contenido_extraido) "
            "AGAINST (:faq_document_query IN BOOLEAN MODE) > 0"
        )
        faq_document_statement = faq_document_statement.where(
            or_(faq_fulltext_filter, or_(*faq_curriculum_filters))
            if faq_curriculum_filters else faq_fulltext_filter
        ).params(faq_document_query=fulltext_query).limit(50)
    elif mysql_search:
        faq_document_statement = faq_document_statement.limit(0)
    else:
        faq_document_filters = list(faq_curriculum_filters)
        for term in sorted(tokens(query) - GENERIC_PROGRAM_TERMS - STOP_WORDS)[:6]:
            pattern = f"%{term}%"
            faq_document_filters.extend((
                DocumentoInstitucional.nombre_archivo.ilike(pattern),
                DocumentoInstitucional.contenido_extraido.ilike(pattern),
            ))
        if faq_document_filters:
            faq_document_statement = faq_document_statement.where(or_(*faq_document_filters)).limit(50)
        else:
            faq_document_statement = faq_document_statement.limit(0)
    for document, faq in db.execute(faq_document_statement).all():
        if int(document.id) in indexed_faq_document_ids:
            continue
        extracted = (document.contenido_extraido or "").strip()
        score, excerpt = relevant_document_excerpt(
            query,
            f"{faq.pregunta}\n{faq.categoria}\n{document.nombre_archivo}\n{extracted}",
        )
        candidate = {
            "score": score + relevance(query, f"{faq.pregunta} {faq.palabras_clave or ''} {faq.categoria}"),
            "tipo": "documento de pregunta frecuente",
            "titulo": f"{faq.pregunta} ({document.nombre_archivo})",
            "categoria": faq.categoria,
            "contenido": excerpt if extracted else faq.respuesta,
            "accion_avatar": faq.accion_avatar or default_avatar_action(f"{faq.pregunta} {excerpt} {faq.categoria}"),
            "animacion": faq.animacion or default_avatar_animation(f"{faq.pregunta} {excerpt} {faq.categoria}"),
            "emocion": faq.emocion,
            "pregunta_frecuente_id": faq.id,
            "fuente_documental": document.nombre_archivo,
            "url_documento": document.url,
            "documentos": faq_documents.get(int(faq.id), [document]),
            "mapa_url": extract_google_maps_url(faq.respuesta),
            "video_url": extract_youtube_url(faq.respuesta),
        }
        if score >= 10 and (not has_location_intent(query) or is_location_source(candidate)):
            candidates.append(candidate)

    info_statement = select(InformacionInstitucional).where(InformacionInstitucional.activo.is_(True))
    if mysql_search:
        if fulltext_query:
            info_filter = text("MATCH(clave, titulo, contenido, categoria) AGAINST (:fts_query IN BOOLEAN MODE) > 0")
            info_score = text("MATCH(clave, titulo, contenido, categoria) AGAINST (:fts_query IN BOOLEAN MODE) DESC")
            info_statement = (
                info_statement.where(info_filter)
                .order_by(info_score, InformacionInstitucional.id.desc())
                .limit(500)
                .params(fts_query=fulltext_query)
            )
        else:
            info_statement = info_statement.limit(0)
    else:
        info_statement = info_statement.order_by(InformacionInstitucional.id.desc()).limit(500)
    info_rows = db.scalars(info_statement).all()
    for item in info_rows:
        score = relevance(query, f"{item.clave} {item.titulo} {item.contenido} {item.categoria}")
        if score >= 10:
            candidates.append({
                "score": score,
                "tipo": "información institucional",
                "titulo": item.titulo,
                "categoria": item.categoria,
                "contenido": item.contenido,
                "accion_avatar": item.accion_avatar or default_avatar_action(f"{query} {item.titulo} {item.contenido[:4000]} {item.categoria}"),
                "animacion": item.animacion or default_avatar_animation(f"{query} {item.titulo} {item.contenido[:4000]} {item.categoria} {item.accion_avatar}"),
                "emocion": item.emocion or "neutral",
                "pregunta_frecuente_id": None,
                "fuente_documental": None,
                "url_documento": None,
                "informacion_id": item.id,
                "documentos": [],
                "mapa_url": extract_google_maps_url(item.contenido),
                "video_url": extract_youtube_url(item.contenido),
            })

    query_words = tokens(query)
    location_intent = has_location_intent(query)
    if location_intent:
        # A short location query should not be matched to an unrelated document
        # merely because it mentions the word "ubicación" somewhere in its body.
        candidates = [item for item in candidates if is_location_source(item)]

    # A clear FAQ or institutional match should not wait for a scan of every PDF.
    if candidates:
        candidates.sort(key=lambda item: int(item["score"] or 0), reverse=True)
        best = candidates[0]
        needs_curriculum_lookup = (
            "cuatrimestre" in query_words
            and bool(query_words & {"materia", "asignatura"})
            and bool(query_words & {str(number) for number in range(1, 11)})
        )
        needs_document_search = bool(query_words & {"mapa", "curricular", "materia", "cuatrimestre", "plan", "estudio"})
        if (
            int(best["score"] or 0) >= 40
            and best["tipo"] == "pregunta frecuente"
            and not needs_curriculum_lookup
            and not needs_document_search
            and not location_intent
        ):
            return candidates[:5]

    matching_information = sorted(
        (
            item for item in candidates
            if item["tipo"] == "información institucional" and int(item["score"] or 0) > 0
        ),
        key=lambda item: int(item["score"] or 0),
        reverse=True,
    )[:10]
    matched_information_ids = [int(item["informacion_id"]) for item in matching_information]
    information_documents: dict[int, list[DocumentoInstitucional]] = {}
    if matched_information_ids:
        attached_documents = db.scalars(
            select(DocumentoInstitucional)
            .where(
                DocumentoInstitucional.informacion_id.in_(matched_information_ids),
                DocumentoInstitucional.activo.is_(True),
                DocumentoInstitucional.papelera_en.is_(None),
            )
            .order_by(DocumentoInstitucional.id)
        )
        for document in attached_documents:
            information_documents.setdefault(int(document.informacion_id), []).append(document)
        for candidate in candidates:
            if candidate["tipo"] == "información institucional":
                candidate["documentos"] = information_documents.get(int(candidate["informacion_id"]), [])
    search_terms = sorted(
        expanded_search_terms(query) - GENERIC_PROGRAM_TERMS - STOP_WORDS - {"tecnologia", "informacion"}
    )[:6]
    document_filters = []
    if matched_information_ids:
        document_filters.append(InformacionInstitucional.id.in_(matched_information_ids))
    if mysql_search and not location_intent:
        if fulltext_query:
            fulltext_filter = text(
                "MATCH(documentos_institucionales.nombre_archivo, documentos_institucionales.contenido_extraido) "
                "AGAINST (:document_fts_query IN BOOLEAN MODE) > 0"
            )
            if curriculum_intent:
                curriculum_filters = []
                for term in CURRICULUM_METADATA_TERMS:
                    pattern = f"%{term}%"
                    curriculum_filters.extend((
                        DocumentoInstitucional.nombre_archivo.ilike(pattern),
                        InformacionInstitucional.titulo.ilike(pattern),
                        InformacionInstitucional.categoria.ilike(pattern),
                    ))
                document_filters.append(or_(fulltext_filter, or_(*curriculum_filters)))
            else:
                document_filters.append(fulltext_filter)
    elif not mysql_search and not location_intent:
        for term in search_terms:
            pattern = f"%{term}%"
            document_filters.extend((
                DocumentoInstitucional.nombre_archivo.ilike(pattern),
                DocumentoInstitucional.contenido_extraido.ilike(pattern),
            ))
        if curriculum_intent:
            for term in CURRICULUM_METADATA_TERMS:
                pattern = f"%{term}%"
                document_filters.extend((
                    DocumentoInstitucional.nombre_archivo.ilike(pattern),
                    InformacionInstitucional.titulo.ilike(pattern),
                    InformacionInstitucional.categoria.ilike(pattern),
                ))
    if not document_filters:
        return candidates[:5]

    document_statement = (
        select(DocumentoInstitucional, InformacionInstitucional)
        .join(InformacionInstitucional, DocumentoInstitucional.informacion_id == InformacionInstitucional.id)
        .where(
            DocumentoInstitucional.activo.is_(True),
            DocumentoInstitucional.papelera_en.is_(None),
            InformacionInstitucional.activo.is_(True),
            InformacionInstitucional.papelera_en.is_(None),
            or_(*document_filters),
        )
        .order_by(DocumentoInstitucional.id.desc())
        .limit(50)
    )
    if mysql_search and fulltext_query:
        document_statement = document_statement.params(document_fts_query=fulltext_query)
    document_rows = db.execute(document_statement).all()
    for document, information in document_rows:
        extracted = (document.contenido_extraido or "").strip()
        if not extracted:
            continue
        score, excerpt = relevant_document_excerpt(
            query,
            f"{information.titulo}\n{document.nombre_archivo}\n{information.categoria}\n{extracted}",
        )
        if score >= 10:
            query_words = tokens(query)
            title_words = tokens(information.titulo)
            score += 35 * len(query_words & title_words & PROGRAM_TERMS)
            if (
                query_words & {"materia", "cuatrimestre", "plan", "estudio"}
                and "mapa curricular" in normalize(f"{information.titulo} {document.nombre_archivo}")
            ):
                score += 50
            candidates.append({
                "score": score,
                "tipo": "documento institucional",
                "titulo": f"{information.titulo} ({document.nombre_archivo})",
                "categoria": information.categoria,
                "contenido": excerpt,
                "accion_avatar": information.accion_avatar or default_avatar_action(f"{query} {information.titulo} {excerpt} {information.categoria}"),
                "animacion": information.animacion or default_avatar_animation(f"{query} {information.titulo} {excerpt} {information.categoria} {information.accion_avatar}"),
                "emocion": information.emocion or "neutral",
                "pregunta_frecuente_id": None,
                "fuente_documental": document.nombre_archivo,
                "url_documento": document.url,
                "documentos": information_documents.get(int(information.id), [document]),
                "mapa_url": extract_google_maps_url(information.contenido),
                "video_url": extract_youtube_url(information.contenido),
            })

    candidates.sort(
        key=lambda item: (int(item["score"] or 0), item["tipo"] == "documento institucional"),
        reverse=True,
    )
    return candidates[:5]


def find_knowledge_sources(db: Session, query: str) -> list[dict[str, object]]:
    try:
        return _find_knowledge_sources(db, query)
    except OperationalError as error:
        if db.get_bind().dialect.name != "mysql":
            raise
        # A local install may have data migrations applied but not the optional
        # FULLTEXT indexes. Retry using bound LIKE filters so a missing index
        # cannot turn an otherwise valid kiosk search into an HTTP 503.
        logger.warning(
            "FULLTEXT search failed (%s); retrying the kiosk lookup with LIKE",
            type(error.orig).__name__,
        )
        db.rollback()
        return _find_knowledge_sources(db, query, use_fulltext=False)


def search_knowledge(db: Session, query: str) -> tuple[str, str, str, int | None]:
    sources = find_knowledge_sources(db, query)
    if not sources:
        return NO_ANSWER, "thinking", "duda", None
    best = sources[0]
    return (
        str(best["contenido"]),
        str(best["animacion"]),
        str(best["emocion"]),
        best["pregunta_frecuente_id"],
    )


def curriculum_period_answer(query: str, sources: list[dict[str, str | int | None]]) -> str | None:
    query_words = tokens(query)
    periods = query_words & {str(number) for number in range(1, 11)}
    if "cuatrimestre" not in query_words or not periods or not query_words & {"materia", "asignatura"}:
        return None

    source = next((
        item for item in sources
        if item["tipo"] == "documento institucional"
        and is_curriculum_source(item)
    ), None)
    if source is None:
        return None

    subjects = []
    for line in str(source["contenido"]).splitlines():
        line = line.strip()
        if not line.startswith("*") or "total de horas" in normalize(line):
            continue
        subject = re.sub(r"^\*\s*", "", line)
        subject = re.sub(r"\*\*", "", subject).strip()
        if subject:
            subjects.append(subject)
    if not subjects:
        return None

    ordinal = {
        "1": "primer", "2": "segundo", "3": "tercer", "4": "cuarto", "5": "quinto",
        "6": "sexto", "7": "séptimo", "8": "octavo", "9": "noveno", "10": "décimo",
    }
    period = sorted(periods, key=int)[0]
    return f"En el {ordinal[period]} cuatrimestre se cursa: " + "; ".join(subjects) + "."


def answer_and_record(
    db: Session,
    message: str,
    context: list[ChatTurn] | None = None,
    request_id: str | None = None,
) -> ChatResponse:
    if request_id:
        existing = db.scalar(select(HistorialConsulta).where(HistorialConsulta.clave_solicitud == request_id))
        if existing is not None:
            return ChatResponse(
                respuesta=existing.respuesta,
                accion_avatar=existing.accion_avatar,
                animacion=existing.animacion,
                emocion=existing.emocion,
                consulta_id=existing.id,
            )
    search_query = contextual_search_query(message, context or [])
    location_intent = has_location_intent(search_query)
    casual = casual_response(message)
    sources = [] if casual else find_knowledge_sources(db, search_query)
    clarification = None if casual else curriculum_clarification(search_query, sources)
    query_words = tokens(search_query)
    if (
        not casual
        and not sources
        and query_words & CURRICULUM_TERMS
        and not query_words & PROGRAM_TERMS
    ):
        clarification = "¡Claro! Te ayudo a encontrarlo. ¿De qué carrera necesitas el mapa curricular? Por ejemplo: Industrial, Mecatrónica, Biotecnología o Tecnologías de la Información."
    best = sources[0] if sources else None
    if casual:
        answer, animation, emotion = casual
        avatar_action = ""
        faq_id = None
    elif clarification:
        answer, animation, emotion, faq_id = clarification, "thinking", "neutral", None
        avatar_action = ""
        best = None
    elif sources:
        best = sources[0]
        # Curriculum PDFs are often scanned or have only their cover indexed.
        # When the database also has a matching institutional record with the
        # attached PDF, use that record as the answer and return its document
        # link instead of sending a weak PDF excerpt to Gemini.
        if query_words & CURRICULUM_TERMS and best["tipo"] == "documento institucional":
            richer_curriculum = next((
                item for item in sources
                if item["tipo"] == "información institucional"
                and int(item["score"] or 0) >= 40
                and is_curriculum_source(item)
                and len(str(item.get("contenido") or "").strip()) >= 100
                and item.get("documentos")
            ), None)
            if richer_curriculum and len(str(best.get("contenido") or "").strip()) < 250:
                best = richer_curriculum
        fallback = str(best["contenido"])
        answer = curriculum_period_answer(search_query, sources)
        if answer is not None:
            best = next(
                item for item in sources
                if item["tipo"] == "documento institucional"
                and is_curriculum_source(item)
            )
        elif best["tipo"] == "pregunta frecuente":
            answer = fallback
        elif best["tipo"] == "información institucional" and int(best["score"] or 0) >= 40:
            answer = fallback
        else:
            answer = generate_grounded_answer(search_query, sources) or fallback
        if best["tipo"] == "documento institucional":
            answer = clean_document_answer(answer)
        animation = str(best["animacion"])
        emotion = str(best["emocion"])
        avatar_action = str(best.get("accion_avatar", "") or "")
        faq_id = best["pregunta_frecuente_id"]
    else:
        answer, animation, emotion, faq_id = NO_ANSWER, "thinking", "duda", None
        avatar_action = ""
    if casual:
        module = "conversacion"
        category = "Conversación"
    elif clarification:
        module = "aclaracion"
        category = "Aclaración"
    elif faq_id is not None:
        module = "preguntas_respuestas"
        category = str(best.get("categoria") or "Preguntas frecuentes") if best else "Preguntas frecuentes"
    elif best and best["tipo"] in {"información institucional", "documento institucional"}:
        module = "informacion_institucional"
        category = str(best.get("categoria") or "Información institucional")
    else:
        module = "sin_coincidencia"
        category = "Sin coincidencia"
    interaction = HistorialConsulta(
        usuario_id=None,
        mensaje=message.strip(),
        respuesta=answer,
        origen="kiosko_kinect",
        pregunta_frecuente_id=faq_id,
        categoria=category,
        modulo=module,
        clave_solicitud=request_id,
        accion_avatar=avatar_action,
        animacion=animation,
        emocion=emotion,
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    map_url = None
    video_url = None
    if best and location_intent:
        map_url = best.get("mapa_url") or extract_google_maps_url(str(best.get("contenido", "")))
    if best:
        video_url = best.get("video_url") or extract_youtube_url(str(best.get("contenido", "")))
    return ChatResponse(
        respuesta=answer,
        accion_avatar=avatar_action,
        animacion=animation,
        emocion=emotion,
        consulta_id=interaction.id,
        fuente_documental=str(best["fuente_documental"]) if best and best.get("fuente_documental") else None,
        url_documento=str(best["url_documento"]) if best and best.get("url_documento") else None,
        mapa_url=str(map_url) if map_url else None,
        video_url=str(video_url) if video_url else None,
        documentos=[
            PreguntaAdjuntoResponse.model_validate(document)
            for document in (best.get("documentos", []) if best else [])
        ],
    )

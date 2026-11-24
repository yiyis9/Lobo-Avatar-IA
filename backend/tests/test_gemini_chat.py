import os
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from database import Base
from models import DocumentoInstitucional, HistorialConsulta, InformacionInstitucional, PreguntaFrecuente
from schemas import ChatResponse, ChatTurn
from services.chat import (
    NO_ANSWER,
    answer_and_record,
    casual_response,
    clean_document_answer,
    default_avatar_animation,
    expanded_search_terms,
    find_knowledge_sources,
)
from services.gemini_chat import generate_grounded_answer


class GeminiChatTests(unittest.TestCase):
    def test_tics_acronym_is_kept_for_database_fulltext_search(self) -> None:
        terms = expanded_search_terms("mapa curricular de TICS")
        self.assertTrue({"mapa", "curricular", "tecnologia", "tics"}.issubset(terms))

    def test_fulltext_search_retries_with_like_when_mysql_index_is_missing(self) -> None:
        db = MagicMock()
        db.get_bind.return_value.dialect.name = "mysql"
        missing_index = OperationalError(
            "MATCH(pregunta, palabras_clave)",
            {},
            Exception("Can't find FULLTEXT index matching the column list"),
        )
        expected = [{"tipo": "documento institucional", "titulo": "Mapa TICS"}]
        with patch("services.chat._find_knowledge_sources", side_effect=[missing_index, expected]) as search:
            self.assertEqual(find_knowledge_sources(db, "mapa curricular de TICS"), expected)

        db.rollback.assert_called_once()
        self.assertEqual(search.call_count, 2)
        self.assertEqual(search.call_args.kwargs, {"use_fulltext": False})

    def test_curriculum_pdf_is_found_when_fulltext_is_unavailable(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            info = InformacionInstitucional(
                clave="mapa-tics", titulo="Mapa curricular de TICS",
                contenido="Plan de estudios de Tecnologías de la Información.",
                categoria="Oferta educativa", activo=True,
            )
            db.add(info)
            db.flush()
            db.add(DocumentoInstitucional(
                informacion_id=info.id, nombre_archivo="mapa-curricular-tics.pdf",
                archivo_key="mapa-tics-pdf", mime_type="application/pdf", tamano_bytes=100,
                contenido_extraido="#### Primer cuatrimestre\n* Fundamentos de programación",
                activo=True,
            ))
            db.commit()

            mysql_bind = SimpleNamespace(dialect=SimpleNamespace(name="mysql"))
            original_get_bind = db.get_bind
            def report_mysql_only_for_dialect_check(*args, **kwargs):
                if not args and not kwargs:
                    return mysql_bind
                return original_get_bind(*args, **kwargs)

            with patch.object(db, "get_bind", side_effect=report_mysql_only_for_dialect_check):
                sources = find_knowledge_sources(db, "mapa curricular de TICS")

            self.assertTrue(sources)
            self.assertEqual(sources[0]["tipo"], "documento institucional")
            self.assertEqual(sources[0]["fuente_documental"], "mapa-curricular-tics.pdf")
        engine.dispose()

    def test_uploaded_curriculum_content_gets_explanation_animation(self) -> None:
        self.assertEqual(
            default_avatar_animation("Mapa curricular de Ingeniería en Tecnologías de la Información"),
            "Explicar",
        )

    def test_common_greetings_are_social_and_prefixes_preserve_real_questions(self) -> None:
        for phrase in ("hola", "Hola!", "OLA", "buenas", "buenas tardes lobo", "hey Lobo"):
            with self.subTest(phrase=phrase):
                response = casual_response(phrase)
                self.assertIsNotNone(response)
                self.assertIn("Hola", response[0])
                self.assertEqual(response[1:], ("greeting", "happy"))

        with self.subTest(phrase="hola, cómo estás"):
            response = casual_response("Hola, ¿cómo estás?")
            self.assertIsNotNone(response)
            self.assertIn("Muy bien", response[0])

        self.assertIsNone(casual_response("Hola, ¿cuándo son las inscripciones?"))

    def test_document_answer_removes_repeated_opening_titles(self) -> None:
        answer = "MAPA CURRICULAR\n\nMAPA CURRICULAR\n\nMapa curricular de Ingeniería en Tecnologías de la Información."
        self.assertEqual(
            clean_document_answer(answer),
            "Mapa curricular de Ingeniería en Tecnologías de la Información.",
        )

    def test_document_answer_removes_short_heading_repeated_inside_full_title(self) -> None:
        answer = (
            "TÉCNICO SUPERIOR UNIVERSITARIO EN PROCESOS PRODUCTIVOS\n\n"
            "TÉCNICO SUPERIOR UNIVERSITARIO"
        )
        self.assertEqual(clean_document_answer(answer), "TÉCNICO SUPERIOR UNIVERSITARIO EN PROCESOS PRODUCTIVOS")

    def test_specific_course_question_prefers_matching_map_and_includes_period_rows(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        query = (
            "que materia se lleva en sexto cuatri de Ingeniería en Tecnologías de la Información "
            "e Innovación Digital con TSU en Desarrollo de Software Multiplataforma"
        )
        with Session(engine) as db:
            info = InformacionInstitucional(
                clave="mapa-ti", titulo="Mapa curricular de Ingeniería en Tecnologías de la Información e Innovación Digital",
                contenido="Mapa curricular de la carrera.", categoria="Oferta educativa", activo=True,
            )
            db.add(info)
            db.flush()
            db.add(DocumentoInstitucional(
                informacion_id=info.id, nombre_archivo="mapa-ti.pdf", archivo_key="mapa-ti-key",
                mime_type="application/pdf", tamano_bytes=100,
                contenido_extraido=(
                    "Programa: Ingeniería en Tecnologías de la Información e Innovación Digital con TSU en Desarrollo de Software Multiplataforma\n"
                    "#### Sexto cuatrimestre\n"
                    "* Estadía Técnico Superior Universitario en Desarrollo de Software Multiplataforma (600 hrs)"
                ),
                activo=True,
            ))
            db.add(PreguntaFrecuente(
                categoria="Oferta educativa",
                pregunta="¿Qué materias se cursan en sexto cuatrimestre de Ingeniería en Tecnologías de la Información?",
                respuesta="Consulta el mapa curricular.",
                palabras_clave="materias sexto cuatrimestre",
                dirigido_a="todos",
                animacion="idle",
                emocion="neutral",
                activo=True,
            ))
            db.commit()

            with patch("services.chat.generate_grounded_answer") as generate:
                response = answer_and_record(db, query)

            self.assertEqual(response.fuente_documental, "mapa-ti.pdf")
            self.assertIn("se cursa: Estadía Técnico Superior Universitario", response.respuesta)
            self.assertIn("600 hrs", response.respuesta)
            generate.assert_not_called()

        engine.dispose()

    def test_generic_curriculum_query_asks_which_program(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            for key, title, filename in (
                ("mapa-ti", "Mapa curricular de Ingeniería en Tecnologías de la Información", "mapa-ti.pdf"),
                ("mapa-industrial", "Mapa curricular de Ingeniería Industrial", "mapa-industrial.pdf"),
            ):
                info = InformacionInstitucional(
                    clave=key, titulo=title, contenido="Mapa curricular institucional.",
                    categoria="Oferta educativa", activo=True,
                )
                db.add(info)
                db.flush()
                db.add(DocumentoInstitucional(
                    informacion_id=info.id, nombre_archivo=filename, archivo_key=key,
                    mime_type="application/pdf", tamano_bytes=100,
                    contenido_extraido="Mapa curricular de la carrera.", activo=True,
                ))
            db.commit()

            with patch("services.chat.generate_grounded_answer") as generate:
                response = answer_and_record(db, "Mapa curricular")

            self.assertIn("¿De cuál necesitas información?", response.respuesta)
            self.assertIsNone(response.fuente_documental)
            generate.assert_not_called()
        engine.dispose()

    def test_short_follow_up_uses_previous_query_to_select_program_document(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            for key, title, filename, text in (
                ("mapa-ti", "Mapa curricular de Ingeniería en Tecnologías de la Información", "mapa-ti.pdf", "Materias de tecnologías de la información."),
                ("mapa-industrial", "Mapa curricular de Ingeniería Industrial", "mapa-industrial.pdf", "Materias de ingeniería industrial."),
            ):
                info = InformacionInstitucional(
                    clave=key, titulo=title, contenido="Mapa curricular institucional.",
                    categoria="Oferta educativa", activo=True,
                )
                db.add(info)
                db.flush()
                db.add(DocumentoInstitucional(
                    informacion_id=info.id, nombre_archivo=filename, archivo_key=key,
                    mime_type="application/pdf", tamano_bytes=100,
                    contenido_extraido=text, activo=True,
                ))
            db.commit()

            context = [
                ChatTurn(role="user", content="Mapa curricular"),
                ChatTurn(role="assistant", content="¿De cuál carrera necesitas información?"),
            ]
            with patch("services.chat.generate_grounded_answer", return_value="Mapa de TI."):
                response = answer_and_record(db, "TICS", context)

            self.assertEqual(response.fuente_documental, "mapa-ti.pdf")
        engine.dispose()

    def test_chat_retrieves_relevant_text_from_active_public_pdf(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            info = InformacionInstitucional(
                clave="plan-industrial", titulo="Plan curricular de Ingeniería Industrial",
                contenido="Documento oficial con el plan de estudios.", categoria="Oferta educativa", activo=True,
            )
            db.add(info)
            db.flush()
            db.add(DocumentoInstitucional(
                informacion_id=info.id, nombre_archivo="plan-industrial.pdf", archivo_key="document-key",
                mime_type="application/pdf", tamano_bytes=128,
                contenido_extraido="La Ingeniería Industrial tiene una duración de diez cuatrimestres y contempla estadías profesionales.",
                activo=True,
            ))
            db.commit()

            with patch("services.chat.generate_grounded_answer", return_value="El plan dura diez cuatrimestres.") as generate:
                response = answer_and_record(db, "¿Cuántos cuatrimestres dura Ingeniería Industrial?")

            self.assertEqual(response.respuesta, "El plan dura diez cuatrimestres.")
            self.assertEqual(response.fuente_documental, "plan-industrial.pdf")
            self.assertEqual(response.url_documento, "/api/v1/documentos/1/archivo")
            sources = generate.call_args.args[1]
            self.assertEqual(sources[0]["tipo"], "documento institucional")
            self.assertIn("diez cuatrimestres", sources[0]["contenido"])
        engine.dispose()

    def test_missing_key_leaves_database_answer_available(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(generate_grounded_answer("¿Dónde está?", []))

    def test_calls_google_sdk_statelessly_with_spanish_grounding(self) -> None:
        fake_genai = ModuleType("google.genai")
        fake_client = MagicMock()
        fake_client.interactions.create.return_value = SimpleNamespace(output_text="La biblioteca abre a las ocho.")
        fake_genai.Client = MagicMock(return_value=fake_client)
        fake_google = ModuleType("google")
        fake_google.genai = fake_genai
        source = {
            "tipo": "pregunta frecuente",
            "titulo": "¿A qué hora abre la biblioteca?",
            "categoria": "Servicios",
            "contenido": "La biblioteca abre a las ocho.",
        }
        with patch.dict(os.environ, {"GEMINI_API_KEY": "local-test-key", "GEMINI_MODEL": "test-model"}):
            with patch.dict("sys.modules", {"google": fake_google, "google.genai": fake_genai}):
                answer = generate_grounded_answer("¿A qué hora abre?", [source])

        self.assertEqual(answer, "La biblioteca abre a las ocho.")
        self.assertEqual(
            fake_genai.Client.call_args.kwargs["http_options"],
            {"timeout": 1_400, "retry_options": {"attempts": 1}},
        )
        fake_client.interactions.create.assert_called_once()
        call = fake_client.interactions.create.call_args.kwargs
        self.assertEqual(call["model"], "test-model")
        self.assertFalse(call["store"])
        self.assertEqual(call["timeout"], 1.4)
        self.assertIn("español", call["system_instruction"])
        self.assertIn(source["contenido"], call["input"])
        self.assertNotIn("local-test-key", str(call))

    def test_chat_records_grounded_answer_and_uses_mysql_fallback(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(PreguntaFrecuente(
                categoria="Servicios",
                pregunta="¿Qué horario tiene la biblioteca?",
                respuesta="La biblioteca abre a las ocho.",
                palabras_clave="biblioteca horario",
                dirigido_a="todos",
                animacion="idle",
                emocion="neutral",
                activo=True,
            ))
            db.commit()

            with patch("services.chat.generate_grounded_answer") as generate:
                response = answer_and_record(db, "¿Cuál es el horario de la biblioteca?")
            self.assertEqual(response.respuesta, "La biblioteca abre a las ocho.")
            generate.assert_not_called()
            history = db.scalar(select(HistorialConsulta))
            self.assertEqual(history.respuesta, response.respuesta)
            self.assertIsNotNone(history.pregunta_frecuente_id)

            with patch("services.chat.generate_grounded_answer") as generate:
                no_match = answer_and_record(db, "¿Cuál es el clima de Marte?")
            self.assertEqual(no_match.respuesta, NO_ANSWER)
            generate.assert_not_called()

        engine.dispose()

    def test_greetings_camera_and_avatar_commands_are_saved_once_on_retry(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            first = answer_and_record(db, "hola", request_id="a" * 32)
            retried = answer_and_record(db, "hola", request_id="a" * 32)
            camera = answer_and_record(db, "El visitante saludó con la mano.", request_id="b" * 32)
            command = answer_and_record(db, "Lobo saluda", request_id="c" * 32)

            self.assertEqual(first.consulta_id, retried.consulta_id)
            self.assertIn("Hola", first.respuesta)
            self.assertEqual(first.animacion, "greeting")
            self.assertEqual(camera.animacion, "greeting")
            self.assertEqual(command.animacion, "greeting")
            self.assertEqual(db.query(HistorialConsulta).count(), 3)
        engine.dispose()

    def test_exact_faq_match_beats_unrelated_document_keyword(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            info = InformacionInstitucional(
                clave="mapa-ti", titulo="Mapa curricular TI", contenido="Oferta educativa.",
                categoria="Oferta educativa", activo=True,
            )
            db.add(info)
            db.flush()
            db.add_all([
                DocumentoInstitucional(
                    informacion_id=info.id, nombre_archivo="mapa-ti.pdf", archivo_key="mapa-ti",
                    mime_type="application/pdf", tamano_bytes=100,
                    contenido_extraido="Servicios: Aplicaciones Web Orientadas a Servicios.", activo=True,
                ),
                PreguntaFrecuente(
                    categoria="Servicios", pregunta="¿Dónde se ubican Servicios Escolares?",
                    respuesta="En edificio E.", palabras_clave="servicios escolares ubicación",
                    dirigido_a="todos", animacion="idle", emocion="neutral", activo=True,
                ),
            ])
            db.commit()

            with patch("services.chat.generate_grounded_answer") as generate:
                response = answer_and_record(db, "¿Dónde está Servicios Escolares?")

            self.assertEqual(response.respuesta, "En edificio E.")
            self.assertIsNone(response.fuente_documental)
            generate.assert_not_called()
        engine.dispose()


if __name__ == "__main__":
    unittest.main()

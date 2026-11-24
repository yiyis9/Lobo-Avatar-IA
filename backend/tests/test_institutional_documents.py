import base64
import os
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi import BackgroundTasks
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database import Base
from models import DocumentoInstitucional, InformacionInstitucional
from routers.admin import create_information_with_optional_pdf, delete_institutional_document, draft_information_from_document
from schemas import ImportarInformacionRequest, InformacionConDocumentoRequest
from routers.public import get_public_document, list_public_documents, list_public_information
from services import institutional_documents
from services.gemini_import import GeminiConfigurationError, analyze_pdf_for_search
from services.institutional_documents import DocumentValidationError, store_pdf


class InstitutionalDocumentTests(unittest.TestCase):
    def test_manual_pdf_upload_queues_gemini_document_indexing(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        pdf = b"%PDF-test-content"
        request = InformacionConDocumentoRequest(
            clave="mapa-curricular-ti",
            titulo="Mapa curricular TI",
            contenido="Mapa de materias de la carrera.",
            categoria="Oferta educativa",
            activo=True,
            archivo_nombre="mapa-ti.pdf",
            archivo_base64=base64.b64encode(pdf).decode("ascii"),
            contenido_publico_confirmado=True,
        )
        with Session(engine) as db:
            background_tasks = BackgroundTasks()
            with patch(
                "routers.admin.store_institutional_file",
                return_value=("test-file-key", "mapa-ti.pdf", "application/pdf", "Encabezado del mapa"),
            ):
                response = create_information_with_optional_pdf(request, background_tasks, db, None)

            saved = db.scalar(select(DocumentoInstitucional))
            self.assertFalse(response.analisis_gemini)
            self.assertEqual(saved.contenido_extraido, "Encabezado del mapa")
            self.assertEqual(saved.nombre_archivo, "mapa-ti.pdf")
            self.assertEqual(len(background_tasks.tasks), 1)

        engine.dispose()

    def test_gemini_receives_pdf_as_document_for_visual_table_analysis(self) -> None:
        fake_genai = ModuleType("google.genai")
        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = SimpleNamespace(
            text="Cuatrimestre 6:\nMaterias: Desarrollo de Aplicaciones Web"
        )
        fake_genai.Client = MagicMock(return_value=fake_client)
        fake_genai.types = SimpleNamespace(
            Part=SimpleNamespace(from_bytes=lambda **kwargs: kwargs)
        )
        fake_google = ModuleType("google")
        fake_google.genai = fake_genai
        pdf = b"%PDF-test-content"

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "test-model"}):
            with patch.dict("sys.modules", {"google": fake_google, "google.genai": fake_genai}):
                analyzed = analyze_pdf_for_search(pdf, "Texto nativo del encabezado")

        self.assertIn("Cuatrimestre 6", analyzed)
        self.assertIn("Texto nativo del encabezado", analyzed)
        call = fake_client.models.generate_content.call_args.kwargs
        self.assertEqual(call["contents"][0]["data"], pdf)
        self.assertEqual(call["contents"][0]["mime_type"], "application/pdf")
        self.assertEqual(
            fake_genai.Client.call_args.kwargs["http_options"],
            {"timeout": 90_000, "retry_options": {"attempts": 1}},
        )

    def test_pdf_analysis_falls_back_when_primary_model_is_unavailable(self) -> None:
        unavailable = RuntimeError("busy")
        unavailable.status_code = 503
        fake_genai = ModuleType("google.genai")
        fake_client = MagicMock()
        fake_client.models.generate_content.side_effect = [
            unavailable,
            SimpleNamespace(text="Cuatrimestre 6: Redes"),
        ]
        fake_genai.Client = MagicMock(return_value=fake_client)
        fake_genai.types = SimpleNamespace(Part=SimpleNamespace(from_bytes=lambda **kwargs: kwargs))
        fake_google = ModuleType("google")
        fake_google.genai = fake_genai

        with patch.dict(os.environ, {
            "GEMINI_API_KEY": "test-key",
            "GEMINI_MODEL": "primary-model",
            "GEMINI_PDF_FALLBACK_MODEL": "fallback-model",
        }):
            with patch.dict("sys.modules", {"google": fake_google, "google.genai": fake_genai}):
                result = analyze_pdf_for_search(b"%PDF-test")

        self.assertIn("Cuatrimestre 6", result)
        models = [call.kwargs["model"] for call in fake_client.models.generate_content.call_args_list]
        self.assertEqual(models, ["primary-model", "fallback-model"])

    def test_import_saves_full_text_source_and_does_not_duplicate_it(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        source = "Las inscripciones para el periodo escolar se realizan en el portal institucional durante las fechas publicadas."
        request = ImportarInformacionRequest(
            nombre_archivo="calendario.txt",
            texto=source,
            contenido_publico_confirmado=True,
        )
        with Session(engine) as db:
            with patch("routers.admin.suggest_information", return_value=[]):
                first = draft_information_from_document(request, BackgroundTasks(), db, None)
                second = draft_information_from_document(request, BackgroundTasks(), db, None)

            saved = list(db.scalars(select(InformacionInstitucional)))
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].contenido, source)
            self.assertTrue(first["fuente_guardada"])
            self.assertFalse(first["fuente_ya_existia"])
            self.assertTrue(second["fuente_ya_existia"])

        engine.dispose()

    def test_source_is_saved_even_when_gemini_is_unavailable(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        source = "La biblioteca universitaria brinda servicios de consulta durante el periodo escolar vigente."
        request = ImportarInformacionRequest(
            nombre_archivo="biblioteca.md",
            texto=source,
            contenido_publico_confirmado=True,
        )
        with Session(engine) as db:
            with patch("routers.admin.suggest_information", side_effect=GeminiConfigurationError("Gemini no configurado")):
                result = draft_information_from_document(request, BackgroundTasks(), db, None)
            saved = list(db.scalars(select(InformacionInstitucional)))
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].contenido, source)
            self.assertIn("Gemini no configurado", result["aviso_analisis"])

        engine.dispose()

    def test_public_information_can_be_filtered_to_active_announcements(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add_all([
                InformacionInstitucional(
                    clave="aviso-vigente", titulo="Convocatoria", contenido="Publicada.",
                    categoria="Avisos", activo=True,
                ),
                InformacionInstitucional(
                    clave="aviso-archivado", titulo="Aviso anterior", contenido="Archivado.",
                    categoria="Avisos", activo=False,
                ),
                InformacionInstitucional(
                    clave="servicios", titulo="Servicios", contenido="Información general.",
                    categoria="General", activo=True,
                ),
            ])
            db.commit()

            records = list_public_information(q=None, categoria="avisos", db=db)

            self.assertEqual([record.clave for record in records], ["aviso-vigente"])
        engine.dispose()

    def test_pdf_upload_checks_extension_and_signature(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            with patch.object(institutional_documents, "UPLOAD_DIRECTORY", Path(directory)):
                key, name = store_pdf("mapa curricular.pdf", b"%PDF-1.7\npublic demo")
                self.assertEqual(name, "mapa curricular.pdf")
                self.assertTrue((Path(directory) / f"{key}.pdf").is_file())
                with self.assertRaises(DocumentValidationError):
                    store_pdf("mapa.exe", b"%PDF-1.7\n")
                with self.assertRaises(DocumentValidationError):
                    store_pdf("falso.pdf", b"not a pdf")

    def test_only_active_public_information_exposes_attached_pdf(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory, Session(engine) as db:
            upload_dir = Path(directory)
            active = InformacionInstitucional(
                clave="mapa-ti", titulo="Mapa curricular de TI", contenido="Consulta el PDF del mapa curricular.",
                categoria="Oferta educativa", activo=True,
            )
            archived = InformacionInstitucional(
                clave="mapa-archivado", titulo="Mapa archivado", contenido="No publicado.",
                categoria="Oferta educativa", activo=False,
            )
            db.add_all([active, archived])
            db.flush()
            visible_doc = DocumentoInstitucional(
                informacion_id=active.id, nombre_archivo="mapa-ti.pdf", archivo_key="visible-key",
                mime_type="application/pdf", tamano_bytes=12, activo=True,
            )
            hidden_doc = DocumentoInstitucional(
                informacion_id=archived.id, nombre_archivo="mapa-archivado.pdf", archivo_key="hidden-key",
                mime_type="application/pdf", tamano_bytes=12, activo=True,
            )
            db.add_all([visible_doc, hidden_doc])
            db.commit()
            (upload_dir / "visible-key.pdf").write_bytes(b"%PDF-1.7\n")

            with patch("routers.public.UPLOAD_DIRECTORY", upload_dir):
                records = list_public_documents("mapa curricular", db)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["nombre_archivo"], "mapa-ti.pdf")
                self.assertEqual(records[0]["url"], f"/api/v1/documentos/{visible_doc.id}/archivo")
                self.assertEqual(list_public_documents("biblioteca", db), [])
                response = get_public_document(visible_doc.id, db)
                self.assertEqual(response.media_type, "application/pdf")
                self.assertTrue(Path(response.path).is_file())
                with self.assertRaises(HTTPException) as error:
                    get_public_document(hidden_doc.id, db)
                self.assertEqual(error.exception.status_code, 404)

        engine.dispose()

    def test_legacy_permanent_document_delete_now_moves_file_to_trash(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory, Session(engine) as db:
            upload_dir = Path(directory)
            information = InformacionInstitucional(
                clave="info-publica", titulo="Información pública", contenido="Contenido conservado.",
                categoria="General", activo=True,
            )
            db.add(information)
            db.flush()
            attachment = DocumentoInstitucional(
                informacion_id=information.id, nombre_archivo="guia.pdf", archivo_key="remove-key",
                mime_type="application/pdf", tamano_bytes=12, activo=False,
            )
            db.add(attachment)
            db.commit()
            document_id = attachment.id
            file_path = upload_dir / "remove-key.pdf"
            file_path.write_bytes(b"%PDF-1.7\n")

            with patch.object(institutional_documents, "UPLOAD_DIRECTORY", upload_dir):
                response = delete_institutional_document(document_id, db)

            self.assertEqual(response.status_code, 204)
            self.assertIsNotNone(db.get(DocumentoInstitucional, document_id))
            self.assertIsNotNone(db.get(DocumentoInstitucional, document_id).papelera_en)
            self.assertIsNotNone(db.get(InformacionInstitucional, information.id))
            self.assertTrue(file_path.exists())

        engine.dispose()


if __name__ == "__main__":
    unittest.main()

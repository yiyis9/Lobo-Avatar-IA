from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database import Base
from models import DocumentoInstitucional, InformacionInstitucional
from routers.admin import list_trash, restore_trashed_document, restore_trashed_information, trash_document, trash_information
from services.trash import move_information_to_trash, purge_expired_trash


class TrashTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def add_record(self, key: str = "guide", deleted_at: datetime | None = None):
        item = InformacionInstitucional(
            clave=key, titulo=f"Guía {key}", contenido="Contenido público.", categoria="General", activo=True,
        )
        self.db.add(item)
        self.db.flush()
        document = DocumentoInstitucional(
            informacion_id=item.id, nombre_archivo=f"{key}.pdf", archivo_key=f"{key}-file",
            mime_type="application/pdf", tamano_bytes=10, activo=True, papelera_en=deleted_at,
        )
        self.db.add(document)
        self.db.commit()
        return item, document

    def test_archived_information_moves_with_documents_and_can_be_restored(self) -> None:
        item, document = self.add_record()
        trash_information(item.id, self.db, None)
        self.db.refresh(item)
        self.db.refresh(document)
        self.assertFalse(item.activo)
        self.assertIsNotNone(item.papelera_en)
        self.assertFalse(document.activo)
        self.assertEqual(document.papelera_en, item.papelera_en)

        restore_trashed_information(item.id, self.db, None)
        self.db.refresh(item)
        self.assertIsNone(item.papelera_en)
        self.assertFalse(item.activo)
        self.assertIsNone(document.papelera_en)
        self.assertTrue(document.activo)

    def test_document_can_be_trashed_and_restored_if_parent_is_available(self) -> None:
        _, document = self.add_record()
        trash_document(document.id, self.db, None)
        self.db.refresh(document)
        self.assertFalse(document.activo)
        self.assertIsNotNone(document.papelera_en)
        restore_trashed_document(document.id, self.db, None)
        self.db.refresh(document)
        self.assertTrue(document.activo)
        self.assertIsNone(document.papelera_en)

    def test_list_hides_documents_nested_under_trashed_information(self) -> None:
        item, _ = self.add_record()
        trash_information(item.id, self.db, None)
        result = list_trash(self.db, None)
        self.assertEqual([entry["titulo"] for entry in result["informacion"]], [item.titulo])
        self.assertEqual(result["documentos"], [])

    def test_expired_entries_and_their_files_are_purged_after_retention(self) -> None:
        old = datetime(2025, 1, 1, 12, 0, 0)
        item, document = self.add_record("expired")
        move_information_to_trash(item, self.db, old)
        self.db.commit()
        file_key = document.archivo_key
        with patch("services.trash.discard_pdf") as discard:
            removed = purge_expired_trash(self.db, old + timedelta(days=31))
        self.assertEqual(removed, 2)
        self.assertIsNone(self.db.get(DocumentoInstitucional, document.id))
        self.assertIsNone(self.db.get(InformacionInstitucional, item.id))
        discard.assert_called_once_with(file_key)

    def test_recent_trash_is_not_purged(self) -> None:
        now = datetime(2025, 2, 1, 12, 0, 0)
        item, document = self.add_record("recent", now - timedelta(days=29))
        self.assertEqual(purge_expired_trash(self.db, now), 0)
        self.assertIsNotNone(self.db.get(InformacionInstitucional, item.id))
        self.assertIsNotNone(self.db.get(DocumentoInstitucional, document.id))


if __name__ == "__main__":
    unittest.main()

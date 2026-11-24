import os
import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi import HTTPException

from models import Usuario
from security import hash_password, is_principal_admin, require_principal_admin, verify_password


class PrincipalAdminTests(unittest.TestCase):
    def make_user(self, correo: str) -> Usuario:
        return Usuario(
            id=1,
            nombre="Admin",
            correo=correo,
            password_hash="unused",
            rol="admin",
            activo=True,
            estado_solicitud="aprobada",
            creado_en=datetime.now(),
        )

    def test_designated_admin_is_principal(self) -> None:
        user = self.make_user("irisgf999@gmail.com")
        with patch.dict(os.environ, {"PRINCIPAL_ADMIN_EMAIL": user.correo}):
            self.assertTrue(is_principal_admin(user))
            self.assertIs(require_principal_admin(user), user)

    def test_other_admin_cannot_use_principal_actions(self) -> None:
        user = self.make_user("otro@example.com")
        with patch.dict(os.environ, {"PRINCIPAL_ADMIN_EMAIL": "irisgf999@gmail.com"}):
            self.assertFalse(is_principal_admin(user))
            with self.assertRaises(HTTPException) as error:
                require_principal_admin(user)
            self.assertEqual(error.exception.status_code, 403)

    def test_unconfigured_principal_denies_privileged_actions(self) -> None:
        user = self.make_user("irisgf999@gmail.com")
        with patch.dict(os.environ, {"PRINCIPAL_ADMIN_EMAIL": ""}):
            with self.assertRaises(HTTPException) as error:
                require_principal_admin(user)
            self.assertEqual(error.exception.status_code, 403)

    def test_password_verification_accepts_only_matching_password(self) -> None:
        password_hash = hash_password("test-password-123")
        self.assertTrue(verify_password("test-password-123", password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))


if __name__ == "__main__":
    unittest.main()

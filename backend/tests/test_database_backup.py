import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.database_backup import BackupConfigurationError, create_database_backup


class DatabaseBackupTests(unittest.TestCase):
    @patch("services.database_backup.engine", SimpleNamespace(url="mysql+pymysql://backup_user:secret%40pw@localhost:3306/lobo_upvt_db"))
    @patch("services.database_backup._find_mysqldump", return_value="mysqldump")
    @patch("services.database_backup.subprocess.run")
    def test_creates_non_destructive_sql_dump(self, run, _find_mysqldump) -> None:
        def write_dump(command, **kwargs):
            kwargs["stdout"].write(b"CREATE TABLE example (id INT);\n")
            self.assertIn("--skip-add-drop-table", command)
            self.assertIn("--single-transaction", command)
            self.assertNotIn("secret", " ".join(command))
            return subprocess.CompletedProcess(command, 0, stderr=b"")

        run.side_effect = write_dump
        path = create_database_backup()
        try:
            self.assertEqual(path.read_bytes(), b"CREATE TABLE example (id INT);\n")
        finally:
            path.unlink(missing_ok=True)

    @patch("services.database_backup.engine", SimpleNamespace(url="mysql+pymysql://backup_user:secret@localhost:3306/lobo_upvt_db"))
    @patch("services.database_backup._find_mysqldump", return_value="mysqldump")
    @patch("services.database_backup.subprocess.run")
    def test_removes_partial_dump_after_mysqldump_failure(self, run, _find_mysqldump) -> None:
        def fail_dump(command, **kwargs):
            kwargs["stdout"].write(b"partial")
            return subprocess.CompletedProcess(command, 2, stderr=b"credentials must not leak")

        run.side_effect = fail_dump
        with self.assertRaises(BackupConfigurationError) as error:
            create_database_backup()
        self.assertNotIn("credentials must not leak", str(error.exception))


if __name__ == "__main__":
    unittest.main()

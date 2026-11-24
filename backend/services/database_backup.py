import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.engine import make_url

from database import engine


class BackupConfigurationError(RuntimeError):
    pass


def _find_mysqldump() -> str:
    configured = os.getenv("MYSQLDUMP_PATH")
    executable = configured or shutil.which("mysqldump")
    if not executable and os.name == "nt":
        candidates = sorted(Path(r"C:\Program Files\MySQL").glob("MySQL Server */bin/mysqldump.exe"), reverse=True)
        executable = str(candidates[0]) if candidates else None
    if not executable:
        raise BackupConfigurationError(
            "No se encontró mysqldump. Instala MySQL Client o configura MYSQLDUMP_PATH en backend/.env."
        )
    return executable


def _option_value(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise BackupConfigurationError("La configuración de MySQL contiene un valor no válido para el respaldo.")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def create_database_backup() -> Path:
    url = make_url(engine.url)
    if not url.database:
        raise BackupConfigurationError("La conexión de MySQL no tiene una base de datos configurada.")

    executable = _find_mysqldump()
    options = [
        f"host={_option_value(url.host or 'localhost')}",
        f"port={url.port or 3306}",
        f"user={_option_value(url.username or '')}",
        "default-character-set=utf8mb4",
    ]
    if url.password is not None:
        options.append(f"password={_option_value(url.password)}")

    option_file_path: Path | None = None
    backup_path: Path | None = None
    completed = False
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".cnf", delete=False) as option_file:
            option_file.write("[client]\n" + "\n".join(options) + "\n")
            option_file_path = Path(option_file.name)
        with tempfile.NamedTemporaryFile("wb", suffix=".sql", delete=False) as backup_file:
            backup_path = Path(backup_file.name)
            result = subprocess.run(
                [
                    executable,
                    f"--defaults-extra-file={option_file_path}",
                    "--single-transaction",
                    "--routines",
                    "--events",
                    "--triggers",
                    "--hex-blob",
                    "--no-tablespaces",
                    "--skip-add-drop-table",
                    "--databases",
                    url.database,
                ],
                stdout=backup_file,
                stderr=subprocess.PIPE,
                timeout=300,
                check=False,
            )
        if result.returncode != 0:
            raise BackupConfigurationError(
                "MySQL no pudo generar el respaldo. Verifica permisos, conexión y la ruta de mysqldump."
            )
        completed = True
        return backup_path
    except subprocess.TimeoutExpired as error:
        raise BackupConfigurationError("El respaldo tardó demasiado. Inténtalo de nuevo.") from error
    except OSError as error:
        raise BackupConfigurationError("No se pudo iniciar mysqldump. Verifica MYSQLDUMP_PATH.") from error
    finally:
        if option_file_path:
            option_file_path.unlink(missing_ok=True)
        if not completed and backup_path:
            backup_path.unlink(missing_ok=True)

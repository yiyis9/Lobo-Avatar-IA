"""Create the current empty schema on TiDB Starter without MySQL FULLTEXT indexes.

This is additive and safe to run on each Render start: it only creates missing
tables and ensures the one-time administrator recovery state exists. It never
imports local records or deletes/changes existing rows.
"""

from __future__ import annotations

import os

import models  # noqa: F401 - registers every ORM model with Base.metadata
from database import Base, SessionLocal, engine
from models import EstadoRelevoAdmin


def main() -> None:
    if os.getenv("BOOTSTRAP_DATABASE_SCHEMA", "").strip().lower() != "true":
        raise SystemExit("Set BOOTSTRAP_DATABASE_SCHEMA=true to initialize a new host database.")

    # TiDB Starter supports most MySQL syntax but FULLTEXT indexes are not
    # available in every Starter region. The kiosk already falls back to LIKE.
    skipped_indexes = []
    for table in Base.metadata.tables.values():
        for index in tuple(table.indexes):
            if index.dialect_options["mysql"].get("prefix", "").upper() == "FULLTEXT":
                table.indexes.remove(index)
                skipped_indexes.append(index)

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        if session.get(EstadoRelevoAdmin, 1) is None:
            session.add(EstadoRelevoAdmin(id=1, usada_en=None, usada_por_id=None))
            session.commit()

    print(
        "Database schema ready. Existing records were preserved; "
        f"{len(skipped_indexes)} optional FULLTEXT indexes were skipped."
    )


if __name__ == "__main__":
    main()

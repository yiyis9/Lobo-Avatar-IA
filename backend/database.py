import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import TIMESTAMP, URL, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()


def _database_url() -> URL | str:
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        url = make_url(configured_url)
        if url.drivername == "mysql":
            return url.set(drivername="mysql+pymysql")
        return url

    password = os.getenv("DB_PASSWORD")
    if not password:
        raise RuntimeError("Configura DATABASE_URL o DB_PASSWORD en el entorno del backend.")

    return URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", "lobo_api"),
        password=password,
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "lobo_upvt_db"),
        query={"charset": "utf8mb4"},
    )


class Base(DeclarativeBase):
    pass


engine = create_engine(
    _database_url(),
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=max(1, min(20, int(os.getenv("DB_POOL_SIZE", "5")))),
    max_overflow=max(0, min(40, int(os.getenv("DB_MAX_OVERFLOW", "10")))),
    pool_timeout=max(1, min(60, int(os.getenv("DB_POOL_TIMEOUT", "10")))),
    pool_use_lifo=True,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        yield db


def check_database_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

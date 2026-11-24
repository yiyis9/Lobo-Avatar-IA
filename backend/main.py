import asyncio
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from database import SessionLocal, check_database_connection
from routers import admin, auth, public
from services.trash import purge_expired_trash


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        check_database_connection()
    except SQLAlchemyError:
        # La interfaz pública puede mostrar el kiosko y el avatar aunque MySQL
        # esté temporalmente apagado. Las rutas que necesitan datos informarán
        # el estado no disponible mediante sus respuestas/health checks.
        logging.exception("MySQL no está disponible al iniciar; el kiosko se servirá en modo limitado")
    async def purge_daily() -> None:
        while True:
            await asyncio.sleep(24 * 60 * 60)
            try:
                with SessionLocal() as db:
                    removed = purge_expired_trash(db)
                if removed:
                    logging.info("Papelera: se purgaron %s elementos vencidos", removed)
            except Exception:
                logging.exception("No se pudo purgar la papelera vencida")

    try:
        with SessionLocal() as db:
            removed = purge_expired_trash(db)
        if removed:
            logging.info("Papelera: se purgaron %s elementos vencidos al iniciar", removed)
    except Exception:
        logging.exception("No se pudo revisar la papelera al iniciar")
    task = asyncio.create_task(purge_daily())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Lobo UPVT API",
    description="API pública del kiosco y API administrativa para el panel web.",
    version="2.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def prevent_private_and_kiosk_cache(request, call_next):
    force_https = os.getenv("FORCE_HTTPS", "").strip().lower() in {"1", "true", "yes"}
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    if force_https and request.url.path != "/health" and request.url.scheme != "https" and forwarded_proto != "https":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("HTTPS es obligatorio para este servicio.", status_code=426)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
    if request.url.scheme == "https" or forwarded_proto == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    path = request.url.path
    if (
        path == "/panel"
        or path.startswith("/panel/")
        or path in {"/kiosko", "/kiosko/"}
        or path.startswith("/kiosko/models/") and path.endswith(".glb")
    ):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.mount(
    "/accesibilidad",
    StaticFiles(directory=Path(__file__).parent / "static" / "accessibility"),
    name="accessibility-assets",
)
app.mount(
    "/home",
    StaticFiles(directory=Path(__file__).parent / "static" / "home"),
    name="home-assets",
)
app.mount(
    "/panel",
    StaticFiles(directory=Path(__file__).parent / "static" / "admin", html=True),
    name="admin-panel",
)
app.mount(
    "/kiosko",
    StaticFiles(directory=Path(__file__).parent / "static" / "kiosk", html=True),
    name="public-kiosk",
)


@app.get("/", tags=["Estado"])
def root() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "home" / "index.html")


@app.get("/health", tags=["Estado"])
def health() -> dict[str, str]:
    try:
        check_database_connection()
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="MySQL no está disponible.") from error
    return {"api": "operativa", "mysql": "conectado"}

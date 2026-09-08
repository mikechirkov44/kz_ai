import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import admin, auth, catalogs, documents, reports, uploads
from app.bootstrap import (
    ensure_admin_user,
    ensure_odata_settings,
    ensure_production_doc_number_column,
    ensure_sync_schedule_time_columns,
    ensure_sync_since_column,
)
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.http_errors import INTERNAL_ERROR_DETAIL
from app.middleware_rate_limit import rate_limit_middleware

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_sync_since_column(engine)
    ensure_production_doc_number_column(engine)
    ensure_sync_schedule_time_columns(engine)
    db = SessionLocal()
    try:
        ensure_admin_user(db)
        ensure_odata_settings(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> Response:
    if isinstance(exc, StarletteHTTPException):
        return await http_exception_handler(request, exc)
    if isinstance(exc, RequestValidationError):
        return await request_validation_exception_handler(request, exc)
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": INTERNAL_ERROR_DETAIL})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


app.middleware("http")(rate_limit_middleware)

# Last = outermost, so 500 JSON from the handler still gets CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(uploads.router)
app.include_router(reports.router)
app.include_router(admin.router)
app.include_router(catalogs.router)
app.include_router(documents.router)


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "docs": "/docs"}

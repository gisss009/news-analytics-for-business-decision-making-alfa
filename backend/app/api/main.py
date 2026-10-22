"""HTTP API прототипа (FastAPI). Запуск: uvicorn app.api.main:app --port 8000

Ошибки в едином формате {"error": {"code", "message", "trace_id"}}; trace_id приходит в заголовке X-Trace-Id
(или создаётся) и возвращается в ответе. OpenAPI: /openapi.json, документация: /docs.
"""
import contextvars
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.db import session
from app.core.logging import get_logger

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")
log = get_logger("api")

app = FastAPI(title="Новостная аналитика для бизнеса", version="0.1.0",
              description="Прототип: персонализированная лента событий и интерпретация с источниками.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["GET", "POST"], allow_headers=["*"], expose_headers=["X-Trace-Id"])


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


class ErrorBody(BaseModel):
    code: str
    message: str
    trace_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    # обработчик 500 работает уже вне middleware, поэтому trace_id берём из request.state
    tid = getattr(request.state, "trace_id", None) or trace_id_var.get()
    return JSONResponse(status_code=status, headers={"X-Trace-Id": tid},
                        content={"error": {"code": code, "message": message, "trace_id": tid}})


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    tid = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:16]
    request.state.trace_id = tid
    token = trace_id_var.set(tid)
    try:
        response = await call_next(request)
    finally:
        trace_id_var.reset(token)
    response.headers["X-Trace-Id"] = tid
    return response


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return error_response(request, exc.status, exc.code, exc.message)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    return error_response(request, exc.status_code, code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []))
    return error_response(request, 422, "invalid_request", f"{where}: {first.get('msg', 'неверный запрос')}")


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    log.exception("unhandled_error", extra={"path": request.url.path})
    return error_response(request, 500, "internal_error", "Внутренняя ошибка сервиса. Сообщите trace_id разработчикам.")


class Health(BaseModel):
    ok: bool
    llm_mode: str
    companies: int
    events: int


@app.get("/health", response_model=Health, tags=["service"])
def health() -> Health:
    with session() as conn:
        def count(table: str) -> int:
            try:
                return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except Exception:  # noqa: BLE001 — таблицы ещё нет до первой загрузки данных
                return 0
        return Health(ok=True, llm_mode=settings.llm_mode, companies=count("companies"), events=count("clusters"))


# маршруты подключаются после объявления app и обработчиков ошибок
from app.api import routes_clients  # noqa: E402

app.include_router(routes_clients.router)

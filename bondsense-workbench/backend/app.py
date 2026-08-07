import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.auth.dependencies import auth_middleware
from backend.config.config import CORS_ORIGINS
from backend.integrations.legacy_api import LegacyApiClient
from backend.repositories.message_repository import MessageRepository
from backend.routers.conversations import router as conversations_router
from backend.routers.projects import router as projects_router
from backend.routers.sidebar import router as sidebar_router
from backend.routers.computer import router as computer_router


logger = logging.getLogger(__name__)
app = FastAPI(title="BondSense Workbench Backend")

app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.middleware("http")(auth_middleware)

app.state.repository = MessageRepository.from_environment()
app.state.legacy_api = LegacyApiClient()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": detail.get("code", "HTTP_ERROR"), "message": detail.get("message", "请求失败"), "details": detail.get("details", {})}})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "请求参数无效", "details": {"errors": exc.errors()}}})


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(sidebar_router)
app.include_router(projects_router)
app.include_router(conversations_router)
app.include_router(computer_router)


@app.on_event("startup")
def startup_event():
    app.state.repository.ensure_tables()
    interrupted = app.state.repository.mark_streaming_messages_interrupted()
    if interrupted:
        logger.warning("已将 %d 条未完成助手消息标记为 interrupted", interrupted)


@app.on_event("shutdown")
async def shutdown_event():
    await app.state.legacy_api.close()

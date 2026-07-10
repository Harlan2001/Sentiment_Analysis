from dotenv import load_dotenv
load_dotenv()

from backend.common.logging_config import setup_logging
setup_logging()

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.common.database import DatabaseConfig, init_database
from backend.vector_store import get_faiss_store
from backend.config.config import MYSQL_CONFIG
from backend.routers.ai_strategy import router as ai_strategy_router
from backend.routers.strategy import router as strategy_router, start_strategy_services, stop_strategy_services
from backend.routers.macro import router as macro_router
from backend.routers.factors import router as factors_router
from backend.routers.news import router as news_router
from backend.routers.pipeline import router as pipeline_router
from backend.routers.forecast import router as forecast_router
from backend.routers.chat import router as chat_router
from backend.routers.graph_augment import router as graph_augment_router
from backend.routers.report import router as report_router
from backend.routers.change import router as change_router
from backend.routers.auth import router as auth_router
from backend.auth.dependencies import auth_middleware

app = FastAPI(title="Bond Yield Backend")

logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 认证中间件（根据 AUTH_ENABLED 配置决定是否拦截）
app.middleware("http")(auth_middleware)

app.include_router(auth_router)
app.include_router(ai_strategy_router)
app.include_router(strategy_router)
app.include_router(macro_router)
app.include_router(factors_router)
app.include_router(news_router)
app.include_router(pipeline_router)
app.include_router(forecast_router)
app.include_router(chat_router)
app.include_router(graph_augment_router)
app.include_router(report_router)
app.include_router(change_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def startup_event():
    db_config = DatabaseConfig(**MYSQL_CONFIG)
    init_database(db_config)
    try:
        store = get_faiss_store()
        logger.info("FaissStore loaded | vectors=%d, dim=%d", store.size(), store.dim)
    except Exception as exc:
        logger.warning("FaissStore unavailable, startup continues: %s", exc)


@app.on_event("startup")
async def startup_services():
    await start_strategy_services()


@app.on_event("shutdown")
async def shutdown_services():
    await stop_strategy_services()

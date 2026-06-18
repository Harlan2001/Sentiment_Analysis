from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.common.database import DatabaseConfig, init_database
from backend.vector_store import get_faiss_store
from backend.config.config import MYSQL_CONFIG
from backend.strategy.ai_strategy_router import router as ai_strategy_recommendation_router
from backend.routers.strategy import router as strategy_router, start_strategy_services, stop_strategy_services
from backend.routers.macro import router as macro_router
from backend.routers.factors import router as factors_router
from backend.routers.news import router as news_router
from backend.routers.pipeline import router as pipeline_router
from backend.routers.forecast import router as forecast_router
from backend.routers.chat import router as chat_router
from backend.routers.graph_augment import router as graph_augment_router
from backend.routers.report import router as report_router

app = FastAPI(title="Bond Yield Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_strategy_recommendation_router)
app.include_router(strategy_router)
app.include_router(macro_router)
app.include_router(factors_router)
app.include_router(news_router)
app.include_router(pipeline_router)
app.include_router(forecast_router)
app.include_router(chat_router)
app.include_router(graph_augment_router)
app.include_router(report_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def startup_event():
    db_config = DatabaseConfig(**MYSQL_CONFIG)
    init_database(db_config)
    try:
        store = get_faiss_store()
        print(f"[STARTUP] FaissStore loaded | vectors={store.size()}, dim={store.dim}")
    except Exception as exc:
        print(f"[STARTUP] FaissStore unavailable, startup continues: {exc}")


@app.on_event("startup")
async def startup_services():
    await start_strategy_services()


@app.on_event("shutdown")
async def shutdown_services():
    await stop_strategy_services()

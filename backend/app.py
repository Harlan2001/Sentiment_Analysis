from dotenv import load_dotenv

load_dotenv()
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.common.logging_config import setup_logging

setup_logging()
from backend.auth.dependencies import auth_middleware
from backend.common.database import DatabaseConfig, init_database
from backend.common.vector_store import get_faiss_store
from backend.config.config import MYSQL_CONFIG
from backend.integrations.feishu.repository import FeishuConnectionRepository
from backend.repositories.ai_strategy_history_repository import AiStrategyHistoryRepository
from backend.repositories.project_management_repository import ProjectManagementRepository
from backend.repositories.user_memory_repository import UserMemoryRepository
from backend.routers.ai_strategy_generation import (
    router as ai_strategy_generation_router,
)
from backend.routers.auth import router as auth_router
from backend.routers.change import router as change_router
from backend.routers.credit_spread import router as credit_spread_router
from backend.routers.daily_news_summary import router as daily_news_summary_router
from backend.routers.dashboard import router as dashboard_router
from backend.routers.discover import router as discover_router
from backend.routers.factors import router as factors_router
from backend.routers.feishu_mcp import router as feishu_mcp_router
from backend.routers.file_library import router as file_library_router
from backend.routers.forecast import router as forecast_router
from backend.routers.futures import router as futures_router
from backend.routers.graph_augment import router as graph_augment_router
from backend.routers.macro import router as macro_router
from backend.routers.macro_data import router as macro_data_router
from backend.routers.mcp_business import router as mcp_business_router
from backend.routers.news import router as news_router
from backend.routers.pipeline import router as pipeline_router
from backend.routers.policy_documents import router as policy_documents_router
from backend.routers.portfolios import router as portfolios_router
from backend.routers.report import router as report_router
from backend.routers.report_generation import router as report_generation_router
from backend.routers.research import router as research_router
from backend.routers.returns import router as returns_router
from backend.routers.skills import router as skills_router
from backend.routers.strategy import router as strategy_router
from backend.routers.treasury import router as treasury_router
from backend.routers.watchlist import router as watchlist_router
from backend.routers.workbench_computer import router as workbench_computer_router
from backend.routers.workbench_conversations import router as workbench_conversations_router
from backend.routers.workbench_memories import router as workbench_memories_router
from backend.routers.workbench_memories import settings_router as workbench_memory_settings_router
from backend.routers.workbench_project_management import (
    router as workbench_project_management_router,
)
from backend.routers.workbench_projects import router as workbench_projects_router
from backend.routers.workbench_sidebar import router as workbench_sidebar_router
from backend.routers.workbench_users import router as workbench_users_router

app = FastAPI(title="Bond Yield Backend")

logger = logging.getLogger(__name__)

# CORS：认证走 Bearer header / query param（不使用 cookie），
# 故去掉 allow_credentials，使 allow_origins=["*"] 组合合法；若将来需要带凭证请改白名单。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 认证中间件（根据 AUTH_ENABLED 配置决定是否拦截）
app.middleware("http")(auth_middleware)


# 未处理异常日志中间件
@app.middleware("http")
async def log_unhandled_exceptions(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception:
        logger.exception("未处理异常: %s %s", request.method, request.url.path)
        raise


app.include_router(auth_router)
app.include_router(ai_strategy_generation_router)
app.include_router(macro_router)
app.include_router(factors_router)
app.include_router(news_router)
app.include_router(pipeline_router)
app.include_router(policy_documents_router)
app.include_router(portfolios_router)
app.include_router(forecast_router)
app.include_router(futures_router)
app.include_router(graph_augment_router)
app.include_router(report_router)
app.include_router(report_generation_router)
app.include_router(research_router)
app.include_router(change_router)
app.include_router(credit_spread_router)
app.include_router(dashboard_router)
app.include_router(macro_data_router)
app.include_router(mcp_business_router)
app.include_router(discover_router)
app.include_router(returns_router)
app.include_router(daily_news_summary_router)
app.include_router(workbench_sidebar_router)
app.include_router(workbench_projects_router)
app.include_router(workbench_conversations_router)
app.include_router(workbench_memories_router)
app.include_router(workbench_memory_settings_router)
app.include_router(workbench_project_management_router)
app.include_router(workbench_computer_router)
app.include_router(watchlist_router)
app.include_router(feishu_mcp_router)
app.include_router(file_library_router)
app.include_router(skills_router)
app.include_router(strategy_router)
app.include_router(treasury_router)
app.include_router(workbench_users_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def startup_event():
    db_config = DatabaseConfig(**MYSQL_CONFIG)
    init_database(db_config)
    # 显式探活一次：连接池 mincached 已在建池时拨号，这里再确认鉴权可用，
    # 让 DB 不可达在启动日志里立刻暴露，而不是拖慢第一个用户请求。
    try:
        from backend.common.database import get_repo_connection

        with get_repo_connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        logger.info("Repo DB connection warmed up")
    except Exception:
        logger.warning("Repo DB warmup failed, startup continues", exc_info=True)
    try:
        store = get_faiss_store()
        logger.info("FaissStore loaded | vectors=%d, dim=%d", store.size(), store.dim)
    except Exception as exc:
        logger.warning("FaissStore unavailable, startup continues: %s", exc)


@app.on_event("startup")
def startup_workbench():
    """工作台仓储映射迁移：启动时确保 workbench_* 表存在并清理遗留 streaming 状态。"""
    app.state.repository = ProjectManagementRepository.from_environment()
    app.state.user_memory_repository = UserMemoryRepository.from_environment()
    app.state.repository.ensure_tables()
    history_repository = AiStrategyHistoryRepository.from_environment()
    try:
        history_repository.warmup()
        logger.info("AI strategy history DB connection warmed up")
    except Exception:
        logger.warning(
            "AI strategy history DB warmup failed, startup continues", exc_info=True
        )
    history_repository.ensure_recycle_bin_schema()
    history_repository.ensure_progress_schema()
    app.state.feishu_mcp_repository = FeishuConnectionRepository()
    interrupted = app.state.repository.mark_streaming_messages_interrupted()
    if interrupted:
        logger.warning("已将 %d 条未完成工作台助手消息标记为 interrupted", interrupted)


@app.on_event("startup")
async def startup_ai_tasks():
    """启动统一 AI 队列；数据库暂不可用时保持原有启动降级策略。"""
    from backend.task_execution.dispatcher import start_dispatcher, stop_dispatcher

    try:
        await start_dispatcher(app)
    except Exception:
        logger.exception("AI 任务调度器启动失败，排队任务将在数据库恢复后的重启中继续")
        await stop_dispatcher(app)


@app.on_event("shutdown")
async def shutdown_ai_tasks():
    from backend.task_execution.dispatcher import stop_dispatcher

    await stop_dispatcher(app)

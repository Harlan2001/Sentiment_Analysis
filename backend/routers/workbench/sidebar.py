from fastapi import APIRouter, Query, Request

from backend.config.config import API_PREFIX
from backend.news_summary.repository import DailyNewsSummaryRepository
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.report_generation_repository import ReportGenerationRepository
from backend.routers.workbench.helpers import raise_repository_error
from backend.strategy.ai_strategy_history import AiStrategyHistoryRepository

router = APIRouter(prefix=f"{API_PREFIX}/workbench", tags=["workbench-sidebar"])


@router.get("/sidebar")
def get_sidebar(request: Request, conversation_limit: int = Query(default=5, ge=1, le=5)):
    repository: ConversationRepository = request.app.state.repository
    try:
        data = repository.get_sidebar(request.state.username, conversation_limit)
    except Exception as exc:
        raise_repository_error(exc)
    data["current_user"] = {
        "id": request.state.username,
        "username": request.state.username,
        "display_name": request.state.username,
        "authenticated": True,
        "role": getattr(request.state, "role", "user"),
    }
    return {"data": data}


@router.get("/deleted-items")
def get_deleted_items(request: Request):
    repository: ConversationRepository = request.app.state.repository
    try:
        username = request.state.username
        data = repository.list_deleted_items(username)
        data["deleted_strategies"] = AiStrategyHistoryRepository.from_environment().list_deleted_conversations(username)
        data["deleted_reports"] = ReportGenerationRepository.from_environment().list_deleted_tasks(username)
        data["deleted_news_summaries"] = DailyNewsSummaryRepository.from_environment().list_deleted_tasks(username)
        return {"data": data}
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("/deleted-items")
def empty_deleted_items(request: Request):
    """Permanently empty the current user's recycle bin across all modules."""
    repository: ConversationRepository = request.app.state.repository
    username = request.state.username
    try:
        counts = repository.permanently_delete_all_deleted_items(username)
        counts["strategies"] = AiStrategyHistoryRepository.from_environment().permanently_delete_all_deleted_conversations(username)
        counts["reports"] = ReportGenerationRepository.from_environment().permanently_delete_all_deleted_tasks(username)
        counts["news_summaries"] = DailyNewsSummaryRepository.from_environment().permanently_delete_all_deleted_tasks(username)
        return {"data": counts}
    except Exception as exc:
        raise_repository_error(exc)

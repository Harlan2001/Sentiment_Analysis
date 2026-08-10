from fastapi import APIRouter, Query, Request

from backend.config.config import API_PREFIX
from backend.repositories.conversation_repository import ConversationRepository
from backend.routers.workbench.helpers import raise_repository_error


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
        return {"data": repository.list_deleted_items(request.state.username)}
    except Exception as exc:
        raise_repository_error(exc)

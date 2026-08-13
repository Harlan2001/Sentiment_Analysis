import os

os.environ.setdefault("MYSQL_HOST", "127.0.0.1")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_USER", "test")
os.environ.setdefault("MYSQL_PASSWORD", "test")
os.environ.setdefault("MYSQL_DATABASE", "test")

import pytest
from pydantic import ValidationError

from backend.repositories.project_management_repository import ProjectManagementRepository
from backend.routers.workbench.project_management import (
    ProjectMemberUpsertRequest,
    ProjectMemoryCreateRequest,
    ProjectMemoryUpdateRequest,
)
from backend.routers.workbench.projects import ProjectCreateRequest


def test_project_create_accepts_idempotency_key_and_normalizes_name():
    request = ProjectCreateRequest(name="  利率   研究  ", client_request_id="request-1")
    assert request.name == "利率 研究"
    assert request.client_request_id == "request-1"

def test_project_create_accepts_initial_memory_and_members():
    request = ProjectCreateRequest(
        name="利率研究",
        initial_memories=[
            {"category": "goal", "title": "目标", "content": "识别利率拐点"}
        ],
        initial_members=[{"username": "analyst", "role": "editor"}],
    )
    assert request.initial_memories[0].category == "goal"
    assert request.initial_members[0].role == "editor"


def test_project_create_rejects_duplicate_initial_members():
    with pytest.raises(ValidationError):
        ProjectCreateRequest(
            name="利率研究",
            initial_members=[
                {"username": "analyst", "role": "editor"},
                {"username": "analyst", "role": "viewer"},
            ],
        )


def test_memory_contract_rejects_blank_content_and_empty_patch():
    with pytest.raises(ValidationError):
        ProjectMemoryCreateRequest(title="目标", content="   ")
    with pytest.raises(ValidationError):
        ProjectMemoryUpdateRequest()
    with pytest.raises(ValidationError):
        ProjectMemoryUpdateRequest(is_active=None)


def test_member_contract_only_accepts_minimum_project_roles():
    assert ProjectMemberUpsertRequest(role="editor").role == "editor"
    with pytest.raises(ValidationError):
        ProjectMemberUpsertRequest(role="owner")


def test_memory_context_only_contains_active_entries_and_respects_limit():
    repository = ProjectManagementRepository({})
    repository.list_project_memories = lambda *_args, **_kwargs: [
        {"category": "goal", "title": "目标", "content": "识别拐点"},
        {"category": "constraint", "title": "边界", "content": "不做投资建议"},
    ]
    context = repository.get_project_memory_context("owner", "project-1", max_chars=100)
    assert context is not None
    assert "[目标] 目标：识别拐点" in context
    assert "[约束] 边界：不做投资建议" in context

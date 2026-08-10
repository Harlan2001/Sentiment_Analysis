import os

os.environ.setdefault("MYSQL_HOST", "127.0.0.1")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_USER", "test")
os.environ.setdefault("MYSQL_PASSWORD", "test")
os.environ.setdefault("MYSQL_DATABASE", "test")

import pytest
from pydantic import ValidationError

from backend.repositories.workbench_repository import WorkbenchCursorError, _decode_cursor, _encode_cursor
from backend.routers.workbench.conversations import ConversationCreateRequest, MessageCreateRequest


def test_project_conversation_requires_project_id():
    with pytest.raises(ValidationError):
        ConversationCreateRequest(source="project")


def test_normal_conversation_rejects_project_id():
    with pytest.raises(ValidationError):
        ConversationCreateRequest(source="sidebar", project_id="project-1")


def test_message_strips_content_without_losing_newlines_inside_message():
    request = MessageCreateRequest(content="  第一行\n第二行  ", client_message_id=" request-1 ")
    assert request.content == "第一行\n第二行"
    assert request.client_message_id == "request-1"


def test_cursor_round_trip_and_rejects_invalid_value():
    cursor = _encode_cursor("2026-08-07T09:00:00", "conversation-1")
    assert _decode_cursor(cursor) == ("2026-08-07T09:00:00", "conversation-1")
    with pytest.raises(WorkbenchCursorError):
        _decode_cursor("not-a-cursor")

"""File library items are copied into chat only for their owner."""

from unittest.mock import MagicMock

import pytest
from starlette.requests import Request

from backend.repositories.file_library_repository import FileLibraryRepository
from backend.repositories.workbench_repository import WorkbenchNotFoundError
from backend.routers import file_library, workbench_conversations


def _repository_with_cursor() -> tuple[FileLibraryRepository, MagicMock]:
    repository = FileLibraryRepository()
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    repository._connection = MagicMock()
    repository._connection.return_value.__enter__.return_value = connection
    return repository, cursor


def test_file_library_chat_filter_only_returns_mountable_items(monkeypatch):
    repository = MagicMock()
    repository.list_files.return_value = [
        {"id": "skill:1", "name": "paper.pdf", "source": "Skills 附件", "format": "PDF", "kind": "upload", "created_at": "2026-11-26T10:00:00", "chat_mountable": True},
        {"id": "figure:2", "name": "figure.png", "source": "研报抽取图表", "format": "PNG", "kind": "generated", "created_at": "2026-11-26T09:00:00", "chat_mountable": False},
    ]
    monkeypatch.setattr(file_library, "_repository", lambda: repository)
    request = Request({"type": "http", "headers": []})
    request.state.username = "alice"

    response = file_library.list_file_library(
        request, purpose="chat_attachment", page=1, page_size=50
    )

    assert response["data"]["total"] == 1
    assert response["data"]["items"][0]["id"] == "skill:1"
    repository.list_files.assert_called_once_with("alice")


def test_owned_skill_file_can_be_read_for_chat(tmp_path, monkeypatch):
    skill_folder = tmp_path / "skill-1"
    skill_folder.mkdir()
    (skill_folder / "saved.md").write_text("# Evidence", encoding="utf-8")
    monkeypatch.setattr("backend.repositories.skill_repository.ATTACHMENT_ROOT", tmp_path)
    repository, cursor = _repository_with_cursor()
    cursor.fetchone.return_value = {
        "skill_id": "skill-1", "stored_filename": "saved.md",
        "original_filename": "research.md",
    }

    filename, content = repository.read_for_chat("alice", "skill_attachment", "attachment-1")

    assert (filename, content) == ("research.md", b"# Evidence")
    assert cursor.execute.call_args.args[1] == ("attachment-1", "alice", "alice")


def test_policy_file_uses_its_owned_parsed_text():
    repository, cursor = _repository_with_cursor()
    cursor.fetchone.return_value = {
        "title": "政策研究", "original_filename": "policy.pdf", "full_text": "政策要点\n第二行",
    }

    filename, content = repository.read_for_chat("alice", "policy_document", "42")

    assert filename == "policy.txt"
    assert content.decode("utf-8") == "政策要点\n第二行"
    assert cursor.execute.call_args.args[1] == ("42", "alice")


def test_other_users_file_cannot_be_read_for_chat():
    repository, cursor = _repository_with_cursor()
    cursor.fetchone.return_value = None

    with pytest.raises(WorkbenchNotFoundError):
        repository.read_for_chat("alice", "research_report", "other-report")

    assert cursor.execute.call_args.args[1] == ("other-report", "alice")


def test_import_route_copies_library_file_into_target_conversation(monkeypatch):
    library_repository = MagicMock()
    library_repository.read_for_chat.return_value = ("research.txt", b"Evidence")
    chat_repository = MagicMock()
    chat_repository.create_attachment.return_value = {
        "id": "chat-attachment-1", "original_filename": "research.txt",
        "size_bytes": 8, "page_count": None,
    }
    monkeypatch.setattr(
        workbench_conversations.FileLibraryRepository,
        "from_environment",
        lambda: library_repository,
    )
    monkeypatch.setattr(
        workbench_conversations.ChatAttachmentRepository,
        "from_environment",
        lambda: chat_repository,
    )
    request = Request({"type": "http", "headers": []})
    request.state.username = "alice"
    body = workbench_conversations.LibraryAttachmentRequest(
        source_key="skill_attachment", source_ref="attachment-1"
    )

    response = workbench_conversations.attach_library_file(request, "conversation-1", body)

    library_repository.read_for_chat.assert_called_once_with(
        "alice", "skill_attachment", "attachment-1"
    )
    chat_repository.create_attachment.assert_called_once_with(
        "alice", "conversation-1", "research.txt", b"Evidence"
    )
    assert response["data"]["id"] == "chat-attachment-1"

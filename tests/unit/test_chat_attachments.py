"""Message-scoped file evidence must stay within its conversation and retain citations."""

import uuid
from io import BytesIO
from unittest.mock import MagicMock
from zipfile import ZipFile

import pymupdf
import pytest

from backend.repositories.chat_attachment_repository import (
    ChatAttachmentRepository,
    purge_conversation_files,
    select_chat_attachment_context,
)
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.workbench_repository import (
    WorkbenchConflictError,
    WorkbenchNotFoundError,
    WorkbenchPermissionError,
)


def test_context_keeps_source_pages_and_reports_partial_coverage():
    rows = [
        {
            "attachment_id": "paper-1",
            "original_filename": "rates.pdf",
            "page_count": 12,
            "chunk_index": index,
            "source_location": f"第 {index + 1} 页",
            "content": f"第 {index + 1} 页的研究内容和回测方法",
        }
        for index in range(12)
    ]

    context = select_chat_attachment_context(rows, "分析回测", char_budget=380)

    assert "rates.pdf" in context
    assert "第 1 页" in context
    assert "已提供" in context and "12 个文本片段" in context
    assert "仅依据提供的片段" in context


def test_upload_rejects_fake_pdf_before_persisting(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.repositories.chat_attachment_repository.ATTACHMENT_ROOT", tmp_path)
    repository = ChatAttachmentRepository()
    repository.get_conversation = MagicMock(return_value={"owner_username": "alice", "status": "active"})
    repository._connection = MagicMock()

    with pytest.raises(ValueError, match="PDF"):
        repository.create_attachment("alice", "conversation-1", "paper.pdf", b"not a pdf")

    repository._connection.assert_not_called()
    assert not list(tmp_path.rglob("*"))


def test_binding_rejects_another_users_attachment():
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    with pytest.raises(WorkbenchNotFoundError):
        ChatAttachmentRepository.bind_to_message(
            cursor, "alice", "conversation-1", "message-1", ["other-users-file"]
        )

    sql, params = cursor.execute.call_args.args
    assert "owner_username" in sql and "conversation_id" in sql
    assert params == ("other-users-file", "alice", "conversation-1")


def test_reusing_client_message_id_with_a_different_pdf_is_rejected():
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"id": "first-paper"}]

    with pytest.raises(WorkbenchConflictError, match="不同附件"):
        ConversationRepository._require_same_attachments(cursor, "message-1", ["second-paper"])


def test_valid_pdf_is_parsed_and_saved_with_page_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.repositories.chat_attachment_repository.ATTACHMENT_ROOT", tmp_path)
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "A reproducible bond strategy uses daily yields")
    content = document.tobytes()
    document.close()

    repository = ChatAttachmentRepository()
    repository._conversation_for_user = MagicMock(
        return_value={"owner_username": "alice", "status": "active", "project_id": None}
    )
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    repository._connection = MagicMock()
    repository._connection.return_value.__enter__.return_value = connection

    result = repository.create_attachment("alice", "conversation-1", "bond-paper.pdf", content)

    assert result["page_count"] == 1
    assert result["original_filename"] == "bond-paper.pdf"
    assert cursor.executemany.call_args.args[1][0][2] == "第 1 页"
    assert list(tmp_path.rglob("*.pdf"))
    connection.commit.assert_called_once()


@pytest.mark.parametrize(
    ("filename", "content", "location"),
    [
        ("research.txt", "债券收益率样本外检验".encode(), "第 1-1 行"),
        ("notes.md", "# 研究结论\n样本外有效".encode(), "第 1-2 行"),
        ("returns.csv", "date,return\n2026-01-01,0.01".encode(), "第 1-2 行"),
    ],
)
def test_text_attachments_are_parsed_with_line_citations(tmp_path, monkeypatch, filename, content, location):
    monkeypatch.setattr("backend.repositories.chat_attachment_repository.ATTACHMENT_ROOT", tmp_path)
    repository = ChatAttachmentRepository()
    repository._conversation_for_user = MagicMock(
        return_value={"owner_username": "alice", "status": "active", "project_id": None}
    )
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    repository._connection = MagicMock()
    repository._connection.return_value.__enter__.return_value = connection

    result = repository.create_attachment("alice", "conversation-1", filename, content)

    assert result["original_filename"] == filename
    assert result["page_count"] is None
    assert cursor.executemany.call_args.args[1][0][2] == location
    assert list(tmp_path.rglob(f"*{filename[filename.rfind('.') :]}"))


def test_docx_attachment_is_parsed_with_paragraph_citation(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.repositories.chat_attachment_repository.ATTACHMENT_ROOT", tmp_path)
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>Bond research evidence</w:t></w:r></w:p></w:body></w:document>',
        )
    repository = ChatAttachmentRepository()
    repository._conversation_for_user = MagicMock(
        return_value={"owner_username": "alice", "status": "active", "project_id": None}
    )
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    repository._connection = MagicMock()
    repository._connection.return_value.__enter__.return_value = connection

    repository.create_attachment("alice", "conversation-1", "paper.docx", buffer.getvalue())

    assert cursor.executemany.call_args.args[1][0][2] == "第 1 段"


def test_binary_content_disguised_as_text_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.repositories.chat_attachment_repository.ATTACHMENT_ROOT", tmp_path)
    repository = ChatAttachmentRepository()
    repository._connection = MagicMock()

    with pytest.raises(ValueError, match="二进制"):
        repository.create_attachment("alice", "conversation-1", "paper.txt", b"text\x00binary")

    repository._connection.assert_not_called()


def test_invalid_docx_is_rejected_before_persisting(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.repositories.chat_attachment_repository.ATTACHMENT_ROOT", tmp_path)
    repository = ChatAttachmentRepository()
    repository._connection = MagicMock()

    with pytest.raises(ValueError, match="DOCX"):
        repository.create_attachment("alice", "conversation-1", "paper.docx", b"not a zip")

    repository._connection.assert_not_called()


def test_project_manager_cannot_upload_to_another_members_conversation(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.repositories.chat_attachment_repository.ATTACHMENT_ROOT", tmp_path)
    repository = ChatAttachmentRepository()
    repository._conversation_for_user = MagicMock(
        return_value={
            "owner_username": "bob", "project_id": "project-1",
            "project_role": "manager", "status": "active",
        }
    )
    repository._connection = MagicMock()

    with pytest.raises(WorkbenchPermissionError):
        repository.create_attachment("alice", "conversation-1", "paper.pdf", b"%PDF-example")

    assert not list(tmp_path.rglob("*.pdf"))


def test_permanent_conversation_deletion_removes_stored_pdfs(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.repositories.chat_attachment_repository.ATTACHMENT_ROOT", tmp_path)
    conversation_id = "conversation-1"
    folder = tmp_path / uuid.uuid5(uuid.NAMESPACE_URL, conversation_id).hex
    folder.mkdir()
    (folder / "paper.pdf").write_bytes(b"%PDF-example")

    purge_conversation_files(conversation_id)

    assert not folder.exists()


def test_strategy_paper_skill_seed_requires_cited_reproducible_analysis():
    from pathlib import Path

    seed = (Path(__file__).resolve().parents[2] / "sql" / "031_strategy_paper_skill.sql").read_text(
        encoding="utf-8"
    )
    for required in ("金融论文审阅", "样本外", "前视", "页码", "可复现", "不得伪造"):
        assert required in seed


@pytest.mark.asyncio
async def test_agent_treats_conversation_pdf_as_untrusted_cited_evidence(monkeypatch):
    from backend.agent import chat_service

    captured = {}

    async def fake_agent_loop(**kwargs):
        captured.update(kwargs)
        yield 'data: {"type":"content","content":"ok"}'

    monkeypatch.setattr(chat_service, "run_agent_loop", fake_agent_loop)
    original = [{"role": "user", "content": "分析论文"}]

    chunks = [
        chunk async for chunk in chat_service.agent_chat_stream(
            original, "alice", chat_attachment_context="[文件：rates.pdf，第 3 页]\n样本外回测"
        )
    ]

    assert chunks == ["ok"]
    enriched = captured["messages"][-1]["content"]
    assert "<conversation_attachment_context>" in enriched
    assert "rates.pdf，第 3 页" in enriched
    assert "不可信资料" in enriched
    assert original[-1]["content"] == "分析论文"

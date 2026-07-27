"""Tests for `.env` loading (stdlib only, no backend required)."""
import os
import textwrap

import pytest

from sentiment_cli.config import Config, load_dotenv


@pytest.fixture(autouse=True)
def _clean_sentiment_env(monkeypatch):
    """Isolate each test from SENTIMENT_* leftover by other tests."""
    for key in list(os.environ):
        if key.startswith("SENTIMENT_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def dotenv_dir(tmp_path, monkeypatch):
    """chdir into a temp dir so <cwd>/.env is discoverable."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write_env(path, body):
    path.write_text(textwrap.dedent(body), encoding="utf-8")


def test_load_dotenv_from_cwd(dotenv_dir):
    _write_env(dotenv_dir / ".env", """
        # comment line, ignored
        SENTIMENT_BASE_URL=http://dotenv:7777
    """)
    loaded = load_dotenv()
    assert str(dotenv_dir / ".env") in loaded
    assert os.environ["SENTIMENT_BASE_URL"] == "http://dotenv:7777"
    assert Config().base_url == "http://dotenv:7777"


def test_load_dotenv_strips_quotes(dotenv_dir):
    _write_env(dotenv_dir / ".env", """
        SENTIMENT_BASE_URL="http://quoted:1234"
        SENTIMENT_TOKEN='abc123'
    """)
    load_dotenv()
    assert os.environ["SENTIMENT_BASE_URL"] == "http://quoted:1234"
    assert os.environ["SENTIMENT_TOKEN"] == "abc123"


def test_load_dotenv_does_not_override_existing_env(dotenv_dir, monkeypatch):
    monkeypatch.setenv("SENTIMENT_BASE_URL", "http://preset:1111")
    _write_env(dotenv_dir / ".env", """
        SENTIMENT_BASE_URL=http://dotenv:2222
    """)
    load_dotenv()
    # existing shell env must win; .env must NOT override it
    assert os.environ["SENTIMENT_BASE_URL"] == "http://preset:1111"
    assert Config().base_url == "http://preset:1111"


def test_load_dotenv_ignores_backend_env(dotenv_dir):
    # a backend-style .env with NO SENTIMENT_ key must be skipped
    _write_env(dotenv_dir / ".env", """
        MYSQL_HOST=10.253.50.134
        MYSQL_PASSWORD=secret
        kingstar_API_KEY=xyz
    """)
    loaded = load_dotenv()
    # the backend-style .env must NOT be treated as a CLI .env
    assert str(dotenv_dir / ".env") not in loaded
    assert "SENTIMENT_BASE_URL" not in os.environ
    # don't leak any CLI gateway vars loaded from sentiment-cli/.env
    # into the shared session (offline tests must stay deterministic).
    for k in ("SENTIMENT_CHAT_GATEWAY_URL", "SENTIMENT_CHAT_GATEWAY_KEY"):
        os.environ.pop(k, None)


def test_flag_overrides_dotenv(dotenv_dir):
    _write_env(dotenv_dir / ".env", """
        SENTIMENT_BASE_URL=http://dotenv:3333
    """)
    load_dotenv()
    assert Config(base_url="http://flag:4444").base_url == "http://flag:4444"

"""Unit tests — no backend required. Exercise the offline logic."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentiment_cli.cli import build_description, build_op_parser, coerce, UsageError
from sentiment_cli.client import Client
from sentiment_cli.config import Config
from sentiment_cli.spec import derive_name, load_spec


# ---- name derivation ---------------------------------------------------------
def test_derive_name_drops_tag_prefix():
    assert derive_name("news", "/sapi/news/sources") == "sources"
    assert derive_name("news", "/sapi/news/similar") == "similar"


def test_derive_name_path_param():
    assert derive_name("dashboard", "/sapi/dashboard/behavior/profile/{user_id}") == \
        "behavior-profile-by-user-id"


def test_derive_name_root_falls_back_to_tag():
    assert derive_name("news", "/sapi/news") == "news"


# ---- spec loading ------------------------------------------------------------
def test_bundled_spec_loads():
    spec = load_spec()
    assert spec.title == "Bond Yield Backend"
    # Bundled spec has 46 operations, but the 12 dashboard/* ops are
    # suppressed from the live command tree (KNOWN_GAPS
    # "dashboard-local-unavailable" -> hide_groups=["dashboard"]).
    assert "dashboard" not in spec.groups
    assert "pipeline" not in spec.groups
    # change trigger is visible again: it only depends on the LLM gateway
    # (verified reachable when the backend can egress to KingStar), not on the
    # embedding model — so it is NOT hidden like dashboard/pipeline.
    assert "change" in spec.groups
    change_ops = {o.name for o in spec.groups["change"]}
    assert change_ops == {"snapshots", "compare", "trigger"}
    assert len(spec.operations) == 33


def test_spec_group_aliases_applied():
    spec = load_spec()
    assert "recommend" in spec.groups   # aliased from ai-strategy
    assert "graph" in spec.groups       # aliased from graph-augment
    assert "ai-strategy" not in spec.groups


def test_spec_find_and_overrides():
    spec = load_spec()
    op = spec.find("news", "detail")
    assert op is not None
    assert op.method == "GET"
    assert op.path == "/sapi/news/{news_id}"
    assert any(p.name == "news_id" and p.location == "path" and p.required for p in op.params)


def test_body_params_parsed():
    spec = load_spec()
    op = spec.find("recommend", "analyze")
    assert op is not None
    names = {p.name for p in op.body_params()}
    assert {"analysis_date", "force_refresh", "model_name"} <= names


# ---- coercion ----------------------------------------------------------------
def test_coerce_types():
    assert coerce("42", "integer") == 42
    assert coerce("3.14", "number") == 3.14
    assert coerce("true", "boolean") is True
    assert coerce("no", "boolean") is False
    assert coerce('["a","b"]', "array") == ["a", "b"]
    assert coerce("hello", "string") == "hello"
    assert coerce(None, "integer") is None


def test_coerce_invalid_raises():
    with pytest.raises(UsageError):
        coerce("notint", "integer")


# ---- op parser ---------------------------------------------------------------
def test_op_parser_requires_path_param():
    spec = load_spec()
    op = spec.find("news", "detail")
    parser = build_op_parser(op)
    with pytest.raises(SystemExit):
        parser.parse_args([])  # missing required --news-id
    ns = parser.parse_args(["--news-id", "5"])
    assert ns.news_id == "5"


def test_render_path_substitutes_and_quotes():
    spec = load_spec()
    op = spec.find("news", "detail")
    assert op.render_path({"news_id": 7}) == "/sapi/news/7"
    factor_op = spec.find("news", "by-factor")
    rendered = factor_op.render_path({"factor_code": "A/B"})
    assert "%2F" in rendered  # slash is percent-encoded


# ---- description -------------------------------------------------------------
def test_build_description_shape():
    spec = load_spec()
    cfg = Config(base_url="http://example:8000")
    doc = build_description(spec, cfg)
    assert doc["name"] == "sentiment"
    assert doc["operation_total"] == 33
    assert doc["backend"]["base_url"] == "http://example:8000"
    assert set(doc["exit_codes"].keys()) == {"0", "1", "2", "3", "4"}
    assert isinstance(doc["groups"], list) and doc["groups"]


# ---- client url building -----------------------------------------------------
def test_client_build_url_encodes_query():
    cfg = Config(base_url="http://h:8000")
    client = Client(cfg)
    url = client.build_url("/sapi/news", {"view": "best", "date": "2026-07-16", "skip": None})
    assert url.startswith("http://h:8000/sapi/news?")
    assert "view=best" in url and "date=2026-07-16" in url
    assert "skip" not in url  # None dropped


def test_client_bool_query_serialised():
    cfg = Config(base_url="http://h:8000")
    client = Client(cfg)
    url = client.build_url("/sapi/x", {"flag": True})
    assert "flag=true" in url


# ---- config precedence -------------------------------------------------------
def test_config_env_overrides_default(monkeypatch):
    monkeypatch.setenv("SENTIMENT_BASE_URL", "http://from-env:9000")
    cfg = Config()
    assert cfg.base_url == "http://from-env:9000"


def test_config_flag_overrides_env(monkeypatch):
    monkeypatch.setenv("SENTIMENT_BASE_URL", "http://from-env:9000")
    cfg = Config(base_url="http://from-flag:1000")
    assert cfg.base_url == "http://from-flag:1000"

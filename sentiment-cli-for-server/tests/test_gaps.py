"""Tests for the not-implemented (known-gaps) surfacing — pure, no network."""
from sentiment_cli.spec import KNOWN_GAPS, Spec
from sentiment_cli.cli import build_description
from sentiment_cli.config import Config


REQUIRED_KEYS = ("id", "title", "category", "status", "priority",
                  "reason", "impact", "workaround")


def test_known_gaps_nonempty_and_well_formed():
    assert len(KNOWN_GAPS) >= 8
    ids = [g["id"] for g in KNOWN_GAPS]
    # no duplicate ids
    assert len(ids) == len(set(ids))
    for g in KNOWN_GAPS:
        for k in REQUIRED_KEYS:
            assert g.get(k), f"gap {g.get('id')!r} missing/empty key {k!r}"
        assert g["status"] in ("not_implemented", "out_of_scope")


def test_known_gaps_cover_audited_items():
    ids = {g["id"] for g in KNOWN_GAPS}
    assert "auth-token-injection" in ids
    assert "push-feishu" in ids
    assert "push-weixin" in ids
    assert "push-pdf" in ids
    assert "scheduler" in ids
    assert "batch-analyzer" in ids
    assert "batch-snapshot" in ids
    assert "batch-bond-download" in ids
    assert "deploy-ops" in ids
    assert "dashboard-local-unavailable" in ids
    assert "pipeline-run-embedding-model" in ids
    # change-trigger-embedding-model was removed: change trigger is LLM-gateway
    # dependent (not model-dependent) and verified reachable in an egress-capable env.
    assert "change-trigger-embedding-model" not in ids


def test_describe_includes_not_implemented():
    spec = Spec({"info": {"title": "t", "version": "0"}, "paths": {}})
    doc = build_description(spec, Config(), None)
    assert "not_implemented" in doc
    assert len(doc["not_implemented"]) == len(KNOWN_GAPS)
    assert doc["not_implemented"][0]["id"] == KNOWN_GAPS[0]["id"]
    # every emitted gap carries the same shape
    for row in doc["not_implemented"]:
        for k in ("id", "title", "category", "status", "reason",
                  "impact", "workaround"):
            assert row.get(k), f"describe gap missing {k}"

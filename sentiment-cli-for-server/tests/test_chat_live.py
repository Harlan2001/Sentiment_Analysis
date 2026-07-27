"""Live chat integration test — proves `chat ask` reaches the KingStar
gateway directly (bypassing the broken /sapi/chat) and returns real
content.

Gated by SENTIMENT_CHAT_LIVE=1. The default `pytest` run
SKIPS this (keeps the suite off-line + secret-free); run it
explicitly to prove the gateway path works end-to-end:

    SENTIMENT_CHAT_LIVE=1 pytest tests/test_chat_live.py -v

The gateway URL/KEY come from sentiment-cli/.env (loaded by
load_dotenv) or exported env vars.
"""
import contextlib
import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sentiment_cli.config import load_dotenv, Config
from sentiment_cli.client import Client
from sentiment_cli.cli import run_operation, Skin
from sentiment_cli.spec import load_spec


@pytest.fixture(scope="module")
def ctx():
    if not os.environ.get("SENTIMENT_CHAT_LIVE"):
        pytest.skip("需 SENTIMENT_CHAT_LIVE=1（且 .env 已配置网关）")
    load_dotenv()
    cfg = Config()
    if not (cfg.chat_gateway_url and cfg.chat_gateway_key):
        pytest.skip("未配置 SENTIMENT_CHAT_GATEWAY_URL/KEY")
    spec = load_spec(cfg.spec_path)
    return cfg, Client(cfg), spec, Skin()


def test_chat_gateway_live(ctx):
    _cfg, client, spec, skin = ctx
    op = spec.find("chat", "ask")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = run_operation(
            op,
            ["--messages",
             '[{"role":"user","content":"用一句话介绍债券收益率曲线"}]',
             "--stream", "false", "--json"],
            client, skin, force_json=True,
        )
    assert rc == 0, buf.getvalue()
    env = json.loads(buf.getvalue())
    assert env["ok"] is True
    assert env["status"] == 200
    assert env["data"]["content"].strip(), "网关未返回内容"
    assert env["data"]["usage"]["total_tokens"] > 0

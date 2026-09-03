"""feishu_daily_push 单测：build_summary 文本格式 + 模块导入环境安全性。

仓库层用假对象注入，不连真实数据库、不推送飞书。
"""

import pytest

import backend.push.feishu_daily_push as push


class _FakeRepo:
    def __init__(self, prediction):
        self._prediction = prediction

    def get_prediction(self, trade_date):
        return self._prediction


# ---- build_summary ----

def test_build_summary_renders_summary_text(monkeypatch):
    text = push.build_summary(
        "2026-09-01", _FakeRepo({"报告摘要": "长端利率下行"})
    )
    assert "2026-09-01 债券市场预测报告" in text
    assert "长端利率下行" in text
    assert "完整分析请查看下方 PDF" in text


def test_build_summary_missing_prediction_uses_fallback(monkeypatch):
    text = push.build_summary("2026-09-01", _FakeRepo(None))
    assert "2026-09-01 债券市场预测报告" in text
    assert "完整分析请查看下方 PDF" in text


def test_build_summary_empty_summary_uses_placeholder(monkeypatch):
    text = push.build_summary("2026-09-01", _FakeRepo({}))
    assert "—" in text


def test_build_summary_decodes_nested_json_string_summary(monkeypatch):
    text = push.build_summary("2026-09-01", _FakeRepo({"报告摘要": '["要点1", "要点2"]'}))
    assert "要点1" in text
    assert "要点2" in text


# ---- 环境守卫 ----

def test_require_env_raises_without_feishu_credentials(monkeypatch):
    # 本模块其余测试不设置 FEISHU_*，APP_* 在 import 时即为空
    monkeypatch.setattr(push, "APP_ID", None)
    with pytest.raises(RuntimeError, match="FEISHU_APP_ID"):
        push._require_env()


def test_require_env_passes_with_credentials(monkeypatch):
    monkeypatch.setattr(push, "APP_ID", "cli_x")
    monkeypatch.setattr(push, "APP_SECRET", "secret")
    monkeypatch.setattr(push, "GROUP_ID", "oc_g")
    push._require_env()  # 不应抛出

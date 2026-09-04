"""analysis/result_processor 单测：因子解析、新因子发现与关联落库的分派逻辑。

不碰真实 DB / 因子池：monkeypatch 掉 DBOperations 与 discovery_manager。
AnalysisResultProcessor 的 conn 参数本就是面向可测设计的（测试传入 mock 连接）。
"""

from unittest.mock import MagicMock

import pytest

from backend.analysis.result_processor import AnalysisResultProcessor


def _make_resp():
    """返回 (proc, db, mgr) —— 注入 fake DB 与 discovery manager 的处理器。"""
    db = MagicMock()
    db.get_factor_id_by_code.return_value = 5  # 默认: 因子已存在
    db.save_news_factor_relation.return_value = True

    mgr = MagicMock()
    mgr.process_new_factor.return_value = {"action": "created", "factor_id": 99}

    return db, mgr


@pytest.fixture
def processor(monkeypatch):
    db, mgr = _make_resp()
    monkeypatch.setattr("backend.analysis.result_processor.DBOperations", MagicMock(return_value=db))
    monkeypatch.setattr(
        "backend.analysis.result_processor.get_factor_discovery_manager",
        MagicMock(return_value=mgr),
    )
    proc = AnalysisResultProcessor(model_name="test-model")
    return proc, db, mgr


class TestValidateAnalysisResult:
    def test_valid_result_passes(self, processor):
        proc, _, _ = processor
        ok = proc.validate_analysis_result(
            {"direction": "positive", "horizon": "短期", "reason": "x", "factors": []}
        )
        assert ok is True

    @pytest.mark.parametrize("missing", ["direction", "horizon", "reason", "factors"])
    def test_missing_required_field_rejected(self, processor, missing):
        proc, _, _ = processor
        result = {
            "direction": "positive",
            "horizon": "短期",
            "reason": "x",
            "factors": [],
        }
        del result[missing]
        assert proc.validate_analysis_result(result) is False

    def test_empty_result_rejected(self, processor):
        proc, _, _ = processor
        assert proc.validate_analysis_result({}) is False


class TestProcessSingleFactor:
    def test_skips_factor_without_code(self, processor):
        proc, db, mgr = processor
        result = proc._process_single_factor(
            news_id=1, factor_data={"name": "无名"}, conn=object()
        )
        assert result is None
        db.save_news_factor_relation.assert_not_called()
        mgr.process_new_factor.assert_not_called()

    def test_existing_factor_only_saves_relation(self, processor):
        proc, db, mgr = processor
        db.get_factor_id_by_code.return_value = 5
        conn = object()
        factor_data = {"code": "RATE", "name": "利率", "is_new_discovery": False}
        factor_id = proc._process_single_factor(
            news_id=1, factor_data=factor_data, conn=conn
        )
        assert factor_id == 5
        mgr.process_new_factor.assert_not_called()
        db.save_news_factor_relation.assert_called_once_with(
            news_id=1, factor_id=5, factor_data=factor_data,
            model="test-model", conn=conn,
        )

    def test_new_discovery_runs_manager_and_reuses_id(self, processor):
        proc, db, mgr = processor
        # 第一次查不到, manager 处理后查到新 id
        db.get_factor_id_by_code.side_effect = [None, 99]
        factor_id = proc._process_single_factor(
            news_id=1,
            factor_data={"code": "NEW_FACTOR_X", "name": "新因子", "is_new_discovery": True},
            conn=object(),
        )
        assert factor_id == 99
        mgr.process_new_factor.assert_called_once()

    def test_new_discovery_still_missing_id_returns_none(self, processor):
        proc, db, mgr = processor
        db.get_factor_id_by_code.return_value = None  # manager 处理后仍无
        factor_id = proc._process_single_factor(
            news_id=1,
            factor_data={"code": "GHOST", "name": "幽灵", "is_new_discovery": True},
            conn=object(),
        )
        assert factor_id is None
        mgr.process_new_factor.assert_called_once()
        db.save_news_factor_relation.assert_not_called()

    def test_name_fallback_from_code_when_missing(self, processor):
        proc, db, mgr = processor
        db.get_factor_id_by_code.side_effect = [None, 7]
        data = {"code": "LIQUIDITY_RISK", "is_new_discovery": True}
        proc._process_single_factor(news_id=1, factor_data=data, conn=object())
        assert data["name"] == "Liquidity Risk"

    def test_save_failure_propagates(self, processor):
        proc, db, mgr = processor
        db.save_news_factor_relation.side_effect = RuntimeError("db down")
        with pytest.raises(RuntimeError, match="db down"):
            proc._process_single_factor(
                news_id=1,
                factor_data={"code": "RATE", "name": "利率"},
                conn=object(),
            )


class TestProcessFactorList:
    def test_single_failure_continues(self, processor):
        proc, db, mgr = processor
        # 第一个因子 save 抛异常(内部 except 吞掉), 第二个正常
        db.save_news_factor_relation.side_effect = [RuntimeError("bad"), True]
        ids = proc._process_factor_list(
            news_id=1,
            factors=[{"code": "A", "name": "甲"}, {"code": "B", "name": "乙"}],
            conn=object(),
        )
        assert ids == [5]  # 只有第二个成功


class TestProcessAnalysisResult:
    def test_empty_factors_returns_true(self, processor):
        proc, db, mgr = processor
        assert proc.process_analysis_result(news_id=1, analysis_result={"factors": []}, conn=object()) is True
        assert not db.save_news_factor_relation.called

    def test_exception_propagates(self, processor):
        # _process_factor_list 会吞掉单因子内的异常(continue)，真正的传播路径是
        # analysis_result 本身结构损坏导致 .get 直接抛错（process_analysis_result 的 except: raise）。
        proc, db, mgr = processor
        with pytest.raises(AttributeError):
            proc.process_analysis_result(news_id=1, analysis_result=None, conn=object())
"""common/llm_json：LLM 输出 JSON 提取与清洗逻辑单测（纯函数，不触网络/DB）。"""

import json

import pytest

from backend.common.llm_json import extract_json, extract_json_string, sanitize_json


class TestSanitizeJson:
    def test_removes_trailing_comma_before_brace(self):
        assert sanitize_json('{"a": 1,}') == '{"a": 1}'

    def test_removes_trailing_comma_before_bracket(self):
        assert sanitize_json('{"a": [1, 2,]}') == '{"a": [1, 2]}'

    def test_removes_nested_trailing_commas(self):
        assert sanitize_json('{"a": {"b": 1,}, "c": 2,}') == '{"a": {"b": 1}, "c": 2}'

    def test_empty_input(self):
        assert sanitize_json("") == ""

    def test_no_changes_when_clean(self):
        assert sanitize_json('{"a": 1}') == '{"a": 1}'


class TestExtractJsonString:
    def test_extracts_from_plain_text(self):
        content = '好的，这是分析结果：{"direction": "positive"} 仅供参考。'
        assert extract_json_string(content) == '{"direction": "positive"}'

    def test_extracts_from_fenced_code_block(self):
        content = '```json\n{"direction": "negative", "horizon": "短期"}\n```'
        out = extract_json_string(content)
        assert json.loads(out)["direction"] == "negative"

    def test_extracts_nested_object(self):
        content = '{"a": {"b": [1, 2, 3]}}'
        assert json.loads(extract_json_string(content))["a"]["b"] == [1, 2, 3]

    def test_strips_trailing_comma_from_llm_output(self):
        # LLM 常见: 数组最后一个元素后带逗号
        content = '{"factors": [{"code": "RATE",},],}'
        out = extract_json_string(content)
        assert json.loads(out)["factors"] == [{"code": "RATE"}]

    def test_no_json_returns_empty(self):
        assert extract_json_string("没有任何 JSON 结构") == ""

    def test_empty_content_returns_empty(self):
        assert extract_json_string("") == ""

    def test_regex_greedy_largest_object(self):
        # 贪心 {.*} 取最外层最大对象
        content = "前缀 {'inner': 1} 后缀"
        out = extract_json_string(content)
        assert out.startswith("{") and out.endswith("}")


class TestExtractJson:
    def test_returns_dict(self):
        assert extract_json('{"direction": "neutral"}') == {"direction": "neutral"}

    def test_raises_when_no_json_found(self):
        with pytest.raises(json.JSONDecodeError):
            extract_json("完全没有 JSON")

    def test_raises_when_unparseable(self):
        with pytest.raises(json.JSONDecodeError) as excinfo:
            extract_json('{"a": ::invalid::}')
        assert "解析 JSON 失败" in str(excinfo.value)
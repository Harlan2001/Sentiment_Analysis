"""agent/spec：OpenAPI 解析 + 工具定义/执行器生成单测（纯逻辑，不触网络）。

覆盖: 参数模型/路径渲染/类型推导/ref 解析/名称推导/Spec 解析(含 override、tag alias、
重复名去重、body $ref 参数)/agent 操作过滤/工具定义生成/执行器错误分支。
"""


from backend.agent.client import BackendError, NetworkError
from backend.agent.spec import (
    Operation,
    Param,
    Spec,
    _resolve_ref,
    _schema_enum,
    _schema_type,
    derive_name,
    filter_agent_operations,
    generate_tool_definitions,
    generate_tool_executors,
    load_spec,
    urllib_quote,
)

MINI_RAW = {
    "info": {"title": "test-api", "version": "9.9"},
    "paths": {
        "/health": {"get": {"tags": ["ops"]}},  # 必须被跳过
        "/sapi/market": {"get": {"tags": ["market"], "summary": "行情总览"}},
        "/sapi/news/{news_id}": {
            "get": {
                "tags": ["news"],
                "parameters": [
                    {
                        "name": "news_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
            }
        },
        "/sapi/news/{news_id}/yield": {"get": {"tags": ["news"]}},
        "/sapi/chat": {
            "post": {
                "tags": ["chat"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ChatRequest"}
                        }
                    }
                },
            }
        },
        "/sapi/report/files/{filename}": {"get": {"tags": ["report"]}},
        "/sapi/dashboard/stats": {"get": {"tags": ["dashboard"]}},
        "/sapi/graph-augment/{news_id}": {"get": {"tags": ["graph-augment"]}},
        "/sapi/dup/x": {
            "get": {"tags": ["dup"], "summary": "x"},
            "post": {"tags": ["dup"], "summary": "x2"},
        },
    },
    "components": {
        "schemas": {
            "ChatRequest": {
                "type": "object",
                "required": ["message"],
                "properties": {
                    "message": {"type": "string", "description": "消息文本"},
                    "room": {"type": "string"},
                },
            }
        }
    },
}


def _op_by_path(spec: Spec, path: str, method: str = "GET") -> Operation:
    for op in spec.operations:
        if op.path == path and op.method == method:
            return op
    raise AssertionError(f"{method} {path} 不在 operations 中")


class TestUrllibQuote:
    def test_quotes_reserved_chars(self):
        assert urllib_quote("a/b c?") == "a%2Fb%20c%3F"

    def test_quotes_unicode(self):
        assert urllib_quote("利率") == "%E5%88%A9%E7%8E%87"


class TestOperation:
    def test_key(self):
        op = Operation(group="g", name="n", method="GET", path="/p", summary="", description="")
        assert op.key == "g n"

    def test_path_params_only_filters_location(self):
        op = Operation(
            group="g", name="n", method="GET", path="/p/{id}", summary="", description="",
            params=[
                Param("id", "path", True, "integer"),
                Param("q", "query", False, "string"),
            ],
        )
        assert [p.name for p in op.path_params()] == ["id"]

    def test_render_path_quotes_and_replaces(self):
        op = Operation(
            group="g", name="n", method="GET", path="/news/{id}/y", summary="", description="",
            params=[Param("id", "path", True, "integer")],
        )
        assert op.render_path({"id": "a/b"}) == "/news/a%2Fb/y"


class TestSchemaTypeEnumResolve:
    def test_schema_type_plain(self):
        assert _schema_type({"type": "integer"}) == "integer"

    def test_schema_type_infers_enum_as_string(self):
        assert _schema_type({"enum": [1, 2]}) == "string"

    def test_schema_type_any_of_skips_null(self):
        schema = {"anyOf": [{"type": "null"}, {"type": "string"}]}
        assert _schema_type(schema) == "string"

    def test_schema_type_all_of_first(self):
        assert _schema_type({"allOf": [{"type": "number"}]}) == "number"

    def test_schema_type_fallback_any(self):
        assert _schema_type({}) == "any"
        assert _schema_type(None) == "any"
        assert _schema_type("not-dict") == "any"

    def test_schema_enum_direct(self):
        assert _schema_enum({"enum": ["a", "b"]}) == ["a", "b"]

    def test_schema_enum_in_any_of(self):
        schema = {"anyOf": [{"type": "null"}, {"enum": ["x", "y"]}]}
        assert _schema_enum(schema) == ["x", "y"]

    def test_schema_enum_none(self):
        assert _schema_enum({"type": "string"}) is None

    def test_resolve_ref_nested(self):
        spec = {"components": {"schemas": {"A": {"properties": {}}}}}
        assert _resolve_ref(spec, "#/components/schemas/A") == {
            "properties": {}
        }

    def test_resolve_ref_missing_returns_empty(self):
        assert _resolve_ref({"a": {}}, "#/a/b/c") == {}
        assert _resolve_ref(42, "#/x") == {}


class TestDeriveName:
    def test_strips_sapi_and_tag_prefix(self):
        assert derive_name("news", "/sapi/news/list") == "list"

    def test_path_param_becomes_by(self):
        assert derive_name("news", "/sapi/news/{news_id}") == "by-news-id"

    def test_underscore_to_dash(self):
        assert derive_name("macro", "/sapi/macro_data") == "macro-data"

    def test_only_tag_returns_tag(self):
        assert derive_name("market", "/sapi/market") == "market"


class TestSpecParsing:
    def test_build_excludes_health(self):
        spec = Spec(MINI_RAW)
        assert all(op.path != "/health" for op in spec.operations)

    def test_sorted_operations(self):
        spec = Spec(MINI_RAW)
        paths = [op.path for op in spec.operations]
        assert paths == sorted(paths)

    def test_name_override_applies(self):
        spec = Spec(MINI_RAW)
        assert _op_by_path(spec, "/sapi/news/{news_id}").name == "detail"
        assert _op_by_path(spec, "/sapi/news/{news_id}/yield").name == "yield"
        assert _op_by_path(spec, "/sapi/chat", "POST").name == "ask"

    def test_path_param_parsed(self):
        spec = Spec(MINI_RAW)
        op = _op_by_path(spec, "/sapi/news/{news_id}")
        assert op.params[0].name == "news_id"
        assert op.params[0].location == "path"
        assert op.params[0].required is True
        assert op.params[0].type == "integer"

    def test_body_params_from_ref(self):
        spec = Spec(MINI_RAW)
        op = _op_by_path(spec, "/sapi/chat", "POST")
        names = {p.name: p for p in op.params if p.location == "body"}
        assert names["message"].required is True
        assert names["room"].required is False
        assert names["message"].type == "string"

    def test_tag_alias_applies(self):
        spec = Spec(MINI_RAW)
        op = _op_by_path(spec, "/sapi/graph-augment/{news_id}")
        assert op.group == "graph"
        assert op.name == "by-news-id"

    def test_duplicate_name_gets_method_suffix(self):
        spec = Spec(MINI_RAW)
        assert _op_by_path(spec, "/sapi/dup/x", "GET").name == "x"
        assert _op_by_path(spec, "/sapi/dup/x", "POST").name == "x-post"

    def test_groups_index(self):
        spec = Spec(MINI_RAW)
        assert set(spec.groups) == {
            "chat", "dashboard", "dup", "graph", "market", "news", "report",
        }


class TestLoadSpec:
    def test_loads_bundled_spec(self):
        spec = load_spec()
        assert isinstance(spec, Spec)
        assert spec.operations
        assert all(op.path.startswith("/") for op in spec.operations)


class TestFilterAgentOperations:
    def test_only_get_and_non_excluded(self):
        spec = Spec(MINI_RAW)
        ops = filter_agent_operations(spec)
        paths = {op.path for op in ops}
        assert "/sapi/news/{news_id}" in paths  # GET news 保留
        assert "/sapi/market" in paths
        # POST 排除
        assert "/sapi/chat" not in paths
        # 排除组: report / dashboard
        assert not any(op.group in {"report", "dashboard"} for op in ops)
        assert all(op.method == "GET" for op in ops)


class TestGenerateToolDefinitions:
    def test_function_shape(self):
        spec = Spec(MINI_RAW)
        op = _op_by_path(spec, "/sapi/news/{news_id}")
        tools = generate_tool_definitions([op])
        assert len(tools) == 1
        fn = tools[0]["function"]
        assert fn["name"] == "news_detail"
        assert fn["description"]
        assert fn["parameters"]["required"] == ["news_id"]
        assert fn["parameters"]["properties"]["news_id"]["type"] == "integer"

    def test_enum_forwarded(self):
        op = Operation(
            group="g", name="n", method="GET", path="/p", summary="", description="",
            params=[Param("cat", "query", False, "string", enum=["a", "b"])],
        )
        fn = generate_tool_definitions([op])[0]["function"]
        assert fn["parameters"]["properties"]["cat"]["enum"] == ["a", "b"]


class _FakeClient:
    """记录调用并可由测试脚本抛出异常。"""

    def __init__(self, response=(200, {"ok": True}), error=None):
        self.calls = []
        self.response = response
        self.error = error

    def request(self, method, path, query=None):
        self.calls.append((method, path, query or {}))
        if self.error:
            raise self.error
        return self.response


class TestGenerateToolExecutors:
    def _executor(self, monkeypatch, op, fake_client):
        return generate_tool_executors([op], fake_client)[f"{op.group}_{op.name}".replace("-", "_")]

    def test_invokes_client_with_path_and_query(self):
        op = Operation(
            group="news", name="detail", method="GET", path="/news/{id}", summary="",
            description="",
            params=[
                Param("id", "path", True, "integer"),
                Param("limit", "query", False, "integer"),
            ],
        )
        client = _FakeClient(response=(200, {"id": 1}))
        executor = generate_tool_executors([op], client)["news_detail"]
        assert executor(id="a b", limit=5) == {"id": 1}
        method, path, query = client.calls[0]
        assert path == "/news/a%20b"
        assert query == {"limit": 5}

    def test_wraps_backend_error(self):
        op = Operation(group="g", name="n", method="GET", path="/p", summary="", description="")
        err = BackendError(404, "not found", "http://x")
        client = _FakeClient(error=err)
        executor = generate_tool_executors([op], client)["g_n"]
        out = executor()
        assert "后端返回 HTTP 404" in out["error"]

    def test_wraps_network_error(self):
        op = Operation(group="g", name="n", method="GET", path="/p", summary="", description="")
        client = _FakeClient(error=NetworkError())
        executor = generate_tool_executors([op], client)["g_n"]
        out = executor()
        assert "无法连接后端" in out["error"]

    def test_wraps_unexpected_error(self):
        op = Operation(group="g", name="n", method="GET", path="/p", summary="", description="")
        client = _FakeClient(error=RuntimeError("boom"))
        executor = generate_tool_executors([op], client)["g_n"]
        out = executor()
        assert "工具执行异常" in out["error"]
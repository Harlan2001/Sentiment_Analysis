"""OpenAPI 解析器 — 从 openapi.json 构建命令模型，并为 agent 生成工具定义与执行器。

从 sentiment-cli-for-server/sentiment_cli/spec.py 提取核心逻辑，
去掉 CLI 相关部分（KNOWN_GAPS / HIDDEN_GROUPS / save_bundled 等），
新增 filter_agent_operations / generate_tool_definitions / generate_tool_executors。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── 数据模型 ──────────────────────────────────────────────────────────────────

@dataclass
class Param:
    """OpenAPI 参数。"""
    name: str
    location: str          # "path" | "query" | "body"
    required: bool
    type: str              # "string" | "integer" | "number" | "boolean" | "array" | "object" | "any"
    description: str = ""
    enum: Optional[List[Any]] = None

    def cli_flag(self) -> str:
        return "--" + self.name.replace("_", "-")


@dataclass
class Operation:
    """一个后端 API 操作。"""
    group: str
    name: str
    method: str
    path: str
    summary: str
    description: str
    params: List[Param] = field(default_factory=list)
    streaming: bool = False

    @property
    def key(self) -> str:
        return f"{self.group} {self.name}"

    @property
    def op_id(self) -> str:
        return f"{self.method} {self.path}"

    def path_params(self) -> List[Param]:
        return [p for p in self.params if p.location == "path"]

    def query_params(self) -> List[Param]:
        return [p for p in self.params if p.location == "query"]

    def body_params(self) -> List[Param]:
        return [p for p in self.params if p.location == "body"]

    def render_path(self, values: Dict[str, Any]) -> str:
        out = self.path
        for p in self.path_params():
            out = out.replace("{" + p.name + "}", urllib_quote(str(values[p.name])))
        return out


# ── 路径与名称映射 ────────────────────────────────────────────────────────────

BUNDLED_SPEC = Path(__file__).resolve().parent / "data" / "openapi.json"

# 友好命令名（"METHOD path" → 短名）
NAME_OVERRIDES: Dict[str, str] = {
    "GET /sapi/news": "list",
    "GET /sapi/news/{news_id}": "detail",
    "GET /sapi/news/{news_id}/yield": "yield",
    "POST /sapi/news/{news_id}/analyze": "analyze",
    "GET /sapi/factor/{factor_code}/news": "by-factor",
    "GET /sapi/factors": "list",
    "GET /sapi/factors/by-category/{category}": "by-category",
    "GET /sapi/forecast": "latest",
    "GET /sapi/forecast/history": "history",
    "GET /sapi/macro/signal": "signal",
    "GET /sapi/macro/signal/logs": "signal-logs",
    "GET /sapi/strategy/snapshot": "snapshot",
    "POST /sapi/strategy/trigger": "trigger",
    "GET /sapi/strategy/sse": "sse",
    "POST /sapi/strategy/portfolio-analysis": "portfolio",
    "POST /sapi/ai-strategy-recommendation/analyze": "analyze",
    "GET /sapi/ai-strategy-recommendation/latest": "latest",
    "GET /sapi/ai-strategy-recommendation/history": "history",
    "GET /sapi/ai-strategy-recommendation/strategies": "strategies",
    "POST /sapi/change/trigger": "trigger",
    "GET /sapi/change/snapshots": "snapshots",
    "POST /sapi/change/compare": "compare",
    "POST /sapi/internal/pipeline/trigger": "run",
    "POST /sapi/report/generate-prediction": "generate",
    "GET /sapi/report/files/{filename}": "download",
    "GET /sapi/graph-augment/job-by-news/{news_id}": "job-by-news",
    "POST /sapi/graph-augment/save": "save",
    "POST /sapi/chat": "ask",
}

# 友好分组名（tag → 命令组）
GROUP_ALIASES: Dict[str, str] = {
    "ai-strategy": "recommend",
    "graph-augment": "graph",
}

# SSE / chunked 流式操作
STREAMING_OPS = {"GET /sapi/strategy/sse"}


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def urllib_quote(value: str) -> str:
    import urllib.parse
    return urllib.parse.quote(value, safe="")


def _schema_type(schema: Dict[str, Any]) -> str:
    if not isinstance(schema, dict):
        return "any"
    if "type" in schema:
        return schema["type"]
    if "enum" in schema:
        return "string"
    if "anyOf" in schema:
        for sub in schema["anyOf"]:
            if isinstance(sub, dict) and sub.get("type") != "null":
                return _schema_type(sub)
    if "allOf" in schema and schema["allOf"]:
        return _schema_type(schema["allOf"][0])
    return "any"


def _schema_enum(schema: Dict[str, Any]) -> Optional[List[Any]]:
    if not isinstance(schema, dict):
        return None
    if "enum" in schema:
        return schema["enum"]
    for key in ("anyOf", "allOf"):
        for sub in schema.get(key, []):
            if isinstance(sub, dict) and "enum" in sub:
                return sub["enum"]
    return None


def _resolve_ref(spec: Dict[str, Any], ref: str) -> Dict[str, Any]:
    node: Any = spec
    for part in ref.lstrip("#/").split("/"):
        if isinstance(node, dict):
            node = node.get(part, {})
        else:
            return {}
    return node if isinstance(node, dict) else {}


def derive_name(tag: str, path: str) -> str:
    """从路径推导操作名（当 NAME_OVERRIDES 中没有时使用）。"""
    segs = [s for s in path.strip("/").split("/") if s and s != "sapi"]
    conv: List[str] = []
    for s in segs:
        if s.startswith("{") and s.endswith("}"):
            conv.append("by-" + s[1:-1].replace("_", "-"))
        else:
            conv.append(s.replace("_", "-"))
    norm_tag = tag.replace("_", "-")
    if conv and conv[0] == norm_tag:
        conv = conv[1:]
    return "-".join(conv) if conv else norm_tag


# ── Spec ──────────────────────────────────────────────────────────────────────

class Spec:
    """从 OpenAPI 文档构建的操作模型。"""

    def __init__(self, raw: Dict[str, Any]):
        self.raw = raw
        self.title = raw.get("info", {}).get("title", "backend")
        self.version = raw.get("info", {}).get("version", "?")
        self.operations: List[Operation] = []
        self.groups: Dict[str, List[Operation]] = {}
        self._build()

    def _build(self) -> None:
        seen: Dict[str, set] = {}
        for path, methods in sorted(self.raw.get("paths", {}).items()):
            if path in ("/health", "/openapi.json"):
                continue
            for method, op in methods.items():
                if method.lower() not in ("get", "post", "put", "patch", "delete"):
                    continue
                tag = (op.get("tags") or ["general"])[0]
                group = GROUP_ALIASES.get(tag, tag).replace("_", "-")
                op_id = f"{method.upper()} {path}"
                name = NAME_OVERRIDES.get(op_id) or derive_name(tag, path)
                bucket = seen.setdefault(group, set())
                if name in bucket:
                    name = f"{name}-{method.lower()}"
                bucket.add(name)

                params = self._params(op)
                operation = Operation(
                    group=group,
                    name=name,
                    method=method.upper(),
                    path=path,
                    summary=op.get("summary", ""),
                    description=(op.get("description") or "").strip(),
                    params=params,
                    streaming=op_id in STREAMING_OPS,
                )
                self.operations.append(operation)
                self.groups.setdefault(group, []).append(operation)

    def _params(self, op: Dict[str, Any]) -> List[Param]:
        out: List[Param] = []
        for p in op.get("parameters", []):
            schema = p.get("schema", {})
            out.append(Param(
                name=p["name"],
                location=p["in"],
                required=bool(p.get("required")),
                type=_schema_type(schema),
                description=p.get("description", ""),
                enum=_schema_enum(schema),
            ))
        rb = op.get("requestBody")
        if rb:
            js = rb.get("content", {}).get("application/json", {}).get("schema", {})
            if isinstance(js, dict) and "$ref" in js:
                js = _resolve_ref(self.raw, js["$ref"])
            props = js.get("properties", {}) if isinstance(js, dict) else {}
            required_names = set(js.get("required", [])) if isinstance(js, dict) else set()
            for pname, pschema in props.items():
                out.append(Param(
                    name=pname,
                    location="body",
                    required=pname in required_names,
                    type=_schema_type(pschema),
                    description=pschema.get("description", "") if isinstance(pschema, dict) else "",
                    enum=_schema_enum(pschema),
                ))
        return out

    def find(self, group: str, name: str) -> Optional[Operation]:
        for op in self.groups.get(group, []):
            if op.name == name:
                return op
        return None


def load_spec(path: Optional[str] = None) -> Spec:
    """从指定路径或 bundled 副本加载 OpenAPI spec。"""
    target = Path(path) if path else BUNDLED_SPEC
    with open(target, "r", encoding="utf-8") as fh:
        return Spec(json.load(fh))


# ── Agent 工具生成 ────────────────────────────────────────────────────────────

_TYPE_MAP = {
    "string": "string", "integer": "integer", "number": "number",
    "boolean": "boolean", "array": "array", "object": "object",
}

_GROUP_DISPLAY: Dict[str, str] = {
    "news": "新闻",
    "factors": "因子",
    "forecast": "预测",
    "macro": "宏观信号",
    "strategy": "策略",
    "recommend": "AI推荐",
    "change": "变动监控",
    "graph": "知识图谱",
}

_GROUP_ICONS: Dict[str, str] = {
    "news": "📰", "factors": "📊", "forecast": "🔮",
    "macro": "⚡", "strategy": "🎯", "recommend": "💡",
    "change": "📈", "graph": "🕸️",
}


# Agent 不关心的 API 组（auth 是登录、dashboard 是行为分析、report 是 PDF 下载）
_AGENT_EXCLUDED_GROUPS = {"auth", "dashboard", "report", "pipeline"}


def filter_agent_operations(spec: Spec) -> List[Operation]:
    """过滤出 agent 适用的操作：仅 GET + 非流式 + 排除无关组。"""
    return [
        op for op in spec.operations
        if op.method == "GET"
        and not op.streaming
        and op.group not in _AGENT_EXCLUDED_GROUPS
    ]


def _make_tool_name(op: Operation) -> str:
    return f"{op.group}_{op.name}".replace("-", "_")


def generate_tool_definitions(ops: List[Operation]) -> List[dict]:
    """将 Operation 列表转换为 OpenAI function-calling 工具定义。"""
    tools: List[dict] = []
    for op in ops:
        properties: Dict[str, dict] = {}
        required: List[str] = []
        for p in op.params:
            prop: dict = {
                "type": _TYPE_MAP.get(p.type, "string"),
                "description": p.description or p.name,
            }
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        tools.append({
            "type": "function",
            "function": {
                "name": _make_tool_name(op),
                "description": op.summary or op.description or f"{op.group} {op.name}",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })
    return tools


def generate_tool_executors(ops: List[Operation], client) -> Dict[str, callable]:
    """为每个 Operation 创建闭包执行器，通过 HTTP client 调用后端 API。"""
    import logging
    _log = logging.getLogger(__name__)

    def _make_executor(op: Operation):
        def executor(**kwargs):
            from backend.agent.client import BackendError, NetworkError
            try:
                path_values: Dict[str, Any] = {}
                query: Dict[str, Any] = {}
                for p in op.params:
                    val = kwargs.get(p.name)
                    if val is None:
                        continue
                    if p.location == "path":
                        path_values[p.name] = val
                    elif p.location == "query":
                        query[p.name] = val
                path = op.render_path(path_values)
                _status, data = client.request(op.method, path, query=query)
                return data if isinstance(data, dict) else {"data": data}
            except BackendError as exc:
                return {"error": f"后端返回 HTTP {exc.status}: {exc.body}"}
            except NetworkError as exc:
                return {"error": f"无法连接后端: {exc}"}
            except Exception as exc:
                _log.exception("工具 %s 执行异常", _make_tool_name(op))
                return {"error": f"工具执行异常: {exc}"}
        return executor

    return {_make_tool_name(op): _make_executor(op) for op in ops}


def generate_display_metadata(ops: List[Operation]) -> tuple[Dict[str, str], Dict[str, str]]:
    """为所有 agent 工具生成中文名和图标映射。"""
    display_names: Dict[str, str] = {}
    icons: Dict[str, str] = {}
    for op in ops:
        name = _make_tool_name(op)
        display_names[name] = op.summary or f"{_GROUP_DISPLAY.get(op.group, op.group)}-{op.name}"
        icons[name] = _GROUP_ICONS.get(op.group, "🔧")
    return display_names, icons

"""Parse an OpenAPI document into an agent-friendly command model.

Each backend operation becomes an ``Operation`` grouped under a command group
(its OpenAPI tag). Command names are derived deterministically from the path,
with a small override table for the few awkward ones.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

BUNDLED_SPEC = Path(__file__).with_name("data") / "openapi.json"

# Nicer command names for a handful of operations (keyed by "METHOD path").
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

# Nicer group names (tag -> command group).
GROUP_ALIASES: Dict[str, str] = {
    "ai-strategy": "recommend",
    "graph-augment": "graph",
}

# Operations that stream (SSE / chunked) rather than return a single JSON body.
STREAMING_OPS = {"GET /sapi/strategy/sse"}

# ---------------------------------------------------------------------------
# Known gaps — capabilities the CLI does NOT wrap yet.
#
# Single source of truth for "what is not implemented". Surfaced by
# `sentiment describe --json` (key "not_implemented") and `sentiment gaps`.
# status: "not_implemented" (should be done) | "out_of_scope" (intentional)
# ---------------------------------------------------------------------------
KNOWN_GAPS: List[Dict[str, Any]] = [
    {
        "id": "push-feishu",
        "title": "飞书每日 PDF 推送 (feishu_daily_push)",
        "category": "push",
        "status": "not_implemented",
        "priority": "low",
        "reason": "backend/push/feishu_daily_push.py 是独立 main() 脚本 + scheduler 触发,没有 HTTP 端点。",
        "impact": "无法经 CLI 触发飞书每日推送。",
        "workaround": "服务器上直接 `python backend/push/feishu_daily_push.py`;或改后端暴露 /sapi/push/feishu。",
    },
    {
        "id": "push-weixin",
        "title": "微信公众号草稿推送 (weixin_push, Playwright)",
        "category": "push",
        "status": "not_implemented",
        "priority": "low",
        "reason": "backend/push/weixin_push.py 用 Playwright 自动化,独立 main(),无 HTTP 端点。",
        "impact": "无法经 CLI 触发公众号推送。",
        "workaround": "服务器上直接运行;或改后端暴露端点(需带浏览器环境)。",
    },
    {
        "id": "scheduler",
        "title": "定时调度器 (scheduler.py)",
        "category": "ops",
        "status": "not_implemented",
        "priority": "low",
        "reason": "backend/scheduler.py 仅存在于服务器,本地仓库没有;负责定时任务(如每日 10:00 推送)。无 API。",
        "impact": "无法经 CLI 查看/管理定时任务。",
        "workaround": "服务器侧管理;或改后端暴露 scheduler 状态/触发端点。",
    },
    {
        "id": "deploy-ops",
        "title": "部署/运维脚本 (deploy_backend.sh, deploy_frontend.sh, deploy-image.sh, start.ps1, Dockerfile)",
        "category": "ops",
        "status": "out_of_scope",
        "priority": "n/a",
        "reason": "属运维动作而非业务 HTTP 能力;cli-anything 聚焦查询/推理类业务。",
        "impact": "CLI 不封装部署/容器运维。",
        "workaround": "直接使用这些脚本 / docker-compose。",
    },
    {
        "id": "dashboard-local-unavailable",
        "title": "Dashboard 行为分析 / 会话清理 (dashboard/* 全部子命令)",
        "category": "dashboard-local",
        "status": "not_implemented",
        "priority": "medium",
        "hide_groups": ["dashboard"],
        "reason": "dashboard/* 共 13 个端点已按 spec 封装;新版后端(07-23 更新)已注册 dashboard router,"
                "本机可用性具备,但按本期需求不接入(保持隐藏,仅 gaps/describe 报告)。",
        "impact": "dashboard 组 13 个子命令不在 CLI 命令树;调用报 unknown command。",
        "workaround": "需要接入时移除本 gap 的 hide_groups 声明即可(命令树自动恢复)。",
    },
    {
        "id": "pipeline-run-embedding-model",
        "title": "Pipeline 完整跑通 (缺本地嵌入模型 all-MiniLM-L6-v2)",
        "category": "local-model",
        "status": "not_implemented",
        "priority": "medium",
        "hide_groups": ["pipeline"],
        "reason": "pipeline run 的 trigger 已被后端接受、KingStar 网关返回 200,但本机缺 "
                "models/all-MiniLM-L6-v2 句向量模型文件,跑到向量化步骤报错退出。属环境缺口,非 CLI 缺陷。",
        "impact": "pipeline run 在本机只能走到触发阶段,无法完成端到端向量化/入库。",
        "workaround": "把 all-MiniLM-L6-v2 模型放到后端 models/ 目录;"
                "或仅在远程后端(已挂 embedding)跑 pipeline run。",
    },
    {
        "id": "server-cli-prune",
        "title": "for-server 版功能裁剪（仅保留指定命令）",
        "category": "scope",
        "status": "out_of_scope",
        "priority": "n/a",
        "hide_groups": ["chat", "report", "auth"],
        "hide_ops": [
            "POST /sapi/strategy/trigger",
            "GET /sapi/strategy/sse",
            "POST /sapi/change/trigger",
            "POST /sapi/graph-augment/save",
        ],
        "reason": "本 for-server 版按需求仅保留 news全部/factors全部/forecast全部/"
                "macro全部/strategy(snapshot+portfolio)/recommend全部/"
                "change(snapshots+compare)/graph(job-by-news)。其余组(chat/report/auth)与"
                "单 op(strategy trigger/sse、change trigger、graph save)暂时不要。",
        "impact": "被隐藏命令不在 CLI 命令树；调用报 unknown command。",
        "workaround": "需要恢复某命令时，从本 gap 的 hide_groups/hide_ops 移除对应项即可。",
    },
]



# ---------------------------------------------------------------------------
# Command-tree suppression — derived from KNOWN_GAPS (single source of truth).
# A gap entry may declare "hide_groups" / "hide_ops" to remove commands from
# the live CLI surface. They still appear in `sentiment gaps` / `describe`.
# ---------------------------------------------------------------------------
HIDDEN_GROUPS: set = {g for gap in KNOWN_GAPS for g in gap.get("hide_groups", [])}
HIDDEN_OP_IDS: set = {op for gap in KNOWN_GAPS for op in gap.get("hide_ops", [])}


@dataclass
class Param:
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
        # FastAPI models Optional[X] as anyOf[X, null]; pick the first non-null.
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


class Spec:
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
                if group in HIDDEN_GROUPS or op_id in HIDDEN_OP_IDS:
                    continue
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
            out.append(
                Param(
                    name=p["name"],
                    location=p["in"],
                    required=bool(p.get("required")),
                    type=_schema_type(schema),
                    description=p.get("description", ""),
                    enum=_schema_enum(schema),
                )
            )
        rb = op.get("requestBody")
        if rb:
            js = rb.get("content", {}).get("application/json", {}).get("schema", {})
            if isinstance(js, dict) and "$ref" in js:
                js = _resolve_ref(self.raw, js["$ref"])
            props = js.get("properties", {}) if isinstance(js, dict) else {}
            required_names = set(js.get("required", [])) if isinstance(js, dict) else set()
            for pname, pschema in props.items():
                out.append(
                    Param(
                        name=pname,
                        location="body",
                        required=pname in required_names,
                        type=_schema_type(pschema),
                        description=pschema.get("description", "") if isinstance(pschema, dict) else "",
                        enum=_schema_enum(pschema),
                    )
                )
        return out

    def find(self, group: str, name: str) -> Optional[Operation]:
        for op in self.groups.get(group, []):
            if op.name == name:
                return op
        return None


def load_spec(path: Optional[str] = None) -> Spec:
    """Load an OpenAPI spec from an explicit path or the bundled copy."""
    target = Path(path) if path else BUNDLED_SPEC
    with open(target, "r", encoding="utf-8") as fh:
        return Spec(json.load(fh))


def save_bundled(raw: Dict[str, Any]) -> Path:
    """Refresh the bundled openapi.json cache."""
    BUNDLED_SPEC.parent.mkdir(parents=True, exist_ok=True)
    with open(BUNDLED_SPEC, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, ensure_ascii=False)
    return BUNDLED_SPEC

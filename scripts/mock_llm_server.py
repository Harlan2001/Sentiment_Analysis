"""假 LLM 服务：供 E2E / 本地联调返回确定性的 OpenAI 兼容响应。

用途:
    - E2E 里把后端 LLM_BASE_URL 指向本服务, 让「新闻分析 → 对话」链路离线可测(不触真实 Kingstar)
    - 本地起: uv run uvicorn scripts.mock_llm_server:app --host 0.0.0.0 --port 8080

行为:
    - POST /v1/chat/completions (OpenAI 兼容):
        * stream=false  返回固定「利多分析」JSON(OpenAI chat.completion 形状)
        * stream=true   返回 SSE 增量(逐 delta 完成一次对话回复)
    - GET  /health  存活探针

安全: 本服务只读取请求体返回固定内容, 不产生任何外部效应。
"""

from __future__ import annotations

import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

app = FastAPI(title="mock-llm-server")

# 固定「利多债市」分析结果(OpenAI 响应里 choices[0].message.content 的 JSON 字符串)
FIXED_ANALYSIS = {
    "direction": "positive",
    "horizon": "短期",
    "reason": "降息预期支撑债市（mock LLM 固定响应）",
    "factors": [
        {
            "code": "RATE",
            "name": "利率",
            "category": "MACRO",
            "type": "quantitative",
            "direction": "positive",
            "logic_impact": "降息 → 流动性宽松 → 收益率下行",
        }
    ],
}

# 流式对话逐段内容(mock 一条简短回复)
STREAM_CHUNKS = ["当前债市情绪以", "利多为主，", "需关注财政供给节奏。"]


def _sse(data: dict) -> str:
    """包装为 SSE data 帧(不带 event 字段, openai SDK 直接读 data)。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    if body.get("stream"):
        async def gen():
            for chunk in STREAM_CHUNKS:
                yield _sse(
                    {
                        "id": "mock-stream",
                        "object": "chat.completion.chunk",
                        "choices": [{"index": 0, "delta": {"content": chunk}}],
                    }
                )
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return JSONResponse(
        {
            "id": "mock-1",
            "object": "chat.completion",
            "model": body.get("model", "mock-model"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(FIXED_ANALYSIS, ensure_ascii=False),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 8, "completion_tokens": 16, "total_tokens": 24},
        }
    )
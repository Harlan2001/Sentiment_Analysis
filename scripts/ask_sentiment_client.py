"""通过 Streamable HTTP 调用 ask_sentiment 的最小 MCP 客户端。

示例：
    uv run python scripts/ask_sentiment_client.py "政策驱动对下半年债市的影响"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

load_dotenv()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="调用 Sentiment MCP 完整 Markdown 问答")
    parser.add_argument("question", help="要交给 Sentiment 分析的问题")
    parser.add_argument(
        "--url",
        default=os.environ.get(
            "SENTIMENT_MCP_RESOURCE_URL", "http://127.0.0.1:8002/mcp"
        ),
        help="Sentiment MCP Streamable HTTP 地址",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("SENTIMENT_MCP_ACCESS_TOKEN"),
        help="MCP Bearer Token，默认读取 .env",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    question = args.question.strip()
    if not question:
        raise SystemExit("问题不能为空")

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    async with httpx.AsyncClient(
        headers=headers,
        timeout=650.0,
        trust_env=False,
    ) as http_client:
        async with streamable_http_client(
            args.url,
            http_client=http_client,
        ) as streams:
            read_stream, write_stream, *_ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    "ask_sentiment",
                    {"question": question},
                )

    if result.is_error:
        message = "\n".join(
            block.text for block in result.content if hasattr(block, "text")
        )
        raise SystemExit(f"ask_sentiment 调用失败：{message or '未知错误'}")

    # 优先读取程序可直接消费的字段，同时兼容仅返回 TextContent 的服务。
    structured = result.structured_content or {}
    markdown = structured.get("markdown") if isinstance(structured, dict) else None
    if not markdown:
        markdown = "\n".join(
            block.text for block in result.content if hasattr(block, "text")
        )
    print(markdown)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(_run(_parse_args()))

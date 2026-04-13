#!/usr/bin/env python3
"""
Tax review v3 MCP server.
기준일·부칙 검토에 더해 연혁법령 분석 인터페이스 결과를 함께 반환합니다.
"""
import asyncio
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastmcp import FastMCP

from .hwpx_parser import extract_hwpx_text
from .tax_case_review_v3 import review_related_laws_v3, summarize_case_v3
from .tools import get_law_detail, get_precedent_detail, search_administrative_rule, search_law, search_precedent

load_dotenv()

api = FastAPI(title="korean-law-tax-review-v3")
mcp = FastMCP()


async def _to_thread(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


@api.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "Korean Tax Review MCP Server v3",
        "law_api_key": "configured" if os.environ.get("LAW_API_KEY") else "missing",
    }


@mcp.tool()
async def health():
    return await health_check()


@mcp.tool()
async def extract_hwpx_text_tool(hwpx_path: Optional[str] = None, hwpx_base64: Optional[str] = None):
    return await _to_thread(extract_hwpx_text, hwpx_path=hwpx_path, hwpx_base64=hwpx_base64)


@mcp.tool()
async def analyze_case_document_tool(document_text: str):
    return await _to_thread(summarize_case_v3, document_text)


@mcp.tool()
async def review_related_laws_tool(document_text: str, include_law_text: bool = False):
    result = await _to_thread(review_related_laws_v3, document_text)
    if not include_law_text:
        for item in result.get("reviewed_laws", []):
            item.pop("article_text", None)
    return result


@mcp.tool()
async def search_law_tool(query: str, page: int = 1, page_size: int = 10):
    return await _to_thread(search_law, query, page, page_size, None)


@mcp.tool()
async def get_law_detail_tool(law_id: str):
    return await _to_thread(get_law_detail, law_id, None)


@mcp.tool()
async def search_precedent_tool(query: str, page: int = 1, page_size: int = 10, court: Optional[str] = None):
    return await _to_thread(search_precedent, query, page, page_size, court, None)


@mcp.tool()
async def get_precedent_detail_tool(precedent_id: str):
    return await _to_thread(get_precedent_detail, precedent_id, None)


@mcp.tool()
async def search_administrative_rule_tool(query: str, page: int = 1, page_size: int = 10):
    return await _to_thread(search_administrative_rule, query, page, page_size, None)


if __name__ == "__main__":
    http_mode = os.getenv("HTTP_MODE") == "1"
    port = int(os.getenv("PORT", "10000"))
    if http_mode:
        mcp.run(transport="http", host="0.0.0.0", port=port)
    else:
        mcp.run()

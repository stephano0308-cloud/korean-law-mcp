#!/usr/bin/env python3
"""
Tax review flavored MCP server built on top of korean-law-mcp.
HWPX 사건개요/관련법령 초안을 입력받아 관련법령 검토 결과를 반환합니다.
"""
import asyncio
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastmcp import FastMCP

from .hwpx_parser import extract_hwpx_text
from .tax_case_review import review_related_laws, summarize_case
from .tools import (
    get_law_detail,
    get_precedent_detail,
    search_administrative_rule,
    search_law,
    search_precedent,
)

load_dotenv()

api = FastAPI(title="korean-law-tax-review")
mcp = FastMCP()


async def _to_thread(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


@api.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "Korean Tax Review MCP Server",
        "law_api_key": "configured" if os.environ.get("LAW_API_KEY") else "missing",
    }


@mcp.tool()
async def health():
    """서비스 상태를 확인합니다."""
    return await health_check()


@mcp.tool()
async def extract_hwpx_text_tool(hwpx_path: Optional[str] = None, hwpx_base64: Optional[str] = None):
    """
    HWPX 파일에서 텍스트를 추출합니다.

    Args:
        hwpx_path: 서버가 읽을 수 있는 HWPX 파일 경로
        hwpx_base64: base64 인코딩된 HWPX 파일 내용

    Returns:
        추출 텍스트와 스캔한 XML 파일 목록
    """
    return await _to_thread(extract_hwpx_text, hwpx_path=hwpx_path, hwpx_base64=hwpx_base64)


@mcp.tool()
async def analyze_case_document_tool(document_text: str):
    """
    사건 문서 텍스트에서 처분개요, 쟁점, 관련법령 기재 내역을 구조화합니다.
    """
    return await _to_thread(summarize_case, document_text)


@mcp.tool()
async def review_related_laws_tool(document_text: str, include_law_text: bool = False):
    """
    사건 문서에 적힌 관련법령을 공식 법령 검색 결과와 대조하여
    유지/수정/추가 필요사항을 출력합니다.
    """
    result = await _to_thread(review_related_laws, document_text)
    if not include_law_text:
        for item in result.get("reviewed_laws", []):
            item.pop("article_text", None)
    return result


@mcp.tool()
async def search_law_tool(query: str, page: int = 1, page_size: int = 10):
    """법령을 키워드로 검색합니다."""
    return await _to_thread(search_law, query, page, page_size, None)


@mcp.tool()
async def get_law_detail_tool(law_id: str):
    """특정 법령의 상세 정보 및 조문을 조회합니다."""
    return await _to_thread(get_law_detail, law_id, None)


@mcp.tool()
async def search_precedent_tool(query: str, page: int = 1, page_size: int = 10, court: Optional[str] = None):
    """판례를 키워드로 검색합니다."""
    return await _to_thread(search_precedent, query, page, page_size, court, None)


@mcp.tool()
async def get_precedent_detail_tool(precedent_id: str):
    """특정 판례의 상세 정보를 조회합니다."""
    return await _to_thread(get_precedent_detail, precedent_id, None)


@mcp.tool()
async def search_administrative_rule_tool(query: str, page: int = 1, page_size: int = 10):
    """행정규칙을 키워드로 검색합니다."""
    return await _to_thread(search_administrative_rule, query, page, page_size, None)


if __name__ == "__main__":
    http_mode = os.getenv("HTTP_MODE") == "1"
    port = int(os.getenv("PORT", "10000"))
    if http_mode:
        mcp.run(transport="http", host="0.0.0.0", port=port)
    else:
        mcp.run()

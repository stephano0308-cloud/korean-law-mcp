#!/usr/bin/env python3
"""
Korean Law & Precedent MCP Server using FastMCP
국가법령정보센터 Open API를 활용한 법률/판례 검색 서버
"""
import asyncio
import sys
import os
import logging
from fastmcp import FastMCP
from fastapi import FastAPI
from pydantic import BaseModel, Field
from .tools import (
    search_law,
    get_law_detail,
    search_precedent,
    get_precedent_detail,
    search_administrative_rule
)
from .hwpx_parser import parse_hwpx_from_path
from .disposition_analyzer import analyze_disposition
from .historical_law_search import (
    search_historical_law,
    get_historical_law_detail,
    get_specific_articles,
)
from .tax_law_agent import (
    research_tax_law_from_file,
    research_tax_law_from_text,
)
from typing import Optional, List
from dotenv import load_dotenv
from contextlib import contextmanager

# .env 파일 로드
load_dotenv()

# FastAPI / FastMCP 앱 구성
api = FastAPI()
mcp_logger = logging.getLogger("law-mcp")
level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
mcp_logger.setLevel(level)
if not mcp_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    mcp_logger.addHandler(handler)
mcp_logger.propagate = True
mcp = FastMCP()


# Pydantic 모델 정의
class LawSearchRequest(BaseModel):
    query: str = Field(..., description="검색할 법령 키워드")
    page: int = Field(1, description="페이지 번호 (기본값: 1)", ge=1)
    page_size: int = Field(10, description="페이지당 결과 수 (기본값: 10, 최대: 50)", ge=1, le=50)


class LawDetailRequest(BaseModel):
    law_id: str = Field(..., description="조회할 법령 ID")


class PrecedentSearchRequest(BaseModel):
    query: str = Field(..., description="검색할 판례 키워드")
    page: int = Field(1, description="페이지 번호 (기본값: 1)", ge=1)
    page_size: int = Field(10, description="페이지당 결과 수 (기본값: 10, 최대: 50)", ge=1, le=50)
    court: Optional[str] = Field(None, description="법원 구분 (예: '대법원', '헌법재판소')")


class PrecedentDetailRequest(BaseModel):
    precedent_id: str = Field(..., description="조회할 판례 일련번호")


class AdminRuleSearchRequest(BaseModel):
    query: str = Field(..., description="검색할 행정규칙 키워드")
    page: int = Field(1, description="페이지 번호 (기본값: 1)", ge=1)
    page_size: int = Field(10, description="페이지당 결과 수 (기본값: 10, 최대: 50)", ge=1, le=50)


class HistoricalLawSearchRequest(BaseModel):
    law_name: str = Field(..., description="검색할 법령명 (예: '소득세법', '법인세법 시행령')")
    effective_date: str = Field(..., description="시행일자 기준일 (YYYYMMDD 형식, 예: '20200301')")


class HistoricalLawDetailRequest(BaseModel):
    law_id: str = Field(..., description="법령 ID (연혁법령 검색 결과에서 얻은 법령ID)")


class SpecificArticlesRequest(BaseModel):
    law_id: str = Field(..., description="법령 ID")
    article_numbers: List[str] = Field(..., description="조문번호 목록 (예: ['94', '95', '96'])")


class TaxLawResearchFileRequest(BaseModel):
    file_path: str = Field(..., description="처분개요 HWPX 파일의 절대 경로")


class TaxLawResearchTextRequest(BaseModel):
    text: str = Field(..., description="처분개요 텍스트 내용")


class ParseHwpxRequest(BaseModel):
    file_path: str = Field(..., description="HWPX 파일의 절대 경로")


class AnalyzeDispositionRequest(BaseModel):
    text: str = Field(..., description="처분개요 텍스트 내용")


# 실제 구현 함수들
async def search_law_impl(req: LawSearchRequest, arguments: Optional[dict] = None):
    """법령 검색 구현"""
    try:
        if arguments is None:
            arguments = {}
        return await asyncio.to_thread(search_law, req.query, req.page, req.page_size, arguments)
    except Exception as e:
        return {"error": f"법령 검색 중 오류가 발생했습니다: {str(e)}"}


async def get_law_detail_impl(req: LawDetailRequest, arguments: Optional[dict] = None):
    """법령 상세 조회 구현"""
    try:
        if arguments is None:
            arguments = {}
        return await asyncio.to_thread(get_law_detail, req.law_id, arguments)
    except Exception as e:
        return {"error": f"법령 상세 조회 중 오류가 발생했습니다: {str(e)}"}


async def search_precedent_impl(req: PrecedentSearchRequest, arguments: Optional[dict] = None):
    """판례 검색 구현"""
    try:
        if arguments is None:
            arguments = {}
        return await asyncio.to_thread(
            search_precedent, 
            req.query, 
            req.page, 
            req.page_size, 
            req.court,
            arguments
        )
    except Exception as e:
        return {"error": f"판례 검색 중 오류가 발생했습니다: {str(e)}"}


async def get_precedent_detail_impl(req: PrecedentDetailRequest, arguments: Optional[dict] = None):
    """판례 상세 조회 구현"""
    try:
        if arguments is None:
            arguments = {}
        return await asyncio.to_thread(get_precedent_detail, req.precedent_id, arguments)
    except Exception as e:
        return {"error": f"판례 상세 조회 중 오류가 발생했습니다: {str(e)}"}


async def search_administrative_rule_impl(req: AdminRuleSearchRequest, arguments: Optional[dict] = None):
    """행정규칙 검색 구현"""
    try:
        if arguments is None:
            arguments = {}
        return await asyncio.to_thread(
            search_administrative_rule, 
            req.query, 
            req.page, 
            req.page_size,
            arguments
        )
    except Exception as e:
        return {"error": f"행정규칙 검색 중 오류가 발생했습니다: {str(e)}"}


async def health_impl():
    """서비스 상태 확인 구현"""
    api_key = os.environ.get("LAW_API_KEY", "")
    api_key_status = "설정됨" if api_key else "설정되지 않음"
    return {
        "status": "ok",
        "service": "Korean Law & Precedent MCP Server",
        "environment": {
            "law_api_key": api_key_status,
            "api_key_preview": api_key[:10] + "..." if api_key else "None"
        }
    }


# 일시 환경 변수 적용용 컨텍스트 매니저
@contextmanager
def temporary_env(overrides: dict):
    saved_values = {}
    try:
        for key, value in (overrides or {}).items():
            saved_values[key] = os.environ.get(key)
            if value is not None:
                os.environ[key] = str(value)
        yield
    finally:
        for key, original in saved_values.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


# HTTP 엔드포인트
@api.get("/health")
async def health_check_get():
    """HTTP GET 엔드포인트: 서비스 상태 확인"""
    return await health_impl()

@api.post("/health")
async def health_check_post():
    """HTTP POST 엔드포인트: 서비스 상태 확인"""
    return await health_impl()


# HTTP 엔드포인트: 도구 목록 조회
@api.get("/tools")
async def get_tools_http():
    """HTTP 엔드포인트: 사용 가능한 도구 목록 조회"""
    try:
        # FastMCP의 내부 도구 목록 가져오기
        tools_list = []
        server = getattr(mcp, 'server', None)  # type: ignore
        if server and hasattr(server, 'tools'):
            tools = getattr(server, 'tools', {})  # type: ignore
            for tool_name, tool in tools.items():
                tool_info = {
                    "name": tool_name,
                    "description": getattr(tool, 'description', '') or '',
                }
                if hasattr(tool, 'parameters'):
                    tool_info["parameters"] = getattr(tool, 'parameters', {})
                else:
                    tool_info["parameters"] = {}
                tools_list.append(tool_info)
        
        # FastMCP 접근 실패 시 하드코딩된 목록 반환
        if not tools_list:
            mcp_logger.warning("FastMCP tools not accessible, returning hardcoded tool list")
            tools_list = [
                {
                    "name": "health",
                    "description": "서비스 상태 확인",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "search_law_tool",
                    "description": "법령을 키워드로 검색합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "검색할 법령 키워드 (예: '민법', '상법')"},
                            "page": {"type": "integer", "description": "페이지 번호 (기본값: 1)", "default": 1, "minimum": 1},
                            "page_size": {"type": "integer", "description": "페이지당 결과 수 (기본값: 10, 최대: 50)", "default": 10, "minimum": 1, "maximum": 50}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "get_law_detail_tool",
                    "description": "특정 법령의 상세 정보 및 전문(조문)을 조회합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "law_id": {"type": "string", "description": "법령 ID (법령 검색 결과에서 얻은 법령ID)"}
                        },
                        "required": ["law_id"]
                    }
                },
                {
                    "name": "search_precedent_tool",
                    "description": "판례를 키워드로 검색합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "검색할 판례 키워드 (예: '손해배상', '계약')"},
                            "page": {"type": "integer", "description": "페이지 번호 (기본값: 1)", "default": 1, "minimum": 1},
                            "page_size": {"type": "integer", "description": "페이지당 결과 수 (기본값: 10, 최대: 50)", "default": 10, "minimum": 1, "maximum": 50},
                            "court": {"type": "string", "description": "법원 구분 (예: '대법원', '헌법재판소')"}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "get_precedent_detail_tool",
                    "description": "특정 판례의 상세 정보를 조회합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "precedent_id": {"type": "string", "description": "판례 일련번호"}
                        },
                        "required": ["precedent_id"]
                    }
                },
                {
                    "name": "search_administrative_rule_tool",
                    "description": "행정규칙을 키워드로 검색합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "검색할 행정규칙 키워드"},
                            "page": {"type": "integer", "description": "페이지 번호 (기본값: 1)", "default": 1, "minimum": 1},
                            "page_size": {"type": "integer", "description": "페이지당 결과 수 (기본값: 10, 최대: 50)", "default": 10, "minimum": 1, "maximum": 50}
                        },
                        "required": ["query"]
                    }
                }
            ]
        
        return tools_list
    except Exception as e:
        mcp_logger.exception("Error getting tools list: %s", str(e))
        return []


# HTTP 엔드포인트: 도구 호출
@api.post("/tools/{tool_name}")
async def call_tool_http(tool_name: str, request_data: dict):
    mcp_logger.debug("HTTP call_tool | tool=%s request=%s", tool_name, request_data)
    env = request_data.get("env", {}) if isinstance(request_data, dict) else {}

    async def run_sync(func, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    
    # 공통 타입 변환 함수들
    def convert_float_to_int(data: dict, keys: list):
        """지정된 키의 float 값을 int로 변환"""
        for key in keys:
            if key in data and isinstance(data[key], float):
                data[key] = int(data[key])
    
    def convert_to_str(data: dict, keys: list):
        """지정된 키의 값을 문자열로 변환"""
        for key in keys:
            if key in data and data[key] is not None and not isinstance(data[key], str):
                data[key] = str(data[key])

    try:
        # 크레덴셜 추출
        creds = {}
        if isinstance(env, dict):
            for k in ("LAW_API_KEY", "LAW_API_URL"):
                if k in env:
                    creds[k] = env[k]
        
        if creds:
            masked = dict(creds)
            if "LAW_API_KEY" in masked and masked["LAW_API_KEY"]:
                masked["LAW_API_KEY"] = masked["LAW_API_KEY"][:6] + "***"
            mcp_logger.debug("Applying temp env | %s", masked)

        async def run_with_env(func, *args, **kwargs):
            with temporary_env(creds):
                return await run_sync(func, *args, **kwargs)

        if tool_name == "health":
            return await health_impl()

        if tool_name == "search_law_tool":
            query = request_data.get("query")
            if not query:
                return {"error": "Missing required parameter: query"}
            # 타입 변환
            convert_float_to_int(request_data, ["page", "page_size"])
            convert_to_str(request_data, ["query"])
            page = request_data.get("page", 1)
            page_size = request_data.get("page_size", 10)
            return await run_with_env(
                search_law, query, page, page_size, arguments=request_data
            )

        if tool_name == "get_law_detail_tool":
            law_id = request_data.get("law_id")
            if not law_id:
                return {"error": "Missing required parameter: law_id"}
            convert_to_str(request_data, ["law_id"])
            return await run_with_env(
                get_law_detail, law_id, arguments=request_data
            )

        if tool_name == "search_precedent_tool":
            query = request_data.get("query")
            if not query:
                return {"error": "Missing required parameter: query"}
            # 타입 변환
            convert_float_to_int(request_data, ["page", "page_size"])
            convert_to_str(request_data, ["query", "court"])
            page = request_data.get("page", 1)
            page_size = request_data.get("page_size", 10)
            court = request_data.get("court")
            return await run_with_env(
                search_precedent, query, page, page_size, court, arguments=request_data
            )

        if tool_name == "get_precedent_detail_tool":
            precedent_id = request_data.get("precedent_id")
            if not precedent_id:
                return {"error": "Missing required parameter: precedent_id"}
            convert_to_str(request_data, ["precedent_id"])
            return await run_with_env(
                get_precedent_detail, precedent_id, arguments=request_data
            )

        if tool_name == "search_administrative_rule_tool":
            query = request_data.get("query")
            if not query:
                return {"error": "Missing required parameter: query"}
            # 타입 변환
            convert_float_to_int(request_data, ["page", "page_size"])
            convert_to_str(request_data, ["query"])
            page = request_data.get("page", 1)
            page_size = request_data.get("page_size", 10)
            return await run_with_env(
                search_administrative_rule, query, page, page_size, arguments=request_data
            )

        # ── 세법 연구 에이전트 도구 ──

        if tool_name == "parse_hwpx_tool":
            fp = request_data.get("file_path")
            if not fp:
                return {"error": "Missing required parameter: file_path"}
            return await run_sync(parse_hwpx_from_path, fp)

        if tool_name == "analyze_disposition_tool":
            txt = request_data.get("text")
            if not txt:
                return {"error": "Missing required parameter: text"}
            return await run_sync(analyze_disposition, txt)

        if tool_name == "search_historical_law_tool":
            ln = request_data.get("law_name")
            ed = request_data.get("effective_date")
            if not ln or not ed:
                return {"error": "Missing required parameters: law_name, effective_date"}
            return await run_with_env(search_historical_law, ln, ed, arguments=request_data)

        if tool_name == "get_historical_law_detail_tool":
            lid = request_data.get("law_id")
            if not lid:
                return {"error": "Missing required parameter: law_id"}
            return await run_with_env(get_historical_law_detail, lid, arguments=request_data)

        if tool_name == "get_specific_articles_tool":
            lid = request_data.get("law_id")
            ans = request_data.get("article_numbers")
            if not lid or not ans:
                return {"error": "Missing required parameters: law_id, article_numbers"}
            if not isinstance(ans, list):
                ans = [str(ans)]
            return await run_with_env(get_specific_articles, lid, ans, arguments=request_data)

        if tool_name == "research_tax_law_tool":
            fp = request_data.get("file_path")
            if not fp:
                return {"error": "Missing required parameter: file_path"}
            return await run_with_env(research_tax_law_from_file, fp, arguments=request_data)

        if tool_name == "research_tax_law_from_text_tool":
            txt = request_data.get("text")
            if not txt:
                return {"error": "Missing required parameter: text"}
            return await run_with_env(research_tax_law_from_text, txt, arguments=request_data)

        return {"error": "Tool not found"}
    except Exception as e:
        mcp_logger.exception("Error in call_tool_http: %s", str(e))
        return {"error": f"Error calling tool: {str(e)}"}


# MCP 도구 정의
@mcp.tool()
async def health():
    """서비스 상태 확인"""
    return await health_impl()


@mcp.tool()
async def search_law_tool(
    query: str,
    page: int = 1,
    page_size: int = 10
):
    """
    법령을 키워드로 검색합니다.
    
    Args:
        query: 검색할 법령 키워드 (예: '민법', '상법', '근로기준법')
        page: 페이지 번호 (기본값: 1)
        page_size: 페이지당 결과 수 (기본값: 10, 최대: 50)
    
    Returns:
        검색된 법령 목록
    """
    req = LawSearchRequest(query=query, page=page, page_size=page_size)
    return await search_law_impl(req, None)


@mcp.tool()
async def get_law_detail_tool(law_id: str):
    """
    특정 법령의 상세 정보 및 전문(조문)을 조회합니다.
    
    Args:
        law_id: 법령 ID (법령 검색 결과에서 얻은 법령ID)
    
    Returns:
        법령의 상세 정보와 조문 내용
    """
    req = LawDetailRequest(law_id=law_id)
    return await get_law_detail_impl(req, None)


@mcp.tool()
async def search_precedent_tool(
    query: str,
    page: int = 1,
    page_size: int = 10,
    court: Optional[str] = None
):
    """
    판례를 키워드로 검색합니다.
    
    Args:
        query: 검색할 판례 키워드 (예: '손해배상', '계약', '부당해고')
        page: 페이지 번호 (기본값: 1)
        page_size: 페이지당 결과 수 (기본값: 10, 최대: 50)
        court: 법원 구분 (예: '대법원', '헌법재판소')
    
    Returns:
        검색된 판례 목록
    """
    req = PrecedentSearchRequest(
        query=query, 
        page=page, 
        page_size=page_size, 
        court=court
    )
    return await search_precedent_impl(req, None)


@mcp.tool()
async def get_precedent_detail_tool(precedent_id: str):
    """
    특정 판례의 상세 정보를 조회합니다.
    
    Args:
        precedent_id: 판례 일련번호 (판례 검색 결과에서 얻은 판례일련번호)
    
    Returns:
        판례의 상세 정보 (판결요지, 판례내용 등)
    """
    req = PrecedentDetailRequest(precedent_id=precedent_id)
    return await get_precedent_detail_impl(req, None)


@mcp.tool()
async def search_administrative_rule_tool(
    query: str,
    page: int = 1,
    page_size: int = 10
):
    """
    행정규칙을 키워드로 검색합니다.
    
    Args:
        query: 검색할 행정규칙 키워드
        page: 페이지 번호 (기본값: 1)
        page_size: 페이지당 결과 수 (기본값: 10, 최대: 50)
    
    Returns:
        검색된 행정규칙 목록
    """
    req = AdminRuleSearchRequest(query=query, page=page, page_size=page_size)
    return await search_administrative_rule_impl(req, None)


# ────────────────────────────────────────────────────────────────
# 세법 연구 에이전트 MCP 도구들
# ────────────────────────────────────────────────────────────────

@mcp.tool()
async def parse_hwpx_tool(file_path: str):
    """
    HWPX(한글) 파일을 파싱하여 텍스트를 추출합니다.
    처분개요 등 한글 문서의 내용을 텍스트로 변환합니다.

    Args:
        file_path: HWPX 파일의 절대 경로

    Returns:
        추출된 텍스트, 섹션 목록, 테이블 데이터
    """
    return await asyncio.to_thread(parse_hwpx_from_path, file_path)


@mcp.tool()
async def analyze_disposition_tool(text: str):
    """
    처분개요 텍스트를 분석하여 세목, 처분일자, 과세기간, 관련 법조문 등
    핵심 정보를 자동 추출합니다.

    Args:
        text: 처분개요 텍스트 내용

    Returns:
        분석 결과 (세목, 처분일자, 과세기간, 처분유형, 세액, 법조문 인용, 관련 법령 등)
    """
    return await asyncio.to_thread(analyze_disposition, text)


@mcp.tool()
async def search_historical_law_tool(law_name: str, effective_date: str):
    """
    특정 시점에 시행 중이던 연혁법령을 검색합니다.
    처분 당시 적용되었던 법령 버전을 찾을 때 사용합니다.

    Args:
        law_name: 법령명 (예: '소득세법', '법인세법 시행령')
        effective_date: 시행일자 기준일 (YYYYMMDD 형식, 예: '20200301')

    Returns:
        해당 시점에 유효했던 법령 정보 (법령ID, 시행일자, 공포일자 등)
    """
    return await asyncio.to_thread(search_historical_law, law_name, effective_date)


@mcp.tool()
async def get_historical_law_detail_tool(law_id: str):
    """
    특정 연혁법령 버전의 상세 정보(전문 및 조문)를 조회합니다.
    search_historical_law_tool로 찾은 법령ID를 사용합니다.

    Args:
        law_id: 법령 ID (연혁법령 검색 결과에서 얻은 법령ID)

    Returns:
        법령 상세 정보 (법령명, 시행일자, 전체 조문 내용)
    """
    return await asyncio.to_thread(get_historical_law_detail, law_id)


@mcp.tool()
async def get_specific_articles_tool(law_id: str, article_numbers: List[str]):
    """
    특정 법령에서 지정된 조문만 추출합니다.
    전체 법령이 아닌 필요한 조문만 조회할 때 사용합니다.

    Args:
        law_id: 법령 ID
        article_numbers: 조문번호 목록 (예: ['94', '95', '96'])

    Returns:
        지정된 조문의 전문 내용
    """
    return await asyncio.to_thread(get_specific_articles, law_id, article_numbers)


@mcp.tool()
async def research_tax_law_tool(file_path: str):
    """
    처분개요 HWPX 파일을 분석하여 처분 당시 적용된 관련 세법 조문을
    자동으로 찾아 정리하는 통합 에이전트 도구입니다.

    워크플로우:
    1. HWPX 파일 파싱 → 텍스트 추출
    2. 처분개요 분석 → 세목, 처분일자, 법조문 인용 등 추출
    3. 연혁법령 검색 → 처분 당시 시행 중이던 법령 버전 식별
    4. 관련 조문 조회 → 해당 법령에서 관련 조문 전문 조회
    5. 결과 정리 → 구조화된 보고서 생성

    Args:
        file_path: 처분개요 HWPX 파일의 절대 경로

    Returns:
        처분개요 분석 결과 및 관련 세법 조문 전문을 포함한 보고서
    """
    return await asyncio.to_thread(research_tax_law_from_file, file_path)


@mcp.tool()
async def research_tax_law_from_text_tool(text: str):
    """
    처분개요 텍스트를 직접 입력받아 관련 세법 조문을 자동으로 찾아 정리합니다.
    HWPX 파일이 아닌 텍스트를 직접 붙여넣을 때 사용합니다.

    Args:
        text: 처분개요 텍스트 내용

    Returns:
        처분개요 분석 결과 및 관련 세법 조문 전문을 포함한 보고서
    """
    return await asyncio.to_thread(research_tax_law_from_text, text)


async def main():
    """MCP 서버를 실행합니다."""
    print("MCP Korean Law & Precedent Server starting...", file=sys.stderr)
    print("Server: korean-law-service", file=sys.stderr)
    print("Available tools: health, search_law_tool, get_law_detail_tool, search_precedent_tool, get_precedent_detail_tool, search_administrative_rule_tool, parse_hwpx_tool, analyze_disposition_tool, search_historical_law_tool, get_historical_law_detail_tool, get_specific_articles_tool, research_tax_law_tool, research_tax_law_from_text_tool", file=sys.stderr)
    
    try:
        await mcp.run_stdio_async()
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise


import os

if __name__ == "__main__":
    http_mode = os.getenv("HTTP_MODE") == "1"
    port = int(os.getenv("PORT", "10000"))

    if http_mode:
        print(f"Starting HTTP MCP server on port {port}")
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=port
        )
    else:
        print("Starting STDIO MCP server")
        mcp.run()


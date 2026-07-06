#!/usr/bin/env python3
"""
조세심판원 인사담당자 지원 MCP 서버 (Tax Tribunal HR MCP Server)

국가공무원(및 파견 지방공무원 참고) 인사 업무를 지원한다.
- 인사 이벤트별 시계열 체크리스트(내장) + 최신 규정 검증용 검색 도구
- 국가법령정보센터 Open API: 법령·행정규칙(예규·지침)·판례 원문 조회
- 인사혁신처 법령정보 목록(법률~훈령·예규·고시) 색인 검색

실행:
    python -m src.hr_main                 # STDIO 모드 (Claude Desktop 등)
    HTTP_MODE=1 python -m src.hr_main     # HTTP 모드 (Claude 웹/모바일 커넥터)
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .admin_rule_detail import get_administrative_rule_detail
from .hr_keywords import suggest_keywords
from .hr_workflows import get_workflow, list_workflows, search_workflow_steps
from .mpm_law_catalog import fetch_mpm_catalog, search_mpm_catalog
from .tools import (
    get_law_detail,
    get_precedent_detail,
    search_administrative_rule,
    search_law,
    search_precedent,
)

load_dotenv()

INSTRUCTIONS_PATH = Path(__file__).resolve().parent.parent / "docs" / "tax-tribunal-hr" / "INSTRUCTIONS.md"

SERVER_INSTRUCTIONS = (
    "조세심판원 인사담당자 지원 MCP 서버입니다. 인사 질문을 받으면 "
    "① get_hr_review_guide_tool로 검토 절차를 확인하고 "
    "② get_hr_workflow_tool로 시계열 체크리스트를 가져온 뒤 "
    "③ search_law_tool/search_admin_rule_tool로 최신 규정을 검증하여 "
    "담당자 할 일(시계열순), 규정 요약, 원문 링크를 답변하세요."
)

mcp = FastMCP(name="tax-tribunal-hr", instructions=SERVER_INSTRUCTIONS)


def _load_instructions() -> str:
    try:
        return INSTRUCTIONS_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        return f"역할 지침 파일을 읽을 수 없습니다: {exc}"


# ────────────────────────────────────────────────────────────────
# 상태·가이드 도구
# ────────────────────────────────────────────────────────────────

def _health_data() -> dict:
    api_key = os.environ.get("LAW_API_KEY", "")
    return {
        "status": "ok",
        "service": "Tax Tribunal HR MCP Server (조세심판원 인사담당자 지원)",
        "law_api_key": "설정됨" if api_key else "설정되지 않음 (법령·예규 원문 조회 불가)",
        "instructions_file": "loaded" if INSTRUCTIONS_PATH.exists() else "missing",
        "mcp_endpoint": "/mcp",
    }


@mcp.custom_route("/", methods=["GET"])
async def root_status(request: Request) -> JSONResponse:
    """브라우저 접속용 상태 페이지. 커넥터 등록 전 서버 기동 확인에 사용."""
    return JSONResponse(_health_data())


@mcp.custom_route("/health", methods=["GET"])
async def health_status(request: Request) -> JSONResponse:
    """플랫폼 헬스체크 및 브라우저 확인용 엔드포인트."""
    return JSONResponse(_health_data())


@mcp.tool()
async def health():
    """서비스 상태 및 API 키 설정 여부를 확인합니다."""
    return _health_data()


@mcp.tool()
async def get_hr_review_guide_tool():
    """
    조세심판원 인사 사안 검토 절차와 답변 형식(역할 지침)을 반환합니다.
    인사 질문에 답하기 전에 이 지침을 확인하세요.

    Returns:
        검토 절차, 답변 형식(시계열 할일 표 + 규정 요약 + 원문 링크), 주의사항
    """
    return {"guide_markdown": _load_instructions()}


# ────────────────────────────────────────────────────────────────
# 시계열 체크리스트 도구
# ────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_hr_workflows_tool():
    """
    내장된 인사 업무 워크플로우(시계열 체크리스트) 목록을 조회합니다.
    채용, 승진, 전보, 파견, 질병휴직, 육아휴직, 징계, 퇴직, 평정, 보수, 겸직 등.

    Returns:
        워크플로우 ID·제목·분류·요약 목록
    """
    return list_workflows()


@mcp.tool()
async def get_hr_workflow_tool(workflow: str):
    """
    특정 인사 업무의 시계열 체크리스트를 조회합니다.
    각 단계별 시기/기한, 담당자 할 일, 근거규정(조문), law.go.kr 원문 링크를 반환합니다.

    반환된 verify_queries의 검색어로 search_law_tool/search_admin_rule_tool을 호출해
    최신 규정과 대조한 후 답변에 사용하세요.

    Args:
        workflow: 워크플로우 ID(예: 'sick_leave', 'discipline') 또는
                  한글 키워드(예: '질병휴직', '징계', '승진')

    Returns:
        시계열 단계별 체크리스트 (단계, 시기, 할일, 근거규정, 원문링크, 유의사항)
    """
    return get_workflow(workflow)


@mcp.tool()
async def search_hr_workflow_steps_tool(query: str):
    """
    모든 인사 워크플로우의 단계·할일·근거규정에서 키워드를 검색합니다.
    어떤 워크플로우에 속하는지 모르는 개별 업무(예: '결원보충', '호봉')를 찾을 때 사용합니다.

    Args:
        query: 검색 키워드

    Returns:
        키워드가 포함된 워크플로우 단계 목록
    """
    return search_workflow_steps(query)


@mcp.tool()
async def suggest_hr_keywords_tool(issue_text: str):
    """
    인사 사안 문구를 바탕으로 우선 검색할 법령·예규 키워드를 추천합니다.
    내장 워크플로우가 없는 사안을 조사할 때 출발점으로 사용하세요.

    Args:
        issue_text: 담당자가 제시한 인사 사안 또는 쟁점 (예: '병가 중 직원의 겸직 신고')

    Returns:
        핵심 법령 목록, 쟁점별 키워드, 추천 검색어
    """
    return suggest_keywords(issue_text)


# ────────────────────────────────────────────────────────────────
# 인사혁신처 법령정보 목록 도구
# ────────────────────────────────────────────────────────────────

@mcp.tool()
async def search_mpm_catalog_tool(query: str, categories: Optional[List[str]] = None):
    """
    인사혁신처 법령정보 목록(법률, 대통령령, 총리령, 대통령·국무총리 훈령,
    인사혁신처 훈령·예규·고시)에서 제목·부서 기준으로 검색합니다.
    각 항목에 law.go.kr 원문 링크가 포함됩니다.

    Args:
        query: 검색 키워드 (예: '보수', '복무', '성과평가')
        categories: 선택 카테고리 (law, presidential_decree, prime_minister_rule,
                    presidential_directive, prime_minister_directive,
                    mpm_directive, mpm_established_rule, mpm_notice)

    Returns:
        매칭된 인사혁신처 소관 법령·행정규칙 목록 (원문 링크 포함)
    """
    return await asyncio.to_thread(search_mpm_catalog, query, categories)


@mcp.tool()
async def fetch_mpm_catalog_tool(categories: Optional[List[str]] = None, force_refresh: bool = False):
    """
    인사혁신처 법령정보 전체 목록을 수집합니다. 특정 분류의 예규·지침 전체를
    훑어볼 때 사용합니다. (결과가 크므로 가급적 search_mpm_catalog_tool 사용 권장)

    Args:
        categories: 선택 카테고리 목록 (예: ['mpm_established_rule']=인사혁신처 예규)
        force_refresh: 캐시를 무시하고 새로 수집할지 여부

    Returns:
        카테고리별 법령·행정규칙 목록 (law.go.kr 원문 링크 포함)
    """
    return await asyncio.to_thread(fetch_mpm_catalog, categories, force_refresh)


# ────────────────────────────────────────────────────────────────
# 국가법령정보센터 원문 조회 도구
# ────────────────────────────────────────────────────────────────

@mcp.tool()
async def search_law_tool(query: str, page: int = 1, page_size: int = 10):
    """
    법령(법률·대통령령·총리령 등)을 키워드로 검색합니다.

    Args:
        query: 검색 키워드 (예: '국가공무원법', '공무원임용령', '지방공무원법')
        page: 페이지 번호 (기본값: 1)
        page_size: 페이지당 결과 수 (기본값: 10, 최대: 50)

    Returns:
        법령 목록 (법령ID, 법령명, 소관부처, 공포·시행일자)
    """
    return await asyncio.to_thread(search_law, query, page, page_size, None)


@mcp.tool()
async def get_law_detail_tool(law_id: str):
    """
    법령ID로 법령 전문(조문)을 조회합니다. 조문 원문 인용 시 사용합니다.

    Args:
        law_id: search_law_tool 결과의 법령ID

    Returns:
        법령 상세 정보 및 전체 조문
    """
    return await asyncio.to_thread(get_law_detail, law_id, None)


@mcp.tool()
async def search_admin_rule_tool(query: str, page: int = 1, page_size: int = 10):
    """
    행정규칙(인사혁신처 예규·지침·훈령·고시 등)을 키워드로 검색합니다.

    Args:
        query: 검색 키워드 (예: '공무원보수 등의 업무지침', '국가공무원 복무 징계 관련 예규')
        page: 페이지 번호 (기본값: 1)
        page_size: 페이지당 결과 수 (기본값: 10, 최대: 50)

    Returns:
        행정규칙 목록 (행정규칙ID, 규칙명, 소관부처, 발령일자)
    """
    return await asyncio.to_thread(search_administrative_rule, query, page, page_size, None)


@mcp.tool()
async def get_admin_rule_detail_tool(admrul_id: str):
    """
    행정규칙ID로 예규·지침·훈령의 본문 원문을 조회합니다.

    Args:
        admrul_id: search_admin_rule_tool 결과의 행정규칙ID

    Returns:
        행정규칙 본문 및 상세 정보
    """
    return await asyncio.to_thread(get_administrative_rule_detail, admrul_id, None)


@mcp.tool()
async def search_precedent_tool(
    query: str,
    page: int = 1,
    page_size: int = 10,
    court: Optional[str] = None,
):
    """
    판례를 키워드로 검색합니다. 징계 양정, 소청·행정소송 등 다툼이 있는 쟁점에서 사용합니다.

    Args:
        query: 검색 키워드 (예: '징계처분 재량권 일탈', '직위해제')
        page: 페이지 번호 (기본값: 1)
        page_size: 페이지당 결과 수 (기본값: 10, 최대: 50)
        court: 법원 구분 (예: '대법원', '헌법재판소')

    Returns:
        판례 목록
    """
    return await asyncio.to_thread(search_precedent, query, page, page_size, court, None)


@mcp.tool()
async def get_precedent_detail_tool(precedent_id: str):
    """
    판례일련번호로 판례 상세(판결요지, 참조조문, 전문)를 조회합니다.

    Args:
        precedent_id: search_precedent_tool 결과의 판례일련번호

    Returns:
        판례 상세 정보
    """
    return await asyncio.to_thread(get_precedent_detail, precedent_id, None)


# ────────────────────────────────────────────────────────────────
# 프롬프트
# ────────────────────────────────────────────────────────────────

@mcp.prompt()
def hr_case_review(question: str) -> str:
    """조세심판원 인사 사안 검토: 시계열 할일 정리 + 규정 요약 + 원문 링크"""
    guide = _load_instructions()
    return (
        f"{guide}\n\n---\n\n"
        f"위 지침에 따라 다음 인사 사안을 검토해 주세요.\n\n"
        f"[담당자 질문]\n{question}"
    )


async def main():
    """MCP 서버를 실행합니다."""
    print("Tax Tribunal HR MCP Server starting...", file=sys.stderr)
    await mcp.run_stdio_async()


if __name__ == "__main__":
    http_mode = os.getenv("HTTP_MODE") == "1"
    port = int(os.getenv("PORT", "8097"))

    if http_mode:
        print(f"Starting HTTP MCP server on port {port} (endpoint: /mcp)", file=sys.stderr)
        mcp.run(transport="http", host="0.0.0.0", port=port, path="/mcp")
    else:
        print("Starting STDIO MCP server", file=sys.stderr)
        mcp.run()

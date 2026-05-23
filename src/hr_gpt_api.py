#!/usr/bin/env python3
"""
National Civil Service HR GPT Action API
국가공무원 인사 관련 법령·판례·행정규칙 검색을 위한 GPT Action용 FastAPI 래퍼.

실행 예시:
    uvicorn src.hr_gpt_api:app --host 0.0.0.0 --port ${PORT:-8080}

필수 환경변수:
    LAW_API_KEY=국가법령정보센터 Open API 인증키
선택 환경변수:
    LAW_API_URL=https://www.law.go.kr/DRF
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .admin_rule_detail import get_administrative_rule_detail
from .mpm_law_catalog import fetch_mpm_catalog, search_mpm_catalog
from .tools import (
    get_law_detail,
    get_precedent_detail,
    search_administrative_rule,
    search_law,
    search_precedent,
)


app = FastAPI(
    title="National Civil Service HR GPT API",
    version="1.2.0",
    description=(
        "국가공무원 인사 사안 검토용 GPT Action API. "
        "인사혁신처 법령정보 목록과 국가법령정보센터 Open API 기반으로 "
        "법령, 행정규칙 원문, 판례를 검색한다."
    ),
)


HR_CORE_KEYWORDS = [
    "국무총리보좌기관인사관리지침",
    "국무총리보좌기관 인사관리지침",
    "국무조정실 인사관리",
    "국무총리비서실 인사관리",
    "국가공무원법",
    "공무원임용령",
    "공무원임용규칙",
    "공무원 보수규정",
    "공무원수당 등에 관한 규정",
    "국가공무원 복무규정",
    "공무원 징계령",
    "공무원 징계령 시행규칙",
    "공무원 성과평가 등에 관한 규정",
    "공무원임용시험령",
    "국가공무원 명예퇴직수당 등 지급 규정",
]

HR_ISSUE_KEYWORDS: Dict[str, List[str]] = {
    "국무조정실·국무총리보좌기관": [
        "국무총리보좌기관인사관리지침",
        "국무총리보좌기관 인사관리지침",
        "국무조정실 인사관리",
        "국무총리비서실 인사관리",
    ],
    "채용·임용": ["국가공무원법 임용", "공무원임용령 신규채용", "공무원임용시험령 결격사유"],
    "전보·전직·파견": ["공무원임용령 전보", "공무원임용령 전직", "국가공무원법 파견", "국무총리보좌기관인사관리지침 전보"],
    "승진·보직": ["공무원임용령 승진", "공무원 성과평가 승진후보자", "보직관리 기준", "국무총리보좌기관인사관리지침 보직"],
    "휴직·복직": ["국가공무원법 휴직", "공무원임용령 휴직", "질병휴직 육아휴직 복직", "국무총리보좌기관인사관리지침 휴직 복직"],
    "복무·겸직": ["국가공무원 복무규정", "국가공무원법 겸직", "공무원 복무 징계", "국무총리보좌기관인사관리지침 복무"],
    "보수·수당": ["공무원 보수규정", "공무원수당 등에 관한 규정", "성과상여금 지급기준"],
    "징계·소청": ["공무원 징계령", "공무원 징계령 시행규칙", "국가공무원법 징계 소청", "국무총리보좌기관인사관리지침 징계"],
    "교육훈련·성과평가": ["공무원 인재개발법", "공무원 성과평가 등에 관한 규정", "근무성적평정"],
}


class SearchRequest(BaseModel):
    query: str = Field(..., description="검색어. 예: 국가공무원법 휴직, 공무원임용령 전보")
    page: int = Field(1, ge=1, description="페이지 번호")
    page_size: int = Field(10, ge=1, le=50, description="페이지당 결과 수")


class MultiSearchRequest(BaseModel):
    queries: List[str] = Field(..., min_length=1, max_length=10, description="검색어 목록")
    page: int = Field(1, ge=1, description="페이지 번호")
    page_size: int = Field(5, ge=1, le=20, description="검색어별 결과 수")


class LawDetailRequest(BaseModel):
    law_id: str = Field(..., description="법령 검색 결과의 법령ID")


class AdminRuleDetailRequest(BaseModel):
    admrul_id: str = Field(..., description="행정규칙 검색 결과의 행정규칙ID")


class PrecedentSearchRequest(BaseModel):
    query: str = Field(..., description="판례 검색어")
    page: int = Field(1, ge=1, description="페이지 번호")
    page_size: int = Field(10, ge=1, le=50, description="페이지당 결과 수")
    court: Optional[str] = Field(None, description="법원명 필터. 예: 대법원")


class PrecedentDetailRequest(BaseModel):
    precedent_id: str = Field(..., description="판례 검색 결과의 판례일련번호")


class IssueKeywordRequest(BaseModel):
    issue_text: str = Field(..., description="사용자가 제시한 국가공무원 인사 사안 또는 쟁점")


class IssueKeywordResponse(BaseModel):
    core_keywords: List[str]
    issue_keywords: Dict[str, List[str]]
    recommended_queries: List[str]
    note: str


class MpmCatalogRequest(BaseModel):
    categories: Optional[List[str]] = Field(
        None,
        description=(
            "선택 카테고리. 예: law, presidential_decree, prime_minister_rule, "
            "presidential_directive, prime_minister_directive, mpm_directive, "
            "mpm_established_rule, mpm_notice"
        ),
    )
    force_refresh: bool = Field(False, description="인사혁신처 목록 캐시를 무시하고 새로 수집할지 여부")


class MpmCatalogSearchRequest(BaseModel):
    query: str = Field(..., description="인사혁신처 법령정보 목록에서 검색할 키워드")
    categories: Optional[List[str]] = Field(None, description="선택 카테고리 목록")


def _arguments() -> Dict[str, Any]:
    """기존 tools.py와 호환되는 arguments 구조를 만든다."""
    env: Dict[str, str] = {}
    if os.getenv("LAW_API_KEY"):
        env["LAW_API_KEY"] = os.getenv("LAW_API_KEY", "")
    if os.getenv("LAW_API_URL"):
        env["LAW_API_URL"] = os.getenv("LAW_API_URL", "")
    return {"env": env} if env else {}


async def _to_thread(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "National Civil Service HR GPT API",
        "law_api_key": "configured" if os.getenv("LAW_API_KEY") else "missing",
        "mpm_catalog": "enabled",
        "administrative_rule_detail": "enabled",
    }


@app.get("/hr/core-keywords")
async def get_core_keywords() -> Dict[str, Any]:
    """국가공무원 인사 검토에 자주 쓰는 기본 법령·쟁점 키워드를 반환한다."""
    return {
        "core_keywords": HR_CORE_KEYWORDS,
        "issue_keywords": HR_ISSUE_KEYWORDS,
    }


@app.post("/hr/mpm-catalog")
async def get_mpm_catalog(req: MpmCatalogRequest) -> Dict[str, Any]:
    """인사혁신처 법령정보 페이지의 법률·대통령령·총리령·훈령·예규·고시 목록을 수집한다."""
    return await _to_thread(fetch_mpm_catalog, req.categories, req.force_refresh)


@app.post("/hr/search-mpm-catalog")
async def search_mpm_catalog_endpoint(req: MpmCatalogSearchRequest) -> Dict[str, Any]:
    """인사혁신처 법령정보 목록에서 법령·행정규칙 제목을 검색한다."""
    return await _to_thread(search_mpm_catalog, req.query, req.categories)


@app.post("/hr/suggest-keywords", response_model=IssueKeywordResponse)
async def suggest_keywords(req: IssueKeywordRequest) -> IssueKeywordResponse:
    """사안 문구를 바탕으로 우선 검색할 국가공무원 인사 키워드 후보를 추천한다."""
    text = req.issue_text
    recommended: List[str] = []
    for issue, keywords in HR_ISSUE_KEYWORDS.items():
        if any(token in text for token in issue.replace("·", " ").split()):
            recommended.extend(keywords)

    for term, keywords in HR_ISSUE_KEYWORDS.items():
        if any(k in text for k in term.split("·")):
            recommended.extend(keywords)

    if not recommended:
        recommended = [
            "국무총리보좌기관인사관리지침 " + text[:20],
            "국가공무원법 " + text[:20],
            "공무원임용령 " + text[:20],
            "국가공무원 복무규정 " + text[:20],
            "공무원 징계령 " + text[:20],
        ]

    seen = set()
    unique = []
    for item in recommended:
        if item not in seen:
            seen.add(item)
            unique.append(item)

    return IssueKeywordResponse(
        core_keywords=HR_CORE_KEYWORDS,
        issue_keywords=HR_ISSUE_KEYWORDS,
        recommended_queries=unique[:10],
        note="추천 키워드는 검색 보조용이다. 최종 판단은 인사혁신처 목록 및 실제 법령·행정규칙 원문 조회 결과로 검증해야 한다.",
    )


@app.post("/hr/search-laws")
async def search_laws(req: SearchRequest) -> Dict[str, Any]:
    """국가공무원 인사 관련 법령을 검색한다."""
    return await _to_thread(search_law, req.query, req.page, req.page_size, _arguments())


@app.post("/hr/search-laws-batch")
async def search_laws_batch(req: MultiSearchRequest) -> Dict[str, Any]:
    """여러 법령 검색어를 일괄 검색한다."""
    results = []
    for query in req.queries:
        result = await _to_thread(search_law, query, req.page, req.page_size, _arguments())
        results.append({"query": query, "result": result})
    return {"results": results}


@app.post("/hr/get-law-detail")
async def get_law(req: LawDetailRequest) -> Dict[str, Any]:
    """법령ID로 법령 상세 및 조문을 조회한다."""
    return await _to_thread(get_law_detail, req.law_id, _arguments())


@app.post("/hr/search-admin-rules")
async def search_admin_rules(req: SearchRequest) -> Dict[str, Any]:
    """국가공무원 인사 관련 행정규칙·예규·지침을 검색한다."""
    return await _to_thread(search_administrative_rule, req.query, req.page, req.page_size, _arguments())


@app.post("/hr/search-admin-rules-batch")
async def search_admin_rules_batch(req: MultiSearchRequest) -> Dict[str, Any]:
    """여러 행정규칙 검색어를 일괄 검색한다."""
    results = []
    for query in req.queries:
        result = await _to_thread(search_administrative_rule, query, req.page, req.page_size, _arguments())
        results.append({"query": query, "result": result})
    return {"results": results}


@app.post("/hr/get-admin-rule-detail")
async def get_admin_rule(req: AdminRuleDetailRequest) -> Dict[str, Any]:
    """행정규칙ID로 행정규칙 본문 및 상세 정보를 조회한다."""
    return await _to_thread(get_administrative_rule_detail, req.admrul_id, _arguments())


@app.post("/hr/search-precedents")
async def search_precedents(req: PrecedentSearchRequest) -> Dict[str, Any]:
    """국가공무원 인사 관련 판례를 검색한다."""
    return await _to_thread(search_precedent, req.query, req.page, req.page_size, req.court, _arguments())


@app.post("/hr/get-precedent-detail")
async def get_precedent(req: PrecedentDetailRequest) -> Dict[str, Any]:
    """판례일련번호로 판례 상세를 조회한다."""
    return await _to_thread(get_precedent_detail, req.precedent_id, _arguments())

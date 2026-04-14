# tax_law_agent.py
"""
세법 연구 에이전트
처분개요 HWPX 파일을 분석하여 처분 당시 적용 대상 연혁법령에서
관련 세법 조문을 자동으로 찾아 정리합니다.

워크플로우:
1. HWPX 파일 파싱 → 텍스트 추출
2. 처분개요 분석 → 세목, 처분일자, 법조문 인용 등 추출
3. 연혁법령 검색 → 처분 당시 시행 중이던 법령 버전 식별
4. 관련 조문 조회 → 해당 법령에서 관련 조문 전문 조회
5. 결과 정리 → 구조화된 보고서 생성
"""
import logging
import os
from typing import Dict, List, Optional
from .hwpx_parser import parse_hwpx_from_path, parse_hwpx_from_bytes
from .disposition_analyzer import analyze_disposition
from .historical_law_search import (
    search_historical_law,
    get_historical_law_detail,
    get_specific_articles,
)

logger = logging.getLogger("law-mcp")


def research_tax_law_from_file(
    file_path: str,
    arguments: Optional[dict] = None,
) -> Dict:
    """
    HWPX 파일에서 처분개요를 읽고, 관련 세법 조문을 자동으로 찾아 정리합니다.

    Args:
        file_path: HWPX 파일의 절대 경로
        arguments: 추가 인자 (API 키 등)

    Returns:
        분석 결과 딕셔너리 (처분개요 분석, 관련 법령, 조문 전문 포함)
    """
    # 상대경로를 절대경로로 변환
    file_path = os.path.abspath(file_path)
    logger.info("세법 연구 에이전트 시작 | file=%s", file_path)

    # Step 1: HWPX 파일 파싱
    parsed = parse_hwpx_from_path(file_path)
    if "error" in parsed:
        return {
            "단계": "HWPX 파싱",
            "error": parsed["error"],
        }

    text = parsed.get("text", "")
    if not text.strip():
        return {
            "단계": "HWPX 파싱",
            "error": "파일에서 텍스트를 추출할 수 없습니다.",
        }

    # Step 2~5: 텍스트 기반 분석 수행
    return research_tax_law_from_text(text, arguments)


def research_tax_law_from_text(
    text: str,
    arguments: Optional[dict] = None,
) -> Dict:
    """
    처분개요 텍스트를 분석하여 관련 세법 조문을 찾아 정리합니다.

    Args:
        text: 처분개요 텍스트
        arguments: 추가 인자 (API 키 등)

    Returns:
        분석 결과 딕셔너리
    """
    logger.info("세법 연구 에이전트 (텍스트) 시작 | text_length=%d", len(text))

    # Step 2: 처분개요 분석
    analysis = analyze_disposition(text)
    if "error" in analysis:
        return {
            "단계": "처분개요 분석",
            "error": analysis["error"],
        }

    disposition_date = analysis.get("disposition_date")
    related_laws = analysis.get("related_laws", [])
    law_references = analysis.get("law_references", [])
    tax_types = analysis.get("tax_types", [])

    if not disposition_date:
        logger.warning("처분일자를 추출할 수 없습니다. 법조문 인용 정보만으로 검색합니다.")

    if not related_laws and not law_references:
        return {
            "처분개요_분석": analysis,
            "warning": "관련 법령을 특정할 수 없습니다. 처분개요에 세목이나 법조문 인용이 포함되어 있는지 확인해주세요.",
            "법령조회결과": [],
        }

    # Step 3 & 4: 각 관련 법령에 대해 연혁법령 검색 및 조문 조회
    law_results = []

    for law_name in related_laws:
        law_result = _search_and_fetch_law(
            law_name=law_name,
            effective_date=disposition_date,
            law_references=law_references,
            arguments=arguments,
        )
        law_results.append(law_result)

    # Step 5: 결과 정리
    report = {
        "처분개요_분석": {
            "세목": tax_types,
            "처분일자": disposition_date,
            "과세기간": analysis.get("tax_period"),
            "처분유형": analysis.get("disposition_type", []),
            "세액": analysis.get("tax_amount"),
            "주요키워드": analysis.get("keywords", []),
            "법조문_인용수": len(law_references),
            "법조문_인용": law_references,
        },
        "관련법령수": len(related_laws),
        "관련법령목록": related_laws,
        "법령조회결과": law_results,
        "요약": _generate_summary(analysis, law_results),
    }

    logger.info(
        "세법 연구 에이전트 완료 | tax_types=%s laws_found=%d",
        tax_types,
        len([r for r in law_results if "error" not in r]),
    )

    return report


def _search_and_fetch_law(
    law_name: str,
    effective_date: Optional[str],
    law_references: List[Dict],
    arguments: Optional[dict] = None,
) -> Dict:
    """
    단일 법령에 대해 연혁법령 검색 및 조문 조회를 수행합니다.
    """
    result = {
        "법령명": law_name,
        "기준일자": effective_date,
    }

    # 연혁법령 검색
    if effective_date:
        search_result = search_historical_law(law_name, effective_date, arguments)
    else:
        # 처분일자가 없는 경우 현행법령 검색
        from .tools import search_law
        search_result = search_law(law_name, page=1, page_size=5, arguments=arguments)
        if "error" not in search_result:
            laws = search_result.get("laws", [])
            if laws:
                search_result["적용법령"] = laws[0]

    if "error" in search_result:
        result["error"] = search_result["error"]
        return result

    applicable = search_result.get("적용법령")
    if not applicable:
        result["warning"] = "해당 시점에 유효한 법령 버전을 찾을 수 없습니다."
        result["검색결과"] = search_result.get("검색결과", [])
        return result

    result["적용법령"] = {
        "법령ID": applicable.get("법령ID", ""),
        "법령명": applicable.get("법령명", ""),
        "시행일자": applicable.get("시행일자", ""),
        "공포일자": applicable.get("공포일자", ""),
        "제개정구분": applicable.get("제개정구분", ""),
    }

    law_id = applicable.get("법령ID", "")
    if not law_id:
        result["warning"] = "법령 ID를 찾을 수 없어 조문 조회가 불가합니다."
        return result

    # 관련 조문번호 추출
    article_numbers = _extract_article_numbers_for_law(law_name, law_references)

    if article_numbers:
        # 특정 조문만 조회
        articles_result = get_specific_articles(law_id, article_numbers, arguments)
        if "error" not in articles_result:
            result["조회방식"] = "특정조문"
            result["조문"] = articles_result.get("조문", [])
            result["조문수"] = articles_result.get("매칭건수", 0)
        else:
            result["error"] = articles_result["error"]
    else:
        # 전체 법령 조회 (조문번호 특정 불가 시)
        detail = get_historical_law_detail(law_id, arguments)
        if "error" not in detail:
            result["조회방식"] = "전체조문"
            result["조문"] = detail.get("조문", [])
            result["조문수"] = detail.get("조문수", 0)
        else:
            result["error"] = detail["error"]

    return result


def _extract_article_numbers_for_law(
    law_name: str,
    law_references: List[Dict],
) -> List[str]:
    """
    법령명에 해당하는 조문번호를 law_references에서 추출합니다.
    """
    import re

    numbers = set()
    normalized_name = re.sub(r"\s+", "", law_name)

    for ref in law_references:
        ref_law = re.sub(r"\s+", "", ref.get("법령명", ""))

        # 정확한 법령명 매칭
        if ref_law == normalized_name:
            detail = ref.get("조문상세", {})
            if "조" in detail:
                article_num = detail["조"]
                if "조의" in detail:
                    article_num += f"의{detail['조의']}"
                numbers.add(detail["조"])

        # "같은 법" 등의 참조는 별도 처리가 필요하나,
        # 여기서는 명시적 법령명 매칭만 수행

    return sorted(numbers)


def _generate_summary(analysis: Dict, law_results: List[Dict]) -> str:
    """분석 결과 요약을 생성합니다."""
    parts = []

    # 처분 개요
    tax_types = analysis.get("tax_types", [])
    disposition_date = analysis.get("disposition_date")
    tax_period = analysis.get("tax_period")

    if tax_types:
        parts.append(f"세목: {', '.join(tax_types)}")
    if disposition_date:
        formatted_date = f"{disposition_date[:4]}.{disposition_date[4:6]}.{disposition_date[6:]}"
        parts.append(f"처분일자: {formatted_date}")
    if tax_period:
        parts.append(f"과세기간: {tax_period}년")

    # 법령 조회 결과
    success_count = sum(1 for r in law_results if "error" not in r and r.get("조문"))
    total_articles = sum(r.get("조문수", 0) for r in law_results if "error" not in r)

    parts.append(f"조회된 법령: {success_count}건")
    parts.append(f"조회된 조문: {total_articles}건")

    # 오류가 있는 법령
    error_laws = [r["법령명"] for r in law_results if "error" in r]
    if error_laws:
        parts.append(f"조회 실패: {', '.join(error_laws)}")

    return " | ".join(parts)

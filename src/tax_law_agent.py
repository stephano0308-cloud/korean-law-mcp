# tax_law_agent.py
"""
세법 연구 에이전트
처분개요 HWPX 파일을 분석하여 처분 당시 적용 대상 연혁법령에서
인용된 세법 조문을 구체적으로 찾아 정리합니다.

출력 형식:
- 처분개요 요약 (세목, 처분일자, 세액)
- 적용법조문 목록 (각 인용 조항별로 법령명, 조문번호, 조문제목, 조문내용,
  해당 항/호/목 내용을 구체적으로 열거)
"""
import logging
import os
import re
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
    HWPX 파일에서 처분개요를 읽고, 인용된 세법 조문을 구체적으로 찾아 정리합니다.
    """
    file_path = os.path.abspath(file_path)
    logger.info("세법 연구 에이전트 시작 | file=%s", file_path)

    parsed = parse_hwpx_from_path(file_path)
    if "error" in parsed:
        return {"단계": "HWPX 파싱", "error": parsed["error"]}

    text = parsed.get("text", "")
    if not text.strip():
        return {"단계": "HWPX 파싱", "error": "파일에서 텍스트를 추출할 수 없습니다."}

    return research_tax_law_from_text(text, arguments)


def research_tax_law_from_text(
    text: str,
    arguments: Optional[dict] = None,
) -> Dict:
    """
    처분개요 텍스트를 분석하여 인용된 세법 조문을 구체적으로 찾아 정리합니다.
    """
    logger.info("세법 연구 에이전트 (텍스트) 시작 | text_length=%d", len(text))

    # Step 1: 처분개요 분석
    analysis = analyze_disposition(text)
    if "error" in analysis:
        return {"단계": "처분개요 분석", "error": analysis["error"]}

    disposition_date = analysis.get("disposition_date")
    law_references = analysis.get("law_references", [])
    related_laws = analysis.get("related_laws", [])
    tax_types = analysis.get("tax_types", [])

    if not law_references:
        return {
            "처분개요": _format_disposition_summary(analysis),
            "warning": "처분개요에서 법조문 인용을 찾을 수 없습니다.",
            "적용법조문": [],
        }

    # Step 2: 법령별로 인용된 조문번호를 그룹화
    law_article_map = _group_references_by_law(law_references)

    # Step 3: 각 법령에 대해 연혁법령 검색 및 해당 조문 조회
    applicable_provisions = []
    law_cache = {}  # 법령ID → 법령상세 (중복 API 호출 방지)

    for law_name in related_laws:
        refs_for_law = law_article_map.get(law_name, [])
        if not refs_for_law:
            continue

        article_numbers = list({r["조문상세"]["조"] for r in refs_for_law if "조" in r.get("조문상세", {})})
        if not article_numbers:
            continue

        # 연혁법령 검색 (처분일 기준)
        law_info = _get_applicable_law(law_name, disposition_date, arguments)
        if not law_info:
            for ref in refs_for_law:
                applicable_provisions.append({
                    "법령명": law_name,
                    "인용조문": ref["조문"],
                    "error": f"처분일({disposition_date}) 기준 '{law_name}' 연혁법령을 찾을 수 없습니다.",
                })
            continue

        law_id = law_info.get("법령ID", "")
        enforcement_date = law_info.get("시행일자", "")

        # 조문 상세 조회 (캐시 사용)
        if law_id not in law_cache:
            articles_result = get_specific_articles(law_id, article_numbers, arguments)
            if "error" in articles_result:
                for ref in refs_for_law:
                    applicable_provisions.append({
                        "법령명": law_name,
                        "인용조문": ref["조문"],
                        "시행일자": enforcement_date,
                        "error": articles_result["error"],
                    })
                continue
            law_cache[law_id] = articles_result.get("조문", [])

        fetched_articles = law_cache[law_id]

        # 각 인용 조문에 대해 구체적 조항 매칭
        for ref in refs_for_law:
            provision = _match_provision(ref, fetched_articles, law_name, enforcement_date, law_info)
            applicable_provisions.append(provision)

    # Step 4: 결과 정리
    report = {
        "처분개요": _format_disposition_summary(analysis),
        "적용법조문_수": len(applicable_provisions),
        "적용법조문": applicable_provisions,
    }

    success_count = sum(1 for p in applicable_provisions if "error" not in p)
    logger.info(
        "세법 연구 에이전트 완료 | tax_types=%s provisions=%d/%d",
        tax_types, success_count, len(applicable_provisions),
    )

    return report


def _format_disposition_summary(analysis: Dict) -> Dict:
    """처분개요 핵심 정보를 정리합니다."""
    date = analysis.get("disposition_date")
    formatted_date = None
    if date and len(date) == 8:
        formatted_date = f"{date[:4]}.{date[4:6]}.{date[6:]}"

    return {
        "세목": analysis.get("tax_types", []),
        "처분일자": formatted_date or date,
        "과세기간": analysis.get("tax_period"),
        "처분유형": analysis.get("disposition_type", []),
        "세액": analysis.get("tax_amount"),
        "인용조문수": len(analysis.get("law_references", [])),
        "인용목록": [
            f"{ref['법령명']} {ref['조문']}" for ref in analysis.get("law_references", [])
        ],
    }


def _group_references_by_law(law_references: List[Dict]) -> Dict[str, List[Dict]]:
    """법령명별로 인용 조문을 그룹화합니다."""
    groups = {}
    for ref in law_references:
        law_name = ref.get("법령명", "")
        if not law_name:
            continue
        groups.setdefault(law_name, []).append(ref)
    return groups


def _get_applicable_law(
    law_name: str,
    effective_date: Optional[str],
    arguments: Optional[dict] = None,
) -> Optional[Dict]:
    """처분일 기준 적용 법령을 찾습니다."""
    if effective_date:
        search_result = search_historical_law(law_name, effective_date, arguments)
    else:
        from .tools import search_law
        search_result = search_law(law_name, page=1, page_size=5, arguments=arguments)
        if "error" not in search_result:
            laws = search_result.get("laws", [])
            if laws:
                search_result["적용법령"] = laws[0]

    if "error" in search_result:
        logger.warning("법령 검색 실패: %s - %s", law_name, search_result["error"])
        return None

    return search_result.get("적용법령")


def _match_provision(
    ref: Dict,
    fetched_articles: List[Dict],
    law_name: str,
    enforcement_date: str,
    law_info: Dict,
) -> Dict:
    """
    인용 조문(ref)에 대해 실제 조문 내용을 매칭하여 구체적 조항 정보를 반환합니다.
    제X조 제X항 제X호 수준까지 구체적으로 열거합니다.
    """
    detail = ref.get("조문상세", {})
    target_jo = detail.get("조", "")
    target_jo_of = detail.get("조의", "")
    target_hang = detail.get("항", "")
    target_ho = detail.get("호", "")
    target_mok = detail.get("목", "")

    provision = {
        "법령명": law_name,
        "인용조문": ref["조문"],
        "시행일자": enforcement_date,
        "제개정구분": law_info.get("제개정구분", ""),
    }

    # 조문번호로 매칭
    matched_article = None
    for article in fetched_articles:
        article_num = article.get("조문번호", "")
        num_match = re.search(r"(\d+)", article_num)
        if not num_match:
            continue
        jo_num = num_match.group(1)

        if jo_num == target_jo:
            # "조의" 처리 (예: 제26조의2)
            if target_jo_of:
                if f"의{target_jo_of}" in article_num or f"의 {target_jo_of}" in article_num:
                    matched_article = article
                    break
            else:
                # "조의"가 없는 인용인데 조문번호에 "의"가 있으면 스킵
                if "의" not in article_num.replace(f"제{jo_num}조", ""):
                    matched_article = article
                    break

    if not matched_article:
        provision["warning"] = f"조문을 찾을 수 없습니다: {ref['조문']}"
        return provision

    provision["조문번호"] = matched_article.get("조문번호", "")
    provision["조문제목"] = matched_article.get("조문제목", "")

    # 구체적 항/호/목 추출
    if target_hang or target_ho or target_mok:
        provision["조문내용_전체"] = matched_article.get("조문내용", "")
        specific = _extract_specific_clause(matched_article, target_hang, target_ho, target_mok)
        provision["적용조항"] = specific
    else:
        # 조 전체가 인용된 경우
        provision["조문내용"] = matched_article.get("조문내용", "")
        # 항 목록도 포함
        items = matched_article.get("항목록", [])
        if items:
            provision["항목록"] = items

    return provision


def _extract_specific_clause(
    article: Dict,
    target_hang: str,
    target_ho: str,
    target_mok: str,
) -> Dict:
    """
    조문에서 구체적인 항/호/목을 추출합니다.
    """
    result = {}

    items = article.get("항목록", [])

    if target_hang:
        # 해당 항 찾기
        matched_hang = None
        for item in items:
            hang_num = item.get("항번호", "")
            num_match = re.search(r"(\d+)", hang_num)
            if num_match and num_match.group(1) == target_hang:
                matched_hang = item
                break

        if matched_hang:
            result["항번호"] = matched_hang.get("항번호", "")
            result["항내용"] = matched_hang.get("항내용", "")

            if target_ho:
                # 해당 호 찾기
                sub_items = matched_hang.get("호목록", [])
                matched_ho = None
                for sub in sub_items:
                    ho_num = sub.get("호번호", "")
                    num_match = re.search(r"(\d+)", ho_num)
                    if num_match and num_match.group(1) == target_ho:
                        matched_ho = sub
                        break

                if matched_ho:
                    result["호번호"] = matched_ho.get("호번호", "")
                    result["호내용"] = matched_ho.get("호내용", "")

                    if target_mok:
                        result["목"] = target_mok
                else:
                    result["호_warning"] = f"제{target_ho}호를 찾을 수 없습니다."
        else:
            result["항_warning"] = f"제{target_hang}항을 찾을 수 없습니다."
    elif not target_hang and target_ho:
        # 항 없이 호만 인용된 경우 (단일항 조문)
        for item in items:
            sub_items = item.get("호목록", [])
            for sub in sub_items:
                ho_num = sub.get("호번호", "")
                num_match = re.search(r"(\d+)", ho_num)
                if num_match and num_match.group(1) == target_ho:
                    result["호번호"] = sub.get("호번호", "")
                    result["호내용"] = sub.get("호내용", "")
                    break
            if result:
                break

    return result

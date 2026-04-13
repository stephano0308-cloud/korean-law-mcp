# historical_law_search.py
"""
연혁법령 검색 모듈
국가법령정보센터 API를 활용하여 특정 시점에 시행 중이던 법령 버전을 찾고,
관련 조문을 조회합니다.
"""
import logging
import re
import requests
from typing import Dict, List, Optional
from .tools import (
    get_credentials,
    make_request_with_retry,
    parse_xml_response,
    VERIFY,
    DEFAULT_LAW_API_URL,
)

logger = logging.getLogger("law-mcp")


def search_historical_law(
    law_name: str,
    effective_date: str,
    arguments: Optional[dict] = None,
) -> Dict:
    """
    특정 시점에 시행 중이던 법령을 검색합니다.

    국가법령정보센터 API의 lawSearch.do 엔드포인트에 efYd(시행일자) 파라미터를
    사용하여 해당 날짜에 유효했던 법령 버전을 찾습니다.

    Args:
        law_name: 법령명 (예: "소득세법", "법인세법 시행령")
        effective_date: 시행일자 기준일 (YYYYMMDD 형식)
        arguments: 추가 인자 (API 키 등)

    Returns:
        검색 결과 딕셔너리
    """
    logger.debug(
        "search_historical_law | law_name=%r effective_date=%s",
        law_name,
        effective_date,
    )

    credentials = get_credentials(arguments)
    api_key = credentials["LAW_API_KEY"]
    base_url = credentials.get("LAW_API_URL", DEFAULT_LAW_API_URL)

    if not api_key:
        return {"error": "API 키가 설정되지 않았습니다. LAW_API_KEY 환경 변수를 설정해주세요."}

    # 날짜 형식 검증
    if not re.match(r"^\d{8}$", effective_date):
        return {"error": f"날짜 형식이 올바르지 않습니다. YYYYMMDD 형식이어야 합니다: {effective_date}"}

    api_url = f"{base_url}/lawSearch.do"

    params = {
        "OC": api_key,
        "target": "law",
        "type": "XML",
        "query": law_name,
        "display": 20,
        "page": 1,
        "efYd": effective_date,  # 시행일자 기준 필터
        "sort": "efYd",          # 시행일자 기준 정렬
    }

    try:
        response = make_request_with_retry(api_url, params, max_retries=3, timeout=30)

        root = parse_xml_response(response.text)
        if root is None:
            return {"error": "API 응답 파싱 실패"}

        laws = []
        for law in root.findall(".//law"):
            law_data = {
                "법령ID": law.findtext("법령ID", ""),
                "법령명": law.findtext("법령명한글", ""),
                "법령약칭": law.findtext("법령약칭명", ""),
                "법령구분": law.findtext("법령구분명", ""),
                "소관부처": law.findtext("소관부처명", ""),
                "공포일자": law.findtext("공포일자", ""),
                "공포번호": law.findtext("공포번호", ""),
                "시행일자": law.findtext("시행일자", ""),
                "제개정구분": law.findtext("제개정구분명", ""),
            }
            laws.append(law_data)

        total_count = root.findtext(".//totalCnt", "0")

        # 정확한 법령명과 매칭되는 것을 우선 선택
        exact_matches = _find_exact_matches(laws, law_name)

        # 시행일자 기준으로 해당 날짜에 유효했던 법령 찾기
        applicable_law = _find_applicable_version(
            exact_matches if exact_matches else laws,
            effective_date,
        )

        result = {
            "검색법령명": law_name,
            "기준일자": effective_date,
            "총검색건수": int(total_count),
            "검색결과": laws,
            "정확매칭": exact_matches,
            "적용법령": applicable_law,
        }

        logger.debug(
            "Historical law search | total=%s exact=%d applicable=%s",
            total_count,
            len(exact_matches),
            applicable_law.get("법령명") if applicable_law else "None",
        )
        return result

    except requests.exceptions.RequestException as e:
        logger.exception("Historical law search API failed: %s", str(e))
        return {"error": f"API 요청 실패: {str(e)}"}
    except Exception as e:
        logger.exception("Historical law search error: %s", str(e))
        return {"error": f"연혁법령 검색 오류: {str(e)}"}


def _find_exact_matches(laws: List[Dict], law_name: str) -> List[Dict]:
    """법령명이 정확히 일치하는 결과를 필터링합니다."""
    # 공백 및 특수문자 정규화
    normalized_name = re.sub(r"\s+", "", law_name)

    exact = []
    for law in laws:
        name = re.sub(r"\s+", "", law.get("법령명", ""))
        abbr = re.sub(r"\s+", "", law.get("법령약칭", ""))
        if name == normalized_name or abbr == normalized_name:
            exact.append(law)

    return exact


def _find_applicable_version(laws: List[Dict], effective_date: str) -> Optional[Dict]:
    """
    주어진 날짜에 유효했던 법령 버전을 찾습니다.
    시행일자 <= 기준일자 인 것 중 가장 최근 시행된 버전을 선택합니다.
    """
    if not laws:
        return None

    candidates = []
    for law in laws:
        enf_date = law.get("시행일자", "")
        if enf_date and enf_date <= effective_date:
            candidates.append(law)

    if not candidates:
        # 시행일자가 모두 기준일 이후인 경우, 가장 가까운 것 반환
        sorted_laws = sorted(laws, key=lambda x: x.get("시행일자", "99999999"))
        return sorted_laws[0] if sorted_laws else None

    # 시행일자가 가장 최근인 것 선택
    candidates.sort(key=lambda x: x.get("시행일자", ""), reverse=True)
    return candidates[0]


def get_historical_law_detail(law_id: str, arguments: Optional[dict] = None) -> Dict:
    """
    특정 법령 버전의 상세 정보(전문 + 조문)를 조회합니다.

    Args:
        law_id: 법령 ID (법령일련번호/MST)
        arguments: 추가 인자

    Returns:
        법령 상세 정보 딕셔너리
    """
    logger.debug("get_historical_law_detail | law_id=%s", law_id)

    credentials = get_credentials(arguments)
    api_key = credentials["LAW_API_KEY"]
    base_url = credentials.get("LAW_API_URL", DEFAULT_LAW_API_URL)

    if not api_key:
        return {"error": "API 키가 설정되지 않았습니다."}

    api_url = f"{base_url}/lawService.do"

    params = {
        "OC": api_key,
        "target": "law",
        "type": "XML",
        "MST": law_id,
    }

    try:
        response = make_request_with_retry(api_url, params, max_retries=3, timeout=30)

        root = parse_xml_response(response.text)
        if root is None:
            return {"error": "응답 파싱 실패"}

        # 기본 정보
        law_info = {
            "법령ID": root.findtext(".//법령ID", ""),
            "법령명": root.findtext(".//법령명한글", ""),
            "법령구분": root.findtext(".//법령구분명", ""),
            "소관부처": root.findtext(".//소관부처명", ""),
            "공포일자": root.findtext(".//공포일자", ""),
            "공포번호": root.findtext(".//공포번호", ""),
            "시행일자": root.findtext(".//시행일자", ""),
            "제개정구분": root.findtext(".//제개정구분명", ""),
        }

        # 전체 조문 추출
        articles = []
        for article in root.findall(".//조문"):
            article_data = {
                "조문번호": article.findtext("조문번호", ""),
                "조문제목": article.findtext("조문제목", ""),
                "조문내용": article.findtext("조문내용", ""),
            }

            # 항 정보 추출
            items = []
            for item in article.findall(".//항"):
                item_data = {
                    "항번호": item.findtext("항번호", ""),
                    "항내용": item.findtext("항내용", ""),
                }
                # 호 정보 추출
                sub_items = []
                for sub in item.findall(".//호"):
                    sub_data = {
                        "호번호": sub.findtext("호번호", ""),
                        "호내용": sub.findtext("호내용", ""),
                    }
                    sub_items.append(sub_data)
                if sub_items:
                    item_data["호목록"] = sub_items
                items.append(item_data)

            if items:
                article_data["항목록"] = items

            articles.append(article_data)

        law_info["조문"] = articles
        law_info["조문수"] = len(articles)

        # 부칙 추출
        addenda = []
        for addendum in root.findall(".//부칙"):
            addendum_data = {
                "부칙번호": addendum.findtext("부칙번호", ""),
                "부칙내용": addendum.findtext("부칙내용", ""),
            }
            addenda.append(addendum_data)

        if addenda:
            law_info["부칙"] = addenda

        logger.debug(
            "Historical law detail | law_id=%s name=%s articles=%d",
            law_id,
            law_info.get("법령명"),
            len(articles),
        )
        return law_info

    except requests.exceptions.RequestException as e:
        logger.exception("Historical law detail API failed: %s", str(e))
        return {"error": f"API 요청 실패: {str(e)}"}
    except Exception as e:
        logger.exception("Historical law detail error: %s", str(e))
        return {"error": f"법령 상세 조회 오류: {str(e)}"}


def get_specific_articles(
    law_id: str,
    article_numbers: List[str],
    arguments: Optional[dict] = None,
) -> Dict:
    """
    특정 법령에서 지정된 조문만 추출합니다.

    Args:
        law_id: 법령 ID
        article_numbers: 조문번호 목록 (예: ["94", "95", "96"])
        arguments: 추가 인자

    Returns:
        추출된 조문 딕셔너리
    """
    # 전체 법령 조회
    law_detail = get_historical_law_detail(law_id, arguments)
    if "error" in law_detail:
        return law_detail

    # 지정된 조문 필터링
    all_articles = law_detail.get("조문", [])
    matched = []

    for article in all_articles:
        article_num = article.get("조문번호", "")
        # 조문번호에서 숫자 추출 (예: "제94조" -> "94")
        num_match = re.search(r"(\d+)", article_num)
        if num_match and num_match.group(1) in article_numbers:
            matched.append(article)

    return {
        "법령명": law_detail.get("법령명", ""),
        "법령ID": law_detail.get("법령ID", ""),
        "시행일자": law_detail.get("시행일자", ""),
        "공포일자": law_detail.get("공포일자", ""),
        "제개정구분": law_detail.get("제개정구분", ""),
        "요청조문": article_numbers,
        "조문": matched,
        "매칭건수": len(matched),
        "전체조문수": len(all_articles),
    }

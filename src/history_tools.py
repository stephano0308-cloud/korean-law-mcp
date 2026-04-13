from typing import Dict, List, Optional

from .tools import get_law_detail, search_law


class HistoryResolutionError(Exception):
    pass


def resolve_law_candidates(law_name: str, arguments: Optional[dict] = None) -> Dict:
    """
    법령명으로 공식 검색 결과 후보를 조회합니다.
    현재 저장소의 기존 search_law 구현을 재사용합니다.
    """
    response = search_law(law_name, page=1, page_size=20, arguments=arguments)
    candidates = response.get("laws", []) if isinstance(response, dict) else []
    return {
        "query": law_name,
        "count": len(candidates),
        "candidates": candidates,
    }


def resolve_current_law_detail(law_name: str, arguments: Optional[dict] = None) -> Dict:
    """
    현재 시점의 공식 법령 상세를 조회합니다.
    연혁버전 고정 조회가 아직 구현되지 않았으므로 현재 본문을 기준값으로 제공합니다.
    """
    candidates = resolve_law_candidates(law_name, arguments=arguments)
    if not candidates["candidates"]:
        raise HistoryResolutionError(f"법령 검색 결과 없음: {law_name}")
    selected = candidates["candidates"][0]
    law_id = selected.get("법령ID")
    detail = get_law_detail(law_id, arguments=arguments)
    return {
        "selected_law_id": law_id,
        "selected_law_name": detail.get("법령명") or law_name,
        "current_effective_date": detail.get("시행일자"),
        "detail": detail,
        "history_mode": "current-detail-fallback",
    }


def analyze_history_applicability(
    law_name: str,
    basis_dates: Optional[List[str]] = None,
    arguments: Optional[dict] = None,
) -> Dict:
    """
    연혁법령 분석 인터페이스.

    현재 단계에서는 공식 연혁버전 고정 조회가 미구현이므로,
    1) 현재 법령 상세를 조회하고
    2) 결과에 '연혁 직접확정 불가' 상태를 명시하며
    3) 후속 구현 시 이 함수만 교체할 수 있게 합니다.
    """
    basis_dates = basis_dates or []
    current = resolve_current_law_detail(law_name, arguments=arguments)
    return {
        "law_name": law_name,
        "basis_dates": basis_dates,
        "history_status": "연혁 직접확정 불가",
        "history_mode": current.get("history_mode"),
        "selected_law_id": current.get("selected_law_id"),
        "current_effective_date": current.get("current_effective_date"),
        "review_note": "현재 저장소에는 공식 연혁버전 특정 조회가 구현되지 않아 현행 상세 본문을 기준으로 검토했습니다. 처분 당시 적용본 확정은 후속 연혁 API 구현이 필요합니다.",
    }

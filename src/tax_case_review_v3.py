from typing import Dict, List, Optional

from .history_tools import analyze_history_applicability
from .tax_case_review_v2 import (
    derive_issue_for_reference,
    extract_addendum_analysis,
    extract_law_references,
    infer_issues,
    normalize_text,
    choose_basis_dates,
    extract_all_dates,
    extract_date_contexts,
    _find_article_text,
    _find_matching_law_id,
    SUGGESTED_LAWS,
)
from .tools import get_law_detail


def summarize_case_v3(text: str) -> Dict:
    normalized = normalize_text(text)
    all_dates = extract_all_dates(normalized)
    date_contexts = extract_date_contexts(normalized)
    issues = infer_issues(normalized)
    basis_dates = choose_basis_dates(issues, date_contexts, all_dates)
    refs = extract_law_references(normalized)
    return {
        "all_dates": all_dates,
        "date_contexts": date_contexts,
        "issues": issues,
        "basis_dates_by_issue": basis_dates,
        "law_references": refs,
        "history_note": "연혁 직접확정 모듈 인터페이스 포함",
    }


def build_revision_points(reviewed: List[Dict], additions: List[Dict]) -> List[str]:
    points: List[str] = []
    for item in reviewed:
        basis = ", ".join(item.get("basis_dates", [])) or "기준일 추가 확인 필요"
        history = item.get("history_analysis") or {}
        if item["status"] == "유지 가능":
            points.append(f"'{item['reference']}'는 공식 법령 검색 결과와 대체로 부합합니다. 다만 적용 기준일은 {basis} 기준으로 다시 대조하는 것이 안전합니다.")
        else:
            points.append(f"'{item['reference']}'는 {item['reason']} 적용 기준일({basis})과 함께 법령명·조문 번호를 재확인할 필요가 있습니다.")
        if history:
            points.append(f"연혁 검토 의견: {history.get('review_note')}")
        addendum = item.get("addendum_analysis") or {}
        if addendum.get("has_addendum"):
            points.append(f"부칙 검토 의견: {addendum.get('review_opinion')}")
    for addition in additions[:10]:
        points.append(f"누락 가능 조문으로 '{addition['suggestion']}'를 검토할 필요가 있습니다. 사유: {addition['reason']}")
    if not points:
        points.append("즉시 수정이 필요한 관련법령은 식별되지 않았습니다.")
    return points


def review_related_laws_v3(document_text: str, arguments: Optional[dict] = None) -> Dict:
    overview = summarize_case_v3(document_text)
    reviewed: List[Dict] = []
    mentioned_names = {ref["law_name"] for ref in overview["law_references"]}

    for ref in overview["law_references"]:
        issue = derive_issue_for_reference(ref, overview["issues"])
        basis_dates = overview["basis_dates_by_issue"].get(issue, [])
        history_analysis = analyze_history_applicability(ref["law_name"], basis_dates=basis_dates, arguments=arguments)
        law_id, candidates = _find_matching_law_id(ref["law_name"], arguments=arguments)
        if not law_id:
            reviewed.append({
                "reference": ref["display"],
                "issue": issue,
                "basis_dates": basis_dates,
                "status": "수정 필요",
                "reason": "공식 법령 검색 결과에서 동일 법령을 확인하지 못했습니다.",
                "official_candidates": candidates,
                "history_analysis": history_analysis,
            })
            continue
        law_detail = get_law_detail(law_id, arguments=arguments)
        article = _find_article_text(law_detail, ref.get("article"))
        addendum_analysis = extract_addendum_analysis(law_detail, basis_dates)
        if ref.get("article") and not article:
            status = "수정 필요"
            reason = "법령 본문은 확인되지만 기재된 조문 번호를 상세 본문에서 확인하지 못했습니다."
        else:
            status = "유지 가능"
            reason = "법령명은 공식 검색 결과와 일치하며, 기재 조문도 본문에서 확인되었습니다." if article else "법령명은 공식 검색 결과와 일치합니다."
        reviewed.append({
            "reference": ref["display"],
            "issue": issue,
            "basis_dates": basis_dates,
            "status": status,
            "reason": reason,
            "law_id": law_id,
            "law_name_official": law_detail.get("법령명") or ref["law_name"],
            "effective_date": law_detail.get("시행일자"),
            "article_title": article.get("조문제목") if article else None,
            "article_text": article.get("조문내용") if article else None,
            "addendum_analysis": addendum_analysis,
            "history_analysis": history_analysis,
        })

    additional_needed = []
    for issue in overview["issues"]:
        for suggestion in SUGGESTED_LAWS.get(issue, []):
            suggested_law_name = suggestion.split(" 제")[0]
            if suggested_law_name not in mentioned_names:
                additional_needed.append({
                    "issue": issue,
                    "basis_dates": overview["basis_dates_by_issue"].get(issue, []),
                    "suggestion": suggestion,
                    "reason": f"{issue} 쟁점과 직접 연결되는 조문 후보입니다.",
                    "history_analysis": analyze_history_applicability(suggested_law_name, basis_dates=overview['basis_dates_by_issue'].get(issue, []), arguments=arguments),
                })

    return {
        "overview": overview,
        "reviewed_laws": reviewed,
        "additional_suggestions": additional_needed,
        "draft_revision_points": build_revision_points(reviewed, additional_needed),
        "limitations": [
            "연혁법령 직접확정은 아직 인터페이스 단계입니다.",
            "현재는 현행 상세 본문 기반 fallback + 부칙 문구 검토 구조입니다.",
        ],
    }

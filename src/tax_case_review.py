import re
from typing import Dict, List, Optional, Tuple

from .tools import get_law_detail, search_law


LAW_NAME_PATTERN = re.compile(
    r"((?:국세기본법|법인세법|소득세법|부가가치세법|상속세 및 증여세법|조세특례제한법|관세법|지방세법|지방세기본법|종합부동산세법|상속세및증여세법)(?: 시행령| 시행규칙)?)"
    r"(?:\s*제\s*(\d+(?:의\d+)?)\s*조)?"
    r"(?:\s*제\s*(\d+)\s*항)?"
    r"(?:\s*제\s*(\d+)\s*호)?"
)

SECTION_HINTS = [
    "처분개요", "사실관계", "청구인 주장", "처분청 의견", "관련법령", "쟁점", "검토"
]

ISSUE_HINTS = {
    "경정청구 적법성": ["경정청구", "환급", "후발적", "감액경정"],
    "부당행위계산부인": ["부당행위", "특수관계", "시가", "저가", "고가"],
    "증여세 과세요건": ["증여", "저가양수", "고가양도", "명의신탁", "상장차익"],
    "양도소득세 필요경비": ["양도소득세", "필요경비", "증권거래세", "명도비"],
    "공시송달·불복절차": ["공시송달", "송달", "불복", "심판청구", "처분성"],
    "세금계산서·실질과세": ["세금계산서", "가공", "용역", "실물거래"],
}

SUGGESTED_LAWS = {
    "경정청구 적법성": ["국세기본법 제45조의2"],
    "부당행위계산부인": ["법인세법 제52조", "법인세법 시행령 제88조"],
    "증여세 과세요건": ["상속세 및 증여세법 제4조", "상속세 및 증여세법 제45조", "상속세 및 증여세법 제47조"],
    "양도소득세 필요경비": ["소득세법 제97조"],
    "공시송달·불복절차": ["국세기본법 제11조", "국세기본법 제55조"],
    "세금계산서·실질과세": ["부가가치세법 제32조"],
}


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sections(text: str) -> Dict[str, str]:
    lines = [line.strip() for line in normalize_text(text).split("\n")]
    sections: Dict[str, List[str]] = {}
    current = "본문"

    for line in lines:
        if not line:
            continue
        header = None
        for hint in SECTION_HINTS:
            if line.startswith(hint):
                header = hint
                break
        if header:
            current = header
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    return {key: "\n".join(values).strip() for key, values in sections.items() if values}


def extract_dates(text: str) -> List[str]:
    found = re.findall(r"(20\d{2}[.\-년]\s*\d{1,2}[.\-월]\s*\d{1,2}일?)", text)
    cleaned = []
    for item in found:
        normalized = re.sub(r"\s+", "", item).replace("년", ".").replace("월", ".").replace("일", "")
        normalized = normalized.replace("-", ".")
        if normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def format_reference(law_name: str, article: Optional[str], paragraph: Optional[str], item: Optional[str]) -> str:
    parts = [law_name]
    if article:
        parts.append(f"제{article}조")
    if paragraph:
        parts.append(f"제{paragraph}항")
    if item:
        parts.append(f"제{item}호")
    return " ".join(parts)


def extract_law_references(text: str) -> List[Dict]:
    seen = set()
    results: List[Dict] = []

    for match in LAW_NAME_PATTERN.finditer(text):
        law_name, article, paragraph, item = match.groups()
        law_name = law_name.replace("상속세및증여세법", "상속세 및 증여세법")
        key = (law_name, article or "", paragraph or "", item or "")
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "law_name": law_name,
            "article": article,
            "paragraph": paragraph,
            "item": item,
            "display": format_reference(law_name, article, paragraph, item),
        })

    return results


def infer_issues(text: str) -> List[str]:
    issues: List[str] = []
    for issue, keywords in ISSUE_HINTS.items():
        if any(keyword in text for keyword in keywords):
            issues.append(issue)
    return issues[:6] or ["적용법령 적정성"]


def summarize_case(text: str) -> Dict:
    normalized = normalize_text(text)
    dates = extract_dates(normalized)
    sections = split_sections(normalized)
    refs = extract_law_references(normalized)

    taxpayer_lines = []
    authority_lines = []
    for line in normalized.split("\n"):
        if any(token in line for token in ["청구인", "납세자"]):
            taxpayer_lines.append(line.strip())
        if any(token in line for token in ["처분청", "과세관청"]):
            authority_lines.append(line.strip())

    return {
        "dates": dates,
        "sections": sections,
        "issues": infer_issues(normalized),
        "taxpayer_summary": taxpayer_lines[:5],
        "authority_summary": authority_lines[:5],
        "law_references": refs,
    }


def _find_matching_law_id(law_name: str, arguments: Optional[dict] = None) -> Tuple[Optional[str], List[Dict]]:
    response = search_law(law_name, page=1, page_size=10, arguments=arguments)
    candidates = response.get("laws", []) if isinstance(response, dict) else []
    for law in candidates:
        if law.get("법령명") == law_name or law.get("법령명_약칭") == law_name:
            return law.get("법령ID"), candidates
    if candidates:
        return candidates[0].get("법령ID"), candidates
    return None, []


def _find_article_text(law_detail: Dict, article_no: Optional[str]) -> Optional[Dict]:
    if not article_no:
        return None
    target = f"제{article_no}조"
    for article in law_detail.get("조문", []):
        if article.get("조문번호") == target:
            return article
    return None


def _extract_addendum_notes(law_detail: Dict) -> Dict:
    notes = {"has_addendum": False, "effective_dates": [], "application_rules": [], "transition_rules": []}
    for article in law_detail.get("조문", []):
        number = article.get("조문번호", "")
        title = article.get("조문제목", "")
        content = article.get("조문내용", "")
        if "부칙" not in number and "부칙" not in title and "부칙" not in content:
            continue
        notes["has_addendum"] = True
        for pattern in [
            r"공포한 날부터 시행",
            r"\d{4}\.\d{1,2}\.\d{1,2}\.부터 시행",
            r"최초로 [^\.]+ 적용",
            r"종전의 규정에 따른다",
        ]:
            for matched in re.findall(pattern, content):
                if "시행" in matched and matched not in notes["effective_dates"]:
                    notes["effective_dates"].append(matched)
                elif "종전의 규정" in matched and matched not in notes["transition_rules"]:
                    notes["transition_rules"].append(matched)
                elif matched not in notes["application_rules"]:
                    notes["application_rules"].append(matched)
    return notes


def build_revision_points(overview: Dict, reviewed: List[Dict], additions: List[Dict]) -> List[str]:
    points: List[str] = []
    for item in reviewed:
        if item["status"] == "유지 가능":
            points.append(f"파일에 기재된 '{item['reference']}'는 공식 법령 검색 결과와 대체로 부합하므로 유지 가능합니다.")
        else:
            points.append(f"파일에 기재된 '{item['reference']}'는 {item['reason']} 따라서 법령명 또는 조문 번호를 재확인하여 수정할 필요가 있습니다.")
        addendum = item.get("addendum") or {}
        if addendum.get("has_addendum"):
            rules = addendum.get("application_rules") or addendum.get("transition_rules")
            if rules:
                points.append(f"'{item['reference']}'와 관련하여 부칙 문구({'; '.join(rules[:2])})가 확인되므로, 처분시점이 아니라 적용례·경과조치 기준으로 재검토할 필요가 있습니다.")
    for addition in additions[:10]:
        points.append(f"파일상 관련법령에 '{addition['suggestion']}'를 추가 검토할 필요가 있습니다. 사유: {addition['reason']}")
    if not points:
        points.append("파일상 관련법령에 대해 즉시 수정이 필요한 사항은 식별되지 않았습니다.")
    return points


def review_related_laws(document_text: str, arguments: Optional[dict] = None) -> Dict:
    overview = summarize_case(document_text)
    reviewed = []
    mentioned_names = {ref["law_name"] for ref in overview["law_references"]}

    for ref in overview["law_references"]:
        law_id, candidates = _find_matching_law_id(ref["law_name"], arguments=arguments)
        if not law_id:
            reviewed.append({
                "reference": ref["display"],
                "status": "수정 필요",
                "reason": "공식 법령 검색 결과에서 동일 법령을 확인하지 못했습니다.",
                "official_candidates": candidates,
            })
            continue

        law_detail = get_law_detail(law_id, arguments=arguments)
        article = _find_article_text(law_detail, ref.get("article"))
        addendum = _extract_addendum_notes(law_detail)

        if ref.get("article") and not article:
            status = "수정 필요"
            reason = "법령 본문은 확인되지만 기재된 조문 번호를 상세 본문에서 확인하지 못했습니다."
        else:
            status = "유지 가능"
            reason = "법령명은 공식 검색 결과와 일치하며, 기재 조문도 본문에서 확인되었습니다." if article else "법령명은 공식 검색 결과와 일치합니다."

        reviewed.append({
            "reference": ref["display"],
            "status": status,
            "reason": reason,
            "law_id": law_id,
            "law_name_official": law_detail.get("법령명") or ref["law_name"],
            "effective_date": law_detail.get("시행일자"),
            "article_title": article.get("조문제목") if article else None,
            "article_text": article.get("조문내용") if article else None,
            "addendum": addendum,
        })

    additional_needed = []
    for issue in overview["issues"]:
        for suggestion in SUGGESTED_LAWS.get(issue, []):
            suggested_law_name = suggestion.split(" 제")[0]
            if suggested_law_name not in mentioned_names:
                additional_needed.append({
                    "issue": issue,
                    "suggestion": suggestion,
                    "reason": f"{issue} 쟁점과 직접 연결되는 조문 후보입니다.",
                })

    return {
        "overview": overview,
        "reviewed_laws": reviewed,
        "additional_suggestions": additional_needed,
        "draft_revision_points": build_revision_points(overview, reviewed, additional_needed),
    }

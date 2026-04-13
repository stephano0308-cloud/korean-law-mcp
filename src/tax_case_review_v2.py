import re
from typing import Dict, List, Optional, Tuple

from .tools import get_law_detail, search_law

DATE_PATTERN = re.compile(r"(20\d{2})[.\-년]\s*(\d{1,2})[.\-월]\s*(\d{1,2})")

LAW_NAME_PATTERN = re.compile(
    r"((?:국세기본법|법인세법|소득세법|부가가치세법|상속세 및 증여세법|조세특례제한법|관세법|지방세법|지방세기본법|종합부동산세법|상속세및증여세법)(?: 시행령| 시행규칙)?)"
    r"(?:\s*제\s*(\d+(?:의\d+)?)\s*조)?"
    r"(?:\s*제\s*(\d+)\s*항)?"
    r"(?:\s*제\s*(\d+)\s*호)?"
)

DATE_LABEL_HINTS = {
    "처분일": ["처분일", "부과처분", "결정고지", "고지일", "통지일"],
    "증여일": ["증여일", "증여", "증여받", "증여재산"],
    "양도일": ["양도일", "양도", "매도"],
    "상속개시일": ["상속개시", "사망"],
    "신고일": ["신고일", "신고", "과세표준신고"],
    "사업연도": ["사업연도", "사업연도 개시", "사업연도 종료"],
}

ISSUE_TO_BASIS = {
    "경정청구 적법성": ["처분일", "신고일"],
    "부당행위계산부인": ["사업연도", "처분일"],
    "증여세 과세요건": ["증여일", "처분일"],
    "양도소득세 필요경비": ["양도일", "처분일"],
    "공시송달·불복절차": ["처분일"],
    "세금계산서·실질과세": ["신고일", "처분일"],
    "적용법령 적정성": ["처분일"],
}

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


def _normalize_date_token(match: Tuple[str, str, str]) -> str:
    y, m, d = match
    return f"{int(y):04d}.{int(m):02d}.{int(d):02d}"


def extract_all_dates(text: str) -> List[str]:
    results: List[str] = []
    for match in DATE_PATTERN.findall(text):
        value = _normalize_date_token(match)
        if value not in results:
            results.append(value)
    return results


def extract_date_contexts(text: str) -> Dict[str, List[str]]:
    contexts = {k: [] for k in DATE_LABEL_HINTS.keys()}
    lines = [line.strip() for line in normalize_text(text).split("\n") if line.strip()]
    for line in lines:
        dates = [_normalize_date_token(m) for m in DATE_PATTERN.findall(line)]
        if not dates:
            continue
        for label, hints in DATE_LABEL_HINTS.items():
            if any(hint in line for hint in hints):
                for date in dates:
                    if date not in contexts[label]:
                        contexts[label].append(date)
    return contexts


def infer_issues(text: str) -> List[str]:
    issues: List[str] = []
    for issue, keywords in ISSUE_HINTS.items():
        if any(keyword in text for keyword in keywords):
            issues.append(issue)
    return issues[:6] or ["적용법령 적정성"]


def choose_basis_dates(issues: List[str], date_contexts: Dict[str, List[str]], all_dates: List[str]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for issue in issues:
        preferred_labels = ISSUE_TO_BASIS.get(issue, ["처분일"])
        chosen: List[str] = []
        for label in preferred_labels:
            for date in date_contexts.get(label, []):
                if date not in chosen:
                    chosen.append(date)
        if not chosen and all_dates:
            chosen.append(all_dates[0])
        result[issue] = chosen
    return result


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


def summarize_case_v2(text: str) -> Dict:
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


def extract_addendum_analysis(law_detail: Dict, basis_dates: List[str]) -> Dict:
    notes = {
        "has_addendum": False,
        "effective_rules": [],
        "application_rules": [],
        "transition_rules": [],
        "basis_dates_considered": basis_dates,
        "review_opinion": "부칙 미확인",
    }
    found_sentences: List[str] = []
    for article in law_detail.get("조문", []):
        text = " ".join(filter(None, [article.get("조문번호", ""), article.get("조문제목", ""), article.get("조문내용", "")]))
        if "부칙" not in text:
            continue
        notes["has_addendum"] = True
        sentences = re.split(r"(?<=[\.])\s+|\n", text)
        for sentence in sentences:
            s = sentence.strip()
            if not s:
                continue
            if any(token in s for token in ["시행", "적용", "종전의 규정", "경과조치", "최초로"]):
                found_sentences.append(s)
                if "종전의 규정" in s or "경과조치" in s:
                    if s not in notes["transition_rules"]:
                        notes["transition_rules"].append(s)
                elif "적용" in s or "최초로" in s:
                    if s not in notes["application_rules"]:
                        notes["application_rules"].append(s)
                elif "시행" in s:
                    if s not in notes["effective_rules"]:
                        notes["effective_rules"].append(s)
    if notes["has_addendum"]:
        if notes["transition_rules"]:
            notes["review_opinion"] = "부칙상 경과조치 또는 종전 규정 적용 가능성이 있어 기준일 대조가 필요합니다."
        elif notes["application_rules"]:
            notes["review_opinion"] = "부칙상 적용례 문구가 확인되어 처분일이 아니라 사건 기준일로 적용 여부를 판단해야 합니다."
        else:
            notes["review_opinion"] = "부칙은 존재하나 자동 판정 가능한 적용례 문구는 제한적으로 확인되었습니다."
    return notes


def derive_issue_for_reference(reference: Dict, issues: List[str]) -> str:
    law_name = reference.get("law_name", "")
    if "국세기본법" in law_name and "경정청구 적법성" in issues:
        return "경정청구 적법성"
    if law_name.startswith("법인세법") and "부당행위계산부인" in issues:
        return "부당행위계산부인"
    if law_name.startswith("상속세 및 증여세법") and "증여세 과세요건" in issues:
        return "증여세 과세요건"
    if law_name.startswith("소득세법") and "양도소득세 필요경비" in issues:
        return "양도소득세 필요경비"
    if law_name.startswith("부가가치세법") and "세금계산서·실질과세" in issues:
        return "세금계산서·실질과세"
    return issues[0] if issues else "적용법령 적정성"


def build_revision_points(reviewed: List[Dict], additions: List[Dict]) -> List[str]:
    points: List[str] = []
    for item in reviewed:
        basis = ", ".join(item.get("basis_dates", [])) or "기준일 추가 확인 필요"
        if item["status"] == "유지 가능":
            points.append(f"'{item['reference']}'는 공식 법령 검색 결과와 대체로 부합합니다. 다만 적용 기준일은 {basis} 기준으로 다시 대조하는 것이 안전합니다.")
        else:
            points.append(f"'{item['reference']}'는 {item['reason']} 적용 기준일({basis})과 함께 법령명·조문 번호를 재확인할 필요가 있습니다.")
        addendum = item.get("addendum_analysis") or {}
        if addendum.get("has_addendum"):
            points.append(f"'{item['reference']}'는 부칙 검토 결과 '{addendum.get('review_opinion')}'로 정리됩니다.")
    for addition in additions[:10]:
        points.append(f"누락 가능 조문으로 '{addition['suggestion']}'를 검토할 필요가 있습니다. 사유: {addition['reason']}")
    if not points:
        points.append("즉시 수정이 필요한 관련법령은 식별되지 않았습니다.")
    return points


def review_related_laws_v2(document_text: str, arguments: Optional[dict] = None) -> Dict:
    overview = summarize_case_v2(document_text)
    reviewed: List[Dict] = []
    mentioned_names = {ref["law_name"] for ref in overview["law_references"]}

    for ref in overview["law_references"]:
        issue = derive_issue_for_reference(ref, overview["issues"])
        basis_dates = overview["basis_dates_by_issue"].get(issue, [])
        law_id, candidates = _find_matching_law_id(ref["law_name"], arguments=arguments)
        if not law_id:
            reviewed.append({
                "reference": ref["display"],
                "issue": issue,
                "basis_dates": basis_dates,
                "status": "수정 필요",
                "reason": "공식 법령 검색 결과에서 동일 법령을 확인하지 못했습니다.",
                "official_candidates": candidates,
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
                })

    return {
        "overview": overview,
        "reviewed_laws": reviewed,
        "additional_suggestions": additional_needed,
        "draft_revision_points": build_revision_points(reviewed, additional_needed),
        "limitations": [
            "현재 구현은 공식 상세 본문과 부칙 문구를 기반으로 한 휴리스틱 판정입니다.",
            "연혁법령 특정 버전 고정 조회 API가 추가 구현되면 처분 당시 적용 법령 판정 정확도를 더 높일 수 있습니다.",
        ],
    }

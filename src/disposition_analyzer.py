# disposition_analyzer.py
"""
처분개요 텍스트 분석 모듈
처분개요에서 세목, 처분일자, 과세기간, 관련 법조문 등 핵심 정보를 추출합니다.
"""
import re
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger("law-mcp")

# 세목(세금 종류) 키워드 매핑
TAX_TYPE_KEYWORDS = {
    "소득세": ["소득세", "종합소득세", "양도소득세", "퇴직소득세", "근로소득세", "사업소득세", "이자소득세", "배당소득세"],
    "법인세": ["법인세"],
    "부가가치세": ["부가가치세", "부가세"],
    "상속세": ["상속세"],
    "증여세": ["증여세"],
    "종합부동산세": ["종합부동산세", "종부세"],
    "취득세": ["취득세"],
    "재산세": ["재산세"],
    "지방소득세": ["지방소득세"],
    "교육세": ["교육세"],
    "농어촌특별세": ["농어촌특별세"],
    "개별소비세": ["개별소비세"],
    "인지세": ["인지세"],
    "증권거래세": ["증권거래세"],
    "관세": ["관세"],
}

# 세법 법령명 매핑 (세목 -> 관련 법령들)
TAX_LAW_NAMES = {
    "소득세": ["소득세법", "소득세법 시행령", "소득세법 시행규칙"],
    "법인세": ["법인세법", "법인세법 시행령", "법인세법 시행규칙"],
    "부가가치세": ["부가가치세법", "부가가치세법 시행령", "부가가치세법 시행규칙"],
    "상속세": ["상속세 및 증여세법", "상속세 및 증여세법 시행령", "상속세 및 증여세법 시행규칙"],
    "증여세": ["상속세 및 증여세법", "상속세 및 증여세법 시행령", "상속세 및 증여세법 시행규칙"],
    "종합부동산세": ["종합부동산세법", "종합부동산세법 시행령", "종합부동산세법 시행규칙"],
    "취득세": ["지방세법", "지방세법 시행령", "지방세법 시행규칙"],
    "재산세": ["지방세법", "지방세법 시행령", "지방세법 시행규칙"],
    "지방소득세": ["지방세법", "지방세법 시행령", "지방세법 시행규칙"],
    "교육세": ["교육세법", "교육세법 시행령"],
    "농어촌특별세": ["농어촌특별세법", "농어촌특별세법 시행령"],
    "개별소비세": ["개별소비세법", "개별소비세법 시행령", "개별소비세법 시행규칙"],
    "인지세": ["인지세법", "인지세법 시행령"],
    "증권거래세": ["증권거래세법", "증권거래세법 시행령"],
    "관세": ["관세법", "관세법 시행령", "관세법 시행규칙"],
}

# 공통 세법 (모든 세목에 관련될 수 있는 법령)
COMMON_TAX_LAWS = ["국세기본법", "국세기본법 시행령", "국세징수법", "조세특례제한법", "조세특례제한법 시행령"]

# 처분 유형 키워드
DISPOSITION_TYPES = {
    "부과처분": ["부과", "과세", "추징", "결정", "경정"],
    "경정청구거부": ["경정청구", "거부", "기각"],
    "가산세부과": ["가산세"],
    "환급거부": ["환급", "거부"],
    "원천징수": ["원천징수", "원천"],
    "세무조사": ["세무조사", "조사"],
}


@dataclass
class DispositionInfo:
    """처분개요 분석 결과"""
    tax_types: List[str]           # 세목 목록
    disposition_date: Optional[str]  # 처분일자 (YYYYMMDD)
    tax_period: Optional[str]       # 과세기간/귀속연도
    disposition_type: List[str]     # 처분 유형
    tax_amount: Optional[str]       # 세액
    law_references: List[Dict]      # 법조문 인용 목록
    related_laws: List[str]         # 관련 법령명 목록
    keywords: List[str]             # 주요 키워드
    raw_text: str                   # 원문 텍스트

    def to_dict(self) -> dict:
        return asdict(self)


def analyze_disposition(text: str) -> dict:
    """
    처분개요 텍스트를 분석하여 핵심 정보를 추출합니다.

    Args:
        text: 처분개요 텍스트

    Returns:
        DispositionInfo를 딕셔너리로 변환한 결과
    """
    if not text or not text.strip():
        return {"error": "분석할 텍스트가 없습니다."}

    logger.debug("처분개요 분석 시작 | text_length=%d", len(text))

    # 각 분석 수행
    tax_types = _extract_tax_types(text)
    disposition_date = _extract_disposition_date(text)
    tax_period = _extract_tax_period(text)
    disposition_type = _extract_disposition_type(text)
    tax_amount = _extract_tax_amount(text)
    law_references = _extract_law_references(text)
    related_laws = _determine_related_laws(tax_types, law_references)
    keywords = _extract_keywords(text)

    info = DispositionInfo(
        tax_types=tax_types,
        disposition_date=disposition_date,
        tax_period=tax_period,
        disposition_type=disposition_type,
        tax_amount=tax_amount,
        law_references=law_references,
        related_laws=related_laws,
        keywords=keywords,
        raw_text=text[:2000],  # 원문은 최대 2000자까지
    )

    result = info.to_dict()
    logger.debug("처분개요 분석 완료 | tax_types=%s, disposition_date=%s, laws=%d",
                 tax_types, disposition_date, len(law_references))
    return result


def _extract_tax_types(text: str) -> List[str]:
    """텍스트에서 세목(세금 종류)을 추출합니다."""
    found = []
    for tax_type, keywords in TAX_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                if tax_type not in found:
                    found.append(tax_type)
                break
    return found


def _extract_disposition_date(text: str) -> Optional[str]:
    """
    처분일자를 추출합니다.
    다양한 날짜 형식을 인식합니다.
    """
    # "처분일자", "부과일", "통지일", "고지일" 등의 키워드 근처에서 날짜 추출
    date_context_patterns = [
        r"처분일(?:자)?[:\s·]*(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})",
        r"부과일(?:자)?[:\s·]*(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})",
        r"통지일(?:자)?[:\s·]*(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})",
        r"고지일(?:자)?[:\s·]*(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})",
        r"결정일(?:자)?[:\s·]*(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})",
        r"경정[:\s·]*(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})",
    ]

    for pattern in date_context_patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day = match.groups()
            return f"{year}{int(month):02d}{int(day):02d}"

    # 일반적인 날짜 패턴 (문맥이 없는 경우)
    # "YYYY.MM.DD" 또는 "YYYY년 MM월 DD일" 형식
    general_date_patterns = [
        r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})",
        r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
    ]

    dates = []
    for pattern in general_date_patterns:
        for match in re.finditer(pattern, text):
            year, month, day = match.groups()
            year_int = int(year)
            if 1990 <= year_int <= 2030:
                dates.append(f"{year}{int(month):02d}{int(day):02d}")

    # 가장 마지막에 나오는 날짜를 처분일로 추정 (처분은 보통 나중에 발생)
    if dates:
        return dates[-1]

    return None


def _extract_tax_period(text: str) -> Optional[str]:
    """과세기간 또는 귀속연도를 추출합니다."""
    # "과세기간", "귀속연도", "귀속", "사업연도" 등의 키워드
    period_patterns = [
        # "2020년 귀속", "2020 사업연도"
        r"(\d{4})\s*(?:년\s*)?(?:귀속|사업연도|과세기간|과세연도)",
        # "귀속연도: 2020"
        r"(?:귀속(?:연도)?|사업연도|과세기간|과세연도)[:\s·]*(\d{4})",
        # "2020.01.01 ~ 2020.12.31" 형태
        r"(\d{4})[.\-/]\d{1,2}[.\-/]\d{1,2}\s*[~∼\-]\s*\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}",
        # "2020년 1기" 또는 "2020년 2기"
        r"(\d{4})\s*년\s*[12]\s*기",
        # "2020년도"
        r"(\d{4})\s*년도",
    ]

    for pattern in period_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None


def _extract_disposition_type(text: str) -> List[str]:
    """처분 유형을 추출합니다."""
    found = []
    for dtype, keywords in DISPOSITION_TYPES.items():
        for kw in keywords:
            if kw in text:
                if dtype not in found:
                    found.append(dtype)
                break
    return found


def _extract_tax_amount(text: str) -> Optional[str]:
    """세액(금액)을 추출합니다."""
    # "세액", "부과세액", "결정세액" 등의 키워드 근처에서 금액 추출
    amount_patterns = [
        r"(?:부과|결정|고지|추징|경정)?\s*세액[:\s·]*(\d[\d,]+)\s*원",
        r"(\d[\d,]+)\s*원\s*(?:을|를)?\s*(?:부과|결정|고지|추징|경정)",
        r"(?:합계|총액|총\s*세액)[:\s·]*(\d[\d,]+)\s*원",
    ]

    for pattern in amount_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).replace(",", "") + "원"

    return None


def _extract_law_references(text: str) -> List[Dict]:
    """
    텍스트에서 법조문 인용을 추출합니다.
    예: "소득세법 제94조 제1항 제2호", "같은 법 시행령 제162조"
    """
    references = []

    # 법령명 + 조문 패턴
    law_article_patterns = [
        # "소득세법 제94조 제1항 제2호 가목"
        r"((?:소득세법|법인세법|부가가치세법|상속세\s*및\s*증여세법|종합부동산세법|"
        r"지방세법|지방세기본법|국세기본법|국세징수법|조세특례제한법|교육세법|농어촌특별세법|"
        r"개별소비세법|인지세법|증권거래세법|관세법)"
        r"(?:\s*시행령|\s*시행규칙)?)"
        r"\s*(제\d+조(?:의\d+)?(?:\s*제\d+항)?(?:\s*제\d+호)?(?:\s*[가-힣]목)?)",

        # "같은 법 제XX조", "동법 제XX조"
        r"(같은\s*(?:법|시행령|시행규칙)|동법|동\s*시행령)"
        r"\s*(제\d+조(?:의\d+)?(?:\s*제\d+항)?(?:\s*제\d+호)?(?:\s*[가-힣]목)?)",
    ]

    for pattern in law_article_patterns:
        for match in re.finditer(pattern, text):
            law_name = match.group(1).strip()
            article = match.group(2).strip()

            # 조문번호 파싱
            article_detail = _parse_article_number(article)

            ref = {
                "법령명": law_name,
                "조문": article,
                "조문상세": article_detail,
            }

            # 중복 방지
            if not any(r["법령명"] == law_name and r["조문"] == article for r in references):
                references.append(ref)

    return references


def _parse_article_number(article_str: str) -> dict:
    """
    조문 문자열을 파싱하여 구조화합니다.
    예: "제94조 제1항 제2호 가목" -> {"조": "94", "항": "1", "호": "2", "목": "가"}
    """
    result = {}

    jo_match = re.search(r"제(\d+)조(?:의(\d+))?", article_str)
    if jo_match:
        result["조"] = jo_match.group(1)
        if jo_match.group(2):
            result["조의"] = jo_match.group(2)

    hang_match = re.search(r"제(\d+)항", article_str)
    if hang_match:
        result["항"] = hang_match.group(1)

    ho_match = re.search(r"제(\d+)호", article_str)
    if ho_match:
        result["호"] = ho_match.group(1)

    mok_match = re.search(r"([가-힣])목", article_str)
    if mok_match:
        result["목"] = mok_match.group(1)

    return result


def _determine_related_laws(tax_types: List[str], law_references: List[Dict]) -> List[str]:
    """
    세목과 법조문 인용으로부터 관련 법령 목록을 결정합니다.
    """
    laws = set()

    # 세목 기반 법령 추가
    for tax_type in tax_types:
        if tax_type in TAX_LAW_NAMES:
            for law_name in TAX_LAW_NAMES[tax_type]:
                laws.add(law_name)

    # 법조문 인용에서 법령명 추가
    for ref in law_references:
        law_name = ref["법령명"]
        # "같은 법", "동법" 등은 제외
        if law_name not in ("같은 법", "같은 시행령", "같은 시행규칙", "동법", "동 시행령",
                            "법", "시행령", "시행규칙"):
            laws.add(law_name)

    # 공통 세법 추가 (국세기본법 등)
    if tax_types:
        # 지방세인 경우 국세기본법 대신 지방세기본법
        is_local_tax = any(t in ("취득세", "재산세", "지방소득세") for t in tax_types)
        if is_local_tax:
            laws.add("지방세기본법")
            laws.add("지방세기본법 시행령")
        else:
            laws.add("국세기본법")
            laws.add("국세기본법 시행령")

    return sorted(laws)


def _extract_keywords(text: str) -> List[str]:
    """주요 키워드를 추출합니다."""
    # 세무/법률 관련 주요 키워드
    keyword_list = [
        "양도", "취득", "매매", "증여", "상속", "배당", "이자", "임대",
        "사업소득", "근로소득", "기타소득", "퇴직소득",
        "필요경비", "공제", "감면", "비과세", "면세",
        "가산세", "과소신고", "무신고", "납부불성실", "초과환급",
        "실질과세", "부당행위계산", "특수관계인",
        "세금계산서", "매입세액", "매출세액", "영세율",
        "1세대1주택", "다주택", "비사업용토지", "주택임대",
        "신고", "납부", "경정", "환급", "징수", "체납",
        "이전가격", "국제거래", "해외금융계좌",
    ]

    found = []
    for kw in keyword_list:
        if kw in text and kw not in found:
            found.append(kw)

    return found

"""
인사혁신처 법령정보 목록 수집기.

인사혁신처 법령·통계정보 > 법령정보 페이지의 법률, 대통령령, 총리령,
대통령 훈령, 국무총리 훈령, 인사혁신처 훈령·예규·고시 목록을 수집한다.

주의:
- 이 모듈은 인사혁신처 목록과 law.go.kr 원문 링크를 색인하는 역할을 한다.
- 조문 원문은 기존 국가법령정보센터 Open API 도구(search_law/get_law_detail 등)로
  재확인하는 것을 원칙으로 한다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse

import certifi
import requests
from bs4 import BeautifulSoup
from cachetools import TTLCache

logger = logging.getLogger("law-mcp.mpm")

MPM_BASE_URL = "https://www.mpm.go.kr"


@dataclass(frozen=True)
class MpmCategory:
    key: str
    label: str
    url: str
    kind: str  # law | administrative_rule


MPM_CATEGORIES: List[MpmCategory] = [
    MpmCategory("law", "법률", "https://www.mpm.go.kr/mpm/lawStat/infoLaw/lawList/", "law"),
    MpmCategory("presidential_decree", "대통령령", "https://www.mpm.go.kr/mpm/lawStat/infoLaw/lawPresident/", "law"),
    MpmCategory("prime_minister_rule", "총리령·시행규칙", "https://www.mpm.go.kr/mpm/lawStat/infoLaw/lawPrimeMinister/", "law"),
    MpmCategory("presidential_directive", "대통령 훈령", "https://www.mpm.go.kr/mpm/lawStat/infoLaw/lawAnwei/lawAnwei01/", "administrative_rule"),
    MpmCategory("prime_minister_directive", "국무총리 훈령", "https://www.mpm.go.kr/mpm/lawStat/infoLaw/lawAnwei/lawAnwei02/", "administrative_rule"),
    MpmCategory("mpm_directive", "인사혁신처 훈령", "https://www.mpm.go.kr/mpm/lawStat/infoLaw/lawAnwei/lawAnwei03/", "administrative_rule"),
    MpmCategory("mpm_established_rule", "인사혁신처 예규", "https://www.mpm.go.kr/mpm/lawStat/infoLaw/lawAnwei/lawAnwei04/", "administrative_rule"),
    MpmCategory("mpm_notice", "인사혁신처 고시", "https://www.mpm.go.kr/mpm/lawStat/infoLaw/lawAnwei/lawAnwei05/", "administrative_rule"),
]

_catalog_cache: TTLCache = TTLCache(maxsize=16, ttl=60 * 60 * 6)  # 6시간


def _normalise_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def _get(url: str, timeout: int = 30) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; korean-law-mcp/1.0; "
            "+https://github.com/stephano0308-cloud/korean-law-mcp)"
        )
    }
    resp = requests.get(url, headers=headers, timeout=timeout, verify=certifi.where())
    resp.raise_for_status()
    # 인사혁신처 페이지는 일반적으로 UTF-8이지만 서버 헤더가 누락될 수 있어 보정한다.
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _extract_total_pages(text: str) -> int:
    # 예: 전체 39 건 (현재 1페이지 / 총 4 페이지)
    match = re.search(r"총\s*(\d+)\s*페이지", text)
    if match:
        return max(1, int(match.group(1)))
    return 1


def _with_page(url: str, page: int) -> str:
    if page <= 1:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}pageIdx={page}"


def _clean_cell_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _parse_rows(html: str, category: MpmCategory, page_url: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    items: List[Dict[str, str]] = []
    seen = set()

    # 목록 표의 행을 우선 사용한다. 표 구조가 바뀌면 law.go.kr 링크 기반으로도 최대한 복구한다.
    rows = soup.select("table tr")
    if not rows:
        rows = soup.find_all("tr")

    for row in rows:
        link = row.find("a", href=re.compile(r"law\.go\.kr"))
        if not link:
            continue
        title = _clean_cell_text(link.get_text(" "))
        if not title:
            continue
        href = urljoin(page_url, link.get("href", ""))
        cells = [_clean_cell_text(cell.get_text(" ")) for cell in row.find_all(["td", "th"])]

        updated_at = ""
        created_at = ""
        department = ""
        if category.kind == "law":
            # 일반 법령 표: 법령명 / 최종 개정일 / 제정일 / 작성자
            if len(cells) >= 4:
                updated_at, created_at, department = cells[1], cells[2], cells[3]
            elif len(cells) >= 3:
                updated_at, created_at = cells[1], cells[2]
            elif len(cells) >= 2:
                updated_at = cells[1]
        else:
            # 행정규칙 표: 행정규칙명 / 최종개정일 / 소관부서
            if len(cells) >= 3:
                updated_at, department = cells[1], cells[2]
            elif len(cells) >= 2:
                updated_at = cells[1]

        key = (category.key, title, _normalise_url(href))
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "category_key": category.key,
                "category_label": category.label,
                "kind": category.kind,
                "title": title,
                "last_modified": updated_at,
                "enacted_or_created": created_at,
                "department": department,
                "law_go_kr_url": href,
                "mpm_list_url": page_url,
            }
        )

    return items


def fetch_mpm_category(category: MpmCategory, max_pages: int = 20) -> Dict[str, object]:
    """단일 인사혁신처 법령정보 카테고리 목록을 수집한다."""
    first_html = _get(category.url)
    total_pages = min(_extract_total_pages(BeautifulSoup(first_html, "lxml").get_text(" ")), max_pages)
    items = _parse_rows(first_html, category, category.url)

    for page in range(2, total_pages + 1):
        page_url = _with_page(category.url, page)
        try:
            html = _get(page_url)
            items.extend(_parse_rows(html, category, page_url))
        except Exception as exc:  # pragma: no cover - 네트워크 상황에 따라 달라짐
            logger.warning("Failed to fetch MPM category page | category=%s page=%s error=%s", category.key, page, exc)

    # 페이지 중복 제거
    unique: List[Dict[str, str]] = []
    seen = set()
    for item in items:
        key = (item.get("category_key"), item.get("title"), item.get("law_go_kr_url"))
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return {
        "category_key": category.key,
        "category_label": category.label,
        "kind": category.kind,
        "source_url": category.url,
        "total_pages_checked": total_pages,
        "count": len(unique),
        "items": unique,
    }


def fetch_mpm_catalog(categories: Optional[Iterable[str]] = None, force_refresh: bool = False) -> Dict[str, object]:
    """인사혁신처 법령정보 전체 목록을 수집한다."""
    selected = set(categories or [])
    cache_key = tuple(sorted(selected)) if selected else ("__all__",)
    if not force_refresh and cache_key in _catalog_cache:
        return _catalog_cache[cache_key]

    category_defs = [c for c in MPM_CATEGORIES if not selected or c.key in selected or c.label in selected]
    result_categories = []
    all_items: List[Dict[str, str]] = []
    errors: List[Dict[str, str]] = []

    for category in category_defs:
        try:
            result = fetch_mpm_category(category)
            result_categories.append(result)
            all_items.extend(result.get("items", []))
        except Exception as exc:  # pragma: no cover - 네트워크 상황에 따라 달라짐
            logger.exception("Failed to fetch MPM category | category=%s", category.key)
            errors.append({"category_key": category.key, "category_label": category.label, "error": str(exc)})

    catalog = {
        "source": "인사혁신처 법령정보 페이지 및 law.go.kr 원문 링크",
        "source_home": "https://www.mpm.go.kr/mpm/lawStat/infoLaw/lawList/",
        "categories": result_categories,
        "items": all_items,
        "total_count": len(all_items),
        "errors": errors,
    }
    _catalog_cache[cache_key] = catalog
    return catalog


def search_mpm_catalog(query: str, categories: Optional[Iterable[str]] = None) -> Dict[str, object]:
    """수집한 인사혁신처 법령정보 목록에서 제목·부서·분류 기준으로 검색한다."""
    catalog = fetch_mpm_catalog(categories=categories)
    q = (query or "").strip().lower()
    if not q:
        return {"query": query, "count": 0, "items": []}

    tokens = [token for token in re.split(r"\s+", q) if token]
    matched = []
    for item in catalog.get("items", []):
        haystack = " ".join(
            str(item.get(field, ""))
            for field in ("title", "category_label", "department", "kind")
        ).lower()
        if all(token in haystack for token in tokens):
            matched.append(item)

    return {"query": query, "count": len(matched), "items": matched}

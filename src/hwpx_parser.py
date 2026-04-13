# hwpx_parser.py
"""
HWPX 파일 파서
HWPX(한글 Open Document) 파일에서 텍스트를 추출합니다.
HWPX는 ZIP 아카이브로, 내부에 OWPML 표준 기반의 XML 파일들을 포함합니다.
"""
import zipfile
import io
import os
import re
import logging
from typing import Optional
from lxml import etree

logger = logging.getLogger("law-mcp")

# HWPX 내부 XML 네임스페이스 (OWPML 표준)
HWPX_NAMESPACES = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hwpml": "http://www.hancom.co.kr/hwpml/2011/hwpml",
    "opf": "http://www.hancom.co.kr/hwpml/2011/opf",
}


def parse_hwpx_from_path(file_path: str) -> dict:
    """
    파일 경로에서 HWPX 파일을 읽어 텍스트를 추출합니다.

    Args:
        file_path: HWPX 파일의 절대 경로

    Returns:
        추출 결과 딕셔너리 {
            "text": 전체 텍스트,
            "sections": [섹션별 텍스트 리스트],
            "tables": [테이블 데이터 리스트],
            "file_name": 파일명,
            "error": 에러 메시지 (실패 시)
        }
    """
    if not os.path.exists(file_path):
        return {"error": f"파일을 찾을 수 없습니다: {file_path}"}

    if not file_path.lower().endswith(".hwpx"):
        return {"error": "HWPX 형식의 파일만 지원합니다."}

    try:
        with open(file_path, "rb") as f:
            return parse_hwpx_from_bytes(f.read(), os.path.basename(file_path))
    except Exception as e:
        logger.exception("HWPX 파일 읽기 실패: %s", str(e))
        return {"error": f"파일 읽기 실패: {str(e)}"}


def parse_hwpx_from_bytes(data: bytes, file_name: str = "unknown.hwpx") -> dict:
    """
    바이트 데이터에서 HWPX 파일을 파싱합니다.

    Args:
        data: HWPX 파일의 바이트 데이터
        file_name: 파일명 (로깅용)

    Returns:
        추출 결과 딕셔너리
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
            return _extract_from_zip(zf, file_name)
    except zipfile.BadZipFile:
        return {"error": "유효하지 않은 HWPX 파일입니다. (ZIP 형식 오류)"}
    except Exception as e:
        logger.exception("HWPX 파싱 실패: %s", str(e))
        return {"error": f"HWPX 파싱 실패: {str(e)}"}


def _extract_from_zip(zf: zipfile.ZipFile, file_name: str) -> dict:
    """
    ZIP으로 열린 HWPX 파일에서 텍스트를 추출합니다.
    """
    file_list = zf.namelist()
    logger.debug("HWPX 내부 파일 목록: %s", file_list)

    # 섹션 파일 찾기 (Contents/section0.xml, Contents/section1.xml, ...)
    section_files = sorted(
        [f for f in file_list if re.match(r"Contents/section\d+\.xml", f, re.IGNORECASE)]
    )

    # 대체 경로 패턴 확인
    if not section_files:
        section_files = sorted(
            [f for f in file_list if "section" in f.lower() and f.lower().endswith(".xml")]
        )

    if not section_files:
        # 모든 XML에서 텍스트 추출 시도
        section_files = [f for f in file_list if f.lower().endswith(".xml")]
        logger.warning("섹션 파일을 찾을 수 없어 모든 XML에서 추출 시도: %s", section_files)

    all_text_parts = []
    sections = []
    tables = []

    for section_file in section_files:
        try:
            xml_data = zf.read(section_file)
            section_text, section_tables = _parse_section_xml(xml_data)
            if section_text.strip():
                sections.append(section_text.strip())
                all_text_parts.append(section_text.strip())
            tables.extend(section_tables)
        except Exception as e:
            logger.warning("섹션 파일 파싱 실패 (%s): %s", section_file, str(e))

    full_text = "\n\n".join(all_text_parts)

    if not full_text.strip():
        return {
            "text": "",
            "sections": [],
            "tables": [],
            "file_name": file_name,
            "error": "텍스트를 추출할 수 없습니다. 빈 문서이거나 지원하지 않는 형식입니다.",
        }

    return {
        "text": full_text,
        "sections": sections,
        "tables": tables,
        "file_name": file_name,
    }


def _parse_section_xml(xml_data: bytes) -> tuple:
    """
    섹션 XML을 파싱하여 텍스트와 테이블 데이터를 추출합니다.

    Returns:
        (텍스트, 테이블 리스트) 튜플
    """
    try:
        root = etree.fromstring(xml_data)
    except etree.XMLSyntaxError:
        # BOM이 있는 경우 제거 후 재시도
        if xml_data.startswith(b"\xef\xbb\xbf"):
            root = etree.fromstring(xml_data[3:])
        else:
            raise

    # 네임스페이스 자동 감지
    nsmap = _detect_namespaces(root)

    paragraphs = []
    tables = []

    # 모든 paragraph 요소를 순서대로 처리
    for elem in root.iter():
        tag = _local_tag(elem.tag)

        if tag == "p":
            para_text = _extract_paragraph_text(elem, nsmap)
            if para_text.strip():
                paragraphs.append(para_text)
        elif tag == "tbl":
            table_data = _extract_table(elem, nsmap)
            if table_data:
                tables.append(table_data)

    return "\n".join(paragraphs), tables


def _detect_namespaces(root) -> dict:
    """
    XML 루트에서 실제 사용된 네임스페이스를 감지합니다.
    """
    nsmap = {}
    if hasattr(root, "nsmap"):
        nsmap = dict(root.nsmap)
    # None 키 제거 (기본 네임스페이스)
    nsmap.pop(None, None)

    # 알려진 네임스페이스 매핑 보완
    for prefix, uri in HWPX_NAMESPACES.items():
        if prefix not in nsmap:
            # 실제 URI가 있는지 확인
            for p, u in nsmap.items():
                if "paragraph" in u and prefix == "hp":
                    nsmap["hp"] = u
                elif "section" in u and prefix == "hs":
                    nsmap["hs"] = u

    return nsmap


def _local_tag(tag: str) -> str:
    """
    네임스페이스를 제거한 로컬 태그명을 반환합니다.
    "{http://...}tagname" -> "tagname"
    """
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _extract_paragraph_text(p_elem, nsmap: dict) -> str:
    """
    <p> 요소에서 텍스트를 추출합니다.
    구조: <p> -> <run> -> <t> (텍스트)
    """
    texts = []

    for elem in p_elem.iter():
        tag = _local_tag(elem.tag)
        if tag == "t" and elem.text:
            texts.append(elem.text)

    return "".join(texts)


def _extract_table(tbl_elem, nsmap: dict) -> Optional[list]:
    """
    <tbl> 요소에서 테이블 데이터를 추출합니다.

    Returns:
        2차원 리스트 (행 x 열) 또는 None
    """
    rows = []

    for elem in tbl_elem.iter():
        tag = _local_tag(elem.tag)
        if tag == "tr":
            row = []
            for cell_elem in elem.iter():
                cell_tag = _local_tag(cell_elem.tag)
                if cell_tag == "tc":
                    cell_text = _extract_cell_text(cell_elem)
                    row.append(cell_text)
            if row:
                rows.append(row)

    return rows if rows else None


def _extract_cell_text(tc_elem) -> str:
    """
    테이블 셀(<tc>)에서 텍스트를 추출합니다.
    """
    texts = []
    for elem in tc_elem.iter():
        tag = _local_tag(elem.tag)
        if tag == "t" and elem.text:
            texts.append(elem.text)
    return " ".join(texts).strip()

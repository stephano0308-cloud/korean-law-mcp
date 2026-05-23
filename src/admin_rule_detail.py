"""
국가법령정보센터 행정규칙 상세 조회 도구.

기존 tools.py의 search_administrative_rule 결과로 받은 행정규칙ID를 이용해
행정규칙 본문과 조문/별표성 항목을 가능한 한 구조화해 반환한다.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import requests

from .tools import VERIFY, get_credentials, parse_xml_response


def _node_to_dict(node) -> Dict[str, object]:
    data: Dict[str, object] = {}
    text = (node.text or "").strip()
    if text:
        data["text"] = text
    for child in list(node):
        tag = child.tag
        child_value = _node_to_dict(child)
        if not child_value:
            child_text = (child.text or "").strip()
            child_value = child_text
        if tag in data:
            existing = data[tag]
            if not isinstance(existing, list):
                data[tag] = [existing]
            data[tag].append(child_value)
        else:
            data[tag] = child_value
    return data


def _collect_leaf_texts(node) -> List[Dict[str, str]]:
    leaves: List[Dict[str, str]] = []
    for child in node.iter():
        text = (child.text or "").strip()
        if text:
            leaves.append({"tag": child.tag, "text": text})
    return leaves


def get_administrative_rule_detail(admrul_id: str, arguments: Optional[dict] = None) -> Dict[str, object]:
    """행정규칙ID로 행정규칙 상세 원문을 조회한다."""
    credentials = get_credentials(arguments)
    api_key = credentials["LAW_API_KEY"]
    base_url = credentials["LAW_API_URL"]

    if not api_key:
        return {"error": "API 키가 설정되지 않았습니다."}

    api_url = f"{base_url}/lawService.do"
    params = {
        "OC": api_key,
        "target": "admrul",
        "type": "XML",
        "ID": admrul_id,
    }

    try:
        response = requests.get(api_url, params=params, timeout=30, verify=VERIFY)
        response.raise_for_status()
        root = parse_xml_response(response.text)
        if root is None:
            return {"error": "응답 파싱 실패"}

        result = {
            "행정규칙ID": root.findtext(".//행정규칙ID", admrul_id),
            "행정규칙명": root.findtext(".//행정규칙명", ""),
            "소관부처": root.findtext(".//소관부처명", ""),
            "발령일자": root.findtext(".//발령일자", ""),
            "시행일자": root.findtext(".//시행일자", ""),
            "제개정구분": root.findtext(".//제개정구분명", ""),
            "원문텍스트": root.findtext(".//행정규칙내용", "") or root.findtext(".//본문", ""),
            "leaf_texts": _collect_leaf_texts(root),
            "raw": _node_to_dict(root),
        }
        return result
    except requests.exceptions.RequestException as exc:
        return {"error": f"API 요청 실패: {str(exc)}"}
    except Exception as exc:
        return {"error": f"행정규칙 상세 조회 중 오류 발생: {str(exc)}"}

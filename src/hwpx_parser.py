import base64
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional


def _read_hwpx_bytes(hwpx_path: Optional[str] = None, hwpx_base64: Optional[str] = None) -> bytes:
    if hwpx_base64:
        return base64.b64decode(hwpx_base64)
    if hwpx_path:
        with open(hwpx_path, "rb") as f:
            return f.read()
    raise ValueError("hwpx_path 또는 hwpx_base64 중 하나는 필요합니다.")


def extract_hwpx_text(hwpx_path: Optional[str] = None, hwpx_base64: Optional[str] = None) -> Dict:
    """
    HWPX(zip+xml) 파일에서 본문 텍스트를 추출합니다.
    """
    raw = _read_hwpx_bytes(hwpx_path=hwpx_path, hwpx_base64=hwpx_base64)
    texts: List[str] = []
    scanned_files: List[str] = []

    with zipfile.ZipFile(__import__("io").BytesIO(raw), "r") as zf:
        xml_names = [name for name in zf.namelist() if name.endswith(".xml")]
        for name in xml_names:
            scanned_files.append(name)
            try:
                root = ET.fromstring(zf.read(name))
            except ET.ParseError:
                continue
            for elem in root.iter():
                if elem.text:
                    value = " ".join(elem.text.split())
                    if value:
                        texts.append(value)

    text = "\n".join(texts)
    return {
        "text": text,
        "length": len(text),
        "scanned_files": scanned_files,
        "source": os.path.basename(hwpx_path) if hwpx_path else "base64_input",
    }

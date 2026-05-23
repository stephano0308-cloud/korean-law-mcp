#!/usr/bin/env python3
"""
인사혁신처 법령정보 목록 동기화 스크립트.

사용 예:
    python scripts/sync_mpm_law_catalog.py
    python scripts/sync_mpm_law_catalog.py --out data/mpm_law_catalog.json --force

출력:
    data/mpm_law_catalog.json

이 파일은 GPT Knowledge에 업로드할 수 있는 색인 자료이다.
다만 최종 조문 판단은 law.go.kr 원문 또는 국가법령정보센터 Open API 상세조회로 재확인한다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.mpm_law_catalog import fetch_mpm_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="인사혁신처 법령정보 전체 목록을 JSON으로 저장합니다.")
    parser.add_argument("--out", default="data/mpm_law_catalog.json", help="저장할 JSON 경로")
    parser.add_argument("--force", action="store_true", help="캐시를 무시하고 새로 수집")
    args = parser.parse_args()

    catalog = fetch_mpm_catalog(force_refresh=args.force)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"saved: {out_path}")
    print(f"total_count: {catalog.get('total_count')}")
    if catalog.get("errors"):
        print("errors:")
        for err in catalog["errors"]:
            print(f"- {err}")


if __name__ == "__main__":
    main()

# Tax Review Extension for korean-law-mcp

이 확장 모듈은 `korean-law-mcp` 위에 다음 기능을 추가합니다.

- HWPX 텍스트 추출
- 사건 문서에서 처분개요 / 날짜 / 쟁점 / 관련법령 기재 부분 구조화
- 파일에 적힌 관련법령을 공식 법령 검색 결과와 대조
- 유지 가능 / 수정 필요 / 추가 필요 문안 생성
- 부칙 문구(시행, 적용, 종전 규정) 탐지

## 새 엔트리포인트

```bash
python -m src.tax_review_main
```

## 추가된 MCP 도구

- `extract_hwpx_text_tool`
- `analyze_case_document_tool`
- `review_related_laws_tool`

## 기본 사용 흐름

1. `extract_hwpx_text_tool`로 HWPX 텍스트 추출
2. `analyze_case_document_tool`로 쟁점 및 관련법령 구조화
3. `review_related_laws_tool`로 관련법령 유지/수정/추가 의견 확인

## Claude Desktop 설정 예시

```json
{
  "mcpServers": {
    "korean-law-tax-review": {
      "command": "python",
      "args": ["-m", "src.tax_review_main"],
      "env": {
        "LAW_API_KEY": "your_law_api_key_here"
      }
    }
  }
}
```

## 한계

현재 구현은 기존 저장소의 `search_law`, `get_law_detail`를 재사용하는 확장 버전입니다.
따라서 연혁법령 개별 버전 고정 및 부칙의 정교한 적용례 판정은 후속 확장 대상입니다.
다만 조문 본문과 부칙 문구 탐지까지는 자동화되어 있어 실무 초안 검토에 바로 활용할 수 있습니다.

# Tax Review Extension V2

V2는 1차 확장 위에 다음 기능을 추가합니다.

- 사건 문서 내 날짜를 맥락별로 분류
  - 처분일
  - 증여일
  - 양도일
  - 상속개시일
  - 신고일
  - 사업연도
- 쟁점별 기준일 후보 자동 선택
- 조문 본문 내 부칙 문구 탐지
- 적용례/경과조치 재검토 필요 문안 생성

## 실행

```bash
python -m src.tax_review_v2_main
```

## 주요 도구

- `extract_hwpx_text_tool`
- `analyze_case_document_tool`
- `review_related_laws_tool`

## V1 대비 차이

- `analyze_case_document_tool`
  - 전체 날짜 목록
  - 날짜 맥락 분류
  - 쟁점별 기준일 후보
  를 함께 반환합니다.

- `review_related_laws_tool`
  - 각 관련법령별로
    - 연결 쟁점
    - 기준일
    - 부칙 검토 의견
    을 함께 반환합니다.

## 한계

- 아직 공식 연혁 버전 고정 조회가 구현된 것은 아닙니다.
- 현재는 공식 법령 상세 본문과 부칙 문구를 활용한 휴리스틱 검토입니다.
- 차후 `history_tools.py`를 추가하면 처분 당시 시행 연혁법령 판정을 더 정확하게 고도화할 수 있습니다.

## MCP 설정 예시

```json
{
  "mcpServers": {
    "korean-law-tax-review-v2": {
      "command": "python",
      "args": ["-m", "src.tax_review_v2_main"],
      "env": {
        "LAW_API_KEY": "your_law_api_key_here"
      }
    }
  }
}
```

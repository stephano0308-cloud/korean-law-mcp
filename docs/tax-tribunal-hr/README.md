# 조세심판원 인사담당자 지원 MCP 서버

조세심판원(국무총리 소속)에서 국가공무원 및 파견 지방공무원 인사 업무를 담당하는
직원을 지원하는 MCP 서버입니다. 인사 질문을 하면 AI가 이 서버의 도구로
관련 법령·인사혁신처 예규·지침을 검토하여:

1. **담당자가 할 일을 시계열순으로 정리**하고
2. **관련 규정을 요약**하며
3. **law.go.kr 원문 링크**를 함께 제공합니다.

## 동작 방식

```
담당자 질문 (예: "직원이 질병휴직을 신청했어요. 뭘 해야 하나요?")
      │
      ▼
① get_hr_review_guide_tool ─ 검토 절차·답변 형식 확인
② get_hr_workflow_tool ────── 내장 시계열 체크리스트 조회 (11개 인사 이벤트)
③ search_law_tool 등 ──────── 국가법령정보센터에서 최신 규정 검증
④ search_mpm_catalog_tool ─── 인사혁신처 예규·지침 목록 확인
      │
      ▼
답변: 시계열 할일 표 + 규정 요약 + 원문 링크
```

내장 체크리스트는 참고자료이며, AI가 답변 전에 반드시 국가법령정보센터 Open API로
최신 원문을 검증하도록 설계되어 있습니다(`verify_queries`).

## 내장 워크플로우 (11종)

| 분류 | 워크플로우 |
|---|---|
| 채용·임용 | 신규채용(경력경쟁 포함)·시보임용 |
| 승진·보직 | 승진임용 |
| 전보·파견 | 전보 / 파견 및 복귀 |
| 휴직·복직 | 질병휴직 / 육아휴직 |
| 징계·소청 | 징계 및 소청 대응 |
| 퇴직·연금 | 정년퇴직·명예퇴직 |
| 평정·성과 | 근무성적평정·성과평가 |
| 보수·수당 | 호봉획정·승급·수당 |
| 복무·겸직 | 겸직허가·영리업무 관리 |

각 워크플로우는 단계별 **시기/기한 → 할 일 → 근거규정(조문) → 원문 링크**로 구성됩니다.

## 제공 도구 (14종)

| 도구 | 설명 |
|---|---|
| `health` | 서버 상태·API 키 확인 |
| `get_hr_review_guide_tool` | 검토 절차·답변 형식 지침 |
| `list_hr_workflows_tool` | 워크플로우 목록 |
| `get_hr_workflow_tool` | 시계열 체크리스트 조회 |
| `search_hr_workflow_steps_tool` | 체크리스트 단계 키워드 검색 |
| `suggest_hr_keywords_tool` | 사안별 검색 키워드 추천 |
| `search_mpm_catalog_tool` | 인사혁신처 법령·훈령·예규·고시 목록 검색 |
| `fetch_mpm_catalog_tool` | 인사혁신처 목록 전체 수집 |
| `search_law_tool` / `get_law_detail_tool` | 법령 검색·조문 원문 |
| `search_admin_rule_tool` / `get_admin_rule_detail_tool` | 예규·지침 검색·본문 원문 |
| `search_precedent_tool` / `get_precedent_detail_tool` | 판례 검색·상세 |

프롬프트 `hr_case_review`도 제공되어, 지원되는 클라이언트에서는 질문만 넣으면
역할 지침이 자동으로 적용됩니다.

## 설치 및 실행

### 1) 준비

```bash
pip install -r requirements.txt
cp .env.example .env   # LAW_API_KEY 설정 (https://open.law.go.kr 에서 발급)
```

`LAW_API_KEY`가 없으면 내장 체크리스트·키워드 추천·인사혁신처 목록은 동작하지만,
법령·예규 원문 조회는 불가합니다.

### 2) STDIO 모드 (Claude Desktop)

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tax-tribunal-hr": {
      "command": "python",
      "args": ["-m", "src.hr_main"],
      "cwd": "/path/to/korean-law-mcp",
      "env": { "LAW_API_KEY": "your_api_key_here" }
    }
  }
}
```

### 3) HTTP 모드 (Claude 웹/모바일 커넥터)

Claude 웹/모바일에서 사용하려면 서버를 인터넷에서 접근 가능한 곳(Cloud Run,
Render, 사내 서버 등)에 HTTP 모드로 배포해야 합니다.

```bash
HTTP_MODE=1 PORT=8097 python -m src.hr_main
# MCP 엔드포인트: http://<host>:8097/mcp
```

Docker 배포:

```bash
docker build -t korean-law-mcp .
docker run --rm \
  -e MCP_SERVER=src.hr_main \
  -e HTTP_MODE=1 \
  -e PORT=8097 -p 8097:8097 \
  -e LAW_API_KEY=your_api_key_here \
  korean-law-mcp
```

배포 후 Claude 웹 → 설정 → 커넥터 → **커스텀 커넥터 추가**에서
`https://<배포주소>/mcp`를 등록합니다.

> 참고: Claude 커넥터는 HTTPS를 요구하므로 실제 배포 시 TLS가 적용된
> 도메인(또는 Cloud Run처럼 HTTPS를 기본 제공하는 플랫폼)을 사용하세요.

### 4) 역할 지침 적용

Claude 웹에서 프로젝트를 만들고 `docs/tax-tribunal-hr/INSTRUCTIONS.md` 내용을
프로젝트 지침으로 붙여넣으면, 모든 대화에서 시계열 정리 + 규정 요약 + 링크
형식의 답변을 받을 수 있습니다. (커넥터의 `hr_case_review` 프롬프트 또는
`get_hr_review_guide_tool` 호출로도 동일한 지침이 적용됩니다.)

## 사용 예시 질문

- "6급 직원이 다음 달부터 질병휴직을 쓰겠다고 합니다. 제가 처리해야 할 일을 순서대로 알려주세요."
- "징계의결 요구를 해야 하는데 기한과 절차, 관할 징계위원회를 확인해 주세요."
- "지자체에서 파견 온 주무관의 복무 관리는 어느 규정을 따르나요?"
- "올해 명예퇴직 수요조사를 시작하려고 합니다. 일정과 요건을 정리해 주세요."
- "공무원보수 등의 업무지침 최신본에서 경력 환산 부분을 찾아 주세요."

## 데이터 출처 및 한계

- 법령·행정규칙·판례: 국가법령정보센터 Open API (https://open.law.go.kr)
- 인사혁신처 목록: 인사혁신처 법령정보 페이지 (https://www.mpm.go.kr) 색인 + law.go.kr 원문 링크
- 내장 체크리스트는 2026년 1월 기준 법령으로 작성된 **참고자료**입니다.
  AI가 최신 원문으로 검증하도록 설계되어 있으나, 최종 판단과 책임 있는 처리는
  담당자가 원문과 소관부처 해석(인사혁신처 인사특례 문의 등)으로 확인해야 합니다.

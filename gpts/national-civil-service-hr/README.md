# 국가공무원 인사 규정 검토 GPT 만들기

이 폴더는 `korean-law-mcp` 저장소의 국가법령정보센터 Open API 검색 로직과 인사혁신처 법령정보 목록 수집기를 재사용하여, GPTs의 Actions에 연결할 수 있는 국가공무원 인사 규정 검토 챗봇 구성을 정리한 것이다.

## 1. 목표

사용자가 국가공무원 인사 사안을 입력하면 GPT가 다음 자료를 공식 API 기반으로 검색·확인한 뒤, 해당 사안이 관련 규정에 적합한지 또는 위반 소지가 있는지 검토한다.

- 인사혁신처 법령정보 페이지의 법률
- 인사혁신처 법령정보 페이지의 대통령령
- 인사혁신처 법령정보 페이지의 총리령 및 시행규칙
- 인사혁신처 법령정보 페이지의 대통령 훈령, 국무총리 훈령, 인사혁신처 훈령
- 인사혁신처 예규, 고시, 지침 등 행정규칙
- 국가공무원법
- 공무원임용령, 공무원임용규칙, 공무원임용시험령
- 국가공무원 복무규정
- 공무원 보수규정
- 공무원수당 등에 관한 규정
- 공무원 징계령, 공무원 징계령 시행규칙
- 공무원 성과평가 등에 관한 규정
- 국무총리보좌기관인사관리지침
- 필요한 경우 대법원·헌법재판소 등 판례

## 2. 저장소에서 재사용하는 기존 기능

기존 `src/tools.py`의 다음 함수를 활용한다.

- `search_law`: 법령 검색
- `get_law_detail`: 법령 상세 및 조문 조회
- `search_administrative_rule`: 행정규칙 검색
- `search_precedent`: 판례 검색
- `get_precedent_detail`: 판례 상세 조회

추가된 기능은 다음과 같다.

- `src/mpm_law_catalog.py`: 인사혁신처 법령정보 전체 목록 수집
- `src/admin_rule_detail.py`: 행정규칙ID 기반 행정규칙 본문 상세 조회
- `scripts/sync_mpm_law_catalog.py`: 인사혁신처 법령정보 목록을 JSON 색인으로 저장
- `src/hr_gpt_api.py`: GPT Action 전용 API

## 3. 인사혁신처 법령정보 전체 목록 동기화

아래 명령으로 인사혁신처 법령정보 페이지의 법률, 대통령령, 총리령·시행규칙, 훈령, 예규, 고시 목록을 JSON으로 저장할 수 있다.

```bash
python scripts/sync_mpm_law_catalog.py --force
```

기본 출력 파일은 다음과 같다.

```text
data/mpm_law_catalog.json
```

이 JSON 파일은 GPT Knowledge에 업로드 가능한 색인 자료다. 다만 최종 판단은 반드시 Action을 통해 국가법령정보센터 원문 또는 law.go.kr 원문 링크로 재확인해야 한다.

## 4. 서버 실행

### 로컬 실행

```bash
pip install -r requirements.txt
set LAW_API_KEY=발급받은_국가법령정보센터_API키
uvicorn src.hr_gpt_api:app --host 0.0.0.0 --port 8080
```

PowerShell에서는 다음과 같이 실행한다.

```powershell
$env:LAW_API_KEY="발급받은_국가법령정보센터_API키"
uvicorn src.hr_gpt_api:app --host 0.0.0.0 --port 8080
```

### Railway 배포 예시

1. Railway에서 이 GitHub 저장소를 연결한다.
2. 환경변수에 `LAW_API_KEY`를 추가한다.
3. Start Command를 다음과 같이 설정한다.

```bash
uvicorn src.hr_gpt_api:app --host 0.0.0.0 --port $PORT
```

4. 배포 후 다음 주소가 열리는지 확인한다.

```text
https://배포도메인/health
https://배포도메인/openapi.json
```

## 5. GPTs 설정

### 이름 예시

```text
국가공무원 인사 규정 검토 GPT
```

### 설명 예시

```text
국가공무원 및 국무조정실 소속 인사 사안에 대해 관련 법령, 행정규칙, 지침 및 필요시 판례를 공식 API 기반으로 확인하여 적합성·위반 여부를 검토합니다.
```

### Instructions

`gpts/national-civil-service-hr/INSTRUCTIONS.md` 전체 내용을 GPT Builder의 Instructions에 붙여넣는다.

### Knowledge

원칙적으로 최신성 확보를 위해 법령 원문 파일을 Knowledge에 대량 업로드하기보다는 Action 검색을 우선 사용한다.

선택적으로 `data/mpm_law_catalog.json`을 Knowledge에 업로드하면, GPT가 인사혁신처 법령정보 목록을 더 빠르게 참조할 수 있다. 이 파일은 색인 자료이므로, 최종 조문 판단은 Action으로 원문을 다시 확인해야 한다.

### Actions

GPT Builder > Configure > Actions > Create new action > Import from URL에 다음 URL을 입력한다.

```text
https://배포도메인/openapi.json
```

인증은 서버에 `LAW_API_KEY`를 환경변수로 넣는 방식이면 GPT Action 인증 설정은 `None`으로 둘 수 있다. 외부 공개 API로 운영할 경우에는 별도 API Key 인증 미들웨어를 추가하는 것이 바람직하다.

## 6. 주요 Action 엔드포인트

| 엔드포인트 | 용도 |
|---|---|
| `GET /health` | 서비스 상태 및 API 키 설정 여부 확인 |
| `GET /hr/core-keywords` | 국가공무원 인사 검토용 기본 키워드 조회 |
| `POST /hr/mpm-catalog` | 인사혁신처 법령정보 전체 목록 수집 |
| `POST /hr/search-mpm-catalog` | 인사혁신처 목록에서 법령·행정규칙 검색 |
| `POST /hr/suggest-keywords` | 사안별 검색 키워드 추천 |
| `POST /hr/search-laws` | 법령 검색 |
| `POST /hr/search-laws-batch` | 여러 법령 키워드 일괄 검색 |
| `POST /hr/get-law-detail` | 법령ID로 조문 상세 조회 |
| `POST /hr/search-admin-rules` | 행정규칙 검색 |
| `POST /hr/search-admin-rules-batch` | 여러 행정규칙 키워드 일괄 검색 |
| `POST /hr/get-admin-rule-detail` | 행정규칙ID로 행정규칙 본문 상세 조회 |
| `POST /hr/search-precedents` | 판례 검색 |
| `POST /hr/get-precedent-detail` | 판례일련번호로 판례 상세 조회 |

## 7. GPT 답변 흐름 예시

사용자가 다음과 같이 질문한다고 가정한다.

```text
육아휴직 중인 국가공무원이 복직 직후 다른 기관으로 전보될 수 있는지 검토해줘.
```

GPT는 다음 순서로 처리한다.

1. 쟁점 구조화: 육아휴직, 복직, 전보 제한 여부, 인사권자 재량 범위
2. 인사혁신처 목록 확인: `/hr/search-mpm-catalog`
3. 키워드 생성: `국가공무원법 휴직`, `공무원임용령 복직`, `공무원임용령 전보`, `육아휴직 전보 제한`
4. Action 검색: 법령 및 행정규칙 검색
5. 조문 상세 조회: 관련 법령ID로 조문 원문 확인
6. 행정규칙 상세 조회: 관련 행정규칙ID로 본문 확인
7. 필요 시 판례 검색
8. 결론: 적합/위반 소지/추가 확인 필요로 구분

국무조정실 또는 국무총리비서실 등 국무총리보좌기관 소속 인원 사안이면 `국무총리보좌기관인사관리지침`을 우선 검색한 뒤 일반 국가공무원 인사법령을 보완 검토한다.

## 8. 주의사항

- 법령의 특정 시점 적용 여부가 중요한 사안은 기준일을 확인해야 한다.
- Action 검색 결과에 없는 내용을 GPT가 임의로 만들어서는 안 된다.
- 인사혁신처 목록은 색인이므로 조문 원문은 국가법령정보센터 상세조회로 재확인해야 한다.
- 행정규칙은 법령에 위반되는 방식으로 결론 근거가 될 수 없다.
- 판례는 사건번호와 선고일자가 확인된 경우만 인용한다.

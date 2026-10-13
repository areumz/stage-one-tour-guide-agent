# 투어 가이드 에이전트 1단계(answer) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `POST /guide/stream`이 on-stage `/api/artists` 데이터로 한·영 질문에 SSE로 답하는 FastAPI 서비스를 로컬에서 동작시킨다 (설계 문서 §13의 1단계).

**Architecture:** FastAPI가 요청을 L0(길이) → L1(IP·일일 한도) → L2(규칙 필터) 순으로 거른 뒤 OpenAI Agents SDK 에이전트를 스트리밍 실행하고, SDK 이벤트를 계약 이벤트(`tool_status`, `text_delta`, `done`, `error`)로 바꿔 SSE로 내보낸다. 데이터는 on-stage `/api/artists`를 5분 TTL 캐시로 읽는다. 에이전트와 API 사이는 `run_guide` 함수 하나로 분리해 API 테스트에 LLM이 필요 없다.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, httpx, openai-agents, pydantic v2, pytest(+pytest-asyncio), ruff, uv

설계 근거: [docs/design.md](../../design.md)

## Global Constraints

- 언어·프레임워크: Python, FastAPI, OpenAI Agents SDK. `requires-python = ">=3.12"`.
- 대화는 저장하지 않는다. 운영 트레이싱은 끈다 (`set_tracing_disabled(True)`가 기본, `TRACING_ENABLED`로만 켠다). 로그에 질문·답변 본문을 남기지 않는다 (설계 §7.1).
- 도구는 읽기 전용이다. 도구 입력은 코드(`slug`, 도시 `code`)만 쓴다 (설계 §5).
- 날짜 계산은 서버가 한다 (KST, `Asia/Seoul`). LLM이 날짜를 계산하지 않는다 (설계 §5).
- 도시 수는 `stats.cities`, 도시 목록은 `cities[]`를 "대표 도시"로만 말한다 (설계 §5, §12 #3).
- 공연 목록은 `load_shows` 한 함수로만 읽는다 (설계 §5, §12 #11).
- CORS는 허용 목록만 쓰고 와일드카드(`*`)를 금지한다 (설계 §8).
- 입력 길이 상한 200자, IP 분당 5회, IP 일일 30회, 전체 일일 1000회는 시작값이며 환경 변수로 바꾼다 (설계 §6).
- SSE 이벤트: `tool_status`, `text_delta`, `action`, `retract`, `error`, `done`. `error`는 종료 이벤트이고 `done`은 정상 종료에만 보낸다 (설계 §4).
- 안내 문구는 서버가 만들지 않는다. `error.code`와 `tool_status.key`만 보내고 문구는 프런트 사전이 맡는다 (설계 §4).
- 계약은 `contracts/`가 기준이다. 구현 중 on-stage 저장소를 열지 않는다 (Task 2의 계약 추출만 예외, 설계 §8.1).

## 범위

| 포함 (1단계) | 제외 (후속 계획) |
| --- | --- |
| FastAPI 골격, `/health`, CORS, 클라이언트 IP | L3 소형 분류기, 출력 검사 (3단계) |
| `data`(캐시, `load_shows`), `tools` 3개 | 세션 히스토리, `busy`, 세션 턴 상한 (4단계) |
| SSE 스트리밍 답변, locale | `action` 이벤트 생성 (2b단계, 계약 모델만 포함) |
| L0 길이, L1 한도, L2 규칙 | Cloud Run 배포, Dockerfile (5단계) |
| `contracts/` 추출과 Pydantic 모델 | 한·영 README 정식본 (5단계) |

1단계에는 L3가 없어 L2가 `AMBIGUOUS`로 판정한 입력도 메인 에이전트로 보낸다. 시스템 프롬프트의 거절이 유일한 방어선이므로 이 상태로 공개 배포하지 않는다 (설계 §13).

## 파일 구조

| 경로 | 책임 |
| --- | --- |
| `pyproject.toml`, `.python-version`, `.env.example`, `README.md` | 의존성·pytest·ruff 설정, 환경 변수 목록, 실행 방법 |
| `contracts/README.md`, `artist_context.md`, `enums_and_constants.md` | [계약] 출처 기록, `/api/artists` 필드 의미, 도시 code/name 규칙 |
| `contracts/artists.py` | [계약] `/api/artists` 부분집합 Pydantic 모델 |
| `contracts/guide_events.py` | [요구사항] 요청·SSE 이벤트·액션 모델, `parse_event` |
| `contracts/fixtures/artists_response.json`, `guide_events_sample.json` | 골든 응답, 이벤트 샘플 |
| `src/tour_guide/clock.py`, `settings.py` | KST 오늘 날짜, 환경 변수 설정 |
| `src/tour_guide/data.py` | `ArtistsCache`(TTL·stale), `load_shows`, slug·도시 집합 |
| `src/tour_guide/tools.py` | 순수 함수 `list_artists`, `get_artist`, `search_shows` |
| `src/tour_guide/limits.py` | `RateLimiter` (L1) |
| `src/tour_guide/guard.py` | `check_length` (L0), `classify` (L2) |
| `src/tour_guide/sse.py` | 이벤트 → SSE 프레임 |
| `src/tour_guide/agent.py` | 시스템 프롬프트, 도구 래퍼, `build_agent`, 이벤트 매핑, `stream_guide` |
| `src/tour_guide/api.py`, `main.py` | `create_app`, `client_ip`, `build_app` |
| `tests/` | 모듈별 단위 테스트, `conftest.py`의 고정 mini 데이터, `llm` 마커 스모크 |

## 태스크

각 태스크는 **실패하는 테스트 작성 → 실패 확인 → 최소 구현 → 통과 확인 → 커밋** 순서로 진행한다.

### Task 1: 프로젝트 골격, 시계, 설정

- **만드는 것:** `pyproject.toml`, `.python-version`, `.env.example`, `src/tour_guide/{__init__,clock,settings}.py`, `tests/{__init__,conftest,test_settings}.py`
- **인터페이스:** `clock.KST`, `clock.today_kst() -> date`, `Settings.from_env(env=None) -> Settings` (`onstage_url`, `allowed_origins`, `allowed_origin_regex`, `openai_model`, `trusted_proxy_hops`, `rate_per_minute`, `rate_per_ip_daily`, `global_daily`, `tracing_enabled`)
- **무시 규칙 확인:** `git check-ignore -v .env <상세 계획 파일>`로 두 경로가 잡히는지 확인하고, 잡히지 않으면 `.gitignore`에 규칙을 추가한다.
- **버전 점검:** `uv sync`에서 `openai-agents` 버전 해석 오류가 나면 PyPI와 공식 문서에서 최신 값을 확인해 하한을 조정한다 (추측하지 않는다). 모델명은 `uv sync`로 검증되지 않으므로 Task 9에서 확인한다.
- **테스트:** 기본값과 끝 슬래시 제거, 환경 변수 덮어쓰기, `ONSTAGE_URL` 누락 시 `KeyError`, `ALLOWED_ORIGINS=*` 거부
- **완료 기준:** `uv sync` 성공, 무시 규칙 확인 통과, `pytest tests/test_settings.py` 4개 통과

### Task 2: contracts 추출과 Pydantic 모델

- **만드는 것:** `contracts/` 전체(위 표), `tests/contracts/test_artists_fixture.py`, `test_guide_events.py`
- **계약 추출:** 라이브 `/api/artists`를 골든 fixture로 저장하고, README에 on-stage 저장소·브랜치·커밋·추출일을 `gh`로 채워 넣는다. 이 단계만 on-stage를 읽을 수 있다.
- **인터페이스:** `Artist`, `ArtistsResponse`, `City`, `Tour`, `Stats`, `Track`, `GuideRequest`, `ViewContext`, `ToolStatus`, `TextDelta`, `ActionEvent`, `Retract`, `ErrorEvent`, `Done`, `FocusArtist`, `OpenTour`, `HighlightCity`, `parse_event(name, data)`, `MAX_MESSAGE_CHARS = 200`
- **테스트:** 골든 응답이 모델로 파싱됨(`stats.cities >= len(cities)`), 샘플 이벤트가 모델로 되돌려짐, 알 수 없는 이벤트·액션 거부, 요청의 공백 제거와 locale·빈 문자열 검증
- **완료 기준:** `pytest tests/contracts` 5개 통과

### Task 3: data (캐시, `load_shows`, enum)

- **만드는 것:** `src/tour_guide/data.py`, `tests/conftest.py`(고정 mini 데이터 `MINI_RAW`, `TODAY = 2026-10-13`), `tests/test_data.py`
- **인터페이스:** `Show`, `load_shows(artist)`, `DataUnavailable`, `make_http_fetcher(base_url, timeout, transport)`, `ArtistsCache(fetch, ttl_seconds=300, clock).get()`, `slug_set`, `city_names`
- **동작 규칙:** TTL 안에서는 재호출하지 않는다. 실패하면 마지막 값(stale)을 쓰고 30초 뒤 재시도한다. 값이 없으면 `DataUnavailable`. 잘못된 페이로드도 실패로 본다.
- **테스트:** TTL 적중, stale 서빙과 30초 백오프, 값 없음 예외, 잘못된 페이로드, HTTP fetcher의 URL, `load_shows`·enum
- **완료 기준:** `pytest tests/test_data.py` 7개 통과

### Task 4: tools (순수 함수)

- **만드는 것:** `src/tour_guide/tools.py`, `tests/test_tools.py`
- **인터페이스:** `ToolInputError`, `list_artists(artists, today)`, `get_artist(artists, slug, today)`, `search_shows(artists, today, *, city, month, artist, upcoming_only)`. show dict 키는 `artistSlug, artistName, cityCode, cityName, date, daysUntil`.
- **동작 규칙:** 다음 공연은 오늘 이후 중 가장 빠른 것. `get_artist`는 `totalCities`(= `stats.cities`)와 `featuredCities`(= `cities[]`)를 구분한다. 검색 결과는 날짜순. 지난 공연은 `daysUntil`이 음수. enum 밖 입력은 `ToolInputError`.
- **테스트:** 다음 공연 계산(서울 63일, 41일), 지난 공연 제외·미래 없음, 총 도시 수와 대표 도시 목록, 도시·월·아티스트 필터, `upcoming_only` 토글, 입력 검증
- **완료 기준:** `pytest tests/test_tools.py` 8개 통과

### Task 5: limits (L1)

- **만드는 것:** `src/tour_guide/limits.py`, `tests/test_limits.py`
- **인터페이스:** `RateLimiter(per_minute, per_ip_daily, global_daily, clock).check(ip) -> bool` (허용이면 기록 후 True, 거절이면 기록 없이 False)
- **동작 규칙:** 분당 슬라이딩 윈도우, IP별 일일, 전체 일일(킬스위치). KST 자정에 전부 초기화. 서버 메모리라 재시작 시 초기화되는 best-effort.
- **테스트:** 분당 창과 IP 분리, IP 일일, 전체 일일, 거절 요청은 카운트하지 않음, KST 자정 초기화
- **완료 기준:** `pytest tests/test_limits.py` 5개 통과

### Task 6: guard (L0 길이, L2 규칙)

- **만드는 것:** `src/tour_guide/guard.py`, `tests/test_guard.py`
- **인터페이스:** `check_length(message) -> bool`, `Verdict(BLOCK, PASS, AMBIGUOUS)`, `build_vocab(artists)`, `classify(message, vocab)`
- **동작 규칙:** 인젝션 패턴(한·영)은 아티스트명이 있어도 먼저 차단한다. 아티스트·도시 이름이나 투어 키워드가 있으면 통과. 그 외는 `AMBIGUOUS`로 다음 계층에 맡긴다. 주제 이탈을 키워드 블록리스트로 막지 않는다 (이어지는 질문 오탐 방지).
- **테스트:** 200자 경계, vocab 구성, 통과·차단·애매 사례 파라미터화
- **완료 기준:** `pytest tests/test_guard.py` 16개 통과

### Task 7: SSE 직렬화와 에이전트

- **만드는 것:** `src/tour_guide/sse.py`, `src/tour_guide/agent.py`, `tests/test_sse.py`, `tests/test_agent.py`, `tests/test_llm_smoke.py`
- **인터페이스:** `to_sse(event)`, `GuideContext(locale, view)`, `list_artists_json`, `get_artist_json`, `search_shows_json`, `build_agent(cache, today_fn, model)`, `map_stream_event(event)`, `stream_guide(agent, request)`
- **동작 규칙:** 도구 이름은 `listArtists`, `getArtist`, `searchShows`. 도구 오류는 `{"error": ...}` JSON으로 돌려준다. 동적 지시문에 기본 응답 언어, 오늘 날짜(KST), 현재 화면, 아티스트 slug 표, 도시 코드 표를 넣는다. `ModelSettings(store=False, include_usage=True)`. 스트림은 텍스트 델타와 도구 호출만 계약 이벤트로 바꾸고, 정상 종료에 `Done`을 낸다. 연결 종료 시 SDK 실행을 취소한다. 로그에는 요청 id와 토큰 수만 남긴다.
- **테스트:** 한국어 문자가 이스케이프되지 않는 SSE, 액션 평탄화, 도구 래퍼의 성공·오류, 에이전트의 도구 3개와 동적 프롬프트, 스트림 이벤트 매핑. `llm` 마커 스모크 2개(한국어 질문이 `getArtist`를 호출, 영어 질문이 영어로 답변).
- **테스트 대체:** `test_map_text_delta`가 OpenAI 타입 생성에서 깨지면 `SimpleNamespace(type="response.output_text.delta", delta=...)` 방식으로 바꾸고 쓰지 않는 import를 지운다.
- **취소 로그:** 연결 종료·오류로 실행이 끝나지 않았으면 `guide cancelled requestId=...`를 남기고 SDK 실행을 취소한다 (Task 9에서 확인).
- **완료 기준:** `pytest tests/test_sse.py tests/test_agent.py` 8개 통과. `.env`가 있으면 `pytest -m llm` 2개 통과.

### Task 8: API (FastAPI 조립)

- **만드는 것:** `src/tour_guide/api.py`, `src/tour_guide/main.py`, `tests/test_api.py`
- **인터페이스:** `create_app(*, settings, cache, limiter, run_guide)`, `client_ip(request, hops)`, `build_app()` (`uvicorn --factory tour_guide.main:build_app`), `GET /health`, `POST /guide/stream`
- **처리 순서:** L0 `too_long` → L1 `rate_limited` → 데이터 없음 `upstream` → L2 차단 `off_topic` → `run_guide`(예외는 `upstream`). `X-Accel-Buffering: no`, `Cache-Control: no-cache`. `X-Forwarded-For`는 오른쪽에서 `hops`번째 값만 신뢰한다.
- **테스트:** health, 정상 스트림 순서, 길이 초과, 한도 초과, 인젝션 차단 시 에이전트 미호출, 애매한 입력은 에이전트 도달(1단계), 데이터 없음, 에이전트 예외, 잘못된 locale 422, CORS 허용·거부, `client_ip` 5가지
- **완료 기준:** `pytest tests/test_api.py` 15개 통과. 전체 `pytest` 68개 통과, `ruff check . --fix` 후 `All checks passed!`

### Task 9: README와 로컬 수동 검증

- **만드는 것:** `README.md`(실행·확인·테스트 방법, 현재 상태)
- **수동 확인:** 서버를 띄워 `/health`, 한국어 질문, 영어 질문, 인젝션 질문을 `curl`로 확인한다. 한국어는 `getArtist` tool_status 후 text_delta, `done`. 영어는 `searchShows`와 영어 답변. 인젝션은 `error off_topic` 한 번만. 서버 로그에 본문이 없어야 한다.
- **취소 확인:** 긴 답변이 흐르는 중간에 `curl`을 Ctrl+C로 끊는다. 서버 로그에 `guide cancelled requestId=...`가 나오고 같은 id의 `guide done`은 나오지 않아야 하며, 이후 요청이 정상 응답해야 한다. 취소 로그가 없으면 실행이 계속 돌며 토큰을 소모하는 것이므로 원인을 해결한 뒤 넘어간다.
- **모델명 오류 시:** `upstream` 오류와 모델 접근 오류가 보이면 공식 문서(모델 목록·종료 일정)에서 현재 ID를 확인해 `OPENAI_MODEL`과 기본값을 조정한다. 추측하지 않는다.
- **기록:** 사용한 `openai-agents` 버전을 README에 남긴다.
- **완료 기준:** 위 네 가지 응답과 취소 확인이 기대대로 나옴

## 후속 계획 (이 계획의 범위 밖)

| 단계 | 내용 | 선행 조건 |
| --- | --- | --- |
| 2a/2b | on-stage 3D 교체, 액션 이벤트 생성(`focusArtist`, `openTour`) + 프런트 검증·실행 | 1단계 완료, on-stage 인수인계 문서(설계 §14) |
| 3 | L3 블로킹 분류기(`run_in_parallel=False`), 출력 검사(도시 코드/이름 대조), 한·영 테스트 세트, 잔액 소진 오류 → `upstream` 테스트, `run_streamed` 가드레일 실측(§12 #5) | 1단계 |
| 4 | 세션 히스토리(6턴, LRU 500, TTL 30분), 세션 턴 상한, `busy`와 `finally` 해제, `highlightCity`, 추천 칩 | 3단계 |
| 5 | Dockerfile, Cloud Run 배포(기존 에이전트와 동일 설정), `X-Forwarded-For` 홉 수 실측, 콜드 스타트 측정, 한·영 README | 3단계 통과 |
| 별도 | on-stage 전체 공연 GET 추가 후 `contracts/` 갱신과 `load_shows` 교체 (설계 §12 #11) | on-stage 작업 |

## 설계 요구 대응

| 설계 요구 | 담당 |
| --- | --- |
| FastAPI 골격, `/health` (§10, §13) | Task 8 |
| `data`·`tools` 3개, 날짜는 서버 계산 (§5) | Task 3, 4 |
| 도시 수는 `stats.cities`, 목록은 대표 도시 (§5) | Task 4, 7 |
| `load_shows` 단일 진입점 (§5, §12 #11) | Task 3 |
| SSE 이벤트 계약, `error`는 종료 (§4) | Task 2, 7, 8 |
| POST + SSE는 `fetch` 스트리밍 전제 (§4) | Task 8 (`StreamingResponse`, `X-Accel-Buffering`) |
| L0 길이, L1 한도, L2 규칙 (§6) | Task 5, 6, 8 |
| 트레이싱 끔, 본문 미로깅, `store=False` (§7.1) | Task 7, 8 |
| CORS 허용 목록, 와일드카드 금지 (§8) | Task 1, 8 |
| `X-Forwarded-For` 신뢰 위치 (§8) | Task 8 (실측은 5단계) |
| `contracts/` 추출·출처·골든 fixture (§8.1) | Task 2 |
| locale을 동적 지시문으로 (§4) | Task 7 |
| `requestId`는 로그용 (§7.2) | Task 2, 7, 8 |

# 투어 가이드 에이전트 4단계(세션·히스토리·busy·highlightCity) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 같은 `sessionId`의 이어지는 질문에 맥락을 유지하고(최근 6턴), 세션 20턴 상한과 `busy`로 비용·순서를 보호하며, 서버가 검증한 `highlightCity` 액션을 `done` 앞에 한 번 내보낸다 (설계 문서 §13의 4단계, 이 저장소 몫).

**Architecture:** `limits.py`에 서버 메모리 `SessionStore`(LRU 500, TTL 30분, 최근 6턴 텍스트, 커밋된 턴 수, 진행 중 표시)를 둔다. `api.py`의 `events()`가 턴 상한 → L2 → `busy` 획득 → 에이전트 실행 → `done`이면 커밋 → `finally` 해제를 순서대로 맡는다. `stream_guide`는 히스토리를 입력 목록으로 받아 Runner에 넘기고, L3 분류기에는 직전 사용자 질문 하나만 보태며, 출력 검사의 허용 도시에 히스토리의 도시를 포함한다. `highlightCity`는 기존 액션 도구와 같은 구조(도구가 기록, `stream_guide`가 한 번 발행)로 추가한다.

**Tech Stack:** 3단계와 동일 (Python 3.12+, FastAPI, openai-agents 0.23.1, pydantic v2, pytest, ruff, uv). 새 의존성 없음.

설계 근거: [docs/design.md](../../design.md) §4(이벤트·액션), §6(가드레일), §7·§7.3(세션과 히스토리, 4단계 설계), §13(4단계), §14.6(계약 갱신 요청 H1~H5)

## Global Constraints

- 이 저장소만 수정한다. on-stage 코드는 열지도 수정하지도 않는다. 계약은 `contracts/`가 기준이다. H1~H5 요청은 사용자가 이미 on-stage에 전달했다.
- 새 SSE 이벤트 타입은 만들지 않는다. 바뀌는 계약은 `ErrorCode`에 `session_limit` 한 값을 더하는 것뿐이다.
- 히스토리: 서버 메모리, 세션당 최근 6턴(12메시지), 30분 TTL, 세션 최대 500개(LRU), 텍스트만 저장 (도구 호출·결과 제외). 초기값은 환경 변수로 바꿀 수 있어야 한다.
- 커밋 규칙: `done`으로 정상 종료됐고 `retract`가 없었던 턴만 커밋한다. `error`(L3·L2 차단 포함)·취소·연결 끊김·`retract`된 턴은 저장하지 않는다. 커밋은 `done`을 클라이언트에 내보내기 **전에** 한다. 답변 텍스트가 비어 있으면 저장하지 않는다.
- 세션 턴 상한은 **커밋된 턴 20** 이상일 때 새 요청을 `session_limit`으로 거절한다. 차단된 턴은 세지 않는다.
- `busy`: 같은 `sessionId`에 진행 중 표시가 있으면 새 요청은 `busy`. 해제는 정상·취소·연결 끊김·오류 모두 `finally`에서 한다. 안전망으로 120초 지난 표시는 무시한다.
- 요청 처리 순서는 길이 → IP 한도 → 데이터 → 세션 턴 상한 → L2 → `busy` 획득 → 실행이다. IP 한도가 모든 요청에 먼저 적용된다.
- L3 분류기는 현재 메시지와 **직전 사용자 질문 하나**만 받는다 (전체 히스토리·assistant 답변 제외). L2는 현재 메시지만 본다.
- 출력 검사의 허용 도시 = 이번 턴 도구 결과 ∪ 현재 질문 ∪ 히스토리(커밋된 질문·답변)의 도시.
- `highlightCity`: `slug`는 enum, `city`는 **그 아티스트의 `load_shows` 도시 코드 안에** 있어야 하고, 현재 화면이 `tour/<그 slug>`일 때만 기록한다. 한 답변에 액션 하나(마지막 유효한 호출). 순서는 `text_delta… → action → done`이며 `retract` 턴에서는 보내지 않는다.
- 로그에 질문·답변·히스토리 본문과 세션 id를 남기지 않는다 (설계 §7.1). 요청 id만 남긴다.
- 사용자 확인 전에는 커밋하지 않는다. `docs/design.md`에는 사용자가 아직 커밋하지 않은 변경이 있으므로 승인 전에는 스테이징하지 않는다.
- LLM 테스트(`llm` 마커)는 사용자가 실행을 승인했을 때만 돌린다 (API 비용).

## 범위

| 포함 | 제외 |
| --- | --- |
| `SessionStore`(히스토리·턴 수·진행 중 표시), 설정 4개 | on-stage 코드 일체 (`session_limit`·`busy` 문구, 새 `sessionId`, 칩, 연출) |
| 히스토리 주입, L3 직전 질문, 출력 검사 히스토리 도시 | 액션 판단 추가 보정 (필요하면 별도 작업) |
| `session_limit` 코드, `busy`·턴 상한·커밋·해제 배선 | 영속 저장소 (DB). 대화는 저장하지 않는다는 원칙 유지 |
| `highlightCity` 도구·규칙·서버 검증·fixture | 추천 칩 구현 (프런트 작업). 칩 문구 회귀 테스트 틀만 둔다 |
| `contracts/`·`design.md`·`handoff-onstage.md` 동기화 | Cloud Run 배포·지연 측정 (5단계) |

## 파일 구조

| 경로 | 변경 | 책임 |
| --- | --- | --- |
| `src/tour_guide/limits.py` | 수정 | `SessionStore`: 히스토리, 턴 수, 진행 중 표시, TTL·LRU |
| `src/tour_guide/settings.py` | 수정 | `SESSION_TTL_SECONDS`, `SESSION_MAX`, `HISTORY_TURNS`, `SESSION_TURN_LIMIT` |
| `src/tour_guide/agent.py` | 수정 | 히스토리 입력, L3 직전 질문, 출력 검사 히스토리 도시, `highlightCity` 도구·규칙 |
| `src/tour_guide/classifier.py` | 수정 | 지시문에 `[이전 질문]` 형식 설명 |
| `src/tour_guide/api.py` | 수정 | 턴 상한, `busy`, 커밋, 해제 배선 |
| `src/tour_guide/main.py` | 수정 | `SessionStore` 생성·주입, `run_guide`에 히스토리 전달 |
| `contracts/guide_events.py` | 수정 | `ErrorCode`에 `session_limit` |
| `contracts/fixtures/guide_events_sample.json` | 수정 | `error_session_limit`, `error_busy`, `success_highlight_city` 추가 |
| `contracts/ui_actions.md`, `contracts/README.md` | 수정 | `highlightCity` 의미·규칙, 변경 기록 |
| `docs/design.md`, `docs/handoff-onstage.md` | 수정 | §7.3 확정, 4단계 인수인계 반영 |
| `tests/test_limits.py`, `test_settings.py`, `test_agent.py`, `test_api.py`, `tests/contracts/test_guide_events.py` | 수정 | 위 변경의 LLM 없는 테스트 |
| `tests/test_history_flow.py` | 생성 | 히스토리 주입·L3 직전 질문·출력 검사 (가짜 Runner) |
| `tests/test_llm_session.py` | 생성 | `llm` 마커: 후속 질문·영어 후속·`highlightCity` 실제 모델 확인 |
| `tests/test_chips.py` | 생성 | on-stage가 칩 문구 목록을 주면 L0·L2를 통과하는지 회귀 테스트 (목록이 없으면 건너뜀) |
| `scripts/measure_actions.py` | 수정 | 화면 컨텍스트별 케이스, `highlightCity` 행 추가 |

## 태스크

각 태스크는 **실패하는 테스트 작성 → 실패 확인 → 최소 구현 → 통과 확인 → 커밋** 순서로 진행한다. 코드와 단계별 명령은 상세본에 있다.

### Task 1: SessionStore와 설정

- **수정:** `src/tour_guide/limits.py`, `src/tour_guide/settings.py`, `tests/test_limits.py`, `tests/test_settings.py`
- **인터페이스:** `SessionStore(max_sessions, ttl_seconds, history_turns, turn_limit, busy_stale_seconds, clock)`와 메서드 `turn_limit_reached(sid)`, `history(sid)`, `try_acquire(sid)`, `release(sid)`, `commit(sid, user, assistant)`. 설정 필드 `session_ttl_seconds`, `session_max`, `history_turns`, `session_turn_limit`.
- **동작 규칙:** 세션은 마지막 사용 순서로 유지하고 만료·초과분은 오래된 쪽부터 제거하되 진행 중인 세션은 건너뛴다. `turn_limit_reached`와 `history`는 세션을 만들지 않고 복사본을 돌려준다. `try_acquire`는 진행 중 표시가 있고 120초 안이면 `False`다. 만료된 id가 다시 오면 빈 세션으로 취급한다. 이벤트 루프가 하나라 확인과 표시 사이에 `await`가 없으면 락은 필요 없다.
- **테스트:** 최근 N턴만 유지, 턴 수는 커밋만 센다, 획득·해제·busy, 오래된 표시 무시, TTL 만료 후 새 세션, LRU 제거와 진행 중 건너뛰기, 복사본 반환, 설정 기본값·환경 변수 덮어쓰기
- **완료 기준:** `pytest tests/test_limits.py tests/test_settings.py` 통과

### Task 2: 계약 — `session_limit`, `busy`, `highlightCity` 샘플

- **수정:** `contracts/guide_events.py`, `contracts/fixtures/guide_events_sample.json`, `contracts/ui_actions.md`, `contracts/README.md`, `tests/contracts/test_guide_events.py`
- **인터페이스:** `ErrorCode`에 `session_limit` 포함. fixture 키 `error_session_limit`, `error_busy`, `success_highlight_city`.
- **동작 규칙:** 에러 스트림은 `error`로 끝나고 `done`이 없다. `success_highlight_city`는 `tool_status → text_delta → action(highlightCity) → done` 순서다. `ui_actions.md`에 `highlightCity` 단계를 "4단계 (지금)"으로 바꾸고 서버 규칙(그 아티스트의 도시, 투어 페이지에서만, 한 답변에 하나, `retract` 턴 없음)을 적는다. README 변경 기록에 한 줄 추가한다.
- **테스트:** 두 에러 스트림 모양, `session_limit` 파싱, `highlightCity` 스트림 순서와 페이로드
- **완료 기준:** `pytest tests/contracts` 통과

### Task 3: 히스토리 주입, L3 직전 질문, 출력 검사의 히스토리 도시

- **수정:** `src/tour_guide/agent.py`, `src/tour_guide/classifier.py`, `tests/test_history_flow.py`(생성), `tests/test_llm_session.py`(생성)
- **인터페이스:** `stream_guide(agent, request, cache=None, needs_classifier=False, history=())`. `GuideContext`에 `message`, `prev_question`. 분류기 입력은 히스토리가 없으면 현재 메시지 그대로, 있으면 `[이전 질문] …` 줄과 `[현재 질문] …` 줄이다.
- **동작 규칙:** 히스토리가 있으면 Runner 입력을 `(질문, 답변)` 쌍을 풀어 만든 user/assistant 메시지 목록 뒤에 현재 질문을 붙인 목록으로 보내고, 없으면 지금처럼 문자열을 보낸다. 지시문 구조는 바꾸지 않아 프롬프트 캐시 앞부분이 유지된다. 출력 검사의 허용 집합에 히스토리 텍스트의 도시를 더한다. 분류기 지시문은 `[이전 질문]`을 맥락으로만 읽고 `[현재 질문]`만 판정하라고 적는다. 입력 가드레일이 목록 입력을 통째로 직렬화하지 않게 한다.
- **테스트:** 히스토리 입력 목록 모양과 `prev_question`, 히스토리 없으면 문자열 유지, 히스토리 도시는 통과하고 아무도 말하지 않은 도시는 여전히 `retract`, 분류기가 직전 질문만 받는다. LLM: 후속 질문이 `retract` 없이 답을 내고, 영어 후속 질문은 영어로 답한다.
- **완료 기준:** `pytest` 통과. 사용자 승인 시 `pytest -m llm tests/test_llm_session.py`로 assistant 메시지 입력 형식이 실제 API에서 받아들여지는지 확인한다 (안 되면 content 형식을 바꾼다).

### Task 4: `highlightCity` 도구·규칙·서버 검증

- **수정:** `src/tour_guide/agent.py`, `tests/test_agent.py`
- **인터페이스:** `record_highlight_json(cache, ctx, slug, city) -> str`, 에이전트 도구 `highlightCity(slug, city)`, `ACTION_TOOLS`에 `highlightCity` 포함, `GuideContext.action`이 `HighlightCity`를 받을 수 있다.
- **동작 규칙:** slug가 enum 밖이거나, city가 그 아티스트의 공연 도시 코드가 아니거나, 현재 화면이 그 아티스트의 투어 페이지가 아니면 `{"error": ...}`를 돌려주고 기록하지 않는다 (앞선 유효한 값을 지우지 않는다). 성공하면 `ctx.action`을 덮어쓰고 `action_calls`를 센다. `ACTION_RULES`의 결정표에 "투어 페이지에서 특정 도시 공연을 물으면 도구로 조회해 답한 뒤 `highlightCity`를 호출"을 더하고, 궤도 화면·다른 아티스트 페이지·도시를 말하지 않는 질문에서는 호출하지 않는다고 적는다.
- **테스트:** 유효한 기록, 다른 아티스트의 도시 거절과 이전 값 유지, 화면이 없음·궤도·다른 slug에서 거절, 모르는 slug와 주입된 도시 문자열 거절, `tool_status`에서 제외, 프롬프트에 규칙 문구 포함. 도구 개수를 세는 기존 테스트는 6개로 갱신한다.
- **완료 기준:** `pytest` 통과, `ruff check .` 통과

### Task 5: `api` 배선 — 턴 상한, busy, 커밋, 해제

- **수정:** `src/tour_guide/api.py`, `src/tour_guide/main.py`, `tests/test_api.py`, (필요 시) `tests/test_main.py`
- **인터페이스:** `create_app(settings, cache, limiter, sessions, run_guide)`. `run_guide(req, needs_classifier, history)`. 연결 끊김 테스트용으로 `events()`를 직접 만들 수 있는 훅 하나를 앱에 둔다 (운영 경로와 같은 함수).
- **동작 규칙:** 길이 → IP 한도 → 데이터 → 턴 상한(`session_limit`) → L2(`off_topic`) → `busy` 획득 → 히스토리 읽기 → 에이전트 실행 순서다. 스트림을 지나가면서 `text_delta`를 모으고 `retract`를 기록하며, `done`을 만나면 `retract`가 없고 답변이 비어 있지 않을 때만 커밋한 뒤 `done`을 내보낸다. 모든 경로의 `finally`에서 해제한다. 예외는 `upstream`으로 바꾼다.
- **테스트:** `done` 턴 커밋과 다음 요청의 히스토리, `retract`·오류·빈 답변·L2 차단은 커밋하지 않음, 턴 상한 거절(에이전트 미호출), 진행 중이면 `busy`이고 해제 뒤 정상, 정상·오류·`retract`·예외 후 모두 표시 해제, 연결이 끊겨 제너레이터가 닫히면 해제되고 커밋되지 않음
- **완료 기준:** `pytest` 통과

### Task 6: LLM 확인과 칩 회귀 테스트 틀

- **수정:** `tests/test_llm_session.py`, `tests/test_chips.py`(생성), `scripts/measure_actions.py`
- **동작 규칙:** 케이스 튜플에 화면 컨텍스트를 넣고 `highlightCity` 행(투어 페이지, "도쿄 공연은 언제 해?", 기준 6/8)과 궤도 화면 대조군을 추가한다. 대조군의 정확한 기대는 첫 실행 결과를 보고 사용자와 정한다 (궤도에서는 `openTour`가 정당할 수 있다). 칩 테스트는 `contracts/fixtures/chips.json`이 있을 때만 돌고, 각 문구가 길이 상한과 L2 차단을 통과하는지 본다.
- **테스트:** 투어 페이지의 도시 질문이 `highlightCity(aurora, TYO)` (3회 중 2회), 궤도의 도시 질문은 `highlightCity`가 나가지 않음 (3회 모두)
- **완료 기준:** 사용자 승인 후 `pytest -m llm tests/test_llm_session.py`와 `scripts/measure_actions.py`에서 기존 5문장이 회귀하지 않고 `highlightCity` 행이 6/8 이상. 실패하면 프롬프트를 고치고 기대값은 고치지 않는다.

### Task 7: 문서 동기화

- **수정:** `docs/design.md`, `docs/handoff-onstage.md`, `contracts/ui_actions.md`
- **동작 규칙:** §7.3과 §14.6의 "제안·확인 대기"를 확정으로 바꾸고 계획서 위치를 적는다. 분류기 직전 질문, 허용 도시, busy 안전망 120초가 확정임을 한 줄로 남긴다. `highlightCity` 측정 결과를 §6.4 아래에 기록한다. 인수인계 문서에 H1~H5와 fixture 이름을 옮긴다.
- **완료 기준:** `pytest -q`, `ruff check .` 통과

## Review Focus

1. 답변 중 연결이 끊기거나 "멈추기"로 취소하면 `busy` 표시가 풀리고 히스토리에 쌓이지 않는다. (Task 5)
2. 같은 세션으로 요청 두 개가 겹치면 두 번째는 `busy`이고 첫 번째 히스토리가 꼬이지 않는다. (Task 5)
3. 20턴에 도달한 세션이라도 차단·`retract`·오류 턴은 턴 수를 올리지 않고, 20턴 이후에는 `session_limit`이다. (Task 1, 5)
4. 만료·밀려난 세션 id가 다시 오면 빈 세션으로 정상 동작한다. (Task 1)
5. 답변 텍스트가 비어 있는(액션만 있는) 턴은 빈 assistant 메시지를 히스토리에 남기지 않는다. (Task 5)
6. 다른 아티스트의 도시나 투어 페이지가 아닌 곳에서의 `highlightCity`는 기록되지 않고 앞선 유효한 액션을 지우지 않는다. (Task 4)

## 위험과 메모

- assistant 메시지를 입력 목록에 넣을 때 API가 요구하는 `content` 형식은 실제 호출로만 확인된다. Task 3의 LLM 확인이 그 단계이고, 실패하면 형식을 바꾼다.
- 입력 가드레일 함수 속성명은 SDK 버전에 달려 있다. Task 3 테스트 작성 시 SDK 소스로 확인한다.

# 투어 가이드 에이전트 2b단계(액션 이벤트) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 에이전트가 답변 끝에 `focusArtist(slug)` 또는 `openTour(slug)` UI 액션을 SSE `action` 이벤트로 한 번 내보내게 한다 (설계 문서 §13의 2b 중 이 저장소 몫).

**Architecture:** 에이전트에게 액션 도구 `focusArtist`, `openTour`를 준다. 도구는 slug를 data의 enum으로 검증한 뒤 요청별 `GuideContext`에 기록만 하고(마지막 유효한 호출만 남는다), `stream_guide`가 텍스트 스트림이 정상 종료된 뒤 `Done` 직전에 `ActionEvent`를 한 번 내보낸다. 액션 도구 호출은 `tool_status`로 내보내지 않는다. 사용 규칙은 시스템 프롬프트에 불릿으로 추가한다.

**Tech Stack:** 1단계와 동일 (Python 3.12+, FastAPI, openai-agents, pydantic v2, pytest, ruff, uv). 새 의존성 없음.

설계 근거: [docs/design.md](../../design.md) §4(액션 이벤트), §5, §13, §14.3

## Global Constraints

- 이 저장소만 수정한다. on-stage 코드는 열지도 수정하지도 않는다. 계약은 `contracts/`가 기준이다.
- 이번 단계가 보내는 액션은 `focusArtist`, `openTour`뿐이다. `highlightCity`는 4단계라 만들지 않는다 (계약 모델은 그대로 둔다).
- `openTour`는 `section` 없이 `slug`만 보낸다. `section` 값은 on-stage가 정해줘야 할 항목이고 추측하지 않는다.
- 순서는 `text_delta... → action → done`이고 `action`은 답변당 한 번만 보낸다. 에러·취소로 끝나는 요청에서는 보내지 않는다 (설계 §4).
- slug는 서버가 `/api/artists`에서 만든 enum(`data.slug_set`)으로 검증한다. 검증에 실패하거나 모르는 액션은 보내지 않고, 답변은 항상 표시한다.
- 한 답변에서 액션 도구가 여러 번 호출되면 마지막 유효한 호출만 보낸다.
- 액션 도구 호출은 `tool_status`로 내보내지 않는다 (`action` 이벤트가 따로 있고, 프런트 사전에 키가 없다).
- 안내 문구는 서버가 만들지 않는다. 로그에 질문·답변 본문을 남기지 않는다 (설계 §4, §7.1).
- 출력 검사(`retract`), L3 분류기는 3단계 범위다. 이번에 만들지 않는다.

## 범위

| 포함 (2b, 이 저장소)                                               | 제외                                                    |
| ------------------------------------------------------------------ | ------------------------------------------------------- |
| 액션 도구 2개, `GuideContext` 기록, `stream_guide`의 `action` 발행 | `highlightCity` (4단계)                                 |
| `tool_status`에서 액션 도구 제외                                   | on-stage 코드 일체                                      |
| 시스템 프롬프트 액션 규칙 + LLM 마커 테스트 4개                    | `retract`, L3 분류기 (3단계)                            |
| `contracts/ui_actions.md` [요구사항], `design.md` §4 동기화        | `openTour.section` 값 정의 (on-stage 결정 후 계약 갱신) |

## 파일 구조

| 경로                                          | 변경      | 책임                                                                                                                     |
| --------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------ |
| `src/tour_guide/agent.py`                     | 수정      | `GuideContext.action`, `record_action_json`, 액션 도구 2개, `ACTION_RULES`, `map_stream_event` 제외, `stream_guide` 발행 |
| `tests/test_agent.py`                         | 수정      | 기록·검증·마지막 값, 도구 스키마, `tool_status` 제외, 프롬프트 규칙, 스트림 순서·에러                                    |
| `tests/test_llm_smoke.py`                     | 수정      | `collect`에 화면 컨텍스트 인자, 액션 LLM 테스트 4개                                                                      |
| `contracts/ui_actions.md`                     | 생성      | [요구사항] 액션 의미, on-stage가 정할 값, on-stage가 할 일                                                               |
| `contracts/README.md`, `docs/design.md`       | 수정      | 파일 표 행 추가, §4 문단 동기화                                                                                          |
| `contracts/fixtures/guide_events_sample.json` | 변경 없음 | 성공 스트림에 `focusArtist`가 이미 있고 순서가 맞다 (확인만)                                                             |

## 태스크

각 태스크는 **실패하는 테스트 작성 → 실패 확인 → 최소 구현 → 통과 확인 → 커밋** 순서로 진행한다.

### Task 1: 액션 도구와 컨텍스트 기록

- **수정:** `src/tour_guide/agent.py`, `tests/test_agent.py`
- **인터페이스:** `GuideContext(locale, view, action=None, action_calls=0)`, `ACTION_MODELS`, `ACTION_TOOLS`, `record_action_json(cache, ctx, action_type, slug) -> str`, 에이전트 도구 5개 (`listArtists`, `getArtist`, `searchShows`, `focusArtist`, `openTour`)
- **동작 규칙:** slug가 enum 밖이면 `{"error": ...}`를 돌려주고 기록하지 않는다 (앞선 유효한 값을 지우지 않는다). 유효하면 `ctx.action`을 덮어쓴다. 액션 도구 호출은 `map_stream_event`에서 `None`이다. ctx 인자는 도구 스키마에 나타나지 않는다.
- **테스트:** 기록·마지막 값 우선, 잘못된 slug 거절과 이전 값 유지, 도구 스키마는 `slug`만, `tool_status` 제외 (도구 2개 파라미터화)
- **완료 기준:** `pytest tests/test_agent.py` 통과, `ruff check .` 통과

### Task 2: 답변 끝에 action 이벤트 발행

- **수정:** `src/tour_guide/agent.py`, `tests/test_agent.py`
- **인터페이스:** `stream_guide`가 정상 종료 시 `... TextDelta, ActionEvent, Done` 순서로 내보낸다. 종료 로그에 `action_calls=<n>`이 붙는다.
- **동작 규칙:** 로그 → `completed = True` → (액션이 있으면) `ActionEvent` → `Done`. 에러·취소 때는 이 지점에 오지 않는다.
- **테스트:** 순서(`tool_status`, `text_delta`, `action`, `done`), 액션 없음, 액션 기록 뒤 에러, 중간 종료
- **완료 기준:** `pytest tests/test_agent.py` 통과

### Task 3: 시스템 프롬프트 액션 규칙

- **수정:** `src/tour_guide/agent.py` (`ACTION_RULES`), `tests/test_agent.py`
- **규칙:** 한국어·영어 모두 같은 규칙, 대상(아티스트 vs 투어 페이지/섹션)으로 구분. 특정 한 아티스트 질문이고 현재 화면이 orbit이면 `focusArtist` 허용(일정 질문 포함), 투어 페이지를 열어 달라는 명시적 요청이면 `openTour`. 여러 아티스트를 다루는 질문·일반 질문은 호출하지 않는다. 불확실하면 호출하지 않고 한 답변에 하나만. `openTour`를 이미 열린 화면에서 다시 호출하지 않는다. slug는 표의 값만, 호출했다는 말은 하지 않는다.
- **테스트:** 프롬프트에 규칙 핵심 문구와 현재 화면이 들어간다
- **완료 기준:** `pytest tests/test_agent.py` 통과

### Task 4: LLM 마커 테스트 (액션 사용 규칙 검증)

- **수정:** `tests/test_llm_smoke.py`
- **테스트 4개** (`MINI_RAW`의 slug는 `aurora`, `velvet`뿐이며 화면은 `orbit`):

| 질문                                        | locale | 기대                                                               |
| ------------------------------------------- | ------ | ------------------------------------------------------------------ |
| "AURORA 보여줘"                             | ko     | `FocusArtist(aurora)`, `done` 직전, `tool_status`에 액션 도구 없음 |
| "AURORA 투어 열어줘"                        | ko     | `OpenTour(aurora)`                                                 |
| "Open the AURORA tour"                      | en     | `OpenTour(aurora)`                                                 |
| "AURORA랑 VELVET 중에 누가 먼저 서울에 와?" | ko     | `ActionEvent` 없음, 답변 텍스트는 있음                             |

- **불안정할 때:** 3회 재현 후 `ACTION_RULES`에 예시 한 줄을 더한다. 테스트 기대값은 고치지 않는다.
- **완료 기준:** `pytest -m llm tests/test_llm_smoke.py` 6개 통과 (`OPENAI_API_KEY` 없으면 미실행으로 보고). 기본 `pytest`는 영향 없음.

### Task 5: contracts [요구사항]과 설계 문서 동기화

- **만드는 것:** `contracts/ui_actions.md`. `contracts/README.md` 파일 표와 `docs/design.md` §4를 갱신한다.
- **ui_actions.md 내용:** 보내는 액션과 시점, 의미(`openTour`: 해당 아티스트 페이지로 이동하고 투어 섹션이 보이게 한다. 카메라 포커스 → 페이지 이동 → 섹션 이동의 연출 순서와 자동 이동/칩 방식은 on-stage가 결정한다. 에이전트는 `openTour` 하나만 보낸다), on-stage가 정할 값(`openTour.section`, 연출 방식), on-stage가 할 일(알 수 없는 액션 무시, 실행 전 slug 재검증, 실패해도 답변 표시, 답변 끝에 한 번 오는 액션 처리, 요청마다 `context { view, slug? }` 전송(안 보내면 에이전트는 화면을 알 수 없음으로 보고 `focusArtist`를 보내지 않을 수 있다), 계약 테스트).
- **fixture:** 성공 스트림에 `focusArtist`가 이미 있어 수정하지 않는다. `tests/contracts/test_guide_events.py::test_success_stream_ends_with_done`로 확인만 한다.
- **완료 기준:** 전체 `pytest`, `ruff check .` 통과

## 로컬 수동 확인 (선택, LLM 키가 있을 때)

서버를 띄워 `curl`로 확인한다

- 궤도 화면 컨텍스트로 "AURORA 보여줘" → `focusArtist(aurora)`가 `done` 직전에 오고 `tool_status`에 액션 도구가 없다.
- 궤도 화면 컨텍스트로 "AURORA 투어 일정 알려줘" 5회 → `focusArtist`가 오는지 센다. 거의 안 오면(5번 중 1번 이하) 코드를 바꾸지 않고, `ACTION_RULES` 규칙 3의 '호출해도 된다'를 '호출한다'로 바꾸는 안을 횟수와 함께 보고한다.
- 답변 도중 연결을 끊으면 `guide cancelled` 로그가 남고 `action`은 오지 않는다.

## 후속 (이 계획의 범위 밖)

| 항목                                                                                            | 선행 조건              |
| ----------------------------------------------------------------------------------------------- | ---------------------- |
| `openTour.section` 값 정의 후 계약 갱신 (`guide_events.py`, fixture, `ui_actions.md`, 프롬프트) | on-stage 결정          |
| `highlightCity` (도시 code enum 검증을 `record_action_json`과 같은 방식으로)                    | 4단계                  |
| 프롬프트 예시(few-shot)                                                                         | Task 4가 불안정할 때만 |
| 3단계: 출력 검사(`retract`) 실패 시 `action`을 보내지 않도록 순서와 규칙을 정의                 | 3단계                  |

## 설계 요구 대응

| 요구                                                            | 담당      |
| --------------------------------------------------------------- | --------- |
| 액션 도구로 기록하고 서버가 끝에 한 번 내보낸다 (결정 1)        | Task 1, 2 |
| 여러 번 호출되면 마지막 것만 (결정 2)                           | Task 1, 2 |
| 규칙 목록 + 도구 docstring, 비교 질문엔 호출하지 않음 (결정 3)  | Task 3, 4 |
| slug 서버 검증, 모르는 액션은 보내지 않음, 답변은 항상 표시     | Task 1    |
| 에러·취소에서는 보내지 않음                                     | Task 2    |
| `tool_status`로 내보내지 않음                                   | Task 1    |
| `section` 없이 slug만, on-stage가 정할 값을 [요구사항]으로 기록 | Task 5    |
| fixture 성공 스트림에 action 예시, on-stage 할 일 정리          | Task 5    |

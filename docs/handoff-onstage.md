# on-stage 인수인계 (에이전트 쪽 → on-stage 세션)

on-stage 세션이 읽고 바로 브레인스토밍을 시작하기 위한 진입점이다. 세부 내용은 복사하지 않고 링크로 가리킨다.
근거는 [design.md](design.md) §4·§9·§14와 [contracts/](../contracts/README.md)이다. 이 문서는 on-stage 코드 구조를 추측해서 쓰지 않았다.

## 1. 경계 한 줄

**에이전트(이 저장소)는 질문에 데이터로 답하고 화면 이동 액션을 "데이터"로 보낸다. on-stage는 그 이벤트를 받아 화면을 그리고 액션을 검증해 실행한다.** 에이전트는 on-stage 코드를 열지 않고, on-stage는 `contracts/`를 직접 고치지 않는다.

## 2. on-stage가 할 일

전체 표는 [design.md §14.3](design.md)에 있다. 이 문서는 순서와 경계만 정리한다.

| 단계          | 할 일                                                                                          | 에이전트 필요 여부 | 근거                                |
| ------------- | ---------------------------------------------------------------------------------------------- | ------------------ | ----------------------------------- |
| **2a**        | A탭 투어 오빗을 3D로 교체 (R3F/WebGL), 기존 2D는 삭제하지 않고 **플래그로 복귀 가능**하게 유지 | 불필요             | [§9](design.md)                     |
| **2b 프런트** | `POST /guide/stream` SSE 소비, 채팅 패널(접힘/반투명/모바일 시트), 이벤트 처리, 액션 검증·실행 | 필요               | [§4](design.md), [§14.3](design.md) |

- 2a 완료 기준: 기존 hover·클릭 진입과 모바일 반응형 유지, 프레임 끊김 없음, `webglcontextlost` 0건 ([§9](design.md)).
- 액션이 `{ slug }` 데이터라 렌더러와 무관하므로, 3D가 지연되면 2D 회전으로 2b를 먼저 진행할 수도 있다.

### 데이터 요청: 전체 공연 읽기 엔드포인트 (확정, on-stage에서 진행)

- **현황:** 에이전트가 읽는 `GET /api/artists`의 `cities[]`는 `featured` 공연만 담고, 전체 공연(`shows`)을 읽는 GET이 없다. 기존 `/api/shows`는 POST 전용이다.
- **요청:** `shows` 전체(`city_code, city_name, country, venue, show_date, featured`)를 읽기 전용 공개 GET으로 노출한다. 경로는 `GET /api/shows` 또는 `/api/artists`의 전체 공연 필드 중 on-stage가 정한다.
- **이유:** 지금 에이전트는 대표 도시만 검색해서 "등록된 일정에서 찾지 못했다"고만 답하고, 도시 "목록"은 "대표 도시"로만 말한다.
- **추가한 뒤:** 경로와 응답 모양을 에이전트 쪽에 "계약 갱신" 요청으로 전달한다. 에이전트는 `contracts/`와 골든 fixture를 갱신하고 공연 목록을 읽는 `load_shows` 한 함수만 바꾼다 ([design.md §5](design.md), [§12 #11](design.md)).
- 이 항목은 2a·2b와 독립이라 순서 제약이 없다.

### 확인 요청: `/api/artists` 계약 재검증

- **배경:** 에이전트의 데이터 정의(`contracts/artists.py`, `artist_context.md`, `fixtures/artists_response.json`)는 on-stage 소스의 타입 정의를 읽고 만든 것이 아니라, **배포된 `GET /api/artists`의 실제 응답(2026-10-13)에서 필드와 타입을 추론**해 만들었다. 그래서 실제 타입과 어긋난 곳이 있어도 에이전트는 스스로 알 수 없다.
- **on-stage 확인해줄 항목:**

| 확인 항목                                                                            | 왜 중요한가                                                                                   |
| ------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| `src/lib/types.ts`의 `Artist` 타입이 `contracts/artists.py`의 필드·타입과 일치하는가 | 다르면 에이전트의 응답 검증이 실패해 `upstream` 오류가 된다                                   |
| `null`이나 빈 값이 될 수 있는 필드가 있는가                                          | 지금 모델은 `null`을 허용하지 않아, 어떤 아티스트에서 값이 비면 같은 이유로 `upstream`이 된다 |
| `contracts/README.md`의 출처 커밋(`e57361ae…`)이 배포본과 같은 버전인가              | 오래된 정의를 기준으로 삼고 있을 수 있다                                                      |

- **차이가 있으면:** 에이전트 저장소에 "계약 갱신" 요청으로 전달한다. 에이전트가 `contracts/`와 골든 fixture를 함께 갱신한다. on-stage가 `contracts/`를 직접 고치지 않는다.
- 상세 문구는 [design.md §14.3-1](design.md)에 있다.

## 3. 요청 규칙

- **매 요청에 `context { view, slug?, section? }`를 보낸다.** `view`는 `orbit | tour`이고 `slug`는 현재 아티스트, `section`은 `hero | tour | album | gallery`(`view="tour"`일 때만 의미)다. 안 보내면 에이전트는 현재 화면을 "알 수 없음"으로 보고 `focusArtist`를 보내지 않을 수 있다.
- **`POST` + SSE는 `fetch` 스트리밍(`ReadableStream`)으로 읽는다.** `EventSource`는 GET만 지원해서 쓸 수 없다.
- 이벤트 종류, 종료 규칙(`error`는 종료 이벤트이고 `done`은 정상 종료에만), 요청 필드는 [guide_events.py](../contracts/guide_events.py)와 [design.md §4](design.md)가 기준이다. 안내 문구는 서버가 만들지 않고 `error.code`·`tool_status.key`를 프런트 사전이 ko/en으로 표시한다.
- 요청 길이, "다시 시도"는 새 요청, 답변 멈추기는 연결 종료다 ([§4](design.md), [§7.2](design.md)).

## 4. 액션 처리

기준 문서는 [contracts/ui_actions.md](../contracts/ui_actions.md)이고, 예시 스트림은 [fixtures/guide_events_sample.json](../contracts/fixtures/guide_events_sample.json)이다. 이 문서에서 다시 쓰는 것은 다음뿐이다.

| 액션                   | 처리                                                                                                         |
| ---------------------- | ------------------------------------------------------------------------------------------------------------ |
| `focusArtist { slug }` | 궤도 화면에서 카메라를 해당 아티스트로 옮긴다                                                                |
| `openTour { slug }`    | 해당 아티스트 페이지로 이동하고 투어 섹션이 보이게 한다. 연출 순서와 자동 이동/칩 방식은 on-stage가 결정한다 |

- 액션은 답변 끝에 **한 번**, `done` 앞에 온다. 알 수 없는 액션은 무시하고, 실행 전에 `slug`를 다시 검증하며, 실패해도 답변은 항상 표시한다.
- **이미 그 아티스트의 투어 섹션이면 서버가 `openTour`를 보내지 않는다.** 서버는 `context.view`가 `tour`이고 `slug`가 같으며 `section`이 `tour`이거나 없을 때만 거른다. 다른 섹션(`hero`/`album`/`gallery`)을 보는 중이면 보내므로 on-stage가 투어 섹션으로 스크롤한다. 그 밖의 중복 방어는 on-stage가 한다.
- `retract`된 턴은 action을 보내지 않는다. 순서는 `text_delta… → retract → done`이다.
- `tool_status`에 `focusArtist`·`openTour`가 오지 않으므로 사전에 키를 추가할 필요가 없다.

### 계약 갱신 요청 (3단계 가드레일, 새 이벤트 타입 없음)

| # | 요청 | 근거 |
| --- | --- | --- |
| R1 | 프런트 사전의 `off_topic` 문구를 [design.md §6.1](design.md)의 ko/en 문구로 반영 | §6.1 |
| R2 | `retract`: `reason: "unverified"` 문구를 사전에 추가하고, `text_delta… → retract → done` 순서(action 없음)를 처리 | §6.2 |

- 분류기 실패는 기존 `upstream`이라 추가 요청이 없다. 예시 스트림은 [fixtures/guide_events_sample.json](../contracts/fixtures/guide_events_sample.json)의 `retract_unverified`다.

### 계약 갱신 요청 (4단계: 세션·`busy`·`highlightCity`)

전체 근거는 [design.md §14.6](design.md), [§7.3](design.md)이다.

| # | 요청 | 근거 |
| --- | --- | --- |
| H1 | `error` 코드 `session_limit`과 `busy`의 ko/en 문구를 사전에 추가한다. `session_limit`을 받으면 "새 대화 시작"을 안내하고 **새 `sessionId`를 만들어 대화창을 비운다** | §7.3 |
| H2 | 답변이 스트리밍 중일 때는 전송을 막고, "답변 멈추기" 뒤에는 **연결이 닫힌 것을 확인한 뒤** 다음 요청을 보낸다 (`busy` 방지). `busy`는 재시도 없이 "아직 답변 중이에요"로 안내한다 | §4, §7.3 |
| H3 | `highlightCity`가 의미 있는 화면(`view`/`section`)과 연출을 정해 알려 준다. 에이전트는 현재 `tour/<slug>`에서만 보내는 것을 가정한다. 다르면 이 규칙을 고친다 | §7.3 |
| H4 | 추천 칩 문구 목록(ko/en)을 전달한다. 이 저장소의 회귀 테스트에 넣어 L2/L3와 한도를 통과하는지 확인한다 | §7.3 |
| H5 | `highlightCity` 액션 샘플을 on-stage 계약 테스트에 추가한다 | §8.1 |

- 예시 스트림은 [fixtures/guide_events_sample.json](../contracts/fixtures/guide_events_sample.json)의 `error_session_limit`, `error_busy`, `success_highlight_city`다.

## 5. 섹션 구분 메모 (on-stage 작업)

[design.md §14.3](design.md)에 "아티스트 페이지 섹션 구분 + `openTour` 스크롤"로 기록한 항목이다.

- 아티스트 페이지(`/artists/[slug]`)는 **섹션 단위로 구분**한다.
- 사용자가 보고 있는 섹션을 감지해 요청 `context`에 **`section`으로 보낸다**.
- 같은 페이지에서 `openTour`를 받으면 **투어 섹션으로 스크롤 이동**한다.
- **섹션 값은 `hero`, `tour`, `album`, `gallery`로 확정**됐고 에이전트 쪽 계약 갱신(요청 `context.section`, `openTour.section`, 서버 필터, 프롬프트 표기, fixture)을 반영했다. 값을 늘리려면 "계약 갱신" 요청으로 전달한다. 모르는 `section` 값은 요청을 거절하지 않고 무시된다(`section`이 없는 것으로 취급, `view`·`slug`는 엄격). 에이전트는 `openTour.section`을 당분간 생략한다.
- 서버 가드는 `view` + `slug` + `section`을 본다 ([contracts/ui_actions.md](../contracts/ui_actions.md)).

## 6. 진행 방식 (plan 파일 구성)

2a와 2b를 **같은 plan 파일에 이어서** 쓰되, 2a 끝에 체크포인트를 둔다.

- 2a 구현이 끝나면 **멈추고**, 화면을 확인해 승인한 뒤에만 2b를 시작한다.
- plan에 적을 체크포인트 항목 :
  1. 3D 궤도가 표시된다 (노드·궤도·라벨)
  2. 아티스트 이동: hover·클릭 진입이 기존과 같이 동작한다
  3. 모바일 화면에서 레이아웃과 조작이 유지된다
  4. 2D 폴백 플래그로 기존 화면에 복귀된다
  5. 프레임 끊김과 `webglcontextlost`가 없다
- 승인 전에는 2b 태스크(SSE 클라이언트, 패널, 액션 실행)를 시작하지 않는다.

## 7. 로컬 연동

에이전트 서버 실행 (이 저장소 루트에서):

```bash
PYTHONPATH=src:. uv run --env-file .env uvicorn --factory tour_guide.main:build_app --port 8000
```

- 상태 확인: `GET http://localhost:8000/health` → `{"status": "ok"}`. 패널을 열 때 한 번 호출해 콜드 스타트를 완화하는 용도로도 쓴다 ([§10](design.md)).
- `.env`에 `ONSTAGE_URL`과 `OPENAI_API_KEY`가 필요하다 ([.env.example](../.env.example)). 허용 Origin 기본값은 `http://localhost:3000`이다. 배포 연동 시 `ALLOWED_ORIGINS`에 `https://on-stage-nine.vercel.app`을 추가한다. 프리뷰 도메인 패턴이 필요하면 on-stage가 정해 전달하고, 에이전트는 `ALLOWED_ORIGIN_REGEX`로 받는다(와일드카드 `*`는 금지).
- 요청·응답 예시는 [README.md](../README.md)의 `curl` 절차를 따른다.

## 8. 아직 정해지지 않은 것

| 항목                              | 상태                                                                                                |
| --------------------------------- | --------------------------------------------------------------------------------------------------- |
| `openTour.section` 값 목록        | **확정** (`hero`/`tour`/`album`/`gallery`). 에이전트는 당분간 생략한다 |
| 섹션 구분 방식, `context.section` | **확정·에이전트 반영 완료** (계약 갱신 C1~C5). on-stage 구현 대기 |
| `highlightCity`                   | 4단계 구현됨. 투어 페이지(`tour/<slug>`)에서만 보낸다. 다른 화면 요청은 H3                          |
| 세션 기록·`busy`·세션 턴 상한     | 4단계 구현됨. `session_limit`·`busy` 문구는 H1, 전송 규칙은 H2                                      |
| 출력 검사(`retract`), L3 분류기   | 3단계. 공개 배포 전 필수이며 `retract` 처리는 on-stage 항목에 있다                                  |
| 전체 공연 읽기 엔드포인트         | 추가하기로 확정. **경로·응답 모양은 on-stage가 정해 전달** (위 "데이터 요청", [§12 #11](design.md)) |

## 규칙

- `contracts/`는 on-stage 쪽에서 **직접 수정하지 않는다.** 필요하면 에이전트 저장소에 "계약 갱신" 요청으로 전달한다 ([contracts/README.md](../contracts/README.md) 규칙).
- 계약 재검증 요청은 2절 "확인 요청"에 풀어 두었다.

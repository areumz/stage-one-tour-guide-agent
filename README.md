# STAGE.ONE Tour Guide Agent

STAGE.ONE A탭의 투어 가이드 에이전트 API. 팬이 자연어로 아티스트·공연을 물으면 실제 데이터를 조회해 답하고, 화면 이동(UI 액션)을 데이터로 돌려줍니다.

The tour-guide agent API behind the STAGE.ONE A tab. Fans ask about artists and shows in natural language; the agent looks up real data, answers, and returns screen-navigation (UI actions) as data.

> **Frontend:** [areumz/on-stage](https://github.com/areumz/on-stage) · **Live demo:** https://on-stage-nine.vercel.app/

---

## 소개 / Introduction

**STAGE.ONE**의 A탭에서 팬이 "서울에서 곧 공연하는 팀은?", "AURORA 투어 일정 보여줘"처럼 묻습니다. 이 저장소는 그 질문을 받아 on-stage의 공개 API(`/api/artists`)로 아티스트·공연 데이터를 조회하고, 스트리밍으로 답변하며, 카메라 이동·투어 페이지 열기·도시 강조 같은 화면 동작을 `action` 이벤트로 돌려줍니다. 한국어와 영어로 묻는 대로 답하고, 로그인 없는 익명 사용자를 전제로 설계했습니다.

In the A tab, fans ask things like "Who's playing in Seoul soon?" or "Show me AURORA's tour." This service receives the question, reads artist and show data from on-stage's public API (`/api/artists`), streams the answer, and returns screen actions (move the camera, open a tour page, highlight a city) as `action` events. It answers in Korean or English as asked and is designed for anonymous visitors with no login.

- 읽기 전용 도구 3개 (`listArtists`, `getArtist`, `searchShows`)와 화면 이동 도구 3개 (`focusArtist`, `openTour`, `highlightCity`)
- 한·영 Q&A, 같은 세션의 후속 질문(최근 6턴), 날짜 계산은 서버가 담당
- 프런트(on-stage)가 액션을 실행하며, 서버는 `slug`·도시 코드를 enum으로 검증해서 보냄

Three read-only data tools (`listArtists`, `getArtist`, `searchShows`) and three navigation tools (`focusArtist`, `openTour`, `highlightCity`); Korean/English Q&A with follow-ups in the same session (last 6 turns); dates are computed server-side; the frontend executes actions and the server only sends `slug` and city codes validated against enums.

---

## 기술 스택 / Tech Stack

| 영역 | 선택 |
|---|---|
| Language | Python 3.12 |
| Framework | FastAPI + uvicorn (SSE 스트리밍) |
| Agent | OpenAI Agents SDK (`openai-agents`) |
| Model | `gpt-4.1-mini` (메인·분류기, 환경 변수로 교체) |
| Data | on-stage `GET /api/artists` (5분 TTL 캐시, 실패 시 마지막 캐시) |
| Contract | `contracts/` — Pydantic 모델 + 골든 fixture, 계약 테스트 |
| Test | pytest (LLM 호출 없는 테스트 + `llm` 마커 실제 호출 테스트), ruff |
| Deploy | Google Cloud Run (서울, 인스턴스 1대) |

FastAPI streams Server-Sent Events from a single agent built with the OpenAI Agents SDK on `gpt-4.1-mini`. Artist and show data comes from on-stage's `/api/artists` with a 5-minute cache (stale data is served if it fails). Request, event, and action models live in `contracts/` as Pydantic models with golden fixtures that the frontend copies for its own contract tests. Tests run without LLM calls by default; real-model tests are behind the `llm` marker. It deploys to Cloud Run in Seoul as a single instance.

---

## 요청 흐름과 가드레일 / Request Flow and Guardrails

```
브라우저(A탭) ── POST /guide/stream ──▶ FastAPI
  L0  입력 길이 (200자) · 세션 턴 상한 (20턴)
  L1  IP 분당·일일 한도, 전체 일일 한도
  L2  규칙 필터: 인젝션 패턴 차단 먼저, 명백한 투어 질문은 통과
  L3  소형 분류기 (애매한 질문만, 차단 시 메인 호출 0)
  L4  메인 에이전트 + 읽기 도구 3개 + 액션 도구 3개
  출력 검사: 답변의 도시가 도구 결과·질문에 없으면 retract
  ◀── SSE: tool_status | text_delta | action | retract | error | done
```

비용을 지키기 위해 값싼 검사를 앞에 두고, 메인 에이전트는 마지막에 부릅니다. 차단된 요청은 도구 호출 없이 끝납니다. 실제 지출 상한은 선불 크레딧 잔액이고(자동 충전 OFF), 이 에이전트 전용 키·프로젝트를 씁니다.

Cheap checks come first and the main agent runs last, so blocked requests end without any tool calls. The real spending cap is a prepaid credit balance (auto-reload off) on a key and project dedicated to this agent.

- 스트림 순서: `text_delta… → action? → done`. 답변 검사에 실패하면 `text_delta… → retract → done`이고 액션은 보내지 않습니다.
- 같은 `sessionId`에 진행 중 요청이 있으면 `busy`, 20턴을 넘기면 `session_limit`.
- 안내 문구는 서버가 만들지 않고, 프런트가 `error.code`로 ko/en 사전에서 표시합니다.

Stream order is `text_delta… → action? → done`; if the output check fails it is `text_delta… → retract → done` with no action. A second request in a session that is still answering gets `busy`; past 20 turns it gets `session_limit`. The server never writes user-facing notices; the frontend renders them from `error.code`.

---

## 로컬 실행 / Local Development

Python 3.12와 [uv](https://docs.astral.sh/uv/)가 필요합니다. OpenAI API 키는 본인 것을 사용합니다.

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/), plus your own OpenAI API key.

```bash
git clone https://github.com/areumz/stage-one-tour-guide-agent.git
cd stage-one-tour-guide-agent
uv sync
cp .env.example .env    # OPENAI_API_KEY 입력 / fill in OPENAI_API_KEY
PYTHONPATH=src:. uv run --env-file .env uvicorn --factory tour_guide.main:build_app --port 8000
```

`PYTHONPATH=src:.`는 editable 설치에 의존하지 않기 위한 것입니다. macOS에서 venv의 `.pth` 파일에 `hidden` 플래그가 붙으면 `ModuleNotFoundError: tour_guide`가 나는데, 영구 해결은 `chflags nohidden .venv/lib/python*/site-packages/*.pth`입니다.

`PYTHONPATH=src:.` avoids relying on an editable install. On macOS a `hidden` flag on the venv `.pth` file can cause `ModuleNotFoundError: tour_guide`; the lasting fix is `chflags nohidden .venv/lib/python*/site-packages/*.pth`.

동작 확인 / Quick check:

```bash
curl -s localhost:8000/health

curl -N -s localhost:8000/guide/stream \
  -H 'content-type: application/json' \
  -d '{"requestId":"r1","sessionId":"s1","locale":"ko","message":"AURORA 투어 일정 보여줘","context":{"view":"orbit"}}'
```

on-stage 로컬과 연동하려면 on-stage의 `NEXT_PUBLIC_GUIDE_API_URL=http://localhost:8000`을 설정하세요 (비우면 패널이 나타나지 않습니다). 이 저장소의 `ALLOWED_ORIGINS` 기본값이 `http://localhost:3000`입니다.

To connect a local on-stage, set `NEXT_PUBLIC_GUIDE_API_URL=http://localhost:8000` there (an empty value hides the panel). `ALLOWED_ORIGINS` defaults to `http://localhost:3000` here.

---

## API

### `POST /guide/stream`

요청 본문 / Request body:

| 필드 | 설명 |
|---|---|
| `requestId` | 클라이언트 UUID (`^[A-Za-z0-9_-]{1,64}$`). 로그 상관관계용 |
| `sessionId` | 브라우저 세션 UUID. 서버는 신뢰하지 않음 |
| `locale` | `ko` / `en`. 기본 응답 언어 |
| `message` | 사용자 질문 (200자 초과 시 `too_long`) |
| `context` | 선택. `{ view: "orbit" \| "tour", slug?, section? }` 현재 화면 |

응답은 SSE입니다. 클라이언트는 `EventSource`가 아니라 `fetch` 스트리밍으로 읽어야 합니다(POST 본문). / The response is SSE; read it with `fetch` streaming, not `EventSource`, because the request is a POST.

| 이벤트 / Event | 페이로드 / Payload |
|---|---|
| `tool_status` | `{ tool, key }` — 조회 중 표시용 사전 키 |
| `text_delta` | `{ text }` — 스트리밍 답변 |
| `action` | `{ type, ... }` — `focusArtist`, `openTour`, `highlightCity` (답변 끝에 한 번) |
| `retract` | `{ reason }` — 답변을 거두고 고정 문구로 교체 |
| `error` | `{ code }` — `rate_limited`, `off_topic`, `too_long`, `busy`, `session_limit`, `upstream`, `internal` (종료 이벤트, `done` 없음) |
| `done` | `{}` — 정상 종료 |

### `GET /health`

외부·LLM 호출이 없는 가벼운 엔드포인트입니다. 프런트가 패널을 열 때 한 번 불러 콜드 스타트를 미리 깨웁니다. / A lightweight endpoint with no external or LLM calls; the frontend calls it when the panel opens to warm a cold instance.

요청·이벤트·액션의 정확한 모양과 예시는 [`contracts/`](contracts)가 기준입니다 (`guide_events.py`, `ui_actions.md`, `fixtures/`).

The exact shapes and examples live in [`contracts/`](contracts).

---

## 환경 변수 / Environment Variables

| 변수 | 기본값 | 설명 |
|---|---|---|
| `ONSTAGE_URL` | (필수) | on-stage 주소. `/api/artists`를 서버에서 호출 |
| `OPENAI_API_KEY` | (필수) | 이 에이전트 전용 키. 운영은 Secret Manager |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS 허용 Origin (쉼표 구분, `*` 금지, 끝의 `/`는 제거됨) |
| `ALLOWED_ORIGIN_REGEX` | - | 프리뷰 도메인 패턴 |
| `OPENAI_MODEL` | `gpt-4.1-mini` | 메인 모델 |
| `CLASSIFIER_MODEL` | `gpt-4.1-mini` | L3 분류기 모델 |
| `OPENAI_TEMPERATURE` | - | 비우면 모델 기본값 |
| `TRUSTED_PROXY_HOPS` | `1` | `X-Forwarded-For` 오른쪽에서 몇 번째를 클라이언트 IP로 볼지 |
| `RATE_PER_MINUTE` | `5` | IP당 분당 요청 |
| `RATE_PER_IP_DAILY` | `30` | IP당 일일 요청 |
| `GLOBAL_DAILY` | `1000` | 전체 일일 요청 (킬스위치) |
| `SESSION_TTL_SECONDS` | `1800` | 세션 유휴 만료 |
| `SESSION_MAX` | `500` | 세션 최대 개수 (LRU) |
| `HISTORY_TURNS` | `6` | 세션당 저장 턴 |
| `SESSION_TURN_LIMIT` | `20` | 세션 턴 상한 |
| `TRACING_ENABLED` | `false` | 운영에서는 끈다 (대화 미저장 원칙) |

한도 수치는 시작값이며, 카운터는 서버 메모리라 재시작 시 초기화됩니다 (best-effort 방어, 최종 상한은 선불 잔액).

Limits are starting values; counters live in server memory and reset on restart (a best-effort defense — the final cap is the prepaid balance).

---

## 테스트 / Tests

```bash
uv run pytest -q                                 # LLM 호출 없음 / no LLM calls
uv run ruff check .
uv run --env-file .env pytest -m llm -q          # 실제 LLM 호출 (비용 발생) / real LLM calls (costs money)
uv run --env-file .env python scripts/measure_actions.py   # 액션 판단 8회 측정 / action stability, 8 runs each
```

LLM 테스트는 같은 입력도 결과가 흔들리므로 "3회 중 2회", "8회 중 6회"처럼 기준을 둡니다. 가드레일(분류기·출력 검사)과 액션 판단은 이 방식으로 검증했고, 측정 결과는 [docs/design.md](docs/design.md) §6.4에 있습니다.

LLM output varies run to run, so pass criteria are counted ("2 of 3", "6 of 8"). Guardrails (classifier, output check) and action selection are verified this way; measurements are in [docs/design.md](docs/design.md) §6.4.

---

## 배포 / Deployment

Cloud Run(서울, `max-instances=1`, `min-instances=0`)에 Dockerfile로 배포합니다. 절차, 시크릿 설정, 배포 후 확인(스트리밍 버퍼링, CORS, 클라이언트 IP 판별)은 [docs/deploy.md](docs/deploy.md)에 있습니다.

Deployed to Cloud Run (Seoul, `max-instances=1`, `min-instances=0`) from the Dockerfile. Steps, secret setup, and post-deploy checks (streaming buffering, CORS, client-IP detection) are in [docs/deploy.md](docs/deploy.md).

---

## 알려진 한계 / Known Limitations

- 출력 검사는 도시 코드·이름만 대조합니다. 날짜·트랙명·투어명 대조와 사전에 없는 도시는 잡지 못합니다.
- 아티스트 이름을 섞은 이탈 질문이나 영어 단어와 겹치는 이름("aurora borealis")은 규칙 필터를 통과해 메인 프롬프트의 거절에 의존합니다(확률적).
- 세션·한도 카운터는 서버 메모리라 재시작 시 사라지고, 인스턴스는 1대로 고정입니다.
- 도시 목록은 on-stage `GET /api/artists`의 대표 도시(`cities[]`)만 알 수 있어 "대표 도시"로 답합니다. 전체 공연 목록은 on-stage에 읽기 엔드포인트가 생기면 전환합니다.
- 분류기는 "의심스러우면 통과"라서 일부 이탈 질문은 메인까지 가서 모델 호출 비용이 듭니다(한도와 잔액이 상한).

The output check compares city codes and names only (no dates, track or tour names, or cities missing from the table). Off-topic questions that mention an artist, or names that collide with English words ("aurora borealis"), pass the rule filter and rely on the main prompt's refusal (probabilistic). Sessions and counters are in-memory and the service is pinned to one instance. Only on-stage's featured cities are known, so city lists are answered as "featured cities" until a full-shows read endpoint exists. The classifier passes when in doubt, so some off-topic questions reach the main model; limits and the prepaid balance bound the cost.

---

## 개발 프로세스 / Development Process

설계는 [docs/design.md](docs/design.md), 단계별 구현 계획은 [docs/superpowers/plans/](docs/superpowers/plans)에 있습니다. 1단계(Q&A·SSE·기본 한도)부터 2b(UI 액션), 3(가드레일), 4(세션·`busy`·`highlightCity`), 5(배포)까지 단계마다 설계 → 테스트 먼저 → 구현 → 실제 모델 확인 순서로 진행했고, on-stage와의 경계는 `contracts/`의 계약 파일과 골든 fixture로 맞췄습니다.

The design is in [docs/design.md](docs/design.md) and each stage's implementation plan is in [docs/superpowers/plans/](docs/superpowers/plans). Stages ran from 1 (Q&A, SSE, basic limits) through 2b (UI actions), 3 (guardrails), 4 (sessions, `busy`, `highlightCity`), to 5 (deployment), each as design → tests first → implementation → real-model verification. The boundary with on-stage is held by the contract files and golden fixtures in `contracts/`.

---

## 라이선스 / License

[MIT](LICENSE)

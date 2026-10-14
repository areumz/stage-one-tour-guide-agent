# stage-one-tour-guide-agent

STAGE.ONE A탭의 투어 가이드 에이전트 API. Python, FastAPI, OpenAI Agents SDK.
설계: [docs/design.md](docs/design.md)

## 실행

```bash
uv sync
cp .env.example .env   # OPENAI_API_KEY 입력
PYTHONPATH=src:. uv run --env-file .env uvicorn --factory tour_guide.main:build_app --port 8000
```

`PYTHONPATH=src:.` 는 editable 설치에 의존하지 않기 위한 것이다. macOS 에서 venv 의 `.pth` 파일에 `hidden` 플래그가 붙으면 Python 이 건너뛰어 `ModuleNotFoundError: tour_guide` 가 난다. 영구 해결은 `chflags nohidden .venv/lib/python*/site-packages/*.pth`.

## 확인

```bash
curl -s localhost:8000/health

curl -N -s localhost:8000/guide/stream \
  -H 'content-type: application/json' \
  -d '{"requestId":"r1","sessionId":"s1","locale":"ko","message":"AURORA 투어 일정 보여줘"}'
```

## 테스트

```bash
uv run pytest -q                                   # LLM 호출 없음
uv run --env-file .env pytest -m llm -q            # 실제 LLM 호출
uv run ruff check .
```

## 알아둘 점

- 속도 제한은 IP당 분당 5회(`RATE_PER_MINUTE`)이고, L2 에서 차단된 요청도 센다 (L1 이 L2 보다 먼저 실행되는 의도된 동작).
- 1단계 한계: 애매한 주제 이탈 질문은 메인 에이전트까지 가서 모델 호출 비용이 든다(정중히 거절은 함). 3단계 전에는 공개 배포하지 않는다.
- `X-Forwarded-For` 는 프록시 없이 노출하면 위조할 수 있다. 배포 구성에 맞게 `TRUSTED_PROXY_HOPS` 를 설정한다.
- 앱 로그(`guide done` / `guide cancelled` / `guide failed`)는 stderr 로 나오며 질문·답변 본문은 남기지 않는다.

## 상태

1단계(한·영 Q&A, SSE, L0·L1·L2). L3 분류기·출력 검사·세션 히스토리·UI 액션은 이후 단계이며, 그 전에는 공개 배포하지 않는다.

openai-agents 0.23.1 기준

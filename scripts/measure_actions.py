"""액션 안정성 측정 (실제 LLM 호출). 설계 §6.4, 계획 T5.

    uv run --env-file .env python scripts/measure_actions.py [--runs 8]
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from contracts.guide_events import (  # noqa: E402
    ActionEvent,
    FocusArtist,
    GuideRequest,
    HighlightCity,
    OpenTour,
    ViewContext,
)
from tests.conftest import MINI_RAW, TODAY  # noqa: E402

from tour_guide.agent import build_agent, stream_guide  # noqa: E402
from tour_guide.data import ArtistsCache  # noqa: E402

ORBIT = ViewContext(view="orbit")
TOUR_AURORA = ViewContext(view="tour", slug="aurora")

# (문장, 기대 액션 또는 None(액션 없음), 통과 기준, 화면)
CASES = [
    ("AURORA 투어 일정 보여줘", OpenTour(slug="aurora"), 6, ORBIT),
    ("오로라 투어 보여줘", OpenTour(slug="aurora"), 6, ORBIT),
    ("오로라 알려줘", FocusArtist(slug="aurora"), 6, ORBIT),
    ("aurora 알려줘", FocusArtist(slug="aurora"), 6, ORBIT),
    ("서울에서 누가 공연해?", None, 7, ORBIT),  # 대조군
    ("도쿄 공연은 언제 해?", HighlightCity(slug="aurora", city="TYO"), 6, TOUR_AURORA),
    ("AURORA 도쿄 공연은 언제 해?", FocusArtist(slug="aurora"), 6, ORBIT),  # 대조군: 궤도에서는 highlightCity 대신 focusArtist
]


async def run_once(agent, message: str, view: ViewContext):
    req = GuideRequest(requestId="m", sessionId="s", locale="ko", message=message, context=view)
    return [e.action async for e in stream_guide(agent, req) if isinstance(e, ActionEvent)]


async def main(runs: int) -> int:
    async def fetch():
        return MINI_RAW

    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    agent = build_agent(ArtistsCache(fetch), lambda: TODAY, model=model)
    print(f"model={model} runs={runs}")
    print(f"{'문장':<26}{'기대':<12}{'횟수':<8}{'기준':<6}결과")
    failed = False
    for message, expected, threshold, view in CASES:
        want = [expected] if expected else []
        hits = 0
        for _ in range(runs):
            hits += await run_once(agent, message, view) == want
        ok = hits >= threshold
        failed |= not ok
        label = f"{expected.type}" if expected else "no action"
        print(f"{message:<26}{label:<12}{f'{hits}/{runs}':<8}{f'{threshold}/{runs}':<6}{'PASS' if ok else 'FAIL'}")
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=8)
    sys.exit(asyncio.run(main(ap.parse_args().runs)))

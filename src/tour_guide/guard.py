"""L0(길이)·L2(규칙) 입력 방어. 토큰을 쓰지 않는다 (설계 §6).

주제 이탈을 키워드 블록리스트로 막지 않는다. 허용 목록은 이어지는 질문을 오탐하므로
명백한 인젝션만 막고(BLOCK), 명백한 투어 질문만 통과시키며(PASS), 나머지는 다음 계층에 맡긴다(AMBIGUOUS).
"""

import re
from enum import StrEnum

from contracts.artists import Artist
from contracts.guide_events import MAX_MESSAGE_CHARS

from tour_guide.data import city_names


class Verdict(StrEnum):
    BLOCK = "block"
    PASS = "pass"
    AMBIGUOUS = "ambiguous"


_BLOCK_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above)\s+(instructions?|prompts?)",
        r"(reveal|show|print|repeat|tell).{0,30}(system|developer)\s+(prompt|message|instructions?)",
        r"\byou\s+are\s+now\b",
        r"\bjailbreak\b",
        r"시스템\s*프롬프트",
        r"(이전|위|앞)\s*의?\s*(지시|명령|지침).{0,10}(무시|잊)",
        r"(역할|롤).{0,6}(바꿔|변경)",
    )
]

_TOPIC_KEYWORDS = (
    "투어", "공연", "콘서트", "일정", "티켓", "앨범", "노래", "아티스트", "도시",
    "tour", "show", "concert", "ticket", "schedule", "album", "song", "artist", "playing", "gig",
)


def check_length(message: str) -> bool:
    return len(message) <= MAX_MESSAGE_CHARS


def build_vocab(artists: list[Artist]) -> frozenset[str]:
    words = {a.name.lower() for a in artists} | {a.nameKo.lower() for a in artists}
    words |= {n.lower() for n in city_names(artists).values()}
    return frozenset(w for w in words if len(w) >= 2)


def classify(message: str, vocab: frozenset[str]) -> Verdict:
    if any(p.search(message) for p in _BLOCK_PATTERNS):
        return Verdict.BLOCK
    lowered = message.lower()
    if any(w in lowered for w in vocab) or any(k in lowered for k in _TOPIC_KEYWORDS):
        return Verdict.PASS
    return Verdict.AMBIGUOUS

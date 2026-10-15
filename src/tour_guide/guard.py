"""L0(길이)·L2(규칙) 입력 방어. (토큰 차감 x) (설계 §6).

주제 이탈을 키워드 블록리스트로 막지 않음 - 오탐 우려
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
    "투어", "공연", "콘서트", "일정", "티켓", "앨범", "노래", "아티스트",
    "tour", "show", "concert", "ticket", "schedule", "album", "song", "artist", "playing", "gig",
)


def check_length(message: str) -> bool:
    return len(message) <= MAX_MESSAGE_CHARS


def build_vocab(artists: list[Artist]) -> frozenset[str]:
    words = {a.name.lower() for a in artists} | {a.nameKo.lower() for a in artists}
    words |= {n.lower() for n in city_names(artists).values()}
    return frozenset(w for w in words if len(w) >= 2)


def _is_ascii_word(w: str) -> bool:
    return w.isascii()


def _word_re(words) -> re.Pattern | None:
    """영어 토큰용 단어 경계 정규식. 복수·소유격(s, 's)을 허용한다."""
    alts = sorted({re.escape(w) for w in words}, key=len, reverse=True)
    if not alts:
        return None
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(alts) + r")(?:'?s)?(?![a-z0-9])")


_EN_KEYWORDS = tuple(k for k in _TOPIC_KEYWORDS if _is_ascii_word(k))
_KO_KEYWORDS = tuple(k for k in _TOPIC_KEYWORDS if not _is_ascii_word(k))


def classify(message: str, vocab: frozenset[str]) -> Verdict:
    """순서는 고정: BLOCK(인젝션) -> PASS(어휘·키워드) -> AMBIGUOUS. 아티스트명이 있어도 BLOCK 이 먼저.

    영어(ASCII)는 단어 경계로, 한국어는 조사가 붙으므로 부분 문자열로 매칭한다.
    """
    if any(p.search(message) for p in _BLOCK_PATTERNS):
        return Verdict.BLOCK
    lowered = message.lower()
    en = _word_re([w for w in vocab if _is_ascii_word(w)] + list(_EN_KEYWORDS))
    ko = [w for w in vocab if not _is_ascii_word(w)] + list(_KO_KEYWORDS)
    if (en and en.search(lowered)) or any(w in lowered for w in ko):
        return Verdict.PASS
    return Verdict.AMBIGUOUS


# 도시 코드 -> 영문명 (계약에 영문명 필드가 없어 서버가 보관, 설계 §12 #10)
CITY_EN = {
    "LA": "Los Angeles", "LDN": "London", "SEO": "Seoul", "TYO": "Tokyo", "BUS": "Busan",
    "BKK": "Bangkok", "DGU": "Daegu", "DJN": "Daejeon", "HKG": "Hong Kong", "ICN": "Incheon",
    "MAD": "Madrid", "OSA": "Osaka", "SIN": "Singapore", "TPE": "Taipei",
}


def cities_in(text: str, city_table: dict[str, str]) -> set[str]:
    """텍스트에 나온 도시 코드. 코드는 대문자 단어 경계, 영문명은 대소문자 무시 단어 경계, 한글명은 부분 문자열."""
    found = set()
    for code, ko in city_table.items():
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(code)}(?![A-Za-z0-9])", text):
            found.add(code)
            continue
        en = CITY_EN.get(code)
        if en and re.search(rf"(?<![a-z0-9]){re.escape(en.lower())}(?![a-z0-9])", text.lower()):
            found.add(code)
        elif ko and ko in text:
            found.add(code)
    return found


def check_output(text: str, allowed_cities: set[str], city_table: dict[str, str]) -> bool:
    """답변에 허용 집합 밖 도시가 있으면 False (설계 §6.2)."""
    return cities_in(text, city_table) <= allowed_cities

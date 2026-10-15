"""추천 칩 문구가 L0·L2 를 통과하는지 확인한다. 목록은 on-stage 가 준다 (설계 §14.6 H4)."""

import json
from pathlib import Path

import pytest
from contracts.artists import ArtistsResponse

from tests.conftest import MINI_RAW
from tour_guide.guard import Verdict, build_vocab, check_length, classify

CHIPS = Path(__file__).resolve().parents[1] / "contracts" / "fixtures" / "chips.json"


def _chips():
    if not CHIPS.exists():
        return []
    data = json.loads(CHIPS.read_text(encoding="utf-8"))
    return [c for texts in data.values() for c in texts]


@pytest.mark.skipif(not CHIPS.exists(), reason="on-stage 칩 문구 목록이 아직 없다 (H4)")
def test_chip_texts_pass_length_and_are_not_blocked_by_l2():
    vocab = build_vocab(ArtistsResponse.model_validate(MINI_RAW).artists)
    for text in _chips():
        assert check_length(text), text
        assert classify(text, vocab) is not Verdict.BLOCK, text

"""User-supplied patterns cannot run for an unbounded time.

Python's `re` backtracks, so `(a+)+$` against a non-matching string takes
exponential time — measurably seconds at 26 characters. A regex cannot be
interrupted once it is running, so no timeout can help; the thread is gone
until it returns. These patterns run once per device or entity and the search
box fires one per settled keystroke, so a single bad pattern is multiplied by
the size of the registry.

RE2 does not backtrack, which makes this structurally impossible rather than
merely bounded.
"""

import re
import time

import pytest

from home_curator.user_regex import UserPatternError, compile_user_pattern

# Long enough that plain `re` takes well over the threshold below, short
# enough not to add noticeable time to the suite. Each extra character
# roughly doubles `re`'s work.
CATASTROPHIC = r"(a+)+$"
DEFEATING_INPUT = "a" * 24 + "b"


def test_a_catastrophic_pattern_returns_immediately():
    compiled = compile_user_pattern(CATASTROPHIC)

    started = time.perf_counter()
    compiled.search(DEFEATING_INPUT)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.5, f"took {elapsed:.2f}s — backtracking is not bounded"


def test_the_same_pattern_is_genuinely_slow_under_python_re():
    """Pins the premise: without this change the input above really does hang.

    If `re` ever stopped backtracking, the test above would prove nothing.
    """
    started = time.perf_counter()
    re.search(CATASTROPHIC, DEFEATING_INPUT)
    elapsed = time.perf_counter() - started

    assert elapsed > 0.25, (
        f"plain `re` finished in {elapsed:.2f}s — the premise no longer holds"
    )


# --- ordinary patterns are unaffected ------------------------------------


@pytest.mark.parametrize(
    ("pattern", "text", "expected"),
    [
        (r"^kitchen_", "kitchen_lamp", True),
        (r"^kitchen_", "hall_lamp", False),
        (r"(?i)lamp", "Living Room LAMP", True),
        (r"^[a-z]+_[0-9]+$", "light_1", True),
        (r"lamp|switch", "porch switch", True),
    ],
)
def test_ordinary_patterns_behave_as_expected(pattern, text, expected):
    assert bool(compile_user_pattern(pattern).search(text)) is expected


def test_substitution_still_works():
    assert compile_user_pattern(r"^old_").sub("new_", "old_lamp") == "new_lamp"


# --- what RE2 gives up, and how it says so -------------------------------


def test_a_malformed_pattern_is_rejected_clearly():
    with pytest.raises(UserPatternError, match="invalid regex"):
        compile_user_pattern("[")


@pytest.mark.parametrize("pattern", [r"^(?!test_)", r"(?=x)", r"(?<=x)y"])
def test_lookaround_is_rejected_with_an_explanation(pattern):
    """Unsupported on purpose: lookaround is what requires backtracking."""
    with pytest.raises(UserPatternError, match="Lookahead and lookbehind"):
        compile_user_pattern(pattern)


def test_backreferences_are_rejected_with_an_explanation():
    with pytest.raises(UserPatternError, match="Backreferences"):
        compile_user_pattern(r"(\w+)\s\1")


def test_every_builtin_preset_still_compiles():
    """The presets go through the same engine as user patterns."""
    from home_curator.rules.naming_convention import PRESET_TO_PATTERN

    for name, pattern in PRESET_TO_PATTERN.items():
        assert compile_user_pattern(pattern) is not None, name


def test_presets_match_exactly_what_python_re_matched():
    """Guards against RE2 silently changing preset behaviour."""
    from home_curator.rules.naming_convention import PRESET_TO_PATTERN

    corpus = [
        "Living Room Lamp", "Clara's Bedroom", "En-Suite", "AP", "Side Lamp 2",
        "Mum and Dad's Bedroom", "Hub (Local)", "Hub (CC:8D:A2:50:E6:7E)",
        "not title", "living_room_lamp", "living-room-lamp", "garage_light_1",
    ]
    for pattern in PRESET_TO_PATTERN.values():
        reference = re.compile(pattern)
        candidate = compile_user_pattern(pattern)
        for text in corpus:
            assert bool(candidate.match(text)) is bool(reference.match(text)), (
                f"{pattern!r} disagrees on {text!r}"
            )

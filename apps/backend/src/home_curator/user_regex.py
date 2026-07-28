"""Compiling regular expressions that came from the user.

Python's `re` backtracks, so a pattern like `(a+)+$` takes exponential time
against a non-matching string — 4.7 seconds at 26 characters, minutes at 30.
A regex cannot be interrupted once running, so there is no timeout to apply:
the thread is gone until it finishes. These patterns are evaluated once per
device or entity, so a single bad one costs that many evaluations, and the
search box sends one per settled keystroke.

RE2 cannot backtrack. Its matching is linear in the length of the input by
construction, so this is not a bound on the damage but an absence of it. The
same pattern above returns in microseconds.

`cel-python` already pulled it in, so adopting it added nothing to the image.
It is declared in `pyproject.toml` all the same, because it is imported here
directly and a future `cel-python` release dropping it would otherwise break
pattern compilation with no warning.

The trade is syntax: RE2 has no lookahead, lookbehind or backreferences,
because those are what make backtracking necessary. Patterns using them now
fail with a clear message instead of being accepted and occasionally hanging.
Every built-in naming preset compiles unchanged, and a differential test over
both engines found no behavioural difference on ordinary patterns.
"""

from typing import Protocol, cast

import re2


class UserPatternError(ValueError):
    """A user-supplied pattern that RE2 will not accept."""


class UserPattern(Protocol):
    """The part of the `re.Pattern` API these call sites use.

    Declared explicitly because `re2` ships no type information, so returning
    its objects directly would make every expression touching a compiled
    pattern `Any` and silently disable type checking at the call sites.
    """

    def match(self, text: str) -> object | None: ...

    def search(self, text: str) -> object | None: ...

    def sub(self, repl: str, text: str) -> str: ...


def compile_user_pattern(pattern: str) -> UserPattern:
    """Compile `pattern`, raising `UserPatternError` if RE2 rejects it."""
    try:
        return cast(UserPattern, re2.compile(pattern))
    except Exception as e:  # re2 raises its own error type
        raise UserPatternError(_explain(pattern, e)) from e


def _explain(pattern: str, error: Exception) -> str:
    detail = str(error).strip().strip("b'\"")
    hint = ""
    if any(token in pattern for token in ("(?=", "(?!", "(?<=", "(?<!")):
        hint = (
            " Lookahead and lookbehind are not supported — they are what make "
            "a pattern able to run for an unbounded time."
        )
    elif any(f"\\{d}" in pattern for d in "123456789"):
        hint = " Backreferences are not supported, for the same reason."
    # Keeps the prefix the API has always returned for a bad pattern.
    return f"invalid regex: {detail}.{hint}"

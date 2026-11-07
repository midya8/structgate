"""Incremental JSON-subset validator with exact allowed-next-token sets.

The validator is a stack-based state machine over a character stream. Given any
prefix it answers two questions exactly:

- is the prefix a valid *partial* JSON document (i.e. it can still be extended to
  a complete one), and
- which next characters keep it valid (`allowed`).

Generation code uses `allowed` to mask a model's next-token distribution so every
emitted character stays inside the grammar. The machine handles objects, arrays,
strings with escapes, numbers per the JSON grammar, the true/false/null literals,
and insignificant whitespace. State is a small immutable snapshot so tests can
save and restore it.
"""

from __future__ import annotations

from typing import FrozenSet, List, Optional, Sequence, Tuple

WS = frozenset(" \t\n\r")
DIGITS = frozenset("0123456789")
NONZERO = frozenset("123456789")
HEX = frozenset("0123456789abcdefABCDEF")

# Structural modes.
EXPECT_VALUE = "expect_value"
EXPECT_KEY = "expect_key"
EXPECT_COLON = "expect_colon"
EXPECT_COMMA = "expect_comma"
IN_STRING = "in_string"
IN_NUMBER = "in_number"
IN_LITERAL = "in_literal"
DONE = "done"


class JSONValidator:
    """Streaming validator for one JSON document."""

    def __init__(self) -> None:
        # Stack of frames: ["obj", phase, first] or ["arr", phase, first].
        # phase is one of EXPECT_KEY/EXPECT_COLON/EXPECT_VALUE/EXPECT_COMMA.
        self._stack: List[list] = []
        self._mode: str = EXPECT_VALUE
        self._str_role: Optional[str] = None  # "key" or "value"
        self._str_escape: bool = False
        self._str_unicode: int = 0  # remaining \uXXXX hex digits
        self._num_state: str = ""  # int_start, int, zero, frac_start, frac, exp_start, exp_sign, exp
        self._literal: str = ""  # remaining literal text, e.g. "rue"
        self._failed: bool = False

    # -- introspection ---------------------------------------------------

    @property
    def failed(self) -> bool:
        return self._failed

    @property
    def complete(self) -> bool:
        """True when the fed prefix is a complete JSON document."""
        return not self._failed and self._mode == DONE

    @property
    def extendable(self) -> bool:
        """True when the fed prefix can still be extended to a complete document."""
        return not self._failed and self._mode != DONE

    def snapshot(self) -> Tuple:
        return (
            tuple(tuple(f) for f in self._stack),
            self._mode,
            self._str_role,
            self._str_escape,
            self._str_unicode,
            self._num_state,
            self._literal,
            self._failed,
        )

    def restore(self, snap: Tuple) -> None:
        stack, mode, role, esc, uni, num, lit, failed = snap
        self._stack = [list(f) for f in stack]
        self._mode = mode
        self._str_role = role
        self._str_escape = esc
        self._str_unicode = uni
        self._num_state = num
        self._literal = lit
        self._failed = failed

    # -- core step ---------------------------------------------------------

    def advance(self, ch: str) -> bool:
        """Feed one character; return True iff the prefix stays valid."""
        if self._failed:
            return False
        if not self._step(ch):
            self._failed = True
            return False
        return True

    def feed(self, text: str) -> bool:
        ok = True
        for ch in text:
            ok = self.advance(ch) and ok
        return ok

    def allowed(self, vocab: Sequence[str]) -> FrozenSet[str]:
        """Exact set of next characters that keep the prefix valid."""
        out = []
        for ch in vocab:
            snap = self.snapshot()
            if self._step(ch):
                out.append(ch)
            self.restore(snap)
        return frozenset(out)

    # -- internals ---------------------------------------------------------

    def _top(self) -> Optional[list]:
        return self._stack[-1] if self._stack else None

    def _close_value(self) -> bool:
        """A value just completed; advance the enclosing context."""
        top = self._top()
        if top is None:
            self._mode = DONE
            return True
        top[1] = EXPECT_COMMA
        self._mode = EXPECT_COMMA
        return True

    def _step(self, ch: str) -> bool:
        if self._mode == IN_STRING:
            return self._step_string(ch)
        if self._mode == IN_NUMBER:
            return self._step_number(ch)
        if self._mode == IN_LITERAL:
            return self._step_literal(ch)
        if self._mode == DONE:
            return ch in WS

        # Structural modes: whitespace is always insignificant here.
        if ch in WS:
            return True

        if self._mode == EXPECT_VALUE:
            if ch == "{":
                self._stack.append(["obj", EXPECT_KEY, True])
                self._mode = EXPECT_KEY
                return True
            if ch == "[":
                self._stack.append(["arr", EXPECT_VALUE, True])
                self._mode = EXPECT_VALUE
                return True
            if ch == '"':
                self._mode = IN_STRING
                self._str_role = "value"
                self._str_escape = False
                self._str_unicode = 0
                return True
            if ch == "-" or ch in DIGITS:
                self._mode = IN_NUMBER
                self._num_state = "int" if ch != "-" else "int_start"
                if ch == "0":
                    self._num_state = "zero"
                return True
            if ch in "tfn":
                self._mode = IN_LITERAL
                self._literal = {"t": "rue", "f": "alse", "n": "ull"}[ch]
                return True
            # empty container close
            top = self._top()
            if top is not None and top[0] == "arr" and top[2] and ch == "]":
                self._stack.pop()
                return self._close_value()
            return False

        if self._mode == EXPECT_KEY:
            top = self._top()
            if ch == '"':
                self._mode = IN_STRING
                self._str_role = "key"
                self._str_escape = False
                self._str_unicode = 0
                return True
            if top is not None and top[2] and ch == "}":
                self._stack.pop()
                return self._close_value()
            return False

        if self._mode == EXPECT_COLON:
            if ch == ":":
                top = self._top()
                top[1] = EXPECT_VALUE
                self._mode = EXPECT_VALUE
                return True
            return False

        if self._mode == EXPECT_COMMA:
            top = self._top()
            if top is None:
                return False
            if ch == ",":
                if top[0] == "obj":
                    top[1] = EXPECT_KEY
                    top[2] = False
                    self._mode = EXPECT_KEY
                else:
                    top[1] = EXPECT_VALUE
                    top[2] = False
                    self._mode = EXPECT_VALUE
                return True
            if ch == "}" and top[0] == "obj":
                self._stack.pop()
                return self._close_value()
            if ch == "]" and top[0] == "arr":
                self._stack.pop()
                return self._close_value()
            return False

        return False

    def _step_string(self, ch: str) -> bool:
        if self._str_unicode:
            if ch not in HEX:
                return False
            self._str_unicode -= 1
            return True
        if self._str_escape:
            if ch in '"\\/bfnrt':
                self._str_escape = False
                return True
            if ch == "u":
                self._str_escape = False
                self._str_unicode = 4
                return True
            return False
        if ch == "\\":
            self._str_escape = True
            return True
        if ch == '"':
            # String closed; resolve by role.
            if self._str_role == "key":
                top = self._top()
                top[1] = EXPECT_COLON
                self._mode = EXPECT_COLON
            else:
                self._close_value()
            self._str_role = None
            return True
        if ord(ch) < 0x20:
            return False  # control characters must be escaped
        return True

    def _step_number(self, ch: str) -> bool:
        st = self._num_state
        cont = False
        if st == "int_start":
            if ch in NONZERO:
                self._num_state = "int"
                cont = True
            elif ch == "0":
                self._num_state = "zero"
                cont = True
        elif st == "int":
            if ch in DIGITS:
                cont = True
        elif st == "zero":
            cont = False
        elif st == "frac_start":
            if ch in DIGITS:
                self._num_state = "frac"
                cont = True
        elif st == "frac":
            if ch in DIGITS:
                cont = True
        elif st == "exp_start":
            if ch in "+-":
                self._num_state = "exp_sign"
                cont = True
            elif ch in DIGITS:
                self._num_state = "exp"
                cont = True
        elif st == "exp_sign":
            if ch in DIGITS:
                self._num_state = "exp"
                cont = True
        elif st == "exp":
            if ch in DIGITS:
                cont = True
        if not cont and st in ("int", "zero", "frac", "exp"):
            if ch == "." and st in ("int", "zero"):
                self._num_state = "frac_start"
                return True
            if ch in "eE" and st in ("int", "zero", "frac"):
                self._num_state = "exp_start"
                return True
        if cont:
            return True
        # Number ends only on a structural boundary; reprocess the character.
        if st in ("int", "zero", "frac", "exp"):
            snap = (self._num_state,)
            self._close_value()
            if self._mode == DONE:
                # Top-level number: only whitespace or EOF may follow.
                self._num_state = snap[0]
                self._mode = DONE
                return ch in WS
            self._num_state = ""
            return self._step(ch)
        return False

    def _step_literal(self, ch: str) -> bool:
        if not self._literal or ch != self._literal[0]:
            return False
        self._literal = self._literal[1:]
        if not self._literal:
            self._close_value()
        return True


def valid_json(text: str) -> bool:
    """True iff text is a complete JSON document per this machine."""
    v = JSONValidator()
    v.feed(text)
    if v.failed:
        return False
    if v._mode == IN_NUMBER and v._num_state in ("int", "zero", "frac", "exp"):
        v._close_value()
    return v._mode == DONE

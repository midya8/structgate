"""Closed-schema constraints layered on the JSON grammar.

A schema is a fixed record shape: required keys in a fixed order, each with a
type slot ("string", "number", "bool"), no additional keys. The validator tracks
where the prefix sits inside that shape and computes allowed next characters
against both JSON grammar and schema position, so a constrained generator emits
records that parse *and* conform.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence, Tuple


class Schema:
    def __init__(self, fields: Sequence[Tuple[str, str]]):
        if not fields:
            raise ValueError("schema needs at least one field")
        names = [n for n, _ in fields]
        if len(set(names)) != len(names):
            raise ValueError("duplicate field names")
        for _, t in fields:
            if t not in ("string", "number", "bool"):
                raise ValueError(f"unknown slot type: {t}")
        self.fields = list(fields)


class SchemaValidator:
    """Streaming validator for one schema-conforming record.

    Mode machine over the JSON token stream with schema position: which field
    (or pre/post document) the prefix is in, and inside a slot, how far the
    token has progressed. Character sets are returned exactly per position.
    """

    def __init__(self, schema: Schema):
        self.schema = schema
        # pos: index into fields, or -1 before '{', or len(fields) after last field
        self._pos = -1
        self._phase = "open"  # open, key, key_str, colon, value, comma, close, done
        self._key_chars = 0   # chars consumed of current key's quoted form
        self._str_escape = False
        self._num_state = ""
        self._literal = ""
        self._failed = False
        self._keys_seen: List[str] = []

    @property
    def failed(self) -> bool:
        return self._failed

    @property
    def complete(self) -> bool:
        return not self._failed and self._phase == "done"

    @property
    def keys_seen(self) -> List[str]:
        return list(self._keys_seen)

    def _ws_or(self, chars: str) -> str:
        return chars + " \t\n\r"

    def _quoted_key(self, i: int) -> str:
        return '"' + self.schema.fields[i][0] + '"'

    def allowed(self, vocab: Sequence[str]) -> frozenset:
        if self._failed:
            return frozenset()
        out = []
        for ch in vocab:
            if self._would_accept(ch):
                out.append(ch)
        return frozenset(out)

    def _would_accept(self, ch: str) -> bool:
        snap = self.__dict__.copy()
        snap["_keys_seen"] = list(self._keys_seen)
        ok = self._step(ch)
        self.__dict__.update(snap)
        return ok

    def advance(self, ch: str) -> bool:
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

    _WS_PHASES = ("open", "key", "colon", "value", "comma", "done")

    def _step(self, ch: str) -> bool:
        if ch in " \t\n\r" and self._phase in self._WS_PHASES:
            return True
        if self._phase == "open":
            if ch == "{":
                self._phase = "key" if self.schema.fields else "close"
                self._pos = 0
                return True
            return False
        if self._phase == "key":
            if ch == '"':
                self._phase = "key_str"
                self._key_chars = 0
                return True
            return False
        if self._phase == "key_str":
            key = self.schema.fields[self._pos][0]
            if self._key_chars < len(key) and ch == key[self._key_chars]:
                self._key_chars += 1
                return True
            if self._key_chars == len(key) and ch == '"':
                self._phase = "colon"
                return True
            return False
        if self._phase == "colon":
            if ch == ":":
                self._phase = "value"
                return True
            return False
        if self._phase == "value":
            typ = self.schema.fields[self._pos][1]
            if typ == "string":
                if ch == '"':
                    self._phase = "value_str"
                    self._str_escape = False
                    return True
                return False
            if typ == "number":
                if ch == "-" or ch in "0123456789":
                    self._phase = "value_num"
                    self._num_state = "int_start" if ch == "-" else ("zero" if ch == "0" else "int")
                    return True
                return False
            if typ == "bool":
                if ch in "tf":
                    self._phase = "value_lit"
                    self._literal = "rue" if ch == "t" else "alse"
                    return True
                return False
            return False
        if self._phase == "value_str":
            if self._str_escape:
                self._str_escape = False
                return ch in '"\\/bfnrt'
            if ch == "\\":
                self._str_escape = True
                return True
            if ch == '"':
                self._keys_seen.append(self.schema.fields[self._pos][0])
                self._phase = "comma"
                return True
            if ord(ch) < 0x20:
                return False
            return True
        if self._phase == "value_num":
            st = self._num_state
            cont = False
            if st == "int_start":
                if ch in "123456789":
                    self._num_state = "int"; cont = True
                elif ch == "0":
                    self._num_state = "zero"; cont = True
            elif st == "int":
                cont = ch in "0123456789"
            elif st == "frac_start":
                if ch in "0123456789":
                    self._num_state = "frac"; cont = True
            elif st == "frac":
                cont = ch in "0123456789"
            elif st == "exp_start":
                if ch in "+-":
                    self._num_state = "exp_sign"; cont = True
                elif ch in "0123456789":
                    self._num_state = "exp"; cont = True
            elif st == "exp_sign":
                if ch in "0123456789":
                    self._num_state = "exp"; cont = True
            elif st == "exp":
                cont = ch in "0123456789"
            if not cont and st in ("int", "zero"):
                if ch == ".":
                    self._num_state = "frac_start"; return True
                if ch in "eE":
                    self._num_state = "exp_start"; return True
            if not cont and st in ("int", "zero", "frac", "exp"):
                # number ends; reprocess as structural
                self._keys_seen.append(self.schema.fields[self._pos][0])
                self._phase = "comma"
                self._num_state = ""
                return self._step(ch)
            return cont
        if self._phase == "value_lit":
            if not self._literal or ch != self._literal[0]:
                return False
            self._literal = self._literal[1:]
            if not self._literal:
                self._keys_seen.append(self.schema.fields[self._pos][0])
                self._phase = "comma"
            return True
        if self._phase == "comma":
            if ch == ",":
                if self._pos + 1 < len(self.schema.fields):
                    self._pos += 1
                    self._phase = "key"
                    return True
                return False  # no additional keys allowed
            if ch == "}":
                if self._pos == len(self.schema.fields) - 1:
                    self._phase = "done"
                    return True
                return False  # missing required keys
            return False
        if self._phase == "done":
            return False
        return False


def conforms(text: str, schema: Schema) -> Dict:
    """Parse and conformance-check a complete document. Returns a report dict."""
    try:
        obj = json.loads(text)
    except Exception:
        return {"parses": False, "conforms": False, "problems": ["invalid JSON"]}
    problems = []
    if not isinstance(obj, dict):
        return {"parses": True, "conforms": False, "problems": ["not an object"]}
    want = [n for n, _ in schema.fields]
    if list(obj.keys()) != want:
        problems.append(f"keys {list(obj.keys())} != required order {want}")
    for name, typ in schema.fields:
        if name not in obj:
            continue
        val = obj[name]
        ok = (
            (typ == "string" and isinstance(val, str))
            or (typ == "number" and isinstance(val, (int, float)) and not isinstance(val, bool))
            or (typ == "bool" and isinstance(val, bool))
        )
        if not ok:
            problems.append(f"field {name!r} is not {typ}")
    return {"parses": True, "conforms": not problems, "problems": problems}


RECORD_SCHEMA = Schema([
    ("active", "bool"),
    ("city", "string"),
    ("name", "string"),
    ("score", "number"),
])

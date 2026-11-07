import json
import unittest

from structgate.grammar import JSONValidator, valid_json


class TestAgainstStdlib(unittest.TestCase):
    CASES = [
        '{"a": 1}', '{"a": [1, 2, {"b": null}]}', "[]", "{}", "[1,]", '{"a":}',
        '{"a" 1}', "01", "1.5e+3", "-0.25", '"a\\n"', '"a\\q"', "true", "tru",
        "[true, false, null]", '{"k":"v","k2":2}', "  {  }  ", "1e", "2.", "0",
        '"x"', "[[]]", '{"a":{"b":{"c":[[]]}}}', '"\\u00e9"', "1e-2", "1E+2",
        "-0", "0.0", "[1 ,2]", '{"a":1,"b":2}', '["}', '{"a":01}', "--1", "+1",
    ]

    def test_matches_stdlib_json(self):
        for text in self.CASES:
            try:
                json.loads(text)
                want = True
            except Exception:
                want = False
            self.assertEqual(valid_json(text), want, text)

    def test_prefix_states(self):
        v = JSONValidator()
        self.assertTrue(v.feed('{"a": [1'))
        self.assertTrue(v.extendable)
        self.assertFalse(v.complete)
        self.assertTrue(v.feed(", 2]}"))
        self.assertTrue(v.complete)

    def test_failed_prefix_stays_failed(self):
        v = JSONValidator()
        self.assertTrue(v.feed("{"))
        self.assertFalse(v.advance("1"))
        self.assertFalse(v.advance('"'))


class TestAllowedSets(unittest.TestCase):
    def allowed(self, prefix, vocab):
        v = JSONValidator()
        self.assertTrue(v.feed(prefix))
        return v.allowed(vocab)

    def test_after_open_brace(self):
        al = self.allowed("{", ['"', "}", "{", "[", "a", " ", "1"])
        self.assertIn('"', al)
        self.assertIn("}", al)  # empty object
        self.assertNotIn("{", al)  # keys must be strings
        self.assertNotIn("1", al)

    def test_after_value_position(self):
        al = self.allowed('{"a": ', ['"', "{", "[", "1", "t", "}", ","])
        for ch in ['"', "{", "[", "1", "t"]:
            self.assertIn(ch, al)
        self.assertNotIn("}", al)
        self.assertNotIn(",", al)

    def test_number_continuation(self):
        al = self.allowed("[1", ["5", ".", "e", ",", "]"])
        for ch in ["5", ".", "e", ",", "]"]:
            self.assertIn(ch, al)

    def test_leading_zero_blocks_digit(self):
        al = self.allowed("[0", ["5", ".", ",", "]"])
        self.assertNotIn("5", al)
        for ch in [".", ",", "]"]:
            self.assertIn(ch, al)

    def test_done_accepts_only_ws(self):
        al = self.allowed("{}", [" ", "x", "{"])
        self.assertEqual(al, frozenset({" "}))

    def test_snapshot_restore(self):
        v = JSONValidator()
        v.feed('{"a": [')
        snap = v.snapshot()
        al1 = v.allowed(['"', "1", "]"])
        v.restore(snap)
        al2 = v.allowed(['"', "1", "]"])
        self.assertEqual(al1, al2)


if __name__ == "__main__":
    unittest.main()

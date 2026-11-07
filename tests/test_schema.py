import unittest

from structgate.schema import RECORD_SCHEMA, Schema, SchemaValidator, conforms


def feed(text):
    v = SchemaValidator(RECORD_SCHEMA)
    v.feed(text)
    return v


class TestSchemaValidator(unittest.TestCase):
    GOOD = '{"active": true, "city": "oslo", "name": "ada lovelace", "score": 91.5}'

    def test_good_record_completes(self):
        v = feed(self.GOOD)
        self.assertTrue(v.complete)
        self.assertFalse(v.failed)

    def test_whitespace_anywhere_structural(self):
        v = feed('{ \n\t"active" : false ,\n "city":"x", "name":"y", "score":0.5 }')
        self.assertTrue(v.complete)

    def test_wrong_key_order_fails(self):
        v = feed('{"city": "oslo"')
        self.assertTrue(v.failed)

    def test_wrong_type_fails_fast(self):
        v = feed('{"active": "yes"')
        self.assertTrue(v.failed)

    def test_extra_key_rejected(self):
        v = feed(self.GOOD[:-1] + ', "extra": 1}')
        self.assertTrue(v.failed)

    def test_missing_key_rejected(self):
        v = feed('{"active": true, "city": "x", "name": "y"}')
        self.assertTrue(v.failed)

    def test_number_whitespace_boundary(self):
        # Regression: ws inside a number token must close it, not continue it.
        v = feed('{"active": true, "city": "x", "name": "y", "score": 33.18 625839}')
        self.assertTrue(v.failed)

    def test_key_allowed_set_exact(self):
        v = feed('{"active": false, ')
        al = v.allowed(list('"aceilnty }'))
        self.assertEqual(al, frozenset({'"', " "}))

    def test_bool_slot_letters(self):
        v = feed('{"active": ')
        al = v.allowed(list("tfn01\" "))
        self.assertEqual(al, frozenset({"t", "f", " "}))


class TestConforms(unittest.TestCase):
    def test_good(self):
        r = conforms(TestSchemaValidator.GOOD, RECORD_SCHEMA)
        self.assertTrue(r["conforms"], r["problems"])

    def test_type_mismatch_named(self):
        r = conforms('{"active": 1, "city": "x", "name": "y", "score": 0.5}', RECORD_SCHEMA)
        self.assertFalse(r["conforms"])
        self.assertIn("active", r["problems"][0])

    def test_invalid_json(self):
        self.assertFalse(conforms("{nope", RECORD_SCHEMA)["parses"])


if __name__ == "__main__":
    unittest.main()

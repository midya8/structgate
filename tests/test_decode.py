import random
import unittest

from structgate.corpus import generate_corpus, vocabulary
from structgate.decode import generate
from structgate.grammar import valid_json
from structgate.model import CharNGram


def fixture_model():
    docs = generate_corpus(200)
    m = CharNGram(3, vocabulary(docs), smoothing=0.05)
    m.train(docs)
    return m


class TestConstrainedGeneration(unittest.TestCase):
    def test_constrained_always_valid(self):
        m = fixture_model()
        for i in range(40):
            r = generate(m, random.Random(1000 + i), constrained=True)
            self.assertTrue(r["complete"], r["text"][:80])
            self.assertTrue(valid_json(r["text"]))

    def test_unconstrained_fixture_fails_often(self):
        # Negative control: without the mask the same model and seeds leave the
        # grammar for the large majority of draws. If this ever flips, the
        # fixture stopped exercising the constraint.
        m = fixture_model()
        invalid = 0
        for i in range(40):
            r = generate(m, random.Random(1000 + i), constrained=False)
            if not (r["complete"] and valid_json(r["text"])):
                invalid += 1
        self.assertGreaterEqual(invalid, 30)

    def test_kl_recorded_only_when_masked(self):
        m = fixture_model()
        c = generate(m, random.Random(7), constrained=True)
        u = generate(m, random.Random(7), constrained=False)
        self.assertGreater(c["mean_kl"], 0.0)
        self.assertEqual(u["mean_kl"], 0.0)


if __name__ == "__main__":
    unittest.main()

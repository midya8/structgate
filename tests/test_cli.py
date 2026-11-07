import io
import json
import unittest
from contextlib import redirect_stdout

from structgate.cli import main
from structgate.eval import build_model, run_evaluation


def run_cli(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(list(argv))
    return code, buf.getvalue()


class TestEvaluateCommand(unittest.TestCase):
    def test_terminal_report(self):
        code, out = run_cli("evaluate")
        self.assertEqual(code, 0)
        self.assertIn("grammar", out)
        self.assertIn("schema", out)
        self.assertIn("40/40", out)

    def test_json_report(self):
        code, out = run_cli("evaluate", "--format", "json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["modes"]["grammar"]["valid"], 40)
        self.assertEqual(data["modes"]["none"]["valid"], 3)
        self.assertEqual(data["modes"]["schema"]["valid"], 40)

    def test_markdown_report(self):
        code, out = run_cli("evaluate", "--format", "markdown")
        self.assertEqual(code, 0)
        self.assertIn("| grammar | 40/40 | 1.00 |", out)


class TestGatesCommand(unittest.TestCase):
    def test_achievable_gates_pass(self):
        code, out = run_cli("gates", "--min-valid-rate", "1.0",
                            "--min-conformance", "1.0", "--max-mean-kl", "2.0",
                            "--max-unconstrained-rate", "0.2")
        self.assertEqual(code, 0)
        self.assertIn("All gates passed", out)

    def test_impossible_gate_fails(self):
        code, out = run_cli("gates", "--max-mean-kl", "0.5")
        self.assertEqual(code, 1)
        self.assertIn("GATE FAILURES", out)

    def test_control_gate_fails_when_control_too_good(self):
        code, out = run_cli("gates", "--max-unconstrained-rate", "0.05")
        self.assertEqual(code, 1)
        self.assertIn("unconstrained", out)


class TestDeterminism(unittest.TestCase):
    def test_repeated_evaluation_identical(self):
        m1 = build_model()
        m2 = build_model()
        r1 = run_evaluation(m1)
        r2 = run_evaluation(m2)
        self.assertEqual(r1, r2)

    def test_pinned_fixture_numbers(self):
        results = run_evaluation(build_model())
        modes = results["modes"]
        self.assertEqual(modes["grammar"]["valid"], 40)
        self.assertEqual(modes["schema"]["valid"], 40)
        self.assertEqual(modes["none"]["valid"], 3)
        self.assertAlmostEqual(modes["grammar"]["mean_kl"], 1.3496, places=4)
        self.assertAlmostEqual(modes["schema"]["mean_kl"], 0.8209, places=4)


if __name__ == "__main__":
    unittest.main()

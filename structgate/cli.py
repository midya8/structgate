"""StructGate command-line interface.

Commands:
  evaluate  Run the three-mode conformance evaluation and report.
  gates     Evaluate and enforce policy gates; exit 1 when any gate fails.

All gates have both sides exercised by examples/demo.sh: achievable gates pass,
an impossible gate fails.
"""

from __future__ import annotations

import argparse
import json
import sys

from .eval import build_model, format_terminal, run_evaluation


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="structgate",
                                     description="Grammar-constrained generation with measured conformance.")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--corpus-size", type=int, default=200)
        p.add_argument("--corpus-seed", type=int, default=42)
        p.add_argument("--order", type=int, default=3)
        p.add_argument("--smoothing", type=float, default=0.05)
        p.add_argument("-n", type=int, default=40)
        p.add_argument("--base-seed", type=int, default=1000)

    p_eval = sub.add_parser("evaluate", help="run the conformance evaluation")
    common(p_eval)
    p_eval.add_argument("--format", choices=("terminal", "json", "markdown"),
                        default="terminal")

    p_gate = sub.add_parser("gates", help="evaluate and enforce policy gates")
    common(p_gate)
    p_gate.add_argument("--min-valid-rate", type=float, default=None,
                        help="minimum valid rate for grammar-constrained mode")
    p_gate.add_argument("--min-conformance", type=float, default=None,
                        help="minimum conformance rate for schema-constrained mode")
    p_gate.add_argument("--max-mean-kl", type=float, default=None,
                        help="maximum mean per-step KL cost of grammar masking")
    p_gate.add_argument("--max-unconstrained-rate", type=float, default=None,
                        help="maximum valid rate tolerated for the unconstrained control")

    args = parser.parse_args(argv)
    model = build_model(args.corpus_size, args.corpus_seed, args.order, args.smoothing)
    results = run_evaluation(model, n=args.n, base_seed=args.base_seed)

    if args.command == "evaluate":
        if args.format == "json":
            print(json.dumps(results, indent=2, sort_keys=True))
        elif args.format == "markdown":
            m = results["modes"]
            print("| mode | valid | rate | mean KL/step | max KL |")
            print("|---|---|---|---|---|")
            for mode in ("none", "grammar", "schema"):
                r = m[mode]
                print(f"| {mode} | {r['valid']}/{r['n']} | {r['rate']:.2f} "
                      f"| {r['mean_kl']:.4f} | {r['max_kl']:.4f} |")
        else:
            print(format_terminal(results))
        return 0

    failures = []
    modes = results["modes"]
    if args.min_valid_rate is not None and modes["grammar"]["rate"] < args.min_valid_rate:
        failures.append(f"grammar valid rate {modes['grammar']['rate']:.2f} "
                        f"< required {args.min_valid_rate:.2f}")
    if args.min_conformance is not None and modes["schema"]["rate"] < args.min_conformance:
        failures.append(f"schema conformance {modes['schema']['rate']:.2f} "
                        f"< required {args.min_conformance:.2f}")
    if args.max_mean_kl is not None and modes["grammar"]["mean_kl"] > args.max_mean_kl:
        failures.append(f"grammar mean KL {modes['grammar']['mean_kl']:.4f} "
                        f"> allowed {args.max_mean_kl:.4f}")
    if args.max_unconstrained_rate is not None and modes["none"]["rate"] > args.max_unconstrained_rate:
        failures.append(f"unconstrained valid rate {modes['none']['rate']:.2f} "
                        f"> allowed {args.max_unconstrained_rate:.2f} "
                        "(control no longer exercises the constraint)")

    print(format_terminal(results))
    if failures:
        print("\nGATE FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nAll gates passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

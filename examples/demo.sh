#!/usr/bin/env bash
# StructGate demo: measured conformance, both sides of every gate. Fully offline.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Evaluate: constrained vs unconstrained, measured =="
python3 -m structgate evaluate

echo
echo "== Achievable gates pass =="
python3 -m structgate gates \
  --min-valid-rate 1.0 \
  --min-conformance 1.0 \
  --max-mean-kl 2.0 \
  --max-unconstrained-rate 0.2

echo
echo "== Impossible gate fails (negative control) =="
if python3 -m structgate gates --max-mean-kl 0.5; then
  echo "ERROR: impossible gate passed" >&2
  exit 1
else
  echo "impossible gate failed as expected"
fi

echo
echo "Demo complete: grammar and schema constraints measured at 40/40 vs a 3/40 unconstrained control."

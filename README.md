# StructGate

Grammar-constrained generation built from scratch in pure Python: an incremental JSON validator and a closed-schema validator that compute the exact set of legal next tokens for any prefix, a masked sampler over an exact character-level n-gram distribution, and a measured evaluation of what the constraints buy and what they cost.

StructGate answers the two questions structured-output write-ups usually skip:

- **Does masking actually guarantee conformance?** On the checked-in fixture, grammar-constrained sampling produces valid JSON on 40/40 seeded draws and schema-constrained sampling produces schema-conforming records on 40/40, against an unconstrained control that manages 3/40 on the same model and seeds. The unconstrained rate is itself gated, so the control cannot quietly stop exercising the constraint.
- **What does the guarantee cost?** Masking renormalizes the distribution to the legal token set; the per-step cost -ln(Z), where Z is the legal mass, is exactly KL(p || p_masked). The evaluation reports it per mode: mean 1.3496 nats/step for grammar masking on the fixture (max 8.8482), mean 0.8209 for schema masking.

## How it works

- **Exact distribution, not an approximation** - an order-3 character n-gram with add-k smoothing over a deterministic corpus of JSON records; next-token probabilities come straight from counts, so constraint effects are measured against ground truth.
- **An incremental JSON validator** - a stack-based state machine (objects, arrays, strings with escapes and \uXXXX, numbers per the JSON grammar, literals, whitespace) whose `allowed()` returns the exact set of next characters that keep a prefix valid. It matches Python's `json` module on 32 adversarial cases in the test suite, and its state snapshots/restores for exact allowed-set queries.
- **A closed-schema validator** - required keys in a fixed order, typed slots (string/number/bool), no additional keys. The same masking loop then yields records that parse *and* conform: keys, order, and types enforced during generation, not after.
- **Deterministic everything** - one seeded RNG per draw, sorted iteration over allowed sets (the suite pins cross-process reproducibility after a hash-order bug was caught), and pinned fixture numbers in tests.

## The trade-off, measured

```
mode            valid     rate   mean KL/step   max KL
---------- ---------- -------- -------------- --------
none          3/40        0.07         0.0000   0.0000
grammar      40/40        1.00         1.3496   8.8482
schema      40/40        1.00         0.8209   8.8482
```

Schema masking costs less per step than grammar masking on this fixture: restricting keys to the schema prunes low-probability continuations the grammar alone would keep, so less mass is renormalized away on average. The maximum single-step cost is high when the mask forces a token the model barely expects (for example a required key's characters in an unusual context) - that is the real price of a hard guarantee, and the report shows it instead of hiding it.

## Usage

```bash
python3 -m structgate evaluate                  # terminal report
python3 -m structgate evaluate --format json    # machine-readable
python3 -m structgate gates \
  --min-valid-rate 1.0 \
  --min-conformance 1.0 \
  --max-mean-kl 2.0 \
  --max-unconstrained-rate 0.2                  # exits 1 on any breach
bash examples/demo.sh                           # both sides of every gate, offline
```

## Verification

- 33 unit tests cover the validator against Python's `json` module (including leading zeros, dangling exponents, bad escapes, and trailing commas), exact allowed-set queries per grammar position, snapshot/restore determinism, schema key order and type rejection, the number/whitespace boundary regression, pinned fixture numbers, and both sides of every CLI gate.
- The unconstrained control is gated from above (`--max-unconstrained-rate`): if a fixture change ever makes raw sampling look good, CI fails instead of letting the comparison go stale.
- CI runs the same suite across Python 3.10-3.13.

## Bounds worth stating

The character-level n-gram is a toy model; it exists to provide an exact, inspectable distribution, not fluent text, and nothing here claims language-model quality. The constraint engines are the artifact: the JSON validator handles the JSON grammar (not arbitrary context-free grammars), and the schema layer covers a flat closed record with three slot types - nested schemas, unions, and optional fields are future work. KL cost is measured against this model's own unconstrained distribution; other models would show different numbers.

## License

MIT

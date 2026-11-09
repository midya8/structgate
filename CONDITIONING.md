# A prefix mask is not a conditional sequence model

This is an implementation of standard constrained decoding, KL identities and
finite-event conditioning. It is not a new decoding algorithm or an LLM result.
The original character model, corpus, CLI, demo, all 32 tests and original gates
are retained byte-for-byte, with hashes in `structgate/data/original-hashes.json`.
The two validators now return an empty allowed set after failure. Successful
historical generation paths and the full original evaluation remain unchanged.

## The corrected KL direction

Let p be the source next-character distribution, A its legal subset and
Z = sum_{c in A} p(c). For Z > 0, q(c) = p(c) / Z on A and zero elsewhere.

```
KL(q || p) = sum_{c in A} q(c) log(q(c)/p(c))
           = sum_{c in A} q(c) (-log Z) = -log Z.
```

The old documentation reversed the arguments. If any c outside A has p(c)>0,
then KL(p || q) is infinite, not -log Z. If no positive mass is removed it is
zero. An empty source-supported mask has no q, so both quantities are undefined.
JSON reports use null plus an explicit status, never a nonstandard Infinity
number. The UI shows the infinite-support case as infinity, and retains every
excluded character and its source probability. Binary64 roundoff can affect
sums in the last few bits; the model arithmetic is not exact real arithmetic.

A single sampled trajectory's sum of log(q(c)/p(c)) is a sampled transition
log-ratio. It is NOT the expected sequence KL. Averaging per-step costs across
visited prefixes in different modes does not isolate the causal effect of a
smaller mask. In particular, the original mean 0.8209 for schema versus 1.3496
for grammar visits different prefixes and cannot establish the explanation the
old README gave for that ordering.

## The real model, all original draws

The browser loads all 287 context count rows of the original order-3 character
n-gram, smoothing 0.05, vocabulary 46, trained on all 200 original synthetic
records with corpus seed 42. It uses the unpadded prefix distribution exactly
like original `generate` and `generate_schema`. The separate original `logprob`
method pads its starting context; it is not used to claim generation path
likelihoods here. Neither the corpus nor its model implementation was changed.

All original seeds 1000..1039 in each of none/grammar/schema are captured, for
120 full paths and 3,729 actual emitted characters. Python random uniforms are
recorded inputs, not claims that JavaScript has Python's RNG. The independent
browser implementation recomputes every distribution, mask, selected character
and state from the full model. It uses a recursive prefix recognizer rather
than the original Python streaming state machine. Every step and all 46 table
rows are available; no failures, whitespace or bad sequences are removed.
The complete paths are JSON-exportable, including each uniform, all probabilities,
KL terms and stop status. Recorded historical text is only a check, never the
inference output substituted for a calculation.

Original fixture results remain none 3/40, grammar 40/40, schema 40/40. The model
is not a language model of useful quality: it generates syntactically structured
nonsense. There is no API, network inference, paid service or external model.

## Completion, acceptance and the historical schema limits

A legal prefix need not finish within a finite budget. The one-character control
exposes a legal incomplete output and reports `budget_exhausted`. Other statuses
are `empty_mask`, `invalid_prefix` and `stream_complete`. The audit distinguishes
EOF acceptance from streaming completion: a root `123` is complete JSON at EOF,
but the historical streaming machine only closes that number after a boundary.
Changing that stopping policy would change the original fixture and is not
silently folded into this continuation.

The historical schema is a fixed-order flat record, not the JSON Schema standard.
It rejects valid fractional-exponent numbers such as 1.2e3 and unicode escape
strings. These are existing limitations, not JSON rules. The inspector and
regression witness retain and disclose them instead of upgrading the validator
while passing off changed fixture measurements as the old baseline. The general
JSON grammar accepts those syntaxes. Prefix validation is relative to the given
vocabulary and grammar machine, not a proof of future model-supported completion.
JSON numeric syntax can include magnitudes beyond binary64; syntax validity does
not establish finite parsed values, semantic truth or safe downstream use.

## Exact finite-language conditioning

The separate rational experiment accepts a user-supplied first-order Markov
source over 1..4 ASCII alphanumeric symbols and 1..128 distinct accepted words of
the same length 1..8. Source rows, including the initial `*` row, use integer or
numerator/positive-denominator strings, each a probability in [0,1], numerator
and denominator bounded by 10^12 after reduction. Rows sum exactly to one.

For each trie prefix u, compute h(u), the exact source probability that the
remaining suffix completes an accepted word. h(w)=1 at accepted leaves, zero
off the trie, and h(u)=sum_c p(c|u)h(uc). At h(u)>0,

```
local(c|u)       = p(c|u) 1[uc is a trie prefix] / Z(u)
conditioned(c|u) = p(c|u) h(uc) / h(u).
```

Python Fraction and independently implemented JavaScript BigInt rational
arithmetic return all nonterminal prefixes, each transition and every accepted
word. Each conditioned word mass is also checked by direct P(word)/P(event).
This is a finite-horizon Doob reweighting on an acyclic prefix state space,
not an implementation of ASAp, not an arbitrary-CFG solver and not efficient
conditioning for an LLM.

Six labeled constructed controls cover future-mass distortion, an unrestricted
identity control, a source-zero locally stranded branch, a zero-probability
event, a three-symbol language and a one-token control. Positive syntactic
viability does not imply positive future source mass. Local dead ends retain
their stranded probability in a failure sink. TV includes that sink; the separate
`terminal_l1_half` does not, so it is not called full TV. A source-zero event is
explicitly undefined; zero rows are placeholders, never normalized conditionals.
No numerical approximation is used in these rational controls.

## Input, CLI and stale-output behavior

```
python -m structgate.audit prefix --input examples/prefix.json
python -m structgate.audit trace --input examples/trace.json
python -m structgate.audit condition --input examples/condition.json
# stdin is supported with --input -; installed entrypoint: structgate-audit
```

The three exact input schemas are `{prefix,mode}`, `{mode,uniforms}` and
`{alphabet,words,rows}`. Prefix length is at most 512 Unicode code points. Mode is
none, grammar or schema. Uniforms contains 1..220 finite numbers in [0,1); booleans
are not numbers. Trace budget is the number of supplied uniforms. Audit JSON is
limited to 100,000 UTF-8 bytes, nesting 8, with duplicate keys, nonfinite numbers,
exponent overflow, unknown fields and invalid shapes rejected. Errors exit 2,
write stderr and no partial JSON. Prefix text is data, not parsed as audit input.
Browser edits clear prior dependent tables, state and exports until recomputed.

## Verification

```
python -m unittest discover -s tests -v
python scripts/verify_regeneration.py
node --test tests/*.cjs
bash examples/demo.sh
bash examples/verify_wheel.sh
```

54 Python tests include all 32 unchanged originals, exact direct-enumeration
references on 24 random small languages, zero events/failure sinks, support-aware
KL, original 120 path replay, EOF/streaming distinction, malformed inputs, CLI
failure behavior and byte-preservation checks. Tests run on 3.10..3.13.

Three Node/actual-Chrome tests compare 1,251 full prefix reports, all 289 exported
and unseen source-context check, all 120 complete paths and six exact controls.
The full comparison visits 741,236 numeric entries, not selected table summaries.
Actual Chrome recomputes and renders all 171,534 historical step-table rows,
three actual JSON downloads, invalidation, keyboard and 320/390/1280 layouts.
Native scalar and JS comparisons use 1e-11 normalized tolerance; original fixture
regeneration uses 1e-12 and restores checked-in bytes. Rational strings must match
exactly. A finite test sweep is not a proof for every possible input.

Isolated install outside checkout checks nine module origins, all 120 paths, all
six conditioning controls, original full evaluation and gates, all three audit
CLIs and the original evaluation CLI. Python/Chrome/Node are independent runtimes;
shared fixtures are input data, not a substitute for native computation.

## Sources and attribution

- Park et al., Grammar-Aligned Decoding, sections 2 and 3:
  https://arxiv.org/html/2405.21047
  Local masking versus global conditioning, expected future grammaticality.
  We do not claim to implement the paper's ASAp algorithm or reproduce its LLM results.
- Gareev et al., Local and Global Decoding in Text Generation,2024:
  https://aclanthology.org/2024.findings-emnlp.854/
  Local/global distribution distinction. Their abstract explicitly reports that
  preserving the global distribution does not universally improve output quality.
- IETF RFC 8259, 2017, sections 2, 6, 7 and 9:
  https://www.rfc-editor.org/rfc/rfc8259.html
  JSON grammar, number/string syntax and permitted parser range limits.
- ECMA-404, JSON Data Interchange Syntax:
  https://tc39.es/ecma404/
  Syntax is separate from semantic interpretation and runtime number types.
- Wolfram MathWorld, Doob h-Transform:
  https://mathworld.wolfram.com/Doobh-Transform.html
  Transition reweighting and space-time conditioning context.
- Pierre C Bellec, The Doob-h transform:
  https://bellecp.github.io/doob_h.html
  Finite-chain harmonic reweighting and explicit conditional transition formula.

These are standard methods. The source model and validators are the original
project's code; the audit, independent browser recognizer, rational experiment
and visual inspector are project implementation. No external model results,
private records or invented attribution are used.

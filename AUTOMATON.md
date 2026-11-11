# The future has a weight

StructGate 0.3 adds a separate exact finite-horizon DFA conditioning API and
inspector. It extends the explicit finite-word trie experiment with a product
state, without enumerating all complete words. The original source model,
JSON/schema validators, default CLI, 120 recorded paths, six trie controls and
old browser inspector remain unchanged. This is standard finite-state dynamic
programming and Doob reweighting, not a new algorithm or an LLM result.

## The witness

The two-symbol source initially gives 0 and 1 probability 1/2 each. After 0 it
emits 1 with probability 1/10; after 1 it emits 1 with probability 9/10. The DFA
accepts words ending in 1, at exactly two symbols. Both first symbols have a
syntactically possible accepting suffix. Local viability masking therefore keeps
the first-symbol probabilities at 1/2 each. Global conditioning instead gives
first-symbol probabilities 1/10 and 9/10.

The selected accepted word 01 has source probability 1/20, local-mask
probability 1/2 and global conditional probability 1/10. Source acceptance mass
is 1/2. These are exact constructed values, not measured model quality.

At horizon 32 the same two-state ending control has 4,294,967,296 possible
source words and 192 product transition rows. The report still exposes every
remaining-time/state/previous-symbol row. This is a structural count, not a
speed, RAM or scaling benchmark. The denser independent browser reference is
not the native recursion and makes no equivalent-work claim.

## Model and exact equations

Input supplies alphabet A, total deterministic transition function delta,
start state s0, accepting states F, first-order source rows p(c | previous),
fixed emitted-symbol count N and one selected word of length N. Acceptance is
checked only after exactly N symbols; accepting states do not stop early.
A complete DFA is required: model rejection with a rejecting sink state.

For k symbols remaining, DFA state s and previous source symbol p:

```
H(0,s,p) = 1[s in F]
H(k,s,p) = sum_c P(c | p) H(k-1,delta(s,c),c)
V(0,s)   = 1[s in F]
V(k,s)   = OR_c V(k-1,delta(s,c))
Z(k,s,p) = sum_c P(c | p) 1[V(k-1,delta(s,c))]
local(c) = P(c | p) 1[V(k-1,delta(s,c))] / Z(k,s,p)
global(c)= P(c | p) H(k-1,delta(s,c),c) / H(k,s,p)
```

A local row is undefined when Z=0. Its 0 entries are labeled placeholders and
all arriving local probability moves to a cumulative failure sink. V deliberately
ignores zero source probabilities. A viable but source-impossible suffix can
strand mass. When H=0 the global row has null entries, never a normalized zero
law. When initial H=0, the entire global event law and all global marginals and
selected-word likelihoods are null. Off-support rows with H>0 still describe
valid hypothetical starting conditions, even if unreachable from the actual
start. They are not claims of observed states.

The source process continues for N symbols, including rejected words. Forward
source marginals sum to 1. Local live marginals plus the failure sink sum to 1.
For positive event mass, global marginals sum to 1 and the terminal accepting
mass is 1. The browser shows all of these separately. At N=0, the empty word is
accepted exactly when s0 is accepting. A rejected empty word goes to the local
failure sink immediately.

For any selected accepted word w, multiplying its global transitions telescopes
to P(w)/H(N,s0,*). A rejected word has global mass 0 when conditioning is defined.
The source word probability still exists even for rejected words. Local prefix
mass can become 0 after a dead end. Path probabilities are not entropy or a
sequence-level total-variation metric. Product-state marginals aggregate many
words; equal marginals do not prove equal word distributions.

The product state retains both DFA state and previous symbol. Dropping the
previous symbol changes the source. The special * row represents the initial
source context, used only before the first emission in an actual run. It is
also exposed as an explicit hypothetical initialization for each DFA state.
This is a supplied first-order source, not the original order-3 character model,
a projection of its counts or a variable-order generator.

## Separate strict API and CLI

```
from structgate.automaton import automaton_report
report = automaton_report(request)

python -m structgate.automaton_cli --input examples/automaton.json
structgate-automaton --input examples/automaton.json
# --input - reads stdin
```

Exact top-level keys:

- `alphabet`: 1..4 distinct one-character ASCII letters/digits, in supplied order.
- `states`: 1..8 distinct ASCII identifiers, letter first then letters/digits/_;
  each at most 16 characters. Supplied order controls report order.
- `start`: a listed state.
- `accept`: a distinct subset of states, including the empty set.
- `transitions`: exactly one array per state, with one known destination for
  every symbol in alphabet order. Every transition must be present.
- `rows`: exactly the keys `*` plus every alphabet symbol, each an array in
  alphabet order. Each entry is an integer or unsigned rational string; reduced
  denominator at most 1,000,000, value in [0,1], rows sum exactly to 1. No float,
  bool, negative, exponent or decimal probability inputs. Numerator/denominator
  strings have at most 32 characters, and denominator starts with 1..9.
- `horizon`: integer 0..32, booleans rejected.
- `word`: exactly horizon symbols from alphabet, including empty at horizon zero.

New CLI/browser JSON is at most 100,000 UTF-8 bytes with nesting at most 8,
rejects duplicate keys and all noninteger numeric tokens, including -0, 2.0
and 1e0. Rational strings have no decimal or exponent syntax. The Python API
rejects float/bool values. JavaScript numbers do not retain lexical spelling;
the browser's strict JSON scanner enforces the lexical rule before calling the
engine. Invalid edits clear tables and disable downloads until recomputation.
CLI errors exit 2 with stderr and no partial stdout. No input object is mutated.

## Implementation and independent checks

Native Python Fraction uses memoized backward recursion for H and Boolean V,
then propagates separate forward source/local/global vectors. Browser BigInt
uses a different decomposition: for every possible product origin it propagates
a full source kernel forward to each horizon, then sums accepting destinations.
V is separately propagated without source weights. No saved native report is
loaded by the browser; `automaton-data.js` contains inputs only.

Native arithmetic state/edge counts are bounded by the finite product and
horizon. Exact rational bit lengths can still grow. The browser deliberately
uses a denser reference kernel, so it is not a speed comparison or production
implementation. All 0..N future-mass layers, all transition symbols and every
forward marginal row are selectable. The full report and canonical input can
be downloaded, including every selected-word prefix probability.

64 Python tests retain all 54 previous tests. Ten new tests include an independent
complete-word oracle on 60 seeded small DFAs, every future mass and syntax
viability, every source/local/global marginal, selected-word likelihoods,
zero events, stranded branches, empty words, strict CLI/schema cases, long
closed-form controls, input immutability and all original source hashes.

Six Node/actual-Chrome tests retain all three previous tests. New tests compare
24 complete reports exactly, plus independent JavaScript fair-bit word counts
at every small control product state. Actual Chrome renders all 2,043 future
transition rows and 6,550 symbol rows, all 2,239 forward marginal rows and all
156 selected-word prefixes. It checks 24 responsive views, stale/invalid edits,
keyboard submission and two trusted input/report downloads. Downloaded reports
are recomputed natively. These finite checks are not a proof for every input.

An isolated eleven-module installed artifact outside the checkout reproduces
all 24 reports through API, module and console entrypoints. The existing isolated
nine-module check separately retains all 120 historical paths, six old trie
controls, original evaluation and CLI gates. Original evaluation still gives
3/40 unconstrained, 40/40 grammar and 40/40 schema. No old gate is weakened.

```
python -m unittest discover -s tests -v
node --test tests/*.cjs
python scripts/verify_regeneration.py
python scripts/verify_automaton_regeneration.py
bash examples/demo.sh
bash examples/verify_wheel.sh
bash scripts/verify_automaton_install.sh
```

## Research and limits

These sources establish the method and interpretation, not evidence that this
implementation reproduces their systems, benchmarks or model quality:

- Park et al., Grammar-Aligned Decoding, sections 2 and 3:
  https://arxiv.org/html/2405.21047
  Global conditioning uses expected future grammaticality, rather than a binary
  support mask. This project does not implement ASAp or an arbitrary CFG/LLM.
- Pachet, Exact Regular-Constrained Variable-Order Markov Generation via Sparse
  Context-State Belief Propagation, 2026, sections 2 and 3:
  https://arxiv.org/html/2605.07839
  Explicitly credits prior first-order regular-constraint inference and explains
  product state/source-memory requirements. This API implements only a supplied
  first-order source, not that paper's variable-order/backoff extension.
- Gareev et al., Local and Global Decoding in Text Generation, 2024:
  https://aclanthology.org/2024.findings-emnlp.854/
  Distribution preservation is not a universal quality improvement; their
  abstract reports worse global-decoding quality in most tested configurations.
- Wolfram MathWorld, Doob h-Transform:
  https://mathworld.wolfram.com/Doobh-Transform.html
  Transition reweighting and space-time conditioning. No new probability method.
- Pierre C. Bellec, The Doob-h transform:
  https://bellecp.github.io/doob_h.html
  Explicit finite-chain transformed transition formula. Its hitting-before
  example differs from this fixed-horizon terminal event.
- Mriganka, Guiding Markov chains via the Doob transform, April 19, 2024:
  https://mriganka.xyz/blog/doob
  Finite-future Bayes reweighting and why future event probabilities matter.
- Python documentation, fractions:
  https://docs.python.org/3/library/fractions.html
  String/integer exact arithmetic differs from reconstructing decimal intent
  from binary floats. The interface rejects floats rather than reinterpreting them.

No random sampler, variable-length stopping, arbitrary JSON conditioning,
learned language, external model, text-quality score, speedup, memory saving,
causal effect or deployment reliability is claimed. The language and source
probabilities are supplied data. The original JSON/schema bounds and streaming
versus EOF behavior in CONDITIONING.md remain unchanged.

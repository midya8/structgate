"""Conformance evaluation: constrained vs unconstrained generation, measured.

Three modes are compared over seeded draws from the same model:

- none:    raw sampling from the exact distribution (negative control)
- grammar: JSON-grammar masking - emitted prefixes stay legal; completion is measured
- schema:  closed-schema masking - completed records conform to the schema

The mask cost is the per-step renormalization cost -ln(Z), exactly the KL
divergence from the masked distribution to its unconstrained source. The
reverse direction is infinite when positive source mass is excluded.
"""

from __future__ import annotations

import json
import random
from typing import Dict, List, Optional, Sequence, Tuple

from .corpus import generate_corpus, vocabulary
from .decode import generate
from .model import CharNGram, sample
from .schema import RECORD_SCHEMA, Schema, SchemaValidator, conforms


def build_model(corpus_size: int = 200, seed: int = 42, order: int = 3,
                smoothing: float = 0.05) -> CharNGram:
    docs = generate_corpus(corpus_size, seed=seed)
    model = CharNGram(order, vocabulary(docs), smoothing=smoothing)
    model.train(docs)
    return model


def generate_schema(model: CharNGram, rng: random.Random, schema: Schema,
                    max_chars: int = 220) -> Tuple[str, bool, List[float]]:
    """Seeded schema-masked generation. Returns (text, complete, per-step KLs)."""
    validator = SchemaValidator(schema)
    text = ""
    kls: List[float] = []
    import math

    for _ in range(max_chars):
        if validator.complete:
            break
        allowed = validator.allowed(model.vocab)
        if not allowed:
            break
        dist = model.distribution(text)
        mass = sum(dist[c] for c in allowed)
        if mass <= 0:
            break
        ch = sample({c: dist[c] / mass for c in sorted(allowed)}, rng)
        kls.append(-math.log(mass))
        if not validator.advance(ch):
            break
        text += ch
    return text, validator.complete, kls


def run_evaluation(model: CharNGram, n: int = 40, base_seed: int = 1000,
                   schema: Optional[Schema] = None) -> Dict:
    """Run all three modes over n seeded draws and return measured results."""
    schema = schema or RECORD_SCHEMA
    modes: Dict[str, Dict] = {}
    for mode in ("none", "grammar", "schema"):
        valid = 0
        kl_sum = 0.0
        kl_max = 0.0
        kl_count = 0
        for i in range(n):
            rng = random.Random(base_seed + i)
            if mode == "schema":
                text, complete, kls = generate_schema(model, rng, schema)
                ok = complete and conforms(text, schema)["conforms"]
            else:
                r = generate(model, rng, constrained=(mode == "grammar"))
                try:
                    json.loads(r["text"])
                    parses = True
                except Exception:
                    parses = False
                ok = r["complete"] and parses
                kls = [s.kl for s in r["steps"]] if mode == "grammar" else []
            valid += ok
            kl_sum += sum(kls)
            kl_count += len(kls)
            kl_max = max(kl_max, max(kls) if kls else 0.0)
        modes[mode] = {
            "valid": valid,
            "n": n,
            "rate": valid / n,
            "mean_kl": (kl_sum / kl_count) if kl_count else 0.0,
            "max_kl": kl_max,
        }
    return {"modes": modes, "n": n, "base_seed": base_seed,
            "model": {"order": model.order, "smoothing": model.smoothing,
                      "vocab_size": len(model.vocab)}}


def format_terminal(results: Dict) -> str:
    lines = [
        f"StructGate evaluation - {results['n']} seeded draws per mode "
        f"(base seed {results['base_seed']}, order-{results['model']['order']} char model, "
        f"smoothing {results['model']['smoothing']})",
        "",
        f"{'mode':<10} {'valid':>10} {'rate':>8} {'mean KL/step':>14} {'max KL':>8}",
        f"{'-'*10} {'-'*10} {'-'*8} {'-'*14} {'-'*8}",
    ]
    for mode in ("none", "grammar", "schema"):
        m = results["modes"][mode]
        lines.append(f"{mode:<10} {m['valid']:>4}/{m['n']:<5} {m['rate']:>8.2f} "
                     f"{m['mean_kl']:>14.4f} {m['max_kl']:>8.4f}")
    return "\n".join(lines)

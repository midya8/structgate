"""Constrained and unconstrained generation with measured distortion.

`generate` walks an exact next-token distribution. In constrained mode the
distribution is masked to the grammar-legal set and renormalized; the
renormalization cost -ln(Z), where Z is the probability mass the grammar
allowed, is the exact KL divergence KL(p || p_masked) and is recorded per step.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Dict, List, Optional, Sequence

from .grammar import JSONValidator
from .model import CharNGram, sample


class Step:
    __slots__ = ("char", "allowed_mass", "kl", "allowed_count")

    def __init__(self, char: str, allowed_mass: float, allowed_count: int):
        self.char = char
        self.allowed_mass = allowed_mass
        self.kl = -math.log(allowed_mass) if allowed_mass > 0 else float("inf")
        self.allowed_count = allowed_count


def generate(
    model: CharNGram,
    rng: random.Random,
    constrained: bool,
    max_chars: int = 200,
    stop_on_complete: bool = True,
) -> Dict:
    """Generate one document. Returns text, steps, and validity flags."""
    validator = JSONValidator()
    text = ""
    steps: List[Step] = []
    for _ in range(max_chars):
        if constrained:
            allowed = validator.allowed(model.vocab)
            if not allowed:
                break  # no legal continuation (grammar dead end)
            dist = model.distribution(text)
            mass = sum(dist[ch] for ch in allowed)
            if mass <= 0:
                break  # model assigns no mass to any legal continuation
            masked = {ch: dist[ch] / mass for ch in sorted(allowed)}
            ch = sample(masked, rng)
            steps.append(Step(ch, mass, len(allowed)))
        else:
            dist = model.distribution(text)
            ch = sample(dist, rng)
            steps.append(Step(ch, 1.0, len(model.vocab)))
        ok = validator.advance(ch)
        text += ch
        if not ok:
            break  # unconstrained run left the grammar
        if stop_on_complete and validator.complete:
            break
    return {
        "text": text,
        "steps": steps,
        "complete": validator.complete,
        "failed": validator.failed,
        "mean_kl": (sum(s.kl for s in steps) / len(steps)) if steps else 0.0,
        "max_kl": max((s.kl for s in steps), default=0.0),
    }

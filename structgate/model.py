"""Exact character-level n-gram model with add-k smoothing.

The model exists to provide an *exact* next-token distribution: probabilities come
straight from counts, so constraint effects are measured against ground truth,
never an approximation. All randomness flows through one seeded RNG.
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple


class CharNGram:
    """Order-n character model over a fixed vocabulary with add-k smoothing."""

    def __init__(self, order: int, vocab: Sequence[str], smoothing: float = 0.1):
        if order < 1:
            raise ValueError("order must be >= 1")
        if not vocab:
            raise ValueError("vocab must be non-empty")
        if smoothing <= 0:
            raise ValueError("smoothing must be positive")
        self.order = order
        self.vocab = tuple(sorted(set(vocab)))
        self.smoothing = smoothing
        # counts[context][char] = count; context length is order - 1.
        self._counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._totals: Dict[str, int] = defaultdict(int)

    def train(self, documents: Iterable[str]) -> None:
        for doc in documents:
            padded = "\x00" * (self.order - 1) + doc
            for i in range(self.order - 1, len(padded)):
                ctx = padded[i - (self.order - 1):i] if self.order > 1 else ""
                ch = padded[i]
                if ch not in self.vocab:
                    continue
                self._counts[ctx][ch] += 1
                self._totals[ctx] += 1

    def distribution(self, context: str) -> Dict[str, float]:
        """Exact next-char distribution for a context (last order-1 chars used)."""
        ctx = context[-(self.order - 1):] if self.order > 1 else ""
        row = self._counts.get(ctx, {})
        total = self._totals.get(ctx, 0)
        k = self.smoothing
        v = len(self.vocab)
        denom = total + k * v
        return {ch: (row.get(ch, 0) + k) / denom for ch in self.vocab}

    def logprob(self, text: str) -> float:
        import math

        padded = "\x00" * (self.order - 1) + text
        lp = 0.0
        for i in range(self.order - 1, len(padded)):
            ctx = padded[max(0, i - (self.order - 1)):i] if self.order > 1 else ""
            ch = padded[i]
            if ch not in self.vocab:
                return float("-inf")
            lp += math.log(self.distribution(ctx)[ch])
        return lp


def sample(distribution: Dict[str, float], rng: random.Random) -> str:
    """Seeded sample from an exact distribution (sums to 1 within fp tolerance)."""
    r = rng.random()
    acc = 0.0
    last = None
    for ch, p in distribution.items():
        acc += p
        last = ch
        if r < acc:
            return ch
    return last  # fp tail

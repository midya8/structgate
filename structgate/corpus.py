"""Deterministic corpus of JSON documents.

One seed reproduces the corpus bit for bit; documents follow a small object
grammar (name/city/score/tags records) so the trained model has real structure
to learn and real grammar mistakes to make.
"""

from __future__ import annotations

import json
import random
from typing import List

_FIRST = ["ada", "ben", "cy", "dora", "eli", "fay", "gus", "hana", "ivo", "jae"]
_LAST = ["kim", "lu", "ma", "ng", "ortiz", "park", "quinn", "rey", "shah", "to"]
_CITY = ["oslo", "lima", "cairo", "perth", "lyon", "busan", "tulsa", "porto"]
_TAG = ["red", "blue", "green", "fast", "slow", "new", "old", "beta"]


def generate_corpus(n: int, seed: int = 42) -> List[str]:
    rng = random.Random(seed)
    docs = []
    for _ in range(n):
        rec = {
            "name": rng.choice(_FIRST) + " " + rng.choice(_LAST),
            "city": rng.choice(_CITY),
            "score": round(rng.uniform(0, 100), 2),
            "tags": rng.sample(_TAG, rng.randint(1, 3)),
            "active": rng.random() < 0.5,
        }
        docs.append(json.dumps(rec, separators=(", ", ": "), sort_keys=True))
    return docs


def vocabulary(docs: List[str]) -> List[str]:
    chars = set(" \n\t")
    for d in docs:
        chars.update(d)
    return sorted(chars)

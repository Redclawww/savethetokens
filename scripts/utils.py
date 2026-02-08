#!/usr/bin/env python3
"""Shared text scoring utilities for savethetokens scripts."""

from __future__ import annotations

import re
from collections import Counter

TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def tokenize(text: str) -> list[str]:
    """Split text into lowercase alphanumeric tokens."""
    return [t.lower() for t in TOKEN_RE.findall(text)]


def cosine_score(query_tokens: list[str], doc_tokens: list[str]) -> float:
    """Cosine similarity between two token lists."""
    if not query_tokens or not doc_tokens:
        return 0.0
    q = Counter(query_tokens)
    d = Counter(doc_tokens)
    overlap = set(q) & set(d)
    dot = float(sum(q[t] * d[t] for t in overlap))
    q_norm = sum(v * v for v in q.values()) ** 0.5
    d_norm = sum(v * v for v in d.values()) ** 0.5
    if q_norm == 0 or d_norm == 0:
        return 0.0
    return dot / (q_norm * d_norm)


def overlap_score(query: str, text: str) -> float:
    """Fraction of query tokens found in text."""
    q = set(tokenize(query))
    d = set(tokenize(text))
    if not q or not d:
        return 0.0
    return len(q & d) / len(q)

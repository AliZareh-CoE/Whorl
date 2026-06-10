"""Related-paper suggestions: TF-IDF cosine similarity over title + abstract.

Venue is deliberately excluded — sharing a journal is too weak a signal and
drowns out topical similarity in small libraries.
"""

import math
import re
from collections import Counter

from .models import Reference

TOKEN_RE = re.compile(r"[a-z]{3,}")

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "are",
    "was",
    "were",
    "have",
    "has",
    "had",
    "not",
    "but",
    "can",
    "its",
    "into",
    "than",
    "then",
    "also",
    "between",
    "among",
    "using",
    "use",
    "used",
    "our",
    "their",
    "these",
    "those",
    "such",
    "more",
    "most",
    "may",
    "might",
    "all",
    "any",
    "both",
    "each",
    "other",
    "some",
    "what",
    "when",
    "where",
    "which",
    "while",
    "how",
    "why",
    "does",
    "did",
    "been",
    "being",
    "during",
    "after",
    "before",
    "under",
    "over",
    "about",
    "against",
    "results",
    "study",
    "studies",
    "effect",
    "effects",
    "evidence",
    "analysis",
    "based",
    "approach",
    "toward",
    "towards",
}


def tokenize(reference: Reference) -> list[str]:
    text = f"{reference.title} {reference.abstract}".lower()
    return [t for t in TOKEN_RE.findall(text) if t not in STOPWORDS]


def _tfidf_vectors(references: list[Reference]) -> dict[int, dict[str, float]]:
    docs = {ref.pk: Counter(tokenize(ref)) for ref in references}
    doc_count = len(docs) or 1
    df: Counter = Counter()
    for counts in docs.values():
        df.update(counts.keys())
    vectors = {}
    for pk, counts in docs.items():
        total = sum(counts.values()) or 1
        vectors[pk] = {
            term: (count / total) * math.log(1 + doc_count / df[term])
            for term, count in counts.items()
        }
    return vectors


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(b) < len(a):
        a, b = b, a
    dot = sum(weight * b.get(term, 0.0) for term, weight in a.items())
    norm_a = math.sqrt(sum(w * w for w in a.values()))
    norm_b = math.sqrt(sum(w * w for w in b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def related_references(reference: Reference, limit: int = 5, min_score: float = 0.05):
    """The library references most similar to this one: [(reference, score), ...]."""
    references = list(Reference.objects.all())
    vectors = _tfidf_vectors(references)
    target = vectors.get(reference.pk, {})
    scored = [
        (other, _cosine(target, vectors[other.pk]))
        for other in references
        if other.pk != reference.pk
    ]
    scored = [(ref, score) for ref, score in scored if score >= min_score]
    scored.sort(key=lambda pair: -pair[1])
    return scored[:limit]

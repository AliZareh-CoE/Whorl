"""Local keyword extraction (Owner idea #5) — RAKE-style, pure Python, no models.

Candidate phrases are maximal runs of non-stopwords; each is scored by the sum of
its words' degree/frequency ratios (words that co-occur in longer phrases score higher).
"""

import re
from collections import defaultdict

from literature.related import STOPWORDS

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z-]{2,}")

EXTRA_STOPWORDS = {
    "via",
    "new",
    "novel",
    "case",
    "role",
    "two",
    "one",
    "non",
    "per",
    "well",
    "however",
    "thus",
    "show",
    "shown",
    "paper",
    "present",
    "presented",
    "propose",
    "proposed",
    "method",
    "methods",
    "model",
    "models",
    "data",
    "result",
}

ALL_STOPWORDS = STOPWORDS | EXTRA_STOPWORDS


def _candidate_phrases(text: str) -> list[list[str]]:
    phrases = []
    # punctuation hard-breaks phrases; stopwords/non-words soft-break within a clause
    for chunk in re.split(r"[.,;:!?()\[\]{}\"'\n]+", text.lower()):
        current = []
        for token in re.split(r"[^a-zA-Z-]+", chunk):
            if WORD_RE.fullmatch(token) and token not in ALL_STOPWORDS:
                current.append(token)
            else:
                if current:
                    phrases.append(current)
                current = []
        if current:
            phrases.append(current)
    return [p[:4] for p in phrases]  # cap phrase length


def extract_keywords(text: str, max_keywords: int = 8) -> list[str]:
    """Top keyword phrases for a blob of text, most salient first."""
    phrases = _candidate_phrases(text or "")
    if not phrases:
        return []
    frequency: dict[str, int] = defaultdict(int)
    degree: dict[str, int] = defaultdict(int)
    for phrase in phrases:
        for word in phrase:
            frequency[word] += 1
            degree[word] += len(phrase)
    word_score = {word: degree[word] / frequency[word] for word in frequency}

    seen: set[str] = set()
    scored: list[tuple[float, str]] = []
    for phrase in phrases:
        label = " ".join(phrase)
        if label in seen:
            continue
        seen.add(label)
        score = sum(word_score[word] for word in phrase)
        # favor multi-word phrases slightly, then frequency of exact phrase
        scored.append((score + 0.1 * len(phrase), label))
    scored.sort(key=lambda pair: -pair[0])
    return [label for _, label in scored[:max_keywords]]

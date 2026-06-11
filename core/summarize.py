"""Local extractive summarization (Owner idea #5) — no models, no APIs.

Sentences are scored by the frequency of their salient words (sharing the keyword
stopword list), with a bonus for opening sentences; the top sentences are returned
in their original order.
"""

import re
from collections import Counter

from .keywords import ALL_STOPWORDS, WORD_RE

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\d])")


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    return [s.strip() for s in SENTENCE_RE.split(text) if len(s.strip()) > 1]


def summarize(text: str, max_sentences: int = 3) -> list[str]:
    """The most informative sentences, in original order. Short texts pass through."""
    sentences = split_sentences(text)
    if len(sentences) <= max_sentences:
        return sentences

    frequencies: Counter = Counter()
    sentence_words = []
    for sentence in sentences:
        words = [w for w in WORD_RE.findall(sentence.lower()) if w not in ALL_STOPWORDS]
        sentence_words.append(words)
        frequencies.update(set(words))

    scored = []
    for index, (sentence, words) in enumerate(zip(sentences, sentence_words, strict=True)):
        if not words:
            continue
        score = sum(frequencies[w] for w in words) / len(words)
        if index == 0:
            score *= 1.25  # openings usually carry the thesis
        scored.append((score, index, sentence))

    top = sorted(scored, key=lambda item: -item[0])[:max_sentences]
    return [sentence for _, _, sentence in sorted(top, key=lambda item: item[1])]

"""Approximate LaTeX word count (Owner idea #24, parity slice 8).

A pure-Python detex: strip comments, math, and command machinery, then count
words in the remaining prose. Numbers will differ slightly from texcount (which
Overleaf uses) — math-heavy documents especially — so the UI says "approx".
"""

import re

_COMMENT = re.compile(r"(?<!\\)%.*")
_DISPLAY_MATH = re.compile(r"\$\$.*?\$\$|\\\[.*?\\\]", re.DOTALL)
_INLINE_MATH = re.compile(r"\$[^$]*\$|\\\((.*?)\\\)", re.DOTALL)
_MATH_ENV = re.compile(
    r"\\begin\{(equation|align|gather|multline|eqnarray|displaymath)\*?\}.*?"
    r"\\end\{\1\*?\}",
    re.DOTALL,
)
_HEADING = re.compile(r"\\(?:part|chapter|section|subsection|subsubsection|paragraph)\*?\{")
_CAPTION = re.compile(r"\\caption\{")
# \command[opt]{arg} -> keep the {arg} text, drop the command + optional arg
_COMMAND_WITH_ARG = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?")
_BRACES = re.compile(r"[{}]")
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")


def _count_pattern(text: str, pattern: re.Pattern) -> int:
    return len(pattern.findall(text))


def word_count(source: str) -> dict:
    """Return {words, headers, captions, math_inlines} for a LaTeX source string."""
    headers = _count_pattern(source, _HEADING)
    captions = _count_pattern(source, _CAPTION)
    math_inlines = _count_pattern(source, _INLINE_MATH)

    text = _COMMENT.sub("", source)
    text = _MATH_ENV.sub(" ", text)
    text = _DISPLAY_MATH.sub(" ", text)
    text = _INLINE_MATH.sub(" ", text)
    text = _COMMAND_WITH_ARG.sub(" ", text)  # drop commands, keep their {brace} contents
    text = _BRACES.sub(" ", text)
    words = len(_WORD.findall(text))

    return {
        "words": words,
        "headers": headers,
        "captions": captions,
        "math_inlines": math_inlines,
    }

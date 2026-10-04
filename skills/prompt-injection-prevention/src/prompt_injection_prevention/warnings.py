"""Pattern warnings for text that looks like an injection attempt.

A warning, not a defense: attackers rephrase, translate, and encode, so a clean scan proves nothing.
Use it to log and flag for review; rely on Policy and the quarantined call to stay safe.
"""

from __future__ import annotations

import re

PATTERNS: dict[str, re.Pattern[str]] = {
    "override": re.compile(
        r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier|all|system)\b.{0,20}"
        r"\b(instructions?|prompts?|rules?|messages?)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    "role": re.compile(r"\b(you are now|act as|new instructions|system prompt|developer mode)\b", re.IGNORECASE),
    "delimiter": re.compile(
        r"(<\|im_(start|end)\|>|</?system>|\[/?INST\]|^#{2,}\s*(system|assistant)\b)", re.IGNORECASE | re.MULTILINE
    ),
    "exfiltration": re.compile(
        r"\b(send|forward|email|post|upload)\b.{0,60}\b(to|at)\b\s+\S+@\S+", re.IGNORECASE | re.DOTALL
    ),
    "hidden": re.compile(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]"),
}


def injection_warnings(text: str) -> list[str]:
    """Names of the patterns the text matches, in a fixed order."""
    return [name for name, p in PATTERNS.items() if p.search(text)]

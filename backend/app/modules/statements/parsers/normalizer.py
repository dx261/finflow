"""Text normalization for matching bank statement labels.

Bank statements are notoriously inconsistent: headers carry stray spaces,
newlines, zero-width characters, and English or Chinese colons. Every
string that needs to be compared (header labels, anchor keys) is passed
through :func:`normalize_text` first so lookups are robust to these
variations.

Example: ``" Posting Date： "`` -> ``"postingdate"``
"""

import re

# Zero-width and format characters plus all Unicode whitespace.
_STRIP_RE = re.compile(r"[\s​‌‍⁠﻿]+")

# English and Chinese colons (and other separator punctuation).
_PUNCT_RE = re.compile(r"[:：,，;；|｜/／·•\-–—_]")


def normalize_text(value: str | None) -> str:
    """Collapse a label into a stable lowercase comparison key.

    - ``None`` becomes an empty string
    - removes all whitespace, newlines and zero-width characters
    - removes colons and common separator punctuation
    - lowercases
    """
    if value is None:
        return ""
    text = _STRIP_RE.sub("", value)
    text = _PUNCT_RE.sub("", text)
    return text.lower()

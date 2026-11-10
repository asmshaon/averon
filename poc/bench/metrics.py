"""Text normalization and quality/latency metrics for the PoC benchmark (design D7)."""

from __future__ import annotations

import math
import re
import unicodedata

import jiwer
import sacrebleu

_AR_DIACRITICS = re.compile("[ً-ْٰـ]")  # harakat, superscript alef, tatweel
_AR_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"})
_DIGITS = str.maketrans(
    "০১২৩৪৫৬৭৮৯" "٠١٢٣٤٥٦٧٨٩" "۰۱۲۳۴۵۶۷۸۹",
    "0123456789" * 3,
)


def normalize(text: str) -> str:
    """Documented normalization applied to both reference and hypothesis before CER/WER.

    NFC → lower-case → Arabic diacritics/tatweel removed → alef/ya/ta-marbuta unified →
    Bangla/Arabic-Indic digits to ASCII → punctuation and symbols removed → whitespace collapsed.
    Bangla vowel signs and virama are kept (they are letters, not decoration).
    """
    t = unicodedata.normalize("NFC", text or "").lower()
    t = _AR_DIACRITICS.sub("", t)
    t = t.translate(_AR_LETTERS).translate(_DIGITS)
    t = "".join(" " if unicodedata.category(c)[0] in "PS" else c for c in t)
    return re.sub(r"\s+", " ", t).strip()


def cer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return float(jiwer.cer(ref, hyp))


def wer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return float(jiwer.wer(ref, hyp))


def chrf(reference: str, hypothesis: str) -> float:
    return float(sacrebleu.sentence_chrf(hypothesis or "", [reference]).score)


def corpus_chrf(references: list[str], hypotheses: list[str]) -> float | None:
    if not references:
        return None
    return float(sacrebleu.corpus_chrf(hypotheses, [references]).score)


def percentile(values: list[float], p: float) -> float | None:
    """Linear-interpolated percentile (p in 0..100)."""
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] if lo == hi else xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def mean(values: list[float]) -> float | None:
    xs = [v for v in values if v is not None]
    return sum(xs) / len(xs) if xs else None

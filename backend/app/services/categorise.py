"""Complaint categorisation: keyword rules first, LLM only for the leftovers."""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

import pandas as pd

from ..config import CACHE_DIR
from ..llm import LLMClient

logger = logging.getLogger(__name__)

DAMAGED = "Damaged packaging"
LATE = "Late delivery"
WRONG = "Wrong item"
QUALITY = "Product quality"
SIZING = "Sizing"
OTHER = "Other"

CATEGORIES = [DAMAGED, LATE, WRONG, QUALITY, SIZING, OTHER]

RULE_ORDER: list[tuple[str, str]] = [
    (
        DAMAGED,
        r"damag|crush|broken|dented|leak|spill|tamper|packaging|package was|box was|torn box|seal was|bubble wrap|smashed",
    ),
    (
        LATE,
        r"\blate\b|delay|deliver(y|ed)? (was )?(very )?slow|never arrived|not arrived|hasn.t arrived|didn.t arrive|"
        r"still waiting|past the promised|took \d+ days|arrived after|late again",
    ),
    (
        WRONG,
        r"wrong (item|product|order|size|colour|color|shade)|incorrect item|different (item|product|colour|color)|"
        r"not what i ordered|sent me the wrong|swapped|missing item|item missing",
    ),
    (
        QUALITY,
        r"quality|defect|faulty|doesn.t work|stopped working|faded|shrunk|shrink|stitching|seam|colour ran|color ran|"
        r"expired|irritat|rash|breakout|smell|stain|rough|pilling|flimsy|broke after",
    ),
    (
        SIZING,
        r"\bsize\b|sizing|\bfit\b|too small|too big|too tight|too loose|runs small|runs large|length|"
        r"smaller than|bigger than",
    ),
]

COMPILED_RULES = [(category, re.compile(pattern, re.IGNORECASE)) for category, pattern in RULE_ORDER]

_CACHE: dict[str, str] = {}
_CACHE_FILE = CACHE_DIR / "category_cache.json"


def _load_cache() -> None:
    global _CACHE
    if _CACHE or not _CACHE_FILE.exists():
        return
    try:
        _CACHE = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        _CACHE = {}


def _save_cache() -> None:
    try:
        _CACHE_FILE.write_text(json.dumps(_CACHE), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("category cache not saved: %s", exc)


def classify_text(text: Optional[str]) -> Optional[str]:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None
    value = " ".join(str(text).split())
    if not value:
        return None
    for category, pattern in COMPILED_RULES:
        if pattern.search(value):
            return category
    return None


def normalise_given_category(value: Optional[str]) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    mapping = {
        DAMAGED.lower(): DAMAGED,
        "damage": DAMAGED,
        "packaging": DAMAGED,
        LATE.lower(): LATE,
        "delay": LATE,
        "shipping": LATE,
        WRONG.lower(): WRONG,
        "wrong": WRONG,
        QUALITY.lower(): QUALITY,
        "defect": QUALITY,
        SIZING.lower(): SIZING,
        "size": SIZING,
        OTHER.lower(): OTHER,
    }
    if text in mapping:
        return mapping[text]
    guessed = classify_text(text)
    return guessed or OTHER


def _llm_categorise(texts: list[str], llm: LLMClient) -> dict[str, str]:
    if not llm.configured or not texts:
        return {}
    lookups = [text for text in texts if text in _CACHE]
    results = {text: _CACHE[text] for text in lookups}
    pending = [text for text in texts if text not in results]

    system = (
        "You label customer complaints for an operations team. Reply with JSON only, shaped as "
        '{"categories": ["..."]}, one category per input, in order. Allowed categories: '
        + ", ".join(CATEGORIES)
        + ". Use \"Other\" when unsure. Do not explain."
    )
    for start in range(0, len(pending), 40):
        batch = pending[start : start + 40]
        user = json.dumps({"complaints": batch})
        payload = llm.complete_json(system, user, max_tokens=700)
        labels = payload.get("categories") if isinstance(payload, dict) else None
        if not isinstance(labels, list) or len(labels) != len(batch):
            logger.info("LLM categorisation skipped for a batch of %s complaints", len(batch))
            continue
        for text, label in zip(batch, labels):
            cleaned = normalise_given_category(label) or OTHER
            results[text] = cleaned
            _CACHE[text] = cleaned
    if results:
        _save_cache()
    return results


def categorise(linked, llm: LLMClient) -> tuple[pd.DataFrame, dict, list[str]]:
    """Fill complaint_view['category'] with a controlled vocabulary."""
    _load_cache()
    frame = linked.complaint_view.copy()
    notes: list[str] = []
    if frame.empty:
        return frame, {"keyword": 0, "given": 0, "llm": 0, "other": 0}, ["No complaints file: categorisation skipped."]

    if "category" in frame.columns:
        frame["category"] = frame["category"].map(normalise_given_category)

    keyword_hits = 0
    for index, row in frame.iterrows():
        text_category = classify_text(row.get("complaintText"))
        if text_category is not None:
            frame.at[index, "category"] = text_category
            keyword_hits += 1

    leftover_mask = frame["category"].isna() & frame["complaintText"].notna()
    leftovers = frame.loc[leftover_mask, "complaintText"].astype(str).tolist()
    llm_labels = _llm_categorise(leftovers, llm)
    for index in frame.index[leftover_mask]:
        text = str(frame.at[index, "complaintText"])
        if text in llm_labels:
            frame.at[index, "category"] = llm_labels[text]

    missing_mask = frame["category"].isna()
    frame.loc[missing_mask, "category"] = OTHER
    notes.append(
        f"Categorised {len(frame)} complaints ({keyword_hits} by keyword rules, "
        f"{len(llm_labels)} by LLM, {int(missing_mask.sum())} fallback to Other)."
    )
    counts = {
        "keyword": keyword_hits,
        "given": int(len(frame) - keyword_hits),
        "llm": len(llm_labels),
        "other": int((frame["category"] == OTHER).sum()),
    }
    return frame, counts, notes

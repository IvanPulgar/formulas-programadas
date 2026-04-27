"""
StatementProblemKnowledge — Phase 10: PDF Knowledge Base loader.

Loads queue_exercise_patterns.json and provides pattern-matching helpers
to the StatementAnalyzer.  All lookups are STRUCTURAL — no numeric answers
are stored or returned.

Public API
----------
load_patterns() -> list[dict]
    Returns the full list of exercise pattern objects (cached).

find_matching_patterns(norm_text: str) -> list[PatternHint]
    Keyword-based matching against model_trigger_patterns + exercise keywords.
    Returns best-match hints, ordered by confidence.

get_formula_order_hint(model: str, objective: str) -> list[str]
    Returns the typical formula execution order for a given model+objective pair.

get_unit_conversion_hints(norm_text: str) -> list[str]
    Returns a list of applicable unit-conversion descriptions for the text.

PatternHint (NamedTuple)
    model_id        : str   – e.g. "PICS", "PICM", "PFCS", "PFCM", "PFHET"
    confidence      : float – 0..1 fraction of structural clues matched
    matched_clues   : list[str]
    formula_order_hints : dict[str, list[str]]  – objective → formula list
    unit_conversion_notes : list[str]
    dimensioning_note : str | None
"""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Path resolution — relative to this file, back two levels to project root
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent          # domain/services/
_ROOT = _HERE.parent.parent                       # project root
_KB_PATH = _ROOT / "infrastructure" / "data" / "analysis" / "queue_exercise_patterns.json"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class PatternHint(NamedTuple):
    """Lightweight structural hint returned to the analyzer."""

    model_id: str
    confidence: float
    matched_clues: list[str]
    formula_order_hints: dict[str, list[str]]
    unit_conversion_notes: list[str]
    dimensioning_note: str | None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase + strip Unicode combining characters (accents)."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Cached data loader
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_patterns() -> dict:
    """Load and cache the full knowledge base JSON.  Returns the root dict."""
    if not _KB_PATH.exists():
        return {}
    with _KB_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _get_model_triggers() -> dict[str, dict]:
    return load_patterns().get("model_trigger_patterns", {})


def _get_exercises() -> list[dict]:
    return load_patterns().get("exercises", [])


def _get_unit_conversion_patterns() -> list[dict]:
    return load_patterns().get("unit_conversion_patterns", [])


def _get_dimensioning_patterns() -> list[dict]:
    return load_patterns().get("dimensioning_patterns", [])


# ---------------------------------------------------------------------------
# Core matching: model-level
# ---------------------------------------------------------------------------

def _score_model(model_id: str, trigger: dict, norm_text: str) -> tuple[float, list[str]]:
    """
    Return (score, matched_clues) for one model against normalized text.
    Score = matched / total_clues, penalized if any contra_indicator is found.
    """
    clues = [_normalize(c) for c in trigger.get("structural_clues", [])]
    contra = [_normalize(c) for c in trigger.get("contra_indicators", [])]

    matched = [c for c in clues if c in norm_text]
    disqualifiers = [c for c in contra if c in norm_text]

    if disqualifiers or not clues:
        return 0.0, []

    score = len(matched) / max(len(clues) * 0.35, 1.0)
    return min(round(score, 4), 1.0), matched


# ---------------------------------------------------------------------------
# Build formula-order hint table from exercises
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _build_formula_order_table() -> dict[str, dict[str, list[str]]]:
    """
    Returns  { "PICS.compute_Lq": ["rho", "Lq"], ... }
    derived from the exercises knowledge base.

    When multiple exercises agree on the same model+objective, the first
    (most specific) formula_order from the first matching exercise is used.
    If two exercises disagree, longer formula_order (more detail) wins.
    """
    table: dict[str, list[str]] = {}
    for ex in _get_exercises():
        model = ex.get("detected_model", "")
        for lit in ex.get("literals", []):
            obj = lit.get("objective", "")
            order = lit.get("formula_order", [])
            ctx_model = lit.get("model_context", model)
            if not (ctx_model and obj and order):
                continue
            key = f"{ctx_model}.{obj}"
            existing = table.get(key, [])
            if len(order) > len(existing):
                table[key] = order
    return table


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_matching_patterns(norm_text: str) -> list[PatternHint]:
    """
    Match norm_text against model trigger patterns and return ranked hints.

    Parameters
    ----------
    norm_text : str
        Accent-stripped, lowercased problem statement text.

    Returns
    -------
    list[PatternHint]
        Sorted descending by confidence.  Empty list if knowledge base missing.
    """
    triggers = _get_model_triggers()
    formula_table = _build_formula_order_table()
    unit_patterns = _get_unit_conversion_patterns()
    dim_patterns = _get_dimensioning_patterns()

    hints: list[PatternHint] = []

    for model_id, trigger in triggers.items():
        score, matched = _score_model(model_id, trigger, norm_text)
        if score <= 0.0:
            continue

        # Build formula order hints for this model
        fo_hints: dict[str, list[str]] = {}
        for key, order in formula_table.items():
            key_model, _, key_obj = key.partition(".")
            if key_model == model_id:
                fo_hints[key_obj] = order

        # Collect applicable unit conversion notes
        uc_notes: list[str] = []
        for uc in unit_patterns:
            trigger_phrases = [_normalize(p) for p in uc.get("trigger_phrases", [])]
            if any(p in norm_text for p in trigger_phrases):
                uc_notes.append(uc.get("description", ""))

        # Find first applicable dimensioning note
        dim_note: str | None = None
        for dp in dim_patterns:
            dp_model = dp.get("model", "")
            dp_phrases = [_normalize(p) for p in dp.get("trigger_phrases", [])]
            if dp_model == model_id and any(p in norm_text for p in dp_phrases):
                dim_note = dp.get("description")
                break

        hints.append(PatternHint(
            model_id=model_id,
            confidence=score,
            matched_clues=matched,
            formula_order_hints=fo_hints,
            unit_conversion_notes=uc_notes,
            dimensioning_note=dim_note,
        ))

    hints.sort(key=lambda h: h.confidence, reverse=True)
    return hints


def get_formula_order_hint(model: str, objective: str) -> list[str]:
    """
    Return the typical formula execution order for a given model+objective.

    Parameters
    ----------
    model : str
        e.g. "PICS", "PICM", "PFCS", "PFCM", "PFHET"
    objective : str
        e.g. "compute_Lq", "compute_wait_probability"

    Returns
    -------
    list[str]
        Ordered list of formula identifiers, or empty list if not found.
    """
    table = _build_formula_order_table()
    return list(table.get(f"{model}.{objective}", []))


def get_unit_conversion_hints(norm_text: str) -> list[str]:
    """
    Return descriptions of applicable unit conversions detected in norm_text.
    """
    results: list[str] = []
    for uc in _get_unit_conversion_patterns():
        trigger_phrases = [_normalize(p) for p in uc.get("trigger_phrases", [])]
        if any(p in norm_text for p in trigger_phrases):
            desc = uc.get("description", "")
            if desc:
                results.append(desc)
    return results


def get_all_model_ids() -> list[str]:
    """Return the list of model IDs present in the knowledge base."""
    return list(_get_model_triggers().keys())


def get_exercises_for_model(model_id: str) -> list[dict]:
    """Return all exercise patterns for a given model."""
    return [ex for ex in _get_exercises() if ex.get("detected_model") == model_id]


def knowledge_base_loaded() -> bool:
    """Return True if the knowledge base JSON was found and loaded."""
    return bool(load_patterns())

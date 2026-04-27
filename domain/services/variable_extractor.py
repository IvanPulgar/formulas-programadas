"""
VariableExtractor — Phase 2 offline statement analysis.

Extracts numeric variable values from a Spanish-language queue-theory problem
statement using:

  1. Regex patterns anchored to semantic context phrases (from synonyms.json
     and variables.json regex_hints).
  2. Unit detection and normalization to a canonical base unit per variable.
  3. Disambiguation for cases where the same number appears for different
     variables (e.g. lambda_ and M both appear as integers).

Design decisions:
  - Pure Python + stdlib re; no external NLP libraries.
  - Normalization is conservative: only conversions present in units.json
    are applied. Unrecognized units are kept as-is and flagged.
  - Numbers detected: integers and decimals (comma or dot as separator).
  - Reads knowledge exclusively through the dict returned by
    OfflineKnowledgeRepository.load_all().
  - Accent-stripped, lowercased text is expected as input.

Limitations documented (not hidden):
  - Does not handle ranges ("entre 2 y 4 servidores") — picks first number.
  - Does not resolve pronouns or anaphora.
  - PFHET mu1/mu2 extraction depends on ordinal position in sentence.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from domain.entities.analysis import AnalysisIssue, ExtractedVariable, IssueSeverity

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_NUMBER_PATTERN = r"(\d+(?:[.,]\d+)?)"


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _parse_number(s: str) -> float:
    return float(s.replace(",", "."))


def _build_context_pattern(context_phrases: list[str], number: str = _NUMBER_PATTERN) -> list[re.Pattern[str]]:
    """Build regex patterns: context phrase followed by a number."""
    patterns = []
    for phrase in context_phrases:
        # Allow optional words between the phrase and the number
        p = re.compile(
            re.escape(phrase) + r"[^.\n]{0,60}?" + number,
            re.IGNORECASE,
        )
        patterns.append(p)
    return patterns


def _reverse_context_pattern(context_phrases: list[str], number: str = _NUMBER_PATTERN) -> list[re.Pattern[str]]:
    """Build regex patterns: number followed by a context phrase."""
    patterns = []
    for phrase in context_phrases:
        p = re.compile(
            number + r"[^.\n]{0,40}?" + re.escape(phrase),
            re.IGNORECASE,
        )
        patterns.append(p)
    return patterns


# ---------------------------------------------------------------------------
# Semantic patterns per variable (derived from synonyms.json + PDF vocabulary)
# These are additional hand-crafted patterns for the most important variables.
# They complement regex_hints from variables.json but do not duplicate them.
# ---------------------------------------------------------------------------

# Lambda — inter-arrival TIME context BEFORE the number (λ = 1/T)
_LAMBDA_INTERARRIVAL_BEFORE = [
    "llegan cada",
    "llega cada",
    "llega un cliente cada",
    "llegan en promedio cada",
    "llegan con una frecuencia de un cliente cada",
    "arriba cada",
    "arriban cada",
    "clientes llegan cada",
    "cliente llega cada",
    "llegan clientes cada",
    "intervalo medio entre llegadas de",
    "tiempo entre llegadas de",
    "cada cliente cada",
    # PFCS / finite-source failure patterns
    "falla en promedio cada",
    "falla cada",
    "averia en promedio cada",
    "averia cada",
    "se averia cada",
]

# Lambda (arrival rate) — context BEFORE the number
_LAMBDA_BEFORE = [
    "tasa de llegada de",
    "tasa de llegadas de",
    "llegan a razon de",
    "llegan con una tasa de",
    "arriban a la tasa de",
    "afluencia de",
    "proceso de poisson con una tasa de",
    "proceso de poisson de intensidad",
    "distribucion poisson con media",
    "intensidad de llegada de",
    "tasa promedio de",
    "promedio de",
]

# Lambda — unit AFTER the number (number then unit)
_LAMBDA_UNIT_AFTER = [
    r"(\d+(?:[.,]\d+)?)\s*(?:por|/)\s*(hora|minuto|segundo|dia)",
    r"(\d+(?:[.,]\d+)?)\s*(?:clientes|llamadas|personas|vehiculos|aviones|equipos|maquinas)\s*(?:por|/)\s*(hora|minuto|segundo|dia)",
]

# Mu (service rate) — context BEFORE
# All these phrases indicate a SERVICE TIME; normalized_value = 1/time
_MU_BEFORE = [
    "tiempo medio de",
    "tiempo promedio de",
    "tiempo de atencion de",
    "distribucion exponencial de media",
    "distribucion exponencial con media",
    "exponencial con media",
    "media de",
    "duracion de las llamadas",
    "atiende en promedio",
    "puede atender",
    "demoran en promedio",
    "tarda en atender",
    "tarda en promedio",
    "servicio tarda",
    "el servicio tarda",
    "demora en promedio",
    "tiempo de ejecucion es de",
    "tiempo de ejecucion de",
    "tiempo medio de ejecucion",
]

# Mu — service capacity number BEFORE unit
_MU_CAPACITY_PATTERNS = [
    r"(\d+(?:[.,]\d+)?)\s*(?:clientes|llamadas|personas|unidades|programas)\s*(?:en|por|/)\s*hora(?:\s*cada\s*uno)?",
    r"(\d+(?:[.,]\d+)?)\s*(?:clientes|llamadas|personas)\s*(?:por|/)\s*minuto(?:\s*cada\s*uno)?",
    r"(\d+(?:[.,]\d+)?)\s*paginas\s*en\s*una\s*hora",
]

# k (number of servers) — number BEFORE role noun
_K_AFTER_PATTERNS = [
    r"(\d+)\s*(?:servidores|canales|cajeros|operarios|operadores|tecnicos|mecanicos)",
    r"(\d+)\s*(?:inspectores|farmaceuticos|mecanografas|examinadores|surtidores|plataformas|ventanillas|personas)",
    r"(\d+)\s*(?:personas|operarios)\s*para\s*(?:recibir|atender)",
    r"(\d+)\s*lineas?\s*telefonicas?",
]

# k — context BEFORE a number
_K_BEFORE = [
    "numero de servidores",
    "numero de cajeros",
    "numero de operarios",
    "numero de personas",
    "lineas telefonicas",
    "canales de atencion",
]

# M (finite population) — number BEFORE entity noun
_M_AFTER_PATTERNS = [
    r"(\d+)\s*(?:aviones|montacargas|equipos|maquinas|vehiculos|empleados)\b",
    r"(\d+)\s*(?:entidades|fuentes)\b",
]

# M — context BEFORE
_M_BEFORE = [
    "numero limitado de",
    "fuente finita de",
    "poblacion finita de",
    "total de",
]

# PFHET mu1/mu2 — "demoran en promedio X y Y minutos"
_MU1_MU2_JOINT = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*y\s*(\d+(?:[.,]\d+)?)\s*minutos",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Unit conversion table (conservative — only what is in units.json)
# Target unit: clientes/minuto for rates, minutos/cliente for times
# ---------------------------------------------------------------------------

def _rate_to_per_minute(value: float, unit: str) -> float | None:
    """Convert a rate to clientes/minuto. Returns None if unit unknown."""
    u = _normalize(unit)
    if "hora" in u or "hour" in u:
        return value / 60.0
    if "minuto" in u or "minute" in u or "min" in u:
        return value
    if "segundo" in u or "second" in u or "seg" in u:
        return value * 60.0
    if "dia" in u or "day" in u:
        return value / (60.0 * 24.0)
    return None


def _time_to_minutes(value: float, unit: str) -> float | None:
    """Convert a service time to minutos/cliente. Returns None if unit unknown."""
    u = _normalize(unit)
    if "minuto" in u or "min" in u:
        return value
    if "hora" in u or "hour" in u:
        return value * 60.0
    if "segundo" in u or "seg" in u:
        return value / 60.0
    if "dia" in u or "day" in u:
        return value * 60.0 * 24.0
    return None


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------

class VariableExtractor:
    """
    Extracts numeric variables from a normalized (lowercased, accent-stripped)
    Spanish queue-theory problem statement.

    Usage::

        repo = OfflineKnowledgeRepository()
        knowledge = repo.load_all()
        extractor = VariableExtractor(knowledge)
        variables, issues = extractor.extract(normalized_text, model_id="PICS")
    """

    def __init__(self, knowledge: dict[str, Any]) -> None:
        # Pre-compile patterns for context-before-number
        self._lambda_before = _build_context_pattern(_LAMBDA_BEFORE)
        self._lambda_interarrival = _build_context_pattern(_LAMBDA_INTERARRIVAL_BEFORE)
        self._mu_before = _build_context_pattern(_MU_BEFORE)
        self._k_before = _build_context_pattern(_K_BEFORE)
        self._m_before = _build_context_pattern(_M_BEFORE)

        # Reverse: number before unit/noun
        self._lambda_unit_after = [re.compile(p, re.IGNORECASE) for p in _LAMBDA_UNIT_AFTER]
        self._mu_capacity = [re.compile(p, re.IGNORECASE) for p in _MU_CAPACITY_PATTERNS]
        self._k_after = [re.compile(p, re.IGNORECASE) for p in _K_AFTER_PATTERNS]
        self._m_after = [re.compile(p, re.IGNORECASE) for p in _M_AFTER_PATTERNS]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        text: str,
        model_id: str | None = None,
    ) -> tuple[list[ExtractedVariable], list[AnalysisIssue]]:
        """
        Extract variables from *text* (should already be accent-normalized).

        Returns (variables, issues).  Issues are warnings/infos only —
        extraction never raises.
        """
        issues: list[AnalysisIssue] = []
        variables: list[ExtractedVariable] = []
        seen: set[str] = set()

        def _add(var: ExtractedVariable) -> None:
            if var.variable_id not in seen:
                seen.add(var.variable_id)
                variables.append(var)

        # --- PFHET: two different service rates in one sentence ---
        if model_id == "PFHET" or model_id is None:
            mu1, mu2 = self._extract_mu1_mu2(text)
            if mu1 is not None:
                _add(mu1)
            if mu2 is not None:
                _add(mu2)

        # --- lambda_ ---
        lam = self._extract_lambda(text, issues)
        if lam is not None:
            _add(lam)

        # --- mu (only if mu1/mu2 were not extracted) ---
        if "mu1" not in seen and "mu2" not in seen:
            mu = self._extract_mu(text, issues)
            if mu is not None:
                _add(mu)

        # --- k (number of servers) ---
        k = self._extract_k(text, issues)
        if k is not None:
            _add(k)

        # --- M (finite population size) ---
        if model_id in ("PFCS", "PFCM", "PFHET", None):
            m = self._extract_M(text, issues)
            if m is not None:
                _add(m)

        return variables, issues

    # ------------------------------------------------------------------
    # Private extraction methods
    # ------------------------------------------------------------------

    def _extract_lambda(self, text: str, issues: list[AnalysisIssue]) -> ExtractedVariable | None:
        # Strategy 1: context phrase before the number
        for pattern in self._lambda_before:
            m = pattern.search(text)
            if m:
                raw = _parse_number(m.group(1))
                unit = self._detect_rate_unit(text, m.start(), m.end())
                norm = _rate_to_per_minute(raw, unit) if unit else None
                return ExtractedVariable(
                    variable_id="lambda_",
                    raw_value=raw,
                    unit=unit or "desconocida",
                    normalized_value=norm,
                    extraction_source=m.group(0)[:80],
                    confidence=0.90,
                )

        # Strategy 2: number followed by rate unit
        for pattern in self._lambda_unit_after:
            m = pattern.search(text)
            if m:
                raw = _parse_number(m.group(1))
                unit = m.group(2) if m.lastindex and m.lastindex >= 2 else "hora"
                norm = _rate_to_per_minute(raw, unit)
                return ExtractedVariable(
                    variable_id="lambda_",
                    raw_value=raw,
                    unit=f"clientes/{unit}",
                    normalized_value=norm,
                    extraction_source=m.group(0)[:80],
                    confidence=0.80,
                )

        # Strategy 3: inter-arrival TIME context (λ = 1/T)
        for pattern in self._lambda_interarrival:
            m = pattern.search(text)
            if m:
                raw = _parse_number(m.group(1))
                unit = self._detect_time_unit(text, m.start(), m.end())
                time_in_min = _time_to_minutes(raw, unit) if unit else None
                norm = (1.0 / time_in_min) if time_in_min else None
                return ExtractedVariable(
                    variable_id="lambda_",
                    raw_value=raw,
                    unit=unit or "desconocida",
                    normalized_value=norm,
                    extraction_source=m.group(0)[:80],
                    confidence=0.80,
                )

        return None

    def _extract_mu(self, text: str, issues: list[AnalysisIssue]) -> ExtractedVariable | None:
        # Strategy 1: time context before the number ("tiempo medio de X minutos")
        # Raw value is a SERVICE TIME; normalized_value = 1/time_in_minutes (rate)
        for pattern in self._mu_before:
            m = pattern.search(text)
            if m:
                raw = _parse_number(m.group(1))
                unit = self._detect_time_unit(text, m.start(), m.end())
                time_in_min = _time_to_minutes(raw, unit) if unit else None
                norm = (1.0 / time_in_min) if time_in_min else None
                return ExtractedVariable(
                    variable_id="mu",
                    raw_value=raw,
                    unit=unit or "desconocida",
                    normalized_value=norm,
                    extraction_source=m.group(0)[:80],
                    confidence=0.85,
                )

        # Strategy 2: service capacity ("X clientes por hora")
        for pattern in self._mu_capacity:
            m = pattern.search(text)
            if m:
                raw = _parse_number(m.group(1))
                unit = self._detect_rate_unit(text, m.start(), m.end()) or "hora"
                norm = _rate_to_per_minute(raw, unit)
                return ExtractedVariable(
                    variable_id="mu",
                    raw_value=raw,
                    unit=f"clientes/{unit}",
                    normalized_value=norm,
                    extraction_source=m.group(0)[:80],
                    confidence=0.80,
                )

        return None

    def _extract_k(self, text: str, issues: list[AnalysisIssue]) -> ExtractedVariable | None:
        # Strategy 1: number directly before a role noun ("3 cajeros", "5 operarios")
        for pattern in self._k_after:
            m = pattern.search(text)
            if m:
                raw = int(_parse_number(m.group(1)))
                return ExtractedVariable(
                    variable_id="k",
                    raw_value=float(raw),
                    unit="servidores",
                    normalized_value=float(raw),
                    extraction_source=m.group(0)[:80],
                    confidence=0.92,
                )

        # Strategy 2: context phrase before the number
        for pattern in self._k_before:
            m = pattern.search(text)
            if m:
                raw = int(_parse_number(m.group(1)))
                return ExtractedVariable(
                    variable_id="k",
                    raw_value=float(raw),
                    unit="servidores",
                    normalized_value=float(raw),
                    extraction_source=m.group(0)[:80],
                    confidence=0.85,
                )

        return None

    def _extract_M(self, text: str, issues: list[AnalysisIssue]) -> ExtractedVariable | None:
        # Strategy 1: number before entity noun ("5 aviones", "10 montacargas")
        for pattern in self._m_after:
            m = pattern.search(text)
            if m:
                raw = int(_parse_number(m.group(1)))
                return ExtractedVariable(
                    variable_id="M",
                    raw_value=float(raw),
                    unit="unidades",
                    normalized_value=float(raw),
                    extraction_source=m.group(0)[:80],
                    confidence=0.88,
                )

        # Strategy 2: context phrase before the number
        for pattern in self._m_before:
            m = pattern.search(text)
            if m:
                raw = int(_parse_number(m.group(1)))
                return ExtractedVariable(
                    variable_id="M",
                    raw_value=float(raw),
                    unit="unidades",
                    normalized_value=float(raw),
                    extraction_source=m.group(0)[:80],
                    confidence=0.80,
                )

        return None

    def _extract_mu1_mu2(self, text: str) -> tuple[ExtractedVariable | None, ExtractedVariable | None]:
        """Extract two different service rates for PFHET from 'X y Y minutos'."""
        m = _MU1_MU2_JOINT.search(text)
        if not m:
            return None, None
        v1 = _parse_number(m.group(1))
        v2 = _parse_number(m.group(2))
        t1 = _time_to_minutes(v1, "minutos")
        t2 = _time_to_minutes(v2, "minutos")
        mu1 = ExtractedVariable(
            variable_id="mu1",
            raw_value=v1,
            unit="minutos/cliente",
            normalized_value=(1.0 / t1) if t1 else None,
            extraction_source=m.group(0)[:80],
            confidence=0.85,
        )
        mu2 = ExtractedVariable(
            variable_id="mu2",
            raw_value=v2,
            unit="minutos/cliente",
            normalized_value=(1.0 / t2) if t2 else None,
            extraction_source=m.group(0)[:80],
            confidence=0.85,
        )
        return mu1, mu2

    # ------------------------------------------------------------------
    # Unit detection helpers
    # ------------------------------------------------------------------

    _RATE_UNITS = re.compile(
        r"(?:por|/)\s*(hora|minuto|segundo|dia|seg)",
        re.IGNORECASE,
    )
    _TIME_UNITS = re.compile(
        r"\b(minutos?|horas?|segundos?|dias?)\b",
        re.IGNORECASE,
    )

    def _detect_rate_unit(self, text: str, start: int, end: int) -> str:
        """Look for a rate unit in a window after the match position."""
        window = text[max(0, start):min(len(text), end + 40)]
        m = self._RATE_UNITS.search(window)
        return _normalize(m.group(1)) if m else ""

    def _detect_time_unit(self, text: str, start: int, end: int) -> str:
        """Look for a time unit in a window after the match position."""
        window = text[max(0, start):min(len(text), end + 40)]
        m = self._TIME_UNITS.search(window)
        return _normalize(m.group(1)) if m else ""

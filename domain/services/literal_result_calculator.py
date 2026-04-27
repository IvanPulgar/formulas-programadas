"""
LiteralResultCalculator — Phase 15.

Computes numeric results for individual literals detected in the
'Analizar enunciado' pipeline.

Supports:
  - PICS / M/M/1  — λ and μ required
  - PICM / M/M/c  — λ, μ and k required
  - PFCS          — λ, μ and M required

NOT in scope this phase:
  - PFCM / PFHET numerical evaluation
  - Cost / optimization / profitability objectives
  - Automatic k/M/c determination

Design decisions:
  - Pure Python + stdlib math; no external dependencies.
  - Reads variables from StatementAnalysisResult.extracted_variables via
    normalized_value (rates in clientes/minuto for λ and μ).
  - All intermediate results are computed from extracted variables; no
    hard-coded answers from any PDF exercise.
  - Does NOT call orchestrator, matcher or solver.
  - Completely additive; does not modify any existing module.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Optional

from domain.entities.analysis import (
    CalculationStep,
    DetectedLiteral,
    LiteralCalculationResult,
    StatementAnalysisResult,
)
from domain.services.literal_segmenter import UNSUPPORTED_OBJECTIVES

# ---------------------------------------------------------------------------
# Objectives that cannot be calculated in this phase
# ---------------------------------------------------------------------------

_UNSUPPORTED_CALC: frozenset[str] = UNSUPPORTED_OBJECTIVES | frozenset({
    "compute_profitability",
})

# ---------------------------------------------------------------------------
# Internal normalizer
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

def _detect_base_time_unit(lambda_unit: str, mu_unit: str) -> str:
    """Determine display time unit ('hora', 'minuto', 'segundo') from variable units."""
    for u in (lambda_unit, mu_unit):
        if not u or u in ("desconocida", "unidades", "servidores", ""):
            continue
        u_low = _norm(u)
        if "hora" in u_low:
            return "hora"
        if "seg" in u_low:
            return "segundo"
        if "minuto" in u_low or "min" in u_low:
            return "minuto"
    return "minuto"


def _to_display_rate(rate_per_min: float, base_unit: str) -> float:
    """Convert per-minute rate to the display time unit."""
    if base_unit == "hora":
        return rate_per_min * 60.0
    if base_unit == "segundo":
        return rate_per_min / 60.0
    return rate_per_min


def _time_to_display_unit(time_in_min: float, base_unit: str) -> float:
    """Convert a time value (minutes) to the display time unit."""
    if base_unit == "hora":
        return time_in_min / 60.0
    if base_unit == "segundo":
        return time_in_min * 60.0
    return time_in_min


def _format_time(time_in_min: float, base_unit: str) -> str:
    """Build a human-readable time string with secondary-unit conversion."""
    if base_unit == "hora":
        hours = time_in_min / 60.0
        return f"{hours:.4f} h = {time_in_min:.2f} min"
    if base_unit == "segundo":
        seconds = time_in_min * 60.0
        return f"{time_in_min:.4f} min = {seconds:.2f} s"
    # base_unit == "minuto"
    if time_in_min < 1.0:
        return f"{time_in_min:.4f} min = {time_in_min * 60.0:.2f} s"
    return f"{time_in_min:.4f} min"


# ---------------------------------------------------------------------------
# Period extraction from statement text (hours/day, hours/week, etc.)
# ---------------------------------------------------------------------------

_PERIOD_HOURS_DAY = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*hora[s]?\s*(?:al?\s*)?(?:d[ií]a|dia)\b",
    re.IGNORECASE,
)
_PERIOD_HOURS_WEEK = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*hora[s]?\s*(?:a\s*la\s*|por\s+)?semana\b",
    re.IGNORECASE,
)
_PERIOD_DAYS_WEEK = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*d[ií]a[s]?\s*(?:a\s*la\s*|por\s+)?semana\b",
    re.IGNORECASE,
)


def _extract_period_minutes(norm_text: str) -> tuple[Optional[float], str]:
    """
    Extract operating period from normalized text.
    Returns (period_in_minutes, label) or (None, '').
    """
    m = _PERIOD_HOURS_DAY.search(norm_text)
    if m:
        hours = float(m.group(1).replace(",", "."))
        return hours * 60.0, f"{hours:.0f} horas/día"
    m = _PERIOD_HOURS_WEEK.search(norm_text)
    if m:
        hours = float(m.group(1).replace(",", "."))
        return hours * 60.0, f"{hours:.0f} horas/semana"
    m = _PERIOD_DAYS_WEEK.search(norm_text)
    if m:
        days = float(m.group(1).replace(",", "."))
        return days * 60.0 * 24.0, f"{days:.0f} días/semana"
    return None, ""


# ---------------------------------------------------------------------------
# Threshold extraction from literal text (for P(Q≥r))
# ---------------------------------------------------------------------------

_THRESHOLD_DIGIT_RE = re.compile(
    r"(?:mas\s*de|al\s*menos|por\s*lo\s*menos|igual\s*o\s*mayor(?:\s*a|\s*que)?)"
    r"\s*(?:a\s*)?(\d+)",
    re.IGNORECASE,
)

_WORD_NUM: dict[str, int] = {
    "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}

_THRESHOLD_WORD_RE = re.compile(
    r"(?:mas\s*de|al\s*menos|por\s*lo\s*menos)"
    r"\s*(" + "|".join(_WORD_NUM.keys()) + r")\b",
    re.IGNORECASE,
)


def _extract_threshold(norm_text: str) -> Optional[int]:
    """Extract numeric threshold r from literal text."""
    m = _THRESHOLD_DIGIT_RE.search(norm_text)
    if m:
        return int(m.group(1))
    m = _THRESHOLD_WORD_RE.search(norm_text)
    if m:
        return _WORD_NUM.get(_norm(m.group(1)))
    return None


# ---------------------------------------------------------------------------
# Erlang C (M/M/c) helpers
# ---------------------------------------------------------------------------

def _picm_p0(a: float, rho: float, c: int) -> float:
    """Compute P₀ for M/M/c (Erlang C formula)."""
    sum_part = sum(a**n / math.factorial(n) for n in range(c))
    last_part = a**c / (math.factorial(c) * (1.0 - rho))
    return 1.0 / (sum_part + last_part)


def _picm_pw(a: float, rho: float, c: int, P0: float) -> float:
    """Compute Pw (probability of waiting / Erlang C) for M/M/c."""
    return (a**c / (math.factorial(c) * (1.0 - rho))) * P0


def _picm_pn(n: int, a: float, rho: float, c: int, P0: float) -> float:
    """Compute P(N=n) for M/M/c."""
    if n <= c:
        return (a**n / math.factorial(n)) * P0
    return (a**c / math.factorial(c)) * (rho ** (n - c)) * P0


# ---------------------------------------------------------------------------
# PFCS helpers
# ---------------------------------------------------------------------------

def _pfcs_p0(M: int, r: float) -> float:
    """Compute P₀ for PFCS (finite-source, single-server M/M/1/M/M model)."""
    denom = sum(math.comb(M, n) * r**n for n in range(M + 1))
    return 1.0 / denom


def _pfcs_pn(n: int, M: int, r: float, P0: float) -> float:
    """Compute P(n) for PFCS."""
    return math.comb(M, n) * r**n * P0


# ---------------------------------------------------------------------------
# Main calculator
# ---------------------------------------------------------------------------

class LiteralResultCalculator:
    """
    Computes numeric results per literal for the 'Analizar enunciado' module.

    Usage::

        calc = LiteralResultCalculator()
        calc_result = calc.calculate(analysis_result, detected_literal)
    """

    def calculate(
        self,
        result: StatementAnalysisResult,
        lit: DetectedLiteral,
    ) -> LiteralCalculationResult:
        """Compute the numeric result for a single literal."""
        obj = lit.inferred_objective
        model = result.identified_model

        # ── Objectives unsupported in this phase ────────────────────────────
        if obj in _UNSUPPORTED_CALC:
            if obj in ("compute_cost", "compute_total_cost"):
                code = "cost_calculation_not_implemented"
            elif obj in ("compare_alternatives", "optimize_cost"):
                code = "optimization_not_implemented"
            else:
                code = "calculation_not_implemented"
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=False,
                issues=[code],
            )

        # ── No objective detected ────────────────────────────────────────────
        if obj is None:
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=None,
                calculated=False,
                issues=["no_objective_detected"],
            )

        # ── Dispatch by model ────────────────────────────────────────────────
        if model == "PICS":
            return self._calc_pics(result, lit)
        if model == "PICM":
            return self._calc_picm(result, lit)
        if model == "PFCS":
            return self._calc_pfcs(result, lit)

        return LiteralCalculationResult(
            literal_id=lit.literal_id,
            objective=obj,
            calculated=False,
            issues=["model_not_calculable_this_phase"],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PICS / M/M/1
    # ──────────────────────────────────────────────────────────────────────────

    def _calc_pics(
        self,
        result: StatementAnalysisResult,
        lit: DetectedLiteral,
    ) -> LiteralCalculationResult:
        obj = lit.inferred_objective
        steps: list[CalculationStep] = []

        # ── Extract variables ────────────────────────────────────────────────
        lambda_ev = result.get_variable("lambda_")
        mu_ev = result.get_variable("mu")
        missing: list[str] = []
        if lambda_ev is None or lambda_ev.normalized_value is None:
            missing.append("lambda_")
        if mu_ev is None or mu_ev.normalized_value is None:
            missing.append("mu")
        if missing:
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=False,
                issues=[f"missing_variables: {', '.join(missing)}"],
            )

        lam: float = lambda_ev.normalized_value  # type: ignore[assignment]
        mu: float = mu_ev.normalized_value        # type: ignore[assignment]
        base_unit = _detect_base_time_unit(lambda_ev.unit, mu_ev.unit)
        lam_d = _to_display_rate(lam, base_unit)
        mu_d = _to_display_rate(mu, base_unit)

        # ── Step 1: ρ ─────────────────────────────────────────────────────────
        rho = lam / mu
        steps.append(CalculationStep(
            formula_key="rho",
            expression="ρ = λ / μ",
            substitution=f"ρ = {lam_d:.4f} / {mu_d:.4f}",
            result=f"ρ = {rho:.4f}",
        ))

        # ── Stability check ──────────────────────────────────────────────────
        if rho >= 1.0:
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=False,
                calculation_steps=steps,
                issues=["unstable_system"],
            )

        # ── Pre-compute all PICS metrics ──────────────────────────────────────
        P0 = 1.0 - rho
        Lq = rho**2 / (1.0 - rho)
        Wq_min = Lq / lam
        W_min = Wq_min + 1.0 / mu
        L_val = lam * W_min

        # ── P0 / compute_server_available_probability ─────────────────────────
        if obj in ("compute_P0", "compute_server_available_probability"):
            steps.append(CalculationStep(
                formula_key="P0",
                expression="P₀ = 1 − ρ",
                substitution=f"P₀ = 1 − {rho:.4f}",
                result=f"P₀ = {P0:.4f}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=P0,
                unit="probabilidad",
                display_value=f"{P0:.4f}",
                calculation_steps=steps,
            )

        # ── P(wait) = ρ ───────────────────────────────────────────────────────
        if obj == "compute_wait_probability":
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=rho,
                unit="probabilidad",
                display_value=f"{rho:.4f}",
                calculation_steps=steps,
            )

        # ── Lq ────────────────────────────────────────────────────────────────
        if obj == "compute_Lq":
            steps.append(CalculationStep(
                formula_key="Lq",
                expression="Lq = ρ² / (1 − ρ)",
                substitution=f"Lq = {rho:.4f}² / (1 − {rho:.4f})",
                result=f"Lq = {Lq:.4f}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=Lq,
                unit="clientes",
                display_value=f"{Lq:.4f} clientes",
                calculation_steps=steps,
            )

        # ── Wq ────────────────────────────────────────────────────────────────
        if obj == "compute_Wq":
            Wq_d = _time_to_display_unit(Wq_min, base_unit)
            steps.append(CalculationStep(
                formula_key="Lq",
                expression="Lq = ρ² / (1 − ρ)",
                substitution=f"Lq = {rho:.4f}² / (1 − {rho:.4f})",
                result=f"Lq = {Lq:.4f}",
            ))
            steps.append(CalculationStep(
                formula_key="Wq",
                expression="Wq = Lq / λ",
                substitution=f"Wq = {Lq:.4f} / {lam_d:.4f}",
                result=f"Wq = {_format_time(Wq_min, base_unit)}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=Wq_min,
                unit="Wq",
                display_value=_format_time(Wq_min, base_unit),
                calculation_steps=steps,
            )

        # ── W ─────────────────────────────────────────────────────────────────
        if obj == "compute_W":
            Wq_d = _time_to_display_unit(Wq_min, base_unit)
            svc_d = _time_to_display_unit(1.0 / mu, base_unit)
            steps.append(CalculationStep(
                formula_key="Lq",
                expression="Lq = ρ² / (1 − ρ)",
                substitution=f"Lq = {rho:.4f}² / (1 − {rho:.4f})",
                result=f"Lq = {Lq:.4f}",
            ))
            steps.append(CalculationStep(
                formula_key="Wq",
                expression="Wq = Lq / λ",
                substitution=f"Wq = {Lq:.4f} / {lam_d:.4f}",
                result=f"Wq = {_format_time(Wq_min, base_unit)}",
            ))
            steps.append(CalculationStep(
                formula_key="W",
                expression="W = Wq + 1/μ",
                substitution=f"W = {Wq_d:.4f} + {svc_d:.4f}",
                result=f"W = {_format_time(W_min, base_unit)}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=W_min,
                unit="W",
                display_value=_format_time(W_min, base_unit),
                calculation_steps=steps,
            )

        # ── L ─────────────────────────────────────────────────────────────────
        if obj == "compute_L":
            Wq_d = _time_to_display_unit(Wq_min, base_unit)
            svc_d = _time_to_display_unit(1.0 / mu, base_unit)
            W_d = _time_to_display_unit(W_min, base_unit)
            steps.append(CalculationStep(
                formula_key="Lq",
                expression="Lq = ρ² / (1 − ρ)",
                substitution=f"Lq = {rho:.4f}² / (1 − {rho:.4f})",
                result=f"Lq = {Lq:.4f}",
            ))
            steps.append(CalculationStep(
                formula_key="Wq",
                expression="Wq = Lq / λ",
                substitution=f"Wq = {Lq:.4f} / {lam_d:.4f}",
                result=f"Wq = {_format_time(Wq_min, base_unit)}",
            ))
            steps.append(CalculationStep(
                formula_key="W",
                expression="W = Wq + 1/μ",
                substitution=f"W = {Wq_d:.4f} + {svc_d:.4f}",
                result=f"W = {_format_time(W_min, base_unit)}",
            ))
            steps.append(CalculationStep(
                formula_key="L",
                expression="L = λ · W",
                substitution=f"L = {lam_d:.4f} · {W_d:.4f}",
                result=f"L = {L_val:.4f}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=L_val,
                unit="clientes",
                display_value=f"{L_val:.4f} clientes",
                calculation_steps=steps,
            )

        # ── P(Q > 0) = ρ² ────────────────────────────────────────────────────
        if obj == "compute_probability_queue_nonempty":
            p_val = rho**2
            steps.append(CalculationStep(
                formula_key="P_queue_nonempty",
                expression="P(Q > 0) = ρ²",
                substitution=f"P(Q > 0) = {rho:.4f}²",
                result=f"P(Q > 0) = {p_val:.6f}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=p_val,
                unit="probabilidad",
                display_value=f"{p_val:.6f}",
                calculation_steps=steps,
            )

        # ── P(Q ≥ r) = ρ^(r+1) ───────────────────────────────────────────────
        if obj == "compute_probability_q_at_least_r":
            r_val = _extract_threshold(lit.normalized_text) or 2
            m_val = r_val + 1
            p_val = rho**m_val
            steps.append(CalculationStep(
                formula_key="P_N_ge_m",
                expression=f"P(Q ≥ {r_val}) = P(N ≥ {m_val}) = ρ^{m_val}",
                substitution=f"P(Q ≥ {r_val}) = {rho:.6f}^{m_val}",
                result=f"P(Q ≥ {r_val}) = {p_val:.6f}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=p_val,
                unit="probabilidad",
                display_value=f"{p_val:.6f}",
                calculation_steps=steps,
            )

        # ── P(Q=1 o Q=2) ─────────────────────────────────────────────────────
        if obj == "compute_probability_q_between":
            steps.append(CalculationStep(
                formula_key="P0",
                expression="P₀ = 1 − ρ",
                substitution=f"P₀ = 1 − {rho:.4f}",
                result=f"P₀ = {P0:.4f}",
            ))
            # P(N=n) = P0 × ρⁿ  →  P(Q=q) = P(N=q+1) = P0 × ρ^(q+1)
            p1 = P0 * rho**2   # P(Q=1) = P(N=2)
            p2 = P0 * rho**3   # P(Q=2) = P(N=3)
            p_val = p1 + p2
            steps.append(CalculationStep(
                formula_key="Pn",
                expression="P(Q=q) = P₀ · ρ^(q+1)",
                substitution=f"P(N=2) = {P0:.4f}·{rho:.4f}² = {p1:.6f};  P(N=3) = {P0:.4f}·{rho:.4f}³ = {p2:.6f}",
                result=f"P(Q=1 o 2) = {p_val:.6f}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=p_val,
                unit="probabilidad",
                display_value=f"{p_val:.6f}",
                calculation_steps=steps,
            )

        # ── Idle time per period ──────────────────────────────────────────────
        if obj == "compute_idle_time":
            steps.append(CalculationStep(
                formula_key="P0",
                expression="P₀ = 1 − ρ",
                substitution=f"P₀ = 1 − {rho:.4f}",
                result=f"P₀ = {P0:.4f}",
            ))
            period_min, period_label = _extract_period_minutes(result.normalized_text)
            if period_min is None:
                steps.append(CalculationStep(
                    formula_key="T_libre",
                    expression="T_libre = P₀ × T_período",
                    substitution="T_período no encontrado en el enunciado",
                    result="Sin resultado",
                ))
                return LiteralCalculationResult(
                    literal_id=lit.literal_id,
                    objective=obj,
                    calculated=False,
                    calculation_steps=steps,
                    issues=["missing_period_hours"],
                )
            T_libre = P0 * period_min
            steps.append(CalculationStep(
                formula_key="T_libre",
                expression="T_libre = P₀ × T_período",
                substitution=f"T_libre = {P0:.4f} × {period_min:.0f} min ({period_label})",
                result=f"T_libre = {T_libre:.2f} min/período",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=T_libre,
                unit="min",
                display_value=f"{T_libre:.2f} min/período",
                calculation_steps=steps,
            )

        # ── Arrivals per period that wait ─────────────────────────────────────
        if obj == "compute_waiting_arrivals":
            period_min, period_label = _extract_period_minutes(result.normalized_text)
            if period_min is None:
                return LiteralCalculationResult(
                    literal_id=lit.literal_id,
                    objective=obj,
                    calculated=False,
                    issues=["missing_period_hours"],
                )
            arrivals = lam * period_min * rho
            steps.append(CalculationStep(
                formula_key="arrivals_waiting",
                expression="Llegadas_espera = λ × T_período × ρ",
                substitution=f"Llegadas_espera = {lam:.4f} × {period_min:.0f} × {rho:.4f}",
                result=f"Llegadas_espera = {arrivals:.2f} clientes/período",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=arrivals,
                unit="clientes/periodo",
                display_value=f"{arrivals:.2f} clientes/período",
                calculation_steps=steps,
            )

        # ── Objective not mapped for PICS ─────────────────────────────────────
        return LiteralCalculationResult(
            literal_id=lit.literal_id,
            objective=obj,
            calculated=False,
            issues=["objective_not_implemented_for_model"],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PICM / M/M/c
    # ──────────────────────────────────────────────────────────────────────────

    def _calc_picm(
        self,
        result: StatementAnalysisResult,
        lit: DetectedLiteral,
    ) -> LiteralCalculationResult:
        obj = lit.inferred_objective
        steps: list[CalculationStep] = []

        # ── Extract variables ────────────────────────────────────────────────
        lambda_ev = result.get_variable("lambda_")
        mu_ev = result.get_variable("mu")
        k_ev = result.get_variable("k")
        missing: list[str] = []
        if lambda_ev is None or lambda_ev.normalized_value is None:
            missing.append("lambda_")
        if mu_ev is None or mu_ev.normalized_value is None:
            missing.append("mu")
        if k_ev is None or k_ev.normalized_value is None:
            missing.append("k")
        if missing:
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=False,
                issues=[f"missing_variables: {', '.join(missing)}"],
            )

        lam: float = lambda_ev.normalized_value  # type: ignore[assignment]
        mu: float = mu_ev.normalized_value        # type: ignore[assignment]
        c: int = int(k_ev.normalized_value)       # type: ignore[assignment]

        base_unit = _detect_base_time_unit(lambda_ev.unit, mu_ev.unit)
        lam_d = _to_display_rate(lam, base_unit)
        mu_d = _to_display_rate(mu, base_unit)

        # ── Step 1: a (traffic intensity) ────────────────────────────────────
        a = lam / mu
        steps.append(CalculationStep(
            formula_key="a",
            expression="a = λ / μ",
            substitution=f"a = {lam_d:.4f} / {mu_d:.4f}",
            result=f"a = {a:.4f}",
        ))

        # ── Step 2: ρ per server ─────────────────────────────────────────────
        rho = lam / (c * mu)
        steps.append(CalculationStep(
            formula_key="rho",
            expression="ρ = λ / (c · μ) = a / c",
            substitution=f"ρ = {a:.4f} / {c}",
            result=f"ρ = {rho:.4f}",
        ))

        # ── Stability check ──────────────────────────────────────────────────
        if rho >= 1.0:
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=False,
                calculation_steps=steps,
                issues=["unstable_system"],
            )

        # ── Step 3: P0 ───────────────────────────────────────────────────────
        P0 = _picm_p0(a, rho, c)
        steps.append(CalculationStep(
            formula_key="P0",
            expression="P₀ = [Σₙ₌₀ᶜ⁻¹ aⁿ/n! + aᶜ/(c!(1−ρ))]⁻¹",
            substitution=f"a={a:.4f}, c={c}, ρ={rho:.4f}",
            result=f"P₀ = {P0:.6f}",
        ))

        # ── Step 4: Pw (Erlang C) ─────────────────────────────────────────────
        Pw = _picm_pw(a, rho, c, P0)
        steps.append(CalculationStep(
            formula_key="Pw",
            expression="Pw = [aᶜ / (c!(1−ρ))] · P₀  — fórmula de Erlang C",
            substitution=f"a={a:.4f}, c={c}, ρ={rho:.4f}, P₀={P0:.6f}",
            result=f"Pw = {Pw:.6f}",
        ))

        # ── Pre-compute remaining metrics ─────────────────────────────────────
        Lq = Pw * rho / (1.0 - rho)
        Wq_min = Lq / lam
        W_min = Wq_min + 1.0 / mu
        L_val = lam * W_min
        P_free = 1.0 - Pw   # P(at least one server free)

        # ── P(wait) = Pw ─────────────────────────────────────────────────────
        if obj == "compute_wait_probability":
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=Pw,
                unit="probabilidad",
                display_value=f"{Pw:.6f}",
                calculation_steps=steps,
            )

        # ── P(≥1 servidor libre) = 1 − Pw ────────────────────────────────────
        if obj == "compute_server_available_probability":
            steps.append(CalculationStep(
                formula_key="P_libre",
                expression="P(≥1 libre) = 1 − Pw",
                substitution=f"P(≥1 libre) = 1 − {Pw:.6f}",
                result=f"P(≥1 libre) = {P_free:.6f}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=P_free,
                unit="probabilidad",
                display_value=f"{P_free:.6f}",
                calculation_steps=steps,
            )

        # ── Lq ────────────────────────────────────────────────────────────────
        if obj == "compute_Lq":
            steps.append(CalculationStep(
                formula_key="Lq",
                expression="Lq = Pw · ρ / (1 − ρ)",
                substitution=f"Lq = {Pw:.6f} · {rho:.4f} / (1 − {rho:.4f})",
                result=f"Lq = {Lq:.6f}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=Lq,
                unit="clientes",
                display_value=f"{Lq:.6f} clientes",
                calculation_steps=steps,
            )

        # ── Wq ────────────────────────────────────────────────────────────────
        if obj == "compute_Wq":
            steps.append(CalculationStep(
                formula_key="Lq",
                expression="Lq = Pw · ρ / (1 − ρ)",
                substitution=f"Lq = {Pw:.6f} · {rho:.4f} / (1 − {rho:.4f})",
                result=f"Lq = {Lq:.6f}",
            ))
            steps.append(CalculationStep(
                formula_key="Wq",
                expression="Wq = Lq / λ",
                substitution=f"Wq = {Lq:.6f} / {lam_d:.4f}",
                result=f"Wq = {_format_time(Wq_min, base_unit)}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=Wq_min,
                unit="Wq",
                display_value=_format_time(Wq_min, base_unit),
                calculation_steps=steps,
            )

        # ── W ─────────────────────────────────────────────────────────────────
        if obj == "compute_W":
            Wq_d = _time_to_display_unit(Wq_min, base_unit)
            svc_d = _time_to_display_unit(1.0 / mu, base_unit)
            steps.append(CalculationStep(
                formula_key="Lq",
                expression="Lq = Pw · ρ / (1 − ρ)",
                substitution=f"Lq = {Pw:.6f} · {rho:.4f} / (1 − {rho:.4f})",
                result=f"Lq = {Lq:.6f}",
            ))
            steps.append(CalculationStep(
                formula_key="Wq",
                expression="Wq = Lq / λ",
                substitution=f"Wq = {Lq:.6f} / {lam_d:.4f}",
                result=f"Wq = {_format_time(Wq_min, base_unit)}",
            ))
            steps.append(CalculationStep(
                formula_key="W",
                expression="W = Wq + 1/μ",
                substitution=f"W = {Wq_d:.4f} + {svc_d:.4f}",
                result=f"W = {_format_time(W_min, base_unit)}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=W_min,
                unit="W",
                display_value=_format_time(W_min, base_unit),
                calculation_steps=steps,
            )

        # ── L ─────────────────────────────────────────────────────────────────
        if obj == "compute_L":
            Wq_d = _time_to_display_unit(Wq_min, base_unit)
            svc_d = _time_to_display_unit(1.0 / mu, base_unit)
            W_d = _time_to_display_unit(W_min, base_unit)
            steps.append(CalculationStep(
                formula_key="Lq",
                expression="Lq = Pw · ρ / (1 − ρ)",
                substitution=f"Lq = {Pw:.6f} · {rho:.4f} / (1 − {rho:.4f})",
                result=f"Lq = {Lq:.6f}",
            ))
            steps.append(CalculationStep(
                formula_key="Wq",
                expression="Wq = Lq / λ",
                substitution=f"Wq = {Lq:.6f} / {lam_d:.4f}",
                result=f"Wq = {_format_time(Wq_min, base_unit)}",
            ))
            steps.append(CalculationStep(
                formula_key="W",
                expression="W = Wq + 1/μ",
                substitution=f"W = {Wq_d:.4f} + {svc_d:.4f}",
                result=f"W = {_format_time(W_min, base_unit)}",
            ))
            steps.append(CalculationStep(
                formula_key="L",
                expression="L = λ · W",
                substitution=f"L = {lam_d:.4f} · {W_d:.4f}",
                result=f"L = {L_val:.6f}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=L_val,
                unit="clientes",
                display_value=f"{L_val:.6f} clientes",
                calculation_steps=steps,
            )

        # ── Idle time per period (PICM) ───────────────────────────────────────
        if obj == "compute_idle_time":
            steps.append(CalculationStep(
                formula_key="P_libre",
                expression="P(≥1 libre) = 1 − Pw",
                substitution=f"P(≥1 libre) = 1 − {Pw:.6f}",
                result=f"P(≥1 libre) = {P_free:.6f}",
            ))
            period_min, period_label = _extract_period_minutes(result.normalized_text)
            if period_min is None:
                return LiteralCalculationResult(
                    literal_id=lit.literal_id,
                    objective=obj,
                    calculated=False,
                    calculation_steps=steps,
                    issues=["missing_period_hours"],
                )
            T_libre = P_free * period_min
            steps.append(CalculationStep(
                formula_key="T_libre",
                expression="T_libre = P(≥1 libre) × T_período",
                substitution=f"T_libre = {P_free:.6f} × {period_min:.0f} min ({period_label})",
                result=f"T_libre = {T_libre:.2f} min/período",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=T_libre,
                unit="min",
                display_value=f"{T_libre:.2f} min/período",
                calculation_steps=steps,
            )

        # ── Arrivals per period that wait (PICM) ──────────────────────────────
        if obj == "compute_waiting_arrivals":
            period_min, period_label = _extract_period_minutes(result.normalized_text)
            if period_min is None:
                return LiteralCalculationResult(
                    literal_id=lit.literal_id,
                    objective=obj,
                    calculated=False,
                    issues=["missing_period_hours"],
                )
            arrivals = lam * period_min * Pw
            steps.append(CalculationStep(
                formula_key="arrivals_waiting",
                expression="Llegadas_espera = λ × T_período × Pw",
                substitution=f"Llegadas_espera = {lam:.4f} × {period_min:.0f} × {Pw:.6f}",
                result=f"Llegadas_espera = {arrivals:.2f} clientes/período",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=arrivals,
                unit="clientes/periodo",
                display_value=f"{arrivals:.2f} clientes/período",
                calculation_steps=steps,
            )

        # ── P(Q=1 o Q=2) in M/M/c ────────────────────────────────────────────
        if obj == "compute_probability_q_between":
            # Q=q means N=c+q → P(Q=1)=P(N=c+1), P(Q=2)=P(N=c+2)
            Pn_c1 = _picm_pn(c + 1, a, rho, c, P0)
            Pn_c2 = _picm_pn(c + 2, a, rho, c, P0)
            p_val = Pn_c1 + Pn_c2
            steps.append(CalculationStep(
                formula_key="Pn_between",
                expression=f"P(Q=1) = P(N={c+1}),  P(Q=2) = P(N={c+2})",
                substitution=f"P(N={c+1}) = {Pn_c1:.6f},  P(N={c+2}) = {Pn_c2:.6f}",
                result=f"P(Q=1 o 2) = {p_val:.6f}",
            ))
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=p_val,
                unit="probabilidad",
                display_value=f"{p_val:.6f}",
                calculation_steps=steps,
            )

        # ── Objective not mapped for PICM ─────────────────────────────────────
        return LiteralCalculationResult(
            literal_id=lit.literal_id,
            objective=obj,
            calculated=False,
            issues=["objective_not_implemented_for_model"],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PFCS / finite-source single-server
    # ──────────────────────────────────────────────────────────────────────────

    def _calc_pfcs(
        self,
        result: StatementAnalysisResult,
        lit: DetectedLiteral,
    ) -> LiteralCalculationResult:
        obj = lit.inferred_objective
        steps: list[CalculationStep] = []

        # ── Extract variables ────────────────────────────────────────────────
        lambda_ev = result.get_variable("lambda_")
        mu_ev = result.get_variable("mu")
        M_ev = result.get_variable("M")
        missing: list[str] = []
        if lambda_ev is None or lambda_ev.normalized_value is None:
            missing.append("lambda_")
        if mu_ev is None or mu_ev.normalized_value is None:
            missing.append("mu")
        if M_ev is None or M_ev.normalized_value is None:
            missing.append("M")
        if missing:
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=False,
                issues=[f"missing_variables: {', '.join(missing)}"],
            )

        lam_ind: float = lambda_ev.normalized_value  # type: ignore[assignment]  # per-unit failure rate
        mu_rep: float = mu_ev.normalized_value        # type: ignore[assignment]  # repair rate
        M: int = int(M_ev.normalized_value)           # type: ignore[assignment]  # population size

        # ── Step 1: r ─────────────────────────────────────────────────────────
        r = lam_ind / mu_rep
        steps.append(CalculationStep(
            formula_key="r",
            expression="r = λ / μ",
            substitution=f"r = {lam_ind:.8f} / {mu_rep:.8f}",
            result=f"r = {r:.6f}",
        ))

        # ── Step 2: P0 ───────────────────────────────────────────────────────
        P0 = _pfcs_p0(M, r)
        steps.append(CalculationStep(
            formula_key="P0",
            expression="P₀ = [Σₙ₌₀ᴹ C(M,n) · rⁿ]⁻¹",
            substitution=f"M={M}, r={r:.6f}",
            result=f"P₀ = {P0:.6f}",
        ))

        # ── Step 3: L = Σ n·Pn ───────────────────────────────────────────────
        Pn_vals = [_pfcs_pn(n, M, r, P0) for n in range(M + 1)]
        L_val = sum(n * Pn_vals[n] for n in range(M + 1))
        steps.append(CalculationStep(
            formula_key="L",
            expression="L = Σₙ₌₀ᴹ n · Pₙ",
            substitution=f"Σ n·Pₙ con M={M}, r={r:.4f}",
            result=f"L = {L_val:.6f}",
        ))

        # ── Step 4: Lq = L − (1 − P0) ───────────────────────────────────────
        Lq = L_val - (1.0 - P0)
        steps.append(CalculationStep(
            formula_key="Lq",
            expression="Lq = L − (1 − P₀)",
            substitution=f"Lq = {L_val:.6f} − (1 − {P0:.6f})",
            result=f"Lq = {Lq:.6f}",
        ))

        # ── Step 5: fracción operando ─────────────────────────────────────────
        frac_op = (M - L_val) / M
        steps.append(CalculationStep(
            formula_key="frac_op",
            expression="Fracción operando = (M − L) / M",
            substitution=f"({M} − {L_val:.4f}) / {M}",
            result=f"Fracción operando = {frac_op:.6f}",
        ))

        # ── P0 / P(taller libre) ─────────────────────────────────────────────
        if obj in ("compute_P0", "compute_server_available_probability"):
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=P0,
                unit="probabilidad",
                display_value=f"{P0:.6f}",
                calculation_steps=steps,
            )

        # ── L ─────────────────────────────────────────────────────────────────
        if obj == "compute_L":
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=L_val,
                unit="unidades",
                display_value=f"{L_val:.4f} unidades",
                calculation_steps=steps,
            )

        # ── Lq ────────────────────────────────────────────────────────────────
        if obj == "compute_Lq":
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=Lq,
                unit="unidades",
                display_value=f"{Lq:.4f} unidades",
                calculation_steps=steps,
            )

        # ── Fraction operating ────────────────────────────────────────────────
        if obj == "compute_fraction_operating":
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=True,
                value=frac_op,
                unit="fracción",
                display_value=f"{frac_op:.4f} ({frac_op * 100:.1f}%)",
                calculation_steps=steps,
            )

        # ── Wq via effective arrival rate ─────────────────────────────────────
        if obj == "compute_Wq":
            lam_eff = (M - L_val) * lam_ind
            if lam_eff > 0 and Lq >= 0:
                Wq_min = Lq / lam_eff
                base_unit = _detect_base_time_unit(lambda_ev.unit, mu_ev.unit)
                steps.append(CalculationStep(
                    formula_key="Wq",
                    expression="λ_eff = (M − L)·λ,  Wq = Lq / λ_eff",
                    substitution=f"λ_eff = ({M} − {L_val:.4f})·{lam_ind:.8f} = {lam_eff:.8f}\nWq = {Lq:.6f} / {lam_eff:.8f}",
                    result=f"Wq = {_format_time(Wq_min, base_unit)}",
                ))
                return LiteralCalculationResult(
                    literal_id=lit.literal_id,
                    objective=obj,
                    calculated=True,
                    value=Wq_min,
                    unit="Wq",
                    display_value=_format_time(Wq_min, _detect_base_time_unit(lambda_ev.unit, mu_ev.unit)),
                    calculation_steps=steps,
                )
            return LiteralCalculationResult(
                literal_id=lit.literal_id,
                objective=obj,
                calculated=False,
                calculation_steps=steps,
                issues=["wq_computation_failed"],
            )

        # ── Default: return Lq as representative PFCS metric ─────────────────
        return LiteralCalculationResult(
            literal_id=lit.literal_id,
            objective=obj,
            calculated=True,
            value=Lq,
            unit="unidades",
            display_value=f"{Lq:.4f} unidades",
            calculation_steps=steps,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_calculator() -> LiteralResultCalculator:
    """Factory function for LiteralResultCalculator."""
    return LiteralResultCalculator()

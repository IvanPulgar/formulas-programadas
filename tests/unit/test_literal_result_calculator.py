"""
Unit tests for LiteralResultCalculator — Phase 15.

Covers:
  - PICS / M/M/1: ρ, P0, Lq, Wq, W, L, P(Q≥r), P(Q=1|2),
                  idle_time, waiting_arrivals, unstable, missing vars
  - PICM / M/M/c: a, ρ, P0, Pw, Lq, Wq, W, L,
                  server_available, idle_time, waiting_arrivals
  - PFCS: r, P0, L, Lq, frac_op, Wq
  - Unsupported objectives and missing model
  - Factory function make_calculator()

No test reads the PDF or hard-codes values derived from it.
All expected values are computed independently with the same formulae.
"""

from __future__ import annotations

import math
from typing import Optional

import pytest

from domain.entities.analysis import (
    AnalysisConfidence,
    DetectedLiteral,
    ExtractedVariable,
    LiteralCalculationResult,
    StatementAnalysisResult,
)
from domain.services.literal_result_calculator import (
    LiteralResultCalculator,
    _detect_base_time_unit,
    _extract_threshold,
    _format_time,
    _pfcs_p0,
    _pfcs_pn,
    _picm_p0,
    _picm_pw,
    _time_to_display_unit,
    _to_display_rate,
    make_calculator,
)


# ---------------------------------------------------------------------------
# Helpers to build fake analysis results for testing
# ---------------------------------------------------------------------------

def _ev(var_id: str, raw: float, unit: str, norm: Optional[float] = None) -> ExtractedVariable:
    from dataclasses import dataclass
    ev = ExtractedVariable.__new__(ExtractedVariable)
    ev.variable_id = var_id
    ev.raw_value = raw
    ev.unit = unit
    ev.normalized_value = norm if norm is not None else raw
    ev.extraction_source = "test"
    ev.confidence = 1.0
    return ev


def _lit(
    literal_id: str,
    objective: Optional[str],
    norm_text: str = "",
    raw_text: str = "",
) -> DetectedLiteral:
    lit = DetectedLiteral.__new__(DetectedLiteral)
    lit.literal_id = literal_id
    lit.raw_text = raw_text or objective or ""
    lit.normalized_text = norm_text or (objective or "")
    lit.inferred_objective = objective
    lit.planned_step_ids = []
    lit.issues = []
    lit.formula_plan = []
    lit.missing_variables = []
    lit.calculation_result = None
    return lit


def _result_pics(
    lam_norm: float,
    mu_norm: float,
    lam_unit: str = "clientes/hora",
    mu_unit: str = "clientes/hora",
    extra_text: str = "",
) -> StatementAnalysisResult:
    r = StatementAnalysisResult()
    r.identified_model = "PICS"
    r.model_confidence = AnalysisConfidence.HIGH
    r.normalized_text = extra_text
    r.extracted_variables = [
        _ev("lambda_", lam_norm, lam_unit, lam_norm),
        _ev("mu", mu_norm, mu_unit, mu_norm),
    ]
    return r


def _result_picm(
    lam_norm: float,
    mu_norm: float,
    k: int,
    lam_unit: str = "clientes/hora",
    mu_unit: str = "clientes/hora",
    extra_text: str = "",
) -> StatementAnalysisResult:
    r = StatementAnalysisResult()
    r.identified_model = "PICM"
    r.model_confidence = AnalysisConfidence.HIGH
    r.normalized_text = extra_text
    r.extracted_variables = [
        _ev("lambda_", lam_norm, lam_unit, lam_norm),
        _ev("mu", mu_norm, mu_unit, mu_norm),
        _ev("k", float(k), "servidores", float(k)),
    ]
    return r


def _result_pfcs(
    lam_norm: float,
    mu_norm: float,
    M: int,
    lam_unit: str = "fallas/minuto",
    mu_unit: str = "reparaciones/minuto",
) -> StatementAnalysisResult:
    r = StatementAnalysisResult()
    r.identified_model = "PFCS"
    r.model_confidence = AnalysisConfidence.HIGH
    r.normalized_text = ""
    r.extracted_variables = [
        _ev("lambda_", lam_norm, lam_unit, lam_norm),
        _ev("mu", mu_norm, mu_unit, mu_norm),
        _ev("M", float(M), "unidades", float(M)),
    ]
    return r


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_make_calculator_returns_instance(self):
        calc = make_calculator()
        assert isinstance(calc, LiteralResultCalculator)


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_detect_base_unit_hora(self):
        assert _detect_base_time_unit("clientes/hora", "") == "hora"

    def test_detect_base_unit_minuto(self):
        assert _detect_base_time_unit("clientes/minuto", "") == "minuto"

    def test_detect_base_unit_segundo(self):
        assert _detect_base_time_unit("", "seg") == "segundo"

    def test_detect_base_unit_default(self):
        assert _detect_base_time_unit("", "") == "minuto"

    def test_to_display_rate_hora(self):
        # 2 per min × 60 = 120 per hour
        assert _to_display_rate(2.0, "hora") == pytest.approx(120.0)

    def test_to_display_rate_minuto(self):
        assert _to_display_rate(5.0, "minuto") == pytest.approx(5.0)

    def test_to_display_rate_segundo(self):
        # 1 per min / 60 ≈ 0.01667 per second
        assert _to_display_rate(1.0, "segundo") == pytest.approx(1.0 / 60.0)

    def test_time_to_display_hora(self):
        # 60 min = 1 h
        assert _time_to_display_unit(60.0, "hora") == pytest.approx(1.0)

    def test_time_to_display_segundo(self):
        # 1 min = 60 s
        assert _time_to_display_unit(1.0, "segundo") == pytest.approx(60.0)

    def test_format_time_hora(self):
        s = _format_time(90.0, "hora")
        assert "h" in s and "min" in s

    def test_format_time_minuto_lt1(self):
        s = _format_time(0.5, "minuto")
        assert "s" in s

    def test_extract_threshold_digit(self):
        assert _extract_threshold("al menos 3 clientes en cola") == 3

    def test_extract_threshold_word(self):
        assert _extract_threshold("al menos dos") == 2

    def test_extract_threshold_none(self):
        assert _extract_threshold("tiempo promedio en cola") is None

    def test_pfcs_p0_single_unit(self):
        # M=1, r=1 → P0 = 1/(1 + 1) = 0.5
        assert _pfcs_p0(1, 1.0) == pytest.approx(0.5)

    def test_picm_p0_single_server(self):
        # c=1, a=0.5, rho=0.5 → P0 = 1 − rho = 0.5
        P0 = _picm_p0(0.5, 0.5, 1)
        assert P0 == pytest.approx(0.5, rel=1e-4)

    def test_picm_pw_equals_rho_when_c1(self):
        # For c=1, Pw=ρ=a
        a = 0.6
        P0 = _picm_p0(a, a, 1)
        Pw = _picm_pw(a, a, 1, P0)
        assert Pw == pytest.approx(a, rel=1e-4)


# ---------------------------------------------------------------------------
# PICS tests
# ---------------------------------------------------------------------------

# λ = 10/hr = 1/6 per min; μ = 15/hr = 1/4 per min; ρ = 2/3
_LAM_PICS = 10.0 / 60.0
_MU_PICS = 15.0 / 60.0
_RHO_PICS = _LAM_PICS / _MU_PICS  # 2/3


class TestPICS:
    """Tests for PICS / M/M/1 computations."""

    def setup_method(self):
        self.calc = LiteralResultCalculator()
        self.result = _result_pics(_LAM_PICS, _MU_PICS, "clientes/hora", "clientes/hora")

    def _compute(self, obj, norm=""):
        lit = _lit("a", obj, norm_text=norm)
        return self.calc.calculate(self.result, lit)

    # ── P0 ──────────────────────────────────────────────────────────────────
    def test_P0_calculated(self):
        cr = self._compute("compute_P0")
        assert cr.calculated
        assert cr.value == pytest.approx(1.0 - _RHO_PICS, rel=1e-4)

    def test_P0_unit_is_probabilidad(self):
        cr = self._compute("compute_P0")
        assert cr.unit == "probabilidad"

    # ── server_available_probability same as P0 for PICS ─────────────────
    def test_server_available_probability(self):
        cr = self._compute("compute_server_available_probability")
        assert cr.calculated
        assert cr.value == pytest.approx(1.0 - _RHO_PICS, rel=1e-4)

    # ── wait_probability = rho ────────────────────────────────────────────
    def test_wait_probability(self):
        cr = self._compute("compute_wait_probability")
        assert cr.calculated
        assert cr.value == pytest.approx(_RHO_PICS, rel=1e-4)

    # ── Lq ───────────────────────────────────────────────────────────────
    def test_Lq(self):
        expected_Lq = _RHO_PICS**2 / (1.0 - _RHO_PICS)
        cr = self._compute("compute_Lq")
        assert cr.calculated
        assert cr.value == pytest.approx(expected_Lq, rel=1e-4)

    # ── Wq ───────────────────────────────────────────────────────────────
    def test_Wq(self):
        Lq = _RHO_PICS**2 / (1.0 - _RHO_PICS)
        expected_Wq_min = Lq / _LAM_PICS
        cr = self._compute("compute_Wq")
        assert cr.calculated
        assert cr.value == pytest.approx(expected_Wq_min, rel=1e-4)

    # ── W ────────────────────────────────────────────────────────────────
    def test_W(self):
        Lq = _RHO_PICS**2 / (1.0 - _RHO_PICS)
        Wq = Lq / _LAM_PICS
        expected_W = Wq + 1.0 / _MU_PICS
        cr = self._compute("compute_W")
        assert cr.calculated
        assert cr.value == pytest.approx(expected_W, rel=1e-4)

    # ── L ────────────────────────────────────────────────────────────────
    def test_L(self):
        Lq = _RHO_PICS**2 / (1.0 - _RHO_PICS)
        Wq = Lq / _LAM_PICS
        W = Wq + 1.0 / _MU_PICS
        expected_L = _LAM_PICS * W
        cr = self._compute("compute_L")
        assert cr.calculated
        assert cr.value == pytest.approx(expected_L, rel=1e-4)

    # ── P(Q≥r) ───────────────────────────────────────────────────────────
    def test_probability_q_at_least_r(self):
        # al menos 2 → r=2, m=3, P(Q≥2) = ρ^3
        r = 2
        expected = _RHO_PICS ** (r + 1)
        cr = self._compute("compute_probability_q_at_least_r",
                           norm="al menos 2 en cola")
        assert cr.calculated
        assert cr.value == pytest.approx(expected, rel=1e-4)

    # ── P(Q=1 o Q=2) ─────────────────────────────────────────────────────
    def test_probability_q_between(self):
        P0 = 1.0 - _RHO_PICS
        p1 = P0 * _RHO_PICS**2
        p2 = P0 * _RHO_PICS**3
        expected = p1 + p2
        cr = self._compute("compute_probability_q_between")
        assert cr.calculated
        assert cr.value == pytest.approx(expected, rel=1e-4)

    # ── Idle time ─────────────────────────────────────────────────────────
    def test_idle_time_with_period(self):
        # "8 horas al dia" → period=480 min; must be in result.normalized_text
        result = _result_pics(_LAM_PICS, _MU_PICS, "clientes/hora", "clientes/hora",
                              extra_text="trabaja 8 horas al dia")
        lit = _lit("a", "compute_idle_time")
        cr = self.calc.calculate(result, lit)
        assert cr.calculated
        P0 = 1.0 - _RHO_PICS
        expected = P0 * 480.0
        assert cr.value == pytest.approx(expected, rel=1e-4)

    def test_idle_time_missing_period(self):
        cr = self._compute("compute_idle_time", norm="calcular minutos libres")
        assert not cr.calculated
        assert any("missing_period_hours" in i for i in cr.issues)

    # ── Waiting arrivals ──────────────────────────────────────────────────
    def test_waiting_arrivals_with_period(self):
        result = _result_pics(_LAM_PICS, _MU_PICS, "clientes/hora", "clientes/hora",
                              extra_text="8 horas al dia")
        period_min = 480.0
        expected = _LAM_PICS * period_min * _RHO_PICS
        lit = _lit("a", "compute_waiting_arrivals")
        cr = self.calc.calculate(result, lit)
        assert cr.calculated
        assert cr.value == pytest.approx(expected, rel=1e-4)

    def test_waiting_arrivals_missing_period(self):
        cr = self._compute("compute_waiting_arrivals", norm="calcular clientes")
        assert not cr.calculated

    # ── Unstable system ───────────────────────────────────────────────────
    def test_unstable_system(self):
        unstable = _result_pics(20.0 / 60.0, 15.0 / 60.0)  # ρ > 1
        lit = _lit("a", "compute_Lq")
        cr = self.calc.calculate(unstable, lit)
        assert not cr.calculated
        assert any("unstable" in i for i in cr.issues)

    # ── Missing variables ─────────────────────────────────────────────────
    def test_missing_lambda(self):
        r = StatementAnalysisResult()
        r.identified_model = "PICS"
        r.model_confidence = AnalysisConfidence.HIGH
        r.normalized_text = ""
        r.extracted_variables = [_ev("mu", _MU_PICS, "clientes/hora", _MU_PICS)]
        lit = _lit("a", "compute_Lq")
        cr = self.calc.calculate(r, lit)
        assert not cr.calculated
        assert any("lambda_" in i for i in cr.issues)

    # ── calculation_steps are populated ──────────────────────────────────
    def test_Lq_has_steps(self):
        cr = self._compute("compute_Lq")
        assert len(cr.calculation_steps) >= 2  # rho + Lq

    def test_W_step_count(self):
        cr = self._compute("compute_W")
        assert len(cr.calculation_steps) >= 3  # rho + Lq + Wq + W

    # ── Unknown objective ─────────────────────────────────────────────────
    def test_unknown_objective_for_pics(self):
        cr = self._compute("compute_fraction_operating")
        assert not cr.calculated
        assert any("objective_not_implemented" in i for i in cr.issues)

    # ── No objective ──────────────────────────────────────────────────────
    def test_none_objective(self):
        cr = self._compute(None)
        assert not cr.calculated
        assert any("no_objective_detected" in i for i in cr.issues)

    # ── Unsupported objectives return calculated=False ────────────────────
    def test_unsupported_cost_objective(self):
        cr = self._compute("compute_cost")
        assert not cr.calculated

    def test_unsupported_optimize_cost(self):
        cr = self._compute("optimize_cost")
        assert not cr.calculated


# ---------------------------------------------------------------------------
# PICM tests
# ---------------------------------------------------------------------------

# λ = 20/hr = 1/3 per min; μ = 15/hr = 1/4 per min; c = 2
_LAM_PICM = 20.0 / 60.0
_MU_PICM = 15.0 / 60.0
_C_PICM = 2
_A_PICM = _LAM_PICM / _MU_PICM         # ~1.333
_RHO_PICM = _A_PICM / _C_PICM          # ~0.667


class TestPICM:
    """Tests for PICM / M/M/c computations."""

    def setup_method(self):
        self.calc = LiteralResultCalculator()
        self.result = _result_picm(
            _LAM_PICM, _MU_PICM, _C_PICM,
            "clientes/hora", "clientes/hora",
        )

    def _compute(self, obj, norm=""):
        lit = _lit("a", obj, norm_text=norm)
        return self.calc.calculate(self.result, lit)

    def _expected_P0(self):
        return _picm_p0(_A_PICM, _RHO_PICM, _C_PICM)

    def _expected_Pw(self):
        P0 = self._expected_P0()
        return _picm_pw(_A_PICM, _RHO_PICM, _C_PICM, P0)

    def _expected_Lq(self):
        Pw = self._expected_Pw()
        return Pw * _RHO_PICM / (1.0 - _RHO_PICM)

    # ── Basic metrics ─────────────────────────────────────────────────────
    def test_wait_probability(self):
        cr = self._compute("compute_wait_probability")
        assert cr.calculated
        assert cr.value == pytest.approx(self._expected_Pw(), rel=1e-4)

    def test_server_available_probability(self):
        cr = self._compute("compute_server_available_probability")
        assert cr.calculated
        expected = 1.0 - self._expected_Pw()
        assert cr.value == pytest.approx(expected, rel=1e-4)

    def test_Lq(self):
        cr = self._compute("compute_Lq")
        assert cr.calculated
        assert cr.value == pytest.approx(self._expected_Lq(), rel=1e-4)

    def test_Wq(self):
        Lq = self._expected_Lq()
        expected_Wq = Lq / _LAM_PICM
        cr = self._compute("compute_Wq")
        assert cr.calculated
        assert cr.value == pytest.approx(expected_Wq, rel=1e-4)

    def test_W(self):
        Lq = self._expected_Lq()
        Wq = Lq / _LAM_PICM
        expected_W = Wq + 1.0 / _MU_PICM
        cr = self._compute("compute_W")
        assert cr.calculated
        assert cr.value == pytest.approx(expected_W, rel=1e-4)

    def test_L(self):
        Lq = self._expected_Lq()
        Wq = Lq / _LAM_PICM
        W = Wq + 1.0 / _MU_PICM
        expected_L = _LAM_PICM * W
        cr = self._compute("compute_L")
        assert cr.calculated
        assert cr.value == pytest.approx(expected_L, rel=1e-4)

    # ── Idle time (PICM) ─────────────────────────────────────────────────
    def test_idle_time(self):
        result = _result_picm(_LAM_PICM, _MU_PICM, _C_PICM,
                              "clientes/hora", "clientes/hora",
                              extra_text="opera 8 horas al dia")
        P_free = 1.0 - self._expected_Pw()
        expected = P_free * 480.0
        lit = _lit("a", "compute_idle_time")
        cr = self.calc.calculate(result, lit)
        assert cr.calculated
        assert cr.value == pytest.approx(expected, rel=1e-4)

    # ── Waiting arrivals (PICM) ───────────────────────────────────────────
    def test_waiting_arrivals(self):
        result = _result_picm(_LAM_PICM, _MU_PICM, _C_PICM,
                              "clientes/hora", "clientes/hora",
                              extra_text="8 horas al dia")
        Pw = self._expected_Pw()
        expected = _LAM_PICM * 480.0 * Pw
        lit = _lit("a", "compute_waiting_arrivals")
        cr = self.calc.calculate(result, lit)
        assert cr.calculated
        assert cr.value == pytest.approx(expected, rel=1e-4)

    # ── Unstable system ───────────────────────────────────────────────────
    def test_unstable_picm(self):
        unstable = _result_picm(50.0 / 60.0, 15.0 / 60.0, 2)  # ρ > 1
        lit = _lit("a", "compute_Lq")
        cr = self.calc.calculate(unstable, lit)
        assert not cr.calculated
        assert any("unstable" in i for i in cr.issues)

    # ── Missing k ────────────────────────────────────────────────────────
    def test_missing_k(self):
        r = StatementAnalysisResult()
        r.identified_model = "PICM"
        r.model_confidence = AnalysisConfidence.HIGH
        r.normalized_text = ""
        r.extracted_variables = [
            _ev("lambda_", _LAM_PICM, "clientes/hora", _LAM_PICM),
            _ev("mu", _MU_PICM, "clientes/hora", _MU_PICM),
        ]
        lit = _lit("a", "compute_Lq")
        cr = self.calc.calculate(r, lit)
        assert not cr.calculated
        assert any("k" in i for i in cr.issues)


# ---------------------------------------------------------------------------
# PFCS tests
# ---------------------------------------------------------------------------

# M = 5 machines, λ = 1/100 failures/min per machine, μ = 1/20 repairs/min
_M_PFCS = 5
_LAM_PFCS = 1.0 / 100.0   # per min per unit
_MU_PFCS = 1.0 / 20.0     # per min
_R_PFCS = _LAM_PFCS / _MU_PFCS  # = 0.2


class TestPFCS:
    """Tests for PFCS finite-source single-server computations."""

    def setup_method(self):
        self.calc = LiteralResultCalculator()
        self.result = _result_pfcs(_LAM_PFCS, _MU_PFCS, _M_PFCS)

    def _compute(self, obj):
        lit = _lit("a", obj)
        return self.calc.calculate(self.result, lit)

    def _expected_P0(self):
        return _pfcs_p0(_M_PFCS, _R_PFCS)

    def _expected_Pn(self, n):
        return _pfcs_pn(n, _M_PFCS, _R_PFCS, self._expected_P0())

    def _expected_L(self):
        P0 = self._expected_P0()
        return sum(n * _pfcs_pn(n, _M_PFCS, _R_PFCS, P0) for n in range(_M_PFCS + 1))

    def _expected_Lq(self):
        P0 = self._expected_P0()
        L = self._expected_L()
        return L - (1.0 - P0)

    # ── P0 ───────────────────────────────────────────────────────────────
    def test_P0(self):
        cr = self._compute("compute_P0")
        assert cr.calculated
        assert cr.value == pytest.approx(self._expected_P0(), rel=1e-4)

    # ── L ────────────────────────────────────────────────────────────────
    def test_L(self):
        cr = self._compute("compute_L")
        assert cr.calculated
        assert cr.value == pytest.approx(self._expected_L(), rel=1e-4)

    # ── Lq ───────────────────────────────────────────────────────────────
    def test_Lq(self):
        cr = self._compute("compute_Lq")
        assert cr.calculated
        assert cr.value == pytest.approx(self._expected_Lq(), rel=1e-4)

    # ── Fraction operating ────────────────────────────────────────────────
    def test_fraction_operating(self):
        L = self._expected_L()
        expected = (_M_PFCS - L) / _M_PFCS
        cr = self._compute("compute_fraction_operating")
        assert cr.calculated
        assert cr.value == pytest.approx(expected, rel=1e-4)

    # ── Wq ───────────────────────────────────────────────────────────────
    def test_Wq(self):
        L = self._expected_L()
        Lq = self._expected_Lq()
        lam_eff = (_M_PFCS - L) * _LAM_PFCS
        expected_Wq = Lq / lam_eff
        cr = self._compute("compute_Wq")
        assert cr.calculated
        assert cr.value == pytest.approx(expected_Wq, rel=1e-3)

    # ── Steps populated ──────────────────────────────────────────────────
    def test_pfcs_has_steps(self):
        cr = self._compute("compute_Lq")
        assert len(cr.calculation_steps) >= 3

    # ── Missing M ────────────────────────────────────────────────────────
    def test_missing_M(self):
        r = StatementAnalysisResult()
        r.identified_model = "PFCS"
        r.model_confidence = AnalysisConfidence.HIGH
        r.normalized_text = ""
        r.extracted_variables = [
            _ev("lambda_", _LAM_PFCS, "fallas/min", _LAM_PFCS),
            _ev("mu", _MU_PFCS, "reps/min", _MU_PFCS),
        ]
        lit = _lit("a", "compute_Lq")
        cr = self.calc.calculate(r, lit)
        assert not cr.calculated
        assert any("M" in i for i in cr.issues)

    # ── server_available = P0 for PFCS ───────────────────────────────────
    def test_server_available_probability_equals_P0(self):
        cr = self._compute("compute_server_available_probability")
        assert cr.calculated
        assert cr.value == pytest.approx(self._expected_P0(), rel=1e-4)


# ---------------------------------------------------------------------------
# Unsupported model / no objective
# ---------------------------------------------------------------------------

class TestUnsupportedCases:
    def setup_method(self):
        self.calc = LiteralResultCalculator()

    def test_pfcm_not_calculable(self):
        r = StatementAnalysisResult()
        r.identified_model = "PFCM"
        r.model_confidence = AnalysisConfidence.LOW
        r.normalized_text = ""
        r.extracted_variables = []
        lit = _lit("a", "compute_Lq")
        cr = self.calc.calculate(r, lit)
        assert not cr.calculated
        assert any("not_calculable" in i for i in cr.issues)

    def test_pfhet_not_calculable(self):
        r = StatementAnalysisResult()
        r.identified_model = "PFHET"
        r.model_confidence = AnalysisConfidence.LOW
        r.normalized_text = ""
        r.extracted_variables = []
        lit = _lit("a", "compute_L")
        cr = self.calc.calculate(r, lit)
        assert not cr.calculated

    def test_compare_alternatives_unsupported(self):
        r = _result_pics(_LAM_PICS, _MU_PICS)
        lit = _lit("a", "compare_alternatives")
        cr = self.calc.calculate(r, lit)
        assert not cr.calculated

    def test_optimize_cost_unsupported(self):
        r = _result_pics(_LAM_PICS, _MU_PICS)
        lit = _lit("a", "optimize_cost")
        cr = self.calc.calculate(r, lit)
        assert not cr.calculated

    def test_literal_id_preserved(self):
        r = _result_pics(_LAM_PICS, _MU_PICS)
        lit = _lit("c", "compute_P0")
        cr = self.calc.calculate(r, lit)
        assert cr.literal_id == "c"

    def test_objective_preserved(self):
        r = _result_pics(_LAM_PICS, _MU_PICS)
        lit = _lit("a", "compute_P0")
        cr = self.calc.calculate(r, lit)
        assert cr.objective == "compute_P0"

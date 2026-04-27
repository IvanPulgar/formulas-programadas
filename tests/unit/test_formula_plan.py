"""
Phase 11 — Tests for formula_plan_builder.py.

8 mandatory test cases covering:
  1. PICS / compute_Wq — plan structure & ordering
  2. PICM / compute_L  — full chain order
  3. PFCS / compute_Wq — correct produces sequence
  4. PFCM / compute_P0 — minimal plan
  5. PFHET / compute_units_operating — all steps present
  6. Missing variable detection with empty extracted set
  7. No false missing-vars when all base vars are provided
  8. Unknown model → empty plan (graceful degradation)
"""

from __future__ import annotations

import pytest

from domain.services.formula_plan_builder import (
    FormulaPlanStep,
    build_formula_plan,
    get_all_models,
    get_available_objectives,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def plan_keys(plan: list[FormulaPlanStep]) -> list[str]:
    """Return the formula_key of each step in order."""
    return [s.formula_key for s in plan]


def produces_sequence(plan: list[FormulaPlanStep]) -> list[str]:
    """Return what each step produces, in order."""
    return [s.produces for s in plan]


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — PICS / compute_Wq: plan structure & ordering
# ─────────────────────────────────────────────────────────────────────────────

def test_pics_compute_wq_plan_structure():
    """Plan for PICS / compute_Wq must contain rho → Lq → Wq in that order."""
    plan, _ = build_formula_plan("PICS", "compute_Wq", {"lambda_", "mu"})

    assert len(plan) >= 3, "Expected at least 3 steps for PICS/compute_Wq"

    produced = produces_sequence(plan)
    assert "rho" in produced
    assert "Lq" in produced
    assert "Wq" in produced

    # Order must respect dependency: rho < Lq < Wq
    rho_idx = produced.index("rho")
    lq_idx = produced.index("Lq")
    wq_idx = produced.index("Wq")
    assert rho_idx < lq_idx < wq_idx, (
        f"Expected rho ({rho_idx}) < Lq ({lq_idx}) < Wq ({wq_idx})"
    )


def test_pics_plan_order_numbers_are_sequential():
    """FormulaPlanStep.order must be 1, 2, 3, … without gaps."""
    plan, _ = build_formula_plan("PICS", "compute_Wq", {"lambda_", "mu"})
    orders = [s.order for s in plan]
    assert orders == list(range(1, len(plan) + 1))


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — PICM / compute_L: full chain order
# ─────────────────────────────────────────────────────────────────────────────

def test_picm_compute_L_chain():
    """
    PICM / compute_L must produce: a, rho, P0, Pw, Lq, Wq, W, L in that order.
    """
    plan, _ = build_formula_plan("PICM", "compute_L", {"lambda_", "mu", "k"})

    produced = produces_sequence(plan)
    expected_subsequence = ["a", "rho", "P0", "Pw", "Lq", "Wq", "W", "L"]

    # Check all expected keys are present
    for key in expected_subsequence:
        assert key in produced, f"Expected '{key}' in PICM/compute_L plan; got {produced}"

    # Check order is respected
    for i in range(len(expected_subsequence) - 1):
        idx_a = produced.index(expected_subsequence[i])
        idx_b = produced.index(expected_subsequence[i + 1])
        assert idx_a < idx_b, (
            f"Step '{expected_subsequence[i]}' must precede '{expected_subsequence[i+1]}'; "
            f"positions: {idx_a}, {idx_b}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — PFCS / compute_Wq: produces sequence
# ─────────────────────────────────────────────────────────────────────────────

def test_pfcs_compute_wq_produces_sequence():
    """PFCS / compute_Wq must include r, P0, Pn, L, Lq, lambda_eff, Wq."""
    plan, _ = build_formula_plan("PFCS", "compute_Wq", {"lambda_", "mu", "M"})

    produced = produces_sequence(plan)
    required = ["r", "P0", "Pn", "L", "Lq", "lambda_eff", "Wq"]
    for key in required:
        assert key in produced, (
            f"Expected '{key}' in PFCS/compute_Wq produces; got {produced}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — PFCM / compute_P0: minimal plan
# ─────────────────────────────────────────────────────────────────────────────

def test_pfcm_compute_P0_minimal():
    """PFCM / compute_P0 needs exactly 2 steps: r and P0."""
    plan, _ = build_formula_plan("PFCM", "compute_P0", {"lambda_", "mu", "M", "k"})

    produced = produces_sequence(plan)
    assert produced == ["r", "P0"], (
        f"Expected ['r', 'P0'] for PFCM/compute_P0, got {produced}"
    )
    assert len(plan) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — PFHET / compute_units_operating: all steps present
# ─────────────────────────────────────────────────────────────────────────────

def test_pfhet_units_operating_all_steps():
    """PFHET / compute_units_operating must end with units_operating."""
    plan, _ = build_formula_plan(
        "PFHET", "compute_units_operating", {"lambda_", "mu1", "mu2", "M"}
    )

    produced = produces_sequence(plan)
    assert "units_operating" in produced, (
        f"Expected 'units_operating' as last or present step in PFHET plan; got {produced}"
    )
    # Must produce all necessary intermediates
    for key in ["lambda_n", "mu_n", "P0", "Pn", "L"]:
        assert key in produced, f"Expected '{key}' in PFHET plan; got {produced}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — Missing variable detection with empty extracted set
# ─────────────────────────────────────────────────────────────────────────────

def test_missing_variables_detected_when_no_vars_extracted():
    """
    If no variables are extracted, the base variables (lambda_, mu)
    should appear in missing_variables for a PICS/compute_Wq plan.
    """
    _, missing = build_formula_plan("PICS", "compute_Wq", set())

    # lambda_ and mu are required by the first step and are not produced by any step
    assert "lambda_" in missing, f"Expected 'lambda_' in missing; got {missing}"
    assert "mu" in missing, f"Expected 'mu' in missing; got {missing}"


def test_missing_variables_excludes_intermediates():
    """
    Derived/intermediate variables (rho, Lq, Wq) must NOT appear in
    missing_variables even when they are not in the extracted set.
    """
    _, missing = build_formula_plan("PICS", "compute_Wq", set())

    # rho, Lq, Wq are produced by plan steps → never missing
    assert "rho" not in missing, f"'rho' should not be in missing; got {missing}"
    assert "Lq" not in missing, f"'Lq' should not be in missing; got {missing}"
    assert "Wq" not in missing, f"'Wq' should not be in missing; got {missing}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 7 — No false missing-vars when all base variables are provided
# ─────────────────────────────────────────────────────────────────────────────

def test_no_false_missing_variables_when_fully_specified():
    """
    When lambda_ and mu are in extracted variables, missing_variables for
    PICS/compute_Wq should be empty (all intermediates are derived by steps).
    """
    _, missing = build_formula_plan("PICS", "compute_Wq", {"lambda_", "mu"})
    assert missing == [], (
        f"Expected no missing variables when lambda_ and mu are provided; got {missing}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 8 — Unknown model → empty plan (graceful degradation)
# ─────────────────────────────────────────────────────────────────────────────

def test_unknown_model_returns_empty_plan():
    """build_formula_plan must return ([], []) for an unrecognised model id."""
    plan, missing = build_formula_plan("UNKNOWN_MODEL", "compute_Lq", {"lambda_", "mu"})

    assert plan == []
    assert missing == []


def test_none_model_returns_empty_plan():
    """build_formula_plan must return ([], []) when model is None."""
    plan, missing = build_formula_plan(None, "compute_Lq", {"lambda_", "mu"})
    assert plan == []
    assert missing == []


def test_none_objective_returns_empty_plan():
    """build_formula_plan must return ([], []) when objective is None."""
    plan, missing = build_formula_plan("PICS", None, {"lambda_", "mu"})
    assert plan == []
    assert missing == []


# ─────────────────────────────────────────────────────────────────────────────
# Bonus: catalog coverage smoke test
# ─────────────────────────────────────────────────────────────────────────────

def test_catalog_covers_all_models():
    """All 5 queue models must be registered in the plan builder catalog."""
    expected = {"PICS", "PICM", "PFCS", "PFCM", "PFHET"}
    registered = set(get_all_models())
    assert expected.issubset(registered), (
        f"Missing models: {expected - registered}"
    )


def test_each_model_has_at_least_one_objective():
    """Every model in the catalog must have at least one objective plan."""
    for model_id in get_all_models():
        objectives = get_available_objectives(model_id)
        assert len(objectives) > 0, f"Model '{model_id}' has no objectives in catalog"


def test_every_plan_step_has_required_fields():
    """Every step in every plan must have all required non-empty fields."""
    for model_id in get_all_models():
        for obj in get_available_objectives(model_id):
            plan, _ = build_formula_plan(model_id, obj, set())
            for step in plan:
                assert step.formula_key, f"Empty formula_key in {model_id}/{obj}"
                assert step.formula_name, f"Empty formula_name in {model_id}/{obj}"
                assert step.formula_expression, f"Empty formula_expression in {model_id}/{obj}"
                assert step.why_needed, f"Empty why_needed in {model_id}/{obj}"
                assert step.produces, f"Empty produces in {model_id}/{obj}"
                assert isinstance(step.order, int) and step.order >= 1

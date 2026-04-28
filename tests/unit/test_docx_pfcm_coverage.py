"""
Phase KB — PFCM Coverage Validation
=====================================
Validates the PFCM (M/M/k/M/M) coverage in analysis_exercise_solutions.json.

PFCM status in the .docx (Ejercicios Propuestos Teoría de Colas.docx):
  - PFCM does NOT appear as a primary model (exercise.model) in any of the 30 exercises.
  - PFCM appears as model_context in exercise 9 (09_turismo_hotelero_pfcs_pfcm),
    literals c and d:
      • Literal c: optimize_k_talleres_pfcm  (k ≥ 1 shops → minimize cost)
      • Literal d: compute_P_max_n_waiting   (P(Nq ≤ 1) with optimal k)
  - Exercise 9 uses PFCS for 1 shop (literals a, b) and transitions to PFCM
    for k shops (literals c, d). It is properly flagged has_multiple_models=True.

Canonical PFCM formula order validated here:
  1. r_pfcs      — r = λ_unidad / μ
  2. P0_pfcm     — P0(k) = 1/[Σ C(M,n)×r^n×...] (population-finite, k servers)
  3. Pn_pfcm     — Pn = ... for n≤k and n>k
  4. Lq_pfcm     — Lq = Σ(n−k)×Pn  (in literal c)
  5. optimize_k_pfcm or P_Nq_leq_1 (in c or d respectively)

Groups:
  1. PFCM is present in the knowledge base (as model_context)
  2. PFCM is NOT a primary model in the .docx (documented fact)
  3. The exercise containing PFCM is properly identified (EX09)
  4. PFCM literals have correct model_context
  5. PFCM literals have all required variables (M, lambda, mu, k)
  6. PFCM literals follow canonical formula_order (P0 → Pn → Lq / P(Nq≤1))
  7. P0_pfcm step is present in every PFCM literal
  8. Pn_pfcm step is present in every PFCM literal
  9. Lq_pfcm step is present in PFCM literals that optimize cost
 10. optimize_k_pfcm or CT step present in optimization literal
 11. Metadata documents PFCM coverage note
 12. The 30-exercise coverage test recognizes PFCM (via model_context)
 13. No temp scripts remain in project root
"""

from __future__ import annotations

import pytest

from domain.services.statement_problem_knowledge import (
    load_solutions,
    solutions_loaded,
    get_solution_by_number,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def solutions():
    return load_solutions()


@pytest.fixture(scope="module")
def all_exercises(solutions):
    return solutions.get("exercises", [])


@pytest.fixture(scope="module")
def pfcm_literals(all_exercises):
    """All literals whose model_context == 'PFCM' across all exercises."""
    result = []
    for ex in all_exercises:
        for lit in ex.get("literals", []):
            if lit.get("model_context") == "PFCM":
                result.append((ex, lit))
    return result


@pytest.fixture(scope="module")
def ex09(all_exercises):
    return next((e for e in all_exercises if e["source_number"] == 9), None)


# ─────────────────────────────────────────────────────────────────────────────
# Group 1 — PFCM is present in the knowledge base (as model_context)
# ─────────────────────────────────────────────────────────────────────────────

class TestPfcmPresence:

    def test_pfcm_present_as_model_context(self, pfcm_literals):
        assert len(pfcm_literals) > 0, (
            "PFCM must be present as model_context in at least one literal. "
            "No PFCM literals found in the 30-exercise knowledge base."
        )

    def test_exactly_2_pfcm_literals(self, pfcm_literals):
        """EX09 has exactly 2 PFCM literals (c and d)."""
        assert len(pfcm_literals) == 2, (
            f"Expected exactly 2 PFCM literals (EX09 lits c and d), "
            f"got {len(pfcm_literals)}: "
            f"{[(ex['exercise_id'], lit['literal_id']) for ex, lit in pfcm_literals]}"
        )

    def test_pfcm_literal_ids_are_c_and_d(self, pfcm_literals):
        lit_ids = sorted(lit["literal_id"] for _, lit in pfcm_literals)
        assert lit_ids == ["c", "d"], (
            f"Expected PFCM literal_ids to be ['c', 'd'], got {lit_ids}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 2 — PFCM is NOT a primary model (documented fact)
# ─────────────────────────────────────────────────────────────────────────────

class TestPfcmNotPrimaryModel:

    def test_no_exercise_has_model_pfcm(self, all_exercises):
        """PFCM does not appear as the primary model (exercise.model) in the .docx."""
        pfcm_primary = [
            e["exercise_id"] for e in all_exercises if e.get("model") == "PFCM"
        ]
        assert pfcm_primary == [], (
            f"No exercise in the .docx has PFCM as primary model. "
            f"Unexpected PFCM exercises found: {pfcm_primary}"
        )

    def test_pfcm_coverage_documented_in_metadata(self, solutions):
        """Metadata must document that PFCM appears as model_context, not primary model."""
        meta = solutions.get("_metadata", {})
        note = meta.get("pfcm_coverage_note", "")
        assert note, (
            "_metadata must have 'pfcm_coverage_note' explaining PFCM coverage status"
        )
        assert "model_context" in note.lower() or "literal" in note.lower(), (
            f"pfcm_coverage_note must mention 'model_context' or 'literal'. Got: {note[:100]}"
        )

    def test_pfcm_coverage_note_mentions_ex09(self, solutions):
        meta = solutions.get("_metadata", {})
        note = meta.get("pfcm_coverage_note", "").lower()
        assert "09" in note or "ejercicio 9" in note or "exercise 9" in note, (
            f"pfcm_coverage_note must mention exercise 9 (EX09). Got: {note[:150]}"
        )

    def test_formula_key_convention_has_pfcm(self, solutions):
        """The metadata formula_key_convention must include PFCM keys."""
        conv = solutions.get("_metadata", {}).get("formula_key_convention", {})
        assert "PFCM" in conv, (
            f"formula_key_convention must include PFCM. Keys: {list(conv.keys())}"
        )

    def test_pfcm_convention_has_canonical_keys(self, solutions):
        conv = solutions.get("_metadata", {}).get("formula_key_convention", {})
        pfcm_keys = conv.get("PFCM", [])
        required_keys = {"P0_pfcm", "Pn_pfcm", "Lq_pfcm"}
        present = required_keys & set(pfcm_keys)
        assert present == required_keys, (
            f"formula_key_convention.PFCM must include {required_keys}. "
            f"Present: {present}. All PFCM keys: {pfcm_keys}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 3 — EX09 is properly identified as the PFCM host exercise
# ─────────────────────────────────────────────────────────────────────────────

class TestEx09Structure:

    def test_ex09_exists(self, ex09):
        assert ex09 is not None, "Exercise 9 not found in knowledge base"

    def test_ex09_exercise_id(self, ex09):
        assert "pfcm" in ex09["exercise_id"].lower(), (
            f"EX09 exercise_id should contain 'pfcm'. Got: {ex09['exercise_id']}"
        )

    def test_ex09_primary_model_is_pfcs(self, ex09):
        assert ex09["model"] == "PFCS", (
            f"EX09 primary model must be PFCS (1 taller), got {ex09['model']!r}"
        )

    def test_ex09_has_multiple_models_flag(self, ex09):
        assert ex09.get("has_multiple_models") is True, (
            "EX09 must have has_multiple_models=True (PFCS for 1 taller + PFCM for k talleres)"
        )

    def test_ex09_has_optimization_flag(self, ex09):
        assert ex09.get("has_optimization") is True, (
            "EX09 must have has_optimization=True (literal c: minimize CT by choosing k)"
        )

    def test_ex09_has_cost_flag(self, ex09):
        assert ex09.get("has_cost_analysis") is True, (
            "EX09 must have has_cost_analysis=True (cost per defective day + taller day)"
        )

    def test_ex09_has_4_literals(self, ex09):
        lits = ex09.get("literals", [])
        assert len(lits) == 4, (
            f"EX09 must have 4 literals (a: PFCS, b: PFCS, c: PFCM, d: PFCM). "
            f"Got {len(lits)}"
        )

    def test_ex09_literal_contexts(self, ex09):
        lit_ctx = {lit["literal_id"]: lit["model_context"] for lit in ex09.get("literals", [])}
        assert lit_ctx.get("a") == "PFCS", f"EX09 lit a must be PFCS, got {lit_ctx.get('a')!r}"
        assert lit_ctx.get("b") == "PFCS", f"EX09 lit b must be PFCS, got {lit_ctx.get('b')!r}"
        assert lit_ctx.get("c") == "PFCM", f"EX09 lit c must be PFCM, got {lit_ctx.get('c')!r}"
        assert lit_ctx.get("d") == "PFCM", f"EX09 lit d must be PFCM, got {lit_ctx.get('d')!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Group 4 — PFCM literals have correct model_context
# ─────────────────────────────────────────────────────────────────────────────

class TestPfcmLiteralModelContext:

    def test_all_pfcm_literals_have_model_context_pfcm(self, pfcm_literals):
        for ex, lit in pfcm_literals:
            assert lit.get("model_context") == "PFCM", (
                f"Literal {lit.get('literal_id')} in {ex['exercise_id']} "
                f"should have model_context=PFCM, got {lit.get('model_context')!r}"
            )

    def test_pfcm_literals_belong_to_ex09(self, pfcm_literals):
        for ex, lit in pfcm_literals:
            assert ex["source_number"] == 9, (
                f"PFCM literal {lit['literal_id']} found in exercise {ex['source_number']} "
                f"({ex['exercise_id']}), expected only in EX09"
            )

    def test_pfcm_literals_have_non_empty_objectives(self, pfcm_literals):
        for ex, lit in pfcm_literals:
            obj = lit.get("objective", "")
            assert obj and " " not in obj, (
                f"PFCM literal {lit['literal_id']} in {ex['exercise_id']} "
                f"has invalid objective: {obj!r}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Group 5 — PFCM literals have all required variables (M, lambda, mu, k)
# ─────────────────────────────────────────────────────────────────────────────

class TestPfcmRequiredVariables:

    def test_pfcm_literals_have_M_variable(self, pfcm_literals):
        """All PFCM literals require M (population size)."""
        for ex, lit in pfcm_literals:
            rv = lit.get("required_variables", [])
            assert "M" in rv, (
                f"PFCM literal {lit['literal_id']} in {ex['exercise_id']} "
                f"must include 'M' (population size) in required_variables. Got: {rv}"
            )

    def test_pfcm_literals_have_lambda_variable(self, pfcm_literals):
        for ex, lit in pfcm_literals:
            rv = lit.get("required_variables", [])
            has_lambda = any("lambda" in v.lower() for v in rv)
            assert has_lambda, (
                f"PFCM literal {lit['literal_id']} in {ex['exercise_id']} "
                f"must include lambda variable. Got: {rv}"
            )

    def test_pfcm_literals_have_mu_variable(self, pfcm_literals):
        for ex, lit in pfcm_literals:
            rv = lit.get("required_variables", [])
            has_mu = any("mu" in v.lower() for v in rv)
            assert has_mu, (
                f"PFCM literal {lit['literal_id']} in {ex['exercise_id']} "
                f"must include mu variable. Got: {rv}"
            )

    def test_pfcm_lit_d_requires_k_optimal(self, pfcm_literals):
        """Literal d (compute_P_max_n_waiting) needs k_optimal."""
        lit_d = next(
            (lit for _, lit in pfcm_literals if lit["literal_id"] == "d"), None
        )
        assert lit_d is not None, "PFCM literal d not found"
        rv = lit_d.get("required_variables", [])
        assert "k_optimal" in rv, (
            f"PFCM literal d must require 'k_optimal'. Got: {rv}"
        )

    def test_ex09_variables_to_extract_has_M(self, ex09):
        names = {v["name"] for v in ex09.get("variables_to_extract", [])}
        assert "M" in names, (
            f"EX09 variables_to_extract must include 'M' (population). Found: {names}"
        )

    def test_ex09_variables_to_extract_has_lambda_and_mu(self, ex09):
        names = {v["name"] for v in ex09.get("variables_to_extract", [])}
        has_lambda = any("lambda" in n.lower() for n in names)
        has_mu = any("mu" in n.lower() for n in names)
        assert has_lambda, f"EX09 must have lambda variable. Found: {names}"
        assert has_mu, f"EX09 must have mu variable. Found: {names}"


# ─────────────────────────────────────────────────────────────────────────────
# Group 6 — PFCM literals follow canonical formula_order
# ─────────────────────────────────────────────────────────────────────────────

class TestPfcmFormulaOrder:

    def test_all_pfcm_literals_have_formula_order(self, pfcm_literals):
        for ex, lit in pfcm_literals:
            fo = lit.get("formula_order", [])
            assert isinstance(fo, list) and len(fo) > 0, (
                f"PFCM literal {lit['literal_id']} in {ex['exercise_id']} "
                f"has empty or missing formula_order"
            )

    def test_pfcm_formula_order_starts_with_r(self, pfcm_literals):
        """First step must compute r = λ/μ."""
        for ex, lit in pfcm_literals:
            steps = lit.get("formula_order", [])
            first = next((s for s in steps if s.get("order") == 1), None)
            assert first is not None, (
                f"PFCM literal {lit['literal_id']} in {ex['exercise_id']} "
                f"missing step with order=1"
            )
            fk = first.get("formula_key", "")
            assert "r_pfcs" in fk or "r_pfcm" in fk or fk.startswith("r"), (
                f"First step of PFCM literal {lit['literal_id']} must be r=λ/μ. "
                f"Got formula_key: {fk!r}"
            )

    def test_pfcm_steps_are_sorted(self, pfcm_literals):
        for ex, lit in pfcm_literals:
            orders = [s.get("order", 0) for s in lit.get("formula_order", [])]
            assert orders == sorted(orders), (
                f"formula_order steps not sorted in {ex['exercise_id']} "
                f"lit {lit['literal_id']}: {orders}"
            )

    def test_all_pfcm_steps_have_required_fields(self, pfcm_literals):
        for ex, lit in pfcm_literals:
            for step in lit.get("formula_order", []):
                eid = ex["exercise_id"]
                lid = lit["literal_id"]
                assert "order" in step, f"Step missing 'order' in {eid} lit {lid}"
                assert step.get("formula_key"), f"Step missing 'formula_key' in {eid} lit {lid}"
                assert step.get("expression"), f"Step missing 'expression' in {eid} lit {lid}"
                assert step.get("produces"), f"Step missing 'produces' in {eid} lit {lid}"
                assert "required_variables" in step, (
                    f"Step missing 'required_variables' in {eid} lit {lid}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 7 — P0_pfcm step present in every PFCM literal
# ─────────────────────────────────────────────────────────────────────────────

class TestP0PfcmStep:

    def test_P0_pfcm_step_present_in_all_pfcm_literals(self, pfcm_literals):
        """Every PFCM literal must have a step with formula_key='P0_pfcm'."""
        for ex, lit in pfcm_literals:
            fkeys = [s.get("formula_key") for s in lit.get("formula_order", [])]
            assert "P0_pfcm" in fkeys, (
                f"PFCM literal {lit['literal_id']} in {ex['exercise_id']} "
                f"is missing P0_pfcm step. Steps: {fkeys}"
            )

    def test_P0_pfcm_expression_contains_sum(self, pfcm_literals):
        """P0_pfcm expression must reference a sum (Σ) formula."""
        for ex, lit in pfcm_literals:
            step = next(
                (s for s in lit.get("formula_order", []) if s.get("formula_key") == "P0_pfcm"),
                None
            )
            if step is None:
                continue
            expr = step.get("expression", "")
            assert "Σ" in expr or "sum" in expr.lower() or "1 /" in expr, (
                f"P0_pfcm expression must reference sum formula in {ex['exercise_id']} "
                f"lit {lit['literal_id']}. Got: {expr[:80]}"
            )

    def test_P0_pfcm_requires_M_and_r(self, pfcm_literals):
        """P0_pfcm step must require M and r (or r_pfcs)."""
        for ex, lit in pfcm_literals:
            step = next(
                (s for s in lit.get("formula_order", []) if s.get("formula_key") == "P0_pfcm"),
                None
            )
            if step is None:
                continue
            rv = step.get("required_variables", [])
            assert "M" in rv, (
                f"P0_pfcm step must require 'M' in {ex['exercise_id']} lit {lit['literal_id']}. "
                f"Got: {rv}"
            )
            has_r = any("r" in v.lower() for v in rv)
            assert has_r, (
                f"P0_pfcm step must require r or r_pfcs in {ex['exercise_id']} "
                f"lit {lit['literal_id']}. Got: {rv}"
            )

    def test_P0_pfcm_produces_P0_pfcm(self, pfcm_literals):
        for ex, lit in pfcm_literals:
            step = next(
                (s for s in lit.get("formula_order", []) if s.get("formula_key") == "P0_pfcm"),
                None
            )
            if step is None:
                continue
            assert step.get("produces") == "P0_pfcm", (
                f"P0_pfcm step must produce 'P0_pfcm' in {ex['exercise_id']} "
                f"lit {lit['literal_id']}. Got: {step.get('produces')!r}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Group 8 — Pn_pfcm step present in every PFCM literal
# ─────────────────────────────────────────────────────────────────────────────

class TestPnPfcmStep:

    def test_Pn_pfcm_step_present_in_all_pfcm_literals(self, pfcm_literals):
        """Every PFCM literal must have a step with formula_key='Pn_pfcm'."""
        for ex, lit in pfcm_literals:
            fkeys = [s.get("formula_key") for s in lit.get("formula_order", [])]
            assert "Pn_pfcm" in fkeys, (
                f"PFCM literal {lit['literal_id']} in {ex['exercise_id']} "
                f"is missing Pn_pfcm step. Steps: {fkeys}"
            )

    def test_Pn_pfcm_expression_distinguishes_n_le_k_and_n_gt_k(self, pfcm_literals):
        """Pn_pfcm expression must show the two-case formula (n≤k and n>k)."""
        for ex, lit in pfcm_literals:
            step = next(
                (s for s in lit.get("formula_order", []) if s.get("formula_key") == "Pn_pfcm"),
                None
            )
            if step is None:
                continue
            expr = step.get("expression", "")
            # Must show n≤k OR k* condition (two cases for n ≤ k and n > k)
            has_condition = (
                "≤k" in expr or "n≤k" in expr or "n > k" in expr or "n>k" in expr
                or "si n" in expr.lower() or "if n" in expr.lower()
                or "n−k" in expr or "n-k" in expr
            )
            assert has_condition, (
                f"Pn_pfcm expression must show the two-case formula (n≤k and n>k) "
                f"in {ex['exercise_id']} lit {lit['literal_id']}. Got: {expr[:100]}"
            )

    def test_Pn_pfcm_requires_P0_pfcm(self, pfcm_literals):
        """Pn_pfcm must depend on P0_pfcm."""
        for ex, lit in pfcm_literals:
            step = next(
                (s for s in lit.get("formula_order", []) if s.get("formula_key") == "Pn_pfcm"),
                None
            )
            if step is None:
                continue
            rv = step.get("required_variables", [])
            assert "P0_pfcm" in rv, (
                f"Pn_pfcm step must require 'P0_pfcm' in {ex['exercise_id']} "
                f"lit {lit['literal_id']}. Got: {rv}"
            )

    def test_Pn_pfcm_produces_Pn_pfcm(self, pfcm_literals):
        for ex, lit in pfcm_literals:
            step = next(
                (s for s in lit.get("formula_order", []) if s.get("formula_key") == "Pn_pfcm"),
                None
            )
            if step is None:
                continue
            assert step.get("produces") == "Pn_pfcm", (
                f"Pn_pfcm step must produce 'Pn_pfcm' in {ex['exercise_id']} "
                f"lit {lit['literal_id']}. Got: {step.get('produces')!r}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Group 9 — Lq_pfcm step present in PFCM cost optimization literal (c)
# ─────────────────────────────────────────────────────────────────────────────

class TestLqPfcmStep:

    def test_Lq_pfcm_present_in_literal_c(self, pfcm_literals):
        """Literal c (optimize_k) must have Lq_pfcm = Σ(n−k)Pn."""
        lit_c = next(
            (lit for _, lit in pfcm_literals if lit["literal_id"] == "c"), None
        )
        assert lit_c is not None, "PFCM literal c not found"
        fkeys = [s.get("formula_key") for s in lit_c.get("formula_order", [])]
        assert "Lq_pfcm" in fkeys, (
            f"Literal c (optimize_k_talleres_pfcm) must have Lq_pfcm step. "
            f"Steps: {fkeys}"
        )

    def test_Lq_pfcm_expression_is_sum_n_minus_k_Pn(self, pfcm_literals):
        """Lq_pfcm expression must reference Σ(n−k)Pn."""
        lit_c = next(
            (lit for _, lit in pfcm_literals if lit["literal_id"] == "c"), None
        )
        if lit_c is None:
            return
        step = next(
            (s for s in lit_c.get("formula_order", []) if s.get("formula_key") == "Lq_pfcm"),
            None
        )
        assert step is not None, "Lq_pfcm step not found in literal c"
        expr = step.get("expression", "")
        has_sum = "Σ" in expr or "sum" in expr.lower()
        has_diff = "n−k" in expr or "n-k" in expr
        assert has_sum and has_diff, (
            f"Lq_pfcm expression must be Σ(n−k)Pn. Got: {expr[:80]}"
        )

    def test_Lq_pfcm_requires_Pn_pfcm(self, pfcm_literals):
        lit_c = next(
            (lit for _, lit in pfcm_literals if lit["literal_id"] == "c"), None
        )
        if lit_c is None:
            return
        step = next(
            (s for s in lit_c.get("formula_order", []) if s.get("formula_key") == "Lq_pfcm"),
            None
        )
        if step is None:
            return
        rv = step.get("required_variables", [])
        assert "Pn_pfcm" in rv, (
            f"Lq_pfcm step must require 'Pn_pfcm'. Got: {rv}"
        )

    def test_Lq_pfcm_produces_Lq_pfcm(self, pfcm_literals):
        lit_c = next(
            (lit for _, lit in pfcm_literals if lit["literal_id"] == "c"), None
        )
        if lit_c is None:
            return
        step = next(
            (s for s in lit_c.get("formula_order", []) if s.get("formula_key") == "Lq_pfcm"),
            None
        )
        if step is None:
            return
        assert step.get("produces") == "Lq_pfcm", (
            f"Lq_pfcm step must produce 'Lq_pfcm'. Got: {step.get('produces')!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 10 — Cost optimization step (CT + k*) present in literal c
# ─────────────────────────────────────────────────────────────────────────────

class TestPfcmOptimizationStep:

    def test_CT_step_present_in_literal_c(self, pfcm_literals):
        lit_c = next(
            (lit for _, lit in pfcm_literals if lit["literal_id"] == "c"), None
        )
        assert lit_c is not None, "PFCM literal c not found"
        fkeys = [s.get("formula_key") for s in lit_c.get("formula_order", [])]
        has_ct = any("ct" in fk.lower() for fk in fkeys)
        assert has_ct, (
            f"Literal c must have a CT (costo total) step. Steps: {fkeys}"
        )

    def test_optimize_k_step_present_in_literal_c(self, pfcm_literals):
        lit_c = next(
            (lit for _, lit in pfcm_literals if lit["literal_id"] == "c"), None
        )
        assert lit_c is not None, "PFCM literal c not found"
        fkeys = [s.get("formula_key") for s in lit_c.get("formula_order", [])]
        has_opt = any(
            "k_opt" in fk.lower() or "optimize" in fk.lower() or "argmin" in fk.lower()
            for fk in fkeys
        )
        assert has_opt, (
            f"Literal c must have an optimization step (k_optimal or optimize_k). "
            f"Steps: {fkeys}"
        )

    def test_literal_c_objective_is_optimization(self, pfcm_literals):
        lit_c = next(
            (lit for _, lit in pfcm_literals if lit["literal_id"] == "c"), None
        )
        assert lit_c is not None
        obj = lit_c.get("objective", "")
        assert "optimize" in obj.lower() or "cost" in obj.lower(), (
            f"Literal c objective must reference optimization. Got: {obj!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 11 — Literal d: P(Nq ≤ 1) step present and uses Pn_pfcm
# ─────────────────────────────────────────────────────────────────────────────

class TestPfcmProbabilityStep:

    def test_P_Nq_leq_1_step_present_in_literal_d(self, pfcm_literals):
        lit_d = next(
            (lit for _, lit in pfcm_literals if lit["literal_id"] == "d"), None
        )
        assert lit_d is not None, "PFCM literal d not found"
        fkeys = [s.get("formula_key") for s in lit_d.get("formula_order", [])]
        has_prob = any(
            "nq" in fk.lower() or "p_nq" in fk.lower() or "leq_1" in fk.lower()
            or "wait" in fk.lower()
            for fk in fkeys
        )
        assert has_prob, (
            f"Literal d must have a P(Nq≤1) probability step. Steps: {fkeys}"
        )

    def test_literal_d_P_Nq_step_requires_Pn_pfcm(self, pfcm_literals):
        lit_d = next(
            (lit for _, lit in pfcm_literals if lit["literal_id"] == "d"), None
        )
        if lit_d is None:
            return
        step = next(
            (s for s in lit_d.get("formula_order", [])
             if "nq" in s.get("formula_key", "").lower()
             or "p_nq" in s.get("formula_key", "").lower()
             or "leq_1" in s.get("formula_key", "").lower()),
            None
        )
        if step is None:
            return
        rv = step.get("required_variables", [])
        assert "Pn_pfcm" in rv, (
            f"P(Nq≤1) step in literal d must require 'Pn_pfcm'. Got: {rv}"
        )

    def test_canonical_order_d_is_r_P0_Pn_prob(self, pfcm_literals):
        """Literal d canonical order: r → P0_pfcm → Pn_pfcm → P(Nq≤1)."""
        lit_d = next(
            (lit for _, lit in pfcm_literals if lit["literal_id"] == "d"), None
        )
        if lit_d is None:
            return
        fkeys = [s.get("formula_key") for s in sorted(
            lit_d.get("formula_order", []), key=lambda s: s.get("order", 0)
        )]
        assert fkeys.index("P0_pfcm") < fkeys.index("Pn_pfcm"), (
            f"P0_pfcm must come before Pn_pfcm in literal d. Order: {fkeys}"
        )
        assert fkeys.index("Pn_pfcm") < max(
            (i for i, k in enumerate(fkeys)
             if "nq" in k.lower() or "leq" in k.lower()),
            default=-1
        ), (
            f"Pn_pfcm must come before P(Nq≤1) step in literal d. Order: {fkeys}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 12 — 30-exercise coverage recognizes PFCM (via model_context)
# ─────────────────────────────────────────────────────────────────────────────

class TestTotalCoveragePfcm:

    def test_model_context_distribution_includes_pfcm(self, all_exercises):
        """Across all 30 exercises, PFCM must appear in model_context distribution."""
        ctxs = set(
            lit.get("model_context", "")
            for ex in all_exercises
            for lit in ex.get("literals", [])
        )
        assert "PFCM" in ctxs, (
            f"PFCM must appear in model_context across all 30 exercises. "
            f"model_contexts found: {ctxs}"
        )

    def test_pfcm_exercises_count_is_1_via_model_context(self, all_exercises):
        """Exactly 1 exercise (EX09) contains PFCM literals."""
        pfcm_exercises = [
            ex for ex in all_exercises
            if any(lit.get("model_context") == "PFCM" for lit in ex.get("literals", []))
        ]
        assert len(pfcm_exercises) == 1, (
            f"Expected exactly 1 exercise with PFCM literals (EX09). "
            f"Found {len(pfcm_exercises)}: "
            f"{[e['exercise_id'] for e in pfcm_exercises]}"
        )

    def test_all_30_exercises_present(self, all_exercises):
        nums = sorted(e["source_number"] for e in all_exercises)
        assert nums == list(range(1, 31)), (
            f"Expected source_numbers [1..30] (30 exercises). Got: {nums}"
        )

    def test_ex09_model_contexts_cover_pfcs_and_pfcm(self, ex09):
        ctxs = {lit.get("model_context") for lit in ex09.get("literals", [])}
        assert "PFCS" in ctxs, f"EX09 must have PFCS literals. Got: {ctxs}"
        assert "PFCM" in ctxs, f"EX09 must have PFCM literals. Got: {ctxs}"


# ─────────────────────────────────────────────────────────────────────────────
# Group 13 — No temp scripts in project root
# ─────────────────────────────────────────────────────────────────────────────

class TestNoTempScripts:

    def test_no_temp_scripts_exist(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent.parent
        forbidden = [
            "debug_literals.py",
            "read_pdf.py",
            "_audit_pfcm.py",
            "_show_ex09.py",
            "_show_pfcm_lits.py",
            "_formalize_pfcm.py",
            "_add_exercises_21_23.py",
            "_add_exercises_24_26.py",
            "_add_exercises_27_30.py",
        ]
        for fname in forbidden:
            assert not (root / fname).exists(), (
                f"Temporary file {fname!r} must not exist in project root"
            )

    def test_docx_source_file_exists(self):
        from pathlib import Path
        docx = (
            Path(__file__).resolve().parent.parent.parent
            / "Ejercicios Propuestos Teoría de Colas.docx"
        )
        assert docx.exists(), f".docx file not found at expected path: {docx}"

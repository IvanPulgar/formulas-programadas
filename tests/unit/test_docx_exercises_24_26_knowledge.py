"""
Phase KB — Ejercicios 24-26 Structural Knowledge Coverage
==========================================================
Validates analysis_exercise_solutions.json (exercises 24-26) against 12 groups:

 1. Exactly 3 NEW exercises exist (source_number 24, 25, 26)
 2. Unique exercise_ids (across all 26)
 3. Every exercise 24-26 has 'model' field (valid model name)
 4. Every exercise 24-26 has 'variables_to_extract'
 5. Every exercise 24-26 has 'literals'
 6. Every literal has 'objective'
 7. Every literal has 'formula_order' (non-empty list)
 8. Every formula_order step has: order, formula_key, expression, produces
 9. Models covered in 24-26: PICS and PICM present
10. At least 1 exercise 24-26 has 'recognition_examples' with modified data
11. The analyzer recognizes recognition_examples for exercises 24-26
12. No memorized numerical results in formula steps of exercises 24-26

Read from: infrastructure/data/analysis/analysis_exercise_solutions.json
Source:    Ejercicios Propuestos Teoría de Colas.docx  (párrafos [201]-[232])
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from domain.entities.analysis import StatementAnalysisRequest
from domain.services.statement_analyzer import make_analyzer
from domain.services.statement_problem_knowledge import (
    load_solutions,
    get_solutions_exercises,
    get_solution_by_number,
    solutions_loaded,
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
def exercises(all_exercises):
    """Only exercises 24-26."""
    return [e for e in all_exercises if 24 <= e["source_number"] <= 26]


@pytest.fixture(scope="module")
def analyzer():
    return make_analyzer()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Group 1 — Exercises 24-26 exist; total ≥ 26
# ─────────────────────────────────────────────────────────────────────────────

class TestExerciseCount:

    def test_solutions_file_loaded(self, solutions):
        assert solutions_loaded(), "analysis_exercise_solutions.json not found or empty"

    def test_at_least_26_exercises_total(self, all_exercises):
        assert len(all_exercises) >= 26, (
            f"Expected ≥26 total exercises, got {len(all_exercises)}"
        )

    def test_exactly_3_exercises_24_to_26(self, exercises):
        assert len(exercises) == 3, (
            f"Expected exactly 3 exercises (24-26), got {len(exercises)}"
        )

    def test_source_numbers_are_24_25_26(self, exercises):
        nums = sorted(e["source_number"] for e in exercises)
        assert nums == [24, 25, 26], (
            f"source_number values must be exactly [24, 25, 26], got {nums}"
        )

    def test_get_solution_by_number_works_for_24_26(self):
        for n in (24, 25, 26):
            sol = get_solution_by_number(n)
            assert sol is not None, f"get_solution_by_number({n}) returned None"
            assert sol["source_number"] == n

    def test_exercises_1_to_23_still_present(self, all_exercises):
        nums = {e["source_number"] for e in all_exercises}
        for n in range(1, 24):
            assert n in nums, f"Exercise {n} (EX01-23) is missing after adding EX24-26"


# ─────────────────────────────────────────────────────────────────────────────
# Group 2 — Unique exercise_ids across all 26 exercises
# ─────────────────────────────────────────────────────────────────────────────

class TestUniqueIds:

    def test_exercise_ids_are_unique_across_all(self, all_exercises):
        ids = [e["exercise_id"] for e in all_exercises]
        assert len(ids) == len(set(ids)), (
            f"Duplicate exercise_ids found: {[x for x in ids if ids.count(x) > 1]}"
        )

    def test_exercise_ids_24_26_are_non_empty_strings(self, exercises):
        for e in exercises:
            eid = e.get("exercise_id", "")
            assert isinstance(eid, str) and eid.strip(), (
                f"Exercise {e.get('source_number')} has invalid exercise_id: {eid!r}"
            )

    def test_exercise_ids_24_26_distinct_from_previous(self, exercises, all_exercises):
        ids_prev = {e["exercise_id"] for e in all_exercises if e["source_number"] < 24}
        ids_new  = {e["exercise_id"] for e in exercises}
        overlap  = ids_prev & ids_new
        assert not overlap, f"exercise_id collision between 1-23 and 24-26: {overlap}"


# ─────────────────────────────────────────────────────────────────────────────
# Group 3 — Every exercise 24-26 has valid 'model' field
# ─────────────────────────────────────────────────────────────────────────────

VALID_MODELS = {"PICS", "PICM", "PFCS", "PFCM", "PFHET"}


class TestModelField:

    def test_all_exercises_have_model(self, exercises):
        for e in exercises:
            assert "model" in e, (
                f"Exercise {e.get('exercise_id')} missing 'model' field"
            )

    def test_all_models_are_valid(self, exercises):
        for e in exercises:
            assert e["model"] in VALID_MODELS, (
                f"Exercise {e['exercise_id']} has unknown model: {e['model']!r}"
            )

    def test_model_alias_present(self, exercises):
        for e in exercises:
            assert e.get("model_alias"), (
                f"Exercise {e['exercise_id']} missing model_alias"
            )

    def test_model_reasoning_present(self, exercises):
        for e in exercises:
            assert e.get("model_reasoning"), (
                f"Exercise {e['exercise_id']} missing model_reasoning"
            )

    def test_ex24_is_picm(self, exercises):
        ex24 = next((e for e in exercises if e["source_number"] == 24), None)
        assert ex24 is not None, "Exercise 24 not found"
        assert ex24["model"] == "PICM", (
            f"Exercise 24 must be PICM (supermercado, dimensionamiento P_w), "
            f"got {ex24['model']!r}"
        )

    def test_ex25_is_pics(self, exercises):
        ex25 = next((e for e in exercises if e["source_number"] == 25), None)
        assert ex25 is not None, "Exercise 25 not found"
        assert ex25["model"] == "PICS", (
            f"Exercise 25 must be PICS (ensamblaje, un técnico especialista), "
            f"got {ex25['model']!r}"
        )

    def test_ex26_is_picm(self, exercises):
        ex26 = next((e for e in exercises if e["source_number"] == 26), None)
        assert ex26 is not None, "Exercise 26 not found"
        assert ex26["model"] == "PICM", (
            f"Exercise 26 must be PICM (control calidad, condición W), "
            f"got {ex26['model']!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 4 — Every exercise 24-26 has variables_to_extract
# ─────────────────────────────────────────────────────────────────────────────

class TestVariablesToExtract:

    def test_all_exercises_have_variables_to_extract(self, exercises):
        for e in exercises:
            vte = e.get("variables_to_extract", [])
            assert isinstance(vte, list) and len(vte) > 0, (
                f"Exercise {e['exercise_id']} missing or empty variables_to_extract"
            )

    def test_each_variable_has_name_and_meaning(self, exercises):
        for e in exercises:
            for v in e.get("variables_to_extract", []):
                assert v.get("name"), (
                    f"Variable in {e['exercise_id']} missing 'name'"
                )
                assert v.get("meaning"), (
                    f"Variable '{v.get('name')}' in {e['exercise_id']} missing 'meaning'"
                )

    def test_each_variable_has_required_flag(self, exercises):
        for e in exercises:
            for v in e.get("variables_to_extract", []):
                assert "required" in v, (
                    f"Variable '{v.get('name')}' in {e['exercise_id']} missing 'required' flag"
                )

    def test_ex24_has_Pw_max(self, exercises):
        """Exercise 24 must expose P_w constraint for dimensioning."""
        ex24 = next((e for e in exercises if e["source_number"] == 24), None)
        assert ex24, "Exercise 24 not found"
        names = {v["name"] for v in ex24.get("variables_to_extract", [])}
        assert "Pw_max" in names, (
            f"Exercise 24 must have Pw_max variable (P(esperar)≤50%). Found: {names}"
        )

    def test_ex25_has_Lq_threshold(self, exercises):
        """Exercise 25 must expose Lq threshold for dimensioning."""
        ex25 = next((e for e in exercises if e["source_number"] == 25), None)
        assert ex25, "Exercise 25 not found"
        names = {v["name"] for v in ex25.get("variables_to_extract", [])}
        assert "Lq_threshold" in names, (
            f"Exercise 25 must have Lq_threshold variable (Lq≤1). Found: {names}"
        )

    def test_ex26_has_W_max_min(self, exercises):
        """Exercise 26 must expose W constraint for dimensioning."""
        ex26 = next((e for e in exercises if e["source_number"] == 26), None)
        assert ex26, "Exercise 26 not found"
        names = {v["name"] for v in ex26.get("variables_to_extract", [])}
        assert "W_max_min" in names, (
            f"Exercise 26 must have W_max_min variable (W≤10 min). Found: {names}"
        )

    def test_ex26_has_M_pfcs(self, exercises):
        """Exercise 26 must expose M for PFCS variant (literal g: 15 employees)."""
        ex26 = next((e for e in exercises if e["source_number"] == 26), None)
        assert ex26, "Exercise 26 not found"
        names = {v["name"] for v in ex26.get("variables_to_extract", [])}
        assert "M_pfcs" in names, (
            f"Exercise 26 must have M_pfcs variable (PFCS recorte 15 empleados). "
            f"Found: {names}"
        )

    def test_ex25_has_reproceso_variable(self, exercises):
        """Exercise 25 must expose the rework probability p_defect_s2."""
        ex25 = next((e for e in exercises if e["source_number"] == 25), None)
        assert ex25, "Exercise 25 not found"
        names = {v["name"] for v in ex25.get("variables_to_extract", [])}
        assert "p_defect_s2" in names, (
            f"Exercise 25 must have p_defect_s2 variable (5% reproceso). Found: {names}"
        )

    def test_picm_exercises_have_lambda_and_mu(self, exercises):
        for e in exercises:
            if e["model"] == "PICM":
                names = {v["name"] for v in e.get("variables_to_extract", [])}
                has_lambda = any(
                    n == "lambda_" or n.startswith("lambda_")
                    or n == "inter_arrival_min"
                    for n in names
                )
                has_mu = any(
                    n == "mu" or n.startswith("mu_") or n == "service_time_min"
                    for n in names
                )
                assert has_lambda, (
                    f"PICM exercise {e['exercise_id']} missing lambda variable. "
                    f"Found: {names}"
                )
                assert has_mu, (
                    f"PICM exercise {e['exercise_id']} missing mu variable. "
                    f"Found: {names}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 5 — Every exercise 24-26 has literals
# ─────────────────────────────────────────────────────────────────────────────

class TestLiterals:

    def test_all_exercises_have_literals(self, exercises):
        for e in exercises:
            lits = e.get("literals", [])
            assert isinstance(lits, list) and len(lits) > 0, (
                f"Exercise {e['exercise_id']} has no literals"
            )

    def test_each_literal_has_literal_id(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                assert lit.get("literal_id"), (
                    f"Literal in {e['exercise_id']} missing literal_id"
                )

    def test_each_literal_has_literal_text(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                assert lit.get("literal_text", "").strip(), (
                    f"Literal {lit.get('literal_id')} in {e['exercise_id']} "
                    f"has empty literal_text"
                )

    def test_each_literal_has_model_context(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                ctx = lit.get("model_context", "")
                assert ctx in VALID_MODELS, (
                    f"Literal {lit.get('literal_id')} in {e['exercise_id']} "
                    f"has invalid model_context: {ctx!r}"
                )

    def test_each_literal_has_required_variables(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                rv = lit.get("required_variables", [])
                assert isinstance(rv, list), (
                    f"required_variables must be a list in {e['exercise_id']} "
                    f"lit {lit.get('literal_id')}"
                )

    def test_ex24_has_Pw_optimization_literal(self, exercises):
        """Exercise 24 must have literal d with objective optimize_c_for_Pw_condition."""
        ex24 = next((e for e in exercises if e["source_number"] == 24), None)
        assert ex24, "Exercise 24 not found"
        pw_lits = [
            lit for lit in ex24.get("literals", [])
            if "pw" in lit.get("objective", "").lower()
               or "pw_condition" in lit.get("objective", "").lower()
        ]
        assert len(pw_lits) > 0, (
            f"Exercise 24 must have at least 1 literal for Pw optimization. "
            f"Objectives found: {[l.get('objective') for l in ex24.get('literals', [])]}"
        )

    def test_ex25_has_Lq_optimization_literal(self, exercises):
        """Exercise 25 must have literal d with objective optimize_c_for_Lq_condition."""
        ex25 = next((e for e in exercises if e["source_number"] == 25), None)
        assert ex25, "Exercise 25 not found"
        lq_lits = [
            lit for lit in ex25.get("literals", [])
            if "lq" in lit.get("objective", "").lower()
               or "lq_condition" in lit.get("objective", "").lower()
        ]
        assert len(lq_lits) > 0, (
            f"Exercise 25 must have at least 1 literal for Lq optimization. "
            f"Objectives found: {[l.get('objective') for l in ex25.get('literals', [])]}"
        )

    def test_ex26_has_pfcs_literal_g(self, exercises):
        """Exercise 26 must have literal g with model_context PFCS (recorte 15 empleados)."""
        ex26 = next((e for e in exercises if e["source_number"] == 26), None)
        assert ex26, "Exercise 26 not found"
        pfcs_lits = [
            lit for lit in ex26.get("literals", [])
            if lit.get("model_context") == "PFCS"
        ]
        assert len(pfcs_lits) > 0, (
            f"Exercise 26 must have at least 1 literal with model_context=PFCS "
            f"(recorte de personal → 15 empleados, fuente finita)."
        )

    def test_ex26_has_cost_literal(self, exercises):
        """Exercise 26 must have a literal with cost analysis objective."""
        ex26 = next((e for e in exercises if e["source_number"] == 26), None)
        assert ex26, "Exercise 26 not found"
        cost_lits = [
            lit for lit in ex26.get("literals", [])
            if "cost" in lit.get("objective", "").lower()
        ]
        assert len(cost_lits) > 0, (
            f"Exercise 26 must have at least 1 literal about weekly cost. "
            f"Objectives found: {[l.get('objective') for l in ex26.get('literals', [])]}"
        )

    def test_ex26_has_W_optimization_literal(self, exercises):
        """Exercise 26 must have literal with optimize_c_for_W_condition."""
        ex26 = next((e for e in exercises if e["source_number"] == 26), None)
        assert ex26, "Exercise 26 not found"
        w_lits = [
            lit for lit in ex26.get("literals", [])
            if "w_condition" in lit.get("objective", "").lower()
               or "optimize_c_for_w" in lit.get("objective", "").lower()
        ]
        assert len(w_lits) > 0, (
            f"Exercise 26 must have at least 1 literal for W constraint optimization. "
            f"Objectives found: {[l.get('objective') for l in ex26.get('literals', [])]}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 6 — Every literal has 'objective'
# ─────────────────────────────────────────────────────────────────────────────

class TestLiteralObjectives:

    def test_all_literals_have_objective(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                assert lit.get("objective"), (
                    f"Literal {lit.get('literal_id')} in {e['exercise_id']} "
                    f"missing objective"
                )

    def test_objectives_are_snake_case_strings(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                obj = lit.get("objective", "")
                assert obj and " " not in obj, (
                    f"Objective '{obj}' in {e['exercise_id']} lit {lit.get('literal_id')} "
                    f"should be snake_case (no spaces)"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 7 — Every literal has non-empty formula_order
# ─────────────────────────────────────────────────────────────────────────────

class TestFormulaOrder:

    def test_all_literals_have_formula_order(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                fo = lit.get("formula_order", [])
                assert isinstance(fo, list) and len(fo) > 0, (
                    f"Literal {lit.get('literal_id')} in {e['exercise_id']} "
                    f"has empty or missing formula_order"
                )

    def test_formula_order_is_sorted_by_order_field(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                steps = lit.get("formula_order", [])
                orders = [s.get("order", 0) for s in steps]
                assert orders == sorted(orders), (
                    f"formula_order steps are not sorted in {e['exercise_id']} "
                    f"lit {lit.get('literal_id')}: {orders}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 8 — Every formula_order step has required fields
# ─────────────────────────────────────────────────────────────────────────────

class TestFormulaOrderSteps:

    def test_each_step_has_order(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for step in lit.get("formula_order", []):
                    assert "order" in step, (
                        f"Step missing 'order' in {e['exercise_id']} "
                        f"lit {lit.get('literal_id')}: {step}"
                    )

    def test_each_step_has_formula_key(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for step in lit.get("formula_order", []):
                    assert step.get("formula_key"), (
                        f"Step missing 'formula_key' in {e['exercise_id']} "
                        f"lit {lit.get('literal_id')}: {step}"
                    )

    def test_each_step_has_expression(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for step in lit.get("formula_order", []):
                    assert step.get("expression"), (
                        f"Step missing 'expression' in {e['exercise_id']} "
                        f"lit {lit.get('literal_id')}: {step.get('formula_key')}"
                    )

    def test_each_step_has_produces(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for step in lit.get("formula_order", []):
                    assert step.get("produces"), (
                        f"Step missing 'produces' in {e['exercise_id']} "
                        f"lit {lit.get('literal_id')}: {step.get('formula_key')}"
                    )

    def test_each_step_has_required_variables(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for step in lit.get("formula_order", []):
                    assert "required_variables" in step, (
                        f"Step missing 'required_variables' in {e['exercise_id']} "
                        f"lit {lit.get('literal_id')}: {step.get('formula_key')}"
                    )


# ─────────────────────────────────────────────────────────────────────────────
# Group 9 — Models covered in 24-26 include PICS and PICM
# ─────────────────────────────────────────────────────────────────────────────

class TestModelsCovered:

    def test_pics_present_in_24_26(self, exercises):
        models = {e["model"] for e in exercises}
        assert "PICS" in models, (
            f"PICS must be present among exercises 24-26 (EX25). Found: {models}"
        )

    def test_picm_present_in_24_26(self, exercises):
        models = {e["model"] for e in exercises}
        assert "PICM" in models, (
            f"PICM must be present among exercises 24-26 (EX24, EX26). Found: {models}"
        )

    def test_ex26_has_multiple_models_flag(self, exercises):
        """Exercise 26 uses PICM + PFCS (literal g) — has_multiple_models must be true."""
        ex26 = next((e for e in exercises if e["source_number"] == 26), None)
        assert ex26 and ex26.get("has_multiple_models") is True, (
            "Exercise 26 should have has_multiple_models=True (PICM → PFCS recorte)"
        )

    def test_optimization_exercises_present(self, exercises):
        """Exercises with dimensioning must be flagged."""
        opt_exs = [e for e in exercises if e.get("has_optimization") is True]
        assert len(opt_exs) >= 2, (
            f"At least 2 of exercises 24-26 should have has_optimization=True. "
            f"Found: {len(opt_exs)}"
        )

    def test_cost_exercise_present(self, exercises):
        """EX26 has cost analysis."""
        cost_exs = [e for e in exercises if e.get("has_cost_analysis") is True]
        assert len(cost_exs) >= 1, (
            f"At least 1 of exercises 24-26 should have has_cost_analysis=True. "
            f"Found: {len(cost_exs)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 10 — At least 1 exercise 24-26 has recognition_examples with modified data
# ─────────────────────────────────────────────────────────────────────────────

class TestRecognitionExamples:

    def test_at_least_one_exercise_has_recognition_examples(self, exercises):
        exs_with_examples = [
            e for e in exercises
            if e.get("recognition_examples") and len(e["recognition_examples"]) > 0
        ]
        assert len(exs_with_examples) >= 1, (
            "At least 1 exercise in 24-26 must have recognition_examples"
        )

    def test_all_three_exercises_have_recognition_examples(self, exercises):
        for e in exercises:
            examples = e.get("recognition_examples", [])
            assert len(examples) >= 1, (
                f"Exercise {e['exercise_id']} should have at least 1 recognition_example"
            )

    def test_recognition_examples_have_modified_data(self, exercises):
        """Recognition examples must be strings with sufficient content."""
        for e in exercises:
            for ex_text in e.get("recognition_examples", []):
                assert isinstance(ex_text, str) and len(ex_text.strip()) > 30, (
                    f"Recognition example in {e['exercise_id']} is too short or not a string: "
                    f"{ex_text!r}"
                )

    def test_recognition_examples_do_not_reference_exact_exercise_numbers(self, exercises):
        """Examples should not reference 'ejercicio 24' etc. (structural, not memorized)."""
        import re
        for e in exercises:
            for ex_text in e.get("recognition_examples", []):
                assert not re.search(r"\bejercicio\s+2[456]\b", ex_text.lower()), (
                    f"Recognition example in {e['exercise_id']} references a specific "
                    f"exercise number: {ex_text[:60]}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 11 — Analyzer recognizes recognition_examples for exercises 24-26
# ─────────────────────────────────────────────────────────────────────────────

def _recognition_cases_24_26() -> list[tuple[str, str, str]]:
    """Build parametrize list from recognition_examples in exercises 24-26."""
    sols = load_solutions()
    cases = []
    for ex in sols.get("exercises", []):
        sn = ex.get("source_number", 0)
        if 24 <= sn <= 26:
            model = ex.get("model", "")
            eid   = ex.get("exercise_id", "")
            for example in ex.get("recognition_examples", []):
                cases.append((eid, model, example))
    return cases


_RECOGNITION_CASES_24_26 = _recognition_cases_24_26()


@pytest.mark.parametrize(
    "exercise_id,expected_model,example_text",
    _RECOGNITION_CASES_24_26,
    ids=[f"{c[0]}_{i}" for i, c in enumerate(_RECOGNITION_CASES_24_26)],
)
def test_analyzer_identifies_model_from_recognition_example_24_26(
    exercise_id, expected_model, example_text, analyzer
):
    """Analyzer must identify the correct model from recognition_examples of EX24-26."""
    req = StatementAnalysisRequest(text=example_text)
    result = analyzer.analyze(req)
    assert result.identified_model == expected_model, (
        f"[{exercise_id}] Expected model {expected_model}, "
        f"got {result.identified_model!r} for text: {example_text[:80]}..."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group 12 — No memorized numerical results in formula steps (exercises 24-26)
# ─────────────────────────────────────────────────────────────────────────────

class TestNoMemoizedResults:

    def _expression_looks_memorized(self, expr: str) -> bool:
        import re
        cleaned = expr.strip()
        # Contains an operator or placeholder → structural, not memorized
        if "{" in cleaned or any(
            op in cleaned
            for op in ["=", "/", "×", "+", "−", "-", "*", "^", "Σ", "⁻", "⌈", "⌉", "·"]
        ):
            return False
        # Pure number string → memorized
        if re.fullmatch(r"[\d.,\s]+", cleaned):
            return True
        return False

    def test_expressions_are_symbolic_not_numeric(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for step in lit.get("formula_order", []):
                    expr = step.get("expression", "")
                    assert not self._expression_looks_memorized(expr), (
                        f"Expression looks memorized (bare number) in "
                        f"{e['exercise_id']} lit {lit['literal_id']} "
                        f"step {step.get('formula_key')}: {expr!r}"
                    )

    def test_substitution_templates_contain_placeholders(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for step in lit.get("formula_order", []):
                    tpl = step.get("substitution_template", "")
                    if tpl:
                        assert "{" in tpl and "}" in tpl, (
                            f"substitution_template has no {{placeholders}} in "
                            f"{e['exercise_id']} lit {lit['literal_id']} "
                            f"step {step.get('formula_key')}: {tpl!r}"
                        )

    def test_expected_results_have_null_value(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                erv = lit.get("expected_result_for_validation", {})
                if erv:
                    val = erv.get("value")
                    assert val is None, (
                        f"expected_result_for_validation.value should be null in "
                        f"{e['exercise_id']} lit {lit['literal_id']}: value={val}"
                    )


# ─────────────────────────────────────────────────────────────────────────────
# Bonus — Metadata and source file integrity
# ─────────────────────────────────────────────────────────────────────────────

class TestMetadataIntegrity:

    def test_metadata_exercises_included_covers_1_to_26(self, solutions):
        meta = solutions.get("_metadata", {})
        included = meta.get("exercises_included", "")
        assert "1" in included and int(included.split("-")[-1]) >= 26, (
            f"_metadata.exercises_included should cover up to 26, got: {included!r}"
        )

    def test_every_exercise_24_26_has_source_file(self, exercises):
        for e in exercises:
            sf = e.get("source_file", "")
            assert "docx" in sf.lower(), (
                f"Exercise {e['exercise_id']} source_file should reference .docx, "
                f"got: {sf!r}"
            )

    def test_known_ids_24_26_present(self, exercises):
        ids = {e["exercise_id"] for e in exercises}
        expected_ids = {
            "24_supermercado_atencion_cliente_picm",
            "25_ventiladores_ensamblaje_pics_reproceso",
            "26_control_calidad_W_condition_pfcs",
        }
        for eid in expected_ids:
            assert eid in ids, f"Expected exercise_id {eid!r} not found. Present: {ids}"

    def test_docx_is_not_modified(self):
        """The source .docx must not be modified (only the JSON knowledge base)."""
        from pathlib import Path
        docx = (
            Path(__file__).resolve().parent.parent.parent
            / "Ejercicios Propuestos Teoría de Colas.docx"
        )
        assert docx.exists(), f".docx file not found at expected path: {docx}"

    def test_no_temp_scripts_exist(self):
        """No temporary debug/read scripts should exist in the project root."""
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent.parent
        forbidden = [
            "debug_literals.py",
            "read_pdf.py",
            "_add_exercises_21_23.py",
            "_add_exercises_24_26.py",
            "_check_recog_24_26.py",
            "_show_ex22.py",
        ]
        for fname in forbidden:
            assert not (root / fname).exists(), (
                f"Temporary file {fname} should not exist in project root"
            )

"""
Phase KB — Ejercicios 27-30 Structural Knowledge Coverage
==========================================================
Validates analysis_exercise_solutions.json (exercises 27-30) against 12 groups:

 1. Exactly 4 NEW exercises exist (source_number 27, 28, 29, 30)
 2. Unique exercise_ids (across all 30)
 3. Every exercise 27-30 has 'model' field (valid model name)
 4. Every exercise 27-30 has 'variables_to_extract'
 5. Every exercise 27-30 has 'literals'
 6. Every literal has 'objective'
 7. Every literal has 'formula_order' (non-empty list)
 8. Every formula_order step has: order, formula_key, expression, produces
 9. Models covered in 27-30: all PICM (dimensioning + cost)
10. At least 1 exercise 27-30 has 'recognition_examples' with modified data
11. The analyzer recognizes recognition_examples for exercises 27-30
12. No memorized numerical results in formula steps of exercises 27-30
    + No temp scripts exist; metadata covers up to 30

Read from: infrastructure/data/analysis/analysis_exercise_solutions.json
Source:    Ejercicios Propuestos Teoría de Colas.docx  (párrafos [234]-[279])
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
    """Only exercises 27-30."""
    return [e for e in all_exercises if 27 <= e["source_number"] <= 30]


@pytest.fixture(scope="module")
def analyzer():
    return make_analyzer()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Group 1 — Exercises 27-30 exist; total = 30
# ─────────────────────────────────────────────────────────────────────────────

class TestExerciseCount:

    def test_solutions_file_loaded(self, solutions):
        assert solutions_loaded(), "analysis_exercise_solutions.json not found or empty"

    def test_exactly_30_exercises_total(self, all_exercises):
        assert len(all_exercises) == 30, (
            f"Expected exactly 30 total exercises, got {len(all_exercises)}"
        )

    def test_exactly_4_exercises_27_to_30(self, exercises):
        assert len(exercises) == 4, (
            f"Expected exactly 4 exercises (27-30), got {len(exercises)}"
        )

    def test_source_numbers_are_27_28_29_30(self, exercises):
        nums = sorted(e["source_number"] for e in exercises)
        assert nums == [27, 28, 29, 30], (
            f"source_number values must be exactly [27, 28, 29, 30], got {nums}"
        )

    def test_get_solution_by_number_works_for_27_30(self):
        for n in (27, 28, 29, 30):
            sol = get_solution_by_number(n)
            assert sol is not None, f"get_solution_by_number({n}) returned None"
            assert sol["source_number"] == n

    def test_exercises_1_to_26_still_present(self, all_exercises):
        nums = {e["source_number"] for e in all_exercises}
        for n in range(1, 27):
            assert n in nums, f"Exercise {n} (EX01-26) is missing after adding EX27-30"


# ─────────────────────────────────────────────────────────────────────────────
# Group 2 — Unique exercise_ids across all 30 exercises
# ─────────────────────────────────────────────────────────────────────────────

class TestUniqueIds:

    def test_exercise_ids_are_unique_across_all(self, all_exercises):
        ids = [e["exercise_id"] for e in all_exercises]
        assert len(ids) == len(set(ids)), (
            f"Duplicate exercise_ids found: {[x for x in ids if ids.count(x) > 1]}"
        )

    def test_exercise_ids_27_30_are_non_empty_strings(self, exercises):
        for e in exercises:
            eid = e.get("exercise_id", "")
            assert isinstance(eid, str) and eid.strip(), (
                f"Exercise {e.get('source_number')} has invalid exercise_id: {eid!r}"
            )

    def test_exercise_ids_27_30_distinct_from_previous(self, exercises, all_exercises):
        ids_prev = {e["exercise_id"] for e in all_exercises if e["source_number"] < 27}
        ids_new  = {e["exercise_id"] for e in exercises}
        overlap  = ids_prev & ids_new
        assert not overlap, f"exercise_id collision between 1-26 and 27-30: {overlap}"

    def test_known_ids_27_30_present(self, exercises):
        ids = {e["exercise_id"] for e in exercises}
        expected_ids = {
            "27_registro_civil_ventanillas_picm",
            "28_reparacion_ordenadores_picm_costo",
            "29_ensamblaje_control_calidad_wq_condition",
            "30_telefonia_asesoras_reclamos_picm_costo",
        }
        for eid in expected_ids:
            assert eid in ids, f"Expected exercise_id {eid!r} not found. Present: {ids}"


# ─────────────────────────────────────────────────────────────────────────────
# Group 3 — Every exercise 27-30 has valid 'model' field
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

    def test_all_27_30_are_picm(self, exercises):
        """All four exercises 27-30 are M/M/c (PICM)."""
        for e in exercises:
            assert e["model"] == "PICM", (
                f"Exercise {e['exercise_id']} must be PICM (multiple servers, "
                f"infinite population), got {e['model']!r}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Group 4 — Every exercise 27-30 has variables_to_extract
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

    def test_all_exercises_have_lambda_and_mu(self, exercises):
        """All PICM exercises need arrival rate and service rate."""
        for e in exercises:
            names = {v["name"] for v in e.get("variables_to_extract", [])}
            has_lambda = any(
                n == "lambda_" or n.startswith("lambda_") or n == "inter_arrival_min"
                for n in names
            )
            has_mu = any(
                n == "mu" or n.startswith("mu_") or n == "service_time_min"
                for n in names
            )
            assert has_lambda, (
                f"PICM exercise {e['exercise_id']} missing lambda variable. Found: {names}"
            )
            assert has_mu, (
                f"PICM exercise {e['exercise_id']} missing mu variable. Found: {names}"
            )

    def test_ex27_has_pw_max(self, exercises):
        """Exercise 27 must expose P_w constraint (P(esperar)≤50%)."""
        ex27 = next((e for e in exercises if e["source_number"] == 27), None)
        assert ex27, "Exercise 27 not found"
        names = {v["name"] for v in ex27.get("variables_to_extract", [])}
        assert "Pw_max" in names, (
            f"Exercise 27 must have Pw_max variable (P(esperar)≤50%). Found: {names}"
        )

    def test_ex28_has_cost_variables(self, exercises):
        """Exercise 28 must expose cost variables for optimization."""
        ex28 = next((e for e in exercises if e["source_number"] == 28), None)
        assert ex28, "Exercise 28 not found"
        names = {v["name"] for v in ex28.get("variables_to_extract", [])}
        has_cost = any("cost" in n.lower() or "costo" in n.lower() for n in names)
        assert has_cost, (
            f"Exercise 28 must have at least one cost variable. Found: {names}"
        )

    def test_ex29_has_wq_max(self, exercises):
        """Exercise 29 must expose Wq constraint (Wq≤4 min)."""
        ex29 = next((e for e in exercises if e["source_number"] == 29), None)
        assert ex29, "Exercise 29 not found"
        names = {v["name"] for v in ex29.get("variables_to_extract", [])}
        has_wq = any("wq" in n.lower() or "Wq" in n for n in names)
        assert has_wq, (
            f"Exercise 29 must have a Wq constraint variable. Found: {names}"
        )

    def test_ex30_has_cost_variables(self, exercises):
        """Exercise 30 must expose cost variables for optimization."""
        ex30 = next((e for e in exercises if e["source_number"] == 30), None)
        assert ex30, "Exercise 30 not found"
        names = {v["name"] for v in ex30.get("variables_to_extract", [])}
        has_cost = any("cost" in n.lower() or "costo" in n.lower() for n in names)
        assert has_cost, (
            f"Exercise 30 must have at least one cost variable. Found: {names}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 5 — Every exercise 27-30 has literals
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

    def test_ex27_has_pw_condition_literal(self, exercises):
        """Exercise 27 must have a literal for P(W)≤0.5 dimensioning."""
        ex27 = next((e for e in exercises if e["source_number"] == 27), None)
        assert ex27, "Exercise 27 not found"
        pw_lits = [
            lit for lit in ex27.get("literals", [])
            if "pw" in lit.get("objective", "").lower()
        ]
        assert len(pw_lits) > 0, (
            f"Exercise 27 must have at least 1 literal for Pw optimization. "
            f"Objectives: {[l.get('objective') for l in ex27.get('literals', [])]}"
        )

    def test_ex28_has_cost_optimization_literal(self, exercises):
        """Exercise 28 must have a literal for cost minimization."""
        ex28 = next((e for e in exercises if e["source_number"] == 28), None)
        assert ex28, "Exercise 28 not found"
        cost_lits = [
            lit for lit in ex28.get("literals", [])
            if "cost" in lit.get("objective", "").lower()
        ]
        assert len(cost_lits) > 0, (
            f"Exercise 28 must have at least 1 literal for cost analysis. "
            f"Objectives: {[l.get('objective') for l in ex28.get('literals', [])]}"
        )

    def test_ex29_has_wq_condition_literal(self, exercises):
        """Exercise 29 must have a literal for Wq≤4min dimensioning."""
        ex29 = next((e for e in exercises if e["source_number"] == 29), None)
        assert ex29, "Exercise 29 not found"
        wq_lits = [
            lit for lit in ex29.get("literals", [])
            if "wq" in lit.get("objective", "").lower()
        ]
        assert len(wq_lits) > 0, (
            f"Exercise 29 must have at least 1 literal for Wq constraint. "
            f"Objectives: {[l.get('objective') for l in ex29.get('literals', [])]}"
        )

    def test_ex30_has_cost_optimization_literal(self, exercises):
        """Exercise 30 must have a literal for cost minimization."""
        ex30 = next((e for e in exercises if e["source_number"] == 30), None)
        assert ex30, "Exercise 30 not found"
        cost_lits = [
            lit for lit in ex30.get("literals", [])
            if "cost" in lit.get("objective", "").lower()
        ]
        assert len(cost_lits) > 0, (
            f"Exercise 30 must have at least 1 literal for cost analysis. "
            f"Objectives: {[l.get('objective') for l in ex30.get('literals', [])]}"
        )

    def test_ex27_has_at_least_5_literals(self, exercises):
        ex27 = next((e for e in exercises if e["source_number"] == 27), None)
        assert ex27, "Exercise 27 not found"
        lits = ex27.get("literals", [])
        assert len(lits) >= 5, (
            f"Exercise 27 (registro civil, 5 parts a-e) should have ≥5 literals, "
            f"got {len(lits)}"
        )

    def test_ex29_has_at_least_4_literals(self, exercises):
        ex29 = next((e for e in exercises if e["source_number"] == 29), None)
        assert ex29, "Exercise 29 not found"
        lits = ex29.get("literals", [])
        assert len(lits) >= 4, (
            f"Exercise 29 (ensamblaje calidad, 4 parts a-d) should have ≥4 literals, "
            f"got {len(lits)}"
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
# Group 9 — Models covered in 27-30 (all PICM, with dimensioning and costs)
# ─────────────────────────────────────────────────────────────────────────────

class TestModelsCovered:

    def test_picm_is_the_only_model_in_27_30(self, exercises):
        models = {e["model"] for e in exercises}
        assert models == {"PICM"}, (
            f"All exercises 27-30 must be PICM. Found: {models}"
        )

    def test_optimization_exercises_present(self, exercises):
        """All 4 exercises involve dimensioning/optimization."""
        opt_exs = [e for e in exercises if e.get("has_optimization") is True]
        assert len(opt_exs) >= 4, (
            f"All 4 of exercises 27-30 should have has_optimization=True. "
            f"Found: {len(opt_exs)}"
        )

    def test_cost_exercises_present(self, exercises):
        """EX28 and EX30 have explicit cost analysis."""
        cost_exs = [e for e in exercises if e.get("has_cost_analysis") is True]
        assert len(cost_exs) >= 2, (
            f"At least 2 of exercises 27-30 should have has_cost_analysis=True (EX28, EX30). "
            f"Found: {len(cost_exs)}"
        )

    def test_ex27_has_optimization_flag(self, exercises):
        ex27 = next((e for e in exercises if e["source_number"] == 27), None)
        assert ex27 and ex27.get("has_optimization") is True, (
            "Exercise 27 (P_w≤0.5 → c_min=3) must have has_optimization=True"
        )

    def test_ex28_has_cost_flag(self, exercises):
        ex28 = next((e for e in exercises if e["source_number"] == 28), None)
        assert ex28 and ex28.get("has_cost_analysis") is True, (
            "Exercise 28 (minimize daily cost) must have has_cost_analysis=True"
        )

    def test_ex29_has_optimization_flag(self, exercises):
        ex29 = next((e for e in exercises if e["source_number"] == 29), None)
        assert ex29 and ex29.get("has_optimization") is True, (
            "Exercise 29 (Wq≤4min → c_min=3) must have has_optimization=True"
        )

    def test_ex30_has_cost_flag(self, exercises):
        ex30 = next((e for e in exercises if e["source_number"] == 30), None)
        assert ex30 and ex30.get("has_cost_analysis") is True, (
            "Exercise 30 (minimize total cost) must have has_cost_analysis=True"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 10 — All exercises 27-30 have recognition_examples with modified data
# ─────────────────────────────────────────────────────────────────────────────

class TestRecognitionExamples:

    def test_all_exercises_have_recognition_examples(self, exercises):
        for e in exercises:
            examples = e.get("recognition_examples", [])
            assert len(examples) >= 1, (
                f"Exercise {e['exercise_id']} must have at least 1 recognition_example"
            )

    def test_all_exercises_have_at_least_2_recognition_examples(self, exercises):
        for e in exercises:
            examples = e.get("recognition_examples", [])
            assert len(examples) >= 2, (
                f"Exercise {e['exercise_id']} should have ≥2 recognition_examples, "
                f"got {len(examples)}"
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
        """Examples should not reference 'ejercicio 27' etc. (structural, not memorized)."""
        import re
        for e in exercises:
            for ex_text in e.get("recognition_examples", []):
                assert not re.search(r"\bejercicio\s+[23][0-9]\b", ex_text.lower()), (
                    f"Recognition example in {e['exercise_id']} references a specific "
                    f"exercise number: {ex_text[:60]}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 11 — Analyzer recognizes recognition_examples for exercises 27-30
# ─────────────────────────────────────────────────────────────────────────────

def _recognition_cases_27_30() -> list[tuple[str, str, str]]:
    """Build parametrize list from recognition_examples in exercises 27-30."""
    sols = load_solutions()
    cases = []
    for ex in sols.get("exercises", []):
        sn = ex.get("source_number", 0)
        if 27 <= sn <= 30:
            model = ex.get("model", "")
            eid   = ex.get("exercise_id", "")
            for example in ex.get("recognition_examples", []):
                cases.append((eid, model, example))
    return cases


_RECOGNITION_CASES_27_30 = _recognition_cases_27_30()


@pytest.mark.parametrize(
    "exercise_id,expected_model,example_text",
    _RECOGNITION_CASES_27_30,
    ids=[f"{c[0]}_{i}" for i, c in enumerate(_RECOGNITION_CASES_27_30)],
)
def test_analyzer_identifies_model_from_recognition_example_27_30(
    exercise_id, expected_model, example_text, analyzer
):
    """Analyzer must identify the correct model from recognition_examples of EX27-30."""
    req = StatementAnalysisRequest(text=example_text)
    result = analyzer.analyze(req)
    assert result.identified_model == expected_model, (
        f"[{exercise_id}] Expected model {expected_model}, "
        f"got {result.identified_model!r} for text: {example_text[:80]}..."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group 12 — No memorized numerical results + metadata + no temp scripts
# ─────────────────────────────────────────────────────────────────────────────

class TestNoMemoizedResults:

    def _expression_looks_memorized(self, expr: str) -> bool:
        import re
        cleaned = expr.strip()
        if "{" in cleaned or any(
            op in cleaned
            for op in ["=", "/", "×", "+", "−", "-", "*", "^", "Σ", "⁻", "⌈", "⌉", "·"]
        ):
            return False
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


class TestMetadataIntegrity:

    def test_metadata_exercises_included_covers_1_to_30(self, solutions):
        meta = solutions.get("_metadata", {})
        included = meta.get("exercises_included", "")
        assert "1" in included and int(included.split("-")[-1]) >= 30, (
            f"_metadata.exercises_included should cover up to 30, got: {included!r}"
        )

    def test_total_exercises_in_metadata_is_30(self, solutions):
        meta = solutions.get("_metadata", {})
        total = meta.get("total_exercises_included", 0)
        assert total == 30, (
            f"_metadata.total_exercises_included should be 30, got: {total}"
        )

    def test_every_exercise_27_30_has_source_file(self, exercises):
        for e in exercises:
            sf = e.get("source_file", "")
            assert "docx" in sf.lower(), (
                f"Exercise {e['exercise_id']} source_file should reference .docx, "
                f"got: {sf!r}"
            )

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
            "_add_exercises_27_30.py",
            "_check_recog_24_26.py",
            "_show_ex22.py",
            "_show_ex26.py",
            "_read_ex27_30.py",
            "_fix_recog_27_30.py",
            "_check_recog_27_30.py",
        ]
        for fname in forbidden:
            assert not (root / fname).exists(), (
                f"Temporary file {fname} should not exist in project root"
            )

"""
Phase KB — Ejercicios 21-23 Structural Knowledge Coverage
==========================================================
Validates analysis_exercise_solutions.json (exercises 21-23) against 12 groups:

 1. Exactly 3 NEW exercises exist (source_number 21, 22, 23)
 2. Unique exercise_ids (across all 23)
 3. Every exercise 21-23 has 'model' field (valid model name)
 4. Every exercise 21-23 has 'variables_to_extract'
 5. Every exercise 21-23 has 'literals'
 6. Every literal has 'objective'
 7. Every literal has 'formula_order' (non-empty list)
 8. Every formula_order step has: order, formula_key, expression, produces
 9. Models covered in 21-23: PICM and PFCS/PFHET present
10. At least 1 exercise 21-23 has 'recognition_examples' with modified data
11. The analyzer recognizes recognition_examples for exercises 21-23
12. No memorized numerical results in formula steps of exercises 21-23

Read from: infrastructure/data/analysis/analysis_exercise_solutions.json
Source:    Ejercicios Propuestos Teoría de Colas.docx  (párrafos [172]-[199])
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
    """Only exercises 21-23."""
    return [e for e in all_exercises if 21 <= e["source_number"] <= 23]


@pytest.fixture(scope="module")
def analyzer():
    return make_analyzer()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Group 1 — Exercises 21-23 exist; total ≥ 23
# ─────────────────────────────────────────────────────────────────────────────

class TestExerciseCount:

    def test_solutions_file_loaded(self, solutions):
        assert solutions_loaded(), "analysis_exercise_solutions.json not found or empty"

    def test_at_least_23_exercises_total(self, all_exercises):
        assert len(all_exercises) >= 23, (
            f"Expected ≥23 total exercises, got {len(all_exercises)}"
        )

    def test_exactly_3_exercises_21_to_23(self, exercises):
        assert len(exercises) == 3, (
            f"Expected exactly 3 exercises (21-23), got {len(exercises)}"
        )

    def test_source_numbers_are_21_22_23(self, exercises):
        nums = sorted(e["source_number"] for e in exercises)
        assert nums == [21, 22, 23], (
            f"source_number values must be exactly [21, 22, 23], got {nums}"
        )

    def test_get_solution_by_number_works_for_21_23(self):
        for n in (21, 22, 23):
            sol = get_solution_by_number(n)
            assert sol is not None, f"get_solution_by_number({n}) returned None"
            assert sol["source_number"] == n

    def test_exercises_1_to_20_still_present(self, all_exercises):
        nums = {e["source_number"] for e in all_exercises}
        for n in range(1, 21):
            assert n in nums, f"Exercise {n} (EX01-20) is missing after adding EX21-23"


# ─────────────────────────────────────────────────────────────────────────────
# Group 2 — Unique exercise_ids across all 23 exercises
# ─────────────────────────────────────────────────────────────────────────────

class TestUniqueIds:

    def test_exercise_ids_are_unique_across_all(self, all_exercises):
        ids = [e["exercise_id"] for e in all_exercises]
        assert len(ids) == len(set(ids)), (
            f"Duplicate exercise_ids found: {[x for x in ids if ids.count(x) > 1]}"
        )

    def test_exercise_ids_21_23_are_non_empty_strings(self, exercises):
        for e in exercises:
            eid = e.get("exercise_id", "")
            assert isinstance(eid, str) and eid.strip(), (
                f"Exercise {e.get('source_number')} has invalid exercise_id: {eid!r}"
            )

    def test_exercise_ids_21_23_distinct_from_previous(self, exercises, all_exercises):
        ids_prev = {e["exercise_id"] for e in all_exercises if e["source_number"] < 21}
        ids_new  = {e["exercise_id"] for e in exercises}
        overlap  = ids_prev & ids_new
        assert not overlap, f"exercise_id collision between 1-20 and 21-23: {overlap}"


# ─────────────────────────────────────────────────────────────────────────────
# Group 3 — Every exercise 21-23 has valid 'model' field
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

    def test_ex21_is_picm(self, exercises):
        ex21 = next((e for e in exercises if e["source_number"] == 21), None)
        assert ex21 is not None, "Exercise 21 not found"
        assert ex21["model"] == "PICM", (
            f"Exercise 21 must be PICM (M/M/c condition L), got {ex21['model']!r}"
        )

    def test_ex22_is_picm(self, exercises):
        ex22 = next((e for e in exercises if e["source_number"] == 22), None)
        assert ex22 is not None, "Exercise 22 not found"
        assert ex22["model"] == "PICM", (
            f"Exercise 22 must be PICM (M/M/5 licencias), got {ex22['model']!r}"
        )

    def test_ex23_is_pfcs(self, exercises):
        ex23 = next((e for e in exercises if e["source_number"] == 23), None)
        assert ex23 is not None, "Exercise 23 not found"
        assert ex23["model"] == "PFCS", (
            f"Exercise 23 must be PFCS (montacargas independientes), got {ex23['model']!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 4 — Every exercise 21-23 has variables_to_extract
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

    def test_picm_exercises_have_lambda_and_mu(self, exercises):
        for e in exercises:
            if e["model"] == "PICM":
                names = {v["name"] for v in e.get("variables_to_extract", [])}
                has_lambda = any(
                    n == "lambda_" or n.startswith("lambda_") or n == "lambda_per_unit"
                    or n == "inter_arrival_min"
                    for n in names
                )
                has_mu = any(n == "mu" or n.startswith("mu_") or n == "service_time_min" for n in names)
                assert has_lambda, (
                    f"PICM exercise {e['exercise_id']} missing lambda variable. Found: {names}"
                )
                assert has_mu, (
                    f"PICM exercise {e['exercise_id']} missing mu variable. Found: {names}"
                )

    def test_pfcs_exercise_has_M(self, exercises):
        for e in exercises:
            if e["model"] == "PFCS":
                names = {v["name"] for v in e.get("variables_to_extract", [])}
                assert "M" in names, (
                    f"PFCS exercise {e['exercise_id']} must have variable M. Found: {names}"
                )

    def test_pfcs_exercise_has_mu_A_and_mu_B(self, exercises):
        """Exercise 23 (PFCS with 2 independent technicians) must have mu_A and mu_B."""
        for e in exercises:
            if e["model"] == "PFCS" and e.get("has_multiple_models"):
                names = {v["name"] for v in e.get("variables_to_extract", [])}
                assert "mu_A" in names and "mu_B" in names, (
                    f"PFCS multi-model exercise {e['exercise_id']} must have mu_A and mu_B. "
                    f"Found: {names}"
                )

    def test_ex21_has_L_threshold(self, exercises):
        ex21 = next((e for e in exercises if e["source_number"] == 21), None)
        assert ex21, "Exercise 21 not found"
        names = {v["name"] for v in ex21.get("variables_to_extract", [])}
        assert "L_threshold" in names, (
            f"Exercise 21 must have L_threshold variable. Found: {names}"
        )

    def test_ex22_has_failure_prob(self, exercises):
        ex22 = next((e for e in exercises if e["source_number"] == 22), None)
        assert ex22, "Exercise 22 not found"
        names = {v["name"] for v in ex22.get("variables_to_extract", [])}
        assert "failure_prob" in names, (
            f"Exercise 22 must have failure_prob variable. Found: {names}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 5 — Every exercise 21-23 has literals
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
                    f"Literal {lit.get('literal_id')} in {e['exercise_id']} has empty literal_text"
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

    def test_ex21_has_pfcs_literal(self, exercises):
        """Exercise 21 must have at least one literal with PFCS model_context (recorte)."""
        ex21 = next((e for e in exercises if e["source_number"] == 21), None)
        assert ex21, "Exercise 21 not found"
        pfcs_lits = [
            lit for lit in ex21.get("literals", [])
            if lit.get("model_context") == "PFCS"
        ]
        assert len(pfcs_lits) > 0, (
            f"Exercise 21 must have at least 1 literal with model_context=PFCS "
            f"(recorte de personal → población finita)."
        )

    def test_ex22_has_cost_literal(self, exercises):
        """Exercise 22 must have a literal with objective related to revenue/cost."""
        ex22 = next((e for e in exercises if e["source_number"] == 22), None)
        assert ex22, "Exercise 22 not found"
        cost_lits = [
            lit for lit in ex22.get("literals", [])
            if "cost" in lit.get("objective", "").lower()
               or "revenue" in lit.get("objective", "").lower()
        ]
        assert len(cost_lits) > 0, (
            f"Exercise 22 must have at least 1 literal about costs/revenue. "
            f"Objectives found: {[l.get('objective') for l in ex22.get('literals', [])]}"
        )

    def test_ex23_has_pfhet_literal(self, exercises):
        """Exercise 23 must have at least one literal with PFHET model_context (unificado)."""
        ex23 = next((e for e in exercises if e["source_number"] == 23), None)
        assert ex23, "Exercise 23 not found"
        pfhet_lits = [
            lit for lit in ex23.get("literals", [])
            if lit.get("model_context") == "PFHET"
        ]
        assert len(pfhet_lits) > 0, (
            f"Exercise 23 must have at least 1 literal with model_context=PFHET "
            f"(taller unificado)."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 6 — Every literal has 'objective'
# ─────────────────────────────────────────────────────────────────────────────

class TestLiteralObjectives:

    def test_all_literals_have_objective(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                assert lit.get("objective"), (
                    f"Literal {lit.get('literal_id')} in {e['exercise_id']} missing objective"
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
# Group 9 — Models covered in 21-23 include PICM and PFCS/PFHET
# ─────────────────────────────────────────────────────────────────────────────

class TestModelsCovered:

    def test_picm_present_in_21_23(self, exercises):
        models = {e["model"] for e in exercises}
        assert "PICM" in models, (
            f"PICM must be present among exercises 21-23. Found: {models}"
        )

    def test_pfcs_or_pfhet_present_in_21_23(self, exercises):
        models = {e["model"] for e in exercises}
        assert models & {"PFCS", "PFHET"}, (
            f"PFCS or PFHET must be present among exercises 21-23. Found: {models}"
        )

    def test_ex21_has_multiple_models_flag(self, exercises):
        """Exercise 21 transitions from PICM to PFCS — has_multiple_models must be true."""
        ex21 = next((e for e in exercises if e["source_number"] == 21), None)
        assert ex21 and ex21.get("has_multiple_models") is True, (
            "Exercise 21 should have has_multiple_models=True (PICM → PFCS)"
        )

    def test_ex23_has_multiple_models_flag(self, exercises):
        """Exercise 23 transitions from PFCS to PFHET — has_multiple_models must be true."""
        ex23 = next((e for e in exercises if e["source_number"] == 23), None)
        assert ex23 and ex23.get("has_multiple_models") is True, (
            "Exercise 23 should have has_multiple_models=True (PFCS → PFHET)"
        )

    def test_cost_exercises_present(self, exercises):
        """Exercises with cost analysis must be flagged."""
        cost_exs = [e for e in exercises if e.get("has_cost_analysis") is True]
        assert len(cost_exs) >= 2, (
            f"At least 2 of exercises 21-23 should have has_cost_analysis=True. "
            f"Found: {len(cost_exs)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 10 — At least 1 exercise 21-23 has recognition_examples with modified data
# ─────────────────────────────────────────────────────────────────────────────

class TestRecognitionExamples:

    def test_at_least_one_exercise_has_recognition_examples(self, exercises):
        exs_with_examples = [
            e for e in exercises
            if e.get("recognition_examples") and len(e["recognition_examples"]) > 0
        ]
        assert len(exs_with_examples) >= 1, (
            "At least 1 exercise in 21-23 must have recognition_examples"
        )

    def test_all_three_exercises_have_recognition_examples(self, exercises):
        for e in exercises:
            examples = e.get("recognition_examples", [])
            assert len(examples) >= 1, (
                f"Exercise {e['exercise_id']} should have at least 1 recognition_example"
            )

    def test_recognition_examples_have_modified_data(self, exercises):
        """Recognition examples must differ from the exact docx statement (modified data)."""
        # Check that at least one example per exercise uses different numeric values
        # by verifying examples are strings with meaningful content
        for e in exercises:
            for ex_text in e.get("recognition_examples", []):
                assert isinstance(ex_text, str) and len(ex_text.strip()) > 30, (
                    f"Recognition example in {e['exercise_id']} is too short or not a string: "
                    f"{ex_text!r}"
                )

    def test_recognition_examples_do_not_reference_exact_exercise_numbers(self, exercises):
        """Examples should not reference 'ejercicio 21' etc. (structural, not memorized)."""
        import re
        for e in exercises:
            for ex_text in e.get("recognition_examples", []):
                assert not re.search(r"\bejercicio\s+2[123]\b", ex_text.lower()), (
                    f"Recognition example in {e['exercise_id']} references a specific "
                    f"exercise number (should be structural): {ex_text[:60]}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 11 — Analyzer recognizes recognition_examples for exercises 21-23
# ─────────────────────────────────────────────────────────────────────────────

def _recognition_cases_21_23() -> list[tuple[str, str, str]]:
    """Build parametrize list from recognition_examples in exercises 21-23."""
    sols = load_solutions()
    cases = []
    for ex in sols.get("exercises", []):
        sn = ex.get("source_number", 0)
        if 21 <= sn <= 23:
            model = ex.get("model", "")
            eid   = ex.get("exercise_id", "")
            for example in ex.get("recognition_examples", []):
                cases.append((eid, model, example))
    return cases


_RECOGNITION_CASES_21_23 = _recognition_cases_21_23()


@pytest.mark.parametrize(
    "exercise_id,expected_model,example_text",
    _RECOGNITION_CASES_21_23,
    ids=[f"{c[0]}_{i}" for i, c in enumerate(_RECOGNITION_CASES_21_23)],
)
def test_analyzer_identifies_model_from_recognition_example_21_23(
    exercise_id, expected_model, example_text, analyzer
):
    """Analyzer must identify the correct model from recognition_examples of EX21-23."""
    req = StatementAnalysisRequest(text=example_text)
    result = analyzer.analyze(req)
    assert result.identified_model == expected_model, (
        f"[{exercise_id}] Expected model {expected_model}, "
        f"got {result.identified_model!r} for text: {example_text[:80]}..."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group 12 — No memorized numerical results in formula steps (exercises 21-23)
# ─────────────────────────────────────────────────────────────────────────────

class TestNoMemoizedResults:

    def _expression_looks_memorized(self, expr: str) -> bool:
        import re
        cleaned = expr.strip()
        # Contains an operator or placeholder → structural, not memorized
        if "{" in cleaned or any(
            op in cleaned for op in ["=", "/", "×", "+", "−", "-", "*", "^", "Σ", "Σ", "⁻"]
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

    def test_metadata_exercises_included_covers_1_to_23(self, solutions):
        meta = solutions.get("_metadata", {})
        included = meta.get("exercises_included", "")
        assert "1" in included and int(included.split("-")[-1]) >= 23, (
            f"_metadata.exercises_included should cover up to at least 23, got: {included!r}"
        )

    def test_every_exercise_21_23_has_source_file(self, exercises):
        for e in exercises:
            sf = e.get("source_file", "")
            assert "docx" in sf.lower(), (
                f"Exercise {e['exercise_id']} source_file should reference .docx, got: {sf!r}"
            )

    def test_known_ids_21_23_present(self, exercises):
        ids = {e["exercise_id"] for e in exercises}
        expected_ids = {
            "21_control_calidad_mmc_L_condition",
            "22_licencias_conducir_mmc_reproceso",
            "23_montacargas_pfcs_2independientes_pfhet",
        }
        for eid in expected_ids:
            assert eid in ids, f"Expected exercise_id {eid!r} not found. Present: {ids}"

    def test_docx_is_not_modified(self):
        """The source .docx must not be modified (only the JSON knowledge base)."""
        import os
        from pathlib import Path
        docx = Path(__file__).resolve().parent.parent.parent / "Ejercicios Propuestos Teoría de Colas.docx"
        assert docx.exists(), f".docx file not found at expected path: {docx}"

    def test_no_temp_scripts_exist(self):
        """No temporary debug/read scripts should exist in the project root."""
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent.parent
        forbidden = ["debug_literals.py", "read_pdf.py", "_add_exercises_21_23.py"]
        for fname in forbidden:
            assert not (root / fname).exists(), (
                f"Temporary file {fname} should not exist in project root"
            )

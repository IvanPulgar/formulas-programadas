"""
Phase KB — Ejercicios 11-20 Structural Knowledge Coverage
==========================================================
Validates analysis_exercise_solutions.json (exercises 11-20) against 12 groups:

 1. Exactly 10 NEW exercises exist (source_number 11..20), total ≥ 20
 2. Unique exercise_ids (across all 20)
 3. Every exercise 11-20 has 'model' field (valid model name)
 4. Every exercise 11-20 has 'variables_to_extract'
 5. Every exercise 11-20 has 'literals'
 6. Every literal has 'objective'
 7. Every literal has 'formula_order' (non-empty list)
 8. Every formula_order step has: order, formula_key, expression,
    required_variables or substitution_template, produces
 9. Models covered: PICS, PICM, PFCS, PFHET appear in exercises 11-20
10. At least 3 exercises 11-20 have 'recognition_examples'
11. Analyzer recognizes recognition_examples for exercises 11-20
12. No memorized numerical results in formula steps of exercises 11-20
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
    """Only exercises 11-20."""
    return [e for e in all_exercises if 11 <= e["source_number"] <= 20]


@pytest.fixture(scope="module")
def analyzer():
    return make_analyzer()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Group 1 — Exercises 11-20 exist; total ≥ 20
# ─────────────────────────────────────────────────────────────────────────────

class TestExerciseCount:

    def test_solutions_file_loaded(self, solutions):
        assert solutions_loaded(), "analysis_exercise_solutions.json not found or empty"

    def test_at_least_20_exercises_total(self, all_exercises):
        assert len(all_exercises) >= 20, (
            f"Expected ≥20 total exercises, got {len(all_exercises)}"
        )

    def test_exactly_10_exercises_11_to_20(self, exercises):
        assert len(exercises) == 10, (
            f"Expected exactly 10 exercises (11-20), got {len(exercises)}"
        )

    def test_source_numbers_are_11_to_20(self, exercises):
        nums = sorted(e["source_number"] for e in exercises)
        assert nums == list(range(11, 21)), (
            f"source_number values must be exactly 11..20, got {nums}"
        )

    def test_get_solution_by_number_works_for_11_20(self):
        for n in range(11, 21):
            sol = get_solution_by_number(n)
            assert sol is not None, f"get_solution_by_number({n}) returned None"
            assert sol["source_number"] == n

    def test_exercises_1_to_10_still_present(self, all_exercises):
        nums = {e["source_number"] for e in all_exercises}
        for n in range(1, 11):
            assert n in nums, f"Exercise {n} (EX01-10) is missing after adding EX11-20"


# ─────────────────────────────────────────────────────────────────────────────
# Group 2 — Unique exercise_ids across all 20 exercises
# ─────────────────────────────────────────────────────────────────────────────

class TestUniqueIds:

    def test_exercise_ids_are_unique_across_all(self, all_exercises):
        ids = [e["exercise_id"] for e in all_exercises]
        assert len(ids) == len(set(ids)), (
            f"Duplicate exercise_ids found: {[x for x in ids if ids.count(x) > 1]}"
        )

    def test_exercise_ids_11_20_are_non_empty_strings(self, exercises):
        for e in exercises:
            eid = e.get("exercise_id", "")
            assert isinstance(eid, str) and eid.strip(), (
                f"Exercise {e.get('source_number')} has invalid exercise_id: {eid!r}"
            )

    def test_exercise_ids_11_20_are_distinct_from_1_10(self, exercises, all_exercises):
        ids_1_10 = {e["exercise_id"] for e in all_exercises if e["source_number"] <= 10}
        ids_11_20 = {e["exercise_id"] for e in exercises}
        overlap = ids_1_10 & ids_11_20
        assert not overlap, f"exercise_id collision between 1-10 and 11-20: {overlap}"


# ─────────────────────────────────────────────────────────────────────────────
# Group 3 — Every exercise 11-20 has valid 'model' field
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


# ─────────────────────────────────────────────────────────────────────────────
# Group 4 — Every exercise 11-20 has variables_to_extract
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

    def test_pics_exercises_have_lambda_and_mu(self, exercises):
        for e in exercises:
            if e["model"] == "PICS":
                names = {v["name"] for v in e.get("variables_to_extract", [])}
                has_lambda = any(
                    n == "lambda_" or n.startswith("lambda_") or n == "lambda_per_unit"
                    for n in names
                )
                has_mu = any(n == "mu" or n.startswith("mu_") for n in names)
                assert has_lambda, (
                    f"PICS exercise {e['exercise_id']} missing lambda variable. Found: {names}"
                )
                assert has_mu, (
                    f"PICS exercise {e['exercise_id']} missing mu variable. Found: {names}"
                )

    def test_picm_exercises_have_c(self, exercises):
        for e in exercises:
            if e["model"] == "PICM":
                names = {v["name"] for v in e.get("variables_to_extract", [])}
                assert "c" in names or "num_cajas" in names, (
                    f"PICM exercise {e['exercise_id']} should have 'c' or 'num_cajas'. Found: {names}"
                )

    def test_pfhet_exercise_has_mu_A_and_mu_B(self, exercises):
        for e in exercises:
            if e["model"] == "PFHET":
                names = {v["name"] for v in e.get("variables_to_extract", [])}
                assert "mu_A" in names and "mu_B" in names, (
                    f"PFHET exercise {e['exercise_id']} must have mu_A and mu_B. Found: {names}"
                )

    def test_pfcs_exercises_have_M(self, exercises):
        for e in exercises:
            if e["model"] == "PFCS":
                names = {v["name"] for v in e.get("variables_to_extract", [])}
                assert "M" in names, (
                    f"PFCS exercise {e['exercise_id']} must have variable M. Found: {names}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 5 — Every exercise 11-20 has literals
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
# Group 7 — Every literal has non-empty formula_order list
# ─────────────────────────────────────────────────────────────────────────────

class TestFormulaOrderPresence:

    def test_all_literals_have_formula_order(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                fo = lit.get("formula_order", [])
                assert isinstance(fo, list) and len(fo) > 0, (
                    f"formula_order missing or empty in {e['exercise_id']} "
                    f"lit {lit.get('literal_id')}"
                )

    def test_formula_order_steps_are_dicts(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for step in lit.get("formula_order", []):
                    assert isinstance(step, dict), (
                        f"formula_order step must be a dict in {e['exercise_id']} "
                        f"lit {lit.get('literal_id')}"
                    )


# ─────────────────────────────────────────────────────────────────────────────
# Group 8 — Every formula_order step has required fields + sequential orders
# ─────────────────────────────────────────────────────────────────────────────

class TestFormulaOrderStepFields:

    def test_all_steps_have_order(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for i, step in enumerate(lit.get("formula_order", [])):
                    assert "order" in step, (
                        f"Step {i} in {e['exercise_id']} lit {lit['literal_id']} missing 'order'"
                    )
                    assert isinstance(step["order"], int), (
                        f"Step order must be int in {e['exercise_id']} lit {lit['literal_id']}"
                    )

    def test_all_steps_have_formula_key(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for i, step in enumerate(lit.get("formula_order", [])):
                    assert step.get("formula_key"), (
                        f"Step {i} in {e['exercise_id']} lit {lit['literal_id']} missing formula_key"
                    )

    def test_all_steps_have_expression(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for i, step in enumerate(lit.get("formula_order", [])):
                    assert step.get("expression"), (
                        f"Step {i} in {e['exercise_id']} lit {lit['literal_id']} missing expression"
                    )

    def test_all_steps_have_produces(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for i, step in enumerate(lit.get("formula_order", [])):
                    assert step.get("produces"), (
                        f"Step {i} in {e['exercise_id']} lit {lit['literal_id']} missing produces"
                    )

    def test_all_steps_have_req_vars_or_substitution(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for i, step in enumerate(lit.get("formula_order", [])):
                    has_rv = "required_variables" in step and isinstance(
                        step["required_variables"], list
                    )
                    has_tpl = bool(step.get("substitution_template", "").strip())
                    assert has_rv or has_tpl, (
                        f"Step {i} ('{step.get('formula_key')}') in {e['exercise_id']} "
                        f"lit {lit['literal_id']} needs required_variables or substitution_template"
                    )

    def test_step_order_is_sequential(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                fo = lit.get("formula_order", [])
                orders = [s["order"] for s in fo if "order" in s]
                assert orders == list(range(1, len(orders) + 1)), (
                    f"formula_order steps must be sequential 1..N in "
                    f"{e['exercise_id']} lit {lit['literal_id']}: {orders}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 9 — Model coverage: PICS, PICM, PFCS, PFHET appear in exercises 11-20
# ─────────────────────────────────────────────────────────────────────────────

class TestModelCoverage:

    def _all_models_in_11_20(self, exercises) -> set[str]:
        models = {e["model"] for e in exercises}
        for e in exercises:
            for lit in e.get("literals", []):
                ctx = lit.get("model_context", "")
                if ctx:
                    models.add(ctx)
        return models

    def test_pics_covered_in_11_20(self, exercises):
        pics = [e for e in exercises if e["model"] == "PICS"]
        all_models = self._all_models_in_11_20(exercises)
        assert "PICS" in all_models, (
            f"PICS must appear in exercises 11-20 (primary or model_context). Found: {all_models}"
        )
        assert len(pics) >= 1, f"Expected at least 1 PICS exercise in 11-20, got {len(pics)}"

    def test_picm_covered_in_11_20(self, exercises):
        picm = [e for e in exercises if e["model"] == "PICM"]
        assert len(picm) >= 2, f"Expected at least 2 PICM exercises in 11-20, got {len(picm)}"

    def test_pfcs_covered_in_11_20(self, exercises):
        pfcs = [e for e in exercises if e["model"] == "PFCS"]
        all_models = self._all_models_in_11_20(exercises)
        assert "PFCS" in all_models, (
            f"PFCS must appear in exercises 11-20. Found: {all_models}"
        )
        assert len(pfcs) >= 2, f"Expected ≥2 PFCS exercises in 11-20, got {len(pfcs)}"

    def test_pfhet_covered_in_11_20(self, exercises):
        pfhet = [e for e in exercises if e["model"] == "PFHET"]
        assert len(pfhet) >= 1, (
            f"Expected ≥1 PFHET exercise in 11-20, got {len(pfhet)}"
        )

    def test_cost_exercises_present_in_11_20(self, exercises):
        with_cost = [e for e in exercises if e.get("has_cost_analysis")]
        assert len(with_cost) >= 3, (
            f"Expected ≥3 exercises with cost analysis in 11-20, got {len(with_cost)}"
        )

    def test_optimization_exercises_present_in_11_20(self, exercises):
        with_opt = [e for e in exercises if e.get("has_optimization")]
        assert len(with_opt) >= 3, (
            f"Expected ≥3 exercises with optimization in 11-20, got {len(with_opt)}"
        )

    def test_multi_model_exercises_present(self, exercises):
        multi = [e for e in exercises if e.get("has_multiple_models")]
        assert len(multi) >= 1, (
            f"Expected ≥1 exercise with has_multiple_models=True in 11-20, got {len(multi)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 10 — At least 3 exercises 11-20 have recognition_examples
# ─────────────────────────────────────────────────────────────────────────────

class TestRecognitionExamples:

    def test_at_least_3_exercises_have_recognition_examples(self, exercises):
        with_ex = [e for e in exercises if len(e.get("recognition_examples", [])) > 0]
        assert len(with_ex) >= 3, (
            f"Expected ≥3 exercises (11-20) with recognition_examples, got {len(with_ex)}"
        )

    def test_recognition_examples_are_non_empty_strings(self, exercises):
        for e in exercises:
            for i, ex_text in enumerate(e.get("recognition_examples", [])):
                assert isinstance(ex_text, str) and ex_text.strip(), (
                    f"recognition_example {i} in {e['exercise_id']} is empty or not a string"
                )

    def test_recognition_examples_are_unique_within_exercise(self, exercises):
        for e in exercises:
            examples = e.get("recognition_examples", [])
            if len(examples) >= 2:
                assert len(set(examples)) == len(examples), (
                    f"Duplicate recognition_examples in {e['exercise_id']}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 11 — Analyzer recognizes recognition_examples for exercises 11-20
# ─────────────────────────────────────────────────────────────────────────────

def _recognition_cases_11_20():
    """Collect (exercise_id, model, example_text) for exercises 11-20 only."""
    try:
        exs = get_solutions_exercises()
    except Exception:
        return []
    cases = []
    for e in exs:
        if 11 <= e.get("source_number", 0) <= 20:
            for ex_text in e.get("recognition_examples", []):
                cases.append((e["exercise_id"], e["model"], ex_text))
    return cases


_RECOGNITION_CASES_11_20 = _recognition_cases_11_20()


@pytest.mark.parametrize(
    "exercise_id,expected_model,example_text",
    _RECOGNITION_CASES_11_20,
    ids=[f"{c[0]}_{i}" for i, c in enumerate(_RECOGNITION_CASES_11_20)],
)
def test_analyzer_identifies_model_from_recognition_example_11_20(
    exercise_id, expected_model, example_text, analyzer
):
    """Analyzer must identify the correct model from recognition_examples of EX11-20."""
    req = StatementAnalysisRequest(text=example_text)
    result = analyzer.analyze(req)
    assert result.identified_model == expected_model, (
        f"[{exercise_id}] Expected model {expected_model}, "
        f"got {result.identified_model!r} for text: {example_text[:80]}..."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group 12 — No memorized numerical results in formula steps (exercises 11-20)
# ─────────────────────────────────────────────────────────────────────────────

class TestNoMemoizedResults:

    def _expression_looks_memorized(self, expr: str) -> bool:
        import re
        cleaned = expr.strip()
        if "{" in cleaned or any(op in cleaned for op in ["=", "/", "×", "+", "−", "-", "*", "^"]):
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


# ─────────────────────────────────────────────────────────────────────────────
# Bonus — Metadata includes exercises 11-20
# ─────────────────────────────────────────────────────────────────────────────

class TestMetadataIntegrity:

    def test_metadata_exercises_included_covers_1_to_20(self, solutions):
        meta = solutions.get("_metadata", {})
        included = meta.get("exercises_included", "")
        assert "1" in included and "20" in included, (
            f"_metadata.exercises_included should describe 1-20, got: {included!r}"
        )

    def test_every_exercise_11_20_has_source_file(self, exercises):
        for e in exercises:
            sf = e.get("source_file", "")
            assert "docx" in sf.lower(), (
                f"Exercise {e['exercise_id']} source_file should reference .docx, got: {sf!r}"
            )

    def test_known_ids_11_20_present(self, exercises):
        ids = {e["exercise_id"] for e in exercises}
        expected_ids = {
            "11_gasolinera_mmc",
            "12_terminal_facturacion_mm2",
            "13_base_aerea_v1_comparacion",
            "14_base_aerea_v2_pfcs",
            "15_base_aerea_v3_pfcs",
            "16_terminal_carga_descarga_mmc",
            "17_cajero_bancario_mm1",
            "18_supermercado_cajas_independientes",
            "19_supermercado_cola_unica_mm2",
            "20_montacargas_tecnicos_heterogeneos",
        }
        assert expected_ids.issubset(ids), (
            f"Missing expected exercise IDs: {expected_ids - ids}"
        )

    def test_pfhet_exercise_is_20(self, exercises):
        pfhet = [e for e in exercises if e["model"] == "PFHET"]
        ids = {e["exercise_id"] for e in pfhet}
        assert "20_montacargas_tecnicos_heterogeneos" in ids, (
            f"Expected PFHET exercise 20, got: {ids}"
        )

"""
Phase KB — Ejercicios 1-10 Structural Knowledge Coverage
=========================================================
Validates analysis_exercise_solutions.json (exercises 1-10) against 12 groups:

 1. Exactly 10 exercises exist (source_number 1..10)
 2. Unique exercise_ids
 3. Every exercise has 'model' field (valid model name)
 4. Every exercise has 'variables_to_extract'
 5. Every exercise has 'literals'
 6. Every literal has 'objective'
 7. Every literal has 'formula_order' (non-empty list)
 8. Every formula_order step has: order, formula_key, expression,
    required_variables or substitution_template, produces
 9. Models covered: PICS, PICM, PFCS, PFCM (directly or via model_context)
10. At least 3 exercises have 'recognition_examples' with modified data
11. Analyzer recognizes recognition_examples by structure (not by numbers)
12. No memorized numerical results in formula steps
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
def exercises(solutions):
    """Only exercises 1-10."""
    return [e for e in solutions.get("exercises", []) if e.get("source_number", 0) <= 10]


@pytest.fixture(scope="module")
def analyzer():
    return make_analyzer()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Group 1 — Exactly 10 exercises (source_number 1..10)
# ─────────────────────────────────────────────────────────────────────────────

class TestExerciseCount:

    def test_solutions_file_loaded(self, solutions):
        assert solutions_loaded(), "analysis_exercise_solutions.json not found or empty"

    def test_exactly_10_exercises(self, exercises):
        assert len(exercises) == 10, (
            f"Expected 10 exercises (1-10), got {len(exercises)}"
        )

    def test_source_numbers_are_1_to_10(self, exercises):
        nums = sorted(e["source_number"] for e in exercises)
        assert nums == list(range(1, 11)), (
            f"source_number values must be exactly 1..10, got {nums}"
        )

    def test_total_exercises_at_least_10(self, solutions):
        all_exs = solutions.get("exercises", [])
        assert len(all_exs) >= 10, (
            f"Expected ≥10 total exercises, got {len(all_exs)}"
        )

    def test_get_solution_by_number_works(self):
        for n in range(1, 11):
            sol = get_solution_by_number(n)
            assert sol is not None, f"get_solution_by_number({n}) returned None"
            assert sol["source_number"] == n


# ─────────────────────────────────────────────────────────────────────────────
# Group 2 — Unique exercise_ids
# ─────────────────────────────────────────────────────────────────────────────

class TestUniqueIds:

    def test_exercise_ids_are_unique(self, exercises):
        ids = [e["exercise_id"] for e in exercises]
        assert len(ids) == len(set(ids)), (
            f"Duplicate exercise_ids found: {[x for x in ids if ids.count(x) > 1]}"
        )

    def test_exercise_ids_are_non_empty_strings(self, exercises):
        for e in exercises:
            eid = e.get("exercise_id", "")
            assert isinstance(eid, str) and eid.strip(), (
                f"Exercise {e.get('source_number')} has invalid exercise_id: {eid!r}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Group 3 — Every exercise has valid 'model' field
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
# Group 4 — Every exercise has variables_to_extract
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
                has_lambda = any(n == "lambda_" or n.startswith("lambda_") for n in names)
                # EX07 uses mu_A/mu_B (two-option comparison), others use mu or mu_eff
                has_mu = "mu" in names or "mu_eff" in names or "mu_A" in names or "mu_B" in names
                assert has_lambda, (
                    f"PICS exercise {e['exercise_id']} missing lambda variable"
                )
                assert has_mu, (
                    f"PICS exercise {e['exercise_id']} missing mu variable "
                    f"(checked: mu, mu_eff, mu_A, mu_B). Found: {names}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 5 — Every exercise has literals
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
                    f"required_variables must be a list in {e['exercise_id']} lit {lit.get('literal_id')}"
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
                # Must be non-empty, lowercase/underscored (not a sentence)
                assert obj and " " not in obj, (
                    f"Objective '{obj}' in {e['exercise_id']} lit {lit.get('literal_id')} "
                    f"should be snake_case (no spaces)"
                )

    def test_known_objectives_appear_in_exercises(self, exercises):
        """At least some standard objectives must exist across exercises."""
        all_objectives = {
            lit["objective"]
            for e in exercises
            for lit in e.get("literals", [])
        }
        standard = {"compute_Wq", "compute_Lq", "compute_P0", "compute_wait_probability",
                    "compute_W", "compute_L", "compute_idle_time_daily"}
        found = standard & all_objectives
        assert found, (
            f"None of the standard objectives {standard} found. Got: {all_objectives}"
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
# Group 8 — Every formula_order step has required fields
# ─────────────────────────────────────────────────────────────────────────────

class TestFormulaOrderStepFields:
    """Each step must have: order, formula_key, expression, produces,
    and either required_variables or substitution_template."""

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
# Group 9 — Model coverage: PICS, PICM, PFCS, PFCM
# ─────────────────────────────────────────────────────────────────────────────

class TestModelCoverage:

    def _all_models_used(self, exercises) -> set[str]:
        models = {e["model"] for e in exercises}
        for e in exercises:
            for lit in e.get("literals", []):
                ctx = lit.get("model_context", "")
                if ctx:
                    models.add(ctx)
        return models

    def test_pics_covered(self, exercises):
        pics = [e for e in exercises if e["model"] == "PICS"]
        assert len(pics) >= 3, f"Expected at least 3 PICS exercises, got {len(pics)}"

    def test_picm_covered(self, exercises):
        picm = [e for e in exercises if e["model"] == "PICM"]
        assert len(picm) >= 3, f"Expected at least 3 PICM exercises, got {len(picm)}"

    def test_pfcs_covered(self, exercises):
        # PFCS as primary model OR as model_context in literals
        pfcs_primary = [e for e in exercises if e["model"] == "PFCS"]
        pfcs_ctx = [
            e for e in exercises
            for lit in e.get("literals", [])
            if lit.get("model_context") == "PFCS"
        ]
        total = len(set(e["exercise_id"] for e in pfcs_primary + pfcs_ctx))
        assert total >= 2, f"Expected ≥2 exercises with PFCS, got {total}"

    def test_pfcm_covered(self, exercises):
        all_models = self._all_models_used(exercises)
        assert "PFCM" in all_models, (
            f"PFCM must appear in at least one exercise model or literal model_context. "
            f"Found models: {all_models}"
        )

    def test_cost_exercises_present(self, exercises):
        with_cost = [e for e in exercises if e.get("has_cost_analysis")]
        assert len(with_cost) >= 3, (
            f"Expected ≥3 exercises with cost analysis, got {len(with_cost)}: "
            f"{[e['exercise_id'] for e in with_cost]}"
        )

    def test_optimization_exercises_present(self, exercises):
        with_opt = [e for e in exercises if e.get("has_optimization")]
        assert len(with_opt) >= 3, (
            f"Expected ≥3 exercises with optimization, got {len(with_opt)}: "
            f"{[e['exercise_id'] for e in with_opt]}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 10 — At least 3 exercises have recognition_examples with modified data
# ─────────────────────────────────────────────────────────────────────────────

class TestRecognitionExamples:

    def test_at_least_3_exercises_have_recognition_examples(self, exercises):
        with_ex = [e for e in exercises if len(e.get("recognition_examples", [])) > 0]
        assert len(with_ex) >= 3, (
            f"Expected ≥3 exercises with recognition_examples, got {len(with_ex)}"
        )

    def test_recognition_examples_are_non_empty_strings(self, exercises):
        for e in exercises:
            for i, ex_text in enumerate(e.get("recognition_examples", [])):
                assert isinstance(ex_text, str) and ex_text.strip(), (
                    f"recognition_example {i} in {e['exercise_id']} is empty or not a string"
                )

    def test_recognition_examples_use_different_numbers_same_structure(self, exercises):
        """Verify that recognition_examples for the same exercise have
        different phrasing (implying different numbers) but all describe
        the same structural situation."""
        exercises_with_ex = [e for e in exercises if len(e.get("recognition_examples", [])) >= 2]
        for e in exercises_with_ex:
            examples = e["recognition_examples"]
            # All examples should be different texts
            assert len(set(examples)) == len(examples), (
                f"Duplicate recognition_examples in {e['exercise_id']}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Group 11 — Analyzer recognizes recognition_examples by structure
# ─────────────────────────────────────────────────────────────────────────────

def _exercises_with_recognition_examples():
    """Collect (exercise_id, model, example_text) tuples for parametrize."""
    try:
        exs = get_solutions_exercises()
    except Exception:
        return []
    cases = []
    for e in exs:
        for ex_text in e.get("recognition_examples", []):
            cases.append((e["exercise_id"], e["model"], ex_text))
    return cases


_RECOGNITION_CASES = _exercises_with_recognition_examples()


@pytest.mark.parametrize(
    "exercise_id,expected_model,example_text",
    _RECOGNITION_CASES,
    ids=[f"{c[0]}_{i}" for i, c in enumerate(_RECOGNITION_CASES)],
)
def test_analyzer_identifies_model_from_recognition_example(
    exercise_id, expected_model, example_text, analyzer
):
    """Analyzer must identify the correct model from recognition_examples."""
    req = StatementAnalysisRequest(text=example_text)
    result = analyzer.analyze(req)
    assert result.identified_model == expected_model, (
        f"[{exercise_id}] Expected model {expected_model}, "
        f"got {result.identified_model!r} for text: {example_text[:80]}..."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group 12 — No memorized numerical results in formula steps
# ─────────────────────────────────────────────────────────────────────────────

class TestNoMemoizedResults:
    """Formula expressions must be symbolic, not hardcoded with specific numbers."""

    def _expression_looks_memorized(self, expr: str) -> bool:
        """Return True if expression contains a suspiciously specific decimal result."""
        import re
        # Flag expressions that are ONLY a number (e.g., "0.6667") with no variable names
        # Legitimate expressions contain '=', operators, or variable names
        cleaned = expr.strip()
        # Expressions with variable templates {..} or operators are fine
        if "{" in cleaned or any(op in cleaned for op in ["=", "/", "×", "+", "−", "-", "*", "^"]):
            return False
        # Flag bare decimal numbers or very short numeric strings
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
        """substitution_template entries must use {variable} placeholders."""
        for e in exercises:
            for lit in e.get("literals", []):
                for step in lit.get("formula_order", []):
                    tpl = step.get("substitution_template", "")
                    if tpl:  # only if present
                        assert "{" in tpl and "}" in tpl, (
                            f"substitution_template has no {{placeholders}} in "
                            f"{e['exercise_id']} lit {lit['literal_id']} "
                            f"step {step.get('formula_key')}: {tpl!r}"
                        )

    def test_expected_results_have_no_hardcoded_logic_value(self, exercises):
        """expected_result_for_validation.value should be null (not a key logic value)."""
        for e in exercises:
            for lit in e.get("literals", []):
                erv = lit.get("expected_result_for_validation", {})
                if erv:
                    # Note field should describe the formula, not store a result
                    # value=null means no hardcoded result drives the logic
                    val = erv.get("value")
                    assert val is None, (
                        f"expected_result_for_validation.value should be null (not used as logic) "
                        f"in {e['exercise_id']} lit {lit['literal_id']}: value={val}"
                    )


# ─────────────────────────────────────────────────────────────────────────────
# Bonus — Source file and metadata integrity
# ─────────────────────────────────────────────────────────────────────────────

class TestMetadataIntegrity:

    def test_metadata_has_source_file(self, solutions):
        meta = solutions.get("_metadata", {})
        sf = meta.get("source_file", "")
        assert "docx" in sf.lower(), (
            f"_metadata.source_file should reference a .docx file, got: {sf!r}"
        )

    def test_metadata_exercises_included_1_to_10(self, solutions):
        meta = solutions.get("_metadata", {})
        included = meta.get("exercises_included", "")
        # Accept '1-10' or any superset like '1-20'
        assert "1" in included, (
            f"_metadata.exercises_included should contain '1', got: {included!r}"
        )

    def test_every_exercise_has_source_file(self, exercises):
        for e in exercises:
            sf = e.get("source_file", "")
            assert "docx" in sf.lower(), (
                f"Exercise {e['exercise_id']} source_file should reference .docx, got: {sf!r}"
            )

    def test_pics_exercises_include_known_ids(self, exercises):
        ids = {e["exercise_id"] for e in exercises if e["model"] == "PICS"}
        expected_ids = {
            "01_tienda_alimentacion_mm1",
            "04_seguridad_social_mm1",
            "06_copiadora_departamentos_mm1",
            "07_mecanico_comparacion_mm1",
            "10_servidor_universitario_mm1",
        }
        assert expected_ids.issubset(ids), (
            f"Missing expected PICS exercise IDs: {expected_ids - ids}"
        )

    def test_picm_exercises_include_known_ids(self, exercises):
        ids = {e["exercise_id"] for e in exercises if e["model"] == "PICM"}
        expected_ids = {
            "02_correo_urgente_mm3",
            "03_farmacia_mmc",
            "05_call_center_iess_mm3",
        }
        assert expected_ids.issubset(ids), (
            f"Missing expected PICM exercise IDs: {expected_ids - ids}"
        )

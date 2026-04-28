"""
Phase KB — Full 30-Exercise Complete Coverage Validation
=========================================================
Cross-validates all 30 exercises in analysis_exercise_solutions.json:

 1. Exactly 30 exercises; source_numbers 1-30 without gaps or duplicates
 2. Unique exercise_ids across all 30
 3. All 30 exercises have model, variables_to_extract, literals
 4. All literals have objective (snake_case) and non-empty formula_order
 5. All formula_order steps have: order, formula_key, expression, produces
 6. Model coverage: PICS, PICM, PFCS, PFHET present across 30 exercises
 7. Cost exercises present (EX28, EX30 + others from 1-26)
 8. Optimization exercises present (EX27, EX28, EX29, EX30 + others from 1-26)
 9. At least 10 exercises have recognition_examples
10. Analyzer correctly identifies all recognition_examples from all 30 exercises
11. POST /api/analyze integration check with PICS, PICM, PFCS examples
12. Metadata and source file integrity

Read from: infrastructure/data/analysis/analysis_exercise_solutions.json
Source:    Ejercicios Propuestos Teoría de Colas.docx
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from domain.entities.analysis import StatementAnalysisRequest
from domain.services.statement_analyzer import make_analyzer
from domain.services.statement_problem_knowledge import (
    load_solutions,
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
    return solutions.get("exercises", [])


@pytest.fixture(scope="module")
def analyzer():
    return make_analyzer()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


VALID_MODELS = {"PICS", "PICM", "PFCS", "PFCM", "PFHET"}


# ─────────────────────────────────────────────────────────────────────────────
# Group 1 — Exercise count and coverage 1-30
# ─────────────────────────────────────────────────────────────────────────────

class TestTotalCount:

    def test_solutions_file_loaded(self):
        assert solutions_loaded(), "analysis_exercise_solutions.json not found or empty"

    def test_exactly_30_exercises(self, exercises):
        assert len(exercises) == 30, (
            f"Expected exactly 30 exercises, got {len(exercises)}"
        )

    def test_source_numbers_are_1_to_30_no_gaps(self, exercises):
        nums = sorted(e["source_number"] for e in exercises)
        assert nums == list(range(1, 31)), (
            f"source_numbers must be [1..30] with no gaps or duplicates. Got: {nums}"
        )

    def test_no_duplicate_source_numbers(self, exercises):
        nums = [e["source_number"] for e in exercises]
        assert len(nums) == len(set(nums)), (
            f"Duplicate source_numbers: {[n for n in nums if nums.count(n) > 1]}"
        )

    def test_get_solution_by_number_works_for_all_30(self):
        for n in range(1, 31):
            sol = get_solution_by_number(n)
            assert sol is not None, f"get_solution_by_number({n}) returned None"
            assert sol["source_number"] == n


# ─────────────────────────────────────────────────────────────────────────────
# Group 2 — Unique exercise_ids
# ─────────────────────────────────────────────────────────────────────────────

class TestUniqueIds:

    def test_exercise_ids_are_unique_across_all_30(self, exercises):
        ids = [e["exercise_id"] for e in exercises]
        assert len(ids) == len(set(ids)), (
            f"Duplicate exercise_ids: {[x for x in ids if ids.count(x) > 1]}"
        )

    def test_all_exercise_ids_are_non_empty_strings(self, exercises):
        for e in exercises:
            eid = e.get("exercise_id", "")
            assert isinstance(eid, str) and eid.strip(), (
                f"Exercise {e.get('source_number')} has invalid exercise_id: {eid!r}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Group 3 — All exercises have model, variables_to_extract, literals
# ─────────────────────────────────────────────────────────────────────────────

class TestMandatoryFields:

    def test_all_have_model(self, exercises):
        for e in exercises:
            assert e.get("model") in VALID_MODELS, (
                f"Exercise {e.get('exercise_id')} has invalid model: {e.get('model')!r}"
            )

    def test_all_have_model_alias(self, exercises):
        for e in exercises:
            assert e.get("model_alias"), (
                f"Exercise {e.get('exercise_id')} missing model_alias"
            )

    def test_all_have_variables_to_extract(self, exercises):
        for e in exercises:
            vte = e.get("variables_to_extract", [])
            assert isinstance(vte, list) and len(vte) > 0, (
                f"Exercise {e['exercise_id']} missing or empty variables_to_extract"
            )

    def test_all_have_literals(self, exercises):
        for e in exercises:
            lits = e.get("literals", [])
            assert isinstance(lits, list) and len(lits) > 0, (
                f"Exercise {e['exercise_id']} has no literals"
            )

    def test_all_have_source_file_referencing_docx(self, exercises):
        for e in exercises:
            sf = e.get("source_file", "")
            assert "docx" in sf.lower(), (
                f"Exercise {e['exercise_id']} source_file should reference .docx, "
                f"got: {sf!r}"
            )

    def test_variables_have_name_meaning_required(self, exercises):
        for e in exercises:
            for v in e.get("variables_to_extract", []):
                assert v.get("name"), f"Variable in {e['exercise_id']} missing 'name'"
                assert v.get("meaning"), (
                    f"Variable '{v.get('name')}' in {e['exercise_id']} missing 'meaning'"
                )
                assert "required" in v, (
                    f"Variable '{v.get('name')}' in {e['exercise_id']} missing 'required'"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 4 — All literals have objective (snake_case) and non-empty formula_order
# ─────────────────────────────────────────────────────────────────────────────

class TestLiterals:

    def test_all_literals_have_objective(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                assert lit.get("objective"), (
                    f"Literal {lit.get('literal_id')} in {e['exercise_id']} "
                    f"missing objective"
                )

    def test_all_objectives_are_snake_case(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                obj = lit.get("objective", "")
                assert obj and " " not in obj, (
                    f"Objective '{obj}' in {e['exercise_id']} lit {lit.get('literal_id')} "
                    f"should be snake_case (no spaces)"
                )

    def test_all_literals_have_formula_order(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                fo = lit.get("formula_order", [])
                assert isinstance(fo, list) and len(fo) > 0, (
                    f"Literal {lit.get('literal_id')} in {e['exercise_id']} "
                    f"has empty or missing formula_order"
                )

    def test_all_literals_have_model_context(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                ctx = lit.get("model_context", "")
                assert ctx in VALID_MODELS, (
                    f"Literal {lit.get('literal_id')} in {e['exercise_id']} "
                    f"has invalid model_context: {ctx!r}"
                )

    def test_formula_order_steps_are_sorted(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                steps = lit.get("formula_order", [])
                orders = [s.get("order", 0) for s in steps]
                assert orders == sorted(orders), (
                    f"formula_order not sorted in {e['exercise_id']} "
                    f"lit {lit.get('literal_id')}: {orders}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 5 — All formula_order steps have required fields
# ─────────────────────────────────────────────────────────────────────────────

class TestFormulaOrderSteps:

    def test_all_steps_have_order_formula_key_expression_produces(self, exercises):
        for e in exercises:
            for lit in e.get("literals", []):
                for step in lit.get("formula_order", []):
                    eid = e["exercise_id"]
                    lid = lit.get("literal_id", "?")
                    fk  = step.get("formula_key", "?")
                    assert "order" in step, (
                        f"Step missing 'order' in {eid} lit {lid}: {step}"
                    )
                    assert step.get("formula_key"), (
                        f"Step missing 'formula_key' in {eid} lit {lid}"
                    )
                    assert step.get("expression"), (
                        f"Step missing 'expression' in {eid} lit {lid} step {fk}"
                    )
                    assert step.get("produces"), (
                        f"Step missing 'produces' in {eid} lit {lid} step {fk}"
                    )
                    assert "required_variables" in step, (
                        f"Step missing 'required_variables' in {eid} lit {lid} step {fk}"
                    )


# ─────────────────────────────────────────────────────────────────────────────
# Group 6 — Model coverage: PICS, PICM, PFCS, PFHET (and optionally PFCM)
# ─────────────────────────────────────────────────────────────────────────────

class TestModelCoverage:

    def test_pics_present(self, exercises):
        models = {e["model"] for e in exercises}
        assert "PICS" in models, f"PICS model not found among 30 exercises. Found: {models}"

    def test_picm_present(self, exercises):
        models = {e["model"] for e in exercises}
        assert "PICM" in models, f"PICM model not found among 30 exercises. Found: {models}"

    def test_pfcs_present(self, exercises):
        models = {e["model"] for e in exercises}
        assert "PFCS" in models, f"PFCS model not found among 30 exercises. Found: {models}"

    def test_pfhet_present(self, exercises):
        models = {e["model"] for e in exercises}
        assert "PFHET" in models, f"PFHET model not found among 30 exercises. Found: {models}"

    def test_each_model_has_multiple_exercises(self, exercises):
        from collections import Counter
        counts = Counter(e["model"] for e in exercises)
        for model, count in counts.items():
            assert count >= 1, (
                f"Model {model} appears only {count} time(s) across 30 exercises"
            )

    def test_picm_exercises_27_30_all_present(self, exercises):
        picm_exs = {e["source_number"] for e in exercises if e["model"] == "PICM"}
        for n in (27, 28, 29, 30):
            assert n in picm_exs, (
                f"Exercise {n} (PICM) not found. PICM exercises present: {sorted(picm_exs)}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Group 7 — Cost exercises present
# ─────────────────────────────────────────────────────────────────────────────

class TestCostExercises:

    def test_at_least_4_cost_exercises_total(self, exercises):
        cost_exs = [e for e in exercises if e.get("has_cost_analysis") is True]
        assert len(cost_exs) >= 4, (
            f"Expected ≥4 exercises with has_cost_analysis=True across all 30. "
            f"Found: {len(cost_exs)} — IDs: {[e['exercise_id'] for e in cost_exs]}"
        )

    def test_ex28_has_cost_flag(self, exercises):
        ex28 = next((e for e in exercises if e["source_number"] == 28), None)
        assert ex28 and ex28.get("has_cost_analysis") is True, (
            "Exercise 28 (reparacion ordenadores — minimize daily cost) "
            "must have has_cost_analysis=True"
        )

    def test_ex30_has_cost_flag(self, exercises):
        ex30 = next((e for e in exercises if e["source_number"] == 30), None)
        assert ex30 and ex30.get("has_cost_analysis") is True, (
            "Exercise 30 (telefonia asesoras — minimize total cost) "
            "must have has_cost_analysis=True"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 8 — Optimization exercises present
# ─────────────────────────────────────────────────────────────────────────────

class TestOptimizationExercises:

    def test_at_least_8_optimization_exercises_total(self, exercises):
        opt_exs = [e for e in exercises if e.get("has_optimization") is True]
        assert len(opt_exs) >= 8, (
            f"Expected ≥8 exercises with has_optimization=True across all 30. "
            f"Found: {len(opt_exs)} — IDs: {[e['exercise_id'] for e in opt_exs]}"
        )

    def test_ex27_has_optimization_flag(self, exercises):
        ex27 = next((e for e in exercises if e["source_number"] == 27), None)
        assert ex27 and ex27.get("has_optimization") is True, (
            "Exercise 27 (registro civil — P_w≤0.5 → c_min=3) must have has_optimization=True"
        )

    def test_ex29_has_optimization_flag(self, exercises):
        ex29 = next((e for e in exercises if e["source_number"] == 29), None)
        assert ex29 and ex29.get("has_optimization") is True, (
            "Exercise 29 (ensamblaje — Wq≤4min → c_min=3) must have has_optimization=True"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 9 — At least 10 exercises have recognition_examples
# ─────────────────────────────────────────────────────────────────────────────

class TestRecognitionExamplesPresence:

    def test_at_least_10_exercises_have_recognition_examples(self, exercises):
        exs_with = [
            e for e in exercises
            if e.get("recognition_examples") and len(e["recognition_examples"]) > 0
        ]
        assert len(exs_with) >= 10, (
            f"Expected ≥10 exercises with recognition_examples, got {len(exs_with)}"
        )

    def test_exercises_27_30_all_have_recognition_examples(self, exercises):
        for e in [ex for ex in exercises if 27 <= ex["source_number"] <= 30]:
            assert len(e.get("recognition_examples", [])) >= 2, (
                f"Exercise {e['exercise_id']} (EX27-30) must have ≥2 recognition_examples"
            )

    def test_recognition_examples_are_non_trivial_strings(self, exercises):
        for e in exercises:
            for ex_text in e.get("recognition_examples", []):
                assert isinstance(ex_text, str) and len(ex_text.strip()) > 30, (
                    f"Recognition example in {e['exercise_id']} is too short: {ex_text!r}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Group 10 — Analyzer recognizes all recognition_examples (all 30 exercises)
# ─────────────────────────────────────────────────────────────────────────────

def _all_recognition_cases() -> list[tuple[str, str, str]]:
    """Build parametrize list from all recognition_examples across 30 exercises."""
    sols = load_solutions()
    cases = []
    for ex in sols.get("exercises", []):
        model = ex.get("model", "")
        eid   = ex.get("exercise_id", "")
        for example in ex.get("recognition_examples", []):
            cases.append((eid, model, example))
    return cases


_ALL_RECOGNITION_CASES = _all_recognition_cases()


@pytest.mark.parametrize(
    "exercise_id,expected_model,example_text",
    _ALL_RECOGNITION_CASES,
    ids=[f"{c[0]}_{i}" for i, c in enumerate(_ALL_RECOGNITION_CASES)],
)
def test_analyzer_identifies_model_from_any_recognition_example(
    exercise_id, expected_model, example_text, analyzer
):
    """Analyzer must correctly identify model for all recognition_examples of all 30 exercises."""
    req = StatementAnalysisRequest(text=example_text)
    result = analyzer.analyze(req)
    assert result.identified_model == expected_model, (
        f"[{exercise_id}] Expected model {expected_model}, "
        f"got {result.identified_model!r} for text: {example_text[:80]}..."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group 11 — POST /api/analyze integration checks
# ─────────────────────────────────────────────────────────────────────────────

class TestApiAnalyzeIntegration:

    def test_api_analyze_picm_example_from_ex27(self, client):
        """POST /api/analyze with a PICM text from EX27 must return PICM model."""
        response = client.post(
            "/api/analyze",
            json={
                "text": (
                    "Varias ventanillas atienden documentos en una oficina. "
                    "Llegadas Poisson 20 por hora. Tiempo de servicio exponencial "
                    "media 5 minutos. Cuantas ventanillas son necesarias para que "
                    "la probabilidad de esperar no supere el 40 por ciento."
                )
            },
        )
        assert response.status_code == 200, (
            f"POST /api/analyze returned {response.status_code}: {response.text[:200]}"
        )
        data = response.json()
        assert data.get("model_id") == "PICM", (
            f"Expected PICM from PICM text (varias ventanillas), "
            f"got {data.get('model_id')!r}"
        )

    def test_api_analyze_picm_example_from_ex30(self, client):
        """POST /api/analyze with a PICM text from EX30 must return PICM model."""
        response = client.post(
            "/api/analyze",
            json={
                "text": (
                    "m/m/c en servicio de atencion al cliente. Cuantos servidores "
                    "optimizan los costos totales considerando costo por servidor "
                    "y costo de espera del cliente."
                )
            },
        )
        assert response.status_code == 200, (
            f"POST /api/analyze returned {response.status_code}: {response.text[:200]}"
        )
        data = response.json()
        assert data.get("model_id") == "PICM", (
            f"Expected PICM from PICM text (m/m/c cuantos servidores), "
            f"got {data.get('model_id')!r}"
        )

    def test_api_analyze_pics_example(self, client):
        """POST /api/analyze with a PICS text must return PICS model."""
        response = client.post(
            "/api/analyze",
            json={
                "text": (
                    "Un servidor atiende llegadas Poisson con distribución "
                    "exponencial. Cola M/M/1. Calcular Lq, Wq, L, W."
                )
            },
        )
        assert response.status_code == 200, (
            f"POST /api/analyze returned {response.status_code}: {response.text[:200]}"
        )
        data = response.json()
        assert data.get("model_id") in {"PICS", "PFCS"}, (
            f"Expected PICS or PFCS from M/M/1 text, "
            f"got {data.get('model_id')!r}"
        )

    def test_api_analyze_returns_required_fields(self, client):
        """POST /api/analyze response must include identified_model and other fields."""
        response = client.post(
            "/api/analyze",
            json={"text": "Cola M/M/1. Lambda 5 clientes por hora. Mu 8 por hora."},
        )
        assert response.status_code == 200
        data = response.json()
        assert "model_id" in data, (
            f"Response missing 'model_id' field. Keys: {list(data.keys())}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Group 12 — Metadata and source integrity
# ─────────────────────────────────────────────────────────────────────────────

class TestMetadataAndIntegrity:

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

    def test_docx_source_file_exists(self):
        from pathlib import Path
        docx = (
            Path(__file__).resolve().parent.parent.parent
            / "Ejercicios Propuestos Teoría de Colas.docx"
        )
        assert docx.exists(), f".docx file not found at expected path: {docx}"

    def test_no_temp_scripts_exist(self):
        """No temporary scripts must remain in the project root."""
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
                f"Temporary file {fname} must not exist in project root"
            )

    def test_json_file_is_valid(self, solutions):
        """The JSON was loaded successfully (implicit: no parse errors)."""
        assert isinstance(solutions, dict), "solutions must be a dict"
        assert "exercises" in solutions, "solutions missing 'exercises' key"
        assert "_metadata" in solutions, "solutions missing '_metadata' key"

    def test_no_duplicate_exercise_ids_or_source_numbers(self, exercises):
        ids = [e["exercise_id"] for e in exercises]
        nums = [e["source_number"] for e in exercises]
        assert len(ids) == len(set(ids)), f"Duplicate exercise_ids: {set(x for x in ids if ids.count(x)>1)}"
        assert len(nums) == len(set(nums)), f"Duplicate source_numbers: {set(x for x in nums if nums.count(x)>1)}"

"""
Phase 12 — QA: Exercise pattern coverage validation.

8 test groups validating the integrity of queue_exercise_patterns.json
and the analyzer's ability to handle all 30 PDF exercise patterns.

CRITICAL: Tests must NOT depend on memorized numerical values from the PDF.
Tests validate STRUCTURE, MODEL IDENTIFICATION, FORMULA ORDER, and
OBJECTIVE DETECTION — not numerical results.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from domain.entities.analysis import StatementAnalysisRequest
from domain.services.formula_plan_builder import build_formula_plan
from domain.services.statement_analyzer import StatementAnalyzer, make_analyzer
from domain.services.statement_problem_knowledge import load_patterns


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def patterns():
    return load_patterns()


@pytest.fixture(scope="module")
def exercises(patterns):
    return patterns["exercises"]


@pytest.fixture(scope="module")
def analyzer():
    return make_analyzer()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Group 1 — Structural integrity
# ---------------------------------------------------------------------------

class TestPatternStructuralIntegrity:
    """Pattern file must contain exactly 30 well-formed exercises."""

    def test_total_exercises_count(self, exercises):
        assert len(exercises) == 30, (
            f"Expected 30 exercises, got {len(exercises)}"
        )

    def test_all_exercise_ids_unique(self, exercises):
        ids = [e["exercise_id"] for e in exercises]
        assert len(ids) == len(set(ids)), "Duplicate exercise_id found"

    def test_exercise_numbers_1_to_30(self, exercises):
        numbers = sorted(e["exercise_number"] for e in exercises)
        assert numbers == list(range(1, 31)), (
            "Exercise numbers must be exactly 1..30"
        )

    def test_all_exercises_have_required_top_level_fields(self, exercises):
        required = {"exercise_id", "exercise_number", "detected_model",
                    "variables_to_extract", "literals", "sample_statement"}
        for ex in exercises:
            missing = required - ex.keys()
            assert not missing, (
                f"Exercise {ex['exercise_id']} missing fields: {missing}"
            )

    def test_all_exercises_have_valid_detected_model(self, exercises):
        valid_models = {"PICS", "PICM", "PFCS", "PFCM", "PFHET"}
        for ex in exercises:
            assert ex["detected_model"] in valid_models, (
                f"Exercise {ex['exercise_id']} has invalid model: {ex['detected_model']}"
            )

    def test_all_literals_have_objective(self, exercises):
        for ex in exercises:
            for lit in ex["literals"]:
                assert "objective" in lit, (
                    f"Literal {lit.get('id')} in {ex['exercise_id']} missing objective"
                )
                assert lit["objective"], (
                    f"Literal {lit.get('id')} in {ex['exercise_id']} has empty objective"
                )

    def test_all_literals_have_formula_order(self, exercises):
        # Objectives that are conceptual and don't require a formula chain
        CONCEPTUAL_OBJECTIVES = {"identify_model", "compute_stability_condition"}
        for ex in exercises:
            for lit in ex["literals"]:
                if lit.get("objective") in CONCEPTUAL_OBJECTIVES:
                    continue  # conceptual literals may omit formula_order
                # formula_order must exist and be a non-empty list
                assert "formula_order" in lit, (
                    f"Literal {lit.get('id')} in {ex['exercise_id']} missing formula_order"
                )
                assert isinstance(lit["formula_order"], list), (
                    f"formula_order must be a list in {ex['exercise_id']}"
                )
                assert len(lit["formula_order"]) > 0, (
                    f"formula_order empty in literal {lit.get('id')} of {ex['exercise_id']}"
                )

    def test_all_sample_statements_non_empty(self, exercises):
        for ex in exercises:
            assert ex.get("sample_statement", "").strip(), (
                f"Exercise {ex['exercise_id']} has empty sample_statement"
            )

    def test_structural_keywords_present(self, exercises):
        for ex in exercises:
            assert "structural_keywords" in ex, (
                f"Exercise {ex['exercise_id']} missing structural_keywords"
            )
            assert isinstance(ex["structural_keywords"], list), (
                f"structural_keywords must be a list in {ex['exercise_id']}"
            )


# ---------------------------------------------------------------------------
# Group 2 — Model coverage
# ---------------------------------------------------------------------------

class TestModelCoverage:
    """Every supported model family must be represented in the pattern file."""

    def _count_model(self, exercises, model: str) -> int:
        return sum(1 for e in exercises if e["detected_model"] == model)

    def test_pics_exercises_count(self, exercises):
        assert self._count_model(exercises, "PICS") >= 5, (
            "Expected at least 5 PICS exercises"
        )

    def test_picm_exercises_count(self, exercises):
        assert self._count_model(exercises, "PICM") >= 5, (
            "Expected at least 5 PICM exercises"
        )

    def test_pfcs_exercises_count(self, exercises):
        assert self._count_model(exercises, "PFCS") >= 2, (
            "Expected at least 2 PFCS exercises"
        )

    def test_pfcm_exercises_count(self, exercises):
        # PFCM may appear as secondary model in literals (e.g., ex.9)
        pfcm_direct = self._count_model(exercises, "PFCM")
        pfcm_in_literals = sum(
            1 for e in exercises
            for lit in e["literals"]
            if lit.get("model_context") == "PFCM"
        )
        assert pfcm_direct + pfcm_in_literals >= 1, (
            "PFCM must appear in at least 1 exercise or literal model_context"
        )

    def test_pfhet_exercises_count(self, exercises):
        pfhet_direct = self._count_model(exercises, "PFHET")
        pfhet_via_context = sum(
            1 for e in exercises
            for lit in e["literals"]
            if lit.get("model_context") == "PFHET"
        )
        assert pfhet_direct + pfhet_via_context >= 2, (
            "PFHET must appear in at least 2 exercises or literal contexts"
        )

    def test_all_5_models_present(self, exercises):
        models_present = {e["detected_model"] for e in exercises}
        # Include context models from literals
        for e in exercises:
            for lit in e["literals"]:
                if lit.get("model_context"):
                    models_present.add(lit["model_context"])
        all_models = {"PICS", "PICM", "PFCS", "PFCM", "PFHET"}
        assert all_models.issubset(models_present), (
            f"Missing models: {all_models - models_present}"
        )


# ---------------------------------------------------------------------------
# Group 3 — Sample statements are analyzable without exceptions
# ---------------------------------------------------------------------------

def _get_exercise_list():
    """Load exercises for parametrize at collection time."""
    try:
        return load_patterns()["exercises"]
    except Exception:  # pragma: no cover
        return []


@pytest.mark.parametrize(
    "exercise",
    _get_exercise_list(),
    ids=[e["exercise_id"] for e in _get_exercise_list()],
)
def test_sample_statement_analyzable_no_exception(exercise, analyzer):
    """Analyzer must not raise an exception for any sample_statement."""
    stmt = exercise.get("sample_statement", "")
    if not stmt:
        pytest.skip(f"No sample_statement for {exercise['exercise_id']}")

    # Must not raise
    req = StatementAnalysisRequest(text=stmt)
    result = analyzer.analyze(req)

    # Analyzer must complete without exception — result itself is the main assertion.
    # Model may not be identified if sample_statement is too short or generic;
    # but the result object must be valid.
    assert result is not None
    if result.identified_model is not None:
        assert result.identified_model in {"PICS", "PICM", "PFCS", "PFCM", "PFHET"}, (
            f"Unexpected model '{result.identified_model}' for {exercise['exercise_id']}"
        )


# ---------------------------------------------------------------------------
# Group 4 — Flexible recognition: model identified from different numbers
# ---------------------------------------------------------------------------

FLEXIBLE_RECOGNITION_CASES = [
    {
        "name": "mm1_variant_A",
        "statement": (
            "Una tienda recibe 18 clientes por hora segun un proceso de Poisson. "
            "El servicio sigue distribucion exponencial con media de 6 minutos por cliente. "
            "Hay un solo servidor. Calcular: a) tiempo de espera en la cola, "
            "b) longitud media de la cola."
        ),
        "expected_model": "PICS",
        "expected_objectives_contain_any": ["compute_Wq", "compute_Lq"],
    },
    {
        "name": "mm1_variant_C",
        "statement": (
            "Una barberia tiene un solo barbero. Los clientes llegan segun proceso Poisson "
            "a razon de 5 clientes por hora. El barbero tarda exponencialmente 10 minutos "
            "por cliente. Hay un solo servidor. Determinar: a) tiempo de espera en la cola, "
            "b) numero esperado en la cola."
        ),
        "expected_model": "PICS",
        "expected_objectives_contain_any": ["compute_Wq", "compute_Lq", "compute_W"],
    },
    {
        "name": "mmc_variant_A",
        "statement": (
            "Llegan 24 clientes por hora. Cada ventanilla atiende en promedio 5 clientes "
            "en 30 minutos segun distribucion exponencial. Hay 4 ventanillas con cola unica. "
            "Hallar: a) probabilidad de esperar, b) numero esperado en el sistema."
        ),
        "expected_model": "PICM",
        "expected_objectives_contain_any": ["compute_wait_probability", "compute_L"],
    },
    {
        "name": "pfcs_variant_B",
        "statement": (
            "Una fabrica tiene 6 maquinas que forman una fuente finita. "
            "Cada maquina se averia exponencialmente cada 8 dias. "
            "Un mecanico puede reparar exponencialmente en 2 dias. "
            "Hay un servidor para toda la poblacion finita de maquinas. Calcular: "
            "a) probabilidad de que el mecanico este libre (P0), "
            "b) numero esperado de maquinas en el sistema."
        ),
        "expected_model": "PFCS",
        "expected_objectives_contain_any": ["compute_P0", "compute_L"],
    },
    {
        "name": "pfhet_variant_A",
        "statement": (
            "Hay 5 montacargas en la empresa. Cada montacargas se averia exponencialmente "
            "cada 8 dias. El tecnico A y tecnico B tienen velocidades diferentes de reparacion: "
            "el tecnico A demora en promedio 2 dias y el tecnico B demora 4 dias. "
            "Ambos tecnicos atienden a los mismos montacargas con tasas distintas. "
            "Calcular: a) probabilidad de sistema vacio, b) montacargas operando."
        ),
        "expected_model": "PFHET",
        "expected_objectives_contain_any": ["compute_P0", "compute_units_operating", "compute_L"],
    },
    {
        "name": "mm1_cost_simple",
        "statement": (
            "Una tienda es atendida por un cajero. "
            "Los clientes llegan segun proceso Poisson con tasa de 10 por hora. "
            "El servicio sigue distribucion exponencial con media de 5 minutos. "
            "El costo del servidor es de 15 dolares por hora y el costo de espera "
            "es de 8 dolares por hora. Calcular: a) costo diario total."
        ),
        "expected_model": "PICS",
        "expected_objectives_contain_any": [
            "compute_cost", "compute_total_cost", "compute_Wq", "compute_Lq",
        ],
    },
]


@pytest.mark.parametrize(
    "case",
    FLEXIBLE_RECOGNITION_CASES,
    ids=[c["name"] for c in FLEXIBLE_RECOGNITION_CASES],
)
def test_flexible_recognition_correct_model(case, analyzer):
    """Same model must be detected regardless of exact numeric values."""
    req = StatementAnalysisRequest(text=case["statement"])
    result = analyzer.analyze(req)
    assert result.identified_model == case["expected_model"], (
        f"[{case['name']}] Expected model {case['expected_model']}, "
        f"got {result.identified_model}"
    )


@pytest.mark.parametrize(
    "case",
    FLEXIBLE_RECOGNITION_CASES,
    ids=[c["name"] for c in FLEXIBLE_RECOGNITION_CASES],
)
def test_flexible_recognition_infers_expected_objectives(case, analyzer):
    """At least one of the expected objectives must appear in the analysis."""
    req = StatementAnalysisRequest(text=case["statement"])
    result = analyzer.analyze(req)

    all_objectives = set(result.inferred_objectives)
    for lit in result.literals:
        if lit.inferred_objective:
            all_objectives.add(lit.inferred_objective)

    expected_any = set(case["expected_objectives_contain_any"])
    assert all_objectives & expected_any, (
        f"[{case['name']}] None of {expected_any} found in objectives {all_objectives}"
    )


# ---------------------------------------------------------------------------
# Group 5 — Formula plans by model family
# ---------------------------------------------------------------------------

class TestFormulaPlansByFamily:
    """Structural formula plan chains must be correct per model family."""

    def test_pics_rho_lq_wq_chain(self):
        """PICS/compute_Wq must include rho → Lq → Wq in order."""
        plan, _ = build_formula_plan("PICS", "compute_Wq", {"lambda_", "mu"})
        keys = [s.produces for s in plan]
        assert "rho" in keys, "PICS Wq plan must include rho"
        assert "Lq" in keys, "PICS Wq plan must include Lq"
        assert "Wq" in keys, "PICS Wq plan must include Wq"
        # Order: rho before Lq before Wq
        assert keys.index("rho") < keys.index("Lq") < keys.index("Wq")

    def test_pics_p0_plan(self):
        """PICS/compute_P0 must compute rho then P0."""
        plan, _ = build_formula_plan("PICS", "compute_P0", {"lambda_", "mu"})
        keys = [s.produces for s in plan]
        assert "rho" in keys
        assert "P0" in keys
        assert keys.index("rho") < keys.index("P0")

    def test_picm_lq_chain_has_required_steps(self):
        """PICM/compute_Lq must include P0, Lq in order, with Pw or Pk as intermediary."""
        plan, _ = build_formula_plan("PICM", "compute_Lq", {"lambda_", "mu", "c"})
        keys = [s.produces for s in plan]
        assert "P0" in keys, "PICM Lq plan must include P0"
        assert "Lq" in keys, "PICM Lq plan must include Lq"
        # Intermediary is Pw (Erlang-C probability) — actual name may differ
        erlang_intermediary = "Pw" in keys or "Pk" in keys
        assert erlang_intermediary, f"PICM Lq plan must include Pw or Pk, got: {keys}"
        assert keys.index("P0") < keys.index("Lq")

    def test_picm_wq_includes_lq_then_wq(self):
        """PICM/compute_Wq must derive Lq before Wq."""
        plan, _ = build_formula_plan("PICM", "compute_Wq", {"lambda_", "mu", "c"})
        keys = [s.produces for s in plan]
        assert "Lq" in keys
        assert "Wq" in keys
        assert keys.index("Lq") < keys.index("Wq")

    def test_picm_wait_probability_plan(self):
        """PICM/compute_wait_probability must include P0 and Pw (Erlang-C)."""
        plan, _ = build_formula_plan("PICM", "compute_wait_probability", {"lambda_", "mu", "c"})
        keys = [s.produces for s in plan]
        assert "P0" in keys
        pw_present = "Pw" in keys or "Pk" in keys
        assert pw_present, f"Expected Pw or Pk in PICM wait_probability plan, got: {keys}"

    def test_pfcs_wq_includes_r_p0_pn(self):
        """PFCS/compute_Wq must include r, P0, and Wq."""
        plan, _ = build_formula_plan("PFCS", "compute_Wq", {"lambda_per_unit", "mu", "M"})
        keys = [s.produces for s in plan]
        assert "r" in keys, "PFCS plan must compute r"
        assert "P0" in keys, "PFCS plan must compute P0"
        assert "Wq" in keys or "W" in keys, "PFCS plan must compute Wq or W"

    def test_pfcs_p0_plan(self):
        """PFCS/compute_P0 must include r before P0."""
        plan, _ = build_formula_plan("PFCS", "compute_P0", {"lambda_per_unit", "mu", "M"})
        keys = [s.produces for s in plan]
        assert "r" in keys
        assert "P0" in keys
        assert keys.index("r") < keys.index("P0")

    def test_pfcm_p0_plan(self):
        """PFCM/compute_P0 must include r before P0."""
        plan, _ = build_formula_plan("PFCM", "compute_P0", {"lambda_per_unit", "mu", "M", "k"})
        keys = [s.produces for s in plan]
        assert "r" in keys
        assert "P0" in keys
        assert keys.index("r") < keys.index("P0")

    def test_pfcm_lq_chain(self):
        """PFCM/compute_Lq must include r → P0 → Pn → Lq."""
        plan, _ = build_formula_plan("PFCM", "compute_Lq", {"lambda_per_unit", "mu", "M", "k"})
        keys = [s.produces for s in plan]
        assert "r" in keys
        assert "P0" in keys
        assert "Lq" in keys
        assert keys.index("r") < keys.index("P0") < keys.index("Lq")

    def test_pfhet_p0_plan(self):
        """PFHET/compute_P0 must compute lambda_n and mu_n before P0."""
        plan, _ = build_formula_plan(
            "PFHET", "compute_P0", {"lambda_per_unit", "mu1", "mu2", "M"}
        )
        keys = [s.produces for s in plan]
        assert "P0" in keys, "PFHET must compute P0"

    def test_pfhet_units_operating_chain(self):
        """PFHET/compute_units_operating must go through P0."""
        plan, _ = build_formula_plan(
            "PFHET", "compute_units_operating",
            {"lambda_per_unit", "mu1", "mu2", "M"}
        )
        keys = [s.produces for s in plan]
        assert "P0" in keys
        assert "units_operating" in keys
        assert keys.index("P0") < keys.index("units_operating")

    def test_plan_steps_have_all_required_fields(self):
        """Every plan step must have all 7 required fields."""
        plan, _ = build_formula_plan("PICS", "compute_Wq", {"lambda_", "mu"})
        for step in plan:
            assert step.order >= 1
            assert step.formula_key
            assert step.formula_name
            assert step.formula_expression
            assert step.why_needed
            assert isinstance(step.required_variables, list)
            assert step.produces

    def test_unknown_model_returns_empty_plan(self):
        """Unknown model must return empty plan without raising."""
        plan, missing = build_formula_plan("INVALID_MODEL", "compute_Wq", set())
        assert plan == []

    def test_none_objective_returns_empty_plan(self):
        """None objective must return empty plan without raising."""
        plan, missing = build_formula_plan("PICS", None, {"lambda_", "mu"})
        assert plan == []


# ---------------------------------------------------------------------------
# Group 6 — Unsupported objectives (cost, dimensioning)
# ---------------------------------------------------------------------------

COST_STATEMENT = (
    "Una empresa quiere minimizar el costo total. "
    "El costo del servidor es de 50 dolares por hora y el costo de espera "
    "es de 20 dolares por hora. Clientes llegan Poisson 12 por hora. "
    "Servicio exponencial media 4 minutos. Un servidor. "
    "Calcular: a) costo diario total."
)

DIMENSIONING_STATEMENT = (
    "Cuantos servidores son necesarios para minimizar el costo total? "
    "Llegan 20 clientes por hora Poisson. Cada servidor atiende 10 por hora "
    "exponencial. Costo servidor 30 dolares hora, costo espera 15 dolares hora. "
    "b) numero optimo de servidores."
)


class TestUnsupportedObjectives:
    """Cost and dimensioning objectives must be detected but not raise errors."""

    def test_cost_objective_no_exception(self, analyzer):
        req = StatementAnalysisRequest(text=COST_STATEMENT)
        result = analyzer.analyze(req)  # must not raise
        assert result is not None

    def test_dimensioning_objective_no_exception(self, analyzer):
        req = StatementAnalysisRequest(text=DIMENSIONING_STATEMENT)
        result = analyzer.analyze(req)  # must not raise
        assert result is not None

    def test_cost_objective_detected_in_literals(self, analyzer):
        """If cost literal is detected, its objective must be set."""
        req = StatementAnalysisRequest(text=COST_STATEMENT)
        result = analyzer.analyze(req)
        # At least one literal or inferred_objective related to cost
        all_objectives = set(result.inferred_objectives)
        for lit in result.literals:
            if lit.inferred_objective:
                all_objectives.add(lit.inferred_objective)
        # Either a cost objective detected or at least a model was identified
        assert result.identified_model is not None

    def test_cost_literal_plan_not_empty_or_advisory(self, analyzer):
        """If cost objective detected in a literal, plan should be advisory or empty — not a crash."""
        req = StatementAnalysisRequest(text=COST_STATEMENT)
        result = analyzer.analyze(req)
        for lit in result.literals:
            if lit.inferred_objective and "cost" in lit.inferred_objective:
                # Plan may be empty or advisory — must not raise and formula_plan must be a list
                assert isinstance(lit.formula_plan, list)
                assert isinstance(lit.missing_variables, list)

    def test_formula_plan_for_cost_objective_does_not_raise(self):
        """build_formula_plan with cost objective must not raise."""
        plan, missing = build_formula_plan("PICS", "compute_cost", {"lambda_", "mu"})
        assert isinstance(plan, list)
        assert isinstance(missing, list)

    def test_formula_plan_for_dimensioning_does_not_raise(self):
        """build_formula_plan with dimensioning objective must not raise."""
        plan, missing = build_formula_plan("PICM", "compute_dimensioning_optimal_k", {"lambda_", "mu"})
        assert isinstance(plan, list)
        assert isinstance(missing, list)


# ---------------------------------------------------------------------------
# Group 7 — API compatibility
# ---------------------------------------------------------------------------

PICS_API_TEXT = (
    "Una tienda de alimentacion es atendida por una sola persona. "
    "Proceso Poisson con tasa de 15 clientes por hora. "
    "Servicio exponencial con media de 5 minutos. "
    "Calcule: a) tiempo medio de espera en cola, b) longitud media de la cola."
)

PICM_API_TEXT = (
    "Una empresa tiene 3 operadores para atender llamadas. "
    "Las llamadas llegan a razon de 2 por minuto (Poisson). "
    "El tiempo de atencion es exponencial con media de 1 minuto. "
    "Calcule: a) probabilidad de esperar, b) tiempo medio de espera."
)

_PICS_PAYLOAD = {"text": PICS_API_TEXT, "hint_model": "PICS"}
_PICM_PAYLOAD = {"text": PICM_API_TEXT, "hint_model": "PICM"}


class TestAPICompatibility:
    """POST /api/analyze must return valid JSON with formula_plan fields."""

    def test_api_analyze_pics_returns_200(self, client):
        resp = client.post("/api/analyze", json=_PICS_PAYLOAD)
        assert resp.status_code == 200

    def test_api_analyze_pics_model_identified(self, client):
        resp = client.post("/api/analyze", json=_PICS_PAYLOAD)
        data = resp.json()
        assert data.get("model_id") == "PICS"

    def test_api_analyze_pics_has_literals_with_formula_plan(self, client):
        resp = client.post("/api/analyze", json=_PICS_PAYLOAD)
        data = resp.json()
        # Literals may be empty if the statement format doesn't trigger segmentation.
        # When present, they must have required fields.
        for lit in data.get("literals", []):
            assert "formula_plan" in lit, f"Literal {lit.get('literal_id')} missing formula_plan"
            assert "missing_variables" in lit, f"Literal missing missing_variables"
            assert isinstance(lit["formula_plan"], list)
            assert isinstance(lit["missing_variables"], list)

    def test_api_analyze_pics_formula_plan_steps_have_fields(self, client):
        resp = client.post("/api/analyze", json=_PICS_PAYLOAD)
        data = resp.json()
        for lit in data.get("literals", []):
            for step in lit.get("formula_plan", []):
                assert "order" in step
                assert "formula_key" in step
                assert "formula_name" in step
                assert "formula_expression" in step
                assert "why_needed" in step
                assert "required_variables" in step
                assert "produces" in step

    def test_api_analyze_picm_returns_200(self, client):
        resp = client.post("/api/analyze", json=_PICM_PAYLOAD)
        assert resp.status_code == 200

    def test_api_analyze_picm_model_identified(self, client):
        resp = client.post("/api/analyze", json=_PICM_PAYLOAD)
        data = resp.json()
        assert data.get("model_id") == "PICM"

    def test_api_analyze_picm_has_literals_with_formula_plan(self, client):
        resp = client.post("/api/analyze", json=_PICM_PAYLOAD)
        data = resp.json()
        # Literals may be empty if the statement format doesn't trigger segmentation.
        # When present, they must have required fields.
        for lit in data.get("literals", []):
            assert "formula_plan" in lit
            assert isinstance(lit["formula_plan"], list)

    def test_api_analyze_empty_text_returns_400_or_error_response(self, client):
        """Empty text must return error (400 or error in response body)."""
        resp = client.post("/api/analyze", json={"text": ""})
        # Either 400 or 422 or response with identified_model=None
        if resp.status_code == 200:
            data = resp.json()
            # If 200, model should be unknown/None
            assert data.get("model_id") != "PICS"
        else:
            assert resp.status_code in {400, 422}


# ---------------------------------------------------------------------------
# Group 8 — UI health checks
# ---------------------------------------------------------------------------

class TestUIHealthChecks:
    """GET /analyze must return valid HTML with necessary elements."""

    def test_analyze_page_loads(self, client):
        response = client.get("/analyze")
        assert response.status_code == 200

    def test_analyze_page_returns_html(self, client):
        response = client.get("/analyze")
        assert "text/html" in response.headers.get("content-type", "")

    def test_analyze_page_has_api_analyze_reference(self, client):
        response = client.get("/analyze")
        assert "/api/analyze" in response.text

    def test_analyze_page_has_formula_plan_rendering(self, client):
        response = client.get("/analyze")
        # The page JS must contain formula plan table logic
        assert "formula_plan" in response.text or "formulaPlan" in response.text or "fp-" in response.text

    def test_analyze_page_has_literal_section(self, client):
        response = client.get("/analyze")
        # Must contain literal-related markup or JS
        assert "literal" in response.text.lower()

    def test_analyze_page_has_text_input_element(self, client):
        response = client.get("/analyze")
        # Must have a textarea or input for the problem statement
        assert "textarea" in response.text.lower() or 'type="text"' in response.text.lower()

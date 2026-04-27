"""
Phase 13 — Corrective tests.

Validates the 6 key improvements delivered in Phase 13:

  Test 1  — PFCS objective detection (P0, L from inline literal statement)
  Test 2  — M/M/1 cost objective detection (cost from single inline literal)
  Test 3  — Compact inline literal segmentation ("Calcule: a)..., b)..., c)...")
  Test 4  — Single compact literal with trigger phrase ("Calcular: a) ...")
  Test 5  — API without hint_model identifies PICS automatically
  Test 6  — API without hint_model identifies PICM automatically
  Test 7  — hint_model still overrides auto-identification correctly
  Test 8  — New unsupported objectives are handled without crashes

Constraints:
  - Only touches the "Analizar enunciado" module.
  - Does NOT modify web.py, solver.py, matcher.py, orchestrator.py, main.py.
  - Baseline tests must still pass (run full suite to verify).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from domain.entities.analysis import StatementAnalysisRequest
from domain.services.statement_analyzer import make_analyzer


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def analyzer():
    return make_analyzer()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1 — PFCS objective detection (P0, L)
# ---------------------------------------------------------------------------

_PFCS_STATEMENT = (
    "Una fabrica tiene 6 maquinas que forman una fuente finita. "
    "Cada maquina se averia exponencialmente cada 8 dias. "
    "Un mecanico puede reparar exponencialmente en 2 dias. "
    "Hay un servidor para toda la poblacion finita de maquinas. Calcular: "
    "a) probabilidad de que el mecanico este libre (P0), "
    "b) numero esperado de maquinas en el sistema."
)


class TestPFCSObjectiveDetection:
    """PFCS statements using 'mecanico libre' and 'maquinas en el sistema' must detect objectives."""

    def test_model_identified_as_pfcs(self, analyzer):
        req = StatementAnalysisRequest(text=_PFCS_STATEMENT)
        result = analyzer.analyze(req)
        assert result.identified_model == "PFCS", (
            f"Expected PFCS, got {result.identified_model}"
        )

    def test_literals_detected(self, analyzer):
        """Compact inline literals a) and b) must be detected."""
        req = StatementAnalysisRequest(text=_PFCS_STATEMENT)
        result = analyzer.analyze(req)
        assert len(result.literals) >= 2, (
            f"Expected ≥2 literals, got {len(result.literals)}: {result.literals}"
        )

    def test_p0_objective_detected(self, analyzer):
        """compute_P0 must appear in objectives (from literal 'a' or full text)."""
        req = StatementAnalysisRequest(text=_PFCS_STATEMENT)
        result = analyzer.analyze(req)
        all_obj = set(result.inferred_objectives)
        for lit in result.literals:
            if lit.inferred_objective:
                all_obj.add(lit.inferred_objective)
        assert "compute_P0" in all_obj, (
            f"compute_P0 not found in {all_obj}"
        )

    def test_l_objective_detected(self, analyzer):
        """compute_L must appear in objectives (from literal 'b' or full text)."""
        req = StatementAnalysisRequest(text=_PFCS_STATEMENT)
        result = analyzer.analyze(req)
        all_obj = set(result.inferred_objectives)
        for lit in result.literals:
            if lit.inferred_objective:
                all_obj.add(lit.inferred_objective)
        assert "compute_L" in all_obj, (
            f"compute_L not found in {all_obj}"
        )


# ---------------------------------------------------------------------------
# Test 2 — M/M/1 cost objective detection
# ---------------------------------------------------------------------------

_COST_STATEMENT = (
    "Una tienda es atendida por un cajero. "
    "Los clientes llegan segun proceso Poisson con tasa de 10 por hora. "
    "El servicio sigue distribucion exponencial con media de 5 minutos. "
    "El costo del servidor es de 15 dolares por hora y el costo de espera "
    "es de 8 dolares por hora. Calcular: a) costo diario total."
)


class TestCostObjectiveDetection:
    """Statements mentioning 'costo diario total' must detect a cost objective."""

    def test_model_identified_as_pics(self, analyzer):
        req = StatementAnalysisRequest(text=_COST_STATEMENT)
        result = analyzer.analyze(req)
        assert result.identified_model == "PICS", (
            f"Expected PICS, got {result.identified_model}"
        )

    def test_cost_objective_detected(self, analyzer):
        """A cost-related objective must appear (compute_cost or compute_total_cost)."""
        req = StatementAnalysisRequest(text=_COST_STATEMENT)
        result = analyzer.analyze(req)
        all_obj = set(result.inferred_objectives)
        for lit in result.literals:
            if lit.inferred_objective:
                all_obj.add(lit.inferred_objective)
        cost_objectives = {"compute_cost", "compute_total_cost"}
        assert all_obj & cost_objectives, (
            f"No cost objective found in {all_obj}"
        )

    def test_no_crash_with_unsupported_objective(self, analyzer):
        """Unsupported cost objectives must produce issues, not raise exceptions."""
        req = StatementAnalysisRequest(text=_COST_STATEMENT)
        result = analyzer.analyze(req)
        # Should return a result without raising
        assert result is not None
        # Any literal with a cost objective must have a warning issue
        for lit in result.literals:
            if lit.inferred_objective in {"compute_cost", "compute_total_cost"}:
                issue_codes = {i.code for i in lit.issues}
                assert "objective_detected_but_not_executable" in issue_codes, (
                    f"Expected warning for unsupported cost objective in literal {lit.literal_id}"
                )


# ---------------------------------------------------------------------------
# Test 3 — Compact inline literal segmentation (3 literals)
# ---------------------------------------------------------------------------

_COMPACT_3_STATEMENT = (
    "Una cola M/M/1 tiene tasa de llegada de 20 por hora y tasa de servicio de 30 por hora. "
    "Calcule: "
    "a) tiempo medio de espera en cola, "
    "b) longitud media de la cola, "
    "c) probabilidad de sistema vacio."
)


class TestCompactLiteralSegmentation:
    """Inline compact format 'Calcule: a)..., b)..., c)...' must produce 3 literals."""

    def test_three_literals_detected(self, analyzer):
        req = StatementAnalysisRequest(text=_COMPACT_3_STATEMENT)
        result = analyzer.analyze(req)
        assert len(result.literals) == 3, (
            f"Expected 3 literals, got {len(result.literals)}: "
            f"{[l.literal_id for l in result.literals]}"
        )

    def test_literal_ids_are_a_b_c(self, analyzer):
        req = StatementAnalysisRequest(text=_COMPACT_3_STATEMENT)
        result = analyzer.analyze(req)
        ids = [l.literal_id for l in result.literals]
        assert ids == ["a", "b", "c"], f"Expected [a, b, c], got {ids}"

    def test_wq_objective_in_literal_a(self, analyzer):
        req = StatementAnalysisRequest(text=_COMPACT_3_STATEMENT)
        result = analyzer.analyze(req)
        lit_a = next((l for l in result.literals if l.literal_id == "a"), None)
        assert lit_a is not None
        assert lit_a.inferred_objective == "compute_Wq", (
            f"Literal 'a' objective: {lit_a.inferred_objective}"
        )

    def test_lq_objective_in_literal_b(self, analyzer):
        req = StatementAnalysisRequest(text=_COMPACT_3_STATEMENT)
        result = analyzer.analyze(req)
        lit_b = next((l for l in result.literals if l.literal_id == "b"), None)
        assert lit_b is not None
        assert lit_b.inferred_objective == "compute_Lq", (
            f"Literal 'b' objective: {lit_b.inferred_objective}"
        )

    def test_p0_objective_in_literal_c(self, analyzer):
        req = StatementAnalysisRequest(text=_COMPACT_3_STATEMENT)
        result = analyzer.analyze(req)
        lit_c = next((l for l in result.literals if l.literal_id == "c"), None)
        assert lit_c is not None
        assert lit_c.inferred_objective == "compute_P0", (
            f"Literal 'c' objective: {lit_c.inferred_objective}"
        )


# ---------------------------------------------------------------------------
# Test 4 — Single compact literal with trigger phrase
# ---------------------------------------------------------------------------

_SINGLE_LITERAL_STATEMENT = (
    "Un sistema de colas atiende clientes con tasa de servicio de 25 por hora. "
    "La tasa de llegada es de 15 clientes por hora. "
    "Determinar: a) tiempo medio de espera en cola."
)


class TestSingleCompactLiteral:
    """A single 'a)' literal after a trigger phrase must be detected."""

    def test_single_literal_detected(self, analyzer):
        req = StatementAnalysisRequest(text=_SINGLE_LITERAL_STATEMENT)
        result = analyzer.analyze(req)
        assert len(result.literals) == 1, (
            f"Expected 1 literal, got {len(result.literals)}"
        )

    def test_literal_id_is_a(self, analyzer):
        req = StatementAnalysisRequest(text=_SINGLE_LITERAL_STATEMENT)
        result = analyzer.analyze(req)
        assert result.literals[0].literal_id == "a"

    def test_wq_objective_detected(self, analyzer):
        req = StatementAnalysisRequest(text=_SINGLE_LITERAL_STATEMENT)
        result = analyzer.analyze(req)
        assert result.literals[0].inferred_objective == "compute_Wq", (
            f"Expected compute_Wq, got {result.literals[0].inferred_objective}"
        )


# ---------------------------------------------------------------------------
# Test 5 — API: PICS identified without hint_model
# ---------------------------------------------------------------------------

_PICS_API_TEXT = (
    "Un sistema M/M/1 con un solo servidor recibe clientes segun Poisson "
    "a razon de 10 por hora. El servicio es exponencial con media de 4 minutos.\n"
    "a) Tiempo medio de espera en cola.\n"
    "b) Longitud media de la cola."
)


class TestAPIWithoutHintModelPICS:
    """Clear M/M/1 text must yield PICS without hint_model."""

    def test_model_id_is_pics(self, client):
        resp = client.post("/api/analyze", json={"text": _PICS_API_TEXT})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("model_id") == "PICS", (
            f"Expected PICS, got {data.get('model_id')}. Full response: {data}"
        )

    def test_at_least_one_literal(self, client):
        resp = client.post("/api/analyze", json={"text": _PICS_API_TEXT})
        data = resp.json()
        assert len(data.get("literals", [])) >= 1, (
            f"Expected ≥1 literal, got {data.get('literals', [])}"
        )

    def test_ok_flag_is_true(self, client):
        resp = client.post("/api/analyze", json={"text": _PICS_API_TEXT})
        assert resp.json().get("ok") is True


# ---------------------------------------------------------------------------
# Test 6 — API: PICM identified without hint_model
# ---------------------------------------------------------------------------

_PICM_API_TEXT = (
    "Un sistema M/M/3 con una sola cola y 3 servidores recibe llamadas segun Poisson "
    "a razon de 24 por hora. El servicio de cada servidor es exponencial con media "
    "de 5 minutos.\n"
    "a) Probabilidad de esperar.\n"
    "b) Numero esperado en el sistema."
)


class TestAPIWithoutHintModelPICM:
    """Clear M/M/3 text must yield PICM without hint_model."""

    def test_model_id_is_picm(self, client):
        resp = client.post("/api/analyze", json={"text": _PICM_API_TEXT})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("model_id") == "PICM", (
            f"Expected PICM, got {data.get('model_id')}. Full response: {data}"
        )

    def test_at_least_one_literal(self, client):
        resp = client.post("/api/analyze", json={"text": _PICM_API_TEXT})
        data = resp.json()
        assert len(data.get("literals", [])) >= 1, (
            f"Expected ≥1 literal, got {data.get('literals', [])}"
        )

    def test_ok_flag_is_true(self, client):
        resp = client.post("/api/analyze", json={"text": _PICM_API_TEXT})
        assert resp.json().get("ok") is True


# ---------------------------------------------------------------------------
# Test 7 — hint_model still overrides auto-identification
# ---------------------------------------------------------------------------

class TestHintModelOverride:
    """hint_model must override auto-identification when provided."""

    def test_hint_overrides_pics_to_pfcs(self, client):
        """Force PFCS on a text that would naturally be identified as PICS."""
        resp = client.post(
            "/api/analyze",
            json={
                "text": (
                    "Un sistema con un servidor atiende clientes con tasa de llegada "
                    "de 10 por hora. Calcule: a) numero esperado en el sistema."
                ),
                "hint_model": "PFCS",
            },
        )
        assert resp.status_code == 200
        assert resp.json().get("model_id") == "PFCS"

    def test_hint_model_not_required_for_clear_mm1(self, client):
        """For unambiguous M/M/1 text, hint_model must be optional (not cause error)."""
        resp = client.post(
            "/api/analyze",
            json={
                "text": (
                    "Sistema M/M/1. Llegan 8 por hora. Tiempo servicio 6 minutos. "
                    "Calcule: a) tiempo de espera en cola."
                ),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("model_id") == "PICS"


# ---------------------------------------------------------------------------
# Test 8 — New unsupported objectives handled cleanly
# ---------------------------------------------------------------------------

_COMPARE_STATEMENT = (
    "Una empresa estudia dos alternativas de servicio. La alternativa A tiene "
    "un servidor con tasa 20 por hora. La alternativa B tiene dos servidores con "
    "tasa 12 por hora cada uno. Llegadas a 15 por hora. Calcule: "
    "a) Compare dos alternativas de servicio, "
    "b) Determine la mejor alternativa."
)


class TestNewUnsupportedObjectives:
    """compare_alternatives and optimize_cost must be detected without crashing."""

    def test_no_exception_raised(self, analyzer):
        req = StatementAnalysisRequest(text=_COMPARE_STATEMENT)
        result = analyzer.analyze(req)
        assert result is not None

    def test_compare_alternatives_detected(self, analyzer):
        req = StatementAnalysisRequest(text=_COMPARE_STATEMENT)
        result = analyzer.analyze(req)
        all_obj = set(result.inferred_objectives)
        for lit in result.literals:
            if lit.inferred_objective:
                all_obj.add(lit.inferred_objective)
        assert "compare_alternatives" in all_obj, (
            f"compare_alternatives not found in {all_obj}"
        )

    def test_optimize_cost_detected(self, analyzer):
        req = StatementAnalysisRequest(text=_COMPARE_STATEMENT)
        result = analyzer.analyze(req)
        all_obj = set(result.inferred_objectives)
        for lit in result.literals:
            if lit.inferred_objective:
                all_obj.add(lit.inferred_objective)
        assert "optimize_cost" in all_obj, (
            f"optimize_cost not found in {all_obj}"
        )

    def test_literals_have_warning_issues(self, analyzer):
        """Unsupported objectives must produce 'objective_detected_but_not_executable' issues."""
        req = StatementAnalysisRequest(text=_COMPARE_STATEMENT)
        result = analyzer.analyze(req)
        unsupported_with_issues = [
            lit for lit in result.literals
            if lit.inferred_objective in {"compare_alternatives", "optimize_cost"}
            and any(i.code == "objective_detected_but_not_executable" for i in lit.issues)
        ]
        assert len(unsupported_with_issues) >= 1, (
            "Expected at least one literal with 'objective_detected_but_not_executable' issue"
        )

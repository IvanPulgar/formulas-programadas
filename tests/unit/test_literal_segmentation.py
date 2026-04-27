"""
Tests for Phase 8 — Literal / inciso segmentation and per-literal objective inference.

PRUEBA 1: 3 literals detected from standard "a) b) c)" format
PRUEBA 2: Correct objective inferred per literal (rho, Lq, Wq)
PRUEBA 3: Literal order preserved (a → b → c)
PRUEBA 4: No literals → backward compat (context = full text, literals = [])
PRUEBA 5: Parenthesized "(a) (b) (c)" format
PRUEBA 6: AnalyzeResponse carries statement_context + literals via POST /api/analyze
PRUEBA 7: GET /analyze still loads correctly
PRUEBA 8: Dot format "a. b. c."
PRUEBA 9: "Literal a / Literal b" keyword format
PRUEBA 10: "inciso a / inciso b" keyword format
PRUEBA 11: statement_context contains only data lines (no question lines)
PRUEBA 12: planned_step_ids populated when model identified
"""

from __future__ import annotations

import unicodedata

import pytest
from fastapi.testclient import TestClient

from app.main import app
from domain.entities.analysis import StatementAnalysisRequest
from domain.services.literal_segmenter import LiteralSegmenter
from domain.services.statement_analyzer import make_analyzer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def segment(text: str):
    """Convenience wrapper."""
    segmenter = LiteralSegmenter()
    return segmenter.segment(text, _norm(text))


# ---------------------------------------------------------------------------
# Standard problem used across multiple tests
# ---------------------------------------------------------------------------
STANDARD_PROBLEM = (
    "Una tienda recibe 10 clientes por hora. El tiempo medio de servicio es de 4 minutos. "
    "Hay un solo servidor.\n"
    "a) Probabilidad de que haya línea de espera.\n"
    "b) Longitud media de la línea de espera.\n"
    "c) Tiempo medio que los clientes permanecen en cola."
)

# ---------------------------------------------------------------------------
# PRUEBA 1 — Three literals detected from standard format
# ---------------------------------------------------------------------------

def test_three_literals_detected():
    ctx, literals = segment(STANDARD_PROBLEM)
    assert len(literals) == 3, f"Expected 3 literals, got {len(literals)}: {literals}"


# ---------------------------------------------------------------------------
# PRUEBA 2 — Correct objective inferred per literal
# ---------------------------------------------------------------------------

def test_objective_rho_for_first_literal():
    _, literals = segment(STANDARD_PROBLEM)
    assert literals[0].inferred_objective == "compute_wait_probability", (
        f"Expected compute_wait_probability for literal a, got {literals[0].inferred_objective}"
    )

def test_objective_lq_for_second_literal():
    _, literals = segment(STANDARD_PROBLEM)
    assert literals[1].inferred_objective == "compute_Lq", (
        f"Expected compute_Lq for literal b, got {literals[1].inferred_objective}"
    )

def test_objective_wq_for_third_literal():
    _, literals = segment(STANDARD_PROBLEM)
    assert literals[2].inferred_objective == "compute_Wq", (
        f"Expected compute_Wq for literal c, got {literals[2].inferred_objective}"
    )


# ---------------------------------------------------------------------------
# PRUEBA 3 — Literal order preserved
# ---------------------------------------------------------------------------

def test_literal_order_preserved():
    _, literals = segment(STANDARD_PROBLEM)
    ids = [lit.literal_id for lit in literals]
    assert ids == ["a", "b", "c"], f"Expected [a, b, c], got {ids}"


# ---------------------------------------------------------------------------
# PRUEBA 4 — No literals → backward compatibility
# ---------------------------------------------------------------------------

def test_no_literals_returns_full_text_as_context():
    text = "Llegan 10 clientes por hora. Tiempo de servicio 4 minutos. Calcular Wq."
    ctx, literals = segment(text)
    assert literals == [], "Expected no literals"
    assert text.strip() in ctx or ctx in text.strip(), (
        f"Context should be the full text, got: {ctx!r}"
    )

def test_no_literals_empty_list():
    _, literals = segment("Sin literales aquí.")
    assert isinstance(literals, list)
    assert len(literals) == 0


# ---------------------------------------------------------------------------
# PRUEBA 5 — Parenthesized format "(a) (b) (c)"
# ---------------------------------------------------------------------------

PARENS_PROBLEM = (
    "Sistema con 2 servidores. λ=6 clientes/hora, μ=4 clientes/hora por servidor.\n"
    "(a) Factor de utilización del sistema.\n"
    "(b) Número medio en el sistema.\n"
    "(c) Tiempo total en el sistema."
)

def test_parenthesized_format_detects_three_literals():
    _, literals = segment(PARENS_PROBLEM)
    assert len(literals) == 3, f"Expected 3 literals (parens), got {len(literals)}"

def test_parenthesized_literal_ids():
    _, literals = segment(PARENS_PROBLEM)
    ids = [lit.literal_id for lit in literals]
    assert ids == ["a", "b", "c"]

def test_parenthesized_objectives():
    _, literals = segment(PARENS_PROBLEM)
    assert literals[0].inferred_objective == "compute_rho"
    assert literals[1].inferred_objective == "compute_L"
    assert literals[2].inferred_objective == "compute_W"


# ---------------------------------------------------------------------------
# PRUEBA 8 — Dot format "a. b. c."
# ---------------------------------------------------------------------------

DOT_PROBLEM = (
    "Un banco atiende clientes. λ=5 clientes/min, μ=8 clientes/min.\n"
    "a. Tiempo ocioso del servidor.\n"
    "b. Tiempo medio en cola.\n"
    "c. Número medio en el sistema."
)

def test_dot_format_detects_three_literals():
    _, literals = segment(DOT_PROBLEM)
    assert len(literals) == 3, f"Expected 3 dot-format literals, got {len(literals)}"

def test_dot_format_ids():
    _, literals = segment(DOT_PROBLEM)
    ids = [lit.literal_id for lit in literals]
    assert ids == ["a", "b", "c"]

def test_dot_format_objectives():
    _, literals = segment(DOT_PROBLEM)
    assert literals[0].inferred_objective == "compute_P0"
    assert literals[1].inferred_objective == "compute_Wq"
    assert literals[2].inferred_objective == "compute_L"


# ---------------------------------------------------------------------------
# PRUEBA 9 — "Literal a / Literal b" keyword format
# ---------------------------------------------------------------------------

KEYWORD_PROBLEM = (
    "Un sistema de colas M/M/1. λ=3/min, μ=5/min.\n"
    "Literal a Tiempo de espera promedio.\n"
    "Literal b Longitud de la cola.\n"
    "Literal c Probabilidad de sistema vacío."
)

def test_literal_keyword_format_detects_three():
    _, literals = segment(KEYWORD_PROBLEM)
    assert len(literals) == 3, f"Expected 3 keyword literals, got {len(literals)}"

def test_literal_keyword_objectives():
    _, literals = segment(KEYWORD_PROBLEM)
    assert literals[0].inferred_objective == "compute_Wq"
    assert literals[1].inferred_objective == "compute_Lq"
    assert literals[2].inferred_objective == "compute_P0"


# ---------------------------------------------------------------------------
# PRUEBA 10 — "inciso a / inciso b" format
# ---------------------------------------------------------------------------

INCISO_PROBLEM = (
    "Sistema de servicio único. λ=2/min, μ=3/min.\n"
    "inciso a Tiempo medio en el sistema.\n"
    "inciso b Factor de utilización."
)

def test_inciso_format_detects_two():
    _, literals = segment(INCISO_PROBLEM)
    assert len(literals) == 2, f"Expected 2 inciso literals, got {len(literals)}"

def test_inciso_format_ids():
    _, literals = segment(INCISO_PROBLEM)
    assert [lit.literal_id for lit in literals] == ["a", "b"]


# ---------------------------------------------------------------------------
# PRUEBA 11 — statement_context contains only the data lines
# ---------------------------------------------------------------------------

def test_statement_context_excludes_literal_questions():
    ctx, _ = segment(STANDARD_PROBLEM)
    # Context must not contain the question texts
    assert "probabilidad" not in ctx.lower(), "Context should not contain literal questions"
    assert "longitud" not in ctx.lower()
    assert "tiempo medio que" not in ctx.lower()

def test_statement_context_contains_data():
    ctx, _ = segment(STANDARD_PROBLEM)
    assert "10 clientes" in ctx or "10 clientes" in ctx.lower()


# ---------------------------------------------------------------------------
# PRUEBA 12 — planned_step_ids populated when model identified
# ---------------------------------------------------------------------------

def test_planned_step_ids_populated():
    analyzer = make_analyzer()
    req = StatementAnalysisRequest(text=STANDARD_PROBLEM)
    result = analyzer.analyze(req)

    assert len(result.literals) == 3
    # At least one literal should have step ids if model was found
    if result.identified_model:
        has_steps = any(len(lit.planned_step_ids) > 0 for lit in result.literals)
        assert has_steps, (
            f"Expected at least one literal to have planned_step_ids, "
            f"model={result.identified_model}, literals={result.literals}"
        )

def test_statement_context_stored_in_analysis_result():
    analyzer = make_analyzer()
    req = StatementAnalysisRequest(text=STANDARD_PROBLEM)
    result = analyzer.analyze(req)
    assert result.statement_context is not None
    assert len(result.statement_context) > 0


# ---------------------------------------------------------------------------
# PRUEBA 6 — API response carries statement_context + literals
# ---------------------------------------------------------------------------

client = TestClient(app)

def test_api_returns_literals_field():
    resp = client.post("/api/analyze", json={"text": STANDARD_PROBLEM})
    assert resp.status_code == 200
    data = resp.json()
    assert "literals" in data
    assert isinstance(data["literals"], list)
    assert len(data["literals"]) == 3

def test_api_returns_statement_context():
    resp = client.post("/api/analyze", json={"text": STANDARD_PROBLEM})
    assert resp.status_code == 200
    data = resp.json()
    assert "statement_context" in data
    assert data["statement_context"] is not None

def test_api_literal_structure():
    resp = client.post("/api/analyze", json={"text": STANDARD_PROBLEM})
    data = resp.json()
    first = data["literals"][0]
    assert "literal_id" in first
    assert "literal_text" in first
    assert "inferred_objective" in first
    assert "planned_step_ids" in first
    assert first["literal_id"] == "a"

def test_api_literal_objectives_in_response():
    resp = client.post("/api/analyze", json={"text": STANDARD_PROBLEM})
    data = resp.json()
    objs = [lit["inferred_objective"] for lit in data["literals"]]
    assert "compute_wait_probability" in objs
    assert "compute_Lq" in objs
    assert "compute_Wq" in objs

def test_api_no_literals_backward_compat():
    text = "Llegan 10 clientes por hora. Tiempo de servicio 4 minutos. Calcular Wq."
    resp = client.post("/api/analyze", json={"text": text})
    assert resp.status_code == 200
    data = resp.json()
    assert "literals" in data
    assert data["literals"] == []

def test_api_ok_field_still_present():
    resp = client.post("/api/analyze", json={"text": STANDARD_PROBLEM})
    data = resp.json()
    assert "ok" in data
    assert data["ok"] is True


# ---------------------------------------------------------------------------
# PRUEBA 7 — GET /analyze still loads
# ---------------------------------------------------------------------------

def test_get_analyze_page_loads():
    resp = client.get("/analyze")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]

def test_get_analyze_page_contains_textarea():
    resp = client.get("/analyze")
    assert "statement-input" in resp.text

def test_get_analyze_page_has_literals_js():
    resp = client.get("/analyze")
    assert "buildLiteralsSection" in resp.text, "Template must include buildLiteralsSection JS function"


# ---------------------------------------------------------------------------
# Extra edge cases
# ---------------------------------------------------------------------------

def test_single_literal_detected():
    text = "Datos del sistema. λ=4/min, μ=6/min.\na) Tiempo medio en cola."
    _, literals = segment(text)
    assert len(literals) == 1
    assert literals[0].literal_id == "a"
    assert literals[0].inferred_objective == "compute_Wq"

def test_literal_text_is_not_empty():
    _, literals = segment(STANDARD_PROBLEM)
    for lit in literals:
        assert len(lit.raw_text) > 0, f"Literal {lit.literal_id} has empty raw_text"
        assert len(lit.normalized_text) > 0

def test_normalized_text_is_lowercase():
    _, literals = segment(STANDARD_PROBLEM)
    for lit in literals:
        assert lit.normalized_text == lit.normalized_text.lower()

def test_literals_have_no_marker_prefix():
    """The marker (e.g. 'a)') should not appear in the literal's raw_text."""
    _, literals = segment(STANDARD_PROBLEM)
    for lit in literals:
        # raw_text must not start with the marker itself
        assert not lit.raw_text.startswith(f"{lit.literal_id})")
        assert not lit.raw_text.startswith(f"({lit.literal_id})")

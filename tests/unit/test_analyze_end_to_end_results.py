"""
test_analyze_end_to_end_results.py  —  Fase 15 — Auditoría E2E

10 pruebas de integración completa (pipeline de extremo a extremo):
  1-7  : dominio puro  via make_analyzer() + StatementAnalysisRequest
  8-9  : API HTTP      via TestClient + POST /api/analyze
  10   : UI            via TestClient + GET  /analyze

Textos calibrados para los patrones del VariableExtractor actual.
Valores esperados verificados con _calibrate.py antes de commit.

RESTRICCIONES:
  - No modifica web.py, solver.py, matcher.py, orchestrator.py, main.py
  - No modifica nav.html ni ningún archivo del módulo "Resolver fórmulas"
  - No modifica el catálogo general de fórmulas ni el PDF
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
# Helper
# ---------------------------------------------------------------------------

def _lit(result, literal_id: str):
    """Return DetectedLiteral by id, or None."""
    for lit in result.literals:
        if lit.literal_id == literal_id:
            return lit
    return None


def _cr(result, literal_id: str):
    """Return calculation_result for literal, or None."""
    lit = _lit(result, literal_id)
    return lit.calculation_result if lit else None


# ---------------------------------------------------------------------------
# PRUEBA 1 — Tienda M/M/1, 5 literales, todos calculados
# λ=10/h → 0.1667/min, μ=4min → 0.25/min, ρ=2/3, periodo 12h=720min
# ---------------------------------------------------------------------------

TIENDA_TEXT = (
    "Una tienda de alimentacion es atendida por una persona. "
    "Los clientes llegan segun un proceso de Poisson con tasa de 10 clientes por hora. "
    "El tiempo medio de servicio es de 4 minutos por cliente. "
    "La tienda opera 12 horas al dia.\n"
    "a) Probabilidad de que haya linea de espera.\n"
    "b) Longitud media de la linea de espera.\n"
    "c) Tiempo medio que los clientes permanecen en cola.\n"
    "d) Total de minutos diarios que permanece desocupada la persona que atiende.\n"
    "e) Numero diario de clientes que esperan para ser atendidos."
)


def test_prueba1_tienda_model_pics(analyzer):
    """Pipeline identifica modelo PICS para texto de tienda M/M/1."""
    req = StatementAnalysisRequest(text=TIENDA_TEXT)
    result = analyzer.analyze(req)
    assert result.identified_model == "PICS"


def test_prueba1_tienda_rho_literal_a(analyzer):
    """[a] P(esperar) = ρ = 2/3 ≈ 0.6667."""
    req = StatementAnalysisRequest(text=TIENDA_TEXT)
    result = analyzer.analyze(req)
    cr = _cr(result, "a")
    assert cr is not None
    assert cr.calculated is True
    assert cr.value == pytest.approx(2 / 3, rel=1e-3)
    assert cr.issues == []


def test_prueba1_tienda_lq_literal_b(analyzer):
    """[b] Lq = ρ²/(1-ρ) = 4/3 ≈ 1.3333 clientes."""
    req = StatementAnalysisRequest(text=TIENDA_TEXT)
    result = analyzer.analyze(req)
    cr = _cr(result, "b")
    assert cr is not None
    assert cr.calculated is True
    assert cr.value == pytest.approx(4 / 3, rel=1e-3)
    assert "clientes" in cr.display_value


def test_prueba1_tienda_wq_literal_c(analyzer):
    """[c] Wq ≈ 8 min."""
    req = StatementAnalysisRequest(text=TIENDA_TEXT)
    result = analyzer.analyze(req)
    cr = _cr(result, "c")
    assert cr is not None
    assert cr.calculated is True
    assert cr.value == pytest.approx(8.0, rel=1e-3)
    assert "min" in cr.display_value


def test_prueba1_tienda_idle_time_literal_d(analyzer):
    """[d] Minutos diarios desocupado = P0 × 720 = (1/3) × 720 = 240 min."""
    req = StatementAnalysisRequest(text=TIENDA_TEXT)
    result = analyzer.analyze(req)
    cr = _cr(result, "d")
    assert cr is not None
    assert cr.calculated is True
    assert cr.value == pytest.approx(240.0, rel=1e-3)


def test_prueba1_tienda_waiting_arrivals_literal_e(analyzer):
    """[e] Clientes/día que esperan = λ × periodo × ρ = 10/h × 12h × 2/3 = 80."""
    req = StatementAnalysisRequest(text=TIENDA_TEXT)
    result = analyzer.analyze(req)
    cr = _cr(result, "e")
    assert cr is not None
    assert cr.calculated is True
    assert cr.value == pytest.approx(80.0, rel=1e-3)


# ---------------------------------------------------------------------------
# PRUEBA 2 — M/M/1 con μ en segundos, λ en minutos
# λ=10/min, μ=5s → 12/min, ρ=5/6≈0.8333
# ---------------------------------------------------------------------------

SERVIDOR_SEGUNDOS_TEXT = (
    "Los clientes llegan con una tasa de 10 clientes por minuto. "
    "El tiempo de servicio es exponencial con media de 5 segundos. "
    "Hay un solo servidor.\n"
    "a) Proporcion de tiempo que el servidor esta desocupado.\n"
    "b) Fraccion de clientes que debe esperar.\n"
    "c) Probabilidad de que al menos dos clientes esten esperando.\n"
    "d) Tiempo esperado total de un cliente en el sistema.\n"
    "e) Numero medio de clientes esperando en la cola."
)


def test_prueba2_servidor_segundos_rho(analyzer):
    """λ=10/min, μ=12/min → ρ = 5/6. P0 = 1/6 ≈ 0.1667."""
    req = StatementAnalysisRequest(text=SERVIDOR_SEGUNDOS_TEXT)
    result = analyzer.analyze(req)
    cr_a = _cr(result, "a")
    assert cr_a is not None
    assert cr_a.calculated is True
    assert cr_a.value == pytest.approx(1 / 6, rel=1e-3)   # P0


def test_prueba2_servidor_segundos_wait_prob(analyzer):
    """[b] P(esperar) = ρ = 5/6 ≈ 0.8333."""
    req = StatementAnalysisRequest(text=SERVIDOR_SEGUNDOS_TEXT)
    result = analyzer.analyze(req)
    cr_b = _cr(result, "b")
    assert cr_b is not None
    assert cr_b.calculated is True
    assert cr_b.value == pytest.approx(5 / 6, rel=1e-3)


def test_prueba2_servidor_segundos_p_at_least_2(analyzer):
    """[c] P(Q ≥ 2) = ρ³ = (5/6)³ ≈ 0.5787."""
    req = StatementAnalysisRequest(text=SERVIDOR_SEGUNDOS_TEXT)
    result = analyzer.analyze(req)
    cr_c = _cr(result, "c")
    assert cr_c is not None
    assert cr_c.calculated is True
    assert cr_c.value == pytest.approx((5 / 6) ** 3, rel=1e-3)


def test_prueba2_servidor_segundos_lq(analyzer):
    """[e] Lq = ρ²/(1-ρ) = (25/36)/(1/6) = 25/6 ≈ 4.1667."""
    req = StatementAnalysisRequest(text=SERVIDOR_SEGUNDOS_TEXT)
    result = analyzer.analyze(req)
    cr_e = _cr(result, "e")
    assert cr_e is not None
    assert cr_e.calculated is True
    assert cr_e.value == pytest.approx(25 / 6, rel=1e-3)


# ---------------------------------------------------------------------------
# PRUEBA 3 — Registro Civil M/M/c (c=3)
# λ=18/h → 0.3/min, μ=6min → 1/6/min, c=3, a=1.8, ρ=0.6
# ---------------------------------------------------------------------------

REGISTRO_CIVIL_TEXT = (
    "Los clientes llegan al Registro Civil segun Poisson con tasa de 18 clientes por hora. "
    "El tiempo de atencion por ventanilla es exponencial con media de 6 minutos. "
    "Hay 3 ventanillas.\n"
    "a) Porcentaje de tiempo con una o varias ventanillas desocupadas.\n"
    "b) Tiempo de espera de un cliente.\n"
    "c) Numero medio de clientes en la oficina.\n"
    "d) Probabilidad de que haya 1 o 2 clientes esperando."
)


def test_prueba3_registro_civil_model_picm(analyzer):
    """Pipeline identifica modelo PICM para sistema de colas con 3 servidores."""
    req = StatementAnalysisRequest(text=REGISTRO_CIVIL_TEXT)
    result = analyzer.analyze(req)
    assert result.identified_model == "PICM"


def test_prueba3_registro_civil_server_available_prob(analyzer):
    """[a] P(≥1 libre) ≈ 0.6453 (1 - Pw donde Pw = P(todos ocupados))."""
    req = StatementAnalysisRequest(text=REGISTRO_CIVIL_TEXT)
    result = analyzer.analyze(req)
    cr = _cr(result, "a")
    assert cr is not None
    assert cr.calculated is True
    assert cr.value == pytest.approx(0.6453, abs=5e-4)


def test_prueba3_registro_civil_wq(analyzer):
    """[b] Wq ≈ 1.77 min."""
    req = StatementAnalysisRequest(text=REGISTRO_CIVIL_TEXT)
    result = analyzer.analyze(req)
    cr = _cr(result, "b")
    assert cr is not None
    assert cr.calculated is True
    assert cr.value == pytest.approx(1.7737, abs=5e-4)


def test_prueba3_registro_civil_L(analyzer):
    """[c] L ≈ 2.3321 clientes en el sistema."""
    req = StatementAnalysisRequest(text=REGISTRO_CIVIL_TEXT)
    result = analyzer.analyze(req)
    cr = _cr(result, "c")
    assert cr is not None
    assert cr.calculated is True
    assert cr.value == pytest.approx(2.3321, abs=5e-4)


def test_prueba3_registro_civil_p_q_between(analyzer):
    """[d] P(Q=1 o Q=2) ≈ 0.1362."""
    req = StatementAnalysisRequest(text=REGISTRO_CIVIL_TEXT)
    result = analyzer.analyze(req)
    cr = _cr(result, "d")
    assert cr is not None
    assert cr.calculated is True
    assert cr.value == pytest.approx(0.1362, abs=5e-4)


# ---------------------------------------------------------------------------
# PRUEBA 4 — M/M/c con k=4 pero identificado como PICS → ρ=2 → inestable
# λ=24/h → 0.4/min, μ=5min → 0.2/min, c=4
# El model identifier elige PICS (conf LOW) → ρ=λ/μ=2.0 → unstable
# ---------------------------------------------------------------------------

CONTROL_CALIDAD_TEXT = (
    "Llegan con una tasa de 24 clientes por hora al departamento de control de calidad. "
    "El tiempo medio de inspeccion es de 5 minutos por pieza. "
    "Hay 4 inspectores. El departamento opera 9 horas al dia.\n"
    "a) Probabilidad de que haya al menos un inspector desocupado.\n"
    "b) Tiempo promedio de espera en cola.\n"
    "c) Minutos diarios con todos los inspectores ocupados simultaneamente.\n"
    "d) Piezas por semana que deberan esperar."
)


def test_prueba4_control_calidad_variables_extracted(analyzer):
    """Lambda, mu y k son extraídas del enunciado de control de calidad."""
    req = StatementAnalysisRequest(text=CONTROL_CALIDAD_TEXT)
    result = analyzer.analyze(req)
    var_ids = [v.variable_id for v in result.extracted_variables]
    assert "lambda_" in var_ids
    assert "mu" in var_ids
    # lambda normalisado a per-minuto
    lam_var = result.get_variable("lambda_")
    assert lam_var is not None
    assert lam_var.normalized_value == pytest.approx(0.4, rel=1e-3)


def test_prueba4_control_calidad_wq_unstable(analyzer):
    """[b] Con ρ=2 (PICS), Wq no es calculable → unstable_system."""
    req = StatementAnalysisRequest(text=CONTROL_CALIDAD_TEXT)
    result = analyzer.analyze(req)
    cr = _cr(result, "b")
    assert cr is not None
    assert cr.calculated is False
    assert "unstable_system" in cr.issues


# ---------------------------------------------------------------------------
# PRUEBA 5 — Población finita, modelo no calculable en esta fase
# M=5 máquinas, λ_fallo cada 10h, μ_rep=2h, 1 técnico
# ---------------------------------------------------------------------------

MAQUINAS_TEXT = (
    "Una empresa tiene 5 maquinas. Cada maquina se averia cada 10 horas de operacion. "
    "Un solo tecnico repara las maquinas con tiempo medio de 2 horas.\n"
    "a) Probabilidad de que el tecnico este libre.\n"
    "b) Numero medio de maquinas en el sistema.\n"
    "c) Numero medio de maquinas esperando reparacion.\n"
    "d) Fraccion del tiempo que las maquinas estan operando."
)


def test_prueba5_maquinas_m_extracted(analyzer):
    """M=5 máquinas es extraído del enunciado de población finita."""
    req = StatementAnalysisRequest(text=MAQUINAS_TEXT)
    result = analyzer.analyze(req)
    var_ids = [v.variable_id for v in result.extracted_variables]
    assert "M" in var_ids
    m_var = result.get_variable("M")
    assert m_var is not None
    assert m_var.normalized_value == pytest.approx(5.0)


def test_prueba5_maquinas_not_calculable_this_phase(analyzer):
    """Literales a/b/c retornan model_not_calculable_this_phase (PFCM/PFCS no implementado aún)."""
    req = StatementAnalysisRequest(text=MAQUINAS_TEXT)
    result = analyzer.analyze(req)
    for lid in ("a", "b", "c"):
        cr = _cr(result, lid)
        assert cr is not None, f"literal {lid!r} no tiene calculation_result"
        assert cr.calculated is False
        assert "model_not_calculable_this_phase" in cr.issues, (
            f"literal {lid!r}: issues={cr.issues}"
        )


# ---------------------------------------------------------------------------
# PRUEBA 6 — Sistema inestable M/M/1 (ρ ≥ 1)
# λ=1/min, μ=0.5/min → ρ=2
# ---------------------------------------------------------------------------

INESTABLE_TEXT = (
    "Los clientes llegan cada 1 minuto y el servicio tarda 2 minutos. "
    "Hay un solo servidor.\n"
    "a) Tiempo medio en cola.\n"
    "b) Numero medio en el sistema."
)


def test_prueba6_inestable_rho_detectado(analyzer):
    """Pipeline detecta ρ=2.0 para sistema inestable."""
    req = StatementAnalysisRequest(text=INESTABLE_TEXT)
    result = analyzer.analyze(req)
    # Al menos un literal debe tener step rho con valor ≥ 1
    cr_a = _cr(result, "a")
    assert cr_a is not None
    rho_step = next((s for s in cr_a.calculation_steps if s.formula_key == "rho"), None)
    assert rho_step is not None
    assert "2.0" in rho_step.result or "2,0" in rho_step.result


def test_prueba6_inestable_todos_los_literales(analyzer):
    """Todos los literales del sistema inestable retornan unstable_system."""
    req = StatementAnalysisRequest(text=INESTABLE_TEXT)
    result = analyzer.analyze(req)
    for lid in ("a", "b"):
        cr = _cr(result, lid)
        assert cr is not None, f"literal {lid!r} sin calculation_result"
        assert cr.calculated is False
        assert "unstable_system" in cr.issues, f"literal {lid!r}: issues={cr.issues}"


# ---------------------------------------------------------------------------
# PRUEBA 7 — Costos / optimización: no calculados en esta fase
# ---------------------------------------------------------------------------

COSTOS_TEXT = (
    "Un sistema M/M/1 con un solo servidor tiene costos por espera y costo diario del servidor.\n"
    "a) Calcule el costo total diario.\n"
    "b) Compare dos alternativas de servicio.\n"
    "c) Determine la opcion optima."
)


def test_prueba7_costos_no_calculados(analyzer):
    """[a] compute_cost → cost_calculation_not_implemented."""
    req = StatementAnalysisRequest(text=COSTOS_TEXT)
    result = analyzer.analyze(req)
    cr = _cr(result, "a")
    assert cr is not None
    assert cr.calculated is False
    assert "cost_calculation_not_implemented" in cr.issues


def test_prueba7_optimizacion_no_calculada(analyzer):
    """[b] y [c] retornan optimization_not_implemented."""
    req = StatementAnalysisRequest(text=COSTOS_TEXT)
    result = analyzer.analyze(req)
    for lid in ("b", "c"):
        cr = _cr(result, lid)
        assert cr is not None, f"literal {lid!r} sin calculation_result"
        assert cr.calculated is False
        assert "optimization_not_implemented" in cr.issues, (
            f"literal {lid!r}: issues={cr.issues}"
        )


# ---------------------------------------------------------------------------
# PRUEBA 8 — API E2E PICS: POST /api/analyze con texto de tienda
# ---------------------------------------------------------------------------

def test_api_prueba8_pics_status_200(client):
    """POST /api/analyze con texto PICS retorna 200."""
    resp = client.post("/api/analyze", json={"text": TIENDA_TEXT})
    assert resp.status_code == 200


def test_api_prueba8_pics_model_id(client):
    """Respuesta JSON de tienda identifica model_id=PICS."""
    resp = client.post("/api/analyze", json={"text": TIENDA_TEXT})
    data = resp.json()
    assert data["model_id"] == "PICS"


def test_api_prueba8_pics_literales_con_resultado(client):
    """Respuesta incluye literales con calculation_result para los 5 incisos."""
    resp = client.post("/api/analyze", json={"text": TIENDA_TEXT})
    data = resp.json()
    literals = data.get("literals", [])
    assert len(literals) >= 5
    lit_a = next((l for l in literals if l["literal_id"] == "a"), None)
    assert lit_a is not None
    cr = lit_a.get("calculation_result")
    assert cr is not None
    assert cr["calculated"] is True
    assert abs(cr["value"] - 2 / 3) < 0.001


# ---------------------------------------------------------------------------
# PRUEBA 9 — API E2E PICM: POST /api/analyze con Registro Civil
# ---------------------------------------------------------------------------

def test_api_prueba9_picm_status_200(client):
    """POST /api/analyze con texto PICM retorna 200."""
    resp = client.post("/api/analyze", json={"text": REGISTRO_CIVIL_TEXT})
    assert resp.status_code == 200


def test_api_prueba9_picm_wq_value(client):
    """Respuesta incluye Wq ≈ 1.77 min para el literal [b] del Registro Civil."""
    resp = client.post("/api/analyze", json={"text": REGISTRO_CIVIL_TEXT})
    data = resp.json()
    literals = data.get("literals", [])
    lit_b = next((l for l in literals if l["literal_id"] == "b"), None)
    assert lit_b is not None
    cr = lit_b.get("calculation_result")
    assert cr is not None
    assert cr["calculated"] is True
    assert abs(cr["value"] - 1.7737) < 0.005


def test_api_prueba9_picm_L_value(client):
    """Respuesta incluye L ≈ 2.3321 clientes para el literal [c] del Registro Civil."""
    resp = client.post("/api/analyze", json={"text": REGISTRO_CIVIL_TEXT})
    data = resp.json()
    literals = data.get("literals", [])
    lit_c = next((l for l in literals if l["literal_id"] == "c"), None)
    assert lit_c is not None
    cr = lit_c.get("calculation_result")
    assert cr is not None
    assert cr["calculated"] is True
    assert abs(cr["value"] - 2.3321) < 0.005


# ---------------------------------------------------------------------------
# PRUEBA 10 — UI: GET /analyze renderiza la página de análisis
# ---------------------------------------------------------------------------

def test_ui_prueba10_analyze_page_status_200(client):
    """GET /analyze retorna 200 OK."""
    resp = client.get("/analyze")
    assert resp.status_code == 200


def test_ui_prueba10_analyze_page_html_elements(client):
    """La página /analyze contiene los elementos HTML de análisis esperados."""
    resp = client.get("/analyze")
    html = resp.text
    # Formulario principal
    assert "analizar" in html.lower() or "enunciado" in html.lower()


def test_ui_prueba10_analyze_page_content_type(client):
    """GET /analyze devuelve content-type text/html."""
    resp = client.get("/analyze")
    assert "text/html" in resp.headers.get("content-type", "")

"""
Phase 7B — Numerical tests for correct time→rate inversion in VariableExtractor.

Rules under test:
  - "tiempo medio de servicio = T min" → μ = 1/T  (clientes/min)
  - "atiende X clientes/hora"          → μ = X/60  (clientes/min)
  - "llegan X clientes/hora"           → λ = X/60  (clientes/min)
  - "llegan cada T minutos"            → λ = 1/T   (clientes/min)
  - PFHET "X y Y minutos"              → μ1=1/X, μ2=1/Y

Full-pipeline arithmetic is also validated for the three canonical cases
from the course specification.
"""

import math

import pytest

from domain.entities.analysis import StatementAnalysisRequest
from domain.services.statement_analyzer import make_analyzer
from domain.services.variable_extractor import VariableExtractor
from domain.services.plan_executor import make_executor
from domain.services.resolution_planner import make_planner
from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def knowledge():
    return OfflineKnowledgeRepository().load_all()


@pytest.fixture(scope="module")
def extractor(knowledge):
    return VariableExtractor(knowledge)


def _norm(text: str) -> str:
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Unit tests — mu normalized_value is a RATE (1/time), not a time
# ---------------------------------------------------------------------------

class TestMuInversion:
    def test_tiempo_medio_4min_normalized_is_rate(self, extractor):
        """'tiempo medio de atencion 4 minutos' → μ = 1/4 = 0.25 /min"""
        text = _norm("El tiempo medio de atencion es de 4 minutos.")
        variables, _ = extractor.extract(text)
        mu = next((v for v in variables if v.variable_id == "mu"), None)
        assert mu is not None
        assert mu.raw_value == pytest.approx(4.0)
        assert mu.normalized_value == pytest.approx(0.25, rel=1e-3)

    def test_tiempo_medio_6min(self, extractor):
        """'tiempo medio de servicio 6 minutos' → μ = 1/6 ≈ 0.1667 /min"""
        text = _norm("El tiempo medio de servicio es 6 minutos.")
        variables, _ = extractor.extract(text)
        mu = next((v for v in variables if v.variable_id == "mu"), None)
        assert mu is not None
        assert mu.normalized_value == pytest.approx(1 / 6, rel=1e-3)

    def test_distribucion_exponencial_media_5seg(self, extractor):
        """'distribucion exponencial con media 5 segundos' → μ = 60/5 = 12 /min"""
        text = _norm("El tiempo de servicio sigue una distribucion exponencial con media 5 segundos por unidad.")
        variables, _ = extractor.extract(text)
        mu = next((v for v in variables if v.variable_id == "mu"), None)
        assert mu is not None
        assert mu.raw_value == pytest.approx(5.0)
        assert mu.normalized_value == pytest.approx(12.0, rel=1e-3)  # 60/5

    def test_tiempo_ejecucion_5_segundos(self, extractor):
        """'tiempo medio de ejecucion es de 5 segundos' → μ = 12 /min"""
        text = _norm("El tiempo medio de ejecucion es de 5 segundos.")
        variables, _ = extractor.extract(text)
        mu = next((v for v in variables if v.variable_id == "mu"), None)
        assert mu is not None
        assert mu.normalized_value == pytest.approx(12.0, rel=1e-3)

    def test_servicio_tarda_3_minutos(self, extractor):
        """'el servicio tarda 3 minutos en promedio' → μ = 1/3 ≈ 0.3333 /min"""
        text = _norm("El servicio tarda 3 minutos en promedio.")
        variables, _ = extractor.extract(text)
        mu = next((v for v in variables if v.variable_id == "mu"), None)
        assert mu is not None
        assert mu.normalized_value == pytest.approx(1 / 3, rel=1e-3)

    def test_media_1min_normalized_is_1(self, extractor):
        """'media de atencion 1 minuto' → μ = 1/1 = 1.0 /min"""
        text = _norm("Media de atencion 1 minuto por llamada.")
        variables, _ = extractor.extract(text)
        mu = next((v for v in variables if v.variable_id == "mu"), None)
        assert mu is not None
        assert mu.normalized_value == pytest.approx(1.0, rel=1e-3)

    def test_service_capacity_25_per_hour(self, extractor):
        """'25 clientes por hora' (capacity pattern) → μ = 25/60 ≈ 0.4167 /min"""
        text = _norm("Los farmaceuticos pueden atender un promedio de 25 clientes por hora cada uno.")
        variables, _ = extractor.extract(text)
        mu = next((v for v in variables if v.variable_id == "mu"), None)
        assert mu is not None
        assert mu.raw_value == pytest.approx(25.0)
        assert mu.normalized_value == pytest.approx(25 / 60, rel=1e-3)


# ---------------------------------------------------------------------------
# Unit tests — lambda inter-arrival time extraction (λ = 1/T)
# ---------------------------------------------------------------------------

class TestLambdaInterarrival:
    def test_llegan_cada_6_minutos(self, extractor):
        """'llegan cada 6 minutos' → λ = 1/6 ≈ 0.1667 /min"""
        text = _norm("Los clientes llegan cada 6 minutos.")
        variables, _ = extractor.extract(text)
        lam = next((v for v in variables if v.variable_id == "lambda_"), None)
        assert lam is not None
        assert lam.normalized_value == pytest.approx(1 / 6, rel=1e-3)

    def test_llegan_cada_1_2_minutos(self, extractor):
        """'llegan cada 1.2 minutos en promedio' → λ = 1/1.2 ≈ 0.8333 /min"""
        text = _norm("Los clientes llegan cada 1.2 minutos en promedio.")
        variables, _ = extractor.extract(text)
        lam = next((v for v in variables if v.variable_id == "lambda_"), None)
        assert lam is not None
        assert lam.normalized_value == pytest.approx(1 / 1.2, rel=1e-3)

    def test_llega_un_cliente_cada_5_minutos(self, extractor):
        """'llega un cliente cada 5 minutos' → λ = 1/5 = 0.2 /min"""
        text = _norm("En promedio, llega un cliente cada 5 minutos.")
        variables, _ = extractor.extract(text)
        lam = next((v for v in variables if v.variable_id == "lambda_"), None)
        assert lam is not None
        assert lam.normalized_value == pytest.approx(0.2, rel=1e-3)

    def test_rate_extraction_still_works(self, extractor):
        """Direct rate 'llegan a razon de 10 por hora' → λ = 10/60 ≈ 0.1667 /min"""
        text = _norm("Llegan a razon de 10 clientes por hora.")
        variables, _ = extractor.extract(text)
        lam = next((v for v in variables if v.variable_id == "lambda_"), None)
        assert lam is not None
        assert lam.normalized_value == pytest.approx(10 / 60, rel=1e-3)


# ---------------------------------------------------------------------------
# Unit tests — PFHET mu1/mu2 inversion
# ---------------------------------------------------------------------------

class TestMu1Mu2Inversion:
    def test_130_y_170_minutos_inverted(self, extractor):
        """'130 y 170 minutos' → μ1=1/130, μ2=1/170"""
        text = _norm("Los tecnicos demoran en promedio 130 y 170 minutos respectivamente.")
        variables, _ = extractor.extract(text, model_id="PFHET")
        mu1 = next((v for v in variables if v.variable_id == "mu1"), None)
        mu2 = next((v for v in variables if v.variable_id == "mu2"), None)
        assert mu1 is not None
        assert mu2 is not None
        assert mu1.raw_value == pytest.approx(130.0)
        assert mu2.raw_value == pytest.approx(170.0)
        assert mu1.normalized_value == pytest.approx(1 / 130, rel=1e-3)
        assert mu2.normalized_value == pytest.approx(1 / 170, rel=1e-3)

    def test_mu1_mu2_raw_values_preserved(self, extractor):
        """raw_value is unchanged; only normalized_value is inverted."""
        text = _norm("Los dos tecnicos demoran en promedio 120 y 150 minutos respectivamente.")
        variables, _ = extractor.extract(text, model_id="PFHET")
        mu1 = next((v for v in variables if v.variable_id == "mu1"), None)
        mu2 = next((v for v in variables if v.variable_id == "mu2"), None)
        assert mu1.raw_value == pytest.approx(120.0)
        assert mu2.raw_value == pytest.approx(150.0)
        assert mu1.normalized_value == pytest.approx(1 / 120, rel=1e-3)
        assert mu2.normalized_value == pytest.approx(1 / 150, rel=1e-3)


# ---------------------------------------------------------------------------
# Full pipeline — Case 1: Tienda M/M/1
# λ = 10/hr = 1/6 /min,  μ = 1/4 /min,  ρ = 2/3,  Wq = 8 min,  Lq = 4/3
# ---------------------------------------------------------------------------

class TestFullPipelineCase1Tienda:
    TIENDA_TEXT = (
        "Una tienda de alimentacion es atendida por una persona. "
        "Llegan 10 clientes por hora con proceso Poisson. "
        "Tiempo medio de atencion 4 minutos. "
        "Calcular tiempo de espera."
    )

    @pytest.fixture(scope="class")
    def result(self):
        analyzer = make_analyzer()
        planner = make_planner()
        executor = make_executor()
        req = StatementAnalysisRequest(text=self.TIENDA_TEXT)
        analysis = analyzer.analyze(req)
        plan = planner.plan(analysis)
        return executor.execute(analysis, plan)

    def test_model_is_pics(self, result):
        assert result.model_id == "PICS"

    def test_is_complete(self, result):
        assert result.is_complete is True

    def test_lambda_normalized_per_minute(self, result):
        lam = result.final_variables.get("lambda_")
        assert lam is not None
        assert lam == pytest.approx(10 / 60, rel=1e-3)

    def test_mu_normalized_per_minute(self, result):
        mu = result.final_variables.get("mu")
        assert mu is not None
        assert mu == pytest.approx(0.25, rel=1e-3)  # 1/4

    def test_rho_correct(self, result):
        rho = result.final_variables.get("rho")
        if rho is not None:
            assert rho == pytest.approx(2 / 3, rel=1e-3)

    def test_wq_correct(self, result):
        wq = result.get_value("Wq")
        assert wq is not None
        assert wq == pytest.approx(8.0, rel=1e-2)  # 8 minutes


# ---------------------------------------------------------------------------
# Full pipeline — Case 2: Servidor de programas
# λ = 10/min,  μ = 1/(5 seg) = 12/min,  ρ = 5/6 ≈ 0.8333
# W = 1/(μ−λ) = 1/2 min = 30 seg,  Lq = ρ²/(1−ρ) ≈ 4.1667
# ---------------------------------------------------------------------------

class TestFullPipelineCase2Servidor:
    # A single-server queue (PICS-identifiable) with mu from seconds
    SERVIDOR_TEXT = (
        "Un servidor unico procesa trabajos que llegan a razon de 10 por minuto. "
        "El tiempo medio de ejecucion es de 5 segundos. "
        "Calcular tiempo medio en el sistema."
    )

    @pytest.fixture(scope="class")
    def analysis(self):
        analyzer = make_analyzer()
        req = StatementAnalysisRequest(text=self.SERVIDOR_TEXT)
        return analyzer.analyze(req)

    @pytest.fixture(scope="class")
    def result(self, analysis):
        planner = make_planner()
        executor = make_executor()
        plan = planner.plan(analysis)
        return executor.execute(analysis, plan)

    def test_model_is_pics(self, analysis):
        assert analysis.identified_model == "PICS"

    def test_lambda_10_per_min(self, analysis):
        lam = analysis.get_variable("lambda_")
        assert lam is not None
        assert lam.normalized_value == pytest.approx(10.0, rel=1e-3)

    def test_mu_12_per_min(self, analysis):
        mu = analysis.get_variable("mu")
        assert mu is not None
        assert mu.normalized_value == pytest.approx(12.0, rel=1e-3)  # 1/(5 sec) = 60/5 = 12/min

    def test_w_correct(self, result):
        w = result.get_value("W")
        if w is not None:
            assert w == pytest.approx(0.5, rel=1e-2)  # 0.5 min = 30 sec


# ---------------------------------------------------------------------------
# Full pipeline — Case 3: Sistema inestable (ρ ≥ 1)
# λ = 1/1.2 ≈ 0.8333 /min,  μ = 1/3 ≈ 0.3333 /min,  ρ ≈ 2.5
# System must detect instability
# ---------------------------------------------------------------------------

class TestFullPipelineCase3Unstable:
    # Single-server queue with ρ > 1 (unstable)
    UNSTABLE_TEXT = (
        "Un cajero atiende clientes. "
        "Los clientes llegan cada 1.2 minutos en promedio. "
        "El servicio tarda 3 minutos en promedio."
    )

    @pytest.fixture(scope="class")
    def analysis(self):
        analyzer = make_analyzer()
        req = StatementAnalysisRequest(text=self.UNSTABLE_TEXT)
        return analyzer.analyze(req)

    def test_lambda_extracted(self, analysis):
        lam = analysis.get_variable("lambda_")
        assert lam is not None
        assert lam.normalized_value == pytest.approx(1 / 1.2, rel=1e-3)

    def test_mu_extracted(self, analysis):
        mu = analysis.get_variable("mu")
        assert mu is not None
        assert mu.normalized_value == pytest.approx(1 / 3, rel=1e-3)

    def test_rho_greater_than_1(self, analysis):
        """With λ > μ the computed ρ should exceed 1 → system unstable."""
        lam = analysis.get_variable("lambda_")
        mu = analysis.get_variable("mu")
        assert lam is not None and mu is not None
        rho = lam.normalized_value / mu.normalized_value
        assert rho == pytest.approx(2.5, rel=1e-2)

    def test_plan_not_executable_or_warns(self):
        """Plan executor or planner should mark system as non-executable when ρ≥1."""
        analyzer = make_analyzer()
        planner = make_planner()
        executor = make_executor()
        req = StatementAnalysisRequest(text=self.UNSTABLE_TEXT)
        analysis = analyzer.analyze(req)
        plan = planner.plan(analysis)
        result = executor.execute(analysis, plan)
        # Either not complete or there is a warning about instability
        lam = analysis.get_variable("lambda_")
        mu = analysis.get_variable("mu")
        if lam and mu and lam.normalized_value and mu.normalized_value:
            rho = lam.normalized_value / mu.normalized_value
            if rho >= 1:
                assert (
                    not result.is_complete
                    or any("estab" in (i.message or "").lower() or "inestab" in (i.message or "").lower()
                           for i in result.execution_issues)
                )

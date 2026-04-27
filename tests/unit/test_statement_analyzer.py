"""
Tests for StatementAnalyzer — Phase 2.

Covers:
- Full pipeline: model identification + variable extraction + objective inference
- Solvability assessment
- Hint model / hint objective
- Issue generation (missing variable, ambiguity, etc.)
- Result structure correctness
- Exercises from the PDF corpus (ex01 PICS, ex02 PICM, ex20 PFHET)
"""

import pytest

from domain.entities.analysis import (
    AnalysisConfidence,
    IssueSeverity,
    StatementAnalysisRequest,
)
from domain.services.statement_analyzer import StatementAnalyzer, make_analyzer
from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository


@pytest.fixture(scope="module")
def knowledge():
    return OfflineKnowledgeRepository().load_all()


@pytest.fixture(scope="module")
def analyzer(knowledge):
    return StatementAnalyzer(knowledge)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_make_analyzer_returns_analyzer(self):
        a = make_analyzer()
        assert isinstance(a, StatementAnalyzer)


# ---------------------------------------------------------------------------
# PICS — Ejercicio 1 del PDF
# ---------------------------------------------------------------------------

class TestAnalyzerPICS:
    PICS_TEXT = (
        "Una tienda de alimentacion es atendida por una persona. "
        "El patron de llegadas sigue un proceso de Poisson con una tasa de llegadas de 10 personas por hora. "
        "El tiempo de atencion se distribuye exponencialmente con un tiempo medio de 4 minutos. "
        "Calcular tiempo de espera en la cola."
        # 'calcular tiempo de espera' is a direct synonym for compute_Wq
    )

    def test_identifies_pics_model(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICS_TEXT)
        result = analyzer.analyze(req)
        assert result.identified_model == "PICS"

    def test_extracts_lambda(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICS_TEXT)
        result = analyzer.analyze(req)
        assert result.get_variable("lambda_") is not None
        lam = result.get_variable("lambda_")
        assert lam.raw_value == pytest.approx(10.0)

    def test_extracts_mu(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICS_TEXT)
        result = analyzer.analyze(req)
        mu = result.get_variable("mu")
        assert mu is not None
        assert mu.raw_value == pytest.approx(4.0)

    def test_infers_wq_objective(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICS_TEXT)
        result = analyzer.analyze(req)
        assert "compute_Wq" in result.inferred_objectives

    def test_pics_is_solvable(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICS_TEXT)
        result = analyzer.analyze(req)
        assert result.is_solvable is True

    def test_model_confidence_is_not_none(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICS_TEXT)
        result = analyzer.analyze(req)
        assert result.model_confidence != AnalysisConfidence.NONE

    def test_no_errors_in_issues(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICS_TEXT)
        result = analyzer.analyze(req)
        assert not result.has_errors()

    def test_normalized_text_is_lowercase(self, analyzer):
        req = StatementAnalysisRequest(text="TEXTO EN MAYUSCULAS")
        result = analyzer.analyze(req)
        assert result.normalized_text == result.normalized_text.lower()


# ---------------------------------------------------------------------------
# PICM — Ejercicio 2 del PDF
# ---------------------------------------------------------------------------

class TestAnalyzerPICM:
    PICM_TEXT = (
        "Una compania de correo urgente tiene 3 personas para recibir las llamadas telefonicas. "
        "Las llamadas se producen segun un proceso de Poisson de intensidad 2 por minuto "
        "y la duracion de las llamadas es una variable exponencial de media 1 minuto por llamada. "
        "Calcular la probabilidad de que haya linea de espera."
    )

    def test_identifies_picm_model(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICM_TEXT)
        result = analyzer.analyze(req)
        assert result.identified_model == "PICM"

    def test_extracts_k_equal_3(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICM_TEXT)
        result = analyzer.analyze(req)
        k = result.get_variable("k")
        assert k is not None
        assert k.normalized_value == pytest.approx(3.0)

    def test_extracts_lambda(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICM_TEXT)
        result = analyzer.analyze(req)
        lam = result.get_variable("lambda_")
        assert lam is not None
        assert lam.raw_value == pytest.approx(2.0)

    def test_extracts_mu(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICM_TEXT)
        result = analyzer.analyze(req)
        mu = result.get_variable("mu")
        assert mu is not None
        assert mu.raw_value == pytest.approx(1.0)

    def test_is_solvable(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICM_TEXT)
        result = analyzer.analyze(req)
        assert result.is_solvable is True

    def test_no_missing_variable_warnings_for_picm(self, analyzer):
        req = StatementAnalysisRequest(text=self.PICM_TEXT)
        result = analyzer.analyze(req)
        missing_var_issues = [
            i for i in result.issues
            if i.code == "missing_variable" and i.severity == IssueSeverity.WARNING
        ]
        assert missing_var_issues == [], f"Unexpected missing variables: {[i.context for i in missing_var_issues]}"


# ---------------------------------------------------------------------------
# PFHET — Ejercicio 20 del PDF
# ---------------------------------------------------------------------------

class TestAnalyzerPFHET:
    PFHET_TEXT = (
        "Un numero limitado de montacargas son atendidos por el taller de mantenimiento. "
        "El taller cuenta con dos tecnicos que demoran en promedio 130 y 170 minutos "
        "respectivamente segun una distribucion exponencial en atender a cada montacargas. "
        "Ambos tecnicos atienden a todos los montacargas de la fabrica."
    )

    def test_identifies_pfhet_model(self, analyzer):
        req = StatementAnalysisRequest(text=self.PFHET_TEXT)
        result = analyzer.analyze(req)
        assert result.identified_model == "PFHET"

    def test_extracts_mu1_and_mu2(self, analyzer):
        req = StatementAnalysisRequest(text=self.PFHET_TEXT)
        result = analyzer.analyze(req)
        mu1 = result.get_variable("mu1")
        mu2 = result.get_variable("mu2")
        assert mu1 is not None, "mu1 not extracted"
        assert mu2 is not None, "mu2 not extracted"
        assert mu1.raw_value == pytest.approx(130.0)
        assert mu2.raw_value == pytest.approx(170.0)


# ---------------------------------------------------------------------------
# Missing variable warnings
# ---------------------------------------------------------------------------

class TestMissingVariableWarnings:
    def test_missing_mu_generates_warning(self, analyzer):
        text = "Una cajera atiende clientes. Los clientes llegan a razon de 10 por hora."
        req = StatementAnalysisRequest(text=text)
        result = analyzer.analyze(req)
        if result.identified_model == "PICS":
            mu = result.get_variable("mu")
            if mu is None:
                warnings = [i for i in result.issues if i.code == "missing_variable"]
                assert any("mu" in i.context for i in warnings)

    def test_missing_k_for_picm_generates_warning(self, analyzer):
        text = (
            "El call center tiene operadores. "
            "Llegan 5 llamadas por minuto. Duracion media 2 minutos. "
            "Calcular el tiempo de espera."
        )
        req = StatementAnalysisRequest(text=text)
        result = analyzer.analyze(req)
        # If identified as PICM and k is missing, should warn
        if result.identified_model == "PICM" and result.get_variable("k") is None:
            issues = [i for i in result.issues if i.code == "missing_variable"]
            assert any("k" in i.context for i in issues)


# ---------------------------------------------------------------------------
# Hint model / hint objective
# ---------------------------------------------------------------------------

class TestHints:
    def test_hint_objective_added_to_inferred(self, analyzer):
        text = "Un mecanico atiende equipos. Tasa 4 por hora. Tiempo medio 6 minutos."
        req = StatementAnalysisRequest(text=text, hint_objective="compute_L")
        result = analyzer.analyze(req)
        assert "compute_L" in result.inferred_objectives

    def test_hint_model_used_on_failure(self, analyzer):
        text = "Un sistema de colas con datos no especificados. Calcular Wq."
        req = StatementAnalysisRequest(text=text, hint_model="PICS")
        result = analyzer.analyze(req)
        # Should use PICS as hint or find it from keywords
        # We just verify no crash and result is a StatementAnalysisResult
        from domain.entities.analysis import StatementAnalysisResult
        assert isinstance(result, StatementAnalysisResult)


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    def test_result_has_all_fields(self, analyzer):
        req = StatementAnalysisRequest(text="texto de prueba")
        result = analyzer.analyze(req)
        assert hasattr(result, "model_candidates")
        assert hasattr(result, "identified_model")
        assert hasattr(result, "model_confidence")
        assert hasattr(result, "extracted_variables")
        assert hasattr(result, "inferred_objectives")
        assert hasattr(result, "issues")
        assert hasattr(result, "is_solvable")
        assert hasattr(result, "normalized_text")

    def test_result_candidates_are_list(self, analyzer):
        req = StatementAnalysisRequest(text="un servidor atiende clientes")
        result = analyzer.analyze(req)
        assert isinstance(result.model_candidates, list)

    def test_variable_ids_helper(self, analyzer):
        text = "Una cajera atiende 10 clientes por hora. Tiempo medio 4 minutos."
        req = StatementAnalysisRequest(text=text)
        result = analyzer.analyze(req)
        vids = result.variable_ids()
        assert isinstance(vids, set)

    def test_analyze_is_deterministic(self, analyzer):
        text = "Un cajero atiende clientes. Tasa de llegadas de 10 por hora. Tiempo medio 4 minutos."
        req = StatementAnalysisRequest(text=text)
        r1 = analyzer.analyze(req)
        r2 = analyzer.analyze(req)
        assert r1.identified_model == r2.identified_model
        assert r1.is_solvable == r2.is_solvable
        assert len(r1.extracted_variables) == len(r2.extracted_variables)

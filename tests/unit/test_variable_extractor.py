"""
Tests for VariableExtractor — Phase 2.

Exercises:
- lambda_ extraction from various PDF-attested phrasings
- mu extraction (time context and capacity context)
- k extraction (number before role noun)
- M extraction (finite population)
- mu1/mu2 joint extraction for PFHET
- Unit normalization to per-minute
- No crash on empty or malformed input
"""

import pytest

from domain.services.variable_extractor import VariableExtractor
from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository


@pytest.fixture(scope="module")
def knowledge():
    return OfflineKnowledgeRepository().load_all()


@pytest.fixture(scope="module")
def extractor(knowledge):
    return VariableExtractor(knowledge)


def _norm(text: str) -> str:
    """Same normalization the analyzer applies."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# lambda_ extraction
# ---------------------------------------------------------------------------

class TestExtractLambda:
    def test_tasa_de_llegadas_por_hora(self, extractor):
        text = _norm("El patron de llegadas sigue un proceso de Poisson con una tasa de llegadas de 10 personas por hora.")
        variables, issues = extractor.extract(text)
        var = next((v for v in variables if v.variable_id == "lambda_"), None)
        assert var is not None
        assert var.raw_value == pytest.approx(10.0)

    def test_intensidad_por_minuto(self, extractor):
        text = _norm("Las llamadas se producen segun un proceso de Poisson de intensidad 2 por minuto.")
        variables, issues = extractor.extract(text)
        var = next((v for v in variables if v.variable_id == "lambda_"), None)
        assert var is not None
        assert var.raw_value == pytest.approx(2.0)
        # Normalized: already in per minute
        assert var.normalized_value == pytest.approx(2.0, abs=1e-4)

    def test_afluencia_por_hora(self, extractor):
        text = _norm("Se estima en 60 personas por hora la afluencia de clientes.")
        variables, issues = extractor.extract(text)
        var = next((v for v in variables if v.variable_id == "lambda_"), None)
        assert var is not None
        assert var.raw_value == pytest.approx(60.0)
        # Normalized: 60/hora = 1/min
        assert var.normalized_value == pytest.approx(1.0, abs=1e-4)

    def test_rate_per_hora_normalization(self, extractor):
        text = _norm("Tasa de llegada de 30 clientes por hora.")
        variables, _ = extractor.extract(text)
        lam = next((v for v in variables if v.variable_id == "lambda_"), None)
        assert lam is not None
        assert lam.normalized_value == pytest.approx(0.5, abs=1e-4)  # 30/60

    def test_rate_per_minuto_normalization(self, extractor):
        text = _norm("Llegan a razon de 5 clientes por minuto.")
        variables, _ = extractor.extract(text)
        lam = next((v for v in variables if v.variable_id == "lambda_"), None)
        assert lam is not None
        assert lam.normalized_value == pytest.approx(5.0, abs=1e-4)


# ---------------------------------------------------------------------------
# mu extraction
# ---------------------------------------------------------------------------

class TestExtractMu:
    def test_tiempo_medio_minutos(self, extractor):
        text = _norm("El tiempo de atencion se distribuye exponencialmente con un tiempo medio de 4 minutos.")
        variables, issues = extractor.extract(text)
        var = next((v for v in variables if v.variable_id == "mu"), None)
        assert var is not None
        assert var.raw_value == pytest.approx(4.0)

    def test_media_de_minutos(self, extractor):
        text = _norm("La duracion de las llamadas es una variable exponencial de media 1 minuto por llamada.")
        variables, issues = extractor.extract(text)
        var = next((v for v in variables if v.variable_id == "mu"), None)
        assert var is not None
        assert var.raw_value == pytest.approx(1.0)

    def test_capacity_clientes_por_hora(self, extractor):
        text = _norm("Los farmaceuticos pueden atender un promedio de 25 clientes por hora cada uno.")
        variables, issues = extractor.extract(text)
        var = next((v for v in variables if v.variable_id == "mu"), None)
        assert var is not None
        assert var.raw_value == pytest.approx(25.0)

    def test_tiempo_medio_distribution_exponencial(self, extractor):
        text = _norm("El tiempo de servicio sigue una distribucion exponencial de media 6 minutos.")
        variables, _ = extractor.extract(text)
        mu = next((v for v in variables if v.variable_id == "mu"), None)
        assert mu is not None
        assert mu.raw_value == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# k extraction
# ---------------------------------------------------------------------------

class TestExtractK:
    def test_tres_personas(self, extractor):
        text = _norm("Una compania tiene 3 personas para recibir las llamadas.")
        variables, issues = extractor.extract(text, model_id="PICM")
        var = next((v for v in variables if v.variable_id == "k"), None)
        assert var is not None
        assert var.normalized_value == pytest.approx(3.0)

    def test_cinco_tecnicos(self, extractor):
        text = _norm("El departamento cuenta con 5 tecnicos especializados.")
        variables, issues = extractor.extract(text, model_id="PICM")
        var = next((v for v in variables if v.variable_id == "k"), None)
        assert var is not None
        assert var.normalized_value == pytest.approx(5.0)

    def test_dos_operarios(self, extractor):
        text = _norm("La empresa dispone de 2 operarios para mantenimiento.")
        variables, issues = extractor.extract(text, model_id="PICM")
        var = next((v for v in variables if v.variable_id == "k"), None)
        assert var is not None
        assert var.normalized_value == pytest.approx(2.0)

    def test_k_is_integer(self, extractor):
        text = _norm("Hay 4 cajeros en la sucursal bancaria.")
        variables, _ = extractor.extract(text)
        k = next((v for v in variables if v.variable_id == "k"), None)
        assert k is not None
        assert k.normalized_value == 4.0


# ---------------------------------------------------------------------------
# M extraction (finite population)
# ---------------------------------------------------------------------------

class TestExtractM:
    def test_cinco_aviones(self, extractor):
        text = _norm("La base aerea cuenta con 5 aviones.")
        variables, issues = extractor.extract(text, model_id="PFCS")
        var = next((v for v in variables if v.variable_id == "M"), None)
        assert var is not None
        assert var.normalized_value == pytest.approx(5.0)

    def test_montacargas_numero_limitado(self, extractor):
        text = _norm("Un numero limitado de 10 montacargas son atendidos por el taller.")
        variables, issues = extractor.extract(text, model_id="PFCS")
        var = next((v for v in variables if v.variable_id == "M"), None)
        assert var is not None

    def test_m_not_extracted_for_infinite_population(self, extractor):
        """For PICS model, M should not be extracted."""
        text = _norm("Los clientes llegan a razon de 10 por hora. Un cajero atiende con media 4 minutos.")
        variables, _ = extractor.extract(text, model_id="PICS")
        m_var = next((v for v in variables if v.variable_id == "M"), None)
        assert m_var is None


# ---------------------------------------------------------------------------
# PFHET mu1/mu2 extraction
# ---------------------------------------------------------------------------

class TestExtractMu1Mu2:
    def test_130_y_170_minutos(self, extractor):
        text = _norm("Los tecnicos demoran en promedio 130 y 170 minutos respectivamente.")
        variables, issues = extractor.extract(text, model_id="PFHET")
        mu1 = next((v for v in variables if v.variable_id == "mu1"), None)
        mu2 = next((v for v in variables if v.variable_id == "mu2"), None)
        assert mu1 is not None
        assert mu2 is not None
        assert mu1.raw_value == pytest.approx(130.0)
        assert mu2.raw_value == pytest.approx(170.0)

    def test_120_y_150_minutos(self, extractor):
        # Joint pattern requires 'N y M minutos' adjacent — use canonical phrasing
        text = _norm("Los dos tecnicos demoran en promedio 120 y 150 minutos respectivamente.")
        variables, issues = extractor.extract(text, model_id="PFHET")
        mu1 = next((v for v in variables if v.variable_id == "mu1"), None)
        mu2 = next((v for v in variables if v.variable_id == "mu2"), None)
        assert mu1 is not None
        assert mu2 is not None
        assert mu1.raw_value == pytest.approx(120.0)
        assert mu2.raw_value == pytest.approx(150.0)

    def test_mu1_mu2_not_extracted_for_pics(self, extractor):
        text = _norm("Un tecnico atiende con tiempo medio de 6 minutos. Llegan 4 por hora.")
        variables, _ = extractor.extract(text, model_id="PICS")
        mu1 = next((v for v in variables if v.variable_id == "mu1"), None)
        mu2 = next((v for v in variables if v.variable_id == "mu2"), None)
        assert mu1 is None
        assert mu2 is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_text_returns_no_variables(self, extractor):
        variables, issues = extractor.extract("")
        assert variables == []

    def test_no_crash_on_irrelevant_text(self, extractor):
        variables, issues = extractor.extract("este texto no tiene datos numericos relevantes.")
        assert isinstance(variables, list)
        assert isinstance(issues, list)

    def test_extract_returns_lists(self, extractor):
        variables, issues = extractor.extract("texto de prueba 10 clientes por hora")
        assert isinstance(variables, list)
        assert isinstance(issues, list)

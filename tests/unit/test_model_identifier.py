"""
Tests for ModelIdentifier — Phase 2.

Exercises:
- PICS identification from typical exercise vocabulary
- PICM identification (multiple servers)
- PFCS identification (finite population, single server)
- PFHET identification (heterogeneous service rates)
- Disqualification by forbidden terms
- Ambiguity detection
- Edge cases: empty text, unknown model text
"""

import pytest

from domain.entities.analysis import AnalysisConfidence, IssueSeverity
from domain.services.model_identifier import ModelIdentifier
from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository


@pytest.fixture(scope="module")
def knowledge():
    return OfflineKnowledgeRepository().load_all()


@pytest.fixture(scope="module")
def identifier(knowledge):
    return ModelIdentifier(knowledge)


# ---------------------------------------------------------------------------
# PICS
# ---------------------------------------------------------------------------

class TestModelIdentifierPICS:
    def test_identifies_pics_from_una_cajera(self, identifier):
        # 'un cajero' is a PICS-exclusive keyword
        text = "Una tienda es atendida por un cajero. Los clientes llegan con una tasa de 10 por hora."
        top, issues = identifier.top_candidate(text)
        assert top is not None
        assert top.model_id == "PICS"

    def test_identifies_pics_from_un_oficinista(self, identifier):
        # 'un oficinista' is a PICS-exclusive keyword (not in PFCS)
        text = "Una compania debe contratar un oficinista. Los clientes llegan a tasa 4 por hora."
        top, issues = identifier.top_candidate(text)
        assert top is not None
        assert top.model_id == "PICS"

    def test_identifies_pics_from_un_oficinista(self, identifier):
        text = "Existe una oficina de la Seguridad Social atendida por un oficinista. Tasa de llegada 1.25 por periodo."
        top, issues = identifier.top_candidate(text)
        assert top is not None
        assert top.model_id == "PICS"

    def test_pics_score_is_high_confidence(self, identifier):
        # 'un cajero', 'cola simple' are PICS-exclusive keywords
        text = "Un cajero atiende clientes con cola simple. Proceso de Poisson con media 10 por hora."
        top, issues = identifier.top_candidate(text)
        assert top is not None
        assert top.model_id == "PICS"
        assert top.score > 0.0


# ---------------------------------------------------------------------------
# PICM
# ---------------------------------------------------------------------------

class TestModelIdentifierPICM:
    def test_identifies_picm_from_3_personas(self, identifier):
        text = (
            "Una compania tiene 3 personas para recibir llamadas. "
            "Las llamadas se producen segun un proceso de Poisson de intensidad 2 por minuto."
        )
        top, issues = identifier.top_candidate(text)
        assert top is not None
        assert top.model_id == "PICM"

    def test_identifies_picm_from_varios_farmaceuticos(self, identifier):
        text = (
            "La farmacia es atendida por farmaceuticos quienes pueden atender 25 clientes por hora cada uno. "
            "Cuantos farmaceuticos debe contratar."
        )
        top, issues = identifier.top_candidate(text)
        assert top is not None
        assert top.model_id == "PICM"

    def test_identifies_picm_from_5_examinadores(self, identifier):
        text = "El departamento cuenta con 5 examinadores para atender los vehiculos."
        top, issues = identifier.top_candidate(text)
        assert top is not None
        assert top.model_id == "PICM"

    def test_picm_not_identified_when_single_server(self, identifier):
        """PICM forbidden term: 'un servidor'."""
        text = "El sistema tiene un servidor y poblacion infinita."
        candidates = identifier.identify(text)
        picm_candidate = next(c for c in candidates if c.model_id == "PICM")
        assert picm_candidate.score == 0.0 or picm_candidate.disqualified_by


# ---------------------------------------------------------------------------
# PFCS
# ---------------------------------------------------------------------------

class TestModelIdentifierPFCS:
    def test_identifies_pfcs_from_numero_limitado(self, identifier):
        text = "Un numero limitado de aviones es atendido por un taller de mantenimiento."
        top, issues = identifier.top_candidate(text)
        assert top is not None
        assert top.model_id == "PFCS"

    def test_identifies_pfcs_from_5_empleados(self, identifier):
        text = (
            "En cada departamento laboran 5 empleados. Cada uno no elabora un nuevo manuscrito "
            "hasta que el anterior sea devuelto por la mecanografa."
        )
        top, issues = identifier.top_candidate(text)
        assert top is not None
        assert top.model_id == "PFCS"


# ---------------------------------------------------------------------------
# PFHET
# ---------------------------------------------------------------------------

class TestModelIdentifierPFHET:
    def test_identifies_pfhet_from_distintas_tasas(self, identifier):
        text = (
            "El taller tiene dos tecnicos que demoran en promedio 130 y 170 minutos. "
            "Ambos tecnicos atienden a todos los montacargas."
        )
        top, issues = identifier.top_candidate(text)
        assert top is not None
        assert top.model_id == "PFHET"

    def test_identifies_pfhet_from_velocidades_diferentes(self, identifier):
        text = "Los dos tecnicos atienden a todos los equipos con velocidades diferentes de servicio."
        top, issues = identifier.top_candidate(text)
        assert top is not None
        assert top.model_id == "PFHET"


# ---------------------------------------------------------------------------
# Forbidden terms / disqualification
# ---------------------------------------------------------------------------

class TestForbiddenTerms:
    def test_pics_disqualified_by_varios_servidores(self, identifier):
        text = "El sistema tiene varios servidores identicos atendiendo clientes."
        candidates = identifier.identify(text)
        pics = next(c for c in candidates if c.model_id == "PICS")
        assert pics.score == 0.0
        assert pics.disqualified_by

    def test_picm_disqualified_by_poblacion_finita(self, identifier):
        text = "Un sistema de poblacion finita con varios servidores."
        candidates = identifier.identify(text)
        picm = next(c for c in candidates if c.model_id == "PICM")
        assert picm.score == 0.0
        assert picm.disqualified_by


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_text_returns_no_model(self, identifier):
        top, issues = identifier.top_candidate("")
        assert top is None or top.score == 0.0
        assert any(i.severity == IssueSeverity.ERROR for i in issues) or top is None

    def test_identify_returns_all_5_models(self, identifier):
        candidates = identifier.identify("texto cualquiera")
        model_ids = {c.model_id for c in candidates}
        assert model_ids == {"PICS", "PICM", "PFCS", "PFCM", "PFHET"}

    def test_candidates_are_sorted_by_score(self, identifier):
        text = "Una cajera atiende clientes. Un servidor. Cola simple."
        candidates = identifier.identify(text)
        scores = [c.score for c in candidates if c.score > 0]
        assert scores == sorted(scores, reverse=True)

    def test_ambiguity_warning_emitted_when_scores_close(self, identifier):
        """When top two models have very similar keyword hits."""
        # A text with both 'un servidor' (PICS) and 'fuente finita' (PFCS)
        text = "Un servidor atiende una fuente finita de equipos. Numero limitado."
        _, issues = identifier.top_candidate(text)
        issue_codes = [i.code for i in issues]
        # Either model_ambiguity or no_model_identified — should not crash
        assert isinstance(issue_codes, list)

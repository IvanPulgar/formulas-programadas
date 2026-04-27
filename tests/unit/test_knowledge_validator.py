import pytest

from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository
from infrastructure.repositories.knowledge_validator import OfflineKnowledgeValidator


@pytest.fixture
def loaded_knowledge():
    repo = OfflineKnowledgeRepository()
    return repo.load_all()


def test_validator_accepts_shipped_knowledge(loaded_knowledge):
    validator = OfflineKnowledgeValidator()
    result = validator.validate(loaded_knowledge)

    assert result.is_valid is True, f"Validation errors: {result.errors}"
    assert result.errors == []


def test_shipped_knowledge_has_compute_l_objective(loaded_knowledge):
    """compute_L must be present - was missing in v1 of objectives.json."""
    objective_ids = [obj["id"] for obj in loaded_knowledge["objectives"]]
    assert "compute_L" in objective_ids, "compute_L objective is missing from objectives.json"


def test_shipped_knowledge_has_compute_pk_objective(loaded_knowledge):
    """compute_Pk (Erlang C / probability of waiting in PICM) must be present."""
    objective_ids = [obj["id"] for obj in loaded_knowledge["objectives"]]
    assert "compute_Pk" in objective_ids, "compute_Pk objective is missing from objectives.json"


def test_all_dependency_formulas_have_valid_ids(loaded_knowledge):
    """All formulas in dependencies must exist in real registry."""
    from domain.formulas.registry import FORMULAS
    formula_ids = {f.id for f in FORMULAS}

    for dep in loaded_knowledge["dependencies"]:
        fid = dep["formula_id"]
        assert fid in formula_ids, f"Dependency formula_id '{fid}' not found in registry"
        for dep_on in dep.get("depends_on_formulas", []):
            assert dep_on in formula_ids, (
                f"Dependency '{fid}' depends on unknown formula '{dep_on}'"
            )


def test_models_have_forbidden_terms_field(loaded_knowledge):
    """All model entries must have the forbidden_terms field (may be empty for GENERAL)."""
    for model in loaded_knowledge["models"]:
        assert "forbidden_terms" in model, (
            f"Model '{model['id']}' is missing the 'forbidden_terms' field"
        )


def test_pics_and_pfcs_have_discriminating_forbidden_terms(loaded_knowledge):
    """PICS and PFCS must have non-empty forbidden_terms to disambiguate each other."""
    models_by_id = {m["id"]: m for m in loaded_knowledge["models"]}
    assert models_by_id["PICS"]["forbidden_terms"], "PICS forbidden_terms must not be empty"
    assert models_by_id["PFCS"]["required_variables"], "PFCS must list M in required_variables"


def test_validator_rejects_unknown_formula_reference(loaded_knowledge):
    loaded_knowledge["objectives"][0]["targets"][0]["formula_id"] = "formula_that_does_not_exist"

    validator = OfflineKnowledgeValidator()
    result = validator.validate(loaded_knowledge)

    assert result.is_valid is False
    assert any("unknown formula" in err for err in result.errors)


def test_validator_rejects_unknown_variable_in_model(loaded_knowledge):
    loaded_knowledge["models"][0]["required_variables"] = ["not_a_variable"]

    validator = OfflineKnowledgeValidator()
    result = validator.validate(loaded_knowledge)

    assert result.is_valid is False
    assert any("requires unknown variable" in err for err in result.errors)


def test_variable_synonyms_cover_core_variables(loaded_knowledge):
    """Core input variables must have synonyms defined."""
    synonyms = loaded_knowledge["synonyms"].get("variable_synonyms", {})
    for var_id in ("lambda_", "mu", "k", "M", "W", "Wq", "L", "Lq"):
        assert var_id in synonyms, f"No synonyms defined for variable '{var_id}'"
        assert len(synonyms[var_id]) >= 3, (
            f"Variable '{var_id}' has fewer than 3 synonyms — too sparse for NLP matching"
        )

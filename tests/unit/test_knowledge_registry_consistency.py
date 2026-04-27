from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository
from infrastructure.repositories.knowledge_validator import OfflineKnowledgeValidator


def test_knowledge_is_consistent_with_formula_registry_and_catalogs():
    repo = OfflineKnowledgeRepository()
    knowledge = repo.load_all()

    result = OfflineKnowledgeValidator().validate(knowledge)

    assert result.is_valid, f"Knowledge consistency errors: {result.errors}"

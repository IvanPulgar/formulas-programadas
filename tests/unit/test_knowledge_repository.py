from pathlib import Path

from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository


def test_load_all_knowledge_files():
    repo = OfflineKnowledgeRepository()
    knowledge = repo.load_all()

    assert "models" in knowledge
    assert "keywords" in knowledge
    assert "synonyms" in knowledge
    assert "variables" in knowledge
    assert "units" in knowledge
    assert "objectives" in knowledge
    assert "dependencies" in knowledge

    assert isinstance(knowledge["models"], list)
    assert isinstance(knowledge["keywords"], dict)
    assert isinstance(knowledge["variables"], list)
    assert isinstance(knowledge["objectives"], list)


def test_load_all_is_deterministic():
    repo = OfflineKnowledgeRepository()
    first = repo.load_all()
    second = repo.load_all()

    assert first == second


def test_repository_uses_expected_default_path():
    repo = OfflineKnowledgeRepository()
    expected_suffix = Path("infrastructure") / "data" / "knowledge"

    assert str(repo.base_path).replace("\\", "/").endswith(str(expected_suffix).replace("\\", "/"))

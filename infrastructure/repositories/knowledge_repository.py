from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class KnowledgeRepositoryError(RuntimeError):
    """Raised when knowledge files cannot be loaded."""


class OfflineKnowledgeRepository:
    """Read-only repository for local, offline analysis knowledge."""

    def __init__(self, base_path: str | Path | None = None):
        if base_path is None:
            base_path = Path(__file__).resolve().parents[1] / "data" / "knowledge"
        self.base_path = Path(base_path)

    def load_all(self) -> dict[str, Any]:
        """Load all known knowledge files into a single dictionary."""
        return {
            "models": self._load_json("models.json").get("models", []),
            "keywords": self._load_json("keywords.json").get("keywords", {}),
            "synonyms": self._load_json("synonyms.json"),
            "variables": self._load_json("variables.json").get("detectable_variables", []),
            "units": self._load_json("units.json").get("conversions", []),
            "objectives": self._load_json("objectives.json").get("objectives", []),
            "dependencies": self._load_json("dependencies.json").get("formula_dependencies", []),
        }

    def _load_json(self, file_name: str) -> dict[str, Any]:
        path = self.base_path / file_name
        if not path.exists():
            raise KnowledgeRepositoryError(f"Knowledge file not found: {path}")

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise KnowledgeRepositoryError(f"Invalid JSON in {path}: {exc}") from exc

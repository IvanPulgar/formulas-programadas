"""
ModelIdentifier — Phase 2 offline statement analysis.

Identifies the most likely queue-theory model (PICS, PICM, PFCS, PFCM, PFHET)
from a plain-text problem statement using:

  1. Keyword scoring: positive hits from keywords.json
  2. Forbidden-term disqualification: terms from models.json forbidden_terms
  3. Tie-breaking by count of matched keywords (higher = better)

Design decisions:
  - Pure Python, no external dependencies.
  - Reads knowledge exclusively through OfflineKnowledgeRepository.
  - All text comparisons are case-insensitive and accent-normalized.
  - "GENERAL" model is never returned as a primary identification result
    (it is a special category for introductory formulas).
"""

from __future__ import annotations

import unicodedata
from typing import Any

from domain.entities.analysis import AnalysisIssue, IssueSeverity, ModelCandidate
from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository

# Models that can be identified as primary queue models
_IDENTIFIABLE_MODELS = {"PICS", "PICM", "PFCS", "PFCM", "PFHET"}


def _normalize(text: str) -> str:
    """Lowercase and strip Unicode accents for robust matching."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


class ModelIdentifier:
    """
    Identifies the queue-theory model from a problem statement.

    Usage::

        repo = OfflineKnowledgeRepository()
        knowledge = repo.load_all()
        identifier = ModelIdentifier(knowledge)
        candidates = identifier.identify("Una farmacia atendida por una cajera ...")
    """

    def __init__(self, knowledge: dict[str, Any]) -> None:
        self._models: list[dict[str, Any]] = knowledge.get("models", [])
        self._keywords: dict[str, list[str]] = knowledge.get("keywords", {})
        self._model_map: dict[str, dict[str, Any]] = {
            m["id"]: m for m in self._models if m["id"] in _IDENTIFIABLE_MODELS
        }

    def identify(self, text: str) -> list[ModelCandidate]:
        """
        Return a ranked list of ModelCandidate ordered by score descending.

        A model is disqualified (score = 0.0) if any forbidden term is found,
        regardless of keyword score.
        """
        norm_text = _normalize(text)
        candidates: list[ModelCandidate] = []

        for model_id in _IDENTIFIABLE_MODELS:
            model_meta = self._model_map.get(model_id, {})
            keyword_list = [_normalize(k) for k in self._keywords.get(model_id, [])]
            forbidden_list = [_normalize(f) for f in model_meta.get("forbidden_terms", [])]

            matched: list[str] = [kw for kw in keyword_list if kw in norm_text]
            disqualifiers: list[str] = [f for f in forbidden_list if f in norm_text]

            if disqualifiers:
                score = 0.0
            elif not keyword_list:
                score = 0.0
            else:
                # Score = fraction of keywords matched, capped at 1.0
                score = min(len(matched) / max(len(keyword_list) * 0.3, 1.0), 1.0)

            candidates.append(
                ModelCandidate(
                    model_id=model_id,
                    score=round(score, 4),
                    matched_keywords=matched,
                    disqualified_by=disqualifiers,
                )
            )

        # Sort: disqualified last, then by score desc, then by matched keyword count desc
        candidates.sort(
            key=lambda c: (
                len(c.disqualified_by) == 0,  # True (1) first
                c.score,
                len(c.matched_keywords),
            ),
            reverse=True,
        )

        return candidates

    def top_candidate(self, text: str) -> tuple[ModelCandidate | None, list[AnalysisIssue]]:
        """
        Return the best candidate and any diagnostic issues.

        Issues produced:
          - ERROR if all candidates are disqualified or have zero score
          - WARNING if top-2 candidates have scores within 0.10 of each other (ambiguity)
          - INFO if the top candidate score is below 0.40 (LOW confidence)
        """
        issues: list[AnalysisIssue] = []
        ranked = self.identify(text)
        viable = [c for c in ranked if c.score > 0.0]

        if not viable:
            issues.append(AnalysisIssue(
                severity=IssueSeverity.ERROR,
                code="no_model_identified",
                message=(
                    "No se pudo identificar el modelo de colas. "
                    "Verifica que el enunciado mencione informacion sobre el numero "
                    "de servidores, la poblacion y la distribucion de llegadas."
                ),
            ))
            return None, issues

        top = viable[0]

        # Ambiguity check: top-2 within 0.10
        if len(viable) >= 2:
            second = viable[1]
            if (top.score - second.score) <= 0.10 and second.score > 0.0:
                issues.append(AnalysisIssue(
                    severity=IssueSeverity.WARNING,
                    code="model_ambiguity",
                    message=(
                        f"El modelo '{top.model_id}' y '{second.model_id}' tienen puntajes similares "
                        f"({top.score:.2f} vs {second.score:.2f}). "
                        "El resultado puede ser incorrecto si el enunciado no especifica claramente "
                        "el numero de servidores y el tamano de la poblacion."
                    ),
                ))

        if top.score < 0.40:
            issues.append(AnalysisIssue(
                severity=IssueSeverity.INFO,
                code="low_model_confidence",
                message=(
                    f"Confianza baja para el modelo '{top.model_id}' (score={top.score:.2f}). "
                    "Considera proporcionar mas detalles en el enunciado."
                ),
            ))

        return top, issues

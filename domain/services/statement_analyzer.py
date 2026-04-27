"""
StatementAnalyzer — Phase 2 offline statement analysis.

Orchestrates ModelIdentifier and VariableExtractor to produce a
StatementAnalysisResult from a plain-text queue-theory problem statement.

Pipeline:
  1. Normalize text (lowercase + strip accents)
  2. Identify model candidates (ModelIdentifier)
  3. Extract variables (VariableExtractor, model-aware)
  4. Infer objectives from objective synonyms + extracted variables
  5. Assess solvability (are all required variables present?)
  6. Return StatementAnalysisResult

Design decisions:
  - Pure Python + stdlib; no external NLP.
  - Does NOT call the existing orchestrator, matcher, or solver.
  - Does NOT perform any mathematical calculation.
  - Safe to run in parallel with the existing calculation pipeline.
  - All text normalization is idempotent — calling analyze() twice
    on the same text produces identical output.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from domain.entities.analysis import (
    AnalysisConfidence,
    AnalysisIssue,
    IssueSeverity,
    StatementAnalysisRequest,
    StatementAnalysisResult,
)
from domain.services.literal_segmenter import (
    LiteralSegmenter,
    OBJECTIVES_NEEDING_PERIOD,
    OBJECTIVES_NEEDING_THRESHOLD,
    UNSUPPORTED_OBJECTIVES,
)
from domain.services.formula_plan_builder import build_formula_plan
from domain.services.literal_result_calculator import LiteralResultCalculator
from domain.services.model_identifier import ModelIdentifier
from domain.services.statement_problem_knowledge import (
    find_matching_patterns,
    get_formula_order_hint,
    get_unit_conversion_hints,
)
from domain.services.variable_extractor import VariableExtractor
from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Period detection regex (operating hours/minutes per day or week)
# ---------------------------------------------------------------------------
_PERIOD_RE = re.compile(
    r"\d+[.,]?\d*\s*"
    r"(?:horas?\s*(?:al?\s*)?(?:dia|semana)"
    r"|minutos?\s*(?:al?\s*)?(?:dia|semana)"
    r"|dias?\s*(?:al?\s*)?semana"
    r")",
    re.IGNORECASE,
)

# Threshold pattern for probability questions ("al menos 2", "más de 3", etc.)
_THRESHOLD_RE = re.compile(
    r"(?:mas\s*de|al\s*menos|por\s*lo\s*menos|igual\s*o\s*mayor\s*(?:a|que)?)"
    r"\s*(?:a\s*)?(\d+)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Extended formula plans for objectives NOT in objectives.json
# These are purely conceptual — formula ids point to existing catalog entries
# that compute the required intermediate or final value.
# ---------------------------------------------------------------------------
_EXTENDED_PLANS: dict[str, dict[str, list[str]]] = {
    # P(customer must wait) = ρ for M/M/1; Erlang C for M/M/c
    "compute_wait_probability": {
        "PICS": ["pics_rho"],
        "PICM": ["picm_pk"],
        "PFCS": ["pfcs_rho"],
        "PFCM": ["pfcm_rho"],
    },
    # Idle time per period = P0 × period
    "compute_idle_time": {
        "PICS": ["pics_p0"],
        "PICM": ["picm_p0"],
        "PFCS": ["pfcs_p0"],
        "PFCM": ["pfcm_p0"],
    },
    # Arrivals per period × P(wait)
    "compute_waiting_arrivals": {
        "PICS": ["pics_rho"],
        "PICM": ["picm_pk"],
        "PFCS": ["pfcs_rho"],
        "PFCM": ["pfcm_rho"],
    },
    # P(Q ≥ r) — in M/M/1: ρ^(r+1) ; in M/M/c needs pk + pk formula
    "compute_probability_q_at_least_r": {
        "PICS": ["pics_rho"],
        "PICM": ["picm_p0", "picm_pk"],
    },
    # P(r1 ≤ Q ≤ r2)
    "compute_probability_q_between": {
        "PICS": ["pics_rho"],
        "PICM": ["picm_p0", "picm_pk"],
    },
    # P(Q > 0) = ρ² in M/M/1
    "compute_probability_queue_nonempty": {
        "PICS": ["pics_rho"],
        "PICM": ["picm_pk"],
    },
    # P(at least one server free) = 1 − Pk in M/M/c ; = P0 in M/M/1
    "compute_server_available_probability": {
        "PICS": ["pics_p0"],
        "PICM": ["picm_p0", "picm_pk"],
        "PFCS": ["pfcs_p0"],
        "PFCM": ["pfcm_p0"],
    },
    # Unsupported — no formula available in current catalog
    "compute_cost": {},
    "compute_total_cost": {},
    "compare_alternatives": {},
    "optimize_cost": {},
}


class StatementAnalyzer:
    """
    Analyzes a Spanish queue-theory problem statement offline.

    Usage::

        repo = OfflineKnowledgeRepository()
        knowledge = repo.load_all()
        analyzer = StatementAnalyzer(knowledge)
        result = analyzer.analyze(StatementAnalysisRequest(text="..."))
    """

    def __init__(self, knowledge: dict[str, Any]) -> None:
        self._knowledge = knowledge
        self._identifier = ModelIdentifier(knowledge)
        self._extractor = VariableExtractor(knowledge)
        self._segmenter = LiteralSegmenter()
        self._calculator = LiteralResultCalculator()
        self._models_meta: dict[str, dict[str, Any]] = {
            m["id"]: m for m in knowledge.get("models", [])
        }
        self._objectives: list[dict[str, Any]] = knowledge.get("objectives", [])
        self._obj_synonyms: dict[str, list[str]] = (
            knowledge.get("synonyms", {}).get("objective_synonyms", {})
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, request: StatementAnalysisRequest) -> StatementAnalysisResult:
        """Run the full analysis pipeline and return a StatementAnalysisResult."""
        result = StatementAnalysisResult()

        # Step 1: normalize text
        norm_text = _normalize(request.text) if request.normalize_text else request.text
        result.normalized_text = norm_text

        # Step 1b: segment literals (Phase 8)
        statement_context, raw_literals = self._segmenter.segment(
            request.text, norm_text
        )
        result.statement_context = statement_context
        result.literals = raw_literals

        # Step 1c: gather KB pattern hints for model reinforcement (Phase 10)
        kb_hints = find_matching_patterns(norm_text)

        # Step 2: identify model
        top_candidate, id_issues = self._identifier.top_candidate(norm_text)
        result.issues.extend(id_issues)

        result.model_candidates = self._identifier.identify(norm_text)

        if top_candidate is not None:
            if request.hint_model and request.hint_model != top_candidate.model_id:
                # User explicitly requested a different model — override auto-identification.
                result.identified_model = request.hint_model
                result.model_confidence = AnalysisConfidence.MEDIUM  # conservative when overriding
                result.add_issue(
                    IssueSeverity.INFO,
                    "hint_model_override",
                    (
                        f"El modelo sugerido '{request.hint_model}' sobreescribe al modelo "
                        f"identificado automaticamente '{top_candidate.model_id}'."
                    ),
                )
            else:
                # Auto-identification succeeded (and matches hint if one was given).
                result.identified_model = top_candidate.model_id
                result.model_confidence = top_candidate.confidence
        else:
            # Auto-identification failed.
            if request.hint_model:
                result.identified_model = request.hint_model
                result.model_confidence = AnalysisConfidence.LOW
                result.add_issue(
                    IssueSeverity.INFO,
                    "hint_model_used",
                    (
                        f"Se usa el modelo sugerido '{request.hint_model}' porque no se pudo "
                        "identificar automaticamente un modelo en el enunciado."
                    ),
                )
            else:
                result.identified_model = None
                result.model_confidence = AnalysisConfidence.NONE

        # Step 2b: reinforce model identification with KB hints (Phase 10).
        # If model_identifier found no confident result but KB has a strong hit,
        # use the KB suggestion as an INFO-level hint (never overrides confident ID).
        if kb_hints:
            top_kb = kb_hints[0]
            model_is_uncertain = (
                result.identified_model is None
                or result.model_confidence
                in (AnalysisConfidence.LOW, AnalysisConfidence.NONE)
            )
            if model_is_uncertain and top_kb.confidence >= 0.35:
                if result.identified_model is None:
                    result.identified_model = top_kb.model_id
                    result.model_confidence = AnalysisConfidence.LOW
                result.add_issue(
                    IssueSeverity.INFO,
                    "kb_model_hint",
                    (
                        f"La base de conocimiento sugiere el modelo '{top_kb.model_id}' "
                        f"(confianza {top_kb.confidence:.0%}). "
                        "Claves encontradas: "
                        + ", ".join(top_kb.matched_clues[:5])
                        + "."
                    ),
                )
            # Emit unit-conversion hints as INFO issues
            uc_notes = get_unit_conversion_hints(norm_text)
            for note in uc_notes:
                result.add_issue(
                    IssueSeverity.INFO,
                    "kb_unit_conversion_hint",
                    f"Conversión de unidades detectada: {note}",
                )
            # Emit dimensioning note if found
            dim_note = top_kb.dimensioning_note
            if dim_note:
                result.add_issue(
                    IssueSeverity.INFO,
                    "kb_dimensioning_hint",
                    f"Patrón de dimensionamiento: {dim_note}",
                )

        # Step 3: extract variables (model-aware when possible)
        extracted_vars, extract_issues = self._extractor.extract(
            norm_text, model_id=result.identified_model
        )
        result.extracted_variables = extracted_vars
        result.issues.extend(extract_issues)

        # Step 4: check for missing required variables and emit warnings
        if result.identified_model:
            self._check_required_variables(result)

        # Step 5: infer objectives from text
        result.inferred_objectives = self._infer_objectives(norm_text, result.identified_model)

        # Apply user hint for objective
        if request.hint_objective and request.hint_objective not in result.inferred_objectives:
            result.inferred_objectives.insert(0, request.hint_objective)
            result.add_issue(
                IssueSeverity.INFO,
                "hint_objective_used",
                f"Objetivo '{request.hint_objective}' agregado por sugerencia del usuario.",
            )

        # Step 5b: enrich each literal with planned step ids (Phase 8)
        for lit in result.literals:
            if lit.inferred_objective:
                lit.planned_step_ids = self._steps_for_objective(
                    lit.inferred_objective, result.identified_model
                )

        # Step 5b+: supplement formula order from KB patterns (Phase 10)
        # Only replaces empty planned_step_ids; never overwrites existing steps.
        if result.identified_model:
            for lit in result.literals:
                if lit.inferred_objective and not lit.planned_step_ids:
                    kb_order = get_formula_order_hint(
                        result.identified_model, lit.inferred_objective
                    )
                    if kb_order:
                        lit.planned_step_ids = kb_order

        # Step 5c: add per-literal diagnostic issues (Phase 9)
        self._enrich_literal_issues(result, norm_text)

        # Step 5d: build structured formula plan per literal (Phase 11)
        extracted_ids = result.variable_ids()
        for lit in result.literals:
            fp, missing = build_formula_plan(
                model_id=result.identified_model,
                objective=lit.inferred_objective,
                extracted_variable_ids=extracted_ids,
            )
            lit.formula_plan = fp
            lit.missing_variables = missing

        # Step 5e: compute numeric result per literal (Phase 15)
        for lit in result.literals:
            lit.calculation_result = self._calculator.calculate(result, lit)

        # Step 6: assess solvability
        result.is_solvable = self._assess_solvability(result)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_required_variables(self, result: StatementAnalysisResult) -> None:
        model_meta = self._models_meta.get(result.identified_model or "", {})
        required = model_meta.get("required_variables", [])
        present = result.variable_ids()

        for var_id in required:
            if var_id not in present:
                result.add_issue(
                    IssueSeverity.WARNING,
                    "missing_variable",
                    (
                        f"La variable requerida '{var_id}' para el modelo "
                        f"'{result.identified_model}' no fue encontrada en el enunciado. "
                        "Verifica que el enunciado incluya este dato."
                    ),
                    context=var_id,
                )

    def _infer_objectives(self, norm_text: str, model_id: str | None) -> list[str]:
        """
        Match objective synonyms against the normalized text.
        Returns a list of objective IDs ordered by number of synonym matches.
        """
        hits: dict[str, int] = {}

        for obj_id, synonyms in self._obj_synonyms.items():
            count = 0
            for synonym in synonyms:
                if _normalize(synonym) in norm_text:
                    count += 1
            if count > 0:
                # Validate that this objective applies to the current model
                if self._objective_applies(obj_id, model_id):
                    hits[obj_id] = count

        # Sort by hit count descending
        return sorted(hits, key=lambda k: hits[k], reverse=True)

    def _objective_applies(self, obj_id: str, model_id: str | None) -> bool:
        """Return True if the objective is defined for the given model (or any model)."""
        if model_id is None:
            return True
        for obj in self._objectives:
            if obj["id"] == obj_id:
                target_models = {t["model"] for t in obj.get("targets", [])}
                return model_id in target_models or "GENERAL" in target_models
        return True  # conservative: allow unknown objectives

    def _steps_for_objective(
        self,
        obj_id: str,
        model_id: str | None,
    ) -> list[str]:
        """Return ordered formula ids that compute *obj_id* for the given model.

        Checks objectives.json first, then falls back to _EXTENDED_PLANS for
        objectives introduced in Phase 9 that are not in the knowledge base.
        """
        # 1. Check objectives.json (managed by OfflineKnowledgeRepository)
        for obj in self._objectives:
            if obj["id"] == obj_id:
                targets = obj.get("targets", [])
                if model_id:
                    specific = [t["formula_id"] for t in targets if t.get("model") == model_id]
                    if specific:
                        return specific
                    general = [t["formula_id"] for t in targets if t.get("model") == "GENERAL"]
                    if general:
                        return general
                return [t["formula_id"] for t in targets]

        # 2. Fall back to extended plans (Phase 9 objectives)
        extended = _EXTENDED_PLANS.get(obj_id, {})
        if model_id and model_id in extended:
            return list(extended[model_id])
        # Return all formula ids flattened when no model known
        seen: list[str] = []
        for ids in extended.values():
            for fid in ids:
                if fid not in seen:
                    seen.append(fid)
        return seen

    def _enrich_literal_issues(
        self,
        result: StatementAnalysisResult,
        norm_context: str,
    ) -> None:
        """Add per-literal issues for unsupported objectives, missing period, etc."""
        for lit in result.literals:
            obj = lit.inferred_objective
            if obj is None:
                continue

            # Unsupported objectives (costs, etc.)
            if obj in UNSUPPORTED_OBJECTIVES:
                lit.issues.append(AnalysisIssue(
                    severity=IssueSeverity.WARNING,
                    code="objective_detected_but_not_executable",
                    message=(
                        f"El objetivo '{obj}' fue detectado en el literal '{lit.literal_id}' "
                        "pero no puede ejecutarse numéricamente en la fase actual. "
                        "Se implementará en una fase posterior."
                    ),
                    context=lit.raw_text,
                ))
                continue  # no point checking other issues for unsupported objectives

            # No formula plan available
            if not lit.planned_step_ids:
                lit.issues.append(AnalysisIssue(
                    severity=IssueSeverity.INFO,
                    code="objective_detected_but_not_executable",
                    message=(
                        f"El objetivo '{obj}' fue detectado en el literal '{lit.literal_id}' "
                        "pero no hay fórmulas disponibles para el modelo "
                        f"'{result.identified_model or 'desconocido'}'."
                    ),
                    context=lit.raw_text,
                ))

            # Objectives that require a period variable (hours/day, etc.)
            if obj in OBJECTIVES_NEEDING_PERIOD:
                if not _PERIOD_RE.search(norm_context):
                    lit.issues.append(AnalysisIssue(
                        severity=IssueSeverity.WARNING,
                        code="missing_period_hours",
                        message=(
                            f"El objetivo '{obj}' requiere un período de operación "
                            "(p. ej. 'horas al día') que no fue encontrado en el enunciado."
                        ),
                        context=lit.raw_text,
                    ))

            # Objectives that require a numeric threshold r
            if obj in OBJECTIVES_NEEDING_THRESHOLD:
                lit_norm = lit.normalized_text
                if not _THRESHOLD_RE.search(lit_norm) and not any(
                    c.isdigit() for c in lit_norm
                ):
                    lit.issues.append(AnalysisIssue(
                        severity=IssueSeverity.WARNING,
                        code="missing_threshold_r",
                        message=(
                            f"El objetivo '{obj}' requiere un umbral numérico r "
                            "(p. ej. 'más de 2') que no fue encontrado en el literal."
                        ),
                        context=lit.raw_text,
                    ))

    def _assess_solvability(self, result: StatementAnalysisResult) -> bool:
        """
        True when:
          - A model has been identified (confidence >= LOW)
          - All required variables for that model are present
          - At least one objective is inferred or hinted
        """
        if result.identified_model is None:
            return False
        if result.model_confidence == AnalysisConfidence.NONE:
            return False

        model_meta = self._models_meta.get(result.identified_model, {})
        required = model_meta.get("required_variables", [])
        present = result.variable_ids()

        if not all(v in present for v in required):
            return False

        if not result.inferred_objectives:
            return False

        return True


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def make_analyzer() -> StatementAnalyzer:
    """
    Convenience factory that loads knowledge from the default path and
    returns a ready-to-use StatementAnalyzer.
    """
    repo = OfflineKnowledgeRepository()
    knowledge = repo.load_all()
    return StatementAnalyzer(knowledge)

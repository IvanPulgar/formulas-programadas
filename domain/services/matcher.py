from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.entities import FormulaDefinition, MatchCandidate
from domain.entities.enums import FormulaCategory
from domain.formulas.registry import FORMULAS
from domain.rules.constraints import (
    list_category_constraints,
    non_negative,
    positive,
    positive_integer,
    probability,
)
from domain.services.input_processing import VariableResolutionResult


@dataclass
class MatchResult:
    candidates: list[MatchCandidate] = field(default_factory=list)
    selected: list[MatchCandidate] = field(default_factory=list)
    discarded: list[dict[str, Any]] = field(default_factory=list)
    category_scores: dict[str, float] = field(default_factory=dict)
    is_ambiguous: bool = False
    explanation: list[str] = field(default_factory=list)


class CategoryScorer:
    def score(self, candidate: MatchCandidate, resolution: VariableResolutionResult) -> float:
        matched = len(candidate.matched_variables)
        required = len(candidate.formula.input_variables)
        result_match = candidate.formula.result_variable in resolution.result_inputs
        category_id = candidate.formula.category.value
        category_present = category_id in resolution.category_inputs
        category_specific = any(
            var in resolution.category_inputs.get(category_id, {})
            for var in candidate.matched_variables
        )

        presence_score = (matched / required) if required > 0 else 1.0
        specificity_bonus = min(required, 5) * 0.04
        category_match_score = 0.18 if category_present else 0.0
        category_specific_score = 0.12 if category_specific else 0.0
        result_score = 0.22 if result_match else 0.0
        missing_penalty = 0.12 * len(candidate.missing_variables)
        generic_penalty = 0.05 if required <= 2 else 0.0

        category_score = category_match_score + category_specific_score + specificity_bonus
        total_score = (
            0.25 * presence_score
            + result_score
            + category_score
            - missing_penalty
            - generic_penalty
        )

        candidate.category_score = round(max(category_score, 0.0), 4)
        candidate.matching_score = round(max(total_score, 0.0), 4)
        return candidate.matching_score


class AmbiguityResolver:
    dominance_threshold = 0.05

    def resolve(self, result: MatchResult) -> MatchResult:
        if not result.candidates:
            result.explanation.append("No hay fórmulas candidatas para procesar.")
            return result

        sorted_candidates = sorted(result.candidates, key=lambda c: c.matching_score, reverse=True)
        result.candidates = sorted_candidates

        category_totals: dict[str, float] = {}
        for candidate in sorted_candidates:
            category_totals[candidate.formula.category.value] = (
                category_totals.get(candidate.formula.category.value, 0.0) + candidate.matching_score
            )
        result.category_scores = {k: round(v, 4) for k, v in category_totals.items()}

        if len(sorted_candidates) > 2:
            result = self._resolve_by_category(result, sorted_candidates)
        else:
            result.selected = sorted_candidates[:2]
            if len(sorted_candidates) == 2:
                same_category = sorted_candidates[0].formula.category == sorted_candidates[1].formula.category
                if not same_category and abs(sorted_candidates[0].matching_score - sorted_candidates[1].matching_score) <= self.dominance_threshold:
                    result.is_ambiguous = True
                    result.selected[0].is_ambiguous = True
                    result.selected[1].is_ambiguous = True
                    result.explanation.append("Ambigüedad entre dos fórmulas de diferentes categorías con puntuación similar.")
                else:
                    result.explanation.append("Se seleccionaron las mejores fórmulas sin ambigüedad significativa.")
            else:
                result.explanation.append("Se seleccionó la mejor fórmula disponible.")

        return result

    def _resolve_by_category(self, result: MatchResult, candidates: list[MatchCandidate]) -> MatchResult:
        category_totals = result.category_scores
        ordered_categories = sorted(category_totals.items(), key=lambda item: item[1], reverse=True)

        if len(ordered_categories) > 1 and abs(ordered_categories[0][1] - ordered_categories[1][1]) <= self.dominance_threshold:
            result.is_ambiguous = True
            result.selected = candidates[:2]
            for candidate in result.selected:
                candidate.is_ambiguous = True
            result.explanation.append(
                "Se detectó ambigüedad entre categorías dominantes con puntajes muy cercanos."
            )
            return result

        dominant_category = ordered_categories[0][0]
        selected = [c for c in candidates if c.formula.category.value == dominant_category][:2]
        result.selected = selected
        result.explanation.append(
            f"Categoría dominante: {dominant_category}. Se seleccionaron las mejores fórmulas de esa categoría."
        )
        return result


class FormulaMatcher:
    def __init__(self, scorer: CategoryScorer | None = None, ambiguity_resolver: AmbiguityResolver | None = None):
        self.scorer = scorer or CategoryScorer()
        self.ambiguity_resolver = ambiguity_resolver or AmbiguityResolver()
        self.formulas = FORMULAS

    def match(self, resolution: VariableResolutionResult, formulas: list[FormulaDefinition] | None = None) -> MatchResult:
        formulas_to_evaluate = formulas if formulas is not None else self.formulas
        result = MatchResult()
        available_vars = set(resolution.consolidated_inputs.keys())
        result_vars = set(resolution.result_inputs.keys())

        for formula in formulas_to_evaluate:
            candidate = self._evaluate_formula(formula, resolution, available_vars, result_vars, result)
            if candidate is None:
                continue

            score = self.scorer.score(candidate, resolution)
            if score <= 0.0:
                self._discard_formula(result, formula, "Puntuación insuficiente después de aplicar las reglas de validación.")
                continue

            result.candidates.append(candidate)

        if not result.candidates:
            result.explanation.append("No se encontraron fórmulas candidatas con los datos suministrados.")
            return result

        return self.ambiguity_resolver.resolve(result)

    def _evaluate_formula(
        self,
        formula: FormulaDefinition,
        resolution: VariableResolutionResult,
        available_vars: set[str],
        result_vars: set[str],
        result: MatchResult,
    ) -> MatchCandidate | None:
        missing = [var for var in formula.input_variables if var not in available_vars]
        matched = [var for var in formula.input_variables if var in available_vars]
        has_result = formula.result_variable in result_vars

        if len(missing) > 1:
            self._discard_formula(
                result,
                formula,
                "Faltan dos o más variables de entrada, por lo que la fórmula no califica.",
            )
            return None

        if len(missing) == 1 and not has_result and len(matched) == 0:
            self._discard_formula(
                result,
                formula,
                "No hay suficientes variables presentes para evaluar esta fórmula.",
            )
            return None

        candidate = MatchCandidate(
            formula=formula,
            matched_variables=matched,
            missing_variables=missing,
        )

        constraint_ok, constraint_warnings = self._validate_constraints(formula, resolution)
        candidate.warnings.extend(constraint_warnings)
        if not constraint_ok:
            self._discard_formula(result, formula, "La fórmula no cumple las restricciones del dominio.")
            candidate.warnings.extend(constraint_warnings)
            return None

        return candidate

    def _validate_constraints(self, formula: FormulaDefinition, resolution: VariableResolutionResult) -> tuple[bool, list[str]]:
        warnings: list[str] = []
        inputs = {key: value.value for key, value in resolution.consolidated_inputs.items() if value is not None}

        for category_constraint in list_category_constraints(formula.category):
            required_keys = self._category_constraint_requirements(category_constraint.id)
            if not self._has_required_inputs(required_keys, inputs):
                warnings.append(f"No se pudo validar la restricción de categoría {category_constraint.id} por datos incompletos.")
                continue
            if not category_constraint.validator(inputs):
                return False, [category_constraint.description]

        known_validators = self._constraint_validators()
        for constraint_id in formula.constraints:
            validator = known_validators.get(constraint_id)
            required_keys = self._constraint_requirements().get(constraint_id, [])
            if validator is None:
                warnings.append(f"No existe validador definido para la restricción {constraint_id}.")
                continue
            if not self._has_required_inputs(required_keys, inputs):
                warnings.append(f"No se pudo validar la restricción {constraint_id} por datos faltantes.")
                continue
            if not validator(inputs):
                return False, [f"Falla restricción de fórmula: {constraint_id}." ]

        return True, warnings

    def _has_required_inputs(self, required_keys: list[str], inputs: dict[str, Any]) -> bool:
        return all(key in inputs and inputs[key] is not None for key in required_keys)

    def _constraint_requirements(self) -> dict[str, list[str]]:
        return {
            "lambda_positive": ["lambda_"],
            "mu_positive": ["mu"],
            "rho_positive": ["rho"],
            "rho_non_negative": ["rho"],
            "n_positive_integer": ["n"],
            "n_non_negative_integer": ["n"],
            "k_positive_integer": ["k"],
            "M_positive_integer": ["M"],
            "probability": ["rho"],
        }

    def _category_constraint_requirements(self, constraint_id: str) -> list[str]:
        return {
            "pics_lambda_positive": ["lambda_"],
            "pics_mu_positive": ["mu"],
            "pics_lambda_less_than_mu": ["lambda_", "mu"],
            "picm_lambda_positive": ["lambda_"],
            "picm_mu_positive": ["mu"],
            "picm_k_positive_integer": ["k"],
            "picm_lambda_less_than_k_mu": ["lambda_", "mu", "k"],
            "pfcs_lambda_positive": ["lambda_"],
            "pfcs_mu_positive": ["mu"],
            "pfcs_m_non_negative": ["M"],
            "pfcm_lambda_positive": ["lambda_"],
            "pfcm_mu_positive": ["mu"],
            "pfcm_k_positive_integer": ["k"],
            "pfcm_lambda_less_than_k_mu": ["lambda_", "mu", "k"],
        }.get(constraint_id, [])

    def _can_evaluate_constraint(self, validator: Any, inputs: dict[str, Any]) -> bool:
        try:
            validator(inputs)
            return True
        except Exception:
            return False

    def _constraint_validators(self) -> dict[str, Any]:
        return {
            "lambda_positive": lambda inputs: positive(inputs.get("lambda_")),
            "mu_positive": lambda inputs: positive(inputs.get("mu")),
            "rho_positive": lambda inputs: positive(inputs.get("rho")),
            "rho_non_negative": lambda inputs: non_negative(inputs.get("rho")),
            "n_positive_integer": lambda inputs: positive_integer(inputs.get("n")),
            "n_non_negative_integer": lambda inputs: isinstance(inputs.get("n"), int) and inputs.get("n", -1) >= 0,
            "k_positive_integer": lambda inputs: positive_integer(inputs.get("k")),
            "M_positive_integer": lambda inputs: positive_integer(inputs.get("M")),
            "probability": lambda inputs: probability(inputs.get("rho")),
        }

    def _discard_formula(self, result: MatchResult | None, formula: FormulaDefinition, reason: str) -> None:
        if result is not None:
            result.discarded.append({"formula_id": formula.id, "reason": reason})

from __future__ import annotations

from typing import Any, Dict, List, Optional

from domain.entities.definitions import CalculationRequest, CalculationResult, FormulaDefinition
from domain.entities.enums import CalculationStatus
from domain.formulas.registry import get_formula_by_id
from domain.services.contracts import (
    FormulaMatcher,
    InputNormalizer,
    MathResolver,
    PremiumPolicy,
    PremiumPolicyResult,
    ResultValidator,
    VariableResolver,
)
from domain.services.matcher import FormulaMatcher as DefaultFormulaMatcher
from domain.services.solver import FormulaSolver


class PremiumPolicyService(PremiumPolicy):
    """Service for enforcing premium/deluxe business policies."""

    def __init__(self, blocked_conditions: Optional[List[Dict[str, Any]]] = None):
        self.blocked_conditions = blocked_conditions or [
            {
                "condition": "all_fields_filled",
                "message": "Premium feature: Complete exploration requires premium access. Please select specific variables to calculate."
            }
        ]

    def check_premium(self, request: CalculationRequest) -> PremiumPolicyResult:
        """Check if the request violates any premium policies."""
        for condition in self.blocked_conditions:
            if condition["condition"] == "all_fields_filled":
                # Block if all possible fields are filled (indicating exploration attempt)
                filled_fields = sum(1 for value in request.inputs.values() if value is not None)
                total_fields = len(request.inputs)
                if filled_fields == total_fields and filled_fields > 3:  # Arbitrary threshold
                    return PremiumPolicyResult(
                        allowed=False,
                        message=condition["message"],
                        policy_name="exploration_limit"
                    )

        return PremiumPolicyResult(allowed=True, message="Access granted")


class CalculationOrchestrator:
    """Central orchestrator for the complete queue theory formula calculation flow."""

    def __init__(
        self,
        normalizer: Optional[InputNormalizer] = None,
        resolver: Optional[VariableResolver] = None,
        matcher: Optional[FormulaMatcher] = None,
        solver: Optional[MathResolver] = None,
        validator: Optional[ResultValidator] = None,
        premium_policy: Optional[PremiumPolicy] = None,
    ):
        self.normalizer = normalizer
        self.resolver = resolver
        self.matcher = matcher or DefaultFormulaMatcher()
        self.solver = solver or FormulaSolver()
        self.validator = validator
        self.premium_policy = premium_policy or PremiumPolicyService()

    def orchestrate(self, request: CalculationRequest) -> CalculationResult:
        """Execute the complete calculation flow."""
        result = CalculationResult(status=CalculationStatus.FAILED)

        try:
            # Step 1: Normalize inputs
            normalized_inputs = self.normalizer.normalize(request.inputs) if self.normalizer else request.inputs
            result.add_step("Input normalization", {"normalized": normalized_inputs})

            # Step 2: Resolve variables
            resolved_inputs = self.resolver.resolve(normalized_inputs) if self.resolver else normalized_inputs
            result.add_step("Variable resolution", {"resolved": resolved_inputs})

            # Step 3: Check for conflicts
            conflicts = self._detect_conflicts(resolved_inputs)
            if conflicts:
                result.status = CalculationStatus.FAILED
                result.messages.append(f"Input conflicts detected: {conflicts}")
                result.add_step("Conflict detection", {"conflicts": conflicts})
                return result

            # Step 4: Validate premium policy
            policy_result = self.premium_policy.check_premium(request)
            if not policy_result.allowed:
                result.status = CalculationStatus.FAILED
                result.messages.append(policy_result.message)
                result.add_step("Premium policy check", {"blocked": True, "reason": policy_result.message})
                return result

            # If a specific formula is selected, use it directly
            if request.selected_formula_id:
                selected_formula = self._find_formula_by_id(request.selected_formula_id)
                if not selected_formula:
                    result.status = CalculationStatus.FAILED
                    result.messages.append(f"Selected formula '{request.selected_formula_id}' not found")
                    result.add_step("Formula lookup", {"formula_id": request.selected_formula_id, "found": False})
                    return result
                result.add_step("Formula selection", {"formula_id": selected_formula.id})
            else:
                # Step 5: Find candidate formulas
                candidates = self.matcher.match_formulas(resolved_inputs)
                result.add_step("Formula matching", {"candidates": [f.id for f in candidates.matched_formulas]})

                if not candidates.matched_formulas:
                    result.messages.append("No matching formulas found")
                    result.add_step("No candidates", {})
                    return result

                # Step 6: Score and rank candidates
                scored_candidates = self._score_candidates(candidates.matched_formulas, resolved_inputs)
                result.add_step("Candidate scoring", {"scored": [(f.id, score) for f, score in scored_candidates]})

                # Step 7: Resolve ambiguity
                selected_formula = self._resolve_ambiguity(scored_candidates)

                if selected_formula is None:
                    # Ambiguous case - return top 2
                    top_candidates = scored_candidates[:2]
                    result.status = CalculationStatus.SUCCESS
                    result.messages.append("Multiple formula options available")
                    result.candidate_formulas = [f for f, _ in top_candidates]
                    result.add_step("Ambiguity resolution", {"ambiguous": True, "top_candidates": [f.id for f, _ in top_candidates]})
                    return result

            # Step 8: Execute calculation or validation
            final_result = self._execute_calculation(selected_formula, resolved_inputs)
            result.status = final_result.status
            result.messages.extend(final_result.messages)
            result.warnings.extend(final_result.warnings)
            result.computed_value = final_result.computed_value
            result.computed_variable = final_result.computed_variable
            result.formula_used = final_result.formula_used
            result.validation_result = final_result.validation_result
            result.add_step("Final execution", {"formula": selected_formula.id, "mode": "calculation" if result.computed_value else "validation"})

            return result

        except Exception as e:
            result.status = CalculationStatus.FAILED
            result.messages.append(f"Orchestration error: {str(e)}")
            result.add_step("Error", {"exception": str(e)})
            return result

    def _find_formula_by_id(self, formula_id: str) -> Optional[FormulaDefinition]:
        """Find a formula by its ID."""
        return get_formula_by_id(formula_id)

    def _score_candidates(self, candidates: List[FormulaDefinition], inputs: Dict[str, Any]) -> List[tuple[FormulaDefinition, float]]:
        """Score and rank candidate formulas."""
        scored = []
        for formula in candidates:
            score = self._calculate_score(formula, inputs)
            scored.append((formula, score))
        return sorted(scored, key=lambda x: x[1], reverse=True)

    def _calculate_score(self, formula: FormulaDefinition, inputs: Dict[str, Any]) -> float:
        """Calculate relevance score for a formula."""
        score = 0.0

        # Score based on input variable matches
        matched_inputs = sum(1 for var in formula.input_variables if inputs.get(var) is not None)
        score += matched_inputs * 10

        # Bonus for result variable match
        if inputs.get(formula.result_variable) is not None:
            score += 15

        # Penalty for generic formulas
        if len(formula.input_variables) > 5:
            score -= 5

        return score

    def _detect_conflicts(self, resolved_inputs: Dict[str, Any]) -> List[str]:
        """Detect conflicts in resolved inputs."""
        # Simple conflict detection - check for duplicate variable definitions
        conflicts = []
        # For now, no conflicts detected
        return conflicts

    def _resolve_ambiguity(self, scored_candidates: List[tuple[FormulaDefinition, float]]) -> Optional[FormulaDefinition]:
        """Resolve ambiguity by selecting the best candidate or None if ambiguous."""
        if not scored_candidates:
            return None

        top_score = scored_candidates[0][1]
        top_candidates = [f for f, s in scored_candidates if s == top_score]

        if len(top_candidates) == 1:
            return top_candidates[0]

        # Check if top candidates are from different categories
        categories = set(f.category for f in top_candidates)
        if len(categories) > 1:
            return None  # Ambiguous

        # Same category - pick the first
        return top_candidates[0]

    def _execute_calculation(self, formula: FormulaDefinition, inputs: Dict[str, Any]) -> CalculationResult:
        """Execute the final calculation or validation."""
        return self.solver.resolve(formula, inputs)
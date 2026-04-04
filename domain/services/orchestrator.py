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
from domain.services.input_processing import DefaultInputNormalizer, DefaultVariableResolver, VariableResolutionResult
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
        self.normalizer = normalizer or DefaultInputNormalizer()
        self.resolver = resolver or DefaultVariableResolver()
        self.matcher = matcher or DefaultFormulaMatcher()
        self.solver = solver or FormulaSolver()
        self.validator = validator
        self.premium_policy = premium_policy or PremiumPolicyService()

    def orchestrate(self, request: CalculationRequest) -> CalculationResult:
        """Execute the complete calculation flow."""
        result = CalculationResult(status=CalculationStatus.FAILED)

        try:
            # Step 1: Normalize inputs
            normalized_inputs = self.normalizer.normalize(request.inputs)
            result.add_step("Input normalization", {"count": len(normalized_inputs)})

            # Step 2: Resolve variables
            resolution: VariableResolutionResult = self.resolver.resolve(normalized_inputs)
            result.add_step("Variable resolution", {"consolidated": list(resolution.consolidated_inputs.keys())})

            # Step 3: Check for conflicts
            if resolution.conflicts:
                conflict_msgs = [c.message for c in resolution.conflicts]
                result.status = CalculationStatus.FAILED
                result.messages.append(f"Input conflicts detected: {conflict_msgs}")
                result.add_step("Conflict detection", {"conflicts": conflict_msgs})
                return result

            # Step 4: Validate premium policy
            policy_result = self.premium_policy.check_premium(request)
            if not policy_result.allowed:
                result.status = CalculationStatus.FAILED
                result.messages.append(policy_result.message)
                result.add_step("Premium policy check", {"blocked": True, "reason": policy_result.message})
                return result

            # Build a plain dict of consolidated values for the solver
            resolved_values = {k: v.value for k, v in resolution.consolidated_inputs.items()}

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
                # Step 5: Find candidate formulas using the matcher
                match_result = self.matcher.match(resolution)
                result.add_step("Formula matching", {"candidates": [c.formula.id for c in match_result.candidates]})

                if not match_result.candidates:
                    result.messages.append("No matching formulas found")
                    result.add_step("No candidates", {})
                    return result

                # Step 6: Handle ambiguity
                if match_result.is_ambiguous:
                    top_candidates = match_result.selected[:2]
                    result.status = CalculationStatus.SUCCESS
                    result.messages.append("Multiple formula options available")
                    result.candidate_formulas = [c.formula for c in top_candidates]
                    result.add_step("Ambiguity resolution", {"ambiguous": True, "top_candidates": [c.formula.id for c in top_candidates]})
                    return result

                # Use the top selected candidate
                if match_result.selected:
                    selected_formula = match_result.selected[0].formula
                else:
                    selected_formula = match_result.candidates[0].formula
                result.add_step("Formula selected", {"formula_id": selected_formula.id})

            # Step 8: Execute calculation or validation
            final_result = self._execute_calculation(selected_formula, resolved_values)
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

    def _execute_calculation(self, formula: FormulaDefinition, inputs: Dict[str, Any]) -> CalculationResult:
        """Execute the final calculation or validation."""
        return self.solver.resolve(formula, inputs)
from __future__ import annotations

import math
from typing import Any, Optional

import sympy as sp

from domain.entities.definitions import CalculationResult, FormulaDefinition
from domain.entities.enums import CalculationStatus, ValidationResult
from domain.services.contracts import MathResolver, ResultValidator


class DefaultResultValidator(ResultValidator):
    """Default implementation of result validation with configurable tolerance."""

    def validate(self, expected: Any, actual: Any, tolerance: float = 1e-6) -> CalculationResult:
        """Validate expected vs actual values with tolerance."""
        result = CalculationResult(status=CalculationStatus.SUCCESS)

        try:
            # Handle None values
            if expected is None or actual is None:
                result.status = CalculationStatus.FAILED
                result.messages.append("Cannot validate None values")
                result.validation_result = ValidationResult.UNKNOWN
                return result

            # Convert to float for comparison
            expected_float = float(expected)
            actual_float = float(actual)

            # Check for NaN or infinity
            if math.isnan(expected_float) or math.isnan(actual_float):
                result.status = CalculationStatus.FAILED
                result.messages.append("Cannot validate NaN values")
                result.validation_result = ValidationResult.UNKNOWN
                return result

            if math.isinf(expected_float) or math.isinf(actual_float):
                result.status = CalculationStatus.FAILED
                result.messages.append("Cannot validate infinite values")
                result.validation_result = ValidationResult.UNKNOWN
                return result

            # Calculate absolute and relative differences
            abs_diff = abs(expected_float - actual_float)
            rel_diff = abs_diff / abs(expected_float) if expected_float != 0 else abs_diff

            # Use the smaller of absolute or relative tolerance
            is_close = abs_diff <= tolerance or rel_diff <= tolerance

            result.expected_value = expected_float
            result.computed_value = actual_float

            if is_close:
                result.validation_result = ValidationResult.PASS
                result.messages.append("Validation passed")
            else:
                result.validation_result = ValidationResult.FAIL
                result.status = CalculationStatus.FAILED
                result.messages.append(f"Validation failed: expected {expected_float:.6f}, got {actual_float:.6f}, difference {abs_diff:.6f}")

        except (ValueError, TypeError, OverflowError) as e:
            result.status = CalculationStatus.FAILED
            result.messages.append(f"Validation error: {str(e)}")
            result.validation_result = ValidationResult.UNKNOWN

        return result


class FormulaSolver(MathResolver):
    """Mathematical solver for queue theory formulas with direct calculation, despeje, and validation modes."""

    def __init__(self, result_validator: Optional[ResultValidator] = None):
        self.validator = result_validator or DefaultResultValidator()

    def resolve(self, formula: FormulaDefinition, inputs: dict[str, Any]) -> CalculationResult:
        """Resolve formula by determining the appropriate mode based on inputs."""
        result = CalculationResult(status=CalculationStatus.FAILED)

        # Check if result variable is provided (validation mode)
        result_value = inputs.get(formula.result_variable)
        if result_value is not None:
            # All inputs + result provided -> validation mode
            required_inputs = {var: inputs.get(var) for var in formula.input_variables}
            if all(v is not None for v in required_inputs.values()):
                return self._validate_formula(formula, required_inputs, result_value)
            # Result provided but some inputs missing -> despeje mode
            else:
                missing_vars = [var for var in formula.input_variables if inputs.get(var) is None]
                if len(missing_vars) == 1:
                    return self._solve_missing_variable(formula, inputs, result_value, missing_vars[0])
                else:
                    result.messages.append(f"Cannot solve: too many missing variables ({len(missing_vars)})")
                    return result
        else:
            # No result provided -> direct calculation mode
            required_inputs = {var: inputs.get(var) for var in formula.input_variables}
            if all(v is not None for v in required_inputs.values()):
                return self._calculate_direct(formula, required_inputs)
            else:
                missing_vars = [var for var in formula.input_variables if inputs.get(var) is None]
                result.messages.append(f"Cannot calculate: missing variables {missing_vars}")
                return result

    def solve_missing(self, formula: FormulaDefinition, inputs: dict[str, Any]) -> CalculationResult:
        """Legacy method for backward compatibility - solve for missing variable."""
        result_value = inputs.get(formula.result_variable)
        if result_value is None:
            result = CalculationResult(status=CalculationStatus.FAILED)
            result.messages.append("No result value provided for solving")
            return result

        missing_vars = [var for var in formula.input_variables if inputs.get(var) is None]
        if len(missing_vars) != 1:
            result = CalculationResult(status=CalculationStatus.FAILED)
            result.messages.append(f"Expected exactly 1 missing variable, found {len(missing_vars)}")
            return result

        return self._solve_missing_variable(formula, inputs, result_value, missing_vars[0])

    def _calculate_direct(self, formula: FormulaDefinition, inputs: dict[str, Any]) -> CalculationResult:
        """Direct calculation when all inputs are provided."""
        result = CalculationResult(status=CalculationStatus.SUCCESS)
        result.add_step("Starting direct calculation", {"inputs": inputs})

        try:
            computed_value = formula.calculate(inputs)
            result.computed_value = computed_value
            result.computed_variable = formula.result_variable
            result.formula_used = formula
            result.messages.append("Direct calculation completed")
            result.add_step("Calculation successful", {"result": computed_value})

        except (ValueError, ZeroDivisionError, OverflowError) as e:
            result.status = CalculationStatus.FAILED
            result.messages.append(f"Calculation error: {str(e)}")
            result.add_step("Calculation failed", {"error": str(e)})

        return result

    def _solve_missing_variable(self, formula: FormulaDefinition, inputs: dict[str, Any],
                               result_value: Any, missing_var: str) -> CalculationResult:
        """Solve for a missing variable using despeje."""
        result = CalculationResult(status=CalculationStatus.SUCCESS)
        result.add_step("Starting despeje", {"missing_var": missing_var, "target_result": result_value})

        try:
            # First try manual despeje if available
            if formula.manual_despeje is not None:
                computed_value = formula.manual_despeje(inputs, result_value, missing_var)
            else:
                # Use SymPy for symbolic solving
                computed_value = self._solve_symbolically(formula, inputs, result_value, missing_var)

            result.computed_value = computed_value
            result.computed_variable = missing_var
            result.formula_used = formula
            result.messages.append(f"Despeje completed for variable '{missing_var}'")
            result.add_step("Despeje successful", {"result": computed_value})

        except (ValueError, ZeroDivisionError, OverflowError) as e:
            result.status = CalculationStatus.FAILED
            result.messages.append(f"Despeje error: {str(e)}")
            result.add_step("Despeje failed", {"error": str(e)})

        return result

    def _validate_formula(self, formula: FormulaDefinition, inputs: dict[str, Any], expected_result: Any) -> CalculationResult:
        """Validate by recalculating and comparing with expected result."""
        result = CalculationResult(status=CalculationStatus.SUCCESS)
        result.add_step("Starting validation", {"inputs": inputs, "expected": expected_result})

        try:
            # Calculate the expected result
            computed_value = formula.calculate(inputs)
            result.computed_value = computed_value
            result.expected_value = expected_result
            result.formula_used = formula

            # Use the validator to compare
            validation_result = self.validator.validate(expected_result, computed_value)
            result.validation_result = validation_result.validation_result
            result.messages.extend(validation_result.messages)
            result.warnings.extend(validation_result.warnings)

            if validation_result.validation_result == ValidationResult.PASS:
                result.messages.append("Validation passed")
            else:
                result.messages.append("Validation failed")
                result.status = CalculationStatus.FAILED

            result.add_step("Validation completed", {
                "computed": computed_value,
                "expected": expected_result,
                "passed": validation_result.validation_result == ValidationResult.PASS
            })

        except (ValueError, ZeroDivisionError, OverflowError) as e:
            result.status = CalculationStatus.FAILED
            result.messages.append(f"Validation error: {str(e)}")
            result.validation_result = ValidationResult.UNKNOWN
            result.add_step("Validation failed", {"error": str(e)})

        return result

    def _solve_symbolically(self, formula: FormulaDefinition, inputs: dict[str, Any], result_value: Any, missing_var: str) -> float:
        """Use SymPy to solve for the missing variable symbolically."""
        try:
            # Parse the symbolic expression (e.g., "lambda * mu / (mu - lambda)")
            expr = sp.sympify(formula.symbolic_expression)
            
            # Define symbols for all variables in the formula
            all_vars = formula.input_variables + [formula.result_variable]
            symbols = {var: sp.Symbol(var) for var in all_vars}
            
            # Substitute known inputs into the expression
            substituted_expr = expr.subs({symbols[var]: value for var, value in inputs.items() if var != missing_var and var in symbols})
            
            # Set up the equation: substituted_expr = result_value
            equation = sp.Eq(substituted_expr, result_value)
            
            # Solve for the missing variable
            target_symbol = symbols.get(missing_var)
            if target_symbol is None:
                raise ValueError(f"Variable {missing_var} not found in formula variables")
            solutions = sp.solve(equation, target_symbol)
            
            # Filter for real solutions
            real_solutions = [sol for sol in solutions if sol.is_real]
            
            if not real_solutions:
                raise ValueError(f"No real solution found for {missing_var}")
            
            # Prefer positive solutions for physical quantities (e.g., rates, times)
            positive_solutions = [sol for sol in real_solutions if sol > 0]
            if positive_solutions:
                return float(positive_solutions[0])  # Return the first positive real solution
            
            # Fallback to first real solution
            return float(real_solutions[0])
        
        except Exception as e:
            raise ValueError(f"Symbolic solving failed for {missing_var}: {str(e)}")

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Optional

from .enums import (
    CalculationStatus,
    FormulaCategory,
    FormulaType,
    ValidationResult,
    VariableScope,
    VariableType,
)


@dataclass
class VariableDefinition:
    id: str
    symbol: str
    display_name: str
    description: str
    scope: VariableScope
    variable_type: VariableType
    unit: Optional[str] = None
    allowed_categories: List[FormulaCategory] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)

    def validate(self, value: Any) -> tuple[bool, list[str]]:
        errors: list[str] = []

        if value is None:
            errors.append("Value is required.")
            return False, errors

        if self.variable_type == VariableType.INTEGER and not isinstance(value, int):
            errors.append("Value must be an integer.")

        if self.variable_type == VariableType.FLOAT and not isinstance(value, (int, float)):
            errors.append("Value must be numeric.")

        min_value = self.constraints.get("min")
        max_value = self.constraints.get("max")

        if min_value is not None and isinstance(value, (int, float)) and value < min_value:
            errors.append(f"Value must be >= {min_value}.")

        if max_value is not None and isinstance(value, (int, float)) and value > max_value:
            errors.append(f"Value must be <= {max_value}.")

        return len(errors) == 0, errors


@dataclass
class CategoryDefinition:
    id: str
    name: str
    description: str
    independent_variables: List[str] = field(default_factory=list)
    dependent_variables: List[str] = field(default_factory=list)
    shared_variables: List[str] = field(default_factory=list)

    def all_variables(self) -> List[str]:
        return list({*self.independent_variables, *self.dependent_variables, *self.shared_variables})


@dataclass
class FormulaDefinition:
    id: str
    name: str
    category: FormulaCategory
    description: str
    result_variable: str
    input_variables: List[str]
    formula_type: FormulaType
    priority: int = 0
    premium_mode: bool = False
    validator: Optional[Callable[[dict[str, Any], Any], bool]] = None
    constraints: dict[str, Any] = field(default_factory=dict)
    manual_calculation: Optional[Callable[[dict[str, Any]], Any]] = None
    manual_despeje: Optional[Callable[[dict[str, Any], Any, str], Any]] = None
    symbolic_expression: Optional[str] = None

    def is_applicable(self, available_variables: Iterable[str]) -> bool:
        return all(variable in available_variables for variable in self.input_variables)

    def calculate(self, inputs: dict[str, Any]) -> Any:
        if self.manual_calculation is None:
            raise NotImplementedError("Manual calculation is not defined for this formula.")
        return self.manual_calculation(inputs)

    def despeje(self, inputs: dict[str, Any], result_value: Any, missing_var: str) -> Any:
        if self.manual_despeje is not None:
            return self.manual_despeje(inputs, result_value, missing_var)
        raise NotImplementedError("Manual despeje is not defined for this formula.")

    def validate_result(self, inputs: dict[str, Any], value: Any) -> tuple[bool, Optional[str]]:
        if self.validator is None:
            return True, None
        valid = self.validator(inputs, value)
        return valid, None if valid else "Result does not satisfy formula constraints." 


@dataclass
class InputValue:
    variable_id: str
    raw_value: Any
    value: Any
    category_id: Optional[str] = None
    source: Optional[str] = None
    is_valid: bool = False
    errors: List[str] = field(default_factory=list)
    normalized: bool = False

    def mark_invalid(self, error: str) -> None:
        self.errors.append(error)
        self.is_valid = False

    def mark_valid(self) -> None:
        self.is_valid = True


@dataclass
class MatchCandidate:
    formula: FormulaDefinition
    matching_score: float = 0.0
    category_score: float = 0.0
    is_ambiguous: bool = False
    matched_variables: List[str] = field(default_factory=list)
    missing_variables: List[str] = field(default_factory=list)
    conflict_details: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def summarize(self) -> dict[str, Any]:
        return {
            "formula_id": self.formula.id,
            "score": self.matching_score,
            "category_score": self.category_score,
            "ambiguous": self.is_ambiguous,
            "matched": self.matched_variables,
            "missing": self.missing_variables,
            "conflicts": self.conflict_details,
            "warnings": self.warnings,
        }


@dataclass
class CalculationResult:
    status: CalculationStatus
    messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    formula_used: Optional[FormulaDefinition] = None
    computed_variable: Optional[str] = None
    computed_value: Any = None
    expected_value: Any = None
    validation_result: Optional[ValidationResult] = None
    steps: List[dict[str, Any]] = field(default_factory=list)
    candidate_formulas: List[FormulaDefinition] = field(default_factory=list)

    def add_step(self, description: str, payload: dict[str, Any] | None = None) -> None:
        self.steps.append({"description": description, "payload": payload or {}})

    def add_warning(self, warning: str) -> None:
        self.warnings.append(warning)

    @property
    def is_success(self) -> bool:
        return self.status == CalculationStatus.SUCCESS


@dataclass
class CalculationRequest:
    inputs: dict[str, Any]
    selected_formula_id: Optional[str] = None

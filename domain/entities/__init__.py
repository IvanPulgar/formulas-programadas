"""Domain entities package.

This package contains domain objects, enums and value types used by the queue
formula engine.
"""

from .catalog import (
    CATEGORY_CATALOG,
    CATEGORY_CATALOG as category_catalog,
    VARIABLE_CATALOG,
    VARIABLE_CATALOG as variable_catalog,
    get_category_definition,
    get_variable_definition,
    list_variables_by_category,
)
from .definitions import (
    CalculationResult,
    CategoryDefinition,
    FormulaDefinition,
    InputValue,
    MatchCandidate,
    VariableDefinition,
)
from .enums import (
    CalculationStatus,
    FormulaCategory,
    FormulaType,
    ValidationResult,
    VariableScope,
    VariableType,
)

__all__ = [
    "VariableDefinition",
    "CategoryDefinition",
    "FormulaDefinition",
    "InputValue",
    "MatchCandidate",
    "CalculationResult",
    "CalculationStatus",
    "FormulaCategory",
    "FormulaType",
    "ValidationResult",
    "VariableScope",
    "VariableType",
    "CATEGORY_CATALOG",
    "VARIABLE_CATALOG",
    "get_category_definition",
    "get_variable_definition",
    "list_variables_by_category",
]

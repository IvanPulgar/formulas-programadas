"""Domain services package.

This package contains business services and orchestration logic for the formula
engine, separate from HTTP transport and persistence.
"""

from .contracts import (
    InputNormalizer,
    FormulaRegistry,
    MathResolver,
    ResultValidator,
    VariableResolver,
)
from .input_processing import DefaultInputNormalizer, DefaultVariableResolver
from .matcher import CategoryScorer, FormulaMatcher, AmbiguityResolver, MatchResult
from .solver import DefaultResultValidator, FormulaSolver

__all__ = [
    "InputNormalizer",
    "VariableResolver",
    "FormulaRegistry",
    "MathResolver",
    "ResultValidator",
    "DefaultInputNormalizer",
    "DefaultVariableResolver",
    "CategoryScorer",
    "FormulaMatcher",
    "AmbiguityResolver",
    "MatchResult",
    "DefaultResultValidator",
    "FormulaSolver",
]

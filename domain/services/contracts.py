from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable, Optional

from domain.entities.definitions import CalculationResult, FormulaDefinition, InputValue


class PremiumPolicyResult:
    """Result of a premium policy check."""

    def __init__(self, allowed: bool, message: str = "", policy_name: str = ""):
        self.allowed = allowed
        self.message = message
        self.policy_name = policy_name


class InputNormalizer(ABC):
    """Contract for input normalization and type-aware value mapping."""

    @abstractmethod
    def normalize(self, raw_inputs: dict[str, Any]) -> list[InputValue]:
        raise NotImplementedError


class FormulaRegistry(ABC):
    """Contract for registering and discovering available formulas."""

    @abstractmethod
    def register(self, formula: FormulaDefinition) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_formulas(self, category: Optional[str] = None) -> list[FormulaDefinition]:
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, formula_id: str) -> Optional[FormulaDefinition]:
        raise NotImplementedError


class VariableResolver(ABC):
    """Contract for resolving normalized inputs across categories and globals."""

    @abstractmethod
    def resolve(self, normalized_inputs: list[InputValue]) -> Any:
        raise NotImplementedError


class MathResolver(ABC):
    """Contract for resolving formula outputs and solving missing variables."""

    @abstractmethod
    def resolve(self, formula: FormulaDefinition, inputs: dict[str, Any]) -> CalculationResult:
        raise NotImplementedError

    @abstractmethod
    def solve_missing(self, formula: FormulaDefinition, inputs: dict[str, Any]) -> CalculationResult:
        raise NotImplementedError


class ResultValidator(ABC):
    """Contract for validating user-provided results against calculated expectations."""

    @abstractmethod
    def validate(self, expected: Any, actual: Any, tolerance: float = 1e-6) -> CalculationResult:
        raise NotImplementedError


class FormulaMatcher(ABC):
    """Contract for matching input variables to appropriate formulas."""

    @abstractmethod
    def match_formulas(self, inputs: dict[str, Any]) -> list[FormulaDefinition]:
        raise NotImplementedError

    @abstractmethod
    def score_candidates(self, candidates: list[FormulaDefinition], inputs: dict[str, Any]) -> list[tuple[FormulaDefinition, float]]:
        raise NotImplementedError


class PremiumPolicy(ABC):
    """Contract for enforcing premium feature policies."""

    @abstractmethod
    def check_premium(self, request: Any) -> PremiumPolicyResult:
        raise NotImplementedError

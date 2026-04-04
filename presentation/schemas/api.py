from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from domain.entities.enums import CalculationStatus, ValidationResult


class CandidateDetectionRequest(BaseModel):
    inputs: Dict[str, Any]


class FormulaSummary(BaseModel):
    id: str
    name: str
    description: str
    category: str
    result_variable: str
    input_variables: List[str]


class CandidateDetectionResponse(BaseModel):
    candidates: List[FormulaSummary]
    status: str = "success"
    message: Optional[str] = None


class CalculationRequest(BaseModel):
    inputs: Dict[str, Any]
    selected_formula_id: Optional[str] = None


class CalculationStep(BaseModel):
    description: str
    payload: Dict[str, Any]


class CalculationResponse(BaseModel):
    status: CalculationStatus
    messages: List[str]
    warnings: List[str]
    computed_variable: Optional[str] = None
    computed_value: Optional[Any] = None
    formula_used: Optional[FormulaSummary] = None
    validation_result: Optional[ValidationResult] = None
    candidate_formulas: List[FormulaSummary] = []
    steps: List[CalculationStep] = []
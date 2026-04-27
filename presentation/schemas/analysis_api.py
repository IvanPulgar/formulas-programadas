"""
Pydantic schemas for the statement analysis API — Phase 5.

These types are additive: they do not modify or extend any existing schema.

Endpoint: POST /api/analyze
  Request  → AnalyzeRequest
  Response → AnalyzeResponse
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Valid queue model identifiers (must stay in sync with FormulaCategory enum)
_VALID_MODELS = Literal["PICS", "PICM", "PFCS", "PFCM", "PFHET"]


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    """Input for the full pipeline: analyzer → planner → executor."""

    text: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Texto del enunciado del problema de colas (en español).",
        examples=["Llegan 10 clientes por hora. Tiempo de atención 4 minutos. Calcular Wq."],
    )
    hint_model: Optional[_VALID_MODELS] = Field(
        default=None,
        description=(
            "Modelo de colas a usar como pista o forzado. "
            "Valores posibles: PICS, PICM, PFCS, PFCM, PFHET. "
            "Si se omite, el modelo se identifica automáticamente."
        ),
    )


# ---------------------------------------------------------------------------
# Response sub-models
# ---------------------------------------------------------------------------


class ExtractedVariableInfo(BaseModel):
    """A single variable extracted from the statement."""

    variable_id: str
    raw_value: float
    unit: str
    normalized_value: Optional[float]
    confidence: float


class StepInfo(BaseModel):
    """Summary of one step in the resolution plan."""

    formula_id: str
    status: str          # "executable" | "blocked"
    is_primary: bool
    produces: list[str]
    blocked_by: list[str]


class StepResultInfo(BaseModel):
    """Execution outcome of one plan step."""

    formula_id: str
    success: bool
    computed_variable: Optional[str]
    computed_value: Optional[float]
    is_primary: bool
    skipped: bool
    error_message: str


# ---------------------------------------------------------------------------
# Literal sub-models (Phase 8 / Phase 11)
# ---------------------------------------------------------------------------


class FormulaPlanStepInfo(BaseModel):
    """One ordered step in a literal's formula plan (Phase 11)."""

    order: int
    formula_key: str
    formula_name: str
    formula_expression: str
    why_needed: str
    required_variables: list[str]
    produces: str


# Phase 15 — per-literal calculation result
class CalculationStepInfo(BaseModel):
    """One algebraic step inside a literal's numeric calculation."""

    formula_key: str
    expression: str
    substitution: str
    result: str


class LiteralCalculationResultInfo(BaseModel):
    """Numeric result computed for a single literal (Phase 15)."""

    literal_id: str
    objective: Optional[str]
    calculated: bool
    value: Optional[float] = None
    unit: str = ""
    display_value: str = ""
    calculation_steps: list[CalculationStepInfo] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class LiteralInfo(BaseModel):
    """A single detected sub-question (literal/inciso) from a problem statement."""

    literal_id: str                        # "a", "b", "c", …
    literal_text: str                      # original text of the sub-question
    inferred_objective: Optional[str]      # e.g. "compute_Wq", or None
    planned_step_ids: list[str] = Field(   # formula ids relevant to this objective
        default_factory=list
    )
    issues: list[str] = Field(             # per-literal diagnostic messages (Phase 9)
        default_factory=list
    )
    # Phase 11 — structured formula plan
    formula_plan: list[FormulaPlanStepInfo] = Field(default_factory=list)
    missing_variables: list[str] = Field(default_factory=list)
    # Phase 15 — numeric calculation result
    calculation_result: Optional[LiteralCalculationResultInfo] = None


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------


class AnalyzeResponse(BaseModel):
    """
    Full pipeline result for a statement analysis request.

    Fields
    ------
    ok : bool
        True when the pipeline ran without fatal errors.
    model_id : str | None
        Identified queue model (e.g. "PICS", "PICM").
    model_confidence : str
        Confidence level: "high", "medium", "low", "none".
    extracted_variables : list[ExtractedVariableInfo]
        Variables parsed from the statement.
    inferred_objectives : list[str]
        Objective ids inferred from the statement (e.g. "compute_Wq").
    plan_is_executable : bool
        True when the planner built at least one executable primary step.
    plan_steps : list[StepInfo]
        Ordered steps produced by the planner (topological order).
    is_complete : bool
        True when every primary step computed successfully.
    primary_values : dict[str, float | None]
        The final answers: variable_id → numeric value.
    step_results : list[StepResultInfo]
        Per-step execution details.
    issues : list[str]
        Human-readable diagnostics from all pipeline stages.
    """

    ok: bool
    model_id: Optional[str]
    model_confidence: str
    extracted_variables: list[ExtractedVariableInfo]
    inferred_objectives: list[str]
    plan_is_executable: bool
    plan_steps: list[StepInfo]
    is_complete: bool
    primary_values: dict[str, Optional[float]]
    step_results: list[StepResultInfo]
    issues: list[str]
    # Phase 8 — literal segmentation (optional, empty when no literals detected)
    statement_context: Optional[str] = None
    literals: list[LiteralInfo] = Field(default_factory=list)

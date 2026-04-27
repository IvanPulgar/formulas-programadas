"""
DTOs for the offline statement analysis pipeline (Phase 2).

These types are self-contained and do not extend or modify any existing
domain entities.  They flow through:
  StatementAnalysisRequest
      → StatementAnalyzer
          → ModelIdentifier  (produces list[ModelCandidate])
          → VariableExtractor (produces list[ExtractedVariable])
      → StatementAnalysisResult
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AnalysisConfidence(str, Enum):
    """Coarse confidence bucket for model or variable identification."""

    HIGH = "high"       # ≥ 0.75
    MEDIUM = "medium"   # 0.40 – 0.74
    LOW = "low"         # < 0.40
    NONE = "none"       # could not determine

    @staticmethod
    def from_score(score: float) -> "AnalysisConfidence":
        if score >= 0.75:
            return AnalysisConfidence.HIGH
        if score >= 0.40:
            return AnalysisConfidence.MEDIUM
        if score > 0.0:
            return AnalysisConfidence.LOW
        return AnalysisConfidence.NONE


class IssueSeverity(str, Enum):
    ERROR = "error"     # prevents analysis from continuing
    WARNING = "warning" # analysis continues but result may be unreliable
    INFO = "info"       # informational note


@dataclass
class AnalysisIssue:
    """A single diagnostic message produced during analysis."""

    severity: IssueSeverity
    code: str               # machine-readable identifier, e.g. "missing_variable"
    message: str            # human-readable description in Spanish
    context: str = ""       # optional: fragment of text that triggered the issue


@dataclass
class ModelCandidate:
    """A single candidate model identified from the statement text."""

    model_id: str           # e.g. "PICS", "PICM", "PFHET"
    score: float            # 0.0 – 1.0
    confidence: AnalysisConfidence = field(init=False)
    matched_keywords: list[str] = field(default_factory=list)
    disqualified_by: list[str] = field(default_factory=list)  # forbidden terms found

    def __post_init__(self) -> None:
        self.confidence = AnalysisConfidence.from_score(self.score)


@dataclass
class ExtractedVariable:
    """A single numeric variable extracted from the statement text."""

    variable_id: str        # matches VARIABLE_CATALOG key, e.g. "lambda_", "mu", "k"
    raw_value: float        # value as parsed from text (may need unit conversion)
    unit: str               # unit string as found in text, e.g. "clientes/hora"
    normalized_value: Optional[float] = None  # after unit normalization (clientes/min)
    extraction_source: str = ""  # text fragment that triggered extraction
    confidence: float = 1.0     # 0–1; lower when inference was indirect


@dataclass
class FormulaPlanStep:
    """One step in the formula execution plan for a detected literal (Phase 11)."""

    order: int                         # 1-based execution order
    formula_key: str                   # short identifier, e.g. "rho", "Lq", "P0"
    formula_name: str                  # human-readable name in Spanish
    formula_expression: str            # symbolic expression, e.g. "ρ = λ / μ"
    why_needed: str                    # reason this step appears in the plan
    required_variables: list[str]      # input variable ids (from text or prior steps)
    produces: str                      # output variable id


@dataclass
class CalculationStep:
    """One computed step in the numeric evaluation of a literal (Phase 15)."""

    formula_key: str          # short identifier, e.g. "rho", "Lq", "P0"
    expression: str           # symbolic expression shown to the user
    substitution: str         # expression with numeric values substituted
    result: str               # computed result string, e.g. "ρ = 0.9000"


@dataclass
class LiteralCalculationResult:
    """Numeric result for a single detected literal (Phase 15)."""

    literal_id: str
    objective: Optional[str]
    calculated: bool                                          # True when a numeric result is available
    value: Optional[float] = None                            # primary numeric result
    unit: str = ""                                           # unit identifier
    display_value: str = ""                                  # human-readable formatted string
    calculation_steps: list[CalculationStep] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)          # machine-readable issue codes


@dataclass
class DetectedLiteral:
    """A single sub-question (literal/inciso) detected in a problem statement."""

    literal_id: str                              # "a", "b", "c", …
    raw_text: str                                # text as it appears in the original input
    normalized_text: str                         # lowercased + accent-stripped version
    inferred_objective: Optional[str] = None     # e.g. "compute_Wq", or None
    planned_step_ids: list[str] = field(default_factory=list)  # formula ids (filled by analyzer)
    issues: list["AnalysisIssue"] = field(default_factory=list)  # per-literal diagnostics (Phase 9)
    # Phase 11 — structured formula plan
    formula_plan: list["FormulaPlanStep"] = field(default_factory=list)
    missing_variables: list[str] = field(default_factory=list)
    # Phase 15 — numeric calculation result per literal
    calculation_result: Optional[LiteralCalculationResult] = None


@dataclass
class StatementAnalysisRequest:
    """Input to the statement analyzer."""

    text: str                                          # raw problem statement (Spanish)
    hint_model: Optional[str] = None                  # optional user hint for model
    hint_objective: Optional[str] = None              # optional user hint for objective
    normalize_text: bool = True                       # lowercase + remove accents before processing


@dataclass
class StatementAnalysisResult:
    """Output of the statement analyzer."""

    # Model identification
    model_candidates: list[ModelCandidate] = field(default_factory=list)
    identified_model: Optional[str] = None            # top candidate model_id
    model_confidence: AnalysisConfidence = AnalysisConfidence.NONE

    # Variable extraction
    extracted_variables: list[ExtractedVariable] = field(default_factory=list)

    # Inferred objectives (ids matching objectives.json)
    inferred_objectives: list[str] = field(default_factory=list)

    # Diagnostics
    issues: list[AnalysisIssue] = field(default_factory=list)

    # Overall readiness — True when model + required variables are all present
    is_solvable: bool = False

    # The normalized (lowercased, accent-stripped) text used for analysis
    normalized_text: str = ""

    # Literal segmentation (Phase 8)
    # statement_context: text before the first literal marker (or full text when no literals)
    statement_context: Optional[str] = None
    # detected literals/incisos with per-literal objective inference
    literals: list[DetectedLiteral] = field(default_factory=list)

    # ------------------------------------------------------------------ helpers

    def add_issue(
        self,
        severity: IssueSeverity,
        code: str,
        message: str,
        context: str = "",
    ) -> None:
        self.issues.append(AnalysisIssue(severity=severity, code=code, message=message, context=context))

    def has_errors(self) -> bool:
        return any(i.severity == IssueSeverity.ERROR for i in self.issues)

    def variable_ids(self) -> set[str]:
        return {ev.variable_id for ev in self.extracted_variables}

    def get_variable(self, variable_id: str) -> Optional[ExtractedVariable]:
        for ev in self.extracted_variables:
            if ev.variable_id == variable_id:
                return ev
        return None

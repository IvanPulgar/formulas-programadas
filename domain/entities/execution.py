"""
DTOs for the Plan Executor — Phase 4.

A PlanExecutionResult captures the outcome of running every step in a
ResolutionPlan through the FormulaSolver, accumulating computed values as
they become available.

Design decisions:
  - Pure Python + stdlib; no external dependencies.
  - Does NOT own any mathematical logic — that belongs to FormulaSolver.
  - Additive: does not modify any Phase 1, 2, or 3 entity.
  - A step that is BLOCKED in the plan or fails numerically still produces a
    StepExecutionResult with success=False, so callers get a full trace.

Typical flow:
  ResolutionPlan + StatementAnalysisResult
      → PlanExecutor.execute()
          → PlanExecutionResult (one StepExecutionResult per plan step)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StepExecutionResult:
    """
    Outcome of executing a single ResolutionStep.

    Attributes
    ----------
    formula_id : str
        The formula that was (or was attempted to be) computed.
    success : bool
        True when FormulaSolver returned SUCCESS and produced a numeric value.
    computed_variable : str | None
        The variable id that was computed, e.g. "Wq", "P0".
    computed_value : float | None
        The numeric result, or None when the step failed.
    is_primary : bool
        Mirrors ResolutionStep.is_primary — True when this step serves an
        explicit objective requested by the user.
    skipped : bool
        True when the step was BLOCKED in the plan and was not attempted.
    error_message : str
        Human-readable explanation of the failure (empty on success).
    inputs_used : dict[str, float]
        Snapshot of the inputs passed to FormulaSolver for this step.
    """

    formula_id: str
    success: bool
    computed_variable: Optional[str] = None
    computed_value: Optional[float] = None
    is_primary: bool = False
    skipped: bool = False
    error_message: str = ""
    inputs_used: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanExecutionResult:
    """
    Full execution outcome for a ResolutionPlan.

    Attributes
    ----------
    model_id : str | None
        The queue model that was executed, e.g. "PICS", "PICM".
    objectives : list[str]
        The objective ids that were targeted.
    step_results : list[StepExecutionResult]
        One entry per ResolutionStep, in topological order.
    final_variables : dict[str, float]
        Accumulated pool of all variables after execution — inputs from the
        statement PLUS all successfully computed intermediary/final values.
    is_complete : bool
        True when every PRIMARY step executed successfully.
    execution_issues : list[str]
        Human-readable diagnostics (Spanish) emitted during execution.
    """

    model_id: Optional[str]
    objectives: list[str]
    step_results: list[StepExecutionResult] = field(default_factory=list)
    final_variables: dict[str, Any] = field(default_factory=dict)
    is_complete: bool = False
    execution_issues: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ helpers

    def primary_results(self) -> list[StepExecutionResult]:
        """Steps that directly answer a user objective."""
        return [r for r in self.step_results if r.is_primary]

    def successful_results(self) -> list[StepExecutionResult]:
        """Steps that produced a numeric value."""
        return [r for r in self.step_results if r.success]

    def failed_results(self) -> list[StepExecutionResult]:
        """Steps that were attempted but did not produce a value."""
        return [r for r in self.step_results if not r.success and not r.skipped]

    def skipped_results(self) -> list[StepExecutionResult]:
        """Steps that were not attempted because they were BLOCKED."""
        return [r for r in self.step_results if r.skipped]

    def get_value(self, variable_id: str) -> Optional[float]:
        """Return the computed (or extracted) value for a variable, or None."""
        return self.final_variables.get(variable_id)

    def primary_values(self) -> dict[str, Optional[float]]:
        """
        Mapping of computed_variable → computed_value for each primary step.
        Useful for quickly reading the answers to the user's objectives.
        """
        return {
            r.computed_variable: r.computed_value
            for r in self.primary_results()
            if r.computed_variable is not None
        }

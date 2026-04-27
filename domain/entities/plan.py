"""
DTOs for the Resolution Planner — Phase 3.

A ResolutionPlan describes which formulas to compute, in what order,
for a given StatementAnalysisResult (model + extracted variables + objectives).

Design decisions:
  - Pure Python + stdlib; no external dependencies.
  - Does NOT execute any mathematics.
  - Intended to be consumed by the existing FormulaSolver after manual
    or automated review.
  - Completely additive — does not modify any Phase 1 or Phase 2 entity.

Typical flow:
  StatementAnalysisResult
      → ResolutionPlanner.plan()
          → ResolutionPlan
              → (future) FormulaSolver.resolve() per step
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StepStatus(str, Enum):
    """Execution status of a single ResolutionStep."""

    EXECUTABLE = "executable"
    # All required input variables are available (from the statement or from
    # upstream steps that are themselves EXECUTABLE).

    BLOCKED = "blocked"
    # One or more required input variables are missing from the extracted set
    # and cannot be derived from earlier steps either.


@dataclass
class ResolutionStep:
    """
    A single formula computation in the resolution plan.

    Attributes
    ----------
    formula_id : str
        Matches a formula_id in dependencies.json, e.g. "pics_wq", "picm_p0".
    objective_ids : list[str]
        Objective ids (from objectives.json) that this step directly serves.
        Empty for auxiliary steps.
    produces : list[str]
        Variable ids this formula computes, e.g. ["Wq"].
    requires : list[str]
        Base input variable ids needed to run this formula, e.g. ["lambda_", "mu"].
    depends_on_formulas : list[str]
        Formula ids that must be executed before this one (ordering constraint).
        Derived from dependencies.json → depends_on_formulas.
    status : StepStatus
        EXECUTABLE if all required variables are available; BLOCKED otherwise.
    blocked_by : list[str]
        The variable_ids that are missing (empty when status is EXECUTABLE).
    is_primary : bool
        True when this step directly serves at least one objective.
        False for auxiliary / intermediate steps.
    """

    formula_id: str
    objective_ids: list[str]
    produces: list[str]
    requires: list[str]
    depends_on_formulas: list[str]
    status: StepStatus
    blocked_by: list[str]
    is_primary: bool


@dataclass
class ResolutionPlan:
    """
    Ordered sequence of ResolutionSteps produced by the ResolutionPlanner.

    Steps are topologically sorted: all formula-level dependencies come before
    the step that needs them.

    Attributes
    ----------
    model_id : str | None
        The queue-theory model identified for this plan.
    objectives : list[str]
        The objective ids that were requested (from StatementAnalysisResult).
    steps : list[ResolutionStep]
        Topologically sorted steps.  Auxiliary steps precede the primaries
        that depend on them.
    available_variables : set[str]
        Variable ids extracted from the statement (input to the planner).
    is_executable : bool
        True when at least one primary step is EXECUTABLE.
    plan_issues : list[str]
        Human-readable diagnostics (Spanish) emitted during planning, e.g.
        skipped objectives, missing formula definitions, etc.
    """

    model_id: Optional[str]
    objectives: list[str]
    steps: list[ResolutionStep] = field(default_factory=list)
    available_variables: set[str] = field(default_factory=set)
    is_executable: bool = False
    plan_issues: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ helpers

    def primary_steps(self) -> list[ResolutionStep]:
        """Return only the steps that directly serve an objective."""
        return [s for s in self.steps if s.is_primary]

    def executable_steps(self) -> list[ResolutionStep]:
        """Return steps whose status is EXECUTABLE."""
        return [s for s in self.steps if s.status == StepStatus.EXECUTABLE]

    def blocked_steps(self) -> list[ResolutionStep]:
        """Return steps whose status is BLOCKED."""
        return [s for s in self.steps if s.status == StepStatus.BLOCKED]

    def step_ids(self) -> list[str]:
        """Ordered list of formula_ids in the plan."""
        return [s.formula_id for s in self.steps]

    def get_step(self, formula_id: str) -> Optional[ResolutionStep]:
        """Return the step with the given formula_id, or None."""
        return next((s for s in self.steps if s.formula_id == formula_id), None)

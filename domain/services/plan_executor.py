"""
Plan Executor — Phase 4.

Connects the ResolutionPlanner (Phase 3) output with the FormulaSolver
(existing) to produce numeric results for each step in a ResolutionPlan.

Contract:
  - Receives a StatementAnalysisResult (Phase 2) and a ResolutionPlan (Phase 3).
  - Builds an initial variable pool from StatementAnalysisResult.extracted_variables
    (normalized values, i.e. per-minute rates).
  - Iterates steps in topological order (already guaranteed by the plan).
  - For each EXECUTABLE step: looks up the FormulaDefinition in the registry,
    calls FormulaSolver.resolve(), and — on success — propagates the computed
    value back into the pool so subsequent steps can use it.
  - For each BLOCKED step: records a skipped StepExecutionResult without
    calling the solver.
  - Returns a PlanExecutionResult with all step outcomes and the final pool.

Restrictions (non-negotiable):
  - Does NOT own any mathematical logic.
  - Does NOT modify solver.py, orchestrator.py, matcher.py, or any existing file.
  - Does NOT call FormulaSolver in any mode other than direct calculation
    (i.e., result_variable is never set in the inputs dict).
  - Fully offline and deterministic.
"""

from __future__ import annotations

from typing import Any, Optional

from domain.entities.analysis import StatementAnalysisResult
from domain.entities.enums import CalculationStatus
from domain.entities.execution import PlanExecutionResult, StepExecutionResult
from domain.entities.plan import ResolutionPlan, StepStatus
from domain.formulas.registry import get_formula_by_id
from domain.services.solver import FormulaSolver


class PlanExecutor:
    """
    Executes a ResolutionPlan step-by-step using the FormulaSolver.

    Parameters
    ----------
    solver : FormulaSolver | None
        If None, a default FormulaSolver is created.
    """

    def __init__(self, solver: Optional[FormulaSolver] = None) -> None:
        self._solver = solver or FormulaSolver()

    # ------------------------------------------------------------------ public

    def execute(
        self,
        analysis: StatementAnalysisResult,
        plan: ResolutionPlan,
    ) -> PlanExecutionResult:
        """
        Run all EXECUTABLE steps in the plan and return the aggregated result.

        Parameters
        ----------
        analysis : StatementAnalysisResult
            Output of StatementAnalyzer — provides the extracted variables.
        plan : ResolutionPlan
            Output of ResolutionPlanner — provides ordered steps and metadata.

        Returns
        -------
        PlanExecutionResult
            Contains per-step outcomes, final variable pool, and overall status.
        """
        result = PlanExecutionResult(
            model_id=plan.model_id,
            objectives=list(plan.objectives),
        )

        # Guard: nothing to execute.
        if not plan.steps:
            result.execution_issues.append(
                "El plan no contiene pasos para ejecutar."
            )
            return result

        # Build initial variable pool from extracted variables (normalized values).
        pool: dict[str, Any] = self._build_initial_pool(analysis)
        result.final_variables = dict(pool)  # snapshot; will be updated per step

        step_results: list[StepExecutionResult] = []

        for step in plan.steps:
            if step.status == StepStatus.BLOCKED:
                step_results.append(
                    StepExecutionResult(
                        formula_id=step.formula_id,
                        success=False,
                        is_primary=step.is_primary,
                        skipped=True,
                        error_message=(
                            f"Paso bloqueado: faltan variables {step.blocked_by}"
                        ),
                    )
                )
                continue

            # Step is EXECUTABLE — attempt to resolve it.
            step_result = self._execute_step(step.formula_id, step.is_primary, pool)
            step_results.append(step_result)

            # Propagate computed value into the pool for downstream steps.
            if step_result.success and step_result.computed_variable is not None:
                pool[step_result.computed_variable] = step_result.computed_value
                result.final_variables[step_result.computed_variable] = step_result.computed_value

        result.step_results = step_results

        # Overall completeness: every primary step must have succeeded.
        primary = [r for r in step_results if r.is_primary]
        result.is_complete = bool(primary) and all(r.success for r in primary)

        if not result.is_complete and primary:
            failed_primaries = [r.formula_id for r in primary if not r.success]
            result.execution_issues.append(
                f"Pasos primarios no completados: {failed_primaries}"
            )

        return result

    # ------------------------------------------------------------------ private

    def _build_initial_pool(self, analysis: StatementAnalysisResult) -> dict[str, Any]:
        """
        Convert extracted_variables into a {variable_id: value} dict.

        Uses normalized_value when available (unit-converted to per-minute),
        falling back to raw_value.

        Floats that represent whole numbers (e.g. k=3.0, M=4.0) are coerced to
        int so that formula validators that call isinstance(value, int) pass.
        """
        pool: dict[str, Any] = {}
        for ev in analysis.extracted_variables:
            value = ev.normalized_value if ev.normalized_value is not None else ev.raw_value
            if isinstance(value, float) and value == int(value):
                value = int(value)
            pool[ev.variable_id] = value
        return pool

    def _execute_step(
        self,
        formula_id: str,
        is_primary: bool,
        pool: dict[str, Any],
    ) -> StepExecutionResult:
        """
        Attempt to resolve a single formula step using the current variable pool.

        Returns a StepExecutionResult regardless of success or failure.
        """
        # Look up the FormulaDefinition in the registry.
        formula = get_formula_by_id(formula_id)
        if formula is None:
            return StepExecutionResult(
                formula_id=formula_id,
                success=False,
                is_primary=is_primary,
                error_message=f"Fórmula '{formula_id}' no encontrada en el registry.",
            )

        # Build input dict from pool — only the variables this formula needs.
        inputs: dict[str, Any] = {
            var: pool.get(var) for var in formula.input_variables
        }
        inputs_snapshot = {k: v for k, v in inputs.items() if v is not None}

        # Call FormulaSolver in direct calculation mode (no result_variable set).
        try:
            calc = self._solver.resolve(formula, inputs)
        except Exception as exc:  # noqa: BLE001 — solver should never raise; belt-and-suspenders
            return StepExecutionResult(
                formula_id=formula_id,
                success=False,
                is_primary=is_primary,
                error_message=f"Error inesperado en el solver: {exc}",
                inputs_used=inputs_snapshot,
            )

        if calc.status == CalculationStatus.SUCCESS and calc.computed_value is not None:
            return StepExecutionResult(
                formula_id=formula_id,
                success=True,
                computed_variable=calc.computed_variable or formula.result_variable,
                computed_value=float(calc.computed_value),
                is_primary=is_primary,
                inputs_used=inputs_snapshot,
            )

        # Solver returned FAILED or no value.
        error = "; ".join(calc.messages) if calc.messages else "El solver no produjo resultado."
        return StepExecutionResult(
            formula_id=formula_id,
            success=False,
            is_primary=is_primary,
            error_message=error,
            inputs_used=inputs_snapshot,
        )


def make_executor() -> PlanExecutor:
    """Factory: returns a PlanExecutor with a default FormulaSolver."""
    return PlanExecutor()

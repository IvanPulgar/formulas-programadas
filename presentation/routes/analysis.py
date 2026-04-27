"""
Analysis API router — Phase 5 & 6.

Phase 5: POST /api/analyze — JSON pipeline endpoint.
Phase 6: GET  /analyze    — HTML page for interactive statement analysis.

Restrictions:
  - Does NOT modify web.py, solver.py, matcher.py, or orchestrator.py.
  - Does NOT share state with the existing CalculationOrchestrator.
  - All pipeline components are instantiated per-request via factories.
  - Fully offline and deterministic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

_templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)

from domain.entities.analysis import StatementAnalysisRequest
from domain.services.plan_executor import make_executor
from domain.services.resolution_planner import make_planner
from domain.services.statement_analyzer import make_analyzer
from presentation.schemas.analysis_api import (
    AnalyzeRequest,
    AnalyzeResponse,
    CalculationStepInfo,
    ExtractedVariableInfo,
    FormulaPlanStepInfo,
    LiteralCalculationResultInfo,
    LiteralInfo,
    StepInfo,
    StepResultInfo,
)

router = APIRouter(tags=["analysis"])


@router.post(
    "/api/analyze",
    response_model=AnalyzeResponse,
    summary="Analizar enunciado y calcular resultados",
    description=(
        "Ejecuta el pipeline completo: identificación de modelo → extracción de variables "
        "→ planificación → ejecución. Devuelve un JSON estructurado con los resultados numéricos."
    ),
)
async def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """
    Full pipeline endpoint.

    POST /api/analyze
    Body: {"text": "<enunciado del problema>"}
    """
    try:
        issues: list[str] = []

        # ── Stage 1: analyze statement ──────────────────────────────────────
        analyzer = make_analyzer()
        req = StatementAnalysisRequest(text=body.text, hint_model=body.hint_model)
        analysis = analyzer.analyze(req)

        # Collect analysis-level diagnostics
        for issue in analysis.issues:
            issues.append(f"[{issue.severity.value}] {issue.message}")

        extracted = [
            ExtractedVariableInfo(
                variable_id=ev.variable_id,
                raw_value=ev.raw_value,
                unit=ev.unit,
                normalized_value=ev.normalized_value,
                confidence=ev.confidence,
            )
            for ev in analysis.extracted_variables
        ]

        # ── Stage 2: build resolution plan ──────────────────────────────────
        planner = make_planner()
        plan = planner.plan(analysis)

        for issue in plan.plan_issues:
            issues.append(f"[plan] {issue}")

        plan_steps = [
            StepInfo(
                formula_id=step.formula_id,
                status=step.status.value,
                is_primary=step.is_primary,
                produces=list(step.produces),
                blocked_by=list(step.blocked_by),
            )
            for step in plan.steps
        ]

        # ── Stage 3: execute plan ────────────────────────────────────────────
        executor = make_executor()
        exec_result = executor.execute(analysis, plan)

        for issue in exec_result.execution_issues:
            issues.append(f"[exec] {issue}")

        step_results = [
            StepResultInfo(
                formula_id=sr.formula_id,
                success=sr.success,
                computed_variable=sr.computed_variable,
                computed_value=sr.computed_value,
                is_primary=sr.is_primary,
                skipped=sr.skipped,
                error_message=sr.error_message,
            )
            for sr in exec_result.step_results
        ]

        # ── Stage 4: populate literal segmentation results (Phase 8 / Phase 11 / Phase 15) ──
        literal_info_list = []
        for lit in analysis.literals:
            # Phase 15 — calculation result
            calc_res: Optional[LiteralCalculationResultInfo] = None
            if lit.calculation_result is not None:
                cr = lit.calculation_result
                calc_res = LiteralCalculationResultInfo(
                    literal_id=cr.literal_id,
                    objective=cr.objective,
                    calculated=cr.calculated,
                    value=cr.value,
                    unit=cr.unit,
                    display_value=cr.display_value,
                    calculation_steps=[
                        CalculationStepInfo(
                            formula_key=s.formula_key,
                            expression=s.expression,
                            substitution=s.substitution,
                            result=s.result,
                        )
                        for s in cr.calculation_steps
                    ],
                    issues=list(cr.issues),
                )
            literal_info_list.append(
                LiteralInfo(
                    literal_id=lit.literal_id,
                    literal_text=lit.raw_text,
                    inferred_objective=lit.inferred_objective,
                    planned_step_ids=list(lit.planned_step_ids),
                    issues=[
                        f"[{issue.severity.value}] {issue.message}"
                        for issue in lit.issues
                    ],
                    formula_plan=[
                        FormulaPlanStepInfo(
                            order=step.order,
                            formula_key=step.formula_key,
                            formula_name=step.formula_name,
                            formula_expression=step.formula_expression,
                            why_needed=step.why_needed,
                            required_variables=list(step.required_variables),
                            produces=step.produces,
                        )
                        for step in lit.formula_plan
                    ],
                    missing_variables=list(lit.missing_variables),
                    calculation_result=calc_res,
                )
            )

        return AnalyzeResponse(
            ok=True,
            model_id=analysis.identified_model,
            model_confidence=analysis.model_confidence.value,
            extracted_variables=extracted,
            inferred_objectives=list(analysis.inferred_objectives),
            plan_is_executable=plan.is_executable,
            plan_steps=plan_steps,
            is_complete=exec_result.is_complete,
            primary_values=exec_result.primary_values(),
            step_results=step_results,
            issues=issues,
            statement_context=analysis.statement_context,
            literals=literal_info_list,
        )

    except ValidationError:
        # Re-raise so FastAPI returns 422
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error interno del pipeline: {exc}") from exc


# ---------------------------------------------------------------------------
# Phase 6 — HTML page
# ---------------------------------------------------------------------------


@router.get("/analyze", response_class=HTMLResponse)
async def analyze_page(request: Request) -> HTMLResponse:
    """Interactive statement analysis page."""
    return _templates.TemplateResponse(
        request,
        "analyze.html",
        {"request": request, "title": "Queue Theory Formula Engine"},
    )

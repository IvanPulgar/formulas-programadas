from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from domain.entities.definitions import CalculationRequest
from domain.services.orchestrator import CalculationOrchestrator
from presentation.schemas.api import (
    CalculationRequest as APICalculationRequest,
    CalculationResponse,
    CandidateDetectionRequest,
    CandidateDetectionResponse,
    FormulaSummary,
)
from presentation.schemas.health import HealthResponse

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

# Initialize orchestrator (in production, use dependency injection)
orchestrator = CalculationOrchestrator()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request, "title": "Queue Theory Formula Engine"},
    )


@router.post("/api/detect-candidates", response_model=CandidateDetectionResponse)
async def detect_candidates(request: CandidateDetectionRequest, req: Request):
    """Detect candidate formulas based on input variables."""
    try:
        calc_request = CalculationRequest(inputs=request.inputs)
        result = orchestrator.orchestrate(calc_request)

        if req.headers.get("HX-Request"):
            # Return HTML fragment for HTMX
            candidates_html = ""
            if result.candidate_formulas:
                candidates_html = "<ul>"
                for f in result.candidate_formulas:
                    candidates_html += f'<li><strong>{f.name}</strong> ({f.id}): {f.description}</li>'
                candidates_html += "</ul>"
            else:
                candidates_html = "<p>No candidates found.</p>"
            
            return HTMLResponse(content=candidates_html)

        # Return JSON for API calls
        if result.candidate_formulas:
            candidates = [
                FormulaSummary(
                    id=f.id,
                    name=f.name,
                    description=f.description,
                    category=f.category.value,
                    result_variable=f.result_variable,
                    input_variables=f.input_variables,
                )
                for f in result.candidate_formulas
            ]
            return CandidateDetectionResponse(
                candidates=candidates,
                message="Candidates detected successfully"
            )
        else:
            return CandidateDetectionResponse(
                candidates=[],
                message="No candidates found or calculation completed"
            )
    except Exception as e:
        if req.headers.get("HX-Request"):
            return HTMLResponse(content=f"<p>Error: {str(e)}</p>", status_code=500)
        raise HTTPException(status_code=500, detail=f"Error detecting candidates: {str(e)}")


@router.post("/api/calculate", response_model=CalculationResponse)
async def calculate(request: APICalculationRequest, req: Request):
    """Perform calculation with selected formula or detect candidates."""
    try:
        calc_request = CalculationRequest(
            inputs=request.inputs,
            selected_formula_id=request.selected_formula_id
        )
        result = orchestrator.orchestrate(calc_request)

        if req.headers.get("HX-Request"):
            # Return HTML fragment for HTMX
            if result.status.value == "success" and result.computed_value is not None:
                html = f"""
                <div class="result-panel">
                    <h3>Calculation Result</h3>
                    <p><strong>Formula:</strong> {result.formula_used.name if result.formula_used else 'N/A'}</p>
                    <p><strong>Computed Variable:</strong> {result.computed_variable}</p>
                    <p><strong>Value:</strong> {result.computed_value}</p>
                </div>
                """
            elif result.candidate_formulas:
                html = "<div class='candidates-panel'><h3>Select a Formula:</h3><ul>"
                for f in result.candidate_formulas:
                    html += f'<li><button onclick="selectFormula(\'{f.id}\')">{f.name}</button>: {f.description}</li>'
                html += "</ul></div>"
            else:
                html = f"<div class='error-panel'><p>Error: {'; '.join(result.messages)}</p></div>"
            
            return HTMLResponse(content=html)

        # Return JSON for API calls
        response = CalculationResponse(
            status=result.status,
            messages=result.messages,
            warnings=result.warnings,
            computed_variable=result.computed_variable,
            computed_value=result.computed_value,
            validation_result=result.validation_result,
            candidate_formulas=[
                FormulaSummary(
                    id=f.id,
                    name=f.name,
                    description=f.description,
                    category=f.category.value,
                    result_variable=f.result_variable,
                    input_variables=f.input_variables,
                )
                for f in result.candidate_formulas
            ],
            steps=[
                {"description": step["description"], "payload": step["payload"]}
                for step in result.steps
            ]
        )

        if result.formula_used:
            response.formula_used = FormulaSummary(
                id=result.formula_used.id,
                name=result.formula_used.name,
                description=result.formula_used.description,
                category=result.formula_used.category.value,
                result_variable=result.formula_used.result_variable,
                input_variables=result.formula_used.input_variables,
            )

        return response
    except Exception as e:
        if req.headers.get("HX-Request"):
            return HTMLResponse(content=f"<div class='error-panel'><p>Error: {str(e)}</p></div>", status_code=500)
        raise HTTPException(status_code=500, detail=f"Error performing calculation: {str(e)}")


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")

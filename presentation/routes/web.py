from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
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


async def _parse_inputs_from_request(req: Request) -> Dict[str, Any]:
    """Parse inputs from either JSON body or form-encoded data."""
    content_type = req.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await req.form()
        inputs: Dict[str, Any] = {}
        skip_keys = {"action", "category", "selected_formula_id"}
        for key, value in form.items():
            if key in skip_keys:
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            try:
                inputs[key] = float(value)
            except (ValueError, TypeError):
                inputs[key] = value
        selected_formula_id = form.get("selected_formula_id")
        return {"inputs": inputs, "selected_formula_id": selected_formula_id if selected_formula_id else None, "action": form.get("action")}
    else:
        body = await req.json()
        return {"inputs": body.get("inputs", {}), "selected_formula_id": body.get("selected_formula_id"), "action": None}




templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

# Initialize orchestrator (in production, use dependency injection)
orchestrator = CalculationOrchestrator()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    from presentation.catalogs.formula_gallery import GALLERY_CAROUSELS, TOTAL_FORMULA_COUNT

    demo_mode = getattr(request.app.state, "demo_mode", False)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "title": "Queue Theory Formula Engine",
            "carousels": GALLERY_CAROUSELS,
            "total_formulas": TOTAL_FORMULA_COUNT,
            "demo_mode": demo_mode,
        },
    )


@router.post("/api/detect-candidates", response_model=CandidateDetectionResponse)
async def detect_candidates(req: Request):
    """Detect candidate formulas based on input variables."""
    try:
        parsed = await _parse_inputs_from_request(req)
        calc_request = CalculationRequest(inputs=parsed["inputs"])
        result = orchestrator.orchestrate(calc_request)

        if req.headers.get("HX-Request"):
            # Return HTML fragment for HTMX
            if result.candidate_formulas:
                candidates_html = f"""
                <div class="alert alert-info">
                    <h4>🔍 Fórmulas Candidatas Encontradas</h4>
                    <p>Se encontraron {len(result.candidate_formulas)} fórmula(s) posible(s).</p>
                    <div class="candidates-list">
                """
                for f in result.candidate_formulas[:2]:  # Show max 2
                    formula_latex = get_formula_latex(f.id)
                    candidates_html += f"""
                        <div class="candidate-card">
                            <h4>{f.name}</h4>
                            <p><strong>Categoría:</strong> {f.category}</p>
                            <p><strong>Variable:</strong> {f.result_variable}</p>
                            <div class="math-formula">$${formula_latex}$$</div>
                            <button class="btn btn-primary"
                                    onclick="showModal('{f.id}', '{f.name}', '{f.category}', '{f.result_variable}')">
                                Ver detalles
                            </button>
                        </div>
                    """
                candidates_html += "</div>"

                if len(result.candidate_formulas) > 2:
                    candidates_html += '<p class="warning">Solo se muestran las primeras 2 fórmulas. Refine sus entradas para obtener resultados más precisos.</p>'

                candidates_html += "</div>"
            else:
                candidates_html = """
                <div class="alert alert-warning">
                    <h4>⚠️ No se encontraron fórmulas candidatas</h4>
                    <p>Verifique que haya ingresado suficientes variables para identificar una fórmula específica.</p>
                </div>
                """

            return HTMLResponse(content=candidates_html, headers={"HX-Trigger": "openResultModal"})

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
            return HTMLResponse(content=f"<p>Error: {str(e)}</p>", status_code=500, headers={"HX-Trigger": "openResultModal"})
        raise HTTPException(status_code=500, detail=f"Error detecting candidates: {str(e)}")


@router.post("/api/calculate", response_model=CalculationResponse)
async def calculate(req: Request):
    """Perform calculation with selected formula or detect candidates."""
    try:
        parsed = await _parse_inputs_from_request(req)
        calc_request = CalculationRequest(
            inputs=parsed["inputs"],
            selected_formula_id=parsed["selected_formula_id"]
        )
        result = orchestrator.orchestrate(calc_request)

        if req.headers.get("HX-Request"):
            # Return HTML fragment for HTMX
            from domain.entities.catalog import VARIABLE_CATALOG

            # Prepare result data for template
            result_data = {
                "status": result.status.value,
                "messages": result.messages,
                "warnings": result.warnings,
                "computed_variable": result.computed_variable,
                "computed_value": result.computed_value,
                "validation_result": result.validation_result.value if result.validation_result else None,
                "candidate_formulas": [
                    {
                        "id": f.id,
                        "name": f.name,
                        "description": f.description,
                        "category": f.category.value,
                        "result_variable": f.result_variable,
                        "input_variables": f.input_variables,
                    }
                    for f in result.candidate_formulas
                ],
                "used_variables": getattr(result, 'used_variables', {}),
            }

            if result.formula_used:
                result_data["formula_used"] = {
                    "id": result.formula_used.id,
                    "name": result.formula_used.name,
                    "description": result.formula_used.description,
                    "category": result.formula_used.category.value,
                    "result_variable": result.formula_used.result_variable,
                    "input_variables": result.formula_used.input_variables,
                }

            # Render result panel
            result_html = f"""
            <div class="result-panel">
                <div class="result-header {'success' if result.status.value == 'success' else 'info' if result.candidate_formulas else 'error'}">
                    <h3>{"✅ Cálculo Exitoso" if result.status.value == "success" else "🔍 Candidatos Encontrados" if result.candidate_formulas else "❌ Error"}</h3>
                </div>
            """

            if result.status.value == "success" and result.computed_value is not None:
                formula_latex = get_formula_latex(result.formula_used.id) if result.formula_used else ""
                result_html += f"""
                <div class="result-section">
                    <h4>Resultado del Cálculo</h4>
                    <div class="result-value">
                        <span class="result-number">{result.computed_value:.4f}</span>
                        <span class="result-unit">{VARIABLE_CATALOG[result.computed_variable].unit if result.computed_variable in VARIABLE_CATALOG else ''}</span>
                    </div>
                    <p><strong>Variable calculada:</strong> {VARIABLE_CATALOG[result.computed_variable].symbol if result.computed_variable in VARIABLE_CATALOG else result.computed_variable}</p>
                    {"<div class='math-formula'>$$" + formula_latex + "$$</div>" if formula_latex else ""}
                </div>
                """
            elif result.candidate_formulas:
                result_html += f"""
                <div class="result-section">
                    <h4>Fórmulas Candidatas ({len(result.candidate_formulas)})</h4>
                    <div class="candidates-preview">
                """
                for f in result.candidate_formulas[:2]:
                    formula_latex = get_formula_latex(f.id)
                    result_html += f"""
                        <div class="candidate-preview">
                            <h4>{f.name}</h4>
                            <p>{f.description}</p>
                            <div class="math-formula">$${formula_latex}$$</div>
                            <button class="btn btn-outline"
                                    onclick="showModal('{f.id}', '{f.name}', '{f.category}', '{f.result_variable}')">
                                Ver detalles
                            </button>
                        </div>
                    """
                result_html += "</div></div>"
            else:
                result_html += f"""
                <div class="result-section">
                    <h4>Errores</h4>
                    <ul>
                        {"".join(f"<li>{msg}</li>" for msg in result.messages)}
                    </ul>
                </div>
                """

            if result.warnings:
                result_html += f"""
                <div class="result-section warnings">
                    <h4>Advertencias</h4>
                    <ul>
                        {"".join(f"<li>{warning}</li>" for warning in result.warnings)}
                    </ul>
                </div>
                """

            result_html += "</div>"

            return HTMLResponse(content=result_html, headers={"HX-Trigger": "openResultModal"})

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
            return HTMLResponse(content=f"<div class='error-panel'><p>Error: {str(e)}</p></div>", status_code=500, headers={"HX-Trigger": "openResultModal"})
        raise HTTPException(status_code=500, detail=f"Error performing calculation: {str(e)}")


@router.get("/api/formula-modal/{formula_id}", response_class=HTMLResponse)
async def get_formula_modal(formula_id: str, request: Request):
    """Get modal content for a specific formula."""
    try:
        from domain.formulas.registry import get_formula_by_id

        formula = get_formula_by_id(formula_id)
        if not formula:
            return HTMLResponse(content="<p>Fórmula no encontrada</p>", status_code=404)

        # Get formula representation (simplified)
        formula_latex = get_formula_latex(formula_id)

        html = f"""
        <div class="modal-formula-detail">
            <h3>{formula.name}</h3>
            <p><strong>Categoría:</strong> {formula.category.value}</p>
            <p><strong>Variable resultante:</strong> {formula.result_variable}</p>
            <p><strong>Descripción:</strong> {formula.description}</p>

            <div class="formula-display">
                <strong>Representación matemática:</strong>
                <div class="math-formula">
                    $${formula_latex}$$
                </div>
            </div>

            <div class="modal-actions">
                <button class="btn btn-primary"
                        onclick="selectFormula('{formula_id}')">
                    Usar esta fórmula
                </button>
                <button class="btn btn-secondary" onclick="closeModal()">Cancelar</button>
            </div>
        </div>
        """

        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(content=f"<p>Error: {str(e)}</p>", status_code=500)


def get_formula_latex(formula_id: str) -> str:
    """Get LaTeX representation for a formula (simplified examples)."""
    formulas = {
        "pics_p0": "P_0 = 1 - \\rho",
        "pics_pn": "P_n = (1 - \\rho) \\rho^n",
        "pics_l": "L = \\frac{\\rho}{1 - \\rho}",
        "pics_lq": "L_q = \\frac{\\rho^2}{1 - \\rho}",
        "pics_lq_from_rho": "L_q = \\frac{\\rho^2}{1 - \\rho}",
        "pics_w": "W = \\frac{1}{\\mu(1 - \\rho)}",
        "pics_wq": "W_q = \\frac{\\rho}{\\mu(1 - \\rho)}",
        "picm_p0": "P_0 = \\left[ \\sum_{k=0}^{c-1} \\frac{(\\lambda/\\mu)^k}{k!} + \\frac{(\\lambda/\\mu)^c}{c!} \\cdot \\frac{c\\mu}{c\\mu - \\lambda} \\right]^{-1}",
        "picm_pk": "P(\\text{esperar}) = P_k = \\frac{(\\lambda/\\mu)^c}{c!} \\cdot \\frac{1}{1-\\rho} \\cdot P_0",
        "pfcs_p0": "P_0 = \\frac{1 - \\rho}{1 - \\rho^{K+1}}",
        "pfcm_p0": "P_0 = \\left[ \\sum_{n=0}^{c-1} \\frac{(c\\rho)^n}{n!} + \\frac{(c\\rho)^c}{c!} \\cdot \\frac{1 - \\rho^{K-c+1}}{1 - \\rho} \\right]^{-1}",

        # PICS derived (A-group)
        "pics_prob_q_ge_2": "P(Q \\ge 2) = \\rho^{3}",

        # PICM derived (B-group)
        "picm_prob_idle":       "P(\\ge 1\\;\\text{desocupado}) = 1 - P_k",
        "picm_prob_exactly_c":  "P_c = \\frac{a^c}{c!}\\,P_0",
        "picm_prob_c_plus_r":   "P_{c+r} = P_c \\cdot \\rho^{r}",
        "picm_prob_c_plus_1":   "P_{c+1} = P_c \\cdot \\rho",
        "picm_prob_c_plus_2":   "P_{c+2} = P_c \\cdot \\rho^{2}",
        "picm_prob_q_waiting":  "P(Q = q) = P_c \\cdot \\rho^{q}",
        "picm_prob_q1_or_q2":   "P(Q=q_1 \\cup Q=q_2) = P_c\\rho^{q_1} + P_c\\rho^{q_2}",

        # Intro — Ley de Little
        "intro_little_system":  "L = \\lambda \\cdot W",
        "intro_little_queue":   "L_q = \\lambda \\cdot W_q",

        # PICS — alternative TT
        "pics_tt_alt": "TT = \\lambda \\cdot 8 \\cdot 0.30 \\cdot \\rho \\cdot W_n",

        # PICM — simplified CT and alternative TT
        "picm_ct_simplified": "CT = \\lambda \\cdot 8 \\cdot W \\cdot C_{TS} + k \\cdot C_S",
        "picm_tt_alt": "TT = \\lambda \\cdot 8 \\cdot 0.30 \\cdot P_k \\cdot W_n",

        # PFHET (C-group + D1)
        "pfhet_mu_bar":           "\\bar{\\mu} = \\frac{\\mu_1 + \\mu_2}{2}",
        "pfhet_lambda_n":         "\\lambda_n = (M - n)\\,\\lambda",
        "pfhet_mu_n":             "\\mu_n: 0\\;(n{=}0),\\;\\bar{\\mu}\\;(n{=}1),\\;\\mu_1{+}\\mu_2\\;(n{\\ge}2)",
        "pfhet_pn":               "P_n = P_0 \\prod_{i=0}^{n-1}\\frac{\\lambda_i}{\\mu_{i+1}}",
        "pfhet_p0":               "P_0 = \\left[1 + \\sum_{n=1}^{M}\\prod_{i=0}^{n-1}\\frac{\\lambda_i}{\\mu_{i+1}}\\right]^{-1}",
        "pfhet_prob_no_wait":     "P(\\text{no espera}) = \\frac{\\sum_{n=0}^{k-1}(M{-}n)P_n}{\\sum_{n=0}^{M-1}(M{-}n)P_n}",
        "pfhet_prob_n_ge_2":      "P(N \\ge 2) = 1 - (P_0 + P_1)",
        "pfhet_prob_available":   "P(\\text{disponible}) = P_0 + P_1",
        "pfhet_operating_units":  "\\text{Operando} = M - L",
        "pfhet_effective_arrival":"\\lambda_{ef} = \\lambda \\cdot (M - L)",
        "pfhet_percent_outside":  "\\%\\;\\text{fuera} = \\frac{M - L}{M} \\times 100",
    }
    return formulas.get(formula_id, f"Fórmula: {formula_id}")


# ─────────────────────────────────────────────────────────────────────
# SOLVER PAGE — manual formula resolution
# ─────────────────────────────────────────────────────────────────────

@router.get("/resolver", response_class=HTMLResponse)
async def solver_page(request: Request):
    """Render the manual formula resolver page."""
    from presentation.catalogs.solver_catalog import (
        SOLVER_GROUPS,
        SOLVER_FORMULA_COUNT,
        solver_json_data,
    )

    return templates.TemplateResponse(
        request,
        "solver.html",
        {
            "request": request,
            "title": "Queue Theory Formula Engine",
            "solver_groups": SOLVER_GROUPS,
            "total_formulas": SOLVER_FORMULA_COUNT,
            "solver_json": solver_json_data(),
        },
    )


@router.post("/api/solve/{formula_id}")
async def solve_formula(formula_id: str, request: Request):
    """Validate inputs and compute a single formula by its ID.

    Expects JSON body: {"inputs": {"lambda_": 4, "mu": 5, ...}}
    Returns JSON with success/error + result.
    """
    from domain.entities.catalog import VARIABLE_CATALOG
    from domain.formulas.registry import get_formula_by_id

    formula = get_formula_by_id(formula_id)
    if not formula:
        return JSONResponse(
            {"status": "error", "message": f"Fórmula no encontrada: {formula_id}"},
            status_code=404,
        )

    # ── Parse body ───────────────────────────────────────────────
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"status": "error", "message": "Cuerpo de la solicitud inválido."},
            status_code=400,
        )

    raw_inputs: Dict[str, Any] = body.get("inputs", {})

    # ── Backend validation ───────────────────────────────────────
    errors: List[str] = []
    validated: Dict[str, Any] = {}

    for var_id in formula.input_variables:
        raw = raw_inputs.get(var_id)

        # Required check
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            cat_entry = VARIABLE_CATALOG.get(var_id)
            symbol = cat_entry.symbol if cat_entry else var_id
            errors.append(f"El campo {symbol} es obligatorio.")
            continue

        # Numeric conversion
        try:
            value = float(raw)
        except (ValueError, TypeError):
            errors.append(f"{var_id}: debe ser un valor numérico.")
            continue

        # Integer check
        cat_entry = VARIABLE_CATALOG.get(var_id)
        if cat_entry and cat_entry.variable_type.value in ("integer", "count"):
            if value != int(value) or value < 0:
                errors.append(f"{cat_entry.symbol}: debe ser un entero no negativo.")
                continue
            value = int(value)

        # Constraint checks
        if cat_entry and cat_entry.constraints:
            c = cat_entry.constraints
            if c.get("strict_positive") and value <= 0:
                errors.append(f"{cat_entry.symbol}: debe ser estrictamente positivo (> 0).")
                continue
            if "min" in c and value < c["min"]:
                errors.append(f"{cat_entry.symbol}: debe ser ≥ {c['min']}.")
                continue
            if "max" in c and value > c["max"]:
                errors.append(f"{cat_entry.symbol}: debe ser ≤ {c['max']}.")
                continue

        validated[var_id] = value

    # ── Category-level preconditions ─────────────────────────────
    if not errors:
        cat = formula.category.value
        lam = validated.get("lambda_")
        mu = validated.get("mu")
        k = validated.get("k")

        if cat == "PICS":
            if lam is not None and mu is not None and lam >= mu:
                errors.append("Precondición PICS: λ debe ser menor que μ (λ < μ) para estabilidad.")
        elif cat == "PICM":
            if lam is not None and mu is not None and k is not None:
                if lam >= k * mu:
                    errors.append(f"Precondición PICM: λ debe ser menor que k·μ ({k}·{mu} = {k * mu}) para estabilidad.")
        # PFCS / PFCM: basic constraints already enforced above

    if errors:
        return JSONResponse(
            {"status": "error", "message": "; ".join(errors)},
            status_code=422,
        )

    # ── Execute calculation ──────────────────────────────────────
    try:
        result_value = formula.manual_calculation(validated)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        return JSONResponse(
            {"status": "error", "message": f"Error de cálculo: {str(exc)}"},
            status_code=422,
        )
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": f"Error inesperado: {str(exc)}"},
            status_code=500,
        )

    # ── Build success response ───────────────────────────────────
    result_var = formula.result_variable
    cat_entry = VARIABLE_CATALOG.get(result_var)

    return JSONResponse({
        "status": "success",
        "formulaId": formula.id,
        "formulaName": formula.name,
        "category": formula.category.value,
        "resultVariable": result_var,
        "resultSymbol": cat_entry.symbol if cat_entry else result_var,
        "resultName": "Probabilidad de esperar (Erlang C)" if formula.id == "picm_pk" else (cat_entry.display_name if cat_entry else result_var),
        "resultValue": round(result_value, 8) if isinstance(result_value, float) else result_value,
        "resultUnit": cat_entry.unit if cat_entry else "",
        "inputsUsed": {v: validated[v] for v in formula.input_variables if v in validated},
    })


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")

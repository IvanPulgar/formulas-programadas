"""
Solver catalog — builds formula metadata for the manual resolver page.

Reads FormulaDefinition objects from the domain registry and produces
SolverCard / SolverGroup structures that the resolver template and API
can consume.  LaTeX strings come from a local mapping; input-field
metadata comes from the domain VARIABLE_CATALOG.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from domain.entities.catalog import VARIABLE_CATALOG
from domain.entities.enums import FormulaCategory, VariableType
from domain.formulas.registry import FORMULAS


# ── LaTeX mapping  (domain formula-id → LaTeX) ──────────────────────
_LATEX: Dict[str, str] = {
    # Intro / General
    "intro_time_between_arrivals": r"T_{llegadas} = \frac{1}{\lambda}",
    "intro_time_between_services": r"T_{servicio} = \frac{1}{\mu}",
    "intro_system_response_time":  r"W = W_q + \frac{1}{\mu}",

    # Intro — Ley de Little
    "intro_little_system":  r"L = \lambda \cdot W",
    "intro_little_queue":   r"L_q = \lambda \cdot W_q",

    # PICS — stability / probability
    "pics_rho": r"\rho = \frac{\lambda}{\mu}",
    "pics_p0":  r"P_0 = 1 - \rho",
    "pics_pn":  r"P_n = (1 - \rho)\,\rho^{n}",
    "pics_l":   r"L = \frac{\lambda}{\mu - \lambda}",
    "pics_lq":  r"L_q = \frac{\lambda^{2}}{\mu(\mu - \lambda)}",
    "pics_lq_from_rho": r"L_q = \frac{\rho^{2}}{1 - \rho}",
    "pics_ln":  r"L_n = \frac{L_q}{\rho}",
    "pics_w":   r"W = \frac{1}{\mu - \lambda}",
    "pics_wq":  r"W_q = \frac{\lambda}{\mu(\mu - \lambda)}",
    "pics_wn":  r"W_n = \frac{W_q}{\rho}",

    # PICS — costs
    "pics_ct_te":  r"CT_{TE} = \lambda \cdot 8 \cdot W_q \cdot C_{TE}",
    "pics_ct_ts":  r"CT_{TS} = \lambda \cdot 8 \cdot W \cdot C_{TS}",
    "pics_ct_tse": r"CT_{TSE} = \lambda \cdot 8 \cdot \frac{1}{\mu} \cdot C_{TSE}",
    "pics_ct_s":   r"CT_S = C_S",
    "pics_ct":     r"CT = CT_{TE} + CT_{TS} + CT_{TSE} + CT_S",
    "pics_tt":     r"TT = \lambda \cdot 8 \cdot 0.30 \cdot W_q",
    "pics_tt_alt": r"TT = \lambda \cdot 8 \cdot 0.30 \cdot \rho \cdot W_n",

    # PICM — stability / probability
    "picm_stability": r"\rho = \frac{\lambda}{k\,\mu}",
    "picm_p0":  r"P_0 = \left[\sum_{n=0}^{k-1}\frac{a^n}{n!} + \frac{a^k}{k!}\cdot\frac{1}{1-\rho}\right]^{-1}",
    "picm_pk":  r"P(\text{esperar}) = P_k = \frac{a^k}{k!}\cdot\frac{1}{1-\rho}\,P_0",
    "picm_pne": r"P_{NE} = 1 - P_k",
    "picm_pn_without_queue": r"P_n = \frac{a^n}{n!}\,P_0 \quad (n < k)",
    "picm_pn_with_queue":   r"P_n = \frac{a^n}{k!\,k^{n-k}}\,P_0 \quad (n \ge k)",
    "picm_lq":  r"L_q = \frac{P_0\,a^k\,\rho}{k!\,(1-\rho)^2}",
    "picm_l":   r"L = a + L_q",
    "picm_wq":  r"W_q = \frac{L_q}{\lambda}",
    "picm_w":   r"W = W_q + \frac{1}{\mu}",
    "picm_ln":  r"L_n = \frac{L_q}{P_k}",
    "picm_wn":  r"W_n = \frac{W_q}{P_k}",

    # PICM — costs
    "picm_ct_te":  r"CT_{TE} = \lambda \cdot 8 \cdot W_q \cdot C_{TE}",
    "picm_ct_ts":  r"CT_{TS} = \lambda \cdot 8 \cdot W \cdot C_{TS}",
    "picm_ct_tse": r"CT_{TSE} = \lambda \cdot 8 \cdot \frac{1}{\mu} \cdot C_{TSE}",
    "picm_ct_s":   r"CT_S = k \cdot C_S",
    "picm_ct":     r"CT = CT_{TE} + CT_{TS} + CT_{TSE} + CT_S",
    "picm_tt":     r"TT = \lambda \cdot 8 \cdot 0.30 \cdot W_q",
    "picm_ct_simplified": r"CT = \lambda \cdot 8 \cdot W \cdot C_{TS} + k \cdot C_S",
    "picm_tt_alt": r"TT = \lambda \cdot 8 \cdot 0.30 \cdot P_k \cdot W_n",

    # PFCS
    "pfcs_p0":  r"P_0 = \left[\sum_{n=0}^{M}\binom{M}{n}\,a^n\right]^{-1}",
    "pfcs_pn":  r"P_n = \binom{M}{n}\,a^n\,P_0",
    "pfcs_rho": r"\rho = 1 - P_0",
    "pfcs_l":   r"L = \sum_{n=0}^{M} n\,P_n",
    "pfcs_lq":  r"L_q = \sum_{n=2}^{M}(n-1)\,P_n",
    "pfcs_wq":  r"W_q = \frac{L_q}{\lambda_{ef}}",
    "pfcs_w":   r"W = \frac{L}{\lambda_{ef}}",

    # PFCM
    "pfcm_p0":  r"P_0 = \left[\sum_{n=0}^{M}\frac{\binom{M}{n}\,a^n}{\min(n,k)!}\right]^{-1}",
    "pfcm_pk":  r"P_k = \frac{\binom{M}{k}\,a^k}{k!}\,P_0",
    "pfcm_pn":  r"P_n = \frac{\binom{M}{n}\,a^n}{\min(n,k)!\,k^{\max(0,n-k)}}\,P_0",
    "pfcm_lq":  r"L_q = \sum_{n=k+1}^{M}(n-k)\,P_n",
    "pfcm_l":   r"L = \sum_{n=0}^{M} n\,P_n",
    "pfcm_rho": r"\rho = \frac{L - L_q}{k}",
    "pfcm_wq":  r"W_q = \frac{L_q}{\lambda_{ef}}",
    "pfcm_w":   r"W = \frac{L}{\lambda_{ef}}",

    # PICS — derived (A-group)
    "pics_prob_q_ge_2": r"P(Q \ge 2) = \rho^{3}",

    # PICM — derived probabilities (B-group)
    "picm_prob_idle":       r"P(\ge 1\;\text{desocupado}) = 1 - P_k",
    "picm_prob_exactly_c":  r"P_c = \frac{a^c}{c!}\,P_0",
    "picm_prob_c_plus_r":   r"P_{c+r} = P_c \cdot \rho^{r}",
    "picm_prob_c_plus_1":   r"P_{c+1} = P_c \cdot \rho",
    "picm_prob_c_plus_2":   r"P_{c+2} = P_c \cdot \rho^{2}",
    "picm_prob_q_waiting":  r"P(Q = q) = P_c \cdot \rho^{q}",
    "picm_prob_q1_or_q2":   r"P(Q=q_1 \cup Q=q_2) = P_c\rho^{q_1} + P_c\rho^{q_2}",

    # PFHET — Pob. Finita Heterogénea (C-group + D1)
    "pfhet_mu_bar":           r"\bar{\mu} = \frac{\mu_1 + \mu_2}{2}",
    "pfhet_lambda_n":         r"\lambda_n = (M - n)\,\lambda",
    "pfhet_mu_n":             r"\mu_n: 0\;(n{=}0),\;\bar{\mu}\;(n{=}1),\;\mu_1{+}\mu_2\;(n{\ge}2)",
    "pfhet_pn":               r"P_n = P_0 \prod_{i=0}^{n-1}\frac{\lambda_i}{\mu_{i+1}}",
    "pfhet_p0":               r"P_0 = \left[1 + \sum_{n=1}^{M}\prod_{i=0}^{n-1}\frac{\lambda_i}{\mu_{i+1}}\right]^{-1}",
    "pfhet_prob_no_wait":     r"P(\text{no espera}) = \frac{\sum_{n=0}^{k-1}(M{-}n)P_n}{\sum_{n=0}^{M-1}(M{-}n)P_n}",
    "pfhet_prob_n_ge_2":      r"P(N \ge 2) = 1 - (P_0 + P_1)",
    "pfhet_prob_available":   r"P(\text{disponible}) = P_0 + P_1",
    "pfhet_operating_units":  r"\text{Operando} = M - L",
    "pfhet_effective_arrival":r"\lambda_{ef} = \lambda \cdot (M - L)",
    "pfhet_percent_outside":  r"\%\;\text{fuera} = \frac{M - L}{M} \times 100",
}


# ── Variable display info  ──────────────────────────────────────────
_VAR_SYMBOLS: Dict[str, str] = {
    "lambda_": "λ", "mu": "μ", "k": "k", "n": "n", "M": "M",
    "rho": "ρ", "P0": "P₀", "Pn": "Pn", "Pk": "Pk", "PNE": "PNE",
    "L": "L", "Lq": "Lq", "Ln": "Ln",
    "W": "W", "Wq": "Wq", "Wn": "Wn",
    "CTE": "CTE", "CTS": "CTS", "CTSE": "CTSE", "CS": "CS",
    "CT_TE": "CT_TE", "CT_TS": "CT_TS", "CT_TSE": "CT_TSE", "CT_S": "CT_S",
    "CT": "CT", "TT": "TT",
    "lambda_inv": "1/λ", "mu_inv": "1/μ",
    "a": "a", "Pc": "Pc", "r": "r", "q": "q",
    "q1": "q₁", "q2": "q₂",
    "mu1": "μ₁", "mu2": "μ₂", "mu_bar": "μ̄", "P1": "P₁",
    "lambda_n": "λₙ", "mu_n": "μₙ", "lambda_ef": "λ_ef",
}

_VAR_NAMES: Dict[str, str] = {
    "lambda_": "Tasa de llegada",
    "mu": "Tasa de servicio",
    "k": "Número de servidores",
    "n": "Número de clientes",
    "M": "Tamaño de población",
    "rho": "Factor de ocupación",
    "P0": "Prob. sistema vacío",
    "Pn": "Prob. n clientes",
    "Pk": "Prob. k servidores ocupados",
    "PNE": "Prob. de no esperar",
    "L": "Clientes en sistema",
    "Lq": "Clientes en cola",
    "Ln": "Clientes (condicionado)",
    "W": "Tiempo en sistema",
    "Wq": "Tiempo en cola",
    "Wn": "Tiempo (condicionado)",
    "CTE": "Costo tiempo espera",
    "CTS": "Costo tiempo servicio",
    "CTSE": "Costo servicio y espera",
    "CS": "Costo servidor",
    "CT_TE": "Costo total espera",
    "CT_TS": "Costo total servicio",
    "CT_TSE": "Costo total serv. y espera",
    "CT_S": "Costo total servidor",
    "CT": "Costo total",
    "TT": "Tiempo total",
    "lambda_inv": "Tiempo entre llegadas",
    "mu_inv": "Tiempo de servicio",
    "a": "Intensidad de tráfico",
    "Pc": "Prob. de c clientes",
    "r": "Exceso sobre c",
    "q": "Clientes esperando",
    "q1": "Primer índice cola",
    "q2": "Segundo índice cola",
    "mu1": "Tasa servicio servidor 1",
    "mu2": "Tasa servicio servidor 2",
    "mu_bar": "Tasa media de servicio",
    "P1": "Prob. 1 cliente",
    "lambda_n": "Tasa de nacimiento",
    "mu_n": "Tasa de muerte",
    "lambda_ef": "Tasa efectiva de llegada",
}

_CATEGORY_LABELS: Dict[str, str] = {
    "generales": "Introducción / Generales",
    "PICS": "PICS",
    "PICM": "PICM",
    "PFCS": "PFCS",
    "PFCM": "PFCM",
    "PFHET": "Pob. Finita Heterogénea",
}

# ── Preconditions by category ───────────────────────────────────────
_PRECONDITIONS: Dict[str, List[str]] = {
    "generales": [],
    "PICS": ["λ > 0", "μ > 0", "λ < μ (estabilidad)"],
    "PICM": ["λ > 0", "μ > 0", "k ≥ 1 entero", "λ < k·μ (estabilidad)"],
    "PFCS": ["λ > 0", "μ > 0", "M ≥ 1 entero"],
    "PFCM": ["λ > 0", "μ > 0", "k ≥ 1 entero", "M ≥ 1 entero"],
    "PFHET": ["μ₁ > 0", "μ₂ > 0", "M ≥ 1 entero"],
}

_RESULT_NAME_OVERRIDES: Dict[str, str] = {
    "picm_pk": "Prob. de esperar (Erlang C)",
}


# ── Dataclasses ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class InputField:
    """Describes one input field in the solver form."""
    var_id: str          # domain variable id  e.g. "lambda_"
    symbol: str          # display symbol       e.g. "λ"
    label: str           # full label           e.g. "Tasa de llegada"
    field_type: str      # "float" or "integer"
    step: str            # "any" for floats, "1" for ints
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    required: bool = True


@dataclass(frozen=True)
class SolverCard:
    """One formula available for manual resolution."""
    formula_id: str
    name: str
    category: str        # label, e.g. "PICS"
    category_key: str    # FormulaCategory value, e.g. "PICS"
    latex: str
    result_var_id: str
    result_symbol: str
    result_name: str
    input_fields: List[InputField]
    preconditions: List[str]
    description: str = ""


@dataclass(frozen=True)
class SolverGroup:
    """A category group of solver cards for one carousel."""
    id: str
    title: str
    cards: List[SolverCard]


# ── Build helpers ────────────────────────────────────────────────────

def _build_input_field(var_id: str) -> InputField:
    """Build an InputField from a domain variable id."""
    cat_entry = VARIABLE_CATALOG.get(var_id)
    if cat_entry:
        is_int = cat_entry.variable_type in (VariableType.INTEGER, VariableType.COUNT)
        constraints = cat_entry.constraints or {}
        return InputField(
            var_id=var_id,
            symbol=cat_entry.symbol,
            label=cat_entry.display_name,
            field_type="integer" if is_int else "float",
            step="1" if is_int else "any",
            min_value=constraints.get("min"),
            max_value=constraints.get("max"),
        )
    # Fallback for variables not in catalog
    return InputField(
        var_id=var_id,
        symbol=_VAR_SYMBOLS.get(var_id, var_id),
        label=_VAR_NAMES.get(var_id, var_id),
        field_type="float",
        step="any",
        min_value=0,
    )


def _build_solver_card(fdef) -> SolverCard:
    """Convert a domain FormulaDefinition into a SolverCard."""
    cat_value = fdef.category.value  # e.g. "PICS"
    return SolverCard(
        formula_id=fdef.id,
        name=fdef.name,
        category=_CATEGORY_LABELS.get(cat_value, cat_value),
        category_key=cat_value,
        latex=_LATEX.get(fdef.id, fdef.symbolic_expression or fdef.id),
        result_var_id=fdef.result_variable,
        result_symbol=_VAR_SYMBOLS.get(fdef.result_variable, fdef.result_variable),
        result_name=_RESULT_NAME_OVERRIDES.get(
            fdef.id,
            _VAR_NAMES.get(fdef.result_variable, fdef.result_variable),
        ),
        input_fields=[_build_input_field(v) for v in fdef.input_variables],
        preconditions=_PRECONDITIONS.get(cat_value, []),
        description=fdef.description or "",
    )


# ── Public API ───────────────────────────────────────────────────────

def build_solver_groups() -> List[SolverGroup]:
    """Return solver cards grouped by category for carousel display."""
    from collections import OrderedDict

    order = ["generales", "PICS", "PICM", "PFCS", "PFCM", "PFHET"]
    groups: Dict[str, List[SolverCard]] = OrderedDict((k, []) for k in order)

    for fdef in FORMULAS:
        cat = fdef.category.value
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(_build_solver_card(fdef))

    result: List[SolverGroup] = []
    for idx, (cat_key, cards) in enumerate(groups.items(), start=1):
        if cards:
            result.append(SolverGroup(
                id=f"sg{idx}",
                title=_CATEGORY_LABELS.get(cat_key, cat_key),
                cards=cards,
            ))
    return result


SOLVER_GROUPS: List[SolverGroup] = build_solver_groups()
SOLVER_FORMULA_COUNT: int = sum(len(g.cards) for g in SOLVER_GROUPS)


def solver_json_data() -> str:
    """Return a JSON string with all solver formulas for the frontend."""
    data: Dict[str, Any] = {}
    for group in SOLVER_GROUPS:
        for card in group.cards:
            data[card.formula_id] = {
                "name": card.name,
                "category": card.category,
                "categoryKey": card.category_key,
                "latex": card.latex,
                "resultVarId": card.result_var_id,
                "resultSymbol": card.result_symbol,
                "resultName": card.result_name,
                "preconditions": card.preconditions,
                "description": card.description,
                "inputs": [
                    {
                        "varId": f.var_id,
                        "symbol": f.symbol,
                        "label": f.label,
                        "fieldType": f.field_type,
                        "step": f.step,
                        "min": f.min_value,
                        "max": f.max_value,
                        "required": f.required,
                    }
                    for f in card.input_fields
                ],
            }
    return json.dumps(data, ensure_ascii=False)

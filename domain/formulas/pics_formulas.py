from __future__ import annotations

from typing import Any

from domain.entities import FormulaCategory, FormulaDefinition, FormulaType
from domain.rules import positive, probability, positive_integer


def validate_positive_number(name: str, value: Any) -> float:
    if not positive(value):
        raise ValueError(f"{name} debe ser un número positivo.")
    return float(value)


def validate_positive_integer(name: str, value: Any) -> int:
    if not positive_integer(value):
        raise ValueError(f"{name} debe ser un entero positivo.")
    return int(value)


def rho_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    mu = validate_positive_number("μ", inputs.get("mu"))
    return lambda_ / mu


def p0_formula(inputs: dict[str, Any]) -> float:
    rho = rho_formula(inputs)
    if not probability(rho):
        raise ValueError("ρ debe estar entre 0 y 1 para P0 en PICS.")
    return 1.0 - rho


def pn_formula(inputs: dict[str, Any]) -> float:
    p0 = p0_formula(inputs)
    rho = rho_formula(inputs)
    n = validate_positive_integer("n", inputs.get("n"))
    return p0 * rho**n


def l_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    mu = validate_positive_number("μ", inputs.get("mu"))
    if lambda_ >= mu:
        raise ValueError("λ debe ser menor que μ para L en PICS.")
    return lambda_ / (mu - lambda_)


def lq_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    mu = validate_positive_number("μ", inputs.get("mu"))
    if lambda_ >= mu:
        raise ValueError("λ debe ser menor que μ para Lq en PICS.")
    return lambda_ ** 2 / (mu * (mu - lambda_))


def ln_formula(inputs: dict[str, Any]) -> float:
    rho = rho_formula(inputs)
    lq = lq_formula(inputs)
    if rho == 0:
        raise ValueError("ρ no puede ser cero para Ln en PICS.")
    return lq / rho


def w_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    mu = validate_positive_number("μ", inputs.get("mu"))
    if lambda_ >= mu:
        raise ValueError("λ debe ser menor que μ para W en PICS.")
    return 1.0 / (mu - lambda_)


def wq_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    mu = validate_positive_number("μ", inputs.get("mu"))
    if lambda_ >= mu:
        raise ValueError("λ debe ser menor que μ para Wq en PICS.")
    return lambda_ / (mu * (mu - lambda_))


def wn_formula(inputs: dict[str, Any]) -> float:
    wq = validate_positive_number("Wq", inputs.get("Wq"))
    rho = validate_positive_number("ρ", inputs.get("rho"))
    if rho == 0:
        raise ValueError("ρ no puede ser cero para Wn en PICS.")
    return wq / rho


def ct_te_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    wq = validate_positive_number("Wq", inputs.get("Wq"))
    cte = validate_positive_number("CTE", inputs.get("CTE"))
    return lambda_ * 8.0 * wq * cte


def ct_ts_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    w = validate_positive_number("W", inputs.get("W"))
    cts = validate_positive_number("CTS", inputs.get("CTS"))
    return lambda_ * 8.0 * w * cts


def ct_tse_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    mu = validate_positive_number("μ", inputs.get("mu"))
    ctse = validate_positive_number("CTSE", inputs.get("CTSE"))
    return lambda_ * 8.0 * (1.0 / mu) * ctse


def ct_s_formula(inputs: dict[str, Any]) -> float:
    cs = validate_positive_number("CS", inputs.get("CS"))
    return cs


def ct_formula(inputs: dict[str, Any]) -> float:
    ct_te = validate_positive_number("CT_TE", inputs.get("CT_TE"))
    ct_ts = validate_positive_number("CT_TS", inputs.get("CT_TS"))
    ct_tse = validate_positive_number("CT_TSE", inputs.get("CT_TSE"))
    ct_s = validate_positive_number("CT_S", inputs.get("CT_S"))
    return ct_te + ct_ts + ct_tse + ct_s


def tt_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    wq = validate_positive_number("Wq", inputs.get("Wq"))
    return lambda_ * 8.0 * 0.30 * wq


PICS_FORMULAS: list[FormulaDefinition] = [
    FormulaDefinition(
        id="pics_rho",
        name="Factor de ocupación",
        category=FormulaCategory.PICS,
        description="Relación entre la tasa de llegada y la tasa de servicio.",
        result_variable="rho",
        input_variables=["lambda_", "mu"],
        formula_type=FormulaType.DIRECT,
        priority=20,
        premium_mode=False,
        manual_calculation=rho_formula,
        symbolic_expression="λ / μ",
        constraints={"lambda_positive": True, "mu_positive": True},
    ),
    FormulaDefinition(
        id="pics_p0",
        name="Probabilidad de estado cero",
        category=FormulaCategory.PICS,
        description="Probabilidad de que el sistema esté vacío en el modelo PICS.",
        result_variable="P0",
        input_variables=["lambda_", "mu"],
        formula_type=FormulaType.DIRECT,
        priority=20,
        premium_mode=False,
        manual_calculation=p0_formula,
        symbolic_expression="1 - ρ",
        constraints={"lambda_positive": True, "mu_positive": True},
    ),
    FormulaDefinition(
        id="pics_pn",
        name="Probabilidad de n clientes",
        category=FormulaCategory.PICS,
        description="Probabilidad de encontrar exactamente n clientes en el sistema.",
        result_variable="Pn",
        input_variables=["lambda_", "mu", "n"],
        formula_type=FormulaType.DIRECT,
        priority=15,
        premium_mode=False,
        manual_calculation=pn_formula,
        symbolic_expression="P0 * ρ^n",
        constraints={"lambda_positive": True, "mu_positive": True, "n_positive_integer": True},
    ),
    FormulaDefinition(
        id="pics_l",
        name="Número promedio de clientes en el sistema",
        category=FormulaCategory.PICS,
        description="Promedio de clientes en el sistema. Equivalente a λ·W cuando W = 1/(μ-λ).",
        result_variable="L",
        input_variables=["lambda_", "mu"],
        formula_type=FormulaType.DIRECT,
        priority=18,
        premium_mode=False,
        manual_calculation=l_formula,
        symbolic_expression="λ / (μ - λ)",
        constraints={"lambda_positive": True, "mu_positive": True},
    ),
    FormulaDefinition(
        id="pics_lq",
        name="Número promedio de clientes en cola",
        category=FormulaCategory.PICS,
        description="Promedio de clientes en cola. Equivalente a λ·Wq.",
        result_variable="Lq",
        input_variables=["lambda_", "mu"],
        formula_type=FormulaType.DIRECT,
        priority=18,
        premium_mode=False,
        manual_calculation=lq_formula,
        symbolic_expression="λ^2 / (μ(μ - λ))",
        constraints={"lambda_positive": True, "mu_positive": True},
    ),
    FormulaDefinition(
        id="pics_ln",
        name="Clientes en el sistema según condición Ln",
        category=FormulaCategory.PICS,
        description="Resultado equivalente a λ/(μ-λ) expresado como Lq/ρ.",
        result_variable="Ln",
        input_variables=["lambda_", "mu"],
        formula_type=FormulaType.COMPOSITE,
        priority=10,
        premium_mode=False,
        manual_calculation=ln_formula,
        symbolic_expression="Lq / ρ",
        constraints={"lambda_positive": True, "mu_positive": True},
    ),
    FormulaDefinition(
        id="pics_w",
        name="Tiempo promedio en el sistema",
        category=FormulaCategory.PICS,
        description="Tiempo promedio que un cliente permanece en el sistema.",
        result_variable="W",
        input_variables=["lambda_", "mu"],
        formula_type=FormulaType.DIRECT,
        priority=18,
        premium_mode=False,
        manual_calculation=w_formula,
        symbolic_expression="1 / (μ - λ)",
        constraints={"lambda_positive": True, "mu_positive": True},
    ),
    FormulaDefinition(
        id="pics_wq",
        name="Tiempo promedio de espera en cola",
        category=FormulaCategory.PICS,
        description="Tiempo promedio de espera en cola para cada cliente.",
        result_variable="Wq",
        input_variables=["lambda_", "mu"],
        formula_type=FormulaType.DIRECT,
        priority=18,
        premium_mode=False,
        manual_calculation=wq_formula,
        symbolic_expression="λ / (μ (μ - λ))",
        constraints={"lambda_positive": True, "mu_positive": True},
    ),
    FormulaDefinition(
        id="pics_wn",
        name="Tiempo condicional Wn",
        category=FormulaCategory.PICS,
        description="Tiempo promedio en función de Wq y el factor de ocupación.",
        result_variable="Wn",
        input_variables=["Wq", "rho"],
        formula_type=FormulaType.COMPOSITE,
        priority=12,
        premium_mode=False,
        manual_calculation=wn_formula,
        symbolic_expression="Wq / ρ",
        constraints={"Wq_non_negative": True, "rho_positive": True},
    ),
    FormulaDefinition(
        id="pics_ct_te",
        name="Costo total de tiempo de espera",
        category=FormulaCategory.PICS,
        description="Costo total asociado al tiempo de espera.",
        result_variable="CT_TE",
        input_variables=["lambda_", "Wq", "CTE"],
        formula_type=FormulaType.DIRECT,
        priority=8,
        premium_mode=False,
        manual_calculation=ct_te_formula,
        symbolic_expression="λ · 8 · Wq · CTE",
        constraints={"lambda_positive": True, "Wq_non_negative": True, "CTE_non_negative": True},
    ),
    FormulaDefinition(
        id="pics_ct_ts",
        name="Costo total por tiempo de servicio",
        category=FormulaCategory.PICS,
        description="Costo total asociado al tiempo de servicio.",
        result_variable="CT_TS",
        input_variables=["lambda_", "W", "CTS"],
        formula_type=FormulaType.DIRECT,
        priority=8,
        premium_mode=False,
        manual_calculation=ct_ts_formula,
        symbolic_expression="λ · 8 · W · CTS",
        constraints={"lambda_positive": True, "W_non_negative": True, "CTS_non_negative": True},
    ),
    FormulaDefinition(
        id="pics_ct_tse",
        name="Costo total de tiempo de servicio y espera",
        category=FormulaCategory.PICS,
        description="Costo total asociado al tiempo combinado de servicio y espera.",
        result_variable="CT_TSE",
        input_variables=["lambda_", "mu", "CTSE"],
        formula_type=FormulaType.DIRECT,
        priority=8,
        premium_mode=False,
        manual_calculation=ct_tse_formula,
        symbolic_expression="λ · 8 · (1/μ) · CTSE",
        constraints={"lambda_positive": True, "mu_positive": True, "CTSE_non_negative": True},
    ),
    FormulaDefinition(
        id="pics_ct_s",
        name="Costo total de servicio",
        category=FormulaCategory.PICS,
        description="Costo total directamente equivalente al costo unitario de servicio.",
        result_variable="CT_S",
        input_variables=["CS"],
        formula_type=FormulaType.DIRECT,
        priority=5,
        premium_mode=False,
        manual_calculation=ct_s_formula,
        symbolic_expression="CS",
        constraints={"CS_non_negative": True},
    ),
    FormulaDefinition(
        id="pics_ct",
        name="Costo total",
        category=FormulaCategory.PICS,
        description="Suma de todos los costos totales parciales del sistema.",
        result_variable="CT",
        input_variables=["CT_TE", "CT_TS", "CT_TSE", "CT_S"],
        formula_type=FormulaType.COMPOSITE,
        priority=5,
        premium_mode=False,
        manual_calculation=ct_formula,
        symbolic_expression="CT_TE + CT_TS + CT_TSE + CT_S",
        constraints={
            "CT_TE_non_negative": True,
            "CT_TS_non_negative": True,
            "CT_TSE_non_negative": True,
            "CT_S_non_negative": True,
        },
    ),
    FormulaDefinition(
        id="pics_tt",
        name="Tiempo total de operación",
        category=FormulaCategory.PICS,
        description="Tiempo total normalizado al factor de 0.30 horas en función de Wq.",
        result_variable="TT",
        input_variables=["lambda_", "Wq"],
        formula_type=FormulaType.DIRECT,
        priority=5,
        premium_mode=False,
        manual_calculation=tt_formula,
        symbolic_expression="λ · 8 · 0.30 · Wq",
        constraints={"lambda_positive": True, "Wq_non_negative": True},
    ),
]

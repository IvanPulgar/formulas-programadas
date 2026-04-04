from __future__ import annotations

from math import comb
from typing import Any

from domain.entities import FormulaCategory, FormulaDefinition, FormulaType
from domain.formulas.formula_utils import (
    effective_arrival_rate,
    finite_source_ratio,
    validate_non_negative_integer,
    validate_population_size,
    validate_positive_number,
)


def state_weight(m: int, a: float, n: int) -> float:
    return comb(m, n) * a**n


def p0_formula(inputs: dict[str, Any]) -> float:
    a = finite_source_ratio(inputs)
    m = validate_population_size("M", inputs.get("M"))
    normalization = sum(state_weight(m, a, n) for n in range(0, m + 1))
    return 1.0 / normalization


def pn_formula(inputs: dict[str, Any]) -> float:
    p0 = p0_formula(inputs)
    a = finite_source_ratio(inputs)
    m = validate_population_size("M", inputs.get("M"))
    n = validate_non_negative_integer("n", inputs.get("n"))
    if n > m:
        raise ValueError("n no puede ser mayor que M en PFCS.")
    return p0 * state_weight(m, a, n)


def l_formula(inputs: dict[str, Any]) -> float:
    a = finite_source_ratio(inputs)
    m = validate_population_size("M", inputs.get("M"))
    p0 = p0_formula(inputs)
    return sum(n * p0 * state_weight(m, a, n) for n in range(0, m + 1))


def lq_formula(inputs: dict[str, Any]) -> float:
    a = finite_source_ratio(inputs)
    m = validate_population_size("M", inputs.get("M"))
    p0 = p0_formula(inputs)
    return sum((n - 1) * p0 * state_weight(m, a, n) for n in range(2, m + 1))


def rho_formula(inputs: dict[str, Any]) -> float:
    p0 = p0_formula(inputs)
    return 1.0 - p0


def wq_formula(inputs: dict[str, Any]) -> float:
    lq = lq_formula(inputs)
    l = l_formula(inputs)
    return lq / effective_arrival_rate(inputs, l)


def w_formula(inputs: dict[str, Any]) -> float:
    l = l_formula(inputs)
    return l / effective_arrival_rate(inputs, l)


PFCS_FORMULAS: list[FormulaDefinition] = [
    FormulaDefinition(
        id="pfcs_p0",
        name="Probabilidad de estado cero",
        category=FormulaCategory.PFCS,
        description="Probabilidad de que el sistema esté vacío con población fuente finita y un solo servidor.",
        result_variable="P0",
        input_variables=["lambda_", "mu", "M"],
        formula_type=FormulaType.SYMBOLIC,
        priority=25,
        premium_mode=False,
        manual_calculation=p0_formula,
        symbolic_expression="[Σ_{n=0}^{M} C(M,n) a^n]^{-1}",
        constraints={"lambda_positive": True, "mu_positive": True, "M_positive_integer": True},
    ),
    FormulaDefinition(
        id="pfcs_pn",
        name="Probabilidad de n clientes",
        category=FormulaCategory.PFCS,
        description="Probabilidad de encontrar exactamente n clientes en el sistema con población finita y un solo servidor.",
        result_variable="Pn",
        input_variables=["lambda_", "mu", "M", "n"],
        formula_type=FormulaType.DIRECT,
        priority=20,
        premium_mode=False,
        manual_calculation=pn_formula,
        symbolic_expression="P0 · C(M,n) a^n",
        constraints={
            "lambda_positive": True,
            "mu_positive": True,
            "M_positive_integer": True,
            "n_non_negative_integer": True,
        },
    ),
    FormulaDefinition(
        id="pfcs_rho",
        name="Factor de ocupación finita",
        category=FormulaCategory.PFCS,
        description="Utilización del servidor para un sistema de población finita con un servidor.",
        result_variable="rho",
        input_variables=["lambda_", "mu", "M"],
        formula_type=FormulaType.DIRECT,
        priority=18,
        premium_mode=False,
        manual_calculation=rho_formula,
        symbolic_expression="1 - P0",
        constraints={"lambda_positive": True, "mu_positive": True, "M_positive_integer": True},
    ),
    FormulaDefinition(
        id="pfcs_l",
        name="Clientes promedio en el sistema",
        category=FormulaCategory.PFCS,
        description="Promedio de clientes en el sistema para el modelo PFCS.",
        result_variable="L",
        input_variables=["lambda_", "mu", "M"],
        formula_type=FormulaType.DIRECT,
        priority=16,
        premium_mode=False,
        manual_calculation=l_formula,
        symbolic_expression="Σ_{n=0}^{M} n · Pn",
        constraints={"lambda_positive": True, "mu_positive": True, "M_positive_integer": True},
    ),
    FormulaDefinition(
        id="pfcs_lq",
        name="Clientes promedio en cola",
        category=FormulaCategory.PFCS,
        description="Promedio de clientes en cola para el modelo PFCS.",
        result_variable="Lq",
        input_variables=["lambda_", "mu", "M"],
        formula_type=FormulaType.SYMBOLIC,
        priority=16,
        premium_mode=False,
        manual_calculation=lq_formula,
        symbolic_expression="Σ_{n=2}^{M} (n-1) · Pn",
        constraints={"lambda_positive": True, "mu_positive": True, "M_positive_integer": True},
    ),
    FormulaDefinition(
        id="pfcs_wq",
        name="Tiempo promedio de espera en cola",
        category=FormulaCategory.PFCS,
        description="Tiempo promedio de espera en cola considerando la tasa de llegada efectiva de una población finita.",
        result_variable="Wq",
        input_variables=["lambda_", "mu", "M"],
        formula_type=FormulaType.SYMBOLIC,
        priority=14,
        premium_mode=False,
        manual_calculation=wq_formula,
        symbolic_expression="Lq / (λ · (M - L))",
        constraints={"lambda_positive": True, "mu_positive": True, "M_positive_integer": True},
    ),
    FormulaDefinition(
        id="pfcs_w",
        name="Tiempo promedio en el sistema",
        category=FormulaCategory.PFCS,
        description="Tiempo promedio en el sistema para un modelo PFCS basado en la tasa de llegada efectiva.",
        result_variable="W",
        input_variables=["lambda_", "mu", "M"],
        formula_type=FormulaType.COMPOSITE,
        priority=12,
        premium_mode=False,
        manual_calculation=w_formula,
        symbolic_expression="L / (λ · (M - L))",
        constraints={"lambda_positive": True, "mu_positive": True, "M_positive_integer": True},
    ),
]

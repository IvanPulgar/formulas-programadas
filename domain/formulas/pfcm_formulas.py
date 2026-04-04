from __future__ import annotations

from math import comb, factorial
from typing import Any

from domain.entities import FormulaCategory, FormulaDefinition, FormulaType
from domain.formulas.formula_utils import (
    effective_arrival_rate,
    finite_source_ratio,
    validate_non_negative_integer,
    validate_population_size,
    validate_positive_integer,
    validate_positive_number,
)


def state_weight(m: int, a: float, k: int, n: int) -> float:
    if n <= k:
        return comb(m, n) * a**n / factorial(n)
    return comb(m, n) * a**n / (factorial(k) * k ** (n - k))


def p0_formula(inputs: dict[str, Any]) -> float:
    a = finite_source_ratio(inputs)
    m = validate_population_size("M", inputs.get("M"))
    k = validate_positive_integer("k", inputs.get("k"))
    normalization = sum(state_weight(m, a, k, n) for n in range(0, m + 1))
    return 1.0 / normalization


def pn_formula(inputs: dict[str, Any]) -> float:
    p0 = p0_formula(inputs)
    a = finite_source_ratio(inputs)
    m = validate_population_size("M", inputs.get("M"))
    k = validate_positive_integer("k", inputs.get("k"))
    n = validate_non_negative_integer("n", inputs.get("n"))
    if n > m:
        raise ValueError("n no puede ser mayor que M en PFCM.")
    return p0 * state_weight(m, a, k, n)


def pk_formula(inputs: dict[str, Any]) -> float:
    m = validate_population_size("M", inputs.get("M"))
    k = validate_positive_integer("k", inputs.get("k"))
    if k > m:
        return 0.0
    return pn_formula({**inputs, "n": k})


def l_formula(inputs: dict[str, Any]) -> float:
    a = finite_source_ratio(inputs)
    m = validate_population_size("M", inputs.get("M"))
    k = validate_positive_integer("k", inputs.get("k"))
    p0 = p0_formula(inputs)
    return sum(n * p0 * state_weight(m, a, k, n) for n in range(0, m + 1))


def lq_formula(inputs: dict[str, Any]) -> float:
    a = finite_source_ratio(inputs)
    m = validate_population_size("M", inputs.get("M"))
    k = validate_positive_integer("k", inputs.get("k"))
    p0 = p0_formula(inputs)
    return sum((n - k) * p0 * state_weight(m, a, k, n) for n in range(k + 1, m + 1))


def rho_formula(inputs: dict[str, Any]) -> float:
    l = l_formula(inputs)
    lq = lq_formula(inputs)
    k = validate_positive_integer("k", inputs.get("k"))
    return (l - lq) / float(k)


def wq_formula(inputs: dict[str, Any]) -> float:
    lq = lq_formula(inputs)
    l = l_formula(inputs)
    return lq / effective_arrival_rate(inputs, l)


def w_formula(inputs: dict[str, Any]) -> float:
    l = l_formula(inputs)
    return l / effective_arrival_rate(inputs, l)


PFCM_FORMULAS: list[FormulaDefinition] = [
    FormulaDefinition(
        id="pfcm_p0",
        name="Probabilidad de estado cero",
        category=FormulaCategory.PFCM,
        description="Probabilidad de que el sistema esté vacío en el modelo de población finita con múltiples servidores.",
        result_variable="P0",
        input_variables=["lambda_", "mu", "k", "M"],
        formula_type=FormulaType.SYMBOLIC,
        priority=30,
        premium_mode=False,
        manual_calculation=p0_formula,
        symbolic_expression="[Σ_{n=0}^{k} C(M,n) a^n / n! + Σ_{n=k+1}^{M} C(M,n) a^n / (k! · k^{n-k})]^{-1}",
        constraints={
            "lambda_positive": True,
            "mu_positive": True,
            "k_positive_integer": True,
            "M_positive_integer": True,
        },
    ),
    FormulaDefinition(
        id="pfcm_pk",
        name="Probabilidad de k servidores ocupados",
        category=FormulaCategory.PFCM,
        description="Probabilidad de que todos los servidores estén ocupados en el modelo PFCM.",
        result_variable="Pk",
        input_variables=["lambda_", "mu", "k", "M"],
        formula_type=FormulaType.DIRECT,
        priority=25,
        premium_mode=False,
        manual_calculation=pk_formula,
        symbolic_expression="P0 · C(M,k) a^k / k!",
        constraints={
            "lambda_positive": True,
            "mu_positive": True,
            "k_positive_integer": True,
            "M_positive_integer": True,
        },
    ),
    FormulaDefinition(
        id="pfcm_pn",
        name="Probabilidad de n clientes",
        category=FormulaCategory.PFCM,
        description="Probabilidad de encontrar exactamente n clientes en el sistema con población finita y múltiples servidores.",
        result_variable="Pn",
        input_variables=["lambda_", "mu", "k", "M", "n"],
        formula_type=FormulaType.DIRECT,
        priority=20,
        premium_mode=False,
        manual_calculation=pn_formula,
        symbolic_expression="P0 · [C(M,n) a^n / n! si n ≤ k, else C(M,n) a^n / (k!·k^{n-k})]",
        constraints={
            "lambda_positive": True,
            "mu_positive": True,
            "k_positive_integer": True,
            "M_positive_integer": True,
            "n_non_negative_integer": True,
        },
    ),
    FormulaDefinition(
        id="pfcm_lq",
        name="Clientes promedio en cola",
        category=FormulaCategory.PFCM,
        description="Número promedio de clientes en cola en el modelo PFCM.",
        result_variable="Lq",
        input_variables=["lambda_", "mu", "k", "M"],
        formula_type=FormulaType.SYMBOLIC,
        priority=18,
        premium_mode=False,
        manual_calculation=lq_formula,
        symbolic_expression="Σ_{n=k+1}^{M} (n-k) · Pn",
        constraints={
            "lambda_positive": True,
            "mu_positive": True,
            "k_positive_integer": True,
            "M_positive_integer": True,
        },
    ),
    FormulaDefinition(
        id="pfcm_l",
        name="Clientes promedio en el sistema",
        category=FormulaCategory.PFCM,
        description="Número promedio total de clientes en el sistema bajo PFCM.",
        result_variable="L",
        input_variables=["lambda_", "mu", "k", "M"],
        formula_type=FormulaType.DIRECT,
        priority=16,
        premium_mode=False,
        manual_calculation=l_formula,
        symbolic_expression="Σ_{n=0}^{M} n · Pn",
        constraints={
            "lambda_positive": True,
            "mu_positive": True,
            "k_positive_integer": True,
            "M_positive_integer": True,
        },
    ),
    FormulaDefinition(
        id="pfcm_rho",
        name="Factor de ocupación finita",
        category=FormulaCategory.PFCM,
        description="Utilización por servidor en el modelo PFCM.",
        result_variable="rho",
        input_variables=["lambda_", "mu", "k", "M"],
        formula_type=FormulaType.DIRECT,
        priority=14,
        premium_mode=False,
        manual_calculation=rho_formula,
        symbolic_expression="(L - Lq) / k",
        constraints={
            "lambda_positive": True,
            "mu_positive": True,
            "k_positive_integer": True,
            "M_positive_integer": True,
        },
    ),
    FormulaDefinition(
        id="pfcm_wq",
        name="Tiempo promedio de espera en cola",
        category=FormulaCategory.PFCM,
        description="Tiempo promedio de espera en cola para PFCM con población finita.",
        result_variable="Wq",
        input_variables=["lambda_", "mu", "k", "M"],
        formula_type=FormulaType.SYMBOLIC,
        priority=12,
        premium_mode=False,
        manual_calculation=wq_formula,
        symbolic_expression="Lq / (λ · (M - L))",
        constraints={
            "lambda_positive": True,
            "mu_positive": True,
            "k_positive_integer": True,
            "M_positive_integer": True,
        },
    ),
    FormulaDefinition(
        id="pfcm_w",
        name="Tiempo promedio en el sistema",
        category=FormulaCategory.PFCM,
        description="Tiempo promedio total en el sistema para PFCM.",
        result_variable="W",
        input_variables=["lambda_", "mu", "k", "M"],
        formula_type=FormulaType.COMPOSITE,
        priority=10,
        premium_mode=False,
        manual_calculation=w_formula,
        symbolic_expression="L / (λ · (M - L))",
        constraints={
            "lambda_positive": True,
            "mu_positive": True,
            "k_positive_integer": True,
            "M_positive_integer": True,
        },
    ),
]

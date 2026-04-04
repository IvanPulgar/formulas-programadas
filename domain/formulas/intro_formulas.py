from __future__ import annotations

from typing import Any

from domain.entities import FormulaCategory, FormulaDefinition, FormulaType
from domain.rules import positive


def validate_positive_number(name: str, value: Any) -> float:
    if not positive(value):
        raise ValueError(f"{name} debe ser un número positivo.")
    return float(value)


def time_between_arrivals(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    return 1.0 / lambda_


def time_between_arrivals_despeje(inputs: dict[str, Any], result_value: Any, missing_var: str) -> float:
    """Despeje for time_between_arrivals: if lambda_inv is known, solve for lambda_."""
    if missing_var == "lambda_":
        result = validate_positive_number("lambda_inv", result_value)
        return 1.0 / result
    raise ValueError(f"Cannot solve for variable {missing_var}")


def time_between_services(inputs: dict[str, Any]) -> float:
    mu = validate_positive_number("μ", inputs.get("mu"))
    return 1.0 / mu


def time_between_services_despeje(inputs: dict[str, Any], result_value: Any, missing_var: str) -> float:
    """Despeje for time_between_services: if mu_inv is known, solve for mu."""
    if missing_var == "mu":
        result = validate_positive_number("mu_inv", result_value)
        return 1.0 / result
    raise ValueError(f"Cannot solve for variable {missing_var}")


def system_response_time(inputs: dict[str, Any]) -> float:
    wq = validate_positive_number("Wq", inputs.get("Wq"))
    mu = validate_positive_number("μ", inputs.get("mu"))
    return wq + 1.0 / mu


def system_response_time_despeje(inputs: dict[str, Any], result_value: Any, missing_var: str) -> float:
    """Despeje for system_response_time: W = Wq + 1/μ."""
    result = validate_positive_number("W", result_value)
    if missing_var == "Wq":
        mu = validate_positive_number("μ", inputs.get("mu"))
        return result - 1.0 / mu
    elif missing_var == "mu":
        wq = validate_positive_number("Wq", inputs.get("Wq"))
        return 1.0 / (result - wq)
    raise ValueError(f"Cannot solve for variable {missing_var}")


INTRO_FORMULAS: list[FormulaDefinition] = [
    FormulaDefinition(
        id="intro_time_between_arrivals",
        name="Tiempo medio entre llegadas",
        category=FormulaCategory.GENERAL,
        description="Tiempo promedio entre llegadas de clientes al sistema.",
        result_variable="lambda_inv",
        input_variables=["lambda_"],
        formula_type=FormulaType.DIRECT,
        priority=10,
        premium_mode=False,
        manual_calculation=time_between_arrivals,
        manual_despeje=time_between_arrivals_despeje,
        symbolic_expression="1 / λ",
        constraints={"lambda_positive": True},
    ),
    FormulaDefinition(
        id="intro_time_between_services",
        name="Tiempo medio de servicio",
        category=FormulaCategory.GENERAL,
        description="Tiempo promedio de servicio para cada cliente.",
        result_variable="mu_inv",
        input_variables=["mu"],
        formula_type=FormulaType.DIRECT,
        priority=10,
        premium_mode=False,
        manual_calculation=time_between_services,
        manual_despeje=time_between_services_despeje,
        symbolic_expression="1 / μ",
        constraints={"mu_positive": True},
    ),
    FormulaDefinition(
        id="intro_system_response_time",
        name="Tiempo total en el sistema",
        category=FormulaCategory.GENERAL,
        description="Tiempo promedio total en el sistema, sumando espera y servicio.",
        result_variable="W",
        input_variables=["Wq", "mu"],
        formula_type=FormulaType.DIRECT,
        priority=5,
        premium_mode=False,
        manual_calculation=system_response_time,
        manual_despeje=system_response_time_despeje,
        symbolic_expression="Wq + 1/μ",
        constraints={"Wq_non_negative": True, "mu_positive": True},
    ),
]

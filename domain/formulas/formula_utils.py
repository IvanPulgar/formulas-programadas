from __future__ import annotations

from math import comb
from typing import Any

from domain.rules import positive, positive_integer


def validate_positive_number(name: str, value: Any) -> float:
    if not positive(value):
        raise ValueError(f"{name} debe ser un número positivo.")
    return float(value)


def validate_positive_integer(name: str, value: Any) -> int:
    if not positive_integer(value):
        raise ValueError(f"{name} debe ser un entero positivo.")
    return int(value)


def validate_non_negative_integer(name: str, value: Any) -> int:
    if not positive_integer(value) and not (isinstance(value, int) and value == 0):
        raise ValueError(f"{name} debe ser un entero no negativo.")
    return int(value)


def validate_population_size(name: str, value: Any) -> int:
    size = validate_positive_integer(name, value)
    if size <= 0:
        raise ValueError(f"{name} debe ser mayor que cero.")
    return size


def validate_server_count(name: str, value: Any) -> int:
    return validate_positive_integer(name, value)


def finite_source_ratio(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    mu = validate_positive_number("μ", inputs.get("mu"))
    return lambda_ / mu


def effective_arrival_rate(inputs: dict[str, Any], system_average: float) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    population = validate_population_size("M", inputs.get("M"))
    available_sources = float(population) - float(system_average)
    if available_sources <= 0.0:
        raise ValueError("No hay fuentes disponibles para generar llegadas.")
    return lambda_ * available_sources


def choose(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    return comb(n, k)

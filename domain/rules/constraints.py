from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from domain.entities.catalog import CATEGORY_CATALOG
from domain.entities.enums import FormulaCategory


ConstraintFunction = Callable[[Any], bool]
CategoryConstraintFunction = Callable[[dict[str, Any]], bool]


@dataclass
class ValueConstraint:
    id: str
    description: str
    validator: ConstraintFunction


@dataclass
class CategoryConstraint:
    id: str
    description: str
    validator: CategoryConstraintFunction


def positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and value > 0


def non_negative(value: Any) -> bool:
    return isinstance(value, (int, float)) and value >= 0


def positive_integer(value: Any) -> bool:
    return isinstance(value, int) and value > 0


def probability(value: Any) -> bool:
    return isinstance(value, (int, float)) and 0 <= value <= 1


CATEGORY_CONSTRAINTS: dict[FormulaCategory, list[CategoryConstraint]] = {
    FormulaCategory.PICS: [
        CategoryConstraint(
            id="pics_lambda_positive",
            description="λ debe ser positivo en PICS.",
            validator=lambda inputs: positive(inputs.get("lambda_")),
        ),
        CategoryConstraint(
            id="pics_mu_positive",
            description="μ debe ser positivo en PICS.",
            validator=lambda inputs: positive(inputs.get("mu")),
        ),
        CategoryConstraint(
            id="pics_lambda_less_than_mu",
            description="λ debe ser menor que μ en PICS.",
            validator=lambda inputs: (
                isinstance(inputs.get("lambda_"), (int, float))
                and isinstance(inputs.get("mu"), (int, float))
                and inputs["lambda_"] < inputs["mu"]
            ),
        ),
    ],
    FormulaCategory.PICM: [
        CategoryConstraint(
            id="picm_lambda_positive",
            description="λ debe ser positivo en PICM.",
            validator=lambda inputs: positive(inputs.get("lambda_")),
        ),
        CategoryConstraint(
            id="picm_mu_positive",
            description="μ debe ser positivo en PICM.",
            validator=lambda inputs: positive(inputs.get("mu")),
        ),
        CategoryConstraint(
            id="picm_k_positive_integer",
            description="k debe ser un entero positivo en PICM.",
            validator=lambda inputs: positive_integer(inputs.get("k")),
        ),
        CategoryConstraint(
            id="picm_lambda_less_than_k_mu",
            description="λ debe ser menor que k·μ en PICM.",
            validator=lambda inputs: (
                isinstance(inputs.get("lambda_"), (int, float))
                and isinstance(inputs.get("mu"), (int, float))
                and isinstance(inputs.get("k"), int)
                and inputs["lambda_"] < inputs["k"] * inputs["mu"]
            ),
        ),
    ],
    FormulaCategory.PFCS: [
        CategoryConstraint(
            id="pfcs_lambda_positive",
            description="λ debe ser positivo en PFCS.",
            validator=lambda inputs: positive(inputs.get("lambda_")),
        ),
        CategoryConstraint(
            id="pfcs_mu_positive",
            description="μ debe ser positivo en PFCS.",
            validator=lambda inputs: positive(inputs.get("mu")),
        ),
        CategoryConstraint(
            id="pfcs_m_non_negative",
            description="M debe ser un entero positivo en PFCS.",
            validator=lambda inputs: positive_integer(inputs.get("M")),
        ),
    ],
    FormulaCategory.PFCM: [
        CategoryConstraint(
            id="pfcm_lambda_positive",
            description="λ debe ser positivo en PFCM.",
            validator=lambda inputs: positive(inputs.get("lambda_")),
        ),
        CategoryConstraint(
            id="pfcm_mu_positive",
            description="μ debe ser positivo en PFCM.",
            validator=lambda inputs: positive(inputs.get("mu")),
        ),
        CategoryConstraint(
            id="pfcm_k_positive_integer",
            description="k debe ser un entero positivo en PFCM.",
            validator=lambda inputs: positive_integer(inputs.get("k")),
        ),
        CategoryConstraint(
            id="pfcm_lambda_less_than_k_mu",
            description="λ debe ser menor que k·μ en PFCM.",
            validator=lambda inputs: (
                isinstance(inputs.get("lambda_"), (int, float))
                and isinstance(inputs.get("mu"), (int, float))
                and isinstance(inputs.get("k"), int)
                and inputs["lambda_"] < inputs["k"] * inputs["mu"]
            ),
        ),
    ],
}


def list_category_constraints(category: FormulaCategory) -> list[CategoryConstraint]:
    return CATEGORY_CONSTRAINTS.get(category, [])

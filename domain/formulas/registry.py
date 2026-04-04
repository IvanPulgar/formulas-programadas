from typing import Iterable, Optional

from domain.entities import FormulaDefinition

from .intro_formulas import INTRO_FORMULAS
from .pics_formulas import PICS_FORMULAS
from .picm_formulas import PICM_FORMULAS
from .pfcs_formulas import PFCS_FORMULAS
from .pfcm_formulas import PFCM_FORMULAS

FORMULAS = [*INTRO_FORMULAS, *PICS_FORMULAS, *PICM_FORMULAS, *PFCS_FORMULAS, *PFCM_FORMULAS]


def get_formula_by_id(formula_id: str) -> Optional[FormulaDefinition]:
    return next((formula for formula in FORMULAS if formula.id == formula_id), None)


def list_formulas(category: Optional[str] = None) -> list[FormulaDefinition]:
    if category is None:
        return list(FORMULAS)
    return [formula for formula in FORMULAS if formula.category == category]


def iter_formulas(category: Optional[str] = None) -> Iterable[FormulaDefinition]:
    yield from list_formulas(category)

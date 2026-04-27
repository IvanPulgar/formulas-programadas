from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.entities.catalog import VARIABLE_CATALOG
from domain.formulas.registry import FORMULAS


@dataclass
class KnowledgeValidationResult:
    """Validation report for offline knowledge consistency."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class OfflineKnowledgeValidator:
    """Validate knowledge files against the current domain catalogs and formulas."""

    def validate(self, knowledge: dict[str, Any]) -> KnowledgeValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        formula_ids = {formula.id for formula in FORMULAS}
        variable_ids = set(VARIABLE_CATALOG.keys())
        model_ids = {model.get("id") for model in knowledge.get("models", [])}

        for objective in knowledge.get("objectives", []):
            objective_id = objective.get("id", "<missing>")
            for target in objective.get("targets", []):
                formula_id = target.get("formula_id")
                model_id = target.get("model")

                if formula_id not in formula_ids:
                    errors.append(
                        f"Objective '{objective_id}' references unknown formula '{formula_id}'."
                    )

                if model_id not in model_ids:
                    errors.append(
                        f"Objective '{objective_id}' references unknown model '{model_id}'."
                    )

        for dep in knowledge.get("dependencies", []):
            dep_formula_id = dep.get("formula_id")
            if dep_formula_id not in formula_ids:
                errors.append(
                    f"Dependency entry references unknown formula '{dep_formula_id}'."
                )

            for required_var in dep.get("requires", []):
                if required_var not in variable_ids:
                    errors.append(
                        f"Dependency '{dep_formula_id}' requires unknown variable '{required_var}'."
                    )

            for producer_formula in dep.get("depends_on_formulas", []):
                if producer_formula not in formula_ids:
                    errors.append(
                        f"Dependency '{dep_formula_id}' references unknown producer formula '{producer_formula}'."
                    )

        for model in knowledge.get("models", []):
            model_id = model.get("id", "<missing>")
            for required_var in model.get("required_variables", []):
                if required_var not in variable_ids:
                    errors.append(
                        f"Model '{model_id}' requires unknown variable '{required_var}'."
                    )

        for var in knowledge.get("variables", []):
            var_id = var.get("id")
            if var_id not in variable_ids:
                warnings.append(
                    f"Detectable variable '{var_id}' is not in VARIABLE_CATALOG."
                )

        return KnowledgeValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

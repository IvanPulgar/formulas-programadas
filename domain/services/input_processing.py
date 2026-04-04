from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from domain.entities import InputValue, VariableDefinition
from domain.entities.catalog import CATEGORY_CATALOG, VARIABLE_CATALOG, get_variable_definition
from domain.entities.enums import VariableType
from domain.services.contracts import InputNormalizer, VariableResolver


class VariableOrigin(str, Enum):
    GLOBAL = "global"
    CATEGORY = "category"
    RESULT = "result"
    UNKNOWN = "unknown"


@dataclass
class ConflictRecord:
    variable_id: str
    message: str
    category_id: str | None = None
    existing_source: str | None = None
    new_source: str | None = None
    existing_value: Any = None
    new_value: Any = None
    sources: list[str] = field(default_factory=list)


@dataclass
class VariableResolutionResult:
    global_inputs: dict[str, InputValue] = field(default_factory=dict)
    category_inputs: dict[str, dict[str, InputValue]] = field(default_factory=dict)
    result_inputs: dict[str, InputValue] = field(default_factory=dict)
    consolidated_inputs: dict[str, InputValue] = field(default_factory=dict)
    conflicts: list[ConflictRecord] = field(default_factory=list)
    unknown_inputs: list[InputValue] = field(default_factory=list)

    def all_inputs(self) -> Iterable[InputValue]:
        yield from self.global_inputs.values()
        for category_map in self.category_inputs.values():
            yield from category_map.values()
        yield from self.result_inputs.values()
        yield from self.unknown_inputs


class DefaultInputNormalizer(InputNormalizer):
    alias_map: dict[str, str] = {
        "lambda": "lambda_",
        "λ": "lambda_",
        "mu": "mu",
        "μ": "mu",
        "rho": "rho",
        "ρ": "rho",
        "wq": "Wq",
        "WQ": "Wq",
        "lq": "Lq",
        "LQ": "Lq",
        "w": "W",
        "l": "L",
        "n": "n",
        "m": "M",
        "k": "k",
        "p0": "P0",
        "pne": "PNE",
    }
    reserved_sections = {"global", "globals", "result", "results", "expected", "expected_results"}

    def normalize(self, raw_inputs: dict[str, Any]) -> list[InputValue]:
        if raw_inputs is None:
            return []

        raw_map = dict(raw_inputs)
        normalized_values: list[InputValue] = []

        # Handle explicit sections.
        for section_name, section_value in raw_map.items():
            lower_section = str(section_name).strip().lower()
            if lower_section in self.reserved_sections:
                normalized_values.extend(self._normalize_section(section_value, VariableOrigin.GLOBAL if lower_section in {"global", "globals"} else VariableOrigin.RESULT, None))
                continue

            category_id = self._category_id_for(section_name)
            if category_id is not None:
                normalized_values.extend(self._normalize_section(section_value, VariableOrigin.CATEGORY, category_id))
                continue

            # Top-level variable entries are treated as global values when they resolve.
            if not isinstance(section_value, dict):
                normalized_values.extend(self._normalize_entry(section_name, section_value, VariableOrigin.GLOBAL, None))
                continue

            # If an unknown top-level dict is provided, attempt to resolve contained variables.
            normalized_values.extend(self._normalize_section(section_value, VariableOrigin.GLOBAL, None))

        return normalized_values

    def _normalize_section(self, section_value: Any, source: VariableOrigin, category_id: str | None) -> list[InputValue]:
        if not isinstance(section_value, dict):
            return []

        normalized_section: list[InputValue] = []
        for raw_key, raw_value in section_value.items():
            normalized_section.extend(self._normalize_entry(raw_key, raw_value, source, category_id))
        return normalized_section

    def _normalize_entry(self, raw_key: str, raw_value: Any, source: VariableOrigin, category_id: str | None) -> list[InputValue]:
        if raw_value is None:
            return []

        variable_id = self._canonical_variable_id(raw_key)
        if variable_id is None:
            return [InputValue(variable_id=str(raw_key), raw_value=raw_value, value=raw_value, category_id=category_id, source=VariableOrigin.UNKNOWN, is_valid=False, errors=["Variable desconocida."], normalized=False)]

        if self._is_missing_value(raw_value):
            return []

        definition = get_variable_definition(variable_id)
        parsed_value, errors = self._parse_value(variable_id, raw_value, definition)
        is_valid = len(errors) == 0

        return [
            InputValue(
                variable_id=variable_id,
                raw_value=raw_value,
                value=parsed_value,
                category_id=category_id,
                source=(VariableOrigin.RESULT if source == VariableOrigin.RESULT else (VariableOrigin.CATEGORY if category_id else VariableOrigin.GLOBAL)),
                is_valid=is_valid,
                errors=errors,
                normalized=is_valid,
            )
        ]

    def _canonical_variable_id(self, raw_key: str) -> str | None:
        candidate = str(raw_key).strip()
        if candidate in VARIABLE_CATALOG:
            return candidate

        candidate_lower = candidate.lower()
        alias_target = self.alias_map.get(candidate) or self.alias_map.get(candidate_lower)
        if alias_target is not None:
            return alias_target

        for variable_id in VARIABLE_CATALOG:
            if variable_id.lower() == candidate_lower:
                return variable_id

        return None

    def _is_missing_value(self, raw_value: Any) -> bool:
        if raw_value is None:
            return True
        if isinstance(raw_value, str) and raw_value.strip() == "":
            return True
        if isinstance(raw_value, str) and raw_value.strip().lower() in {"null", "none", "nan"}:
            return True
        return False

    def _parse_value(self, variable_id: str, raw_value: Any, definition: VariableDefinition | None) -> tuple[Any, list[str]]:
        if definition is None:
            return raw_value, []

        if definition.variable_type == VariableType.INTEGER:
            return self._parse_integer(raw_value)
        if definition.variable_type == VariableType.FLOAT:
            return self._parse_float(raw_value)
        if definition.variable_type == VariableType.BOOLEAN:
            return self._parse_boolean(raw_value)
        return raw_value, []

    def _parse_integer(self, raw_value: Any) -> tuple[int | None, list[str]]:
        if isinstance(raw_value, int) and not isinstance(raw_value, bool):
            return raw_value, []
        if isinstance(raw_value, float) and raw_value.is_integer():
            return int(raw_value), []
        if isinstance(raw_value, str):
            text = raw_value.strip()
            if text == "":
                return None, ["Valor vacío."]
            try:
                return int(float(text)), []
            except ValueError:
                return None, ["Valor entero inválido."]
        return None, ["Valor entero inválido."]

    def _parse_float(self, raw_value: Any) -> tuple[float | None, list[str]]:
        if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
            return float(raw_value), []
        if isinstance(raw_value, str):
            text = raw_value.strip()
            if text == "":
                return None, ["Valor vacío."]
            try:
                return float(text), []
            except ValueError:
                return None, ["Valor numérico inválido."]
        return None, ["Valor numérico inválido."]

    def _parse_boolean(self, raw_value: Any) -> tuple[bool | None, list[str]]:
        if isinstance(raw_value, bool):
            return raw_value, []
        if isinstance(raw_value, str):
            normalized = raw_value.strip().lower()
            if normalized in {"true", "yes", "1"}:
                return True, []
            if normalized in {"false", "no", "0"}:
                return False, []
        return None, ["Valor booleano inválido."]

    def _category_id_for(self, section_name: str) -> str | None:
        lookup = str(section_name).strip().lower()
        for category_id in CATEGORY_CATALOG:
            if category_id.lower() == lookup:
                return category_id
        return None


class DefaultVariableResolver(VariableResolver):
    def resolve(self, normalized_inputs: list[InputValue]) -> VariableResolutionResult:
        result = VariableResolutionResult()

        for value in normalized_inputs:
            if value.source == VariableOrigin.UNKNOWN:
                result.unknown_inputs.append(value)
                continue

            if value.source == VariableOrigin.RESULT:
                result.result_inputs[value.variable_id] = value
                continue

            if value.source == VariableOrigin.CATEGORY:
                category_inputs = result.category_inputs.setdefault(value.category_id or "unknown", {})
                existing = category_inputs.get(value.variable_id)
                if existing is not None and existing.value != value.value:
                    result.conflicts.append(
                        ConflictRecord(
                            variable_id=value.variable_id,
                            category_id=value.category_id,
                            existing_source=existing.source,
                            new_source=value.source,
                            existing_value=existing.value,
                            new_value=value.value,
                            message=f"Valor distinto para {value.variable_id} en la categoría {value.category_id}.",
                            sources=[existing.source, value.source],
                        )
                    )
                category_inputs[value.variable_id] = value
                continue

            result.global_inputs[value.variable_id] = value

        self._consolidate(result)
        return result

    def _consolidate(self, result: VariableResolutionResult) -> None:
        for category_id, values in result.category_inputs.items():
            for variable_id, input_value in values.items():
                existing = result.consolidated_inputs.get(variable_id)
                if existing is not None and existing.value != input_value.value:
                    result.conflicts.append(
                        ConflictRecord(
                            variable_id=variable_id,
                            category_id=category_id,
                            existing_source=existing.source,
                            new_source=input_value.source,
                            existing_value=existing.value,
                            new_value=input_value.value,
                            message=(
                                f"Conflicto de variables para {variable_id}: "
                                f"valor de la categoría {category_id} compite con entrada previa."
                            ),
                            sources=[existing.source, input_value.source],
                        )
                    )
                result.consolidated_inputs[variable_id] = input_value

        for variable_id, input_value in result.global_inputs.items():
            existing = result.consolidated_inputs.get(variable_id)
            if existing is not None and existing.value != input_value.value:
                result.conflicts.append(
                    ConflictRecord(
                        variable_id=variable_id,
                        existing_source=existing.source,
                        new_source=input_value.source,
                        existing_value=existing.value,
                        new_value=input_value.value,
                        message=(
                            f"Conflicto entre valor global y categoría para {variable_id}. "
                            "La variable de categoría tiene precedencia."
                        ),
                        sources=[existing.source, input_value.source],
                    )
                )
            elif existing is None:
                result.consolidated_inputs[variable_id] = input_value

        for variable_id, input_value in result.result_inputs.items():
            existing = result.consolidated_inputs.get(variable_id)
            if existing is not None and existing.value != input_value.value:
                result.conflicts.append(
                    ConflictRecord(
                        variable_id=variable_id,
                        existing_source=existing.source,
                        new_source=input_value.source,
                        existing_value=existing.value,
                        new_value=input_value.value,
                        message=(
                            f"Valor esperado para {variable_id} difiere de la entrada calculable."
                        ),
                        sources=[existing.source, input_value.source],
                    )
                )
            result.consolidated_inputs[variable_id] = input_value

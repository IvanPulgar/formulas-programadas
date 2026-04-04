from domain.services.input_processing import (
    DefaultInputNormalizer,
    DefaultVariableResolver,
    VariableOrigin,
)


def test_normalize_global_and_category_values():
    normalizer = DefaultInputNormalizer()
    raw_inputs = {
        "global": {"λ": "2", "μ": "3"},
        "PICS": {"Wq": "0.5", "rho": "0.67"},
        "expected": {"L": "5"},
    }

    normalized = normalizer.normalize(raw_inputs)
    normalized_map = {value.variable_id: value for value in normalized}

    assert normalized_map["lambda_"].value == 2.0
    assert normalized_map["lambda_"].source == VariableOrigin.GLOBAL
    assert normalized_map["mu"].value == 3.0
    assert normalized_map["Wq"].category_id == "PICS"
    assert normalized_map["Wq"].source == VariableOrigin.CATEGORY
    assert normalized_map["L"].source == VariableOrigin.RESULT
    assert normalized_map["L"].normalized is True


def test_variable_resolver_applies_category_precedence():
    normalizer = DefaultInputNormalizer()
    resolver = DefaultVariableResolver()

    raw_inputs = {
        "global": {"lambda_": "2", "mu": "3"},
        "PICS": {"lambda_": "4", "Wq": "0.6"},
    }

    normalized = normalizer.normalize(raw_inputs)
    resolved = resolver.resolve(normalized)

    assert resolved.consolidated_inputs["lambda_"].value == 4.0
    assert resolved.consolidated_inputs["lambda_"].source == VariableOrigin.CATEGORY
    assert resolved.global_inputs["mu"].value == 3.0
    assert resolved.consolidated_inputs["mu"].value == 3.0
    assert resolved.category_inputs["PICS"]["Wq"].value == 0.6
    assert len(resolved.conflicts) == 1
    assert "Conflicto" in resolved.conflicts[0].message


def test_conflict_between_global_and_category_with_distinct_values():
    normalizer = DefaultInputNormalizer()
    resolver = DefaultVariableResolver()

    raw_inputs = {
        "global": {"mu": "4"},
        "PICM": {"mu": "5"},
    }

    normalized = normalizer.normalize(raw_inputs)
    resolved = resolver.resolve(normalized)

    assert resolved.consolidated_inputs["mu"].value == 5.0
    assert resolved.consolidated_inputs["mu"].source == VariableOrigin.CATEGORY
    assert len(resolved.conflicts) == 1
    assert resolved.conflicts[0].variable_id == "mu"
    assert resolved.conflicts[0].existing_value == 5.0
    assert resolved.conflicts[0].new_value == 4.0


def test_unknown_variable_is_reported_as_unknown():
    normalizer = DefaultInputNormalizer()
    raw_inputs = {"global": {"foobar": "10"}}

    normalized = normalizer.normalize(raw_inputs)
    assert len(normalized) == 1
    assert normalized[0].source == VariableOrigin.UNKNOWN
    assert normalized[0].is_valid is False
    assert "desconocida" in normalized[0].errors[0]

from domain.formulas.registry import get_formula_by_id
from domain.services import DefaultInputNormalizer, DefaultVariableResolver, FormulaMatcher


def normalize_and_resolve(raw_inputs):
    normalizer = DefaultInputNormalizer()
    resolver = DefaultVariableResolver()
    normalized = normalizer.normalize(raw_inputs)
    return resolver.resolve(normalized)


def test_formula_matcher_selects_pics_candidates_for_category_inputs():
    resolution = normalize_and_resolve({"PICS": {"lambda_": "2.0", "mu": "5.0"}})
    matcher = FormulaMatcher()
    result = matcher.match(resolution)

    assert len(result.selected) == 2
    assert all(candidate.formula.category.value == "PICS" for candidate in result.selected)
    assert result.is_ambiguous is False
    assert any("categoría dominante" in explanation.lower() for explanation in result.explanation)


def test_formula_matcher_returns_two_candidates_when_two_formulas_are_evaluated():
    resolution = normalize_and_resolve({"PICS": {"lambda_": "2.0", "mu": "5.0"}})
    formulas = [get_formula_by_id("pics_wq"), get_formula_by_id("pics_w")]
    assert all(formulas)

    matcher = FormulaMatcher()
    result = matcher.match(resolution, formulas=formulas)

    assert len(result.selected) == 2
    assert result.is_ambiguous is False
    assert result.selected[0].matching_score >= result.selected[1].matching_score


def test_formula_matcher_detects_ambiguity_for_different_categories_with_similar_scores():
    resolution = normalize_and_resolve(
        {
            "PFCS": {"lambda_": "2.0", "mu": "3.0", "M": "5"},
            "PICM": {"lambda_": "2.0", "mu": "3.0", "k": "2"},
        }
    )
    formulas = [get_formula_by_id("pfcs_rho"), get_formula_by_id("picm_rho")]
    assert all(formulas)

    matcher = FormulaMatcher()
    result = matcher.match(resolution, formulas=formulas)

    assert len(result.selected) == 2
    assert result.is_ambiguous is True
    assert any("ambigüedad" in explanation.lower() for explanation in result.explanation)


def test_formula_matcher_discards_formula_failing_pics_restrictions():
    resolution = normalize_and_resolve({"PICS": {"lambda_": "5.0", "mu": "2.0"}})
    formulas = [get_formula_by_id("pics_w"), get_formula_by_id("pics_l")]
    assert all(formulas)

    matcher = FormulaMatcher()
    result = matcher.match(resolution, formulas=formulas)

    assert len(result.candidates) == 0
    assert len(result.discarded) == 2
    assert all("restricción" in item["reason"].lower() or "validación" in item["reason"].lower() for item in result.discarded)


def test_formula_matcher_accepts_result_variable_with_one_missing_input():
    resolution = normalize_and_resolve(
        {
            "PICS": {"Wq": "0.2"},
            "global": {"lambda_": "2.0"},
        }
    )
    formula = get_formula_by_id("pics_wq")
    assert formula is not None

    matcher = FormulaMatcher()
    result = matcher.match(resolution, formulas=[formula])

    assert len(result.selected) == 1
    assert result.selected[0].formula.id == "pics_wq"
    assert result.selected[0].missing_variables == ["mu"]
    assert result.selected[0].matching_score > 0

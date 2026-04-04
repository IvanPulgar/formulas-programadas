import pytest

from domain.formulas import FORMULAS, get_formula_by_id


def test_intro_time_between_arrivals():
    formula = get_formula_by_id("intro_time_between_arrivals")
    assert formula is not None
    result = formula.calculate({"lambda_": 2.0})
    assert pytest.approx(result, rel=1e-9) == 0.5


def test_intro_time_between_services():
    formula = get_formula_by_id("intro_time_between_services")
    assert formula is not None
    result = formula.calculate({"mu": 4.0})
    assert pytest.approx(result, rel=1e-9) == 0.25


def test_intro_system_response_time():
    formula = get_formula_by_id("intro_system_response_time")
    assert formula is not None
    result = formula.calculate({"Wq": 1.0, "mu": 2.0})
    assert pytest.approx(result, rel=1e-9) == 1.5


def test_pics_rho():
    formula = get_formula_by_id("pics_rho")
    assert formula is not None
    result = formula.calculate({"lambda_": 3.0, "mu": 5.0})
    assert pytest.approx(result, rel=1e-9) == 0.6


def test_pics_p0():
    formula = get_formula_by_id("pics_p0")
    assert formula is not None
    result = formula.calculate({"lambda_": 2.0, "mu": 5.0})
    assert pytest.approx(result, rel=1e-9) == 0.6


def test_pics_wq_and_l_relations():
    wq_formula = get_formula_by_id("pics_wq")
    w_formula = get_formula_by_id("pics_w")
    l_formula = get_formula_by_id("pics_l")
    ln_formula = get_formula_by_id("pics_ln")
    rho_formula = get_formula_by_id("pics_rho")
    assert wq_formula is not None
    assert w_formula is not None
    assert l_formula is not None
    assert ln_formula is not None
    assert rho_formula is not None

    inputs = {"lambda_": 2.0, "mu": 5.0, "n": 1}
    wq = wq_formula.calculate(inputs)
    w = w_formula.calculate(inputs)
    l = l_formula.calculate(inputs)
    lq_formula = get_formula_by_id("pics_lq")
    assert lq_formula is not None
    lq = lq_formula.calculate(inputs)
    rho = rho_formula.calculate(inputs)
    ln = ln_formula.calculate(inputs)

    assert pytest.approx(l, rel=1e-9) == pytest.approx(2.0 * w, rel=1e-9)
    assert pytest.approx(lq, rel=1e-9) == pytest.approx(2.0 * wq, rel=1e-9)
    assert pytest.approx(ln, rel=1e-9) == pytest.approx(lq / rho, rel=1e-9)


def test_pics_ct_total():
    ct_formula = get_formula_by_id("pics_ct")
    assert ct_formula is not None
    values = {"CT_TE": 10.0, "CT_TS": 5.0, "CT_TSE": 2.0, "CT_S": 3.0}
    assert pytest.approx(ct_formula.calculate(values), rel=1e-9) == 20.0


def test_registry_contains_intro_and_pics():
    ids = {formula.id for formula in FORMULAS}
    assert "intro_time_between_arrivals" in ids
    assert "pics_rho" in ids
    assert "pics_wq" in ids
    assert "pfcs_p0" in ids
    assert "pfcm_p0" in ids


def test_pfcs_probabilities_and_waiting():
    p0_formula = get_formula_by_id("pfcs_p0")
    pn_formula = get_formula_by_id("pfcs_pn")
    wq_formula = get_formula_by_id("pfcs_wq")
    w_formula = get_formula_by_id("pfcs_w")
    assert p0_formula is not None
    assert pn_formula is not None
    assert wq_formula is not None
    assert w_formula is not None

    inputs = {"lambda_": 2.0, "mu": 3.0, "M": 5, "n": 2}
    p0 = p0_formula.calculate({"lambda_": 2.0, "mu": 3.0, "M": 5})
    pn = pn_formula.calculate(inputs)

    assert 0 < p0 < 1
    assert 0 < pn < 1
    assert 1.0 - p0 > 0
    assert wq_formula.calculate({"lambda_": 2.0, "mu": 3.0, "M": 5}) >= 0
    assert w_formula.calculate({"lambda_": 2.0, "mu": 3.0, "M": 5}) >= 0


def test_pfcm_probabilities_and_utilization():
    p0_formula = get_formula_by_id("pfcm_p0")
    pk_formula = get_formula_by_id("pfcm_pk")
    lq_formula = get_formula_by_id("pfcm_lq")
    rho_formula = get_formula_by_id("pfcm_rho")
    assert p0_formula is not None
    assert pk_formula is not None
    assert lq_formula is not None
    assert rho_formula is not None

    inputs = {"lambda_": 2.0, "mu": 2.0, "k": 2, "M": 5, "n": 2}
    p0 = p0_formula.calculate({"lambda_": 2.0, "mu": 2.0, "k": 2, "M": 5})
    pk = pk_formula.calculate({"lambda_": 2.0, "mu": 2.0, "k": 2, "M": 5})
    lq = lq_formula.calculate({"lambda_": 2.0, "mu": 2.0, "k": 2, "M": 5})
    rho = rho_formula.calculate({"lambda_": 2.0, "mu": 2.0, "k": 2, "M": 5})

    assert 0 < p0 < 1
    assert 0 <= pk <= 1
    assert lq >= 0
    assert 0 <= rho <= 1


def test_picm_p0_and_pk():
    p0_formula = get_formula_by_id("picm_p0")
    pk_formula = get_formula_by_id("picm_pk")
    assert p0_formula is not None
    assert pk_formula is not None

    inputs = {"lambda_": 4.0, "mu": 3.0, "k": 2}
    p0 = p0_formula.calculate(inputs)
    pk = pk_formula.calculate(inputs)

    assert 0 < p0 < 1
    assert 0 < pk < 1
    assert pytest.approx(1.0 - pk, rel=1e-9) == get_formula_by_id("picm_pne").calculate(inputs)


def test_picm_pn_states():
    pn_without = get_formula_by_id("picm_pn_without_queue")
    pn_with = get_formula_by_id("picm_pn_with_queue")
    assert pn_without is not None
    assert pn_with is not None

    inputs = {"lambda_": 4.0, "mu": 3.0, "k": 2, "n": 1}
    result_without = pn_without.calculate(inputs)
    assert result_without > 0

    inputs_queue = {"lambda_": 4.0, "mu": 3.0, "k": 2, "n": 3}
    result_with = pn_with.calculate(inputs_queue)
    assert result_with > 0


def test_picm_performance_metrics():
    l_formula = get_formula_by_id("picm_l")
    w_formula = get_formula_by_id("picm_w")
    wq_formula = get_formula_by_id("picm_wq")
    lq_formula = get_formula_by_id("picm_lq")
    assert l_formula is not None
    assert w_formula is not None
    assert wq_formula is not None
    assert lq_formula is not None

    inputs = {"lambda_": 4.0, "mu": 3.0, "k": 2}
    l = l_formula.calculate(inputs)
    w = w_formula.calculate(inputs)
    wq = wq_formula.calculate(inputs)
    lq = lq_formula.calculate(inputs)

    assert pytest.approx(l, rel=1e-9) == pytest.approx(4.0 * w, rel=1e-6)
    assert pytest.approx(lq, rel=1e-9) == pytest.approx(4.0 * wq, rel=1e-6)


def test_picm_costs_and_tt():
    ct_formula = get_formula_by_id("picm_ct")
    tt_formula = get_formula_by_id("picm_tt")
    assert ct_formula is not None
    assert tt_formula is not None

    values = {"CT_TE": 4.0, "CT_TS": 3.0, "CT_TSE": 2.0, "CT_S": 6.0}
    assert pytest.approx(ct_formula.calculate(values), rel=1e-9) == 15.0

    tt = tt_formula.calculate({"lambda_": 4.0, "Wq": 0.1})
    assert pytest.approx(tt, rel=1e-9) == 0.96


def test_picm_invalid_stability_raises():
    p0_formula = get_formula_by_id("picm_p0")
    assert p0_formula is not None

    with pytest.raises(ValueError):
        p0_formula.calculate({"lambda_": 10.0, "mu": 1.0, "k": 2})

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
    assert "pics_lq_from_rho" in ids
    assert "pfcs_p0" in ids
    assert "pfcm_p0" in ids


def test_pics_lq_from_rho():
    """Lq = ρ² / (1 − ρ) with ρ = 0.5 → 0.25/0.5 = 0.5"""
    formula = get_formula_by_id("pics_lq_from_rho")
    assert formula is not None
    assert formula.result_variable == "Lq"
    assert formula.input_variables == ["rho"]
    result = formula.calculate({"rho": 0.5})
    assert pytest.approx(result, rel=1e-9) == 0.5


def test_pics_lq_from_rho_equivalence():
    """Lq(ρ) must equal Lq(λ,μ) when ρ = λ/μ."""
    lq_lambda = get_formula_by_id("pics_lq")
    lq_rho = get_formula_by_id("pics_lq_from_rho")
    inputs = {"lambda_": 2.0, "mu": 5.0}
    rho = 2.0 / 5.0
    lq_via_lambda = lq_lambda.calculate(inputs)
    lq_via_rho = lq_rho.calculate({"rho": rho})
    assert pytest.approx(lq_via_lambda, rel=1e-9) == pytest.approx(lq_via_rho, rel=1e-9)


def test_pics_lq_from_rho_invalid_rho_one():
    """ρ = 1 must raise ValueError (division by zero)."""
    formula = get_formula_by_id("pics_lq_from_rho")
    with pytest.raises(ValueError, match=r"0 < ρ < 1"):
        formula.calculate({"rho": 1.0})


def test_pics_lq_from_rho_invalid_rho_zero():
    """ρ = 0 must raise ValueError."""
    formula = get_formula_by_id("pics_lq_from_rho")
    with pytest.raises(ValueError, match=r"0 < ρ < 1"):
        formula.calculate({"rho": 0.0})


def test_pics_lq_from_rho_invalid_negative():
    """ρ < 0 must raise ValueError."""
    formula = get_formula_by_id("pics_lq_from_rho")
    with pytest.raises(ValueError, match=r"0 < ρ < 1"):
        formula.calculate({"rho": -0.3})


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

    tt = tt_formula.calculate({"lambda_": 4.0, "Wq": 0.1, "H": 8.0})
    assert pytest.approx(tt, rel=1e-9) == 0.96


def test_picm_invalid_stability_raises():
    p0_formula = get_formula_by_id("picm_p0")
    assert p0_formula is not None

    with pytest.raises(ValueError):
        p0_formula.calculate({"lambda_": 10.0, "mu": 1.0, "k": 2})


def test_picm_p_wait_erlang_c_known_case():
    """Erlang C known case: λ=18, μ=10, c=3 => P0≈0.145985 and P(wait)≈0.354745."""
    p0_formula = get_formula_by_id("picm_p0")
    p_wait_formula = get_formula_by_id("picm_pk")
    assert p0_formula is not None
    assert p_wait_formula is not None

    inputs = {"lambda_": 18.0, "mu": 10.0, "k": 3}
    p0 = p0_formula.calculate(inputs)
    p_wait = p_wait_formula.calculate(inputs)

    assert pytest.approx(p0, rel=1e-6) == 0.14598540145985403
    assert pytest.approx(p_wait, rel=1e-6) == 0.3547445255474453


@pytest.mark.parametrize(
    "inputs",
    [
        {"lambda_": 0.0, "mu": 10.0, "k": 3},
        {"lambda_": -1.0, "mu": 10.0, "k": 3},
        {"lambda_": 18.0, "mu": 0.0, "k": 3},
        {"lambda_": 18.0, "mu": -2.0, "k": 3},
        {"lambda_": 18.0, "mu": 10.0, "k": 0},
        {"lambda_": 18.0, "mu": 10.0, "k": -1},
        {"lambda_": 18.0, "mu": 10.0, "k": 2.5},
        {"lambda_": 30.0, "mu": 10.0, "k": 3},
        {"lambda_": 31.0, "mu": 10.0, "k": 3},
    ],
)
def test_picm_p_wait_invalid_inputs_raise(inputs):
    formula = get_formula_by_id("picm_pk")
    assert formula is not None
    with pytest.raises(ValueError):
        formula.calculate(inputs)


def test_picm_p_wait_solver_and_gallery_latex_are_complete():
    from presentation.catalogs.formula_gallery import GALLERY_CAROUSELS
    from presentation.catalogs.solver_catalog import SOLVER_GROUPS

    solver_card = next(
        card
        for group in SOLVER_GROUPS
        for card in group.cards
        if card.formula_id == "picm_pk"
    )
    assert "\\frac{1}{1-\\rho}" in solver_card.latex
    assert "Erlang C" in solver_card.name

    gallery_card = next(
        card
        for carousel in GALLERY_CAROUSELS
        for card in carousel.cards
        if card.id == "f33"
    )
    assert "k\\mu" in gallery_card.latex
    assert "k\\mu-\\lambda" in gallery_card.latex
    assert "Erlang C" in gallery_card.name


# =====================================================================
# A-group: PICS derived (1 formula)
# =====================================================================

def test_pics_prob_q_ge_2():
    """A1: P(Q ≥ 2) = ρ³.  ρ=0.5 → 0.125"""
    formula = get_formula_by_id("pics_prob_q_ge_2")
    assert formula is not None
    assert formula.input_variables == ["rho"]
    result = formula.calculate({"rho": 0.5})
    assert pytest.approx(result, rel=1e-9) == 0.125


def test_pics_prob_q_ge_2_invalid():
    formula = get_formula_by_id("pics_prob_q_ge_2")
    with pytest.raises(ValueError):
        formula.calculate({"rho": 1.0})
    with pytest.raises(ValueError):
        formula.calculate({"rho": 0.0})


# =====================================================================
# B-group: PICM derived probabilities (7 formulas)
# =====================================================================

def test_picm_prob_idle():
    """B1: 1 − Pk.  Pk=0.35 → 0.65"""
    formula = get_formula_by_id("picm_prob_idle")
    assert formula is not None
    result = formula.calculate({"Pk": 0.35})
    assert pytest.approx(result, rel=1e-9) == 0.65


def test_picm_prob_exactly_c():
    """B2: Pc = (a^c / c!) P0.  a=1.8, c=3, P0=0.145985"""
    formula = get_formula_by_id("picm_prob_exactly_c")
    assert formula is not None
    from math import factorial
    a, c, p0 = 1.8, 3, 0.145985
    expected = (a**c / factorial(c)) * p0
    result = formula.calculate({"a": a, "k": c, "P0": p0})
    assert pytest.approx(result, rel=1e-6) == expected


def test_picm_prob_c_plus_r():
    """B3: P_{c+r} = Pc·ρ^r.  Pc=0.141898, ρ=0.6, r=2"""
    formula = get_formula_by_id("picm_prob_c_plus_r")
    assert formula is not None
    result = formula.calculate({"Pc": 0.141898, "rho": 0.6, "r": 2})
    assert pytest.approx(result, rel=1e-6) == 0.141898 * 0.6**2


def test_picm_prob_c_plus_1():
    """B4: P_{c+1} = Pc·ρ"""
    formula = get_formula_by_id("picm_prob_c_plus_1")
    assert formula is not None
    result = formula.calculate({"Pc": 0.2, "rho": 0.5})
    assert pytest.approx(result, rel=1e-9) == 0.1


def test_picm_prob_c_plus_2():
    """B5: P_{c+2} = Pc·ρ²"""
    formula = get_formula_by_id("picm_prob_c_plus_2")
    assert formula is not None
    result = formula.calculate({"Pc": 0.2, "rho": 0.5})
    assert pytest.approx(result, rel=1e-9) == 0.05


def test_picm_prob_q_waiting():
    """B6: P(Q=q) = Pc·ρ^q"""
    formula = get_formula_by_id("picm_prob_q_waiting")
    assert formula is not None
    result = formula.calculate({"Pc": 0.3, "rho": 0.4, "q": 3})
    assert pytest.approx(result, rel=1e-9) == 0.3 * 0.4**3


def test_picm_prob_q1_or_q2():
    """B7: P(Q=q1 ∪ Q=q2) = Pc·ρ^q1 + Pc·ρ^q2"""
    formula = get_formula_by_id("picm_prob_q1_or_q2")
    assert formula is not None
    result = formula.calculate({"Pc": 0.3, "rho": 0.4, "q1": 1, "q2": 3})
    expected = 0.3 * 0.4 + 0.3 * 0.4**3
    assert pytest.approx(result, rel=1e-9) == expected


# =====================================================================
# C-group / D1: PFHET — Pob. Finita Heterogénea (11 formulas)
# =====================================================================

def test_pfhet_mu_bar():
    """C1: μ̄ = (μ1+μ2)/2.  μ1=3, μ2=4 → 3.5"""
    formula = get_formula_by_id("pfhet_mu_bar")
    assert formula is not None
    result = formula.calculate({"mu1": 3.0, "mu2": 4.0})
    assert pytest.approx(result, rel=1e-9) == 3.5


def test_pfhet_lambda_n():
    """C2: λ_n = (M-n)λ.  M=7, n=2, λ=0.2 → 1.0"""
    formula = get_formula_by_id("pfhet_lambda_n")
    assert formula is not None
    result = formula.calculate({"M": 7, "n": 2, "lambda_": 0.2})
    assert pytest.approx(result, rel=1e-9) == 1.0


def test_pfhet_mu_n_cases():
    """C3: μ_n piecewise: n=0→0, n=1→μ̄, n=2→μ1+μ2"""
    formula = get_formula_by_id("pfhet_mu_n")
    assert formula is not None
    args = {"mu_bar": 3.5, "mu1": 3.0, "mu2": 4.0}
    assert formula.calculate({"n": 0, **args}) == 0.0
    assert pytest.approx(formula.calculate({"n": 1, **args}), rel=1e-9) == 3.5
    assert pytest.approx(formula.calculate({"n": 2, **args}), rel=1e-9) == 7.0
    assert pytest.approx(formula.calculate({"n": 5, **args}), rel=1e-9) == 7.0


def test_pfhet_p0():
    """C5: P₀ from heterogeneous model — must be between 0 and 1."""
    formula = get_formula_by_id("pfhet_p0")
    assert formula is not None
    result = formula.calculate({"M": 7, "lambda_": 0.2, "mu1": 3.0, "mu2": 4.0})
    assert 0 < result < 1


def test_pfhet_pn_state_0_equals_p0():
    """C4: P_n with n=0 must equal P₀ from C5."""
    pn = get_formula_by_id("pfhet_pn")
    p0 = get_formula_by_id("pfhet_p0")
    assert pn is not None and p0 is not None
    args = {"M": 7, "lambda_": 0.2, "mu1": 3.0, "mu2": 4.0}
    assert pytest.approx(pn.calculate({"n": 0, **args}), rel=1e-9) == p0.calculate(args)


def test_pfhet_pn_sum_to_one():
    """All P_n for n=0..M must sum to 1."""
    pn = get_formula_by_id("pfhet_pn")
    M = 7
    args = {"M": M, "lambda_": 0.2, "mu1": 3.0, "mu2": 4.0}
    total = sum(pn.calculate({"n": n, **args}) for n in range(M + 1))
    assert pytest.approx(total, rel=1e-9) == 1.0


def test_pfhet_prob_no_wait():
    """C6: Probability of no waiting — must be between 0 and 1."""
    formula = get_formula_by_id("pfhet_prob_no_wait")
    assert formula is not None
    result = formula.calculate({"M": 7, "k": 2, "lambda_": 0.2, "mu1": 3.0, "mu2": 4.0})
    assert 0 < result <= 1


def test_pfhet_prob_n_ge_2():
    """C7: P(N≥2) = 1-(P0+P1)."""
    formula = get_formula_by_id("pfhet_prob_n_ge_2")
    assert formula is not None
    result = formula.calculate({"P0": 0.034386, "P1": 0.118211})
    expected = 1.0 - (0.034386 + 0.118211)
    assert pytest.approx(result, rel=1e-6) == expected


def test_pfhet_prob_available():
    """C8: P(available) = P0+P1.  P0=0.034386, P1=0.118211 → 0.152597"""
    formula = get_formula_by_id("pfhet_prob_available")
    assert formula is not None
    result = formula.calculate({"P0": 0.034386, "P1": 0.118211})
    assert pytest.approx(result, rel=1e-6) == 0.152597


def test_pfhet_operating_units():
    """C9: Operating = M-L.  M=7, L=3.308336 → 3.691664"""
    formula = get_formula_by_id("pfhet_operating_units")
    assert formula is not None
    result = formula.calculate({"M": 7, "L": 3.308336})
    assert pytest.approx(result, rel=1e-6) == 3.691664


def test_pfhet_effective_arrival():
    """C10: λ_ef = λ(M-L).  λ=0.2, M=7, L=3.308336"""
    formula = get_formula_by_id("pfhet_effective_arrival")
    assert formula is not None
    result = formula.calculate({"lambda_": 0.2, "M": 7, "L": 3.308336})
    expected = 0.2 * (7 - 3.308336)
    assert pytest.approx(result, rel=1e-6) == expected


def test_pfhet_percent_outside():
    """D1: % = (M-L)/M·100.  M=15, L=0.863956 → ~94.24%"""
    formula = get_formula_by_id("pfhet_percent_outside")
    assert formula is not None
    result = formula.calculate({"M": 15, "L": 0.863956})
    expected = (15 - 0.863956) / 15 * 100
    assert pytest.approx(result, rel=1e-4) == expected


def test_registry_contains_all_new_formulas():
    """Verify all 19 new formula IDs are in the registry."""
    ids = {f.id for f in FORMULAS}
    new_ids = [
        "pics_prob_q_ge_2",
        "picm_prob_idle", "picm_prob_exactly_c", "picm_prob_c_plus_r",
        "picm_prob_c_plus_1", "picm_prob_c_plus_2",
        "picm_prob_q_waiting", "picm_prob_q1_or_q2",
        "pfhet_mu_bar", "pfhet_lambda_n", "pfhet_mu_n",
        "pfhet_pn", "pfhet_p0", "pfhet_prob_no_wait",
        "pfhet_prob_n_ge_2", "pfhet_prob_available",
        "pfhet_operating_units", "pfhet_effective_arrival",
        "pfhet_percent_outside",
    ]
    for fid in new_ids:
        assert fid in ids, f"Formula {fid} missing from registry"


# ── Little's Law tests ──────────────────────────────────────────────

def test_intro_little_system():
    formula = get_formula_by_id("intro_little_system")
    assert formula is not None
    result = formula.calculate({"lambda_": 5.0, "W": 2.0})
    assert pytest.approx(result, rel=1e-9) == 10.0


def test_intro_little_queue():
    formula = get_formula_by_id("intro_little_queue")
    assert formula is not None
    result = formula.calculate({"lambda_": 5.0, "Wq": 0.8})
    assert pytest.approx(result, rel=1e-9) == 4.0


def test_intro_little_system_consistency():
    """L = λ·W should match the L computed directly from PICS formulas."""
    pics_l = get_formula_by_id("pics_l")
    pics_w = get_formula_by_id("pics_w")
    little = get_formula_by_id("intro_little_system")
    inputs = {"lambda_": 3.0, "mu": 5.0}
    l_direct = pics_l.calculate(inputs)
    w_value = pics_w.calculate(inputs)
    l_little = little.calculate({"lambda_": 3.0, "W": w_value})
    assert pytest.approx(l_direct, rel=1e-9) == l_little


def test_intro_little_queue_consistency():
    """Lq = λ·Wq should match the Lq computed directly from PICS formulas."""
    pics_lq = get_formula_by_id("pics_lq")
    pics_wq = get_formula_by_id("pics_wq")
    little = get_formula_by_id("intro_little_queue")
    inputs = {"lambda_": 3.0, "mu": 5.0}
    lq_direct = pics_lq.calculate(inputs)
    wq_value = pics_wq.calculate(inputs)
    lq_little = little.calculate({"lambda_": 3.0, "Wq": wq_value})
    assert pytest.approx(lq_direct, rel=1e-9) == lq_little


# ── Alternative TT / CT simplified tests ────────────────────────────

def test_pics_tt_alt_equivalence():
    """TT = λ·H·0.30·ρ·Wn should equal TT = λ·H·0.30·Wq (since Wq = ρ·Wn)."""
    pics_tt = get_formula_by_id("pics_tt")
    pics_tt_alt = get_formula_by_id("pics_tt_alt")
    lambda_, mu = 3.0, 5.0
    rho = lambda_ / mu
    wq = lambda_ / (mu * (mu - lambda_))
    wn = wq / rho
    tt_direct = pics_tt.calculate({"lambda_": lambda_, "Wq": wq, "H": 8.0})
    tt_alt = pics_tt_alt.calculate({"lambda_": lambda_, "rho": rho, "Wn": wn, "H": 8.0})
    assert pytest.approx(tt_direct, rel=1e-9) == tt_alt


def test_picm_ct_simplified():
    formula = get_formula_by_id("picm_ct_simplified")
    assert formula is not None
    result = formula.calculate({"lambda_": 10.0, "W": 0.5, "CTS": 2.0, "k": 3, "CS": 50.0, "H": 8.0})
    expected = 10.0 * 8.0 * 0.5 * 2.0 + 3 * 50.0
    assert pytest.approx(result, rel=1e-9) == expected


def test_picm_tt_alt():
    formula = get_formula_by_id("picm_tt_alt")
    assert formula is not None
    result = formula.calculate({"lambda_": 10.0, "Pk": 0.4, "Wn": 0.25, "H": 8.0})
    expected = 10.0 * 8.0 * 0.30 * 0.4 * 0.25
    assert pytest.approx(result, rel=1e-9) == expected


# ── Solver count and coverage audit ─────────────────────────────────

def test_solver_formula_count_at_least_76():
    """After adding 5 new formulas, solver should have at least 76."""
    from presentation.catalogs.solver_catalog import SOLVER_FORMULA_COUNT
    assert SOLVER_FORMULA_COUNT >= 76


def test_all_solver_latex_keys_exist_in_registry():
    """Every formula in _LATEX dict should have a matching domain FormulaDefinition."""
    from presentation.catalogs.solver_catalog import _LATEX
    registry_ids = {f.id for f in FORMULAS}
    for fid in _LATEX:
        assert fid in registry_ids, f"LaTeX key '{fid}' has no domain FormulaDefinition"


def test_solver_cards_have_descriptions():
    """All solver cards should have a non-empty description."""
    from presentation.catalogs.solver_catalog import SOLVER_GROUPS
    for group in SOLVER_GROUPS:
        for card in group.cards:
            assert card.description, f"SolverCard '{card.formula_id}' has empty description"

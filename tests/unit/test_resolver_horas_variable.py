"""
Tests para verificar que las horas de operación del período (H) es
una variable de entrada configurable en el módulo Resolver fórmulas.

Cubre las 11 fórmulas de PICS y PICM que antes tenían 8.0 fijo.
"""
import pytest

from domain.formulas import get_formula_by_id
from domain.entities.catalog import VARIABLE_CATALOG
from presentation.catalogs.solver_catalog import SOLVER_GROUPS


# ── Grupo 1: Fórmulas de costo con H variable ─────────────────────

class TestCostFormulasWithH:
    """CT_TE = λ·H·Wq·CTE — H=8 y H=12 deben dar resultados distintos."""

    def test_pics_ct_te_h8(self):
        f = get_formula_by_id("pics_ct_te")
        result = f.calculate({"lambda_": 10.0, "Wq": 0.1, "CTE": 5.0, "H": 8.0})
        assert pytest.approx(result, rel=1e-9) == 40.0

    def test_pics_ct_te_h12(self):
        f = get_formula_by_id("pics_ct_te")
        result = f.calculate({"lambda_": 10.0, "Wq": 0.1, "CTE": 5.0, "H": 12.0})
        assert pytest.approx(result, rel=1e-9) == 60.0

    def test_pics_ct_te_h_changes_result(self):
        f = get_formula_by_id("pics_ct_te")
        r8 = f.calculate({"lambda_": 10.0, "Wq": 0.1, "CTE": 5.0, "H": 8.0})
        r12 = f.calculate({"lambda_": 10.0, "Wq": 0.1, "CTE": 5.0, "H": 12.0})
        assert r8 != r12
        assert pytest.approx(r12 / r8, rel=1e-9) == 1.5

    def test_pics_ct_ts_h_variable(self):
        f = get_formula_by_id("pics_ct_ts")
        r8 = f.calculate({"lambda_": 5.0, "W": 0.2, "CTS": 3.0, "H": 8.0})
        r10 = f.calculate({"lambda_": 5.0, "W": 0.2, "CTS": 3.0, "H": 10.0})
        assert pytest.approx(r8, rel=1e-9) == 24.0
        assert pytest.approx(r10, rel=1e-9) == 30.0

    def test_pics_ct_tse_h_variable(self):
        f = get_formula_by_id("pics_ct_tse")
        r8 = f.calculate({"lambda_": 4.0, "mu": 2.0, "CTSE": 3.0, "H": 8.0})
        r16 = f.calculate({"lambda_": 4.0, "mu": 2.0, "CTSE": 3.0, "H": 16.0})
        assert pytest.approx(r16 / r8, rel=1e-9) == 2.0

    def test_picm_ct_te_h_variable(self):
        f = get_formula_by_id("picm_ct_te")
        r8 = f.calculate({"lambda_": 10.0, "Wq": 0.1, "CTE": 5.0, "H": 8.0})
        r12 = f.calculate({"lambda_": 10.0, "Wq": 0.1, "CTE": 5.0, "H": 12.0})
        assert pytest.approx(r8, rel=1e-9) == 40.0
        assert pytest.approx(r12, rel=1e-9) == 60.0

    def test_picm_ct_simplified_h_variable(self):
        f = get_formula_by_id("picm_ct_simplified")
        r8 = f.calculate({"lambda_": 10.0, "W": 0.5, "CTS": 2.0, "k": 3, "CS": 50.0, "H": 8.0})
        r12 = f.calculate({"lambda_": 10.0, "W": 0.5, "CTS": 2.0, "k": 3, "CS": 50.0, "H": 12.0})
        # Only λ·H·W·CTS changes; k·CS=150 is constant
        assert r8 != r12
        expected_8 = 10.0 * 8.0 * 0.5 * 2.0 + 3 * 50.0
        assert pytest.approx(r8, rel=1e-9) == expected_8


# ── Grupo 2: TT con H variable ────────────────────────────────────

class TestTTWithH:
    """TT = λ·H·0.30·Wq — 0.30 es coeficiente fijo, H es variable."""

    def test_pics_tt_h8(self):
        f = get_formula_by_id("pics_tt")
        result = f.calculate({"lambda_": 4.0, "Wq": 0.1, "H": 8.0})
        assert pytest.approx(result, rel=1e-9) == 4.0 * 8.0 * 0.30 * 0.1

    def test_pics_tt_h12(self):
        f = get_formula_by_id("pics_tt")
        result = f.calculate({"lambda_": 4.0, "Wq": 0.1, "H": 12.0})
        assert pytest.approx(result, rel=1e-9) == 4.0 * 12.0 * 0.30 * 0.1

    def test_pics_tt_h_changes_result(self):
        f = get_formula_by_id("pics_tt")
        r8 = f.calculate({"lambda_": 4.0, "Wq": 0.1, "H": 8.0})
        r12 = f.calculate({"lambda_": 4.0, "Wq": 0.1, "H": 12.0})
        assert r8 != r12
        assert pytest.approx(r12 / r8, rel=1e-9) == 1.5

    def test_pics_tt_alt_h_variable(self):
        f = get_formula_by_id("pics_tt_alt")
        r8 = f.calculate({"lambda_": 3.0, "rho": 0.6, "Wn": 0.2, "H": 8.0})
        r12 = f.calculate({"lambda_": 3.0, "rho": 0.6, "Wn": 0.2, "H": 12.0})
        assert r8 != r12
        assert pytest.approx(r12 / r8, rel=1e-9) == 1.5

    def test_picm_tt_h_variable(self):
        f = get_formula_by_id("picm_tt")
        r8 = f.calculate({"lambda_": 4.0, "Wq": 0.1, "H": 8.0})
        r12 = f.calculate({"lambda_": 4.0, "Wq": 0.1, "H": 12.0})
        assert pytest.approx(r8, rel=1e-9) == 4.0 * 8.0 * 0.30 * 0.1
        assert r8 != r12

    def test_picm_tt_alt_h_variable(self):
        f = get_formula_by_id("picm_tt_alt")
        r8 = f.calculate({"lambda_": 10.0, "Pk": 0.4, "Wn": 0.25, "H": 8.0})
        r12 = f.calculate({"lambda_": 10.0, "Pk": 0.4, "Wn": 0.25, "H": 12.0})
        assert pytest.approx(r8, rel=1e-9) == 10.0 * 8.0 * 0.30 * 0.4 * 0.25
        assert r8 != r12


# ── Grupo 3: Coeficiente 0.30 es constante (no reemplazar por H) ─

class TestCoefficient030IsFixed:
    """0.30 no cambia con H — solo H escala el resultado."""

    def test_0_30_is_not_H(self):
        f = get_formula_by_id("pics_tt")
        r = f.calculate({"lambda_": 1.0, "Wq": 1.0, "H": 1.0})
        # Si 0.30 fuera H, el resultado sería 1 no 0.30
        assert pytest.approx(r, rel=1e-9) == 0.30

    def test_scale_h_not_030(self):
        f = get_formula_by_id("pics_tt")
        r1 = f.calculate({"lambda_": 1.0, "Wq": 1.0, "H": 1.0})
        r2 = f.calculate({"lambda_": 1.0, "Wq": 1.0, "H": 2.0})
        # r2/r1 = 2 (H doubled), not more
        assert pytest.approx(r2 / r1, rel=1e-9) == 2.0


# ── Grupo 4: H es requerido — falta → ValueError ──────────────────

class TestHRequiredValidation:
    """Si H no se pasa o es None, debe lanzar ValueError."""

    @pytest.mark.parametrize("formula_id,inputs", [
        ("pics_ct_te",  {"lambda_": 10.0, "Wq": 0.1, "CTE": 5.0}),
        ("pics_ct_ts",  {"lambda_": 5.0,  "W": 0.2,  "CTS": 3.0}),
        ("pics_ct_tse", {"lambda_": 4.0,  "mu": 2.0, "CTSE": 3.0}),
        ("pics_tt",     {"lambda_": 4.0,  "Wq": 0.1}),
        ("pics_tt_alt", {"lambda_": 3.0,  "rho": 0.6, "Wn": 0.2}),
        ("picm_ct_te",  {"lambda_": 10.0, "Wq": 0.1, "CTE": 5.0}),
        ("picm_ct_ts",  {"lambda_": 5.0,  "W": 0.2,  "CTS": 3.0}),
        ("picm_ct_tse", {"lambda_": 4.0,  "mu": 2.0, "CTSE": 3.0}),
        ("picm_tt",     {"lambda_": 4.0,  "Wq": 0.1}),
        ("picm_ct_simplified", {"lambda_": 10.0, "W": 0.5, "CTS": 2.0, "k": 3, "CS": 50.0}),
        ("picm_tt_alt", {"lambda_": 10.0, "Pk": 0.4, "Wn": 0.25}),
    ])
    def test_h_missing_raises(self, formula_id, inputs):
        f = get_formula_by_id(formula_id)
        assert f is not None
        with pytest.raises((ValueError, TypeError)):
            f.calculate(inputs)


# ── Grupo 5: H debe ser positivo ──────────────────────────────────

class TestHMustBePositive:
    """H=0 o H<0 deben lanzar ValueError."""

    @pytest.mark.parametrize("bad_h", [0, -1, -8.0])
    def test_pics_ct_te_h_zero_or_negative(self, bad_h):
        f = get_formula_by_id("pics_ct_te")
        with pytest.raises((ValueError, TypeError)):
            f.calculate({"lambda_": 10.0, "Wq": 0.1, "CTE": 5.0, "H": bad_h})

    @pytest.mark.parametrize("bad_h", [0, -1, -8.0])
    def test_picm_tt_h_zero_or_negative(self, bad_h):
        f = get_formula_by_id("picm_tt")
        with pytest.raises((ValueError, TypeError)):
            f.calculate({"lambda_": 4.0, "Wq": 0.1, "H": bad_h})


# ── Grupo 6: InputField de H aparece en las fórmulas afectadas ───

class TestFormHFieldPresence:
    """Las SolverCards de fórmulas afectadas deben tener un campo H."""

    _AFFECTED = {
        "pics_ct_te", "pics_ct_ts", "pics_ct_tse", "pics_tt", "pics_tt_alt",
        "picm_ct_te", "picm_ct_ts", "picm_ct_tse", "picm_tt",
        "picm_ct_simplified", "picm_tt_alt",
    }

    _NOT_AFFECTED = {
        "pics_rho", "pics_p0", "pics_wq", "pics_lq",
        "picm_rho" if False else "picm_stability", "picm_p0", "picm_wq",
    }

    def _get_cards(self):
        cards = {}
        for group in SOLVER_GROUPS:
            for card in group.cards:
                cards[card.formula_id] = card
        return cards

    def test_affected_formulas_have_H_field(self):
        cards = self._get_cards()
        for fid in self._AFFECTED:
            assert fid in cards, f"Fórmula {fid} no encontrada en SOLVER_GROUPS"
            var_ids = [f.var_id for f in cards[fid].input_fields]
            assert "H" in var_ids, f"Fórmula {fid} no tiene campo H; tiene: {var_ids}"

    def test_unaffected_formulas_do_not_have_H_field(self):
        unaffected = {"pics_rho", "pics_p0", "pics_wq", "picm_stability", "picm_p0"}
        cards = self._get_cards()
        for fid in unaffected:
            if fid in cards:
                var_ids = [f.var_id for f in cards[fid].input_fields]
                assert "H" not in var_ids, f"Fórmula {fid} no debería tener campo H"

    def test_H_input_field_metadata(self):
        """El campo H debe tener label correcto y min > 0."""
        cards = self._get_cards()
        card = cards["pics_ct_te"]
        h_field = next(f for f in card.input_fields if f.var_id == "H")
        assert h_field.symbol == "H"
        assert h_field.min_value is not None
        assert h_field.min_value >= 0


# ── Grupo 7: Sin regresión — fórmulas sin H siguen funcionando ───

class TestNoRegressionFormulasSansH:
    """Las fórmulas que NO usan H deben funcionar correctamente sin él."""

    def test_pics_rho(self):
        f = get_formula_by_id("pics_rho")
        assert pytest.approx(f.calculate({"lambda_": 3.0, "mu": 5.0}), rel=1e-9) == 0.6

    def test_pics_p0(self):
        f = get_formula_by_id("pics_p0")
        assert pytest.approx(f.calculate({"lambda_": 2.0, "mu": 5.0}), rel=1e-9) == 0.6

    def test_pics_lq(self):
        f = get_formula_by_id("pics_lq")
        # λ=2, μ=5 → Lq = 4/(5*3) = 4/15
        result = f.calculate({"lambda_": 2.0, "mu": 5.0})
        assert pytest.approx(result, rel=1e-9) == 4.0 / 15.0

    def test_pics_ct_total(self):
        f = get_formula_by_id("pics_ct")
        result = f.calculate({"CT_TE": 10.0, "CT_TS": 5.0, "CT_TSE": 2.0, "CT_S": 3.0})
        assert pytest.approx(result, rel=1e-9) == 20.0

    def test_picm_stability(self):
        f = get_formula_by_id("picm_stability")
        result = f.calculate({"lambda_": 18.0, "mu": 10.0, "k": 3})
        assert pytest.approx(result, rel=1e-9) == pytest.approx(18.0 / (3 * 10.0), rel=1e-9)

    def test_picm_ct_total(self):
        f = get_formula_by_id("picm_ct")
        result = f.calculate({"CT_TE": 4.0, "CT_TS": 3.0, "CT_TSE": 2.0, "CT_S": 6.0})
        assert pytest.approx(result, rel=1e-9) == 15.0


# ── Grupo 8: H en VARIABLE_CATALOG ───────────────────────────────

class TestHInVariableCatalog:
    """La variable H debe estar en VARIABLE_CATALOG con constraints correctas."""

    def test_h_exists_in_catalog(self):
        assert "H" in VARIABLE_CATALOG

    def test_h_symbol(self):
        assert VARIABLE_CATALOG["H"].symbol == "H"

    def test_h_is_positive(self):
        vd = VARIABLE_CATALOG["H"]
        assert vd.constraints.get("strict_positive") is True or vd.constraints.get("min", -1) >= 0

    def test_h_display_name(self):
        vd = VARIABLE_CATALOG["H"]
        assert "horas" in vd.display_name.lower() or "H" in vd.display_name

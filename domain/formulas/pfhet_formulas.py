from __future__ import annotations

from typing import Any

from domain.entities import FormulaCategory, FormulaDefinition, FormulaType


# ── Validators ──────────────────────────────────────────────────────

def _pos(name: str, value: Any) -> float:
    if value is None:
        raise ValueError(f"{name} es obligatorio.")
    v = float(value)
    if v <= 0:
        raise ValueError(f"{name} debe ser positivo (> 0).")
    return v


def _non_neg(name: str, value: Any) -> float:
    if value is None:
        raise ValueError(f"{name} es obligatorio.")
    v = float(value)
    if v < 0:
        raise ValueError(f"{name} debe ser ≥ 0.")
    return v


def _pos_int(name: str, value: Any) -> int:
    if value is None:
        raise ValueError(f"{name} es obligatorio.")
    v = int(float(value))
    if v < 1:
        raise ValueError(f"{name} debe ser un entero ≥ 1.")
    return v


def _nn_int(name: str, value: Any) -> int:
    if value is None:
        raise ValueError(f"{name} es obligatorio.")
    v = int(float(value))
    if v < 0:
        raise ValueError(f"{name} debe ser un entero ≥ 0.")
    return v


def _prob(name: str, value: Any) -> float:
    if value is None:
        raise ValueError(f"{name} es obligatorio.")
    v = float(value)
    if v < 0 or v > 1:
        raise ValueError(f"{name} debe estar entre 0 y 1.")
    return v


# ── Heterogeneous birth-death helpers ───────────────────────────────

def _birth_rate(i: int, M: int, lam: float) -> float:
    if i < 0 or i >= M:
        return 0.0
    return (M - i) * lam


def _death_rate(i: int, mu_bar: float, mu1: float, mu2: float) -> float:
    if i <= 0:
        return 0.0
    if i == 1:
        return mu_bar
    return mu1 + mu2


def _compute_ratios(M: int, lam: float, mu1: float, mu2: float) -> list[float]:
    mu_bar = (mu1 + mu2) / 2.0
    ratios: list[float] = []
    product = 1.0
    for n in range(1, M + 1):
        li = _birth_rate(n - 1, M, lam)
        mj = _death_rate(n, mu_bar, mu1, mu2)
        if mj <= 0:
            raise ValueError(f"μ_{n} debe ser positivo.")
        product *= li / mj
        ratios.append(product)
    return ratios


def _compute_p0(M: int, lam: float, mu1: float, mu2: float) -> float:
    ratios = _compute_ratios(M, lam, mu1, mu2)
    return 1.0 / (1.0 + sum(ratios))


def _compute_all_pn(M: int, lam: float, mu1: float, mu2: float) -> list[float]:
    ratios = _compute_ratios(M, lam, mu1, mu2)
    p0 = 1.0 / (1.0 + sum(ratios))
    return [p0] + [p0 * r for r in ratios]


# ── Formula functions ────────────────────────────────────────────────

def mu_bar_formula(inputs: dict[str, Any]) -> float:
    mu1 = _pos("μ₁", inputs.get("mu1"))
    mu2 = _pos("μ₂", inputs.get("mu2"))
    return (mu1 + mu2) / 2.0


def lambda_n_formula(inputs: dict[str, Any]) -> float:
    M = _pos_int("M", inputs.get("M"))
    n = _nn_int("n", inputs.get("n"))
    lam = _pos("λ", inputs.get("lambda_"))
    if n > M:
        raise ValueError("n no puede ser mayor que M.")
    return (M - n) * lam


def mu_n_formula(inputs: dict[str, Any]) -> float:
    n = _nn_int("n", inputs.get("n"))
    mu_bar = _pos("μ̄", inputs.get("mu_bar"))
    mu1 = _pos("μ₁", inputs.get("mu1"))
    mu2 = _pos("μ₂", inputs.get("mu2"))
    if n == 0:
        return 0.0
    if n == 1:
        return mu_bar
    return mu1 + mu2


def pn_formula(inputs: dict[str, Any]) -> float:
    n = _nn_int("n", inputs.get("n"))
    M = _pos_int("M", inputs.get("M"))
    lam = _pos("λ", inputs.get("lambda_"))
    mu1 = _pos("μ₁", inputs.get("mu1"))
    mu2 = _pos("μ₂", inputs.get("mu2"))
    if n > M:
        raise ValueError("n no puede ser mayor que M.")
    probs = _compute_all_pn(M, lam, mu1, mu2)
    return probs[n]


def p0_formula(inputs: dict[str, Any]) -> float:
    M = _pos_int("M", inputs.get("M"))
    lam = _pos("λ", inputs.get("lambda_"))
    mu1 = _pos("μ₁", inputs.get("mu1"))
    mu2 = _pos("μ₂", inputs.get("mu2"))
    return _compute_p0(M, lam, mu1, mu2)


def prob_no_wait_formula(inputs: dict[str, Any]) -> float:
    M = _pos_int("M", inputs.get("M"))
    k = _pos_int("k", inputs.get("k"))
    lam = _pos("λ", inputs.get("lambda_"))
    mu1 = _pos("μ₁", inputs.get("mu1"))
    mu2 = _pos("μ₂", inputs.get("mu2"))
    if k > M:
        raise ValueError("k no puede ser mayor que M.")
    probs = _compute_all_pn(M, lam, mu1, mu2)
    num = sum((M - i) * probs[i] for i in range(min(k, M + 1)))
    den = sum((M - i) * probs[i] for i in range(M))
    if den <= 0:
        raise ValueError("Denominador de la probabilidad de no espera es cero.")
    return num / den


def prob_n_ge_2_formula(inputs: dict[str, Any]) -> float:
    p0 = _prob("P₀", inputs.get("P0"))
    p1 = _prob("P₁", inputs.get("P1"))
    if p0 + p1 > 1.0 + 1e-9:
        raise ValueError("P₀ + P₁ no puede exceder 1.")
    return max(0.0, 1.0 - (p0 + p1))


def prob_available_formula(inputs: dict[str, Any]) -> float:
    p0 = _prob("P₀", inputs.get("P0"))
    p1 = _prob("P₁", inputs.get("P1"))
    if p0 + p1 > 1.0 + 1e-9:
        raise ValueError("P₀ + P₁ no puede exceder 1.")
    return p0 + p1


def operating_units_formula(inputs: dict[str, Any]) -> float:
    M = _pos_int("M", inputs.get("M"))
    L = _non_neg("L", inputs.get("L"))
    if L > M:
        raise ValueError("L no puede ser mayor que M.")
    return M - L


def effective_arrival_formula(inputs: dict[str, Any]) -> float:
    lam = _pos("λ", inputs.get("lambda_"))
    M = _pos_int("M", inputs.get("M"))
    L = _non_neg("L", inputs.get("L"))
    if L > M:
        raise ValueError("L no puede ser mayor que M.")
    return lam * (M - L)


def percent_outside_formula(inputs: dict[str, Any]) -> float:
    M = _pos_int("M", inputs.get("M"))
    L = _non_neg("L", inputs.get("L"))
    if L > M:
        raise ValueError("L no puede ser mayor que M.")
    return (M - L) / M * 100.0


# ── FormulaDefinition list ──────────────────────────────────────────

PFHET_FORMULAS: list[FormulaDefinition] = [
    FormulaDefinition(
        id="pfhet_mu_bar",
        name="Tasa media de servicio heterogéneo",
        category=FormulaCategory.PFHET,
        description="Promedio de las tasas de servicio de dos servidores heterogéneos. μ̄ = (μ₁ + μ₂)/2.",
        result_variable="mu_bar",
        input_variables=["mu1", "mu2"],
        formula_type=FormulaType.DIRECT,
        priority=25,
        premium_mode=False,
        manual_calculation=mu_bar_formula,
        symbolic_expression="μ̄ = (μ₁ + μ₂) / 2",
        constraints={"mu1_positive": True, "mu2_positive": True},
    ),
    FormulaDefinition(
        id="pfhet_lambda_n",
        name="Tasa de nacimiento por estado",
        category=FormulaCategory.PFHET,
        description="Tasa de llegada dependiente del estado n en población finita. λₙ = (M − n)·λ.",
        result_variable="Pn",
        input_variables=["M", "n", "lambda_"],
        formula_type=FormulaType.DIRECT,
        priority=24,
        premium_mode=False,
        manual_calculation=lambda_n_formula,
        symbolic_expression="λ_n = (M − n)·λ",
        constraints={"M_positive_integer": True, "n_non_negative": True, "lambda_positive": True},
    ),
    FormulaDefinition(
        id="pfhet_mu_n",
        name="Tasa de muerte por estado (heterogénea)",
        category=FormulaCategory.PFHET,
        description="Tasa de servicio por estado: 0 si n=0, μ̄ si n=1, μ₁+μ₂ si n≥2.",
        result_variable="Pn",
        input_variables=["n", "mu_bar", "mu1", "mu2"],
        formula_type=FormulaType.DIRECT,
        priority=24,
        premium_mode=False,
        manual_calculation=mu_n_formula,
        symbolic_expression="μ_n: 0 (n=0), μ̄ (n=1), μ₁+μ₂ (n≥2)",
        constraints={"n_non_negative": True, "mu_bar_positive": True, "mu1_positive": True, "mu2_positive": True},
    ),
    FormulaDefinition(
        id="pfhet_pn",
        name="Probabilidad de estado n (heterogéneo)",
        category=FormulaCategory.PFHET,
        description="P_n del modelo de nacimiento-muerte con servidores heterogéneos y población finita.",
        result_variable="Pn",
        input_variables=["n", "M", "lambda_", "mu1", "mu2"],
        formula_type=FormulaType.COMPOSITE,
        priority=20,
        premium_mode=False,
        manual_calculation=pn_formula,
        symbolic_expression=r"P_n = P_0 \prod_{i=0}^{n-1}\frac{\lambda_i}{\mu_{i+1}}",
        constraints={"n_non_negative": True, "M_positive_integer": True, "lambda_positive": True, "mu1_positive": True, "mu2_positive": True},
    ),
    FormulaDefinition(
        id="pfhet_p0",
        name="Probabilidad de sistema vacío (heterogéneo)",
        category=FormulaCategory.PFHET,
        description="Constante de normalización P₀ del modelo de nacimiento-muerte heterogéneo.",
        result_variable="P0",
        input_variables=["M", "lambda_", "mu1", "mu2"],
        formula_type=FormulaType.COMPOSITE,
        priority=22,
        premium_mode=False,
        manual_calculation=p0_formula,
        symbolic_expression=r"P_0 = \left[1 + \sum_{n=1}^{M}\prod_{i=0}^{n-1}\frac{\lambda_i}{\mu_{i+1}}\right]^{-1}",
        constraints={"M_positive_integer": True, "lambda_positive": True, "mu1_positive": True, "mu2_positive": True},
    ),
    FormulaDefinition(
        id="pfhet_prob_no_wait",
        name="Probabilidad de no espera (heterogéneo)",
        category=FormulaCategory.PFHET,
        description="Probabilidad de que un cliente no espere al llegar al sistema heterogéneo.",
        result_variable="PNE",
        input_variables=["M", "k", "lambda_", "mu1", "mu2"],
        formula_type=FormulaType.COMPOSITE,
        priority=18,
        premium_mode=False,
        manual_calculation=prob_no_wait_formula,
        symbolic_expression=r"P(\text{no espera}) = \frac{\sum_{n=0}^{k-1}(M-n)P_n}{\sum_{n=0}^{M-1}(M-n)P_n}",
        constraints={"M_positive_integer": True, "k_positive_integer": True, "lambda_positive": True, "mu1_positive": True, "mu2_positive": True},
    ),
    FormulaDefinition(
        id="pfhet_prob_n_ge_2",
        name="Probabilidad de al menos 2 clientes en sistema",
        category=FormulaCategory.PFHET,
        description="P(N ≥ 2) = 1 − (P₀ + P₁). Ambos servidores heterogéneos ocupados.",
        result_variable="Pn",
        input_variables=["P0", "P1"],
        formula_type=FormulaType.DIRECT,
        priority=16,
        premium_mode=False,
        manual_calculation=prob_n_ge_2_formula,
        symbolic_expression="P(N \\ge 2) = 1 - (P_0 + P_1)",
        constraints={"P0_probability": True, "P1_probability": True},
    ),
    FormulaDefinition(
        id="pfhet_prob_available",
        name="Probabilidad de servidor disponible",
        category=FormulaCategory.PFHET,
        description="Probabilidad de que al menos un servidor esté libre. P(disp) = P₀ + P₁.",
        result_variable="PNE",
        input_variables=["P0", "P1"],
        formula_type=FormulaType.DIRECT,
        priority=16,
        premium_mode=False,
        manual_calculation=prob_available_formula,
        symbolic_expression="P(\\text{disponible}) = P_0 + P_1",
        constraints={"P0_probability": True, "P1_probability": True},
    ),
    FormulaDefinition(
        id="pfhet_operating_units",
        name="Unidades operando fuera del taller",
        category=FormulaCategory.PFHET,
        description="Número promedio de unidades funcionando fuera del sistema. Operando = M − L.",
        result_variable="L",
        input_variables=["M", "L"],
        formula_type=FormulaType.DIRECT,
        priority=14,
        premium_mode=False,
        manual_calculation=operating_units_formula,
        symbolic_expression="\\text{Operando} = M - L",
        constraints={"M_positive_integer": True, "L_non_negative": True},
    ),
    FormulaDefinition(
        id="pfhet_effective_arrival",
        name="Tasa efectiva de llegada (pob. finita)",
        category=FormulaCategory.PFHET,
        description="Tasa efectiva de llegada en población finita. λ_ef = λ·(M − L).",
        result_variable="Lq",
        input_variables=["lambda_", "M", "L"],
        formula_type=FormulaType.DIRECT,
        priority=14,
        premium_mode=False,
        manual_calculation=effective_arrival_formula,
        symbolic_expression="\\lambda_{ef} = \\lambda \\cdot (M - L)",
        constraints={"lambda_positive": True, "M_positive_integer": True, "L_non_negative": True},
    ),
    FormulaDefinition(
        id="pfhet_percent_outside",
        name="Porcentaje de unidades fuera del sistema",
        category=FormulaCategory.PFHET,
        description="Porcentaje del tiempo que las unidades están operando fuera del taller.",
        result_variable="Pn",
        input_variables=["M", "L"],
        formula_type=FormulaType.DIRECT,
        priority=12,
        premium_mode=False,
        manual_calculation=percent_outside_formula,
        symbolic_expression="\\% = \\frac{M - L}{M} \\times 100",
        constraints={"M_positive_integer": True, "L_non_negative": True},
    ),
]

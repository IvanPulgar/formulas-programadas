from __future__ import annotations

from math import factorial
from typing import Any

from domain.entities import FormulaCategory, FormulaDefinition, FormulaType
from domain.rules import positive, positive_integer


def validate_positive_number(name: str, value: Any) -> float:
    if not positive(value):
        raise ValueError(f"{name} debe ser un número positivo.")
    return float(value)


def validate_non_negative_integer(name: str, value: Any) -> int:
    if not positive_integer(value) and not (isinstance(value, int) and value == 0):
        raise ValueError(f"{name} debe ser un entero no negativo.")
    return int(value)


def validate_positive_integer(name: str, value: Any) -> int:
    if not positive_integer(value):
        raise ValueError(f"{name} debe ser un entero positivo.")
    return int(value)


def stability_ratio(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    mu = validate_positive_number("μ", inputs.get("mu"))
    k = validate_positive_integer("k", inputs.get("k"))
    return lambda_ / (k * mu)


def arrival_service_ratio(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    mu = validate_positive_number("μ", inputs.get("mu"))
    return lambda_ / mu


def is_stable(inputs: dict[str, Any]) -> bool:
    return stability_ratio(inputs) < 1.0


def p0_formula(inputs: dict[str, Any]) -> float:
    if not is_stable(inputs):
        raise ValueError("El sistema no es estable: λ/(k·μ) debe ser menor que 1.")

    a = arrival_service_ratio(inputs)
    k = validate_positive_integer("k", inputs.get("k"))
    rho = stability_ratio(inputs)

    numerator = sum(a**n / factorial(n) for n in range(0, k))
    denominator = a**k / factorial(k) * (1.0 / (1.0 - rho))
    return 1.0 / (numerator + denominator)


def pk_formula(inputs: dict[str, Any]) -> float:
    p0 = p0_formula(inputs)
    a = arrival_service_ratio(inputs)
    k = validate_positive_integer("k", inputs.get("k"))
    rho = stability_ratio(inputs)
    if rho >= 1.0:
        raise ValueError("El sistema no es estable: λ/(k·μ) debe ser menor que 1 para P(esperar).")
    return p0 * a**k / factorial(k) * (1.0 / (1.0 - rho))


def pne_formula(inputs: dict[str, Any]) -> float:
    pk = pk_formula(inputs)
    return 1.0 - pk


def pn_without_queue_formula(inputs: dict[str, Any]) -> float:
    p0 = p0_formula(inputs)
    a = arrival_service_ratio(inputs)
    n = validate_non_negative_integer("n", inputs.get("n"))
    k = validate_positive_integer("k", inputs.get("k"))
    if n >= k:
        raise ValueError("Pn sin cola sólo aplica para n < k.")
    return p0 * a**n / factorial(n)


def pn_with_queue_formula(inputs: dict[str, Any]) -> float:
    p0 = p0_formula(inputs)
    a = arrival_service_ratio(inputs)
    n = validate_non_negative_integer("n", inputs.get("n"))
    k = validate_positive_integer("k", inputs.get("k"))
    if n < k:
        raise ValueError("Pn con cola sólo aplica para n >= k.")
    return p0 * a**n / (factorial(k) * k**(n - k))


def lq_formula(inputs: dict[str, Any]) -> float:
    p0 = p0_formula(inputs)
    a = arrival_service_ratio(inputs)
    rho = stability_ratio(inputs)
    k = validate_positive_integer("k", inputs.get("k"))
    if rho >= 1.0:
        raise ValueError("El sistema no es estable: λ/(k·μ) debe ser menor que 1 para Lq.")
    return p0 * a**k * rho / (factorial(k) * (1.0 - rho) ** 2)


def l_formula(inputs: dict[str, Any]) -> float:
    a = arrival_service_ratio(inputs)
    return a + lq_formula(inputs)


def wq_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    return lq_formula(inputs) / lambda_



def w_formula(inputs: dict[str, Any]) -> float:
    mu = validate_positive_number("μ", inputs.get("mu"))
    return wq_formula(inputs) + 1.0 / mu



def ln_formula(inputs: dict[str, Any]) -> float:
    pk = pk_formula(inputs)
    if pk == 0:
        raise ValueError("Pk no puede ser cero para Ln en PICM.")
    return lq_formula(inputs) / pk



def wn_formula(inputs: dict[str, Any]) -> float:
    pk = pk_formula(inputs)
    if pk == 0:
        raise ValueError("Pk no puede ser cero para Wn en PICM.")
    return wq_formula(inputs) / pk



def ct_te_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    wq = validate_positive_number("Wq", inputs.get("Wq"))
    cte = validate_positive_number("CTE", inputs.get("CTE"))
    return lambda_ * 8.0 * wq * cte



def ct_ts_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    w = validate_positive_number("W", inputs.get("W"))
    cts = validate_positive_number("CTS", inputs.get("CTS"))
    return lambda_ * 8.0 * w * cts



def ct_tse_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    mu = validate_positive_number("μ", inputs.get("mu"))
    ctse = validate_positive_number("CTSE", inputs.get("CTSE"))
    return lambda_ * 8.0 * (1.0 / mu) * ctse



def ct_s_formula(inputs: dict[str, Any]) -> float:
    k = validate_positive_integer("k", inputs.get("k"))
    cs = validate_positive_number("CS", inputs.get("CS"))
    return k * cs



def ct_formula(inputs: dict[str, Any]) -> float:
    ct_te = validate_positive_number("CT_TE", inputs.get("CT_TE"))
    ct_ts = validate_positive_number("CT_TS", inputs.get("CT_TS"))
    ct_tse = validate_positive_number("CT_TSE", inputs.get("CT_TSE"))
    ct_s = validate_positive_number("CT_S", inputs.get("CT_S"))
    return ct_te + ct_ts + ct_tse + ct_s



def tt_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    wq = validate_positive_number("Wq", inputs.get("Wq"))
    return lambda_ * 8.0 * 0.30 * wq


def ct_simplified_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    w = validate_positive_number("W", inputs.get("W"))
    cts = validate_positive_number("CTS", inputs.get("CTS"))
    k = validate_positive_integer("k", inputs.get("k"))
    cs = validate_positive_number("CS", inputs.get("CS"))
    return lambda_ * 8.0 * w * cts + k * cs


def tt_alt_formula(inputs: dict[str, Any]) -> float:
    lambda_ = validate_positive_number("λ", inputs.get("lambda_"))
    pk = validate_positive_number("Pk", inputs.get("Pk"))
    wn = validate_positive_number("Wn", inputs.get("Wn"))
    return lambda_ * 8.0 * 0.30 * pk * wn


def qualifies_for_pne(inputs: dict[str, Any], threshold: float = 0.85) -> bool:
    return pne_formula(inputs) >= threshold



def qualifies_for_service_time(inputs: dict[str, Any], threshold: float = 0.20) -> bool:
    return w_formula(inputs) <= threshold


# ── B-group: flexible derived probabilities ─────────────────────────

def _validate_probability(name: str, value: Any) -> float:
    if value is None:
        raise ValueError(f"{name} es obligatorio.")
    v = float(value)
    if v < 0 or v > 1:
        raise ValueError(f"{name} debe estar entre 0 y 1.")
    return v


def _validate_rho_strict(value: Any) -> float:
    if value is None:
        raise ValueError("ρ es obligatorio.")
    v = float(value)
    if v <= 0 or v >= 1:
        raise ValueError("ρ debe estar estrictamente entre 0 y 1.")
    return v


def prob_idle_formula(inputs: dict[str, Any]) -> float:
    pk = _validate_probability("P(esperar)", inputs.get("Pk"))
    return 1.0 - pk


def prob_exactly_c_formula(inputs: dict[str, Any]) -> float:
    a = inputs.get("a")
    if a is None:
        raise ValueError("a (intensidad) es obligatorio.")
    a = float(a)
    if a < 0:
        raise ValueError("a debe ser ≥ 0.")
    c = validate_positive_integer("c", inputs.get("k"))
    p0 = _validate_probability("P0", inputs.get("P0"))
    return (a ** c / factorial(c)) * p0


def prob_c_plus_r_formula(inputs: dict[str, Any]) -> float:
    pc = _validate_probability("Pc", inputs.get("Pc"))
    rho = _validate_rho_strict(inputs.get("rho"))
    r = validate_non_negative_integer("r", inputs.get("r"))
    return pc * rho ** r


def prob_c_plus_1_formula(inputs: dict[str, Any]) -> float:
    pc = _validate_probability("Pc", inputs.get("Pc"))
    rho = _validate_rho_strict(inputs.get("rho"))
    return pc * rho


def prob_c_plus_2_formula(inputs: dict[str, Any]) -> float:
    pc = _validate_probability("Pc", inputs.get("Pc"))
    rho = _validate_rho_strict(inputs.get("rho"))
    return pc * rho ** 2


def prob_q_waiting_formula(inputs: dict[str, Any]) -> float:
    pc = _validate_probability("Pc", inputs.get("Pc"))
    rho = _validate_rho_strict(inputs.get("rho"))
    q = validate_non_negative_integer("q", inputs.get("q"))
    return pc * rho ** q


def prob_q1_or_q2_waiting_formula(inputs: dict[str, Any]) -> float:
    pc = _validate_probability("Pc", inputs.get("Pc"))
    rho = _validate_rho_strict(inputs.get("rho"))
    q1 = validate_non_negative_integer("q1", inputs.get("q1"))
    q2 = validate_non_negative_integer("q2", inputs.get("q2"))
    return pc * rho ** q1 + pc * rho ** q2


PICM_FORMULAS: list[FormulaDefinition] = [
    FormulaDefinition(
        id="picm_stability",
        name="Condición de estabilidad",
        category=FormulaCategory.PICM,
        description="Verifica que la tasa de llegada no supere la capacidad de servicio total.",
        result_variable="rho",
        input_variables=["lambda_", "mu", "k"],
        formula_type=FormulaType.VALIDATION,
        priority=30,
        premium_mode=False,
        manual_calculation=stability_ratio,
        symbolic_expression="λ / (k·μ)",
        constraints={"lambda_positive": True, "mu_positive": True, "k_positive_integer": True},
    ),
    FormulaDefinition(
        id="picm_p0",
        name="Probabilidad de estado cero",
        category=FormulaCategory.PICM,
        description="Probabilidad de que no haya clientes en el sistema en el modelo PICM.",
        result_variable="P0",
        input_variables=["lambda_", "mu", "k"],
        formula_type=FormulaType.SYMBOLIC,
        priority=25,
        premium_mode=False,
        manual_calculation=p0_formula,
        symbolic_expression="[Σ_{n=0}^{k-1} a^n/n! + a^k/(k!·(1-ρ))]^{-1}",
        constraints={"lambda_positive": True, "mu_positive": True, "k_positive_integer": True},
    ),
    FormulaDefinition(
        id="picm_pk",
        name="Probabilidad de esperar (Erlang C)",
        category=FormulaCategory.PICM,
        description="Probabilidad de que una llegada deba esperar en el modelo M/M/c (Erlang C).",
        result_variable="Pk",
        input_variables=["lambda_", "mu", "k"],
        formula_type=FormulaType.DIRECT,
        priority=20,
        premium_mode=False,
        manual_calculation=pk_formula,
        symbolic_expression="P(esperar) = P0 · a^k/k! · 1/(1-ρ)",
        constraints={"lambda_positive": True, "mu_positive": True, "k_positive_integer": True},
    ),
    FormulaDefinition(
        id="picm_pne",
        name="Probabilidad de no existencia",
        category=FormulaCategory.PICM,
        description="Probabilidad complementaria a Pk en el sistema PICM.",
        result_variable="PNE",
        input_variables=["lambda_", "mu", "k"],
        formula_type=FormulaType.DIRECT,
        priority=20,
        premium_mode=False,
        manual_calculation=pne_formula,
        symbolic_expression="1 - Pk",
        constraints={"lambda_positive": True, "mu_positive": True, "k_positive_integer": True},
    ),
    FormulaDefinition(
        id="picm_pn_without_queue",
        name="Probabilidad de n clientes sin cola",
        category=FormulaCategory.PICM,
        description="Probabilidad de estado n en el sistema básico antes de que exista cola.",
        result_variable="Pn",
        input_variables=["lambda_", "mu", "k", "n"],
        formula_type=FormulaType.DIRECT,
        priority=18,
        premium_mode=False,
        manual_calculation=pn_without_queue_formula,
        symbolic_expression="P0 · a^n / n!",
        constraints={
            "lambda_positive": True,
            "mu_positive": True,
            "k_positive_integer": True,
            "n_non_negative_integer": True,
        },
    ),
    FormulaDefinition(
        id="picm_pn_with_queue",
        name="Probabilidad de n clientes con cola",
        category=FormulaCategory.PICM,
        description="Probabilidad de estado n donde hay cola en el sistema.",
        result_variable="Pn",
        input_variables=["lambda_", "mu", "k", "n"],
        formula_type=FormulaType.DIRECT,
        priority=18,
        premium_mode=False,
        manual_calculation=pn_with_queue_formula,
        symbolic_expression="P0 · a^n / (k!·k^{n-k})",
        constraints={
            "lambda_positive": True,
            "mu_positive": True,
            "k_positive_integer": True,
            "n_non_negative_integer": True,
        },
    ),
    FormulaDefinition(
        id="picm_lq",
        name="Clientes promedio en cola",
        category=FormulaCategory.PICM,
        description="Número promedio de clientes en la cola del modelo PICM.",
        result_variable="Lq",
        input_variables=["lambda_", "mu", "k"],
        formula_type=FormulaType.SYMBOLIC,
        priority=18,
        premium_mode=False,
        manual_calculation=lq_formula,
        symbolic_expression="P0 · a^k · ρ / (k!·(1-ρ)^2)",
        constraints={"lambda_positive": True, "mu_positive": True, "k_positive_integer": True},
    ),
    FormulaDefinition(
        id="picm_l",
        name="Clientes promedio en el sistema",
        category=FormulaCategory.PICM,
        description="Número promedio total de clientes en el sistema del modelo PICM.",
        result_variable="L",
        input_variables=["lambda_", "mu", "k"],
        formula_type=FormulaType.COMPOSITE,
        priority=16,
        premium_mode=False,
        manual_calculation=l_formula,
        symbolic_expression="a + Lq",
        constraints={"lambda_positive": True, "mu_positive": True, "k_positive_integer": True},
    ),
    FormulaDefinition(
        id="picm_wq",
        name="Tiempo promedio de espera en cola",
        category=FormulaCategory.PICM,
        description="Tiempo promedio que un cliente espera antes del servicio.",
        result_variable="Wq",
        input_variables=["lambda_", "mu", "k"],
        formula_type=FormulaType.SYMBOLIC,
        priority=16,
        premium_mode=False,
        manual_calculation=wq_formula,
        symbolic_expression="Lq / λ",
        constraints={"lambda_positive": True, "mu_positive": True, "k_positive_integer": True},
    ),
    FormulaDefinition(
        id="picm_w",
        name="Tiempo promedio en el sistema",
        category=FormulaCategory.PICM,
        description="Tiempo promedio total que un cliente pasa en el sistema.",
        result_variable="W",
        input_variables=["lambda_", "mu", "k"],
        formula_type=FormulaType.COMPOSITE,
        priority=14,
        premium_mode=False,
        manual_calculation=w_formula,
        symbolic_expression="Wq + 1/μ",
        constraints={"lambda_positive": True, "mu_positive": True, "k_positive_integer": True},
    ),
    FormulaDefinition(
        id="picm_ln",
        name="Clientes en función de Pk",
        category=FormulaCategory.PICM,
        description="Estimación de clientes en el sistema basada en Lq y Pk.",
        result_variable="Ln",
        input_variables=["lambda_", "mu", "k"],
        formula_type=FormulaType.COMPOSITE,
        priority=12,
        premium_mode=False,
        manual_calculation=ln_formula,
        symbolic_expression="Lq / Pk",
        constraints={"lambda_positive": True, "mu_positive": True, "k_positive_integer": True},
    ),
    FormulaDefinition(
        id="picm_wn",
        name="Tiempo condicional Wn",
        category=FormulaCategory.PICM,
        description="Tiempo de espera ajustado según Pk.",
        result_variable="Wn",
        input_variables=["lambda_", "mu", "k"],
        formula_type=FormulaType.COMPOSITE,
        priority=12,
        premium_mode=False,
        manual_calculation=wn_formula,
        symbolic_expression="Wq / Pk",
        constraints={"lambda_positive": True, "mu_positive": True, "k_positive_integer": True},
    ),
    FormulaDefinition(
        id="picm_ct_te",
        name="Costo total de tiempo de espera",
        category=FormulaCategory.PICM,
        description="Costo total asociado al tiempo de espera.",
        result_variable="CT_TE",
        input_variables=["lambda_", "Wq", "CTE"],
        formula_type=FormulaType.DIRECT,
        priority=10,
        premium_mode=False,
        manual_calculation=ct_te_formula,
        symbolic_expression="λ · 8 · Wq · CTE",
        constraints={"lambda_positive": True, "Wq_non_negative": True, "CTE_non_negative": True},
    ),
    FormulaDefinition(
        id="picm_ct_ts",
        name="Costo total por tiempo de servicio",
        category=FormulaCategory.PICM,
        description="Costo total asociado al tiempo de servicio.",
        result_variable="CT_TS",
        input_variables=["lambda_", "W", "CTS"],
        formula_type=FormulaType.DIRECT,
        priority=10,
        premium_mode=False,
        manual_calculation=ct_ts_formula,
        symbolic_expression="λ · 8 · W · CTS",
        constraints={"lambda_positive": True, "W_non_negative": True, "CTS_non_negative": True},
    ),
    FormulaDefinition(
        id="picm_ct_tse",
        name="Costo total de tiempo de servicio y espera",
        category=FormulaCategory.PICM,
        description="Costo total asociado al tiempo combinado de servicio y espera.",
        result_variable="CT_TSE",
        input_variables=["lambda_", "mu", "CTSE"],
        formula_type=FormulaType.DIRECT,
        priority=10,
        premium_mode=False,
        manual_calculation=ct_tse_formula,
        symbolic_expression="λ · 8 · (1/μ) · CTSE",
        constraints={"lambda_positive": True, "mu_positive": True, "CTSE_non_negative": True},
    ),
    FormulaDefinition(
        id="picm_ct_s",
        name="Costo total de servicio",
        category=FormulaCategory.PICM,
        description="Costo total de servicio de todos los servidores.",
        result_variable="CT_S",
        input_variables=["k", "CS"],
        formula_type=FormulaType.DIRECT,
        priority=8,
        premium_mode=False,
        manual_calculation=ct_s_formula,
        symbolic_expression="k · CS",
        constraints={"k_positive_integer": True, "CS_non_negative": True},
    ),
    FormulaDefinition(
        id="picm_ct",
        name="Costo total",
        category=FormulaCategory.PICM,
        description="Costo total combinado del sistema PICM.",
        result_variable="CT",
        input_variables=["CT_TE", "CT_TS", "CT_TSE", "CT_S"],
        formula_type=FormulaType.COMPOSITE,
        priority=8,
        premium_mode=False,
        manual_calculation=ct_formula,
        symbolic_expression="CT_TE + CT_TS + CT_TSE + CT_S",
        constraints={
            "CT_TE_non_negative": True,
            "CT_TS_non_negative": True,
            "CT_TSE_non_negative": True,
            "CT_S_non_negative": True,
        },
    ),
    FormulaDefinition(
        id="picm_tt",
        name="Tiempo total de operación",
        category=FormulaCategory.PICM,
        description="Tiempo total asociado a la operación en función de Wq.",
        result_variable="TT",
        input_variables=["lambda_", "Wq"],
        formula_type=FormulaType.DIRECT,
        priority=6,
        premium_mode=False,
        manual_calculation=tt_formula,
        symbolic_expression="λ · 8 · 0.30 · Wq",
        constraints={"lambda_positive": True, "Wq_non_negative": True},
    ),
    # ── B-group: flexible derived probabilities ─────────────────
    FormulaDefinition(
        id="picm_prob_idle",
        name="Probabilidad de al menos un servidor desocupado",
        category=FormulaCategory.PICM,
        description="Complemento de P(esperar). P(≥1 desocupado) = 1 − Pk.",
        result_variable="PNE",
        input_variables=["Pk"],
        formula_type=FormulaType.DIRECT,
        priority=15,
        premium_mode=False,
        manual_calculation=prob_idle_formula,
        symbolic_expression="1 − Pk",
        constraints={"Pk_probability": True},
    ),
    FormulaDefinition(
        id="picm_prob_exactly_c",
        name="Probabilidad de exactamente c clientes",
        category=FormulaCategory.PICM,
        description="Probabilidad de que haya exactamente c clientes en el sistema. Pc = (a^c / c!) P0.",
        result_variable="Pc",
        input_variables=["a", "k", "P0"],
        formula_type=FormulaType.DIRECT,
        priority=15,
        premium_mode=False,
        manual_calculation=prob_exactly_c_formula,
        symbolic_expression="(a^c / c!) P0",
        constraints={"a_non_negative": True, "k_positive_integer": True, "P0_probability": True},
    ),
    FormulaDefinition(
        id="picm_prob_c_plus_r",
        name="Probabilidad de exactamente c+r clientes",
        category=FormulaCategory.PICM,
        description="Probabilidad flexible: P_{c+r} = Pc · ρ^r. Generaliza todos los casos P_{c+1}, P_{c+2}, etc.",
        result_variable="Pn",
        input_variables=["Pc", "rho", "r"],
        formula_type=FormulaType.DIRECT,
        priority=15,
        premium_mode=False,
        manual_calculation=prob_c_plus_r_formula,
        symbolic_expression="Pc · ρ^r",
        constraints={"Pc_probability": True, "rho_strict_0_1": True, "r_non_negative": True},
    ),
    FormulaDefinition(
        id="picm_prob_c_plus_1",
        name="Probabilidad de exactamente c+1 clientes",
        category=FormulaCategory.PICM,
        description="Caso particular: P_{c+1} = Pc · ρ.",
        result_variable="Pn",
        input_variables=["Pc", "rho"],
        formula_type=FormulaType.DIRECT,
        priority=12,
        premium_mode=False,
        manual_calculation=prob_c_plus_1_formula,
        symbolic_expression="Pc · ρ",
        constraints={"Pc_probability": True, "rho_strict_0_1": True},
    ),
    FormulaDefinition(
        id="picm_prob_c_plus_2",
        name="Probabilidad de exactamente c+2 clientes",
        category=FormulaCategory.PICM,
        description="Caso particular: P_{c+2} = Pc · ρ².",
        result_variable="Pn",
        input_variables=["Pc", "rho"],
        formula_type=FormulaType.DIRECT,
        priority=12,
        premium_mode=False,
        manual_calculation=prob_c_plus_2_formula,
        symbolic_expression="Pc · ρ²",
        constraints={"Pc_probability": True, "rho_strict_0_1": True},
    ),
    FormulaDefinition(
        id="picm_prob_q_waiting",
        name="Probabilidad de exactamente q clientes esperando",
        category=FormulaCategory.PICM,
        description="P(Q = q) = Pc · ρ^q. Número exacto de clientes en cola.",
        result_variable="Pn",
        input_variables=["Pc", "rho", "q"],
        formula_type=FormulaType.DIRECT,
        priority=15,
        premium_mode=False,
        manual_calculation=prob_q_waiting_formula,
        symbolic_expression="Pc · ρ^q",
        constraints={"Pc_probability": True, "rho_strict_0_1": True, "q_non_negative": True},
    ),
    FormulaDefinition(
        id="picm_prob_q1_or_q2",
        name="Probabilidad de q₁ o q₂ clientes esperando",
        category=FormulaCategory.PICM,
        description="P(Q = q₁ o q₂) = Pc·ρ^q₁ + Pc·ρ^q₂. Suma de dos probabilidades de cola.",
        result_variable="Pn",
        input_variables=["Pc", "rho", "q1", "q2"],
        formula_type=FormulaType.DIRECT,
        priority=15,
        premium_mode=False,
        manual_calculation=prob_q1_or_q2_waiting_formula,
        symbolic_expression="Pc·ρ^{q₁} + Pc·ρ^{q₂}",
        constraints={"Pc_probability": True, "rho_strict_0_1": True, "q1_non_negative": True, "q2_non_negative": True},
    ),
    FormulaDefinition(
        id="picm_ct_simplified",
        name="Costo total simplificado",
        category=FormulaCategory.PICM,
        description="Versión reducida del costo total para comparar alternativas de servidores.",
        result_variable="CT",
        input_variables=["lambda_", "W", "CTS", "k", "CS"],
        formula_type=FormulaType.DIRECT,
        priority=6,
        premium_mode=False,
        manual_calculation=ct_simplified_formula,
        symbolic_expression="λ · 8 · W · CTS + k · CS",
        constraints={"lambda_positive": True, "W_non_negative": True, "CTS_non_negative": True, "k_positive_integer": True, "CS_non_negative": True},
    ),
    FormulaDefinition(
        id="picm_tt_alt",
        name="Tiempo total diario (usando Pk y Wn)",
        category=FormulaCategory.PICM,
        description="Expresión alternativa del tiempo total diario usando probabilidad de esperar y espera condicionada.",
        result_variable="TT",
        input_variables=["lambda_", "Pk", "Wn"],
        formula_type=FormulaType.DIRECT,
        priority=5,
        premium_mode=False,
        manual_calculation=tt_alt_formula,
        symbolic_expression="λ · 8 · 0.30 · Pk · Wn",
        constraints={"lambda_positive": True, "Pk_probability": True, "Wn_non_negative": True},
    ),
]

"""
FormulaPlanBuilder — Phase 11.

Builds a structured, ordered formula plan for each detected literal based on:
  - identified queue model (PICS, PICM, PFCS, PFCM, PFHET)
  - literal's inferred objective
  - variables already extracted from the statement text

Returns a list of FormulaPlanStep objects (one per formula in execution order)
and a list of missing_variables (base variables that cannot be derived from text
or from preceding steps).

Design decisions
----------------
- Pure Python + stdlib; no numerical computation.
- Declarative catalog: one entry per (model, objective) → ordered step list.
- Each step records formula_key, formula_name, formula_expression (symbolic),
  why_needed, required_variables (inputs), produces (output variable id).
- Missing variables computed via forward simulation:
    known = extracted_variables
    for step in plan:
        known += step.produces
        missing += [v for v in step.required_variables if v not in known]
- No hardcoded numeric answers.  Same structure works with any numeric input.
- Completely additive — does not touch any other service or entity.

Catalog coverage
----------------
PICS  : P0, Lq, Wq, W, L, wait_probability, probability_q_at_least_r,
        probability_q_between, probability_queue_nonempty,
        server_available_probability, idle_time, waiting_arrivals
PICM  : P0, Pw/wait_probability, Lq, Wq, W, L, probability_q_between,
        probability_q_at_least_r, server_available_probability
PFCS  : P0, Lq, Wq, W, L, wait_probability, fraction_operating,
        probability_q_between
PFCM  : P0, Lq, Wq, L, probability_q_between, cost (advisory only)
PFHET : P0, L, Lq, units_operating, wait_probability, cost (advisory)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class FormulaPlanStep:
    """A single formula step in an execution plan for one literal."""

    order: int                        # 1-based execution order
    formula_key: str                  # short identifier, e.g. "rho", "Lq", "P0"
    formula_name: str                 # human-readable name (Spanish)
    formula_expression: str           # symbolic / LaTeX-like expression
    why_needed: str                   # reason this step precedes the next
    required_variables: list[str]     # input variable ids (from text or prior steps)
    produces: str                     # output variable id


# ---------------------------------------------------------------------------
# Internal step-definition catalog
# Each entry is a dict that will become a FormulaPlanStep (minus `order`).
# Keys: formula_key, formula_name, formula_expression, why_needed,
#       required_variables, produces.
# ---------------------------------------------------------------------------

# ── PICS / M/M/1 primitive steps ─────────────────────────────────────────

_PICS_RHO = dict(
    formula_key="rho",
    formula_name="Utilización del sistema",
    formula_expression="ρ = λ / μ",
    why_needed="ρ es el parámetro base del modelo M/M/1; todas las fórmulas dependen de él.",
    required_variables=["lambda_", "mu"],
    produces="rho",
)
_PICS_P0 = dict(
    formula_key="P0",
    formula_name="Probabilidad de sistema vacío",
    formula_expression="P₀ = 1 − ρ",
    why_needed="Probabilidad de que no haya ningún cliente en el sistema.",
    required_variables=["rho"],
    produces="P0",
)
_PICS_LQ = dict(
    formula_key="Lq",
    formula_name="Longitud media de la cola",
    formula_expression="Lq = ρ² / (1 − ρ)",
    why_needed="Número promedio de clientes esperando en cola.",
    required_variables=["rho"],
    produces="Lq",
)
_PICS_WQ = dict(
    formula_key="Wq",
    formula_name="Tiempo medio de espera en cola",
    formula_expression="Wq = Lq / λ",
    why_needed="Tiempo que un cliente espera antes de ser atendido (Ley de Little).",
    required_variables=["Lq", "lambda_"],
    produces="Wq",
)
_PICS_W = dict(
    formula_key="W",
    formula_name="Tiempo medio en el sistema",
    formula_expression="W = Wq + 1/μ",
    why_needed="Tiempo total en el sistema = espera en cola + tiempo de servicio.",
    required_variables=["Wq", "mu"],
    produces="W",
)
_PICS_L = dict(
    formula_key="L",
    formula_name="Número medio de clientes en el sistema",
    formula_expression="L = λ · W",
    why_needed="Número total de clientes en el sistema (Ley de Little).",
    required_variables=["lambda_", "W"],
    produces="L",
)
_PICS_PN = dict(
    formula_key="Pn",
    formula_name="Probabilidad de exactamente n clientes",
    formula_expression="Pₙ = (1 − ρ) · ρⁿ",
    why_needed="Distribución de probabilidad del número de clientes en el sistema.",
    required_variables=["rho"],
    produces="Pn",
)
_PICS_P_GE_R = dict(
    formula_key="P_N_ge_m",
    formula_name="Probabilidad de N ≥ m (cola ≥ r implica N ≥ r+1)",
    formula_expression="P(N ≥ m) = ρᵐ",
    why_needed="Para Q ≥ r se requiere N ≥ r+1; probabilidad acumulada geométrica.",
    required_variables=["rho"],
    produces="P_N_ge_m",
)
_PICS_IDLE_TIME = dict(
    formula_key="T_libre",
    formula_name="Tiempo ocioso del servidor por período",
    formula_expression="T_libre = P₀ × T_periodo",
    why_needed="Fracción de tiempo sin clientes multiplicada por duración del período.",
    required_variables=["P0", "T_periodo"],
    produces="T_libre",
)
_PICS_WAIT_ARRIVALS = dict(
    formula_key="arrivals_waiting",
    formula_name="Llegadas que deben esperar por período",
    formula_expression="Llegadas_espera = λ_periodo × ρ",
    why_needed="En M/M/1: la fracción de clientes que espera = ρ.",
    required_variables=["lambda_", "rho"],
    produces="arrivals_waiting",
)

# ── PICM / M/M/c primitive steps ─────────────────────────────────────────

_PICM_A = dict(
    formula_key="a",
    formula_name="Tráfico ofrecido (intensidad de tráfico)",
    formula_expression="a = λ / μ",
    why_needed="a es el parámetro de tráfico del modelo M/M/c; necesario para P₀ y Erlang C.",
    required_variables=["lambda_", "mu"],
    produces="a",
)
_PICM_RHO = dict(
    formula_key="rho",
    formula_name="Utilización por servidor",
    formula_expression="ρ = λ / (c · μ) = a / c",
    why_needed="ρ < 1 garantiza estabilidad; determina comportamiento asintótico de la cola.",
    required_variables=["a", "k"],
    produces="rho",
)
_PICM_P0 = dict(
    formula_key="P0",
    formula_name="Probabilidad de sistema vacío (Erlang C)",
    formula_expression="P₀ = [Σₙ₌₀ᶜ⁻¹ aⁿ/n! + aᶜ/(c!(1−ρ))]⁻¹",
    why_needed="Base para calcular la fórmula de Erlang C y todas las métricas de cola.",
    required_variables=["a", "rho", "k"],
    produces="P0",
)
_PICM_PW = dict(
    formula_key="Pw",
    formula_name="Probabilidad de esperar — Erlang C",
    formula_expression="C(c,a) = Pw = [aᶜ / (c! (1−ρ))] · P₀",
    why_needed="Responde directamente al literal de fracción de clientes que esperan.",
    required_variables=["P0", "a", "rho", "k"],
    produces="Pw",
)
_PICM_LQ = dict(
    formula_key="Lq",
    formula_name="Longitud media de la cola (M/M/c)",
    formula_expression="Lq = Pw · ρ / (1 − ρ)",
    why_needed="Número promedio de clientes esperando en el sistema de colas M/M/c.",
    required_variables=["Pw", "rho"],
    produces="Lq",
)
_PICM_WQ = dict(
    formula_key="Wq",
    formula_name="Tiempo medio de espera en cola (M/M/c)",
    formula_expression="Wq = Lq / λ",
    why_needed="Tiempo promedio en cola por cliente (Ley de Little).",
    required_variables=["Lq", "lambda_"],
    produces="Wq",
)
_PICM_W = dict(
    formula_key="W",
    formula_name="Tiempo medio en el sistema (M/M/c)",
    formula_expression="W = Wq + 1/μ",
    why_needed="Tiempo total = espera en cola + tiempo de servicio.",
    required_variables=["Wq", "mu"],
    produces="W",
)
_PICM_L = dict(
    formula_key="L",
    formula_name="Número medio en el sistema (M/M/c)",
    formula_expression="L = λ · W",
    why_needed="Número total de clientes en el sistema (Ley de Little).",
    required_variables=["lambda_", "W"],
    produces="L",
)
_PICM_PN = dict(
    formula_key="Pn",
    formula_name="Probabilidad de n clientes en sistema (n ≥ c)",
    formula_expression="Pₙ = (aⁿ / (c! · cⁿ⁻ᶜ)) · P₀   para n ≥ c",
    why_needed="Calcula probabilidades específicas de estados del sistema.",
    required_variables=["P0", "a", "k"],
    produces="Pn",
)

# ── PFCS (Finite Population, 1 server) primitive steps ───────────────────

_PFCS_R = dict(
    formula_key="r",
    formula_name="Razón de servicio relativa",
    formula_expression="r = λ / μ",
    why_needed="r es el cociente tasa-llegada/tasa-servicio; parámetro básico del modelo PFCS.",
    required_variables=["lambda_", "mu"],
    produces="r",
)
_PFCS_P0 = dict(
    formula_key="P0",
    formula_name="Probabilidad de sistema vacío (PFCS)",
    formula_expression="P₀ = [Σₙ₌₀ᴹ M!/(M−n)! · rⁿ]⁻¹",
    why_needed="Punto de partida para calcular todas las demás probabilidades en población finita.",
    required_variables=["r", "M"],
    produces="P0",
)
_PFCS_PN = dict(
    formula_key="Pn",
    formula_name="Probabilidad de n unidades en el sistema (PFCS)",
    formula_expression="Pₙ = [M! / (M−n)!] · rⁿ · P₀",
    why_needed="Distribución de probabilidad de estados necesaria para calcular L y Lq.",
    required_variables=["P0", "r", "M"],
    produces="Pn",
)
_PFCS_L = dict(
    formula_key="L",
    formula_name="Número medio de unidades en el sistema (PFCS)",
    formula_expression="L = Σₙ₌₀ᴹ n · Pₙ",
    why_needed="Número esperado de unidades presentes (en cola + en servicio).",
    required_variables=["Pn", "M"],
    produces="L",
)
_PFCS_LQ = dict(
    formula_key="Lq",
    formula_name="Longitud media de la cola (PFCS)",
    formula_expression="Lq = L − (1 − P₀)",
    why_needed="Unidades esperando = total en sistema − unidades en servicio.",
    required_variables=["L", "P0"],
    produces="Lq",
)
_PFCS_LAMBDA_EFF = dict(
    formula_key="lambda_eff",
    formula_name="Tasa efectiva de llegada (PFCS)",
    formula_expression="λₑff = λ · (M − L)",
    why_needed="En población finita la tasa efectiva depende del estado medio del sistema.",
    required_variables=["lambda_", "M", "L"],
    produces="lambda_eff",
)
_PFCS_WQ = dict(
    formula_key="Wq",
    formula_name="Tiempo medio en cola (PFCS)",
    formula_expression="Wq = Lq / λₑff",
    why_needed="Tiempo de espera en cola usando la tasa efectiva de llegada.",
    required_variables=["Lq", "lambda_eff"],
    produces="Wq",
)
_PFCS_W = dict(
    formula_key="W",
    formula_name="Tiempo medio en el sistema (PFCS)",
    formula_expression="W = L / λₑff",
    why_needed="Tiempo total en el sistema usando la tasa efectiva.",
    required_variables=["L", "lambda_eff"],
    produces="W",
)
_PFCS_FRAC_OP = dict(
    formula_key="frac_operating",
    formula_name="Fracción de unidades operando",
    formula_expression="f_op = (M − L) / M",
    why_needed="Proporción de la flota funcionando (no en cola ni en servicio).",
    required_variables=["M", "L"],
    produces="frac_operating",
)

# ── PFCM (Finite Population, k servers) primitive steps ──────────────────

_PFCM_R = dict(
    formula_key="r",
    formula_name="Razón de servicio relativa (PFCM)",
    formula_expression="r = λ / μ",
    why_needed="Parámetro básico del modelo PFCM.",
    required_variables=["lambda_", "mu"],
    produces="r",
)
_PFCM_P0 = dict(
    formula_key="P0",
    formula_name="Probabilidad de sistema vacío (PFCM)",
    formula_expression=(
        "P₀ = [Σₙ₌₀ᵏ (M!/(M−n)!) · rⁿ/n! + Σₙ₌ₖ₊₁ᴹ (M!/(M−n)!) · rⁿ/(k! · kⁿ⁻ᵏ)]⁻¹"
    ),
    why_needed="Base de todas las probabilidades de estado en el modelo de k talleres.",
    required_variables=["r", "M", "k"],
    produces="P0",
)
_PFCM_PN = dict(
    formula_key="Pn",
    formula_name="Probabilidad de n unidades en sistema (PFCM)",
    formula_expression=(
        "Pₙ = (M!/(M−n)!) · rⁿ/n! · P₀   (n ≤ k)\n"
        "Pₙ = (M!/(M−n)!) · rⁿ/(k! · kⁿ⁻ᵏ) · P₀   (n > k)"
    ),
    why_needed="Distribución de probabilidad de estados para calcular métricas de cola.",
    required_variables=["P0", "r", "M", "k"],
    produces="Pn",
)
_PFCM_LQ = dict(
    formula_key="Lq",
    formula_name="Número esperado en cola (PFCM)",
    formula_expression="Lq = Σₙ₌ₖ₊₁ᴹ (n − k) · Pₙ",
    why_needed="Unidades esperando = suma ponderada de estados con cola activa.",
    required_variables=["Pn", "k", "M"],
    produces="Lq",
)
_PFCM_LAMBDA_EFF = dict(
    formula_key="lambda_eff",
    formula_name="Tasa efectiva de llegada (PFCM)",
    formula_expression="λₑff = λ · (M − L)",
    why_needed="Tasa real de llegadas al sistema en estado estacionario.",
    required_variables=["lambda_", "M", "L"],
    produces="lambda_eff",
)
_PFCM_L = dict(
    formula_key="L",
    formula_name="Número medio en el sistema (PFCM)",
    formula_expression="L = Σₙ₌₁ᴹ n · Pₙ",
    why_needed="Total de unidades presentes en el sistema.",
    required_variables=["Pn", "M"],
    produces="L",
)
_PFCM_WQ = dict(
    formula_key="Wq",
    formula_name="Tiempo medio en cola (PFCM)",
    formula_expression="Wq = Lq / λₑff",
    why_needed="Tiempo de espera en cola con tasa efectiva.",
    required_variables=["Lq", "lambda_eff"],
    produces="Wq",
)
_PFCM_FRAC_OP = dict(
    formula_key="frac_operating",
    formula_name="Fracción de unidades operando (PFCM)",
    formula_expression="f_op = (M − L) / M",
    why_needed="Proporción de la flota operando en estado estacionario.",
    required_variables=["M", "L"],
    produces="frac_operating",
)
_PFCM_COST = dict(
    formula_key="cost_total",
    formula_name="Costo total diario (evaluación por k)",
    formula_expression="CT(k) = k · C_taller + Lq · C_averia",
    why_needed="Permite comparar costo total para k = 1, 2, 3, … talleres.",
    required_variables=["Lq", "k", "C_taller", "C_averia"],
    produces="cost_total",
)

# ── PFHET (Finite Population, Heterogeneous servers) primitive steps ─────

_PFHET_LAMBDA_N = dict(
    formula_key="lambda_n",
    formula_name="Tasa de llegada en estado n",
    formula_expression="λₙ = (M − n) · λ",
    why_needed="En población finita, la tasa de llegada depende del número de unidades operando.",
    required_variables=["lambda_", "M"],
    produces="lambda_n",
)
_PFHET_MU_N = dict(
    formula_key="mu_n",
    formula_name="Tasa de servicio en estado n (heterogéneo)",
    formula_expression=(
        "μ₁ = n=1\n"
        "μ₁+μ₂ = n=2\n"
        "μ₁+μ₂ = n=3,4,…,M  (ambos ocupados)"
    ),
    why_needed="Cada técnico tiene tasa distinta; la tasa total depende de cuántos están activos.",
    required_variables=["mu1", "mu2"],
    produces="mu_n",
)
_PFHET_P0 = dict(
    formula_key="P0",
    formula_name="Probabilidad de sistema vacío (PFHET)",
    formula_expression="P₀ = [1 + Σₙ₌₁ᴹ ∏ₖ₌₀ⁿ⁻¹ (λₖ / μₖ₊₁)]⁻¹",
    why_needed="Base del proceso de nacimiento-muerte con tasas heterogéneas.",
    required_variables=["lambda_n", "mu_n", "M"],
    produces="P0",
)
_PFHET_PN = dict(
    formula_key="Pn",
    formula_name="Probabilidad de estado n (nacimiento-muerte PFHET)",
    formula_expression="Pₙ = P₀ · ∏ₖ₌₀ⁿ⁻¹ (λₖ / μₖ₊₁)",
    why_needed="Distribución de probabilidad de estados para calcular métricas.",
    required_variables=["P0", "lambda_n", "mu_n"],
    produces="Pn",
)
_PFHET_L = dict(
    formula_key="L",
    formula_name="Número medio en el sistema (PFHET)",
    formula_expression="L = Σₙ₌₁ᴹ n · Pₙ",
    why_needed="Total de unidades presentes (en cola + en servicio).",
    required_variables=["Pn", "M"],
    produces="L",
)
_PFHET_LQ = dict(
    formula_key="Lq",
    formula_name="Número esperado en cola (PFHET)",
    formula_expression="Lq = L − (1 − P₀ − P₁·𝟙[solo_1_tecnico])",
    why_needed="Unidades en cola = total en sistema − unidades en servicio.",
    required_variables=["L", "P0", "Pn"],
    produces="Lq",
)
_PFHET_UNITS_OP = dict(
    formula_key="units_operating",
    formula_name="Unidades operando en promedio",
    formula_expression="U = M − L",
    why_needed="Montacargas / unidades funcionando en promedio.",
    required_variables=["M", "L"],
    produces="units_operating",
)
_PFHET_LAMBDA_EFF = dict(
    formula_key="lambda_eff",
    formula_name="Tasa efectiva de llegada (PFHET)",
    formula_expression="λₑff = λ · (M − L)",
    why_needed="Tasa real de fallas/llegadas al sistema.",
    required_variables=["lambda_", "M", "L"],
    produces="lambda_eff",
)
_PFHET_COST = dict(
    formula_key="cost_weekly",
    formula_name="Costo semanal estimado (orientativo)",
    formula_expression="CT = C_falla · L + C_tecnico · (número de técnicos)",
    why_needed="Evaluación económica del esquema de mantenimiento.",
    required_variables=["L", "C_falla", "C_tecnico"],
    produces="cost_weekly",
)

# ── Advisory step for unsupported objectives ─────────────────────────────

_ADVISORY_COST = dict(
    formula_key="cost_advisory",
    formula_name="Evaluación de costos (orientativa)",
    formula_expression="CT = C_espera · Lq + C_servidor · k",
    why_needed="El objetivo de costo requiere datos de costo no extraíbles automáticamente.",
    required_variables=["Lq", "k"],
    produces="cost_total",
)


# ---------------------------------------------------------------------------
# Helper: build ordered FormulaPlanStep list from step dicts
# ---------------------------------------------------------------------------

def _build_plan(steps: list[dict]) -> list[FormulaPlanStep]:
    return [
        FormulaPlanStep(
            order=i + 1,
            formula_key=s["formula_key"],
            formula_name=s["formula_name"],
            formula_expression=s["formula_expression"],
            why_needed=s["why_needed"],
            required_variables=list(s["required_variables"]),
            produces=s["produces"],
        )
        for i, s in enumerate(steps)
    ]


# ---------------------------------------------------------------------------
# Master plan catalog: model → objective → [step dicts]
# ---------------------------------------------------------------------------

_CATALOG: dict[str, dict[str, list[dict]]] = {

    # ── PICS / M/M/1 ─────────────────────────────────────────────────────
    "PICS": {
        "compute_P0": [
            _PICS_RHO,
            _PICS_P0,
        ],
        "compute_Lq": [
            _PICS_RHO,
            _PICS_LQ,
        ],
        "compute_Wq": [
            _PICS_RHO,
            _PICS_LQ,
            _PICS_WQ,
        ],
        "compute_W": [
            _PICS_RHO,
            _PICS_LQ,
            _PICS_WQ,
            _PICS_W,
        ],
        "compute_L": [
            _PICS_RHO,
            _PICS_LQ,
            _PICS_WQ,
            _PICS_W,
            _PICS_L,
        ],
        "compute_wait_probability": [
            # P(wait) = ρ for M/M/1
            _PICS_RHO,
        ],
        "compute_probability_q_at_least_r": [
            _PICS_RHO,
            _PICS_PN,
            _PICS_P_GE_R,
        ],
        "compute_probability_q_between": [
            _PICS_RHO,
            _PICS_PN,
        ],
        "compute_probability_queue_nonempty": [
            # P(Q > 0) = P(N ≥ 2) = ρ² for M/M/1
            _PICS_RHO,
            _PICS_PN,
        ],
        "compute_server_available_probability": [
            _PICS_RHO,
            _PICS_P0,
        ],
        "compute_idle_time": [
            _PICS_RHO,
            _PICS_P0,
            _PICS_IDLE_TIME,
        ],
        "compute_waiting_arrivals": [
            _PICS_RHO,
            _PICS_WAIT_ARRIVALS,
        ],
        "compute_cost": [
            _PICS_RHO,
            _PICS_LQ,
            _ADVISORY_COST,
        ],
    },

    # ── PICM / M/M/c ─────────────────────────────────────────────────────
    "PICM": {
        "compute_P0": [
            _PICM_A,
            _PICM_RHO,
            _PICM_P0,
        ],
        "compute_wait_probability": [
            _PICM_A,
            _PICM_RHO,
            _PICM_P0,
            _PICM_PW,
        ],
        "compute_Lq": [
            _PICM_A,
            _PICM_RHO,
            _PICM_P0,
            _PICM_PW,
            _PICM_LQ,
        ],
        "compute_Wq": [
            _PICM_A,
            _PICM_RHO,
            _PICM_P0,
            _PICM_PW,
            _PICM_LQ,
            _PICM_WQ,
        ],
        "compute_W": [
            _PICM_A,
            _PICM_RHO,
            _PICM_P0,
            _PICM_PW,
            _PICM_LQ,
            _PICM_WQ,
            _PICM_W,
        ],
        "compute_L": [
            _PICM_A,
            _PICM_RHO,
            _PICM_P0,
            _PICM_PW,
            _PICM_LQ,
            _PICM_WQ,
            _PICM_W,
            _PICM_L,
        ],
        "compute_probability_q_between": [
            _PICM_A,
            _PICM_RHO,
            _PICM_P0,
            _PICM_PN,
        ],
        "compute_probability_q_at_least_r": [
            _PICM_A,
            _PICM_RHO,
            _PICM_P0,
            _PICM_PW,
            _PICM_PN,
        ],
        "compute_server_available_probability": [
            _PICM_A,
            _PICM_RHO,
            _PICM_P0,
            _PICM_PW,
        ],
        "compute_cost": [
            _PICM_A,
            _PICM_RHO,
            _PICM_P0,
            _PICM_PW,
            _PICM_LQ,
            _ADVISORY_COST,
        ],
    },

    # ── PFCS (Finite Population, 1 server) ───────────────────────────────
    "PFCS": {
        "compute_P0": [
            _PFCS_R,
            _PFCS_P0,
        ],
        "compute_Lq": [
            _PFCS_R,
            _PFCS_P0,
            _PFCS_PN,
            _PFCS_L,
            _PFCS_LQ,
        ],
        "compute_Wq": [
            _PFCS_R,
            _PFCS_P0,
            _PFCS_PN,
            _PFCS_L,
            _PFCS_LQ,
            _PFCS_LAMBDA_EFF,
            _PFCS_WQ,
        ],
        "compute_W": [
            _PFCS_R,
            _PFCS_P0,
            _PFCS_PN,
            _PFCS_L,
            _PFCS_LAMBDA_EFF,
            _PFCS_W,
        ],
        "compute_L": [
            _PFCS_R,
            _PFCS_P0,
            _PFCS_PN,
            _PFCS_L,
        ],
        "compute_wait_probability": [
            _PFCS_R,
            _PFCS_P0,
        ],
        "compute_fraction_operating": [
            _PFCS_R,
            _PFCS_P0,
            _PFCS_PN,
            _PFCS_L,
            _PFCS_FRAC_OP,
        ],
        "compute_probability_q_between": [
            _PFCS_R,
            _PFCS_P0,
            _PFCS_PN,
        ],
        "compute_cost": [
            _PFCS_R,
            _PFCS_P0,
            _PFCS_PN,
            _PFCS_L,
            _PFCS_LQ,
            _ADVISORY_COST,
        ],
    },

    # ── PFCM (Finite Population, k servers) ──────────────────────────────
    "PFCM": {
        "compute_P0": [
            _PFCM_R,
            _PFCM_P0,
        ],
        "compute_Lq": [
            _PFCM_R,
            _PFCM_P0,
            _PFCM_PN,
            _PFCM_LQ,
        ],
        "compute_Wq": [
            _PFCM_R,
            _PFCM_P0,
            _PFCM_PN,
            _PFCM_L,
            _PFCM_LQ,
            _PFCM_LAMBDA_EFF,
            _PFCM_WQ,
        ],
        "compute_L": [
            _PFCM_R,
            _PFCM_P0,
            _PFCM_PN,
            _PFCM_L,
        ],
        "compute_probability_q_between": [
            _PFCM_R,
            _PFCM_P0,
            _PFCM_PN,
        ],
        "compute_fraction_operating": [
            _PFCM_R,
            _PFCM_P0,
            _PFCM_PN,
            _PFCM_L,
            _PFCM_FRAC_OP,
        ],
        "compute_cost": [
            _PFCM_R,
            _PFCM_P0,
            _PFCM_PN,
            _PFCM_LQ,
            _PFCM_COST,
        ],
        "compute_dimensioning_optimal_k": [
            _PFCM_R,
            _PFCM_P0,
            _PFCM_PN,
            _PFCM_LQ,
            _PFCM_COST,
        ],
    },

    # ── PFHET (Finite Population, Heterogeneous servers) ─────────────────
    "PFHET": {
        "compute_P0": [
            _PFHET_LAMBDA_N,
            _PFHET_MU_N,
            _PFHET_P0,
        ],
        "compute_wait_probability": [
            _PFHET_LAMBDA_N,
            _PFHET_MU_N,
            _PFHET_P0,
        ],
        "compute_L": [
            _PFHET_LAMBDA_N,
            _PFHET_MU_N,
            _PFHET_P0,
            _PFHET_PN,
            _PFHET_L,
        ],
        "compute_Lq": [
            _PFHET_LAMBDA_N,
            _PFHET_MU_N,
            _PFHET_P0,
            _PFHET_PN,
            _PFHET_L,
            _PFHET_LQ,
        ],
        "compute_units_operating": [
            _PFHET_LAMBDA_N,
            _PFHET_MU_N,
            _PFHET_P0,
            _PFHET_PN,
            _PFHET_L,
            _PFHET_UNITS_OP,
        ],
        "compute_Wq": [
            _PFHET_LAMBDA_N,
            _PFHET_MU_N,
            _PFHET_P0,
            _PFHET_PN,
            _PFHET_L,
            _PFHET_LQ,
            _PFHET_LAMBDA_EFF,
        ],
        "compute_cost": [
            _PFHET_LAMBDA_N,
            _PFHET_MU_N,
            _PFHET_P0,
            _PFHET_PN,
            _PFHET_L,
            _PFHET_COST,
        ],
    },
}

# Objective aliases — maps alternative objective ids to canonical ones
# Used when the literal_segmenter assigns a slightly different id.
_OBJECTIVE_ALIASES: dict[str, str] = {
    "compute_fraction_operating": "compute_fraction_operating",
    "compute_units_operating": "compute_units_operating",
    "compute_dimensioning_optimal_k": "compute_dimensioning_optimal_k",
    # wait_probability is the same for all models
    "compute_wait_probability": "compute_wait_probability",
    # idle time
    "compute_idle_time": "compute_idle_time",
    "compute_waiting_arrivals": "compute_waiting_arrivals",
}

# Cross-model fallbacks: if model X doesn't have objective Y, try model Z
# Useful when a PFCS literal requires L (also called compute_L).
_CROSS_MODEL_FALLBACK: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class FormulaPlanBuilder:
    """
    Builds structured formula plans per literal.

    Usage::

        builder = FormulaPlanBuilder()
        plan, missing = builder.build(
            model_id="PICS",
            objective="compute_Wq",
            extracted_variable_ids={"lambda_", "mu"},
        )
    """

    def build(
        self,
        model_id: Optional[str],
        objective: Optional[str],
        extracted_variable_ids: set[str],
    ) -> tuple[list[FormulaPlanStep], list[str]]:
        """
        Build a formula plan for one (model, objective) pair.

        Parameters
        ----------
        model_id : str | None
            Identified queue model, e.g. "PICS".
        objective : str | None
            Literal's inferred objective, e.g. "compute_Wq".
        extracted_variable_ids : set[str]
            Variable ids extracted from the statement text.

        Returns
        -------
        (plan, missing_variables)
            plan : list[FormulaPlanStep] — ordered steps (may be empty)
            missing_variables : list[str] — base vars not found in text
        """
        if not model_id or not objective:
            return [], []

        # Look up step dict list from catalog
        model_plans = _CATALOG.get(model_id, {})
        step_dicts = model_plans.get(objective)

        # Try without "compute_" prefix
        if step_dicts is None:
            bare = objective.replace("compute_", "")
            for key in model_plans:
                if key.replace("compute_", "") == bare:
                    step_dicts = model_plans[key]
                    break

        if not step_dicts:
            return [], []

        plan = _build_plan(step_dicts)
        missing = self._compute_missing(plan, extracted_variable_ids)
        return plan, missing

    @staticmethod
    def _compute_missing(
        plan: list[FormulaPlanStep],
        extracted: set[str],
    ) -> list[str]:
        """
        Simulate forward execution to find base variables that are missing.

        Rules
        -----
        - Start with ``known`` = extracted variable ids.
        - After each step: add its ``produces`` to known.
        - A variable is missing if it is required by a step AND
          is not in known when that step is reached,
          AND has not already been flagged.
        - Variables produced by prior steps are never missing.
        - Derived intermediates (rho, P0, Lq, etc.) are NEVER in ``missing``:
          they are always computed by the plan itself.
        """
        # Set of intermediate/derived variable ids produced within the plan
        plan_produces: set[str] = {s.produces for s in plan}

        known: set[str] = set(extracted)
        missing_set: list[str] = []
        seen_missing: set[str] = set()

        for step in plan:
            for var in step.required_variables:
                if var not in known and var not in plan_produces and var not in seen_missing:
                    missing_set.append(var)
                    seen_missing.add(var)
            # Mark this step's output as known for downstream steps
            known.add(step.produces)

        return missing_set


# Module-level convenience function
_builder = FormulaPlanBuilder()


def build_formula_plan(
    model_id: Optional[str],
    objective: Optional[str],
    extracted_variable_ids: set[str],
) -> tuple[list[FormulaPlanStep], list[str]]:
    """
    Convenience wrapper around FormulaPlanBuilder.build().

    Returns (plan_steps, missing_variables).
    """
    return _builder.build(model_id, objective, extracted_variable_ids)


def get_available_objectives(model_id: str) -> list[str]:
    """Return all objective ids for which a plan exists for the given model."""
    return list(_CATALOG.get(model_id, {}).keys())


def get_all_models() -> list[str]:
    """Return all model ids in the catalog."""
    return list(_CATALOG.keys())

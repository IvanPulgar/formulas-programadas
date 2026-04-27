"""
LiteralSegmenter — Phase 8 / Phase 9.

Detects lettered sub-questions (literals / incisos) in a Spanish queue-theory
problem statement and splits the text into:
  - statement_context : the general data part (everything before the first literal)
  - literals          : an ordered list of DetectedLiteral objects

Supported marker formats
------------------------
  a)   b)   c)  …  g)         ← most common
  (a)  (b)  (c)               ← parenthesized
  a.   b.   c.                ← dot-terminated  (not followed by a digit)
  Literal a  /  Literal b     ← explicit keyword
  inciso a   /  inciso b      ← inciso keyword

Phase 9 adds:
  - compute_wait_probability  — P(customer must wait)
  - compute_idle_time         — daily/weekly idle-server time
  - compute_waiting_arrivals  — arrivals per period that must wait
  - compute_probability_q_at_least_r — P(Q ≥ r)
  - compute_probability_q_between    — P(r1 ≤ Q ≤ r2)
  - compute_probability_queue_nonempty — P(Q > 0)
  - compute_server_available_probability — P(at least one server free)
  - compute_cost              — cost objectives (unsupported this phase)

Objective sets exported for use by statement_analyzer.py
---------------------------------------------------------
  UNSUPPORTED_OBJECTIVES        — always generate objective_detected_but_not_executable
  OBJECTIVES_NEEDING_PERIOD     — need operating-hours variable; else missing_period_hours
  OBJECTIVES_NEEDING_THRESHOLD  — need a numeric threshold; else missing_threshold_r
"""

from __future__ import annotations

import re
from typing import Optional

from domain.entities.analysis import DetectedLiteral


# ---------------------------------------------------------------------------
# Literal marker regex — matches at the START of a line (MULTILINE)
# ---------------------------------------------------------------------------
_LITERAL_LINE_RE = re.compile(
    r"^[ \t]*"
    r"(?:"
    r"(?:literal|inciso)\s+([a-g])\b"
    r"|\(([a-g])\)"
    r"|([a-g])\)"
    r"|([a-g])\.(?!\d)"
    r")",
    re.IGNORECASE | re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Compact inline marker regex — matches a), b), ... anywhere in the text.
# Guards:
#   (?<!\w)       — letter is not inside a word (e.g. "alternativa)" is rejected)
#   (?=\s*[^\s)\d]) — must be followed by actual text content (not just space/)/digit)
# ---------------------------------------------------------------------------
_COMPACT_RE = re.compile(
    r"(?<!\w)([a-g])\)(?=\s*[^\s)\d])",
    re.IGNORECASE,
)

# Trigger phrases that indicate an enumerated sub-question follows (for
# single-marker compact detection).
_SINGLE_TRIGGER_RE = re.compile(
    r"(?:calcul[ae]r?|determin[ae]r?|se pide|obtener|hallar|encontrar"
    r"|se requiere|determine|calcule|calcular)\s*:?\s*$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Objective sets (exported — used by statement_analyzer for issue generation)
# ---------------------------------------------------------------------------

#: Objectives that cannot be executed numerically in the current phase.
UNSUPPORTED_OBJECTIVES: frozenset[str] = frozenset({
    "compute_cost",
    "compute_total_cost",
    "compare_alternatives",
    "optimize_cost",
})

#: Objectives that require an operating-period variable (hours/day, etc.).
OBJECTIVES_NEEDING_PERIOD: frozenset[str] = frozenset({
    "compute_idle_time",
    "compute_waiting_arrivals",
})

#: Objectives that require a numeric threshold r in the literal text.
OBJECTIVES_NEEDING_THRESHOLD: frozenset[str] = frozenset({
    "compute_probability_q_at_least_r",
    "compute_probability_q_between",
})

# ---------------------------------------------------------------------------
# Objective keyword mapping
# Ordered by specificity — FIRST match wins.
#
# Ordering rules:
#   1. compute_idle_time  BEFORE compute_P0   (more specific daily/weekly phrases)
#   2. compute_waiting_arrivals BEFORE compute_Lq  (temporal qualifiers)
#   3. compute_probability_q_between BEFORE compute_probability_q_at_least_r
#   4. compute_wait_probability BEFORE compute_rho / compute_Pk
#   5. compute_cost last among high-priority entries (very specific phrases)
# ---------------------------------------------------------------------------
_OBJECTIVE_MAP: list[tuple[str, str]] = [

    # ── compute_idle_time (daily/weekly idle) — before P0 ─────────────────
    ("minutos diarios que permanece desocupad",        "compute_idle_time"),
    ("minutos diarios que permanece",                  "compute_idle_time"),
    ("minutos diarios que el servidor esta",           "compute_idle_time"),
    ("minutos diarios desocupado",                     "compute_idle_time"),
    ("tiempo diario que esta ocioso",                  "compute_idle_time"),
    ("tiempo diario desocupado",                       "compute_idle_time"),
    ("horas por dia con servidores desocupados",       "compute_idle_time"),
    ("horas diarias desocupado",                       "compute_idle_time"),
    ("tiempo semanal desocupado",                      "compute_idle_time"),
    ("minutos al dia con al menos un servidor libre",  "compute_idle_time"),
    ("minutos diarios con al menos un servidor libre", "compute_idle_time"),
    ("tiempo que permanece desocupado",                "compute_idle_time"),

    # ── compute_server_available_probability — percentage time server free ─
    ("porcentaje de tiempo con una o varias ventanillas desocupadas",
                                                       "compute_server_available_probability"),
    ("porcentaje de tiempo con servidores disponibles","compute_server_available_probability"),
    ("proporcion del tiempo con servidor disponible",  "compute_server_available_probability"),
    ("probabilidad de que alguna ventanilla este libre","compute_server_available_probability"),
    ("probabilidad de que al menos un servidor este libre", "compute_server_available_probability"),
    ("probabilidad de que al menos un servidor este disponible", "compute_server_available_probability"),

    # ── compute_waiting_arrivals (count/period that wait) — before Lq ─────
    ("numero diario de clientes que esperan",          "compute_waiting_arrivals"),
    ("clientes que deberan esperar por dia",           "compute_waiting_arrivals"),
    ("clientes diarios que esperan",                   "compute_waiting_arrivals"),
    ("llamadas que esperan diariamente",               "compute_waiting_arrivals"),
    ("piezas por semana que deberan esperar",          "compute_waiting_arrivals"),
    ("vehiculos que esperan al dia",                   "compute_waiting_arrivals"),
    ("ordenadores diarios que deberan esperar",        "compute_waiting_arrivals"),
    ("programas diarios que deberan esperar",          "compute_waiting_arrivals"),
    ("diariamente deberan esperar",                    "compute_waiting_arrivals"),
    ("esperan diariamente",                            "compute_waiting_arrivals"),
    ("deberan esperar por dia",                        "compute_waiting_arrivals"),
    ("diario de clientes que esperan",                 "compute_waiting_arrivals"),

    # ── compute_probability_q_between (range) — before q_at_least_r ──────
    ("haya 1 o 2",                                     "compute_probability_q_between"),
    ("1 o 2 clientes",                                 "compute_probability_q_between"),
    ("uno o dos clientes",                             "compute_probability_q_between"),
    ("1 o 2 programas",                                "compute_probability_q_between"),
    ("1 o 2 esperando",                                "compute_probability_q_between"),
    ("entre 1 y 2",                                    "compute_probability_q_between"),

    # ── compute_probability_q_at_least_r ─────────────────────────────────
    ("al menos dos programas",                         "compute_probability_q_at_least_r"),
    ("al menos dos clientes",                          "compute_probability_q_at_least_r"),
    ("al menos dos equipos",                           "compute_probability_q_at_least_r"),
    ("al menos dos",                                   "compute_probability_q_at_least_r"),
    ("mas de dos clientes",                            "compute_probability_q_at_least_r"),
    ("mas de dos programas",                           "compute_probability_q_at_least_r"),
    ("mas de un equipo",                               "compute_probability_q_at_least_r"),
    ("mas de dos",                                     "compute_probability_q_at_least_r"),
    ("por lo menos dos",                               "compute_probability_q_at_least_r"),

    # ── compute_probability_queue_nonempty ────────────────────────────────
    ("probabilidad de cola no vacia",                  "compute_probability_queue_nonempty"),
    ("cola no vacia",                                  "compute_probability_queue_nonempty"),

    # ── compute_cost (unsupported this phase) ─────────────────────────────
    ("costo ocasionado",                               "compute_cost"),
    ("costo total",                                    "compute_cost"),
    ("costo en el",                                    "compute_cost"),
    ("costo por",                                      "compute_cost"),
    ("costo del sistema",                              "compute_cost"),

    # ── compute_total_cost (daily/weekly cost totals — unsupported) ───────
    ("costo diario total",                             "compute_total_cost"),
    ("costo total diario",                             "compute_total_cost"),
    ("costo diario",                                   "compute_total_cost"),

    # ── compare_alternatives / optimize_cost (economic decisions — unsupported) ──
    ("comparar alternativas",                          "compare_alternatives"),
    ("compare alternativas",                           "compare_alternatives"),
    ("compare dos alternativas",                       "compare_alternatives"),
    ("comparar dos alternativas",                      "compare_alternatives"),
    ("alternativas de servicio",                       "compare_alternatives"),
    ("mejor alternativa",                              "optimize_cost"),
    ("la mejor alternativa",                           "optimize_cost"),
    ("determinar la mejor",                            "optimize_cost"),
    ("opcion optima",                                  "optimize_cost"),
    ("la opcion optima",                               "optimize_cost"),

    # ── compute_wait_probability — before rho/Pk (overlapping phrases) ───
    ("probabilidad de que todas las lineas esten ocupadas",
                                                       "compute_wait_probability"),
    ("probabilidad de que todos los servidores esten ocupados",
                                                       "compute_wait_probability"),
    ("fraccion de afiliados que debe esperar",         "compute_wait_probability"),
    ("fraccion de programas que debe esperar",         "compute_wait_probability"),
    ("porcentaje de clientes que esperan",             "compute_wait_probability"),
    ("probabilidad de que un cliente tenga que esperar","compute_wait_probability"),
    ("probabilidad de que exista cola",                "compute_wait_probability"),
    ("probabilidad de que haya linea de espera",       "compute_wait_probability"),
    ("fraccion de clientes que debe esperar",          "compute_wait_probability"),
    ("fraccion de clientes que deben esperar",         "compute_wait_probability"),

    # ── Wq (time in queue) ────────────────────────────────────────────────
    ("tiempo medio que permanec",                      "compute_Wq"),
    ("tiempo que permanecen en cola",                  "compute_Wq"),
    ("permanecen en cola",                             "compute_Wq"),
    ("tiempo medio de espera",                         "compute_Wq"),
    ("tiempo medio en cola",                           "compute_Wq"),
    ("tiempo de espera en la cola",                    "compute_Wq"),
    ("tiempo promedio de espera",                      "compute_Wq"),
    ("cuanto tiempo espera",                           "compute_Wq"),
    ("espera un afiliado",                             "compute_Wq"),
    ("tiempo que debe esperar un afiliado",            "compute_Wq"),
    ("tiempo de espera de un cliente",                 "compute_Wq"),
    ("tiempo de espera de un",                         "compute_Wq"),
    ("espera promedio",                                "compute_Wq"),
    ("que debe esperar",                               "compute_Wq"),
    ("tiempo de espera",                               "compute_Wq"),

    # ── W (time in system) ────────────────────────────────────────────────
    ("tiempo esperado total de salida",                "compute_W"),
    ("tiempo total de salida",                         "compute_W"),
    ("tiempo total en el sistema",                     "compute_W"),
    ("tiempo medio en el sistema",                     "compute_W"),
    ("tiempo promedio en el sistema",                  "compute_W"),
    ("tiempo de permanencia",                          "compute_W"),
    ("tiempo que pasa en el sistema",                  "compute_W"),
    ("tiempo en la farmacia",                          "compute_W"),
    ("tiempo en el terminal",                          "compute_W"),
    ("tiempo en la oficina",                           "compute_W"),
    ("espera mas servicio",                            "compute_W"),
    ("desde que llega hasta que termina",              "compute_W"),
    ("tiempo que pasan en",                            "compute_W"),

    # ── Lq (queue length) ─────────────────────────────────────────────────
    ("longitud media de la cola",                      "compute_Lq"),
    ("longitud media de la linea",                     "compute_Lq"),
    ("longitud de la cola",                            "compute_Lq"),
    ("longitud de la linea",                           "compute_Lq"),
    ("numero promedio de clientes esperando",          "compute_Lq"),
    ("numero medio de clientes en cola",               "compute_Lq"),
    ("numero de clientes esperando",                   "compute_Lq"),
    ("numero esperado en cola",                        "compute_Lq"),
    ("numero medio en cola",                           "compute_Lq"),
    ("programas esperando en la cola",                 "compute_Lq"),
    ("clientes esperando en promedio",                 "compute_Lq"),
    ("numero promedio esperando",                      "compute_Lq"),
    ("promedio esperando",                             "compute_Lq"),
    ("empleados esperando",                            "compute_Lq"),
    ("programas esperando",                            "compute_Lq"),
    ("clientes esperando",                             "compute_Lq"),
    # PFCS/PFCM/PFHET — entities instead of clientes
    ("numero esperado de maquinas esperando",          "compute_Lq"),
    ("numero esperado de equipos esperando",           "compute_Lq"),
    ("numero esperado de aviones esperando",           "compute_Lq"),
    ("numero esperado de montacargas esperando",       "compute_Lq"),
    ("maquinas esperando",                             "compute_Lq"),
    ("equipos esperando",                              "compute_Lq"),
    ("aviones esperando",                              "compute_Lq"),
    ("montacargas esperando",                          "compute_Lq"),

    # ── L (customers in system) ───────────────────────────────────────────
    ("numero esperado de clientes en la oficina",      "compute_L"),
    ("numero de clientes en la oficina",               "compute_L"),
    ("numero medio en el sistema",                     "compute_L"),
    ("numero promedio en el sistema",                  "compute_L"),
    ("numero de clientes en el sistema",               "compute_L"),
    ("numero esperado en el sistema",                  "compute_L"),
    ("numero promedio dentro del sistema",             "compute_L"),
    ("clientes en la farmacia",                        "compute_L"),
    ("programas en el servidor",                       "compute_L"),
    ("clientes en el terminal",                        "compute_L"),
    ("numero medio de clientes en la",                 "compute_L"),
    # PFCS/PFCM/PFHET — entities instead of clientes
    ("numero esperado de maquinas en el sistema",      "compute_L"),
    ("numero esperado de equipos en el sistema",       "compute_L"),
    ("numero esperado de aviones en el sistema",       "compute_L"),
    ("numero esperado de montacargas en el sistema",   "compute_L"),
    ("numero esperado de maquinas",                    "compute_L"),
    ("numero esperado de equipos",                     "compute_L"),
    ("numero esperado de aviones",                     "compute_L"),
    ("numero esperado de montacargas",                 "compute_L"),
    ("maquinas en el sistema",                         "compute_L"),
    ("equipos en el sistema",                          "compute_L"),
    ("aviones en el sistema",                          "compute_L"),
    ("montacargas en el sistema",                      "compute_L"),

    # ── P0 (idle probability / empty system) ─────────────────────────────
    ("probabilidad de que el servidor este ocioso",    "compute_P0"),
    ("porcentaje del tiempo que esta desocupado",      "compute_P0"),
    ("proporcion de tiempo que el servidor esta desocupado", "compute_P0"),
    ("servidor esta desocupado",                       "compute_P0"),
    ("que esta desocupado",                            "compute_P0"),
    ("proporcion de tiempo ocioso",                    "compute_P0"),
    ("fraccion del tiempo desocupado",                 "compute_P0"),
    ("fraccion del tiempo libre",                      "compute_P0"),
    ("tiempo libre del servidor",                      "compute_P0"),
    ("tiempo ocioso",                                  "compute_P0"),
    ("tiempo que estara desocupado",                   "compute_P0"),
    ("servidor desocupado",                            "compute_P0"),
    ("tiempo desocupado",                              "compute_P0"),
    ("probabilidad de sistema vacio",                  "compute_P0"),
    ("probabilidad de que el sistema este vacio",      "compute_P0"),
    ("proporcion del tiempo desocupado",               "compute_P0"),
    # PFCS/PFCM/PFHET — mechanic/technician/workshop free (instead of server idle)
    ("probabilidad de que el mecanico este libre",     "compute_P0"),
    ("probabilidad de que el tecnico este libre",      "compute_P0"),
    ("probabilidad de que el taller este libre",       "compute_P0"),
    ("mecanico este libre",                            "compute_P0"),
    ("mecanico libre",                                 "compute_P0"),
    ("tecnico este libre",                             "compute_P0"),
    ("tecnico libre",                                  "compute_P0"),
    ("taller este libre",                              "compute_P0"),
    ("taller libre",                                   "compute_P0"),
    ("servidor libre",                                 "compute_P0"),
    ("servidor este libre",                            "compute_P0"),
    ("(p0)",                                           "compute_P0"),

    # ── rho (utilization) ────────────────────────────────────────────────
    ("proporcion del tiempo que esta ocupado",         "compute_rho"),
    ("porcentaje del tiempo laborando",                "compute_rho"),
    ("probabilidad de que algun servidor este ocupado","compute_rho"),
    ("utilizacion del servidor",                       "compute_rho"),
    ("utilizacion del sistema",                        "compute_rho"),
    ("fraccion de tiempo ocupado",                     "compute_rho"),
    ("proporcion del tiempo ocupado",                  "compute_rho"),
    ("factor de utilizacion",                          "compute_rho"),

    # ── Pk (PICM: Erlang C / all servers busy) ────────────────────────────
    ("probabilidad de encontrar todos los servidores ocupados", "compute_Pk"),
]



class LiteralSegmenter:
    """
    Splits a queue-theory problem statement into a context block and an
    ordered list of sub-questions (DetectedLiteral objects).

    If no literal markers are found the full text is returned as the
    context and the literal list is empty — existing pipeline is unchanged.
    """

    def segment(
        self,
        text: str,
        norm_text: str,
    ) -> tuple[str, list[DetectedLiteral]]:
        """
        Parameters
        ----------
        text : str
            Original (possibly mixed-case, accented) text.
        norm_text : str
            Accent-normalized, lowercased version of *text* produced by the
            same normalizer used in the analysis pipeline.  Character
            positions in *norm_text* correspond 1-to-1 to positions in
            *text* for standard Spanish content.

        Returns
        -------
        (statement_context, literals)
            statement_context — text before the first literal marker (stripped).
            literals          — ordered list of DetectedLiteral; may be empty.
        """
        spans = list(_LITERAL_LINE_RE.finditer(norm_text))
        if not spans:
            # Second pass: try compact inline format (e.g. "Calcule: a) ..., b) ...")
            spans = self._find_compact_markers(norm_text)
        if not spans:
            return text.strip(), []

        # Context = everything in the original text before the first marker
        first_start = spans[0].start()
        statement_context = text[:first_start].strip()

        literals: list[DetectedLiteral] = []
        for i, span in enumerate(spans):
            # Recover letter from the first non-None capturing group
            letter = next(g for g in span.groups() if g is not None).lower()

            body_start = span.end()
            body_end = spans[i + 1].start() if (i + 1) < len(spans) else len(text)

            raw_body = text[body_start:body_end].strip().rstrip(",;")
            norm_body = norm_text[body_start:body_end].strip().rstrip(",;")

            objective = self._infer_objective(norm_body)

            literals.append(
                DetectedLiteral(
                    literal_id=letter,
                    raw_text=raw_body,
                    normalized_text=norm_body,
                    inferred_objective=objective,
                )
            )

        return statement_context, literals

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_compact_markers(self, norm_text: str) -> list[re.Match]:
        """Find inline compact markers a), b), ... in alphabetical sequence.

        Returns a list of regex Match objects suitable for use in segment().
        Requires either:
        - at least 2 markers in alphabetical sequence starting from 'a', OR
        - exactly 1 marker ('a') preceded by a trigger phrase (Calcule:, etc.)
        """
        all_matches = list(_COMPACT_RE.finditer(norm_text))
        if not all_matches:
            return []

        # Find the first occurrence of 'a'
        a_matches = [m for m in all_matches if m.group(1).lower() == "a"]
        if not a_matches:
            return []

        first_a = a_matches[0]

        # Build the longest valid alphabetical sequence a, b, c, ...
        valid: list[re.Match] = [first_a]
        expected = "b"
        for m in all_matches:
            if m.start() <= first_a.start():
                continue
            if m.group(1).lower() == expected:
                valid.append(m)
                expected = chr(ord(expected) + 1)
                if expected > "g":
                    break

        # Accept if 2+ markers, or 1 marker preceded by a trigger phrase
        if len(valid) >= 2:
            return valid

        text_before_a = norm_text[: first_a.start()]
        if _SINGLE_TRIGGER_RE.search(text_before_a):
            return valid

        return []

    def _infer_objective(self, norm_text: str) -> Optional[str]:
        """Return the first matching objective id, or None."""
        for keyword, obj_id in _OBJECTIVE_MAP:
            if keyword in norm_text:
                return obj_id
        return None

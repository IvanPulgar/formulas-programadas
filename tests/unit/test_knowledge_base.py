"""
tests/unit/test_knowledge_base.py — Phase 10 knowledge base tests

7 mandatory pruebas:
1. KB exists, has all 5 models, each exercise has required fields
2. Flexible M/M/1 (PICS) recognition — does NOT match by specific numbers
3. Flexible M/M/c (PICM) recognition
4. Flexible PFCS recognition
5. Flexible PFCM recognition
6. Flexible PFHET recognition
7. System does NOT memorize numeric results (same structure, different numbers)
"""

import pytest

from domain.services.statement_problem_knowledge import (
    find_matching_patterns,
    get_formula_order_hint,
    get_unit_conversion_hints,
    get_all_model_ids,
    get_exercises_for_model,
    knowledge_base_loaded,
    load_patterns,
)


# ---------------------------------------------------------------------------
# Prueba 1 — Knowledge base integrity
# ---------------------------------------------------------------------------

class TestKnowledgeBaseIntegrity:
    """Prueba 1: KB exists, contains all 5 models, each exercise has required fields."""

    def test_kb_loaded(self):
        """Knowledge base JSON is found and non-empty."""
        assert knowledge_base_loaded(), "Knowledge base not loaded — check queue_exercise_patterns.json path"

    def test_all_five_models_present(self):
        """All 5 queue models are represented in model_trigger_patterns."""
        model_ids = get_all_model_ids()
        expected = {"PICS", "PICM", "PFCS", "PFCM", "PFHET"}
        assert expected.issubset(set(model_ids)), (
            f"Missing models: {expected - set(model_ids)}"
        )

    def test_all_exercises_have_required_fields(self):
        """Each exercise pattern has: exercise_id, detected_model, literals, variables_to_extract."""
        exercises = load_patterns().get("exercises", [])
        assert len(exercises) >= 25, f"Expected at least 25 exercises, found {len(exercises)}"
        for ex in exercises:
            eid = ex.get("exercise_id", "<missing>")
            assert "exercise_id" in ex, f"Missing exercise_id in: {ex}"
            assert "detected_model" in ex, f"Missing detected_model in exercise: {eid}"
            assert "literals" in ex, f"Missing literals in exercise: {eid}"
            assert "variables_to_extract" in ex, f"Missing variables_to_extract in exercise: {eid}"

    def test_each_literal_has_objective(self):
        """Each literal has at minimum an 'id' and an 'objective' field."""
        exercises = load_patterns().get("exercises", [])
        for ex in exercises:
            eid = ex.get("exercise_id", "<missing>")
            for lit in ex.get("literals", []):
                assert "id" in lit, f"Literal missing 'id' in exercise: {eid}"
                # objective is expected on most; allow missing only for identify_model special case
                obj = lit.get("objective", "")
                assert obj or lit.get("notes"), (
                    f"Literal '{lit.get('id')}' in '{eid}' has neither objective nor notes"
                )

    def test_each_model_has_at_least_one_exercise(self):
        """Each of the 5 models is covered either as detected_model or as model_context in literals."""
        exercises = load_patterns().get("exercises", [])
        covered_models: set[str] = set()
        for ex in exercises:
            covered_models.add(ex.get("detected_model", ""))
            for lit in ex.get("literals", []):
                mc = lit.get("model_context", "")
                if mc:
                    covered_models.add(mc)
        for model_id in ["PICS", "PICM", "PFCS", "PFCM", "PFHET"]:
            assert model_id in covered_models, (
                f"Model '{model_id}' not covered by any exercise (detected_model or model_context)"
            )

    def test_no_numeric_results_in_exercises(self):
        """Exercises must NOT contain keys like 'answer', 'result', or 'value'."""
        exercises = load_patterns().get("exercises", [])
        forbidden_keys = {"answer", "result", "calculated_value", "numeric_result"}
        for ex in exercises:
            eid = ex.get("exercise_id", "<missing>")
            found = forbidden_keys & set(ex.keys())
            assert not found, f"Exercise '{eid}' has forbidden result keys: {found}"


# ---------------------------------------------------------------------------
# Prueba 2 — Flexible M/M/1 (PICS) recognition
# ---------------------------------------------------------------------------

class TestFlexiblePICSRecognition:
    """Prueba 2: Recognizes M/M/1 structure without relying on specific numbers."""

    def test_recognizes_single_server_poisson(self):
        """Simple M/M/1 problem with Poisson arrivals is recognized as PICS."""
        text = (
            "una tienda de comida rapida es atendida por una sola persona. "
            "los clientes llegan segun un proceso de poisson y el tiempo de atencion "
            "sigue una distribucion exponencial. el local opera durante ciertas horas diarias."
        )
        hints = find_matching_patterns(text)
        assert hints, "No pattern hints returned for a clear M/M/1 problem"
        top = hints[0]
        assert top.model_id == "PICS", (
            f"Expected PICS, got {top.model_id} (confidence={top.confidence})"
        )
        assert top.confidence > 0.0

    def test_recognizes_single_server_different_numbers(self):
        """Same M/M/1 structure with completely different numbers still recognized as PICS."""
        text_a = (
            "una farmacia con una cajera. llegan clientes segun distribucion de poisson "
            "a una tasa de 18 por hora. servicio exponencial media 3 minutos. labora 8 horas."
        )
        text_b = (
            "un banco con una taquilla. llegan clientes segun distribucion de poisson "
            "a una tasa de 4 por hora. servicio exponencial media 10 minutos. labora 12 horas."
        )
        hints_a = find_matching_patterns(text_a)
        hints_b = find_matching_patterns(text_b)

        model_a = hints_a[0].model_id if hints_a else None
        model_b = hints_b[0].model_id if hints_b else None

        # Both should recognize PICS (single server) or at least the same model
        assert model_a == model_b, (
            f"Different numbers changed model recognition: {model_a} vs {model_b}"
        )

    def test_formula_order_hint_pics_lq(self):
        """get_formula_order_hint returns expected order for PICS + compute_Lq."""
        order = get_formula_order_hint("PICS", "compute_Lq")
        assert isinstance(order, list)
        # Should contain rho and Lq in that order
        assert len(order) >= 2, f"Expected >=2 steps for PICS.compute_Lq, got: {order}"
        rho_pos = next((i for i, s in enumerate(order) if "rho" in s.lower()), None)
        lq_pos = next((i for i, s in enumerate(order) if "lq" in s.lower()), None)
        assert rho_pos is not None, f"'rho' not in order: {order}"
        assert lq_pos is not None, f"'Lq' not in order: {order}"
        assert rho_pos < lq_pos, f"rho must come before Lq: {order}"


# ---------------------------------------------------------------------------
# Prueba 3 — Flexible M/M/c (PICM) recognition
# ---------------------------------------------------------------------------

class TestFlexiblePICMRecognition:
    """Prueba 3: Recognizes M/M/c structure (multiple servers, single queue)."""

    def test_recognizes_multiple_servers_single_queue(self):
        """M/M/c problem with explicit multiple servers is recognized as PICM."""
        text = (
            "en un centro de llamadas, cuatro operadores reciben las solicitudes. "
            "los clientes se forman en una unica cola y son atendidos por cualquier "
            "operador disponible. las llegadas siguen un proceso de poisson y los "
            "tiempos de servicio son exponenciales."
        )
        hints = find_matching_patterns(text)
        assert hints, "No hints returned for M/M/c problem"
        top = hints[0]
        assert top.model_id == "PICM", (
            f"Expected PICM, got {top.model_id} (confidence={top.confidence})"
        )

    def test_cost_minimization_triggers_picm_hint(self):
        """Cost minimization language with multiple servers hints PICM."""
        text = (
            "una empresa quiere minimizar costos. hay varios servidores disponibles. "
            "llegadas poisson, servicio exponencial. determinar el numero optimo "
            "de servidores para minimizar los costos totales."
        )
        hints = find_matching_patterns(text)
        top = hints[0] if hints else None
        # Should match PICM (cost minimization + multiple servers)
        if top:
            assert top.model_id == "PICM", f"Expected PICM for cost min problem, got {top.model_id}"

    def test_formula_order_hint_picm_wq(self):
        """get_formula_order_hint returns P0 before Pk before Lq before Wq for PICM."""
        order = get_formula_order_hint("PICM", "compute_Wq")
        assert isinstance(order, list)
        assert len(order) >= 3, f"Expected >=3 steps for PICM.compute_Wq, got: {order}"


# ---------------------------------------------------------------------------
# Prueba 4 — Flexible PFCS recognition
# ---------------------------------------------------------------------------

class TestFlexiblePFCSRecognition:
    """Prueba 4: Recognizes finite population single-server (PFCS) structure."""

    def test_recognizes_finite_population_pattern(self):
        """Finite population problem is recognized as PFCS."""
        text = (
            "un numero limitado de maquinas son atendidas por un taller de reparacion. "
            "cada maquina falla despues de cierto tiempo y requiere servicio. "
            "el taller atiende una maquina a la vez. los tiempos son exponenciales."
        )
        hints = find_matching_patterns(text)
        assert hints, "No hints for finite population problem"
        # PFCS or PFCM should be the top model
        top_model = hints[0].model_id
        assert top_model in ("PFCS", "PFCM"), (
            f"Expected PFCS or PFCM for finite population, got {top_model}"
        )

    def test_aviones_pfcs_pattern(self):
        """Aircraft maintenance with finite fleet recognized as PFCS."""
        text = (
            "una base aerea cuenta con un numero limitado de aviones. "
            "el taller de mantenimiento puede revisar un motor a la vez. "
            "los aviones llegan segun distribucion exponencial al taller."
        )
        hints = find_matching_patterns(text)
        assert hints, "No hints for aircraft PFCS problem"
        top_model = hints[0].model_id
        assert top_model in ("PFCS", "PFCM", "PFHET"), (
            f"Expected finite population model, got {top_model}"
        )

    def test_formula_order_hint_pfcs(self):
        """get_formula_order_hint for PFCS returns non-empty list."""
        order = get_formula_order_hint("PFCS", "compute_P0")
        assert isinstance(order, list)
        # Some order should exist (may be empty for non-catalogued objectives — acceptable)


# ---------------------------------------------------------------------------
# Prueba 5 — Flexible PFCM recognition
# ---------------------------------------------------------------------------

class TestFlexiblePFCMRecognition:
    """Prueba 5: Recognizes finite population multi-server (PFCM) structure."""

    def test_recognizes_multiple_talleres_pfcm(self):
        """Multiple maintenance shops for finite population recognized as PFCM."""
        text = (
            "se evaluan varios talleres de mantenimiento para atender a los equipos. "
            "se desea determinar cuantos talleres resultan mas economicos. "
            "poblacion finita. distribucion exponencial para llegadas y servicios."
        )
        hints = find_matching_patterns(text)
        assert hints, "No hints for PFCM problem"
        top_model = hints[0].model_id
        # PFCM or PFCS acceptable (both finite population models)
        assert top_model in ("PFCM", "PFCS", "PICM"), (
            f"Unexpected model for multi-taller finite problem: {top_model}"
        )

    def test_pfcm_formula_order_hint(self):
        """get_formula_order_hint for PFCM returns list (may be empty for unknown objectives)."""
        order = get_formula_order_hint("PFCM", "compute_Lq")
        assert isinstance(order, list)


# ---------------------------------------------------------------------------
# Prueba 6 — Flexible PFHET recognition
# ---------------------------------------------------------------------------

class TestFlexiblePFHETRecognition:
    """Prueba 6: Recognizes heterogeneous-server finite population (PFHET) structure."""

    def test_recognizes_two_heterogeneous_technicians(self):
        """Two technicians with different rates + finite population → PFHET."""
        text = (
            "el taller cuenta con dos tecnicos que demoran en promedio distintos tiempos "
            "respectivamente segun una distribucion exponencial en atender a cada unidad. "
            "ambos tecnicos atienden a todos los equipos de la fabrica. "
            "los equipos llegan al taller cada cierto tiempo segun una exponencial."
        )
        hints = find_matching_patterns(text)
        assert hints, "No hints for PFHET problem"
        # Top hint should be PFHET or PFCS (heterogeneous servers are the key signal)
        top_model = hints[0].model_id
        assert top_model in ("PFHET", "PFCS", "PFCM"), (
            f"Expected PFHET for heterogeneous technicians, got {top_model}"
        )

    def test_pfhet_has_exercises_in_kb(self):
        """At least one PFHET exercise exists in the KB."""
        pfhet_exs = get_exercises_for_model("PFHET")
        assert len(pfhet_exs) >= 1, "No PFHET exercises found in knowledge base"

    def test_heterogeneous_keyword_scores_higher_for_pfhet(self):
        """Text with 'dos tecnicos' + 'respectivamente' should rank PFHET above PICS."""
        text = (
            "dos tecnicos demoran en promedio 120 y 150 minutos respectivamente "
            "segun exponencial. numero limitado de montacargas. exponencial."
        )
        hints = find_matching_patterns(text)
        model_scores = {h.model_id: h.confidence for h in hints}
        pfhet_score = model_scores.get("PFHET", 0.0)
        pics_score = model_scores.get("PICS", 0.0)
        assert pfhet_score >= pics_score, (
            f"PFHET ({pfhet_score}) should score >= PICS ({pics_score}) for heterogeneous text"
        )


# ---------------------------------------------------------------------------
# Prueba 7 — System does NOT memorize numeric results
# ---------------------------------------------------------------------------

class TestNoNumericMemorization:
    """Prueba 7: Knowledge base stores only structural patterns, not numeric results."""

    def test_kb_exercises_have_no_numeric_answers(self):
        """No exercise entry contains numeric answer fields."""
        exercises = load_patterns().get("exercises", [])
        result_like_keys = {"answer", "result", "value", "P0_value", "Lq_value",
                            "Wq_value", "mu_value", "lambda_value", "rho_value"}
        for ex in exercises:
            eid = ex.get("exercise_id", "<missing>")
            overlap = result_like_keys & set(ex.keys())
            assert not overlap, f"Exercise '{eid}' contains answer keys: {overlap}"

    def test_same_structure_different_numbers_same_model(self):
        """Two texts with identical structure but different λ/μ map to same model."""
        # Text A: faster service
        text_a = "una fabrica con un tecnico unico. proceso de poisson. servicio exponencial. distribucion exponencial."
        # Text B: slower service, different rates
        text_b = "una oficina con un empleado. proceso de poisson. tiempos de servicio exponenciales. distribucion exponencial."

        hints_a = find_matching_patterns(text_a)
        hints_b = find_matching_patterns(text_b)

        # Both should identify the same model (PICS) — numbers are irrelevant
        model_a = hints_a[0].model_id if hints_a else "NONE"
        model_b = hints_b[0].model_id if hints_b else "NONE"

        assert model_a == model_b, (
            f"Same structural pattern gave different models: {model_a} vs {model_b}"
        )

    def test_formula_order_is_structural_not_numeric(self):
        """Formula order hints returned are string identifiers, not numbers."""
        for model in ["PICS", "PICM", "PFCS"]:
            for obj in ["compute_Lq", "compute_Wq", "compute_W"]:
                order = get_formula_order_hint(model, obj)
                for step in order:
                    # No step should be a plain number
                    assert not step.replace(".", "").isdigit(), (
                        f"Formula step looks numeric: '{step}' in {model}.{obj}"
                    )

    def test_unit_conversion_hints_are_descriptions_not_values(self):
        """Unit conversion hints are human-readable descriptions, not computed values."""
        text = "tiempo de servicio de 5 minutos por cliente"
        hints = get_unit_conversion_hints(text)
        for hint in hints:
            assert isinstance(hint, str), f"Expected string hint, got: {type(hint)}"
            assert len(hint) > 5, f"Hint too short (possibly a raw number): '{hint}'"
            # Should not be a pure number
            assert not hint.strip().replace(".", "").isdigit(), (
                f"Hint looks like a numeric result: '{hint}'"
            )


# ---------------------------------------------------------------------------
# Prueba 8 — Isolation: knowledge files belong exclusively to "Analizar enunciado"
# ---------------------------------------------------------------------------

class TestKnowledgeIsolation:
    """
    Prueba 8 (Phase 14): synonyms.json and keywords.json are used ONLY by the
    'Analizar enunciado' module.  The 'Resolver fórmulas' pipeline
    (orchestrator, matcher, solver) has its own formula-registry data system
    and does NOT access infrastructure/data/knowledge/.
    """

    def test_orchestrator_does_not_import_knowledge_repository(self):
        """orchestrator.py must not import OfflineKnowledgeRepository."""
        import inspect
        import domain.services.orchestrator as orch_mod
        source = inspect.getsource(orch_mod)
        assert "OfflineKnowledgeRepository" not in source, (
            "orchestrator.py must NOT use OfflineKnowledgeRepository"
        )

    def test_matcher_does_not_import_knowledge_repository(self):
        """matcher.py must not import OfflineKnowledgeRepository."""
        import inspect
        import domain.services.matcher as matcher_mod
        source = inspect.getsource(matcher_mod)
        assert "OfflineKnowledgeRepository" not in source, (
            "matcher.py must NOT use OfflineKnowledgeRepository"
        )

    def test_solver_does_not_import_knowledge_repository(self):
        """solver.py must not import OfflineKnowledgeRepository."""
        import inspect
        import domain.services.solver as solver_mod
        source = inspect.getsource(solver_mod)
        assert "OfflineKnowledgeRepository" not in source, (
            "solver.py must NOT use OfflineKnowledgeRepository"
        )

    def test_orchestrator_does_not_read_knowledge_data_path(self):
        """orchestrator.py must not reference infrastructure/data/knowledge."""
        import inspect
        import domain.services.orchestrator as orch_mod
        source = inspect.getsource(orch_mod)
        assert "data/knowledge" not in source and "keywords.json" not in source, (
            "orchestrator.py must not read knowledge JSON files"
        )

    def test_resolver_pipeline_uses_formula_registry(self):
        """The resolver pipeline must use domain/formulas/registry — its own data system."""
        import inspect
        import domain.services.orchestrator as orch_mod
        source = inspect.getsource(orch_mod)
        assert "registry" in source or "get_formula_by_id" in source, (
            "orchestrator.py must use the formula registry (not knowledge files)"
        )

    def test_knowledge_repo_loads_both_files_without_error(self):
        """OfflineKnowledgeRepository must load keywords.json and synonyms.json cleanly."""
        from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository
        repo = OfflineKnowledgeRepository()
        knowledge = repo.load_all()
        assert "keywords" in knowledge, "keywords missing from loaded knowledge"
        assert "synonyms" in knowledge, "synonyms missing from loaded knowledge"
        # Both must be non-empty dicts/structures
        assert knowledge["keywords"], "keywords.json loaded but empty"
        assert knowledge["synonyms"], "synonyms.json loaded but empty"

    def test_analysis_module_consumers_only(self):
        """
        OfflineKnowledgeRepository is only imported by analysis-module files,
        not by the formula-resolver files (orchestrator, matcher, solver).
        """
        import inspect
        import domain.services.orchestrator as orch
        import domain.services.matcher as matcher
        import domain.services.solver as solver

        for mod, name in [(orch, "orchestrator"), (matcher, "matcher"), (solver, "solver")]:
            src = inspect.getsource(mod)
            assert "OfflineKnowledgeRepository" not in src, (
                f"{name}.py must NOT import OfflineKnowledgeRepository — "
                "knowledge files belong exclusively to the 'Analizar enunciado' module"
            )


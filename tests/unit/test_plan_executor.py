"""
Tests for PlanExecutor — Phase 4.

Exercises:
- make_executor() factory
- PICS + compute_Wq: full execution, correct numeric value
- PICS + compute_Wq with missing mu: step skipped, is_complete=False
- PICS + compute_Wq + compute_L: two primary steps both succeed
- PICM + compute_Wq: 3-step chain, all succeed, propagation into pool
- PFCS + compute_Wq: 4-step chain, all succeed
- Empty plan: returns result with issue, not complete
- Unknown formula_id in plan step: fails gracefully, no exception raised
- PlanExecutionResult helpers: primary_results, successful_results,
  failed_results, skipped_results, get_value, primary_values
- Full pipeline: make_analyzer → analyze → make_planner → plan → make_executor → execute
"""

import math

import pytest

from domain.entities.analysis import (
    AnalysisConfidence,
    ExtractedVariable,
    StatementAnalysisResult,
)
from domain.entities.execution import PlanExecutionResult, StepExecutionResult
from domain.entities.plan import ResolutionPlan, ResolutionStep, StepStatus
from domain.services.plan_executor import PlanExecutor, make_executor
from domain.services.resolution_planner import ResolutionPlanner, make_planner
from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis(
    model_id: str | None,
    variables: dict[str, float],
    objectives: list[str],
) -> StatementAnalysisResult:
    """Build a StatementAnalysisResult with normalized_value per variable."""
    result = StatementAnalysisResult()
    result.identified_model = model_id
    result.model_confidence = (
        AnalysisConfidence.HIGH if model_id else AnalysisConfidence.NONE
    )
    for var_id, value in variables.items():
        result.extracted_variables.append(
            ExtractedVariable(
                variable_id=var_id,
                raw_value=value,
                unit="",
                normalized_value=value,
            )
        )
    result.inferred_objectives = list(objectives)
    return result


# PICS with λ=2, μ=4 → stable (ρ=0.5)
PICS_VARS = {"lambda_": 2.0, "mu": 4.0}
# Expected PICS Wq = λ / (μ·(μ−λ)) = 2 / (4·2) = 0.25
PICS_WQ_EXPECTED = 0.25
# Expected PICS L = λ / (μ−λ) = 2 / 2 = 1.0
PICS_L_EXPECTED = 1.0

# PICM with λ=2, μ=4, k=3 → stable (ρ=2/(3·4)≈0.167)
PICM_VARS = {"lambda_": 2.0, "mu": 4.0, "k": 3}

# PFCS with λ=1, μ=2, M=4 → stable
PFCS_VARS = {"lambda_": 1.0, "mu": 2.0, "M": 4}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def knowledge():
    return OfflineKnowledgeRepository().load_all()


@pytest.fixture(scope="module")
def planner(knowledge):
    return ResolutionPlanner(knowledge)


@pytest.fixture(scope="module")
def executor():
    return PlanExecutor()


def _plan(planner, model_id, variables, objectives):
    analysis = _make_analysis(model_id, variables, objectives)
    return analysis, planner.plan(analysis)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestFactory:
    def test_make_executor_returns_executor(self):
        ex = make_executor()
        assert isinstance(ex, PlanExecutor)

    def test_factory_creates_independent_instances(self):
        a = make_executor()
        b = make_executor()
        assert a is not b


# ---------------------------------------------------------------------------
# PICS — single-step compute_Wq
# ---------------------------------------------------------------------------


class TestPICSWqSingleStep:
    def test_is_complete(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.is_complete is True

    def test_model_id_preserved(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.model_id == "PICS"

    def test_objectives_preserved(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert "compute_Wq" in result.objectives

    def test_one_step_result(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert len(result.step_results) == len(plan.steps)

    def test_wq_computed_value_correct(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        wq_step = next(r for r in result.step_results if r.formula_id == "pics_wq")
        assert wq_step.success is True
        assert wq_step.computed_variable == "Wq"
        assert math.isclose(wq_step.computed_value, PICS_WQ_EXPECTED, rel_tol=1e-6)

    def test_wq_in_final_variables(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert "Wq" in result.final_variables
        assert math.isclose(result.final_variables["Wq"], PICS_WQ_EXPECTED, rel_tol=1e-6)

    def test_inputs_preserved_in_final_variables(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.final_variables["lambda_"] == 2.0
        assert result.final_variables["mu"] == 4.0

    def test_primary_result_is_wq(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        primaries = result.primary_results()
        assert len(primaries) == 1
        assert primaries[0].formula_id == "pics_wq"
        assert primaries[0].is_primary is True

    def test_primary_values_returns_wq(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        pv = result.primary_values()
        assert "Wq" in pv
        assert math.isclose(pv["Wq"], PICS_WQ_EXPECTED, rel_tol=1e-6)

    def test_no_execution_issues_on_success(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.execution_issues == []

    def test_inputs_used_recorded(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        wq_step = next(r for r in result.step_results if r.formula_id == "pics_wq")
        assert "lambda_" in wq_step.inputs_used
        assert "mu" in wq_step.inputs_used


# ---------------------------------------------------------------------------
# PICS — blocked when mu is missing
# ---------------------------------------------------------------------------


class TestPICSBlocked:
    def test_is_complete_false(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", {"lambda_": 2.0}, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.is_complete is False

    def test_step_is_skipped(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", {"lambda_": 2.0}, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        wq_step = next(
            (r for r in result.step_results if r.formula_id == "pics_wq"), None
        )
        assert wq_step is not None
        assert wq_step.skipped is True
        assert wq_step.success is False

    def test_computed_value_is_none(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", {"lambda_": 2.0}, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        wq_step = next(r for r in result.step_results if r.formula_id == "pics_wq")
        assert wq_step.computed_value is None

    def test_skipped_results_lists_step(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", {"lambda_": 2.0}, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        skipped_ids = [r.formula_id for r in result.skipped_results()]
        assert "pics_wq" in skipped_ids

    def test_execution_issues_emitted(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", {"lambda_": 2.0}, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert len(result.execution_issues) > 0

    def test_wq_not_in_final_variables(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", {"lambda_": 2.0}, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.get_value("Wq") is None


# ---------------------------------------------------------------------------
# PICS — multiple objectives: compute_Wq + compute_L
# ---------------------------------------------------------------------------


class TestPICSMultipleObjectives:
    def test_is_complete(self, planner, executor):
        analysis, plan = _plan(
            planner, "PICS", PICS_VARS, ["compute_Wq", "compute_L"]
        )
        result = executor.execute(analysis, plan)
        assert result.is_complete is True

    def test_two_primary_results(self, planner, executor):
        analysis, plan = _plan(
            planner, "PICS", PICS_VARS, ["compute_Wq", "compute_L"]
        )
        result = executor.execute(analysis, plan)
        primaries = result.primary_results()
        assert len(primaries) == 2

    def test_wq_value_correct(self, planner, executor):
        analysis, plan = _plan(
            planner, "PICS", PICS_VARS, ["compute_Wq", "compute_L"]
        )
        result = executor.execute(analysis, plan)
        assert math.isclose(result.get_value("Wq"), PICS_WQ_EXPECTED, rel_tol=1e-6)

    def test_l_value_correct(self, planner, executor):
        analysis, plan = _plan(
            planner, "PICS", PICS_VARS, ["compute_Wq", "compute_L"]
        )
        result = executor.execute(analysis, plan)
        assert math.isclose(result.get_value("L"), PICS_L_EXPECTED, rel_tol=1e-6)

    def test_both_in_primary_values(self, planner, executor):
        analysis, plan = _plan(
            planner, "PICS", PICS_VARS, ["compute_Wq", "compute_L"]
        )
        result = executor.execute(analysis, plan)
        pv = result.primary_values()
        assert "Wq" in pv
        assert "L" in pv


# ---------------------------------------------------------------------------
# PICM — 3-step chain for compute_Wq
# ---------------------------------------------------------------------------


class TestPICMChain:
    def test_is_complete(self, planner, executor):
        analysis, plan = _plan(planner, "PICM", PICM_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.is_complete is True

    def test_all_steps_succeed(self, planner, executor):
        analysis, plan = _plan(planner, "PICM", PICM_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        for step_r in result.step_results:
            assert step_r.success is True, f"Step {step_r.formula_id} failed: {step_r.error_message}"

    def test_p0_in_final_variables(self, planner, executor):
        analysis, plan = _plan(planner, "PICM", PICM_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.get_value("P0") is not None

    def test_lq_in_final_variables(self, planner, executor):
        analysis, plan = _plan(planner, "PICM", PICM_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.get_value("Lq") is not None

    def test_wq_in_final_variables(self, planner, executor):
        analysis, plan = _plan(planner, "PICM", PICM_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.get_value("Wq") is not None

    def test_wq_is_positive(self, planner, executor):
        analysis, plan = _plan(planner, "PICM", PICM_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.get_value("Wq") > 0

    def test_three_step_results(self, planner, executor):
        analysis, plan = _plan(planner, "PICM", PICM_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert len(result.step_results) == 3

    def test_picm_wq_step_is_primary(self, planner, executor):
        analysis, plan = _plan(planner, "PICM", PICM_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        wq_step = next(r for r in result.step_results if r.formula_id == "picm_wq")
        assert wq_step.is_primary is True

    def test_picm_p0_step_is_auxiliary(self, planner, executor):
        analysis, plan = _plan(planner, "PICM", PICM_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        p0_step = next(r for r in result.step_results if r.formula_id == "picm_p0")
        assert p0_step.is_primary is False


# ---------------------------------------------------------------------------
# PFCS — 4-step chain for compute_Wq
# ---------------------------------------------------------------------------


class TestPFCSChain:
    def test_is_complete(self, planner, executor):
        analysis, plan = _plan(planner, "PFCS", PFCS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.is_complete is True

    def test_four_step_results(self, planner, executor):
        analysis, plan = _plan(planner, "PFCS", PFCS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert len(result.step_results) == 4

    def test_all_steps_succeed(self, planner, executor):
        analysis, plan = _plan(planner, "PFCS", PFCS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        for step_r in result.step_results:
            assert step_r.success is True, f"Step {step_r.formula_id} failed: {step_r.error_message}"

    def test_wq_is_positive(self, planner, executor):
        analysis, plan = _plan(planner, "PFCS", PFCS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.get_value("Wq") is not None
        assert result.get_value("Wq") > 0

    def test_pfcs_wq_is_primary(self, planner, executor):
        analysis, plan = _plan(planner, "PFCS", PFCS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        wq_step = next(r for r in result.step_results if r.formula_id == "pfcs_wq")
        assert wq_step.is_primary is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_plan_returns_result_with_issue(self, executor):
        analysis = _make_analysis("PICS", PICS_VARS, [])
        plan = ResolutionPlan(
            model_id="PICS",
            objectives=[],
            steps=[],
            available_variables=set(PICS_VARS),
            is_executable=False,
            plan_issues=[],
        )
        result = executor.execute(analysis, plan)
        assert result.is_complete is False
        assert len(result.execution_issues) > 0

    def test_unknown_formula_id_fails_gracefully(self, executor):
        """A plan with a non-existent formula_id must not raise an exception."""
        fake_step = ResolutionStep(
            formula_id="nonexistent_formula_xyz",
            objective_ids=["compute_Wq"],
            produces=["Wq"],
            requires=["lambda_", "mu"],
            depends_on_formulas=[],
            status=StepStatus.EXECUTABLE,
            blocked_by=[],
            is_primary=True,
        )
        plan = ResolutionPlan(
            model_id="PICS",
            objectives=["compute_Wq"],
            steps=[fake_step],
            available_variables={"lambda_", "mu"},
            is_executable=True,
            plan_issues=[],
        )
        analysis = _make_analysis("PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.is_complete is False
        assert len(result.step_results) == 1
        step_r = result.step_results[0]
        assert step_r.success is False
        assert step_r.skipped is False
        assert "nonexistent_formula_xyz" in step_r.error_message

    def test_no_extracted_variables_produces_failures(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", {}, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.is_complete is False
        for step_r in result.step_results:
            assert step_r.success is False

    def test_result_is_deterministic(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        r1 = executor.execute(analysis, plan)
        r2 = executor.execute(analysis, plan)
        assert r1.is_complete == r2.is_complete
        assert r1.get_value("Wq") == r2.get_value("Wq")


# ---------------------------------------------------------------------------
# PlanExecutionResult helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_successful_results_lists_success(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        ok = result.successful_results()
        assert all(r.success for r in ok)

    def test_failed_results_empty_on_success(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.failed_results() == []

    def test_skipped_results_empty_on_success(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.skipped_results() == []

    def test_get_value_returns_none_for_unknown(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        assert result.get_value("nonexistent_variable") is None

    def test_primary_values_keys_are_variable_ids(self, planner, executor):
        analysis, plan = _plan(planner, "PICS", PICS_VARS, ["compute_Wq"])
        result = executor.execute(analysis, plan)
        for key in result.primary_values():
            assert isinstance(key, str)


# ---------------------------------------------------------------------------
# Full pipeline — make_analyzer → analyze → make_planner → plan → make_executor → execute
# ---------------------------------------------------------------------------


class TestFullPipeline:
    def test_pics_end_to_end(self):
        """
        PDF Exercise 01 — PICS.
        Una tienda: 10 clientes/hora, tiempo medio de atencion 4 minutos.
        """
        from domain.entities.analysis import StatementAnalysisRequest
        from domain.services.statement_analyzer import make_analyzer

        analyzer = make_analyzer()
        planner = make_planner()
        executor = make_executor()

        req = StatementAnalysisRequest(
            text=(
                "Una tienda de alimentacion es atendida por una persona. "
                "Llegan 10 clientes por hora con proceso Poisson. "
                "Tiempo medio de atencion 4 minutos. "
                "Calcular tiempo de espera."
            )
        )
        analysis = analyzer.analyze(req)
        assert analysis.identified_model == "PICS"

        plan = planner.plan(analysis)
        assert plan.is_executable is True

        result = executor.execute(analysis, plan)
        assert result.is_complete is True
        assert result.get_value("Wq") is not None
        assert result.get_value("Wq") > 0

    def test_picm_end_to_end(self):
        """
        PDF Exercise 02 — PICM.
        3 personas, 2 llamadas/min, media de atencion 1 minuto.
        """
        from domain.entities.analysis import StatementAnalysisRequest
        from domain.services.statement_analyzer import make_analyzer

        analyzer = make_analyzer()
        planner = make_planner()
        executor = make_executor()

        req = StatementAnalysisRequest(
            text=(
                "Una compania tiene 3 personas para recibir llamadas. "
                "Llegan a razon de 2 por minuto con proceso Poisson. "
                "Media de atencion 1 minuto. "
                "Calcular tiempo de espera."
            )
        )
        analysis = analyzer.analyze(req)
        assert analysis.identified_model == "PICM"

        plan = planner.plan(analysis)
        assert plan.is_executable is True

        result = executor.execute(analysis, plan)
        assert result.is_complete is True
        assert result.get_value("Wq") is not None
        assert result.get_value("Wq") > 0

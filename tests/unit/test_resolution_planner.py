"""
Tests for ResolutionPlanner — Phase 3.

Exercises:
- PICS + compute_Wq: single-step plan (pics_wq), EXECUTABLE
- PICM + compute_Wq: 3-step chain (picm_p0 → picm_lq → picm_wq), all EXECUTABLE
- PICS + compute_Wq + missing mu: plan produced but step BLOCKED
- Multiple objectives: compute_Wq + compute_L → 2 primary steps + shared auxiliaries
- Objective not applicable to model: compute_Pk on PICS → plan_issue
- No model identified: empty plan with plan_issue
- No objectives: empty plan with plan_issue
- PFCS + compute_Wq: 4-step chain (pfcs_p0 → pfcs_l → pfcs_lq → pfcs_wq)
- PFHET + compute_P0: single step (pfhet_p0), EXECUTABLE
- Topological ordering guarantee
- make_planner() factory
- Plan helpers: primary_steps, executable_steps, blocked_steps, step_ids, get_step
- Full pipeline: make_analyzer → analyze → make_planner → plan
"""

import pytest

from domain.entities.analysis import (
    AnalysisConfidence,
    ExtractedVariable,
    StatementAnalysisResult,
)
from domain.entities.plan import ResolutionPlan, ResolutionStep, StepStatus
from domain.services.resolution_planner import ResolutionPlanner, make_planner
from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def knowledge():
    return OfflineKnowledgeRepository().load_all()


@pytest.fixture(scope="module")
def planner(knowledge):
    return ResolutionPlanner(knowledge)


def _make_analysis(
    model_id: str | None,
    variable_ids: list[str],
    objectives: list[str],
) -> StatementAnalysisResult:
    """Build a minimal StatementAnalysisResult for planner tests."""
    result = StatementAnalysisResult()
    result.identified_model = model_id
    result.model_confidence = (
        AnalysisConfidence.HIGH if model_id else AnalysisConfidence.NONE
    )
    for var_id in variable_ids:
        result.extracted_variables.append(
            ExtractedVariable(
                variable_id=var_id,
                raw_value=1.0,
                unit="",
                normalized_value=1.0,
            )
        )
    result.inferred_objectives = list(objectives)
    return result


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_make_planner_returns_planner(self):
        p = make_planner()
        assert isinstance(p, ResolutionPlanner)


# ---------------------------------------------------------------------------
# PICS — compute_Wq
# ---------------------------------------------------------------------------

class TestPICSComputeWq:
    def test_plan_is_executable(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert plan.is_executable is True

    def test_model_id_preserved(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert plan.model_id == "PICS"

    def test_objectives_preserved(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert "compute_Wq" in plan.objectives

    def test_pics_wq_is_in_plan(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert "pics_wq" in plan.step_ids()

    def test_pics_wq_is_primary(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        step = plan.get_step("pics_wq")
        assert step is not None
        assert step.is_primary is True
        assert "compute_Wq" in step.objective_ids

    def test_pics_wq_is_executable(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        step = plan.get_step("pics_wq")
        assert step.status == StepStatus.EXECUTABLE

    def test_no_plan_issues_for_valid_pics(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert plan.plan_issues == []

    def test_available_variables_match_extracted(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert plan.available_variables == {"lambda_", "mu"}


# ---------------------------------------------------------------------------
# PICS — compute_Wq with missing mu (BLOCKED)
# ---------------------------------------------------------------------------

class TestPICSBlocked:
    def test_pics_wq_blocked_without_mu(self, planner):
        analysis = _make_analysis("PICS", ["lambda_"], ["compute_Wq"])
        plan = planner.plan(analysis)
        step = plan.get_step("pics_wq")
        assert step is not None
        assert step.status == StepStatus.BLOCKED

    def test_blocked_by_lists_mu(self, planner):
        analysis = _make_analysis("PICS", ["lambda_"], ["compute_Wq"])
        plan = planner.plan(analysis)
        step = plan.get_step("pics_wq")
        assert "mu" in step.blocked_by

    def test_plan_not_executable_when_primary_blocked(self, planner):
        analysis = _make_analysis("PICS", ["lambda_"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert plan.is_executable is False

    def test_blocked_step_appears_in_blocked_steps(self, planner):
        analysis = _make_analysis("PICS", ["lambda_"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert any(s.formula_id == "pics_wq" for s in plan.blocked_steps())


# ---------------------------------------------------------------------------
# PICM — compute_Wq (3-step chain)
# ---------------------------------------------------------------------------

class TestPICMComputeWq:
    def test_plan_is_executable(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert plan.is_executable is True

    def test_chain_contains_3_steps(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert "picm_p0" in plan.step_ids()
        assert "picm_lq" in plan.step_ids()
        assert "picm_wq" in plan.step_ids()

    def test_picm_wq_is_primary(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Wq"])
        plan = planner.plan(analysis)
        step = plan.get_step("picm_wq")
        assert step.is_primary is True

    def test_picm_p0_is_auxiliary(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Wq"])
        plan = planner.plan(analysis)
        step = plan.get_step("picm_p0")
        assert step.is_primary is False

    def test_topological_order_p0_before_lq(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Wq"])
        plan = planner.plan(analysis)
        ids = plan.step_ids()
        assert ids.index("picm_p0") < ids.index("picm_lq")

    def test_topological_order_lq_before_wq(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Wq"])
        plan = planner.plan(analysis)
        ids = plan.step_ids()
        assert ids.index("picm_lq") < ids.index("picm_wq")

    def test_all_steps_executable_when_vars_present(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert all(s.status == StepStatus.EXECUTABLE for s in plan.steps)

    def test_picm_blocked_without_k(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert plan.is_executable is False
        for s in plan.steps:
            assert "k" in s.blocked_by


# ---------------------------------------------------------------------------
# PICM — compute_Pk (single step, needs picm_p0)
# ---------------------------------------------------------------------------

class TestPICMComputePk:
    def test_compute_pk_includes_p0(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Pk"])
        plan = planner.plan(analysis)
        assert "picm_p0" in plan.step_ids()
        assert "picm_pk" in plan.step_ids()

    def test_picm_pk_is_primary(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Pk"])
        plan = planner.plan(analysis)
        step = plan.get_step("picm_pk")
        assert step.is_primary is True

    def test_compute_pk_executable(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Pk"])
        plan = planner.plan(analysis)
        assert plan.is_executable is True


# ---------------------------------------------------------------------------
# Multiple objectives — compute_Wq + compute_L
# ---------------------------------------------------------------------------

class TestMultipleObjectives:
    def test_pics_two_objectives(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Wq", "compute_L"])
        plan = planner.plan(analysis)
        assert plan.is_executable is True
        assert "pics_wq" in plan.step_ids()
        assert "pics_l" in plan.step_ids()

    def test_two_primary_steps(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Wq", "compute_L"])
        plan = planner.plan(analysis)
        primaries = {s.formula_id for s in plan.primary_steps()}
        assert "pics_wq" in primaries
        assert "pics_l" in primaries

    def test_picm_two_objectives_shared_auxiliary(self, planner):
        analysis = _make_analysis(
            "PICM", ["lambda_", "mu", "k"], ["compute_Wq", "compute_Lq"]
        )
        plan = planner.plan(analysis)
        # picm_p0 should appear only ONCE even though both objectives need it
        assert plan.step_ids().count("picm_p0") == 1
        assert plan.is_executable is True


# ---------------------------------------------------------------------------
# Objective not applicable to model
# ---------------------------------------------------------------------------

class TestObjectiveNotApplicable:
    def test_compute_pk_not_applicable_to_pics(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Pk"])
        plan = planner.plan(analysis)
        # compute_Pk has no target for PICS → plan_issue emitted
        assert any("compute_Pk" in issue for issue in plan.plan_issues)

    def test_plan_empty_when_only_inapplicable_objective(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Pk"])
        plan = planner.plan(analysis)
        assert plan.is_executable is False
        assert len(plan.steps) == 0


# ---------------------------------------------------------------------------
# Edge cases: no model / no objectives
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_no_model_returns_empty_plan(self, planner):
        analysis = _make_analysis(None, ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert plan.model_id is None
        assert plan.steps == []
        assert plan.is_executable is False
        assert len(plan.plan_issues) > 0

    def test_no_objectives_returns_empty_plan(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], [])
        plan = planner.plan(analysis)
        assert plan.steps == []
        assert plan.is_executable is False
        assert len(plan.plan_issues) > 0

    def test_no_variables_produces_blocked_steps(self, planner):
        analysis = _make_analysis("PICS", [], ["compute_Wq"])
        plan = planner.plan(analysis)
        step = plan.get_step("pics_wq")
        assert step is not None
        assert step.status == StepStatus.BLOCKED

    def test_plan_is_deterministic(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Wq"])
        p1 = planner.plan(analysis)
        p2 = planner.plan(analysis)
        assert p1.step_ids() == p2.step_ids()
        assert p1.is_executable == p2.is_executable


# ---------------------------------------------------------------------------
# PFCS — compute_Wq (4-step chain)
# ---------------------------------------------------------------------------

class TestPFCSComputeWq:
    def test_pfcs_wq_chain_has_4_steps(self, planner):
        analysis = _make_analysis("PFCS", ["lambda_", "mu", "M"], ["compute_Wq"])
        plan = planner.plan(analysis)
        for fid in ["pfcs_p0", "pfcs_l", "pfcs_lq", "pfcs_wq"]:
            assert fid in plan.step_ids(), f"Missing step: {fid}"

    def test_pfcs_wq_is_primary(self, planner):
        analysis = _make_analysis("PFCS", ["lambda_", "mu", "M"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert plan.get_step("pfcs_wq").is_primary is True

    def test_pfcs_topological_order(self, planner):
        analysis = _make_analysis("PFCS", ["lambda_", "mu", "M"], ["compute_Wq"])
        plan = planner.plan(analysis)
        ids = plan.step_ids()
        assert ids.index("pfcs_p0") < ids.index("pfcs_l")
        assert ids.index("pfcs_l") < ids.index("pfcs_lq")
        assert ids.index("pfcs_lq") < ids.index("pfcs_wq")

    def test_pfcs_all_executable(self, planner):
        analysis = _make_analysis("PFCS", ["lambda_", "mu", "M"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert plan.is_executable is True
        assert all(s.status == StepStatus.EXECUTABLE for s in plan.steps)

    def test_pfcs_blocked_without_M(self, planner):
        analysis = _make_analysis("PFCS", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert plan.is_executable is False


# ---------------------------------------------------------------------------
# PFHET — compute_P0 (single step)
# ---------------------------------------------------------------------------

class TestPFHETComputeP0:
    def test_pfhet_p0_in_plan(self, planner):
        analysis = _make_analysis(
            "PFHET", ["lambda_", "mu1", "mu2", "M"], ["compute_P0"]
        )
        plan = planner.plan(analysis)
        assert "pfhet_p0" in plan.step_ids()

    def test_pfhet_p0_executable(self, planner):
        analysis = _make_analysis(
            "PFHET", ["lambda_", "mu1", "mu2", "M"], ["compute_P0"]
        )
        plan = planner.plan(analysis)
        assert plan.is_executable is True

    def test_pfhet_wq_not_applicable(self, planner):
        # compute_Wq has no PFHET target in objectives.json
        analysis = _make_analysis(
            "PFHET", ["lambda_", "mu1", "mu2", "M"], ["compute_Wq"]
        )
        plan = planner.plan(analysis)
        assert plan.is_executable is False
        assert any("compute_Wq" in issue for issue in plan.plan_issues)


# ---------------------------------------------------------------------------
# Plan helper methods
# ---------------------------------------------------------------------------

class TestPlanHelpers:
    def test_primary_steps_helper(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Wq"])
        plan = planner.plan(analysis)
        primaries = plan.primary_steps()
        assert all(s.is_primary for s in primaries)
        assert any(s.formula_id == "picm_wq" for s in primaries)

    def test_executable_steps_helper(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu", "k"], ["compute_Wq"])
        plan = planner.plan(analysis)
        execs = plan.executable_steps()
        assert all(s.status == StepStatus.EXECUTABLE for s in execs)

    def test_blocked_steps_helper_when_var_missing(self, planner):
        analysis = _make_analysis("PICM", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        blocked = plan.blocked_steps()
        assert len(blocked) > 0

    def test_get_step_returns_none_for_unknown(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        assert plan.get_step("nonexistent_formula") is None

    def test_step_ids_returns_list(self, planner):
        analysis = _make_analysis("PICS", ["lambda_", "mu"], ["compute_Wq"])
        plan = planner.plan(analysis)
        ids = plan.step_ids()
        assert isinstance(ids, list)
        assert all(isinstance(i, str) for i in ids)


# ---------------------------------------------------------------------------
# Full pipeline: Analyzer → Planner
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_pics_ex01_full_pipeline(self):
        """
        PDF Exercise 01 — PICS.
        Statement: 10 clientes/hora, 4 minutos de atencion, tiempo de espera.
        """
        from domain.services.statement_analyzer import make_analyzer
        from domain.entities.analysis import StatementAnalysisRequest

        analyzer = make_analyzer()
        planner = make_planner()

        req = StatementAnalysisRequest(
            text=(
                "Una tienda de alimentacion es atendida por una persona. "
                "Llegan 10 clientes por hora con proceso Poisson. "
                "Tiempo medio de atencion 4 minutos. "
                "Calcular tiempo de espera."
            )
        )
        analysis = analyzer.analyze(req)
        plan = planner.plan(analysis)

        assert plan.model_id == "PICS"
        assert plan.is_executable is True
        assert any(s.is_primary for s in plan.steps)

    def test_picm_ex02_full_pipeline(self):
        """
        PDF Exercise 02 — PICM.
        3 operators, lambda=2/min, mu=1 min/call.
        """
        from domain.services.statement_analyzer import make_analyzer
        from domain.entities.analysis import StatementAnalysisRequest

        analyzer = make_analyzer()
        planner = make_planner()

        req = StatementAnalysisRequest(
            text=(
                "Una compania tiene 3 personas para recibir llamadas. "
                "Llegan a razon de 2 por minuto con proceso Poisson. "
                "Media de atencion 1 minuto. "
                "Calcular tiempo de espera."
            )
        )
        analysis = analyzer.analyze(req)
        plan = planner.plan(analysis)

        assert plan.model_id == "PICM"
        assert plan.is_executable is True
        assert "picm_wq" in plan.step_ids()

"""
ResolutionPlanner — Phase 3.

Receives a StatementAnalysisResult (Phase 2) and produces a ResolutionPlan:
an ordered sequence of formula steps that need to be computed to satisfy the
inferred objectives, given the extracted variables.

Algorithm
---------
1. For each inferred objective, look up the target formula for the identified
   model in objectives.json.  Objectives without a target for that model are
   skipped (with a plan_issue note).
2. Collect the full set of formula steps needed: target formulas + all their
   transitive formula-level dependencies (from dependencies.json).
3. Topological sort (Kahn's algorithm) — deterministic and cycle-safe.
4. Simulate execution in topological order:
   - Maintain a ``known`` set starting from the extracted variables.
   - For each step, if all ``requires`` variables are in ``known`` →
     EXECUTABLE (add produced variables to ``known`` for downstream steps).
   - Otherwise → BLOCKED (record missing variable ids).
5. Return a ResolutionPlan with is_executable=True iff at least one primary
   step is EXECUTABLE.

Design constraints
------------------
- Pure Python + stdlib; no external dependencies.
- Does NOT call any existing orchestrator, solver or matcher.
- Does NOT perform any mathematical calculation.
- Read-only access to knowledge data.
- Completely deterministic — identical inputs produce identical plans.
- No modification to any existing file.
"""

from __future__ import annotations

from typing import Any

from domain.entities.analysis import StatementAnalysisResult
from domain.entities.plan import ResolutionPlan, ResolutionStep, StepStatus
from infrastructure.repositories.knowledge_repository import OfflineKnowledgeRepository


class ResolutionPlanner:
    """
    Offline, deterministic resolution planner for queue-theory problems.

    Usage::

        repo = OfflineKnowledgeRepository()
        knowledge = repo.load_all()
        planner = ResolutionPlanner(knowledge)
        plan = planner.plan(analysis_result)

    The ``knowledge`` dict is the direct output of
    ``OfflineKnowledgeRepository.load_all()``::

        {
            "dependencies": list[dict],   # from dependencies.json
            "objectives":   list[dict],   # from objectives.json
            ...
        }
    """

    def __init__(self, knowledge: dict[str, Any]) -> None:
        # Build formula_id → dep-info lookup
        self._deps: dict[str, dict[str, Any]] = {}
        for dep in knowledge.get("dependencies", []):
            fid = dep.get("formula_id")
            if fid:
                self._deps[fid] = dep

        # Build objective_id → {model_id → formula_id} lookup
        # When both a specific model and GENERAL are present, the specific
        # model takes priority.
        self._obj_targets: dict[str, dict[str, str]] = {}
        for obj in knowledge.get("objectives", []):
            obj_id = obj.get("id")
            if not obj_id:
                continue
            targets: dict[str, str] = {}
            for target in obj.get("targets", []):
                model = target.get("model")
                formula_id = target.get("formula_id")
                if model and formula_id:
                    targets[model] = formula_id
            self._obj_targets[obj_id] = targets

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self, analysis: StatementAnalysisResult) -> ResolutionPlan:
        """
        Build a ResolutionPlan from a StatementAnalysisResult.

        Parameters
        ----------
        analysis : StatementAnalysisResult
            Output of StatementAnalyzer.analyze() — contains identified model,
            extracted variables, and inferred objectives.

        Returns
        -------
        ResolutionPlan
            Ordered steps (may be empty) with is_executable flag.
        """
        model_id = analysis.identified_model
        objectives = list(analysis.inferred_objectives)
        available_variables: set[str] = {
            ev.variable_id for ev in analysis.extracted_variables
        }
        plan_issues: list[str] = []

        # --- Guard: no model ---
        if not model_id:
            plan_issues.append(
                "No se pudo identificar el modelo de colas. "
                "El plan no puede generarse sin un modelo."
            )
            return ResolutionPlan(
                model_id=None,
                objectives=objectives,
                steps=[],
                available_variables=available_variables,
                is_executable=False,
                plan_issues=plan_issues,
            )

        # --- Guard: no objectives ---
        if not objectives:
            plan_issues.append(
                "No se infirieron objetivos del enunciado. "
                "El plan no puede generarse sin al menos un objetivo."
            )
            return ResolutionPlan(
                model_id=model_id,
                objectives=objectives,
                steps=[],
                available_variables=available_variables,
                is_executable=False,
                plan_issues=plan_issues,
            )

        # --- Map objectives → target formula ids ---
        objective_to_formula: dict[str, str] = {}  # obj_id → formula_id
        for obj_id in objectives:
            targets = self._obj_targets.get(obj_id, {})
            # Prefer the model-specific formula over GENERAL
            formula_id = targets.get(model_id) or targets.get("GENERAL")
            if formula_id:
                objective_to_formula[obj_id] = formula_id
            else:
                plan_issues.append(
                    f"El objetivo '{obj_id}' no tiene formula definida para el "
                    f"modelo '{model_id}'. Se omite de este plan."
                )

        if not objective_to_formula:
            plan_issues.append(
                "Ninguno de los objetivos inferidos es aplicable al modelo "
                f"'{model_id}'."
            )
            return ResolutionPlan(
                model_id=model_id,
                objectives=objectives,
                steps=[],
                available_variables=available_variables,
                is_executable=False,
                plan_issues=plan_issues,
            )

        # --- Collect all formula ids (targets + transitive deps) ---
        primary_formula_ids = set(objective_to_formula.values())
        all_formula_ids = self._collect_all(primary_formula_ids)

        # Report and discard any formula referenced but not defined in knowledge
        unknown_formulas = all_formula_ids - set(self._deps.keys())
        if unknown_formulas:
            for fid in sorted(unknown_formulas):
                plan_issues.append(
                    f"Formula '{fid}' referenciada como dependencia pero no "
                    f"definida en el knowledge base. Se omite."
                )
            all_formula_ids -= unknown_formulas

        if not all_formula_ids:
            plan_issues.append(
                "No quedaron formulas validas tras filtrar referencias desconocidas."
            )
            return ResolutionPlan(
                model_id=model_id,
                objectives=objectives,
                steps=[],
                available_variables=available_variables,
                is_executable=False,
                plan_issues=plan_issues,
            )

        # --- Topological sort ---
        sorted_formula_ids = self._topological_sort(all_formula_ids)

        # --- Build formula_id → objective_ids reverse mapping ---
        formula_to_objectives: dict[str, list[str]] = {}
        for obj_id, fid in objective_to_formula.items():
            formula_to_objectives.setdefault(fid, []).append(obj_id)

        # --- Simulate execution: propagate known variables through the plan ---
        # ``known`` starts with the variables extracted from the statement.
        # When a step is EXECUTABLE, its produced variables become available
        # to downstream steps that explicitly list them in ``requires``.
        known: set[str] = set(available_variables)
        steps: list[ResolutionStep] = []

        for fid in sorted_formula_ids:
            dep_info = self._deps[fid]
            requires: list[str] = dep_info.get("requires", [])
            produces: list[str] = dep_info.get("produces", [])
            # Only include deps that are actually in the plan (unknown formulas
            # have been stripped from all_formula_ids already)
            depends_on: list[str] = [
                d for d in dep_info.get("depends_on_formulas", [])
                if d in all_formula_ids
            ]
            obj_ids: list[str] = formula_to_objectives.get(fid, [])
            is_primary: bool = bool(obj_ids)

            missing: list[str] = [v for v in requires if v not in known]
            if missing:
                status = StepStatus.BLOCKED
            else:
                status = StepStatus.EXECUTABLE
                # Make produced variables available to downstream steps
                known.update(produces)

            steps.append(
                ResolutionStep(
                    formula_id=fid,
                    objective_ids=sorted(obj_ids),  # deterministic order
                    produces=produces,
                    requires=requires,
                    depends_on_formulas=depends_on,
                    status=status,
                    blocked_by=sorted(missing),
                    is_primary=is_primary,
                )
            )

        is_executable = any(
            s.is_primary and s.status == StepStatus.EXECUTABLE for s in steps
        )

        return ResolutionPlan(
            model_id=model_id,
            objectives=objectives,
            steps=steps,
            available_variables=available_variables,
            is_executable=is_executable,
            plan_issues=plan_issues,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_all(self, start_formula_ids: set[str]) -> set[str]:
        """
        BFS expansion: collect ``start_formula_ids`` plus all transitive
        formula-level dependencies as recorded in dependencies.json.
        """
        result: set[str] = set()
        queue = list(start_formula_ids)
        while queue:
            fid = queue.pop()
            if fid in result:
                continue
            result.add(fid)
            dep_info = self._deps.get(fid)
            if dep_info:
                for prereq in dep_info.get("depends_on_formulas", []):
                    if prereq not in result:
                        queue.append(prereq)
        return result

    def _topological_sort(self, formula_ids: set[str]) -> list[str]:
        """
        Kahn's algorithm over the subset of the dependency DAG defined by
        ``formula_ids``.  Deterministic (sorted queue) and cycle-safe
        (remaining nodes appended at end if a cycle is detected).
        """
        in_degree: dict[str, int] = {fid: 0 for fid in formula_ids}
        adj: dict[str, list[str]] = {fid: [] for fid in formula_ids}

        for fid in formula_ids:
            dep_info = self._deps.get(fid, {})
            for prereq in dep_info.get("depends_on_formulas", []):
                if prereq in formula_ids:
                    adj[prereq].append(fid)
                    in_degree[fid] += 1

        # Start from nodes with no prerequisites; sort for determinism
        queue: list[str] = sorted(
            fid for fid in formula_ids if in_degree[fid] == 0
        )
        result: list[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in sorted(adj[node]):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Cycle detection: append any unvisited nodes (should never happen
        # with a valid knowledge base)
        if len(result) < len(formula_ids):
            remaining = sorted(formula_ids - set(result))
            result.extend(remaining)

        return result


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def make_planner() -> ResolutionPlanner:
    """
    Convenience factory that loads knowledge from the default path and
    returns a ready-to-use ResolutionPlanner.
    """
    knowledge = OfflineKnowledgeRepository().load_all()
    return ResolutionPlanner(knowledge)

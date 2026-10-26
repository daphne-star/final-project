"""Operational analysis tools.

Like the financial calculators these are pure: they structure and check what
the caller supplied rather than inventing capacity, headcount, or dates. The
COO is the agent that uses them, and its instructions forbid inventing exactly
these inputs, so a tool that guessed them would undercut the agent.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorkstreamLoad(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    required_person_weeks: float = Field(gt=0)
    required_skills: list[str] = Field(default_factory=list)


class CapacityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available_people: int = Field(gt=0, description="People who can do this work")
    weeks_available: float = Field(gt=0, description="Calendar weeks in the window")
    existing_commitment_rate: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Fraction of their time already committed, e.g. 0.7",
    )
    workstreams: list[WorkstreamLoad] = Field(min_length=1, max_length=20)


class CapacityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available_person_weeks: float
    required_person_weeks: float
    surplus_person_weeks: float
    utilisation_rate: float
    feasible: bool
    verdict: str
    calculation: str
    skills_required: list[str]
    caveats: list[str]


def assess_execution_capacity(data: CapacityInput) -> CapacityResult:
    """Can this team do this work in this window?"""
    free_rate = 1 - data.existing_commitment_rate
    available = data.available_people * data.weeks_available * free_rate
    required = sum(w.required_person_weeks for w in data.workstreams)
    surplus = available - required
    utilisation = required / available if available > 0 else float("inf")

    if available <= 0:
        verdict = "No capacity at all: the team is fully committed in this window."
    elif utilisation <= 0.8:
        verdict = (
            f"Feasible with slack. The plan uses {utilisation:.0%} of free capacity."
        )
    elif utilisation <= 1.0:
        verdict = (
            f"Feasible but tight at {utilisation:.0%} of free capacity. No room for "
            "the first failed attempt, onboarding, or anything unplanned."
        )
    else:
        verdict = (
            f"Not feasible as scoped: {utilisation:.0%} of free capacity, short by "
            f"{abs(surplus):.1f} person-weeks. Cut scope, extend the window, or add people."
        )

    skills = sorted({s for w in data.workstreams for s in w.required_skills})

    return CapacityResult(
        available_person_weeks=round(available, 1),
        required_person_weeks=round(required, 1),
        surplus_person_weeks=round(surplus, 1),
        utilisation_rate=round(utilisation, 3),
        feasible=surplus >= 0,
        verdict=verdict,
        calculation=(
            f"{data.available_people} people x {data.weeks_available:.0f} weeks x "
            f"{free_rate:.0%} free = {available:.1f} person-weeks available; "
            f"{required:.1f} person-weeks required across "
            f"{len(data.workstreams)} workstream(s)."
        ),
        skills_required=skills,
        caveats=[
            "Person-weeks assume fungible people. Named skills may not be.",
            "Ramp-up, coordination overhead, and rework are not modelled.",
        ],
    )


class DependencyTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    depends_on: list[str] = Field(default_factory=list)
    duration_weeks: float = Field(default=1.0, gt=0)


class DependencyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[DependencyTask] = Field(min_length=1, max_length=40)


class DependencyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordered_stages: list[list[str]]
    critical_path: list[str]
    critical_path_weeks: float
    blocking_tasks: list[str]
    unresolved_dependencies: list[str]
    has_cycle: bool
    notes: list[str]


def identify_operational_dependencies(data: DependencyInput) -> DependencyResult:
    """Topologically order tasks and find the critical path.

    Returns the cycle condition rather than raising: a plan with circular
    dependencies is a real finding the COO should report, not a tool error.
    """
    by_id = {t.id: t for t in data.tasks}
    known = set(by_id)

    unresolved = sorted(
        f"{t.id} -> {dep}" for t in data.tasks for dep in t.depends_on if dep not in known
    )

    remaining = {t.id: {d for d in t.depends_on if d in known} for t in data.tasks}
    stages: list[list[str]] = []
    done: set[str] = set()

    while remaining:
        ready = sorted(tid for tid, deps in remaining.items() if deps <= done)
        if not ready:
            return DependencyResult(
                ordered_stages=stages,
                critical_path=[],
                critical_path_weeks=0.0,
                blocking_tasks=sorted(remaining),
                unresolved_dependencies=unresolved,
                has_cycle=True,
                notes=[
                    (
                        "These tasks depend on each other in a cycle and cannot be "
                        "sequenced as written. Break the cycle before planning."
                    ),
                ],
            )
        stages.append(ready)
        done.update(ready)
        for tid in ready:
            remaining.pop(tid)

    # Longest path by duration, which is the schedule-determining one.
    finish: dict[str, float] = {}
    predecessor: dict[str, str | None] = {}
    for stage in stages:
        for tid in stage:
            task = by_id[tid]
            deps = [d for d in task.depends_on if d in finish]
            if deps:
                worst = max(deps, key=lambda d: finish[d])
                start = finish[worst]
                predecessor[tid] = worst
            else:
                start = 0.0
                predecessor[tid] = None
            finish[tid] = start + task.duration_weeks

    end = max(finish, key=lambda t: finish[t]) if finish else None
    path: list[str] = []
    cursor = end
    while cursor is not None:
        path.append(cursor)
        cursor = predecessor.get(cursor)
    path.reverse()

    blocking = sorted(
        tid
        for tid in by_id
        if sum(1 for t in data.tasks if tid in t.depends_on) >= 2
    )

    return DependencyResult(
        ordered_stages=stages,
        critical_path=path,
        critical_path_weeks=round(finish[end], 1) if end else 0.0,
        blocking_tasks=blocking,
        unresolved_dependencies=unresolved,
        has_cycle=False,
        notes=[
            f"{len(stages)} stage(s); work within a stage can run in parallel.",
            "Durations are the ones supplied, not estimates produced here.",
        ]
        + (
            [f"{len(unresolved)} dependency reference(s) point at unknown tasks."]
            if unresolved
            else []
        ),
    )


class PlanTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    owner: str | None = None
    effort_weeks: float = Field(default=1.0, gt=0)
    depends_on: list[str] = Field(default_factory=list)


class ImplementationPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str
    tasks: list[PlanTask] = Field(min_length=1, max_length=30)
    weeks_per_phase: float = Field(default=4.3, gt=0, description="Weeks in each 30-day phase")


class PlanPhase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window: str
    tasks: list[str]
    total_effort_weeks: float


class ImplementationPlanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str
    phases: list[PlanPhase]
    unscheduled_tasks: list[str]
    total_effort_weeks: float
    notes: list[str]


def build_implementation_plan(data: ImplementationPlanInput) -> ImplementationPlanResult:
    """Pack supplied tasks into 30/60/90-day windows by effort.

    Uses relative windows only. The spec forbids inventing calendar dates and
    this tool has no idea when the work starts.
    """
    windows = ["0-30 days", "30-60 days", "60-90 days"]
    capacity = data.weeks_per_phase
    phases: list[PlanPhase] = [PlanPhase(window=w, tasks=[], total_effort_weeks=0.0) for w in windows]

    unscheduled: list[str] = []
    for task in data.tasks:
        placed = False
        for phase in phases:
            if phase.total_effort_weeks + task.effort_weeks <= capacity:
                label = f"{task.description}" + (f" [{task.owner}]" if task.owner else "")
                phase.tasks.append(label)
                phase.total_effort_weeks = round(
                    phase.total_effort_weeks + task.effort_weeks, 2
                )
                placed = True
                break
        if not placed:
            unscheduled.append(task.description)

    total = round(sum(t.effort_weeks for t in data.tasks), 2)
    notes = [
        "Windows are relative to the start date, which this tool does not know.",
        f"Each window assumes {capacity:.1f} weeks of sequential effort.",
    ]
    if unscheduled:
        notes.append(
            f"{len(unscheduled)} task(s) did not fit in 90 days. The plan is "
            "over-scoped for the window, which is a finding, not a formatting problem."
        )

    return ImplementationPlanResult(
        objective=data.objective,
        phases=phases,
        unscheduled_tasks=unscheduled,
        total_effort_weeks=total,
        notes=notes,
    )

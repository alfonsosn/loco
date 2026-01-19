"""Plan mode for loco - multi-step task planning and execution."""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from loco.config import get_config_dir


class StepStatus(str, Enum):
    """Status of a plan step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStatus(str, Enum):
    """Status of a plan."""
    DRAFT = "draft"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PlanStep:
    """A single step in a plan."""

    id: str
    description: str
    status: StepStatus = StepStatus.PENDING
    result: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanStep":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            status=StepStatus(data.get("status", "pending")),
            result=data.get("result"),
            error=data.get("error"),
        )


@dataclass
class Plan:
    """A multi-step execution plan."""

    id: str
    task: str
    steps: list[PlanStep]
    status: PlanStatus = PlanStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    approved_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "task": self.task,
            "steps": [step.to_dict() for step in self.steps],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            task=data["task"],
            steps=[PlanStep.from_dict(s) for s in data["steps"]],
            status=PlanStatus(data.get("status", "draft")),
            created_at=datetime.fromisoformat(data["created_at"]),
            approved_at=datetime.fromisoformat(data["approved_at"]) if data.get("approved_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )

    def get_current_step(self) -> PlanStep | None:
        """Get the current step being executed."""
        for step in self.steps:
            if step.status == StepStatus.IN_PROGRESS:
                return step
        return None

    def get_next_step(self) -> PlanStep | None:
        """Get the next pending step."""
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                return step
        return None

    def get_progress(self) -> tuple[int, int]:
        """Get (completed, total) step counts."""
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return completed, len(self.steps)


def get_plans_dir() -> Path:
    """Get the directory where plans are stored."""
    plans_dir = get_config_dir() / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    return plans_dir


def save_plan(plan: Plan) -> None:
    """Save a plan to disk."""
    plans_dir = get_plans_dir()
    plan_file = plans_dir / f"{plan.id}.json"

    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(plan.to_dict(), f, indent=2)


def load_plan(plan_id: str) -> Plan | None:
    """Load a plan from disk."""
    plans_dir = get_plans_dir()
    plan_file = plans_dir / f"{plan_id}.json"

    if not plan_file.exists():
        return None

    with open(plan_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    return Plan.from_dict(data)


def list_plans() -> list[Plan]:
    """List all saved plans."""
    plans_dir = get_plans_dir()
    plans = []

    for plan_file in plans_dir.glob("*.json"):
        try:
            with open(plan_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            plans.append(Plan.from_dict(data))
        except Exception:
            continue

    # Sort by created_at descending
    plans.sort(key=lambda p: p.created_at, reverse=True)
    return plans


def create_plan(task: str, steps: list[str]) -> Plan:
    """Create a new plan from a task and list of step descriptions."""
    plan_id = str(uuid.uuid4())[:8]

    plan_steps = [
        PlanStep(id=f"step-{i+1}", description=desc)
        for i, desc in enumerate(steps)
    ]

    return Plan(
        id=plan_id,
        task=task,
        steps=plan_steps,
    )


PLANNING_SYSTEM_PROMPT = """You are a planning assistant. Your job is to break down complex tasks into clear, actionable steps.

When given a task:
1. Explore the codebase to understand the context
2. Identify all files that need to be modified or created
3. Break the task into sequential, logical steps
4. Each step should be specific and actionable
5. Consider dependencies between steps
6. Think about testing and validation

Respond with a numbered list of steps. Each step should:
- Be clear and specific
- Mention which files will be affected
- Describe what changes will be made
- Be completable in a reasonable amount of time

Example format:
1. Read the existing authentication module to understand the current flow
2. Create a new middleware file for JWT validation
3. Update the user model to include a token field
4. Modify the login endpoint to generate and return JWTs
5. Add tests for the new JWT authentication flow
6. Update the API documentation

Be thorough but concise. Focus on the "what" and "why", not the detailed "how" (that comes during execution).
"""


def format_plan_for_display(plan: Plan) -> str:
    """Format a plan for display to the user."""
    lines = []
    lines.append(f"[bold]Plan: {plan.task}[/bold]")
    lines.append(f"[dim]ID: {plan.id} | Status: {plan.status.value}[/dim]")
    lines.append("")

    completed, total = plan.get_progress()
    if plan.status in (PlanStatus.EXECUTING, PlanStatus.COMPLETED):
        lines.append(f"[dim]Progress: {completed}/{total} steps completed[/dim]")
        lines.append("")

    for i, step in enumerate(plan.steps, 1):
        status_icon = {
            StepStatus.PENDING: "○",
            StepStatus.IN_PROGRESS: "◐",
            StepStatus.COMPLETED: "●",
            StepStatus.FAILED: "✗",
            StepStatus.SKIPPED: "⊘",
        }.get(step.status, "○")

        status_color = {
            StepStatus.PENDING: "dim",
            StepStatus.IN_PROGRESS: "yellow",
            StepStatus.COMPLETED: "green",
            StepStatus.FAILED: "red",
            StepStatus.SKIPPED: "dim",
        }.get(step.status, "dim")

        lines.append(f"[{status_color}]{status_icon}[/{status_color}] {i}. {step.description}")

        if step.error:
            lines.append(f"   [red]Error: {step.error}[/red]")

    return "\n".join(lines)

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


TASK_STAGES = [
    "START",
    "ORDER_IDENTIFIED",
    "ORDER_VERIFIED",
    "AFTERSALE_TYPE_CONFIRMED",
    "REASON_COLLECTED",
    "POLICY_CHECKED",
    "USER_CONFIRMED",
    "TICKET_CREATED",
    "DONE",
]


@dataclass
class TaskStep:
    name: str
    status: str = "pending"
    tool_name: str | None = None
    reason: str = ""


@dataclass
class TaskState:
    task_id: str
    goal: str
    stage: str = "START"
    aftersale_priority: list[str] = field(default_factory=list)
    steps: list[TaskStep] = field(default_factory=list)
    collected: dict[str, Any] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    last_error: dict[str, Any] | None = None
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [asdict(step) for step in self.steps]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TaskState | None":
        if not data:
            return None
        steps = [TaskStep(**item) for item in data.get("steps", []) if isinstance(item, dict)]
        return cls(
            task_id=str(data.get("task_id") or "TASK"),
            goal=str(data.get("goal") or ""),
            stage=str(data.get("stage") or "START"),
            aftersale_priority=list(data.get("aftersale_priority") or []),
            steps=steps,
            collected=dict(data.get("collected") or {}),
            missing_slots=list(data.get("missing_slots") or []),
            last_error=data.get("last_error"),
            status=str(data.get("status") or "active"),
        )


def get_task_state(memory: Any) -> TaskState | None:
    context = getattr(memory, "current_business_context", {}) or {}
    task = context.get("task_state")
    return TaskState.from_dict(task) if isinstance(task, dict) else None


def set_task_state(memory: Any, task: TaskState | None) -> None:
    context = getattr(memory, "current_business_context", None)
    if context is None:
        return
    if task is None:
        context.pop("task_state", None)
    else:
        context["task_state"] = task.to_dict()


def update_task_after_tool(
    memory: Any,
    *,
    intent: str | None,
    tool_name: str | None,
    arguments: dict[str, Any] | None,
    tool_result: dict[str, Any] | None,
) -> TaskState | None:
    task = get_task_state(memory)
    if not task:
        return None

    args = arguments or {}
    data = (tool_result or {}).get("result")
    data = data if isinstance(data, dict) else {}
    success = bool((tool_result or {}).get("success")) and data.get("success", True) is not False

    for key in ["order_id", "customer_id", "product_id", "ticket_type", "reason", "package_status"]:
        if args.get(key):
            task.collected[key] = args[key]

    found_order = data.get("primary_order_id") or data.get("order_id")
    if found_order:
        task.collected["order_id"] = found_order
        task.stage = "ORDER_IDENTIFIED"

    if intent == "screenshot_order_review":
        analyses = data.get("analyses") or []
        validation = {}
        if analyses and isinstance(analyses[0], dict):
            validation = analyses[0].get("database_validation") or {}
        if validation.get("matched"):
            task.stage = "ORDER_VERIFIED"
        elif found_order:
            task.stage = "ORDER_IDENTIFIED"

    if intent in {"aftersale_check", "ticket_create"} and args.get("ticket_type"):
        task.stage = "AFTERSALE_TYPE_CONFIRMED"

    if intent in {"aftersale_check", "ticket_create"} and args.get("reason"):
        task.stage = "REASON_COLLECTED"

    if intent == "aftersale_check" and data.get("rule_result"):
        task.stage = "POLICY_CHECKED"
        task.collected["policy_decision"] = data.get("decision") or (data.get("rule_result") or {}).get("decision")

    if intent == "ticket_create" and data.get("ticket"):
        task.stage = "TICKET_CREATED"
        task.status = "done"

    if not success:
        task.last_error = {
            "intent": intent,
            "tool_name": tool_name,
            "message": data.get("message") or (tool_result or {}).get("message"),
        }

    set_task_state(memory, task)
    return task

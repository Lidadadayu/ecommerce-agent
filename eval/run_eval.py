from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.intent_slot_extractor import extract_intent_slots
from agent.order_screenshot_validator import validate_screenshot_against_order
from agent.rule_router import route_user_query
from tools.business_tools import check_aftersale_eligibility


EVAL_DIR = Path(__file__).resolve().parent


def _load_jsonl(name: str) -> list[dict[str, Any]]:
    path = EVAL_DIR / name
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _pct(ok: int, total: int) -> float:
    return round(ok / total * 100, 2) if total else 0.0


def eval_intent() -> dict[str, Any]:
    rows = _load_jsonl("intent_cases.jsonl")
    intent_ok = tool_ok = order_ok = 0
    latencies = []
    failures = 0
    for row in rows:
        start = time.perf_counter()
        try:
            route = route_user_query(row["query"])
            slots = extract_intent_slots(row["query"])
            latencies.append((time.perf_counter() - start) * 1000)
            intent_ok += route.get("intent") == row.get("expected_intent")
            tool_ok += route.get("tool_name") == row.get("expected_tool")
            order_ok += slots.get("order_id") == row.get("expected_order_id")
        except Exception:
            failures += 1
    total = len(rows)
    return {
        "intent_accuracy": _pct(intent_ok, total),
        "tool_call_accuracy": _pct(tool_ok, total),
        "order_id_extraction_accuracy": _pct(order_ok, total),
        "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "failure_rate": _pct(failures, total),
        "total": total,
    }


def eval_aftersale() -> dict[str, Any]:
    rows = _load_jsonl("aftersale_cases.jsonl")
    ok = failures = 0
    for row in rows:
        try:
            result = check_aftersale_eligibility(
                row["order_id"],
                row["ticket_type"],
                row["reason"],
                application_time=row.get("application_time"),
                package_complete=bool(row.get("package_complete", True)),
            )
            ok += result.get("eligible") == row.get("expected_eligible")
        except Exception:
            failures += 1
    total = len(rows)
    return {"aftersale_decision_accuracy": _pct(ok, total), "failure_rate": _pct(failures, total), "total": total}


def eval_screenshot() -> dict[str, Any]:
    rows = _load_jsonl("screenshot_cases.jsonl")
    ok = field_ok = failures = 0
    for row in rows:
        try:
            result = validate_screenshot_against_order(row["analysis"], customer_id=row.get("customer_id"))
            ok += result.get("matched") == row.get("expected_matched")
            expected_field = row.get("expected_mismatch_field")
            fields = {item.get("field") for item in result.get("mismatches") or []}
            field_ok += (not expected_field) or expected_field in fields
        except Exception:
            failures += 1
    total = len(rows)
    return {"screenshot_field_accuracy": _pct(ok, total), "mismatch_field_accuracy": _pct(field_ok, total), "failure_rate": _pct(failures, total), "total": total}


def main() -> None:
    report = {
        "intent": eval_intent(),
        "aftersale": eval_aftersale(),
        "screenshot": eval_screenshot(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

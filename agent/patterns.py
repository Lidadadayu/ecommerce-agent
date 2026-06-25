from __future__ import annotations

import re

ORDER_ID_PATTERN = re.compile(r"O\d{12}")
PRODUCT_ID_PATTERN = re.compile(r"P\d{5}")
TICKET_ID_PATTERN = re.compile(r"T\d{14}[A-Z0-9]{6}")


def extract_order_id(text: str) -> str | None:
    m = ORDER_ID_PATTERN.search(text or "")
    return m.group(0) if m else None


def extract_order_ids(text: str) -> list[str]:
    return ORDER_ID_PATTERN.findall(text or "")


def extract_product_id(text: str) -> str | None:
    m = PRODUCT_ID_PATTERN.search(text or "")
    return m.group(0) if m else None


def extract_product_ids(text: str) -> list[str]:
    return PRODUCT_ID_PATTERN.findall(text or "")


def extract_ticket_id(text: str) -> str | None:
    m = TICKET_ID_PATTERN.search(text or "")
    return m.group(0) if m else None


def extract_ticket_ids(text: str) -> list[str]:
    return TICKET_ID_PATTERN.findall(text or "")


def is_only_order_id(text: str) -> bool:
    return bool(ORDER_ID_PATTERN.fullmatch((text or "").strip()))

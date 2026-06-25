from __future__ import annotations

import io

from fastapi.testclient import TestClient

from api.server import create_app
from frontend_api_client import AgentAPIClient


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT"
    b"\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfeA"
    b"\xe2&\x0b\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_frontend_api_client_has_upload_methods() -> None:
    client = AgentAPIClient("http://127.0.0.1:8001")
    for name in ["upload_order_screenshot", "list_evidences", "get_evidence", "evidence_file_url"]:
        assert hasattr(client, name)


def test_upload_route_saves_and_lists_evidence() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/uploads/order-screenshot",
        data={
            "customer_id": "C10001",
            "session_id": "TEST_UPLOAD_FLOW",
            "order_id": "O202605010001",
            "note": "pytest upload evidence flow",
        },
        files={"file": ("order_screenshot_test.png", io.BytesIO(PNG_1X1), "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    evidence_id = payload["evidence"]["evidence_id"]
    assert evidence_id.startswith("EV")

    listed = client.get(
        "/api/uploads/evidences",
        params={"customer_id": "C10001", "session_id": "TEST_UPLOAD_FLOW", "limit": 10},
    )
    assert listed.status_code == 200
    rows = listed.json()["evidences"]
    assert any(row.get("evidence_id") == evidence_id for row in rows)


def test_upload_response_is_fast_metadata_only() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/uploads/order-screenshot",
        data={
            "customer_id": "C10001",
            "session_id": "TEST_UPLOAD_ANALYSIS",
            "order_id": "O202605010001",
            "note": "订单截图 O202605010001",
        },
        files={"file": ("order_O202605010001.png", io.BytesIO(PNG_1X1), "image/png")},
    )

    assert response.status_code == 200
    evidence = response.json()["evidence"]
    assert evidence["evidence_id"].startswith("EV")
    assert evidence.get("order_id") == "O202605010001"
    # 上传接口只保存凭证，不同步调用视觉模型，避免 Streamlit 点击发送后长时间阻塞。
    assert "screenshot_analysis" not in evidence


def test_agent_reviews_uploaded_order_screenshot_from_memory() -> None:
    from agent.agent import run_agent
    from agent.evidence_store import save_order_screenshot

    record = save_order_screenshot(
        content=PNG_1X1,
        filename="order_O202605010001.png",
        customer_id="C10001",
        session_id="TEST_AGENT_SCREENSHOT",
        order_id="O202605010001",
        note="订单截图 O202605010001",
    )

    memory = {
        "customer_id": "C10001",
        "user_id": "C10001",
        "current_order_id": "O202605010001",
        "current_business_context": {
            "order_id": "O202605010001",
            "evidence_ids": [record["evidence_id"]],
            "evidence_files": [record],
        },
    }

    result = run_agent("我上传了一张订单截图，请帮我识别截图中的订单信息", memory=memory, user_id="C10001")
    answer = result.get("final_answer") or ""
    assert "订单截图" in answer
    assert "O202605010001" in answer
    assert "查物流" in answer or "申请退货" in answer

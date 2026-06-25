from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="测试订单截图上传接口。")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--customer-id", default="C10001")
    parser.add_argument("--session-id", default="TEST_UPLOAD_SESSION")
    parser.add_argument("--order-id", default="O202605010001")
    args = parser.parse_args()

    from frontend_api_client import AgentAPIClient

    client = AgentAPIClient(args.api_base_url)

    # 1x1 png
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
        b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT"
        b"\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfeA"
        b"\xe2&\x0b\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    class DummyFile(io.BytesIO):
        name = "order_screenshot_test.png"
        type = "image/png"

        def getvalue(self) -> bytes:  # type: ignore[override]
            return png_bytes

    result = client.upload_order_screenshot(
        file_obj=DummyFile(png_bytes),
        customer_id=args.customer_id,
        session_id=args.session_id,
        order_id=args.order_id,
        note="自动化测试上传订单截图",
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not result.get("success"):
        raise SystemExit("上传失败。")

    evidence = result.get("evidence") or {}
    evidence_id = evidence.get("evidence_id")
    if not evidence_id:
        raise SystemExit("没有返回 evidence_id。")

    listed = client.list_evidences(customer_id=args.customer_id, session_id=args.session_id, limit=10)
    print(json.dumps(listed, ensure_ascii=False, indent=2))

    if not any(x.get("evidence_id") == evidence_id for x in listed.get("evidences", [])):
        raise SystemExit("列表中没有刚上传的凭证。")

    print()
    print("订单截图上传接口测试通过。")


if __name__ == "__main__":
    main()

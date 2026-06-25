from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    from frontend_api_client import AgentAPIClient

    client = AgentAPIClient("http://127.0.0.1:8001")
    required = ["upload_order_screenshot", "list_evidences", "get_evidence", "evidence_file_url"]

    missing = [name for name in required if not hasattr(client, name)]
    if missing:
        print("缺少方法：")
        for name in missing:
            print("-", name)
        raise SystemExit(1)

    print("上传客户端方法检查通过：")
    for name in required:
        print(f"- {name}")


if __name__ == "__main__":
    main()

from __future__ import annotations

"""
兼容入口。

当前最终前端是 app_api_streaming.py。
本脚本转发到 scripts/run_web_streaming.py。
"""

from scripts.run_web_streaming import main


if __name__ == "__main__":
    main()

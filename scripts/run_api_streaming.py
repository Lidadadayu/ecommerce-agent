from __future__ import annotations

"""
兼容入口。

现在 api.server 默认已经注册 /api/chat/stream，所以这个脚本只转发到 run_api.py。
保留它是为了避免旧文档或旧习惯中的命令失效。
"""

from scripts.run_api import main


if __name__ == "__main__":
    main()

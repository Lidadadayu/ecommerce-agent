from __future__ import annotations

"""
兼容入口。

当前最终前端是 app_api_streaming.py。
保留本文件是为了避免旧启动命令失效：

    streamlit run app_api.py

等价于运行：

    streamlit run app_api_streaming.py
"""

from app_api_streaming import main


if __name__ == "__main__":
    main()

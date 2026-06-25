from __future__ import annotations

import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "domain_packs" / "robot_vacuum" / "raw"
OUT_DIR = PROJECT_ROOT / "data" / "knowledge" / "robot_vacuum"


FILE_CONFIGS = {
    "故障排除": {
        "output": "robot_vacuum_troubleshooting.md",
        "title": "扫地/扫拖一体机器人故障检测与修复",
        "category": "robot_vacuum_troubleshooting",
        "tags": "扫地机器人, 扫拖一体机器人, 故障排查, 维修, 售后",
        "parser": "troubleshooting",
    },
    "扫地机器人100问": {
        "output": "robot_vacuum_faq_100.md",
        "title": "扫地机器人100问",
        "category": "robot_vacuum_faq",
        "tags": "扫地机器人, FAQ, 基础问题, 导航, 使用",
        "parser": "faq",
    },
    "扫地机器人100问2": {
        "output": "robot_vacuum_faq_100_2.md",
        "title": "扫地机器人常见问题及解答",
        "category": "robot_vacuum_faq",
        "tags": "扫地机器人, 常见问题, 使用, 售后",
        "parser": "faq",
    },
    "扫拖一体机器人100问": {
        "output": "robot_vacuum_mop_faq_100.md",
        "title": "扫拖一体机器人常见问题及解答",
        "category": "robot_vacuum_mop_faq",
        "tags": "扫拖一体机器人, 拖地, FAQ, 使用",
        "parser": "faq",
    },
    "维护保养": {
        "output": "robot_vacuum_maintenance.md",
        "title": "扫地/扫拖一体机器人维护保养",
        "category": "robot_vacuum_maintenance",
        "tags": "扫地机器人, 扫拖一体机器人, 维护, 保养, 耗材",
        "parser": "numbered",
    },
    "选购指南": {
        "output": "robot_vacuum_buying_guide.md",
        "title": "扫地/扫拖一体机器人选购指南",
        "category": "robot_vacuum_buying_guide",
        "tags": "扫地机器人, 扫拖一体机器人, 选购, 售前, 参数",
        "parser": "numbered",
    },
}


def read_text_file(path: Path) -> str:
    encodings = ["utf-8", "utf-8-sig", "gbk", "gb18030"]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def read_pdf_file(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader
        except Exception as exc:
            raise RuntimeError(
                f"读取 PDF 需要安装 pypdf 或 PyPDF2：pip install pypdf。文件：{path}"
            ) from exc

    reader = PdfReader(str(path))
    texts: list[str] = []
    for page in reader.pages:
        texts.append(page.extract_text() or "")
    return "\n".join(texts)


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_numbered_items(text: str) -> list[tuple[str, str]]:
    """
    解析：
    1. 内容
    2. 内容

    返回 [(序号, 内容)]
    """
    text = clean_text(text)
    pattern = re.compile(r"(?m)^\s*(\d+)[\.、]\s*")
    matches = list(pattern.finditer(text))

    if not matches:
        return [("1", text)] if text else []

    items: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        number = match.group(1)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        content = clean_text(text[start:end])
        if content:
            items.append((number, content))

    return items


def parse_troubleshooting(text: str) -> str:
    items = split_numbered_items(text)
    chunks: list[str] = []

    for number, content in items:
        phenomenon = ""
        check = ""
        repair = ""

        m1 = re.search(r"故障现象[:：](.*?)(?=；检测[:：]|;检测[:：]|检测[:：]|$)", content)
        m2 = re.search(r"检测[:：](.*?)(?=；修复[:：]|;修复[:：]|修复[:：]|$)", content)
        m3 = re.search(r"修复[:：](.*)$", content)

        if m1:
            phenomenon = clean_text(m1.group(1))
        if m2:
            check = clean_text(m2.group(1))
        if m3:
            repair = clean_text(m3.group(1))

        title = phenomenon or content[:40]
        chunk = [f"## 故障 {number}：{title}"]

        if phenomenon:
            chunk.append(f"- 故障现象：{phenomenon}")
        if check:
            chunk.append(f"- 检测方法：{check}")
        if repair:
            chunk.append(f"- 修复建议：{repair}")

        if not (phenomenon or check or repair):
            chunk.append(content)

        chunks.append("\n".join(chunk))

    return "\n\n".join(chunks)


def parse_faq(text: str) -> str:
    text = clean_text(text)

    # 保留原有大标题/分类标题，同时把 “1. **问题**- 答案” 规范化为二级 chunk。
    lines = text.splitlines()
    output: list[str] = []
    current_section = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("#"):
            if line.startswith("###"):
                current_section = re.sub(r"^#+\s*", "", line).strip()
                output.append(f"## {current_section}")
            elif line.startswith("##"):
                current_section = re.sub(r"^#+\s*", "", line).strip()
                output.append(f"## {current_section}")
            continue

        m_inline = re.match(r"^(\d+)[\.、]\s*\*\*(.+?)\*\*\s*[-：:]\s*(.*)$", line)
        if m_inline:
            number, question, answer = m_inline.groups()
            title_prefix = f"{current_section} - " if current_section else ""
            output.append(f"## {title_prefix}{number}. {question.strip()}")
            output.append(f"- 问题：{question.strip()}")
            output.append(f"- 回答：{answer.strip()}")
            continue

        m_q = re.match(r"^(\d+)[\.、]\s*\*\*(.+?)\*\*\s*$", line)
        if m_q:
            number, question = m_q.groups()
            title_prefix = f"{current_section} - " if current_section else ""
            output.append(f"## {title_prefix}{number}. {question.strip()}")
            output.append(f"- 问题：{question.strip()}")
            continue

        if line.startswith("-"):
            output.append(f"- 回答：{line.lstrip('-').strip()}")
        else:
            output.append(line)

    return "\n\n".join(output)


def parse_numbered(text: str) -> str:
    items = split_numbered_items(text)
    chunks = []
    for number, content in items:
        title = content.split("。")[0].split("；")[0].strip()
        title = title[:48] if title else f"条目 {number}"
        chunks.append(f"## {number}. {title}\n\n{content}")
    return "\n\n".join(chunks)


def build_front_matter(title: str, category: str, tags: str) -> str:
    return f"""---
title: {title}
category: {category}
tags: {tags}
domain: robot_vacuum
---

"""


def find_raw_file(stem_keyword: str) -> Path | None:
    if not RAW_DIR.exists():
        return None

    for path in RAW_DIR.iterdir():
        if not path.is_file():
            continue
        if stem_keyword in path.stem:
            return path
    return None


def load_raw_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return read_pdf_file(path)
    return read_text_file(path)


def convert_one(stem_keyword: str, config: dict[str, str]) -> tuple[bool, str]:
    raw_path = find_raw_file(stem_keyword)
    if not raw_path:
        return False, f"未找到原始文件：{stem_keyword}"

    text = load_raw_text(raw_path)
    parser = config["parser"]

    if parser == "troubleshooting":
        body = parse_troubleshooting(text)
    elif parser == "faq":
        body = parse_faq(text)
    elif parser == "numbered":
        body = parse_numbered(text)
    else:
        body = clean_text(text)

    output = build_front_matter(config["title"], config["category"], config["tags"]) + body
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / config["output"]
    out_path.write_text(output, encoding="utf-8")

    return True, f"已生成：{out_path.relative_to(PROJECT_ROOT)}"


def main() -> None:
    print(f"原始文件目录：{RAW_DIR}")
    print(f"输出目录：{OUT_DIR}")
    print()

    ok_count = 0
    for stem_keyword, config in FILE_CONFIGS.items():
        ok, message = convert_one(stem_keyword, config)
        print(("✅ " if ok else "⚠️ ") + message)
        ok_count += int(ok)

    print()
    print(f"完成：{ok_count}/{len(FILE_CONFIGS)} 个知识文件已转换。")

    if ok_count == 0:
        print()
        print("请先把原始文件放到 domain_packs/robot_vacuum/raw/ 目录。")
        print("建议文件名：故障排除.txt、扫地机器人100问.pdf、扫地机器人100问2.txt、扫拖一体机器人100问.txt、维护保养.txt、选购指南.txt")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""从引导语知识库随机取一条引导语，打印到 stdout。

用法：
    python scripts/pick_guidance.py

库文件：本脚本上级目录下的 references/guidance_library.json
结构兼容两种：纯字符串数组 ["...", "..."]，或对象数组 [{"text": "..."}]。
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "references", "guidance_library.json")


def load_items(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = []
    for it in data:
        if isinstance(it, str) and it.strip():
            items.append(it.strip())
        elif isinstance(it, dict) and str(it.get("text", "")).strip():
            items.append(str(it["text"]).strip())
    return items


def main():
    # 强制 UTF-8 输出，避免 Windows 下中文 GBK 乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if not os.path.exists(LIB):
        sys.stderr.write("引导语库不存在：%s\n" % LIB)
        sys.exit(1)

    items = load_items(LIB)
    if not items:
        sys.stderr.write("引导语库为空，请先往 references/guidance_library.json 导入引导语。\n")
        sys.exit(2)

    print(random.choice(items))


if __name__ == "__main__":
    main()

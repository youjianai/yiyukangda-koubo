# -*- coding: utf-8 -*-
"""从引导语知识库随机取一条引导语，打印到 stdout。

用法：
    python scripts/pick_guidance.py [--mode short|long|any]

模式：
    short  只从短引导语（≤75字）中随机选，适合原文较长需压缩整体的场景
    long   只从长引导语（≥95字）中随机选，适合原文较短需充实整体的场景
    any    从全部引导语中随机选（默认）

库文件：本脚本上级目录下的 references/guidance_library.json
结构兼容两种：纯字符串数组 ["...", "..."]，或对象数组 [{"text": "..."}]。
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "references", "guidance_library.json")

SHORT_MAX = 75    # ≤75 字为短引导语
LONG_MIN = 95     # ≥95 字为长引导语


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


def filter_by_mode(items, mode):
    if mode == "any":
        return items
    if mode == "short":
        return [t for t in items if len(t) <= SHORT_MAX]
    if mode == "long":
        return [t for t in items if len(t) >= LONG_MIN]
    return items


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="从引导语库随机取一条引导语")
    parser.add_argument(
        "--mode",
        choices=["short", "long", "any"],
        default="any",
        help="short=≤70字 / long=≥100字 / any=全部（默认）",
    )
    args = parser.parse_args()

    if not os.path.exists(LIB):
        sys.stderr.write("引导语库不存在：%s\n" % LIB)
        sys.exit(1)

    all_items = load_items(LIB)
    if not all_items:
        sys.stderr.write("引导语库为空，请先往 references/guidance_library.json 导入引导语。\n")
        sys.exit(2)

    pool = filter_by_mode(all_items, args.mode)
    if not pool:
        # 降级：指定模式下无匹配条目时回退到全部
        sys.stderr.write(
            "警告：--mode %s 无匹配条目（短≤%d字/长≥%d字），已回退到全部。\n"
            % (args.mode, SHORT_MAX, LONG_MIN)
        )
        pool = all_items

    print(random.choice(pool))


if __name__ == "__main__":
    main()

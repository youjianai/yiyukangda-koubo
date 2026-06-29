# -*- coding: utf-8 -*-
"""从引导语知识库随机取一条引导语，打印到 stdout。

用法：
    python scripts/pick_guidance.py [--mode short|long|any]

模式：
    short  优先从短引导语（≤75字）中随机选，适合原文较长需压缩整体的场景
    long   优先从长引导语（≥95字）中随机选，适合原文较短需充实整体的场景
    any    从全部引导语中随机选（默认）

就近取（方案B）：short/long 命中的池子不足 NEAR_MIN_POOL 条时，向相邻长度
（76–94 字「死区」乃至更远）按最接近目标的顺序就近补足，而不是回退到全部——
既保证随机池足够大、避免反复撞同几条，又让长度尽量贴近目标。

去重（方案E）：load_items 加载时按归一化（去标点、空白）后的文本去重，
标点/空格差异或重复追加进来的同一条只算一条进随机池。

库文件：本脚本上级目录下的 references/guidance_library.json
结构兼容两种：纯字符串数组 ["...", "..."]，或对象数组 [{"text": "..."}]。
"""
import argparse
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "references", "guidance_library.json")

SHORT_MAX = 75       # ≤75 字为短引导语（理想阈值）
LONG_MIN = 95        # ≥95 字为长引导语（理想阈值）
NEAR_MIN_POOL = 12   # short/long 命中池小于此值时，向相邻长度就近补足（而非回退全部）

# 去重用：去掉标点、空白、下划线，只留文字与数字后比较
_NORM_RE = re.compile(r"[\W_]+", re.UNICODE)


def _norm(text):
    return _NORM_RE.sub("", text)


def load_items(path):
    """加载库并按归一化文本去重（方案E）：标点/空白差异、重复追加的同一条只留首次出现。
    若 JSON 损坏，给出明确报错并退出，不静默返回空列表。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        sys.stderr.write("引导语库 JSON 已损坏，请检查修复后重试：%s\n" % e)
        sys.exit(3)
    if not isinstance(data, list):
        sys.stderr.write("引导语库 JSON 格式错误：顶层必须是数组。\n")
        sys.exit(3)
    items, seen = [], set()
    for it in data:
        if isinstance(it, str):
            t = it.strip()
        elif isinstance(it, dict):
            t = str(it.get("text", "")).strip()
        else:
            t = ""
        if not t:
            continue
        key = _norm(t)
        if key in seen:
            continue
        seen.add(key)
        items.append(t)
    return items


def filter_by_mode(items, mode):
    """short/long 优先取对应长度档；池子不足 NEAR_MIN_POOL 时，向最接近目标的相邻长度就近补足（方案B）。"""
    if mode == "short":
        primary = [t for t in items if len(t) <= SHORT_MAX]
        if len(primary) >= NEAR_MIN_POOL:
            return primary
        # 不足：从 >SHORT_MAX 的条目里，越短越接近「短引导语」，升序就近补足
        spare = sorted((t for t in items if len(t) > SHORT_MAX), key=len)
        return primary + spare[: max(0, NEAR_MIN_POOL - len(primary))]
    if mode == "long":
        primary = [t for t in items if len(t) >= LONG_MIN]
        if len(primary) >= NEAR_MIN_POOL:
            return primary
        # 不足：从 <LONG_MIN 的条目里，越长越接近「长引导语」，降序就近补足
        spare = sorted((t for t in items if len(t) < LONG_MIN), key=len, reverse=True)
        return primary + spare[: max(0, NEAR_MIN_POOL - len(primary))]
    return items  # any


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
        help="short=≤75字优先 / long=≥95字优先 / any=全部（默认）",
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
        # 兜底：理论上就近取后不会为空，保留以防库异常
        sys.stderr.write("警告：--mode %s 无匹配条目，已回退到全部。\n" % args.mode)
        pool = all_items

    print(random.choice(pool))


if __name__ == "__main__":
    main()

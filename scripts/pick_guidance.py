# -*- coding: utf-8 -*-
"""从引导语知识库随机取候选引导语，打印到 stdout（每行一条）。

用法：
    python scripts/pick_guidance.py [--mode short|long|any] [--count N]

模式：
    short  优先从短引导语（≤75字）中随机选，适合原文较长需压缩整体的场景
    long   优先从长引导语（≥95字）中随机选，适合原文较短需充实整体的场景
    any    从全部引导语中随机选（默认）

多候选（--count N，默认 3）：一次返回 N 条不重复候选，交由调用方按主题挑定，
避免「随机取一条→替换→事后发现不匹配→回头重取」的循环。候选优先取通用型
（universal != false，如交医生朋友/有缘人，任何主题都搭），不足再用利益绑定型补。

就近取（方案B）：short/long 命中池不足 NEAR_MIN_POOL 条时，向相邻长度就近补足。
去重（方案E）：按归一化文本（去标点、空白）去重，同一条只进池一次。

库文件：本脚本上级目录下的 references/guidance_library.json
结构兼容：纯字符串数组 ["...", "..."]，或对象数组 [{"text":"...", "universal":true}]。
对象缺 universal 字段时按利益绑定词表推断（省钱/长高/省下…钱 等标非通用），存量条目不加字段也能跑。
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
DEFAULT_COUNT = 3    # 默认返回候选数

# 去重用：去掉标点、空白、下划线，只留文字与数字后比较
_NORM_RE = re.compile(r"[\W_]+", re.UNICODE)

# 利益绑定词：引导语把点赞/关注与具体利益（省钱、长高等）挂钩，主题适配性差，视为非通用
_BENEFIT_BOUND = ("省钱", "少遭罪", "长高", "省下", "少花钱", "不花冤枉钱")


def _norm(text):
    return _NORM_RE.sub("", text)


def _infer_universal(text):
    """无 universal 字段时的兜底判断：含利益绑定词 → 非通用（False），否则通用（True）。"""
    return not any(w in text for w in _BENEFIT_BOUND)


def load_items(path):
    """加载库并按归一化文本去重。返回 [{"text":..., "universal":bool}]。
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
            t, uni = it.strip(), None
        elif isinstance(it, dict):
            t = str(it.get("text", "")).strip()
            uni = it.get("universal", None)
        else:
            t, uni = "", None
        if not t:
            continue
        key = _norm(t)
        if key in seen:
            continue
        seen.add(key)
        universal = bool(uni) if isinstance(uni, bool) else _infer_universal(t)
        items.append({"text": t, "universal": universal})
    return items


def filter_by_mode(items, mode):
    """short/long 优先取对应长度档；池子不足 NEAR_MIN_POOL 时，向最接近目标的相邻长度就近补足。"""
    if mode == "short":
        primary = [x for x in items if len(x["text"]) <= SHORT_MAX]
        if len(primary) >= NEAR_MIN_POOL:
            return primary
        spare = sorted((x for x in items if len(x["text"]) > SHORT_MAX), key=lambda x: len(x["text"]))
        return primary + spare[: max(0, NEAR_MIN_POOL - len(primary))]
    if mode == "long":
        primary = [x for x in items if len(x["text"]) >= LONG_MIN]
        if len(primary) >= NEAR_MIN_POOL:
            return primary
        spare = sorted((x for x in items if len(x["text"]) < LONG_MIN), key=lambda x: len(x["text"]), reverse=True)
        return primary + spare[: max(0, NEAR_MIN_POOL - len(primary))]
    return items  # any


def pick(pool, count):
    """优先从通用型（universal）随机不重复抽 count 条，不足再用非通用型补足。"""
    universal = [x for x in pool if x["universal"]]
    other = [x for x in pool if not x["universal"]]
    random.shuffle(universal)
    random.shuffle(other)
    ordered = universal + other
    return ordered[:count]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="从引导语库随机取候选引导语（每行一条）")
    parser.add_argument(
        "--mode",
        choices=["short", "long", "any"],
        default="any",
        help="short=≤75字优先 / long=≥95字优先 / any=全部（默认）",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help="返回候选条数（默认 %d），优先通用型" % DEFAULT_COUNT,
    )
    parser.add_argument(
        "--lib-path",
        default=None,
        help="引导语库 JSON 文件的路径（默认 ../references/guidance_library.json）",
    )
    args = parser.parse_args()

    count = max(1, args.count)
    lib_path = args.lib_path if args.lib_path else LIB
    if not os.path.exists(lib_path):
        sys.stderr.write("引导语库不存在：%s\n" % lib_path)
        sys.exit(1)

    all_items = load_items(lib_path)
    if not all_items:
        sys.stderr.write("引导语库为空，请先往 references/guidance_library.json 导入引导语。\n")
        sys.exit(2)

    pool = filter_by_mode(all_items, args.mode)
    if not pool:
        sys.stderr.write("警告：--mode %s 无匹配条目，已回退到全部。\n" % args.mode)
        pool = all_items

    for x in pick(pool, count):
        print(x["text"])


if __name__ == "__main__":
    main()

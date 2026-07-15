# -*- coding: utf-8 -*-
"""从已审核引导语库选择候选，支持可复现抽样和正文预算。"""
import argparse
import json
import os
import random
import re
import sys
from difflib import SequenceMatcher

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "references", "guidance_library.json")

SHORT_MAX = 75
LONG_MIN = 95
NEAR_MIN_POOL = 12
DEFAULT_COUNT = 3
VALID_STATUS = {"approved", "quarantined"}
_NORM_RE = re.compile(r"[\W_]+", re.UNICODE)
_BENEFIT_BOUND = (
    "省钱", "少遭罪", "长高", "省下", "少花钱", "不花冤枉钱",
    "少花冤枉钱", "少挨一刀", "不用跑医院", "治疗的方子",
)
_RISK_PATTERNS = {
    "attacks_peers": ("药店就要干不下去", "药店都要干不下去", "利益都会受损", "高价药"),
    "self_treatment": ("小毛病，咱不求人", "回去试一试", "自己就能调"),
    "second_person_plural": ("你们",),
    "disease_binding": ("腰腿疼痛", "颈肩僵痛", "全身关节不适"),
}


class LibraryError(ValueError):
    pass


def normalize(text):
    return _NORM_RE.sub("", text)


def infer_universal(text):
    return not any(word in text for word in _BENEFIT_BOUND)


def infer_risk_tags(text):
    return [tag for tag, words in _RISK_PATTERNS.items() if any(word in text for word in words)]


def parse_entry(entry, index):
    """兼容旧字符串；正式库对象执行严格 schema 校验。"""
    if isinstance(entry, str):
        text = entry.strip()
        if not text:
            raise LibraryError("第%d条是空字符串" % index)
        risks = infer_risk_tags(text)
        return {
            "id": "legacy-%03d" % index,
            "text": text,
            "status": "quarantined" if risks else "approved",
            "universal": infer_universal(text),
            "risk_tags": risks,
            "char_count": len(text),
        }
    if not isinstance(entry, dict):
        raise LibraryError("第%d条必须是字符串或对象" % index)

    required = {"id", "text", "status", "universal", "risk_tags", "char_count"}
    missing = sorted(required - set(entry))
    unknown = sorted(set(entry) - required)
    if missing:
        raise LibraryError("第%d条缺字段：%s" % (index, ",".join(missing)))
    if unknown:
        raise LibraryError("第%d条含未知字段：%s" % (index, ",".join(unknown)))

    item_id = entry["id"]
    text = entry["text"]
    status = entry["status"]
    universal = entry["universal"]
    risk_tags = entry["risk_tags"]
    char_count = entry["char_count"]
    if not isinstance(item_id, str) or not item_id.strip():
        raise LibraryError("第%d条 id 必须是非空字符串" % index)
    if not isinstance(text, str) or not text.strip():
        raise LibraryError("第%d条 text 必须是非空字符串" % index)
    if status not in VALID_STATUS:
        raise LibraryError("第%d条 status 必须是 approved/quarantined" % index)
    if not isinstance(universal, bool):
        raise LibraryError("第%d条 universal 必须是布尔值" % index)
    if not isinstance(risk_tags, list) or not all(isinstance(x, str) and x for x in risk_tags):
        raise LibraryError("第%d条 risk_tags 必须是字符串数组" % index)
    if not isinstance(char_count, int) or char_count != len(text.strip()):
        raise LibraryError("第%d条 char_count 与 text 实际字数不一致" % index)
    return {
        "id": item_id.strip(),
        "text": text.strip(),
        "status": status,
        "universal": universal,
        "risk_tags": risk_tags,
        "char_count": char_count,
    }


def load_items(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise LibraryError("引导语库无法读取：%s" % exc) from exc
    if not isinstance(data, list):
        raise LibraryError("引导语库顶层必须是数组")

    items = []
    seen_ids = set()
    seen_text = set()
    for index, entry in enumerate(data, 1):
        item = parse_entry(entry, index)
        key = normalize(item["text"])
        if not key:
            raise LibraryError("第%d条归一化后为空" % index)
        if item["id"] in seen_ids:
            raise LibraryError("重复 id：%s" % item["id"])
        if key in seen_text:
            raise LibraryError("重复文本：%s" % item["id"])
        seen_ids.add(item["id"])
        seen_text.add(key)
        items.append(item)
    return items


def filter_by_mode(items, mode):
    if mode == "short":
        primary = [x for x in items if x["char_count"] <= SHORT_MAX]
        if len(primary) >= NEAR_MIN_POOL:
            return primary
        spare = sorted(
            (x for x in items if x["char_count"] > SHORT_MAX),
            key=lambda x: (x["char_count"], x["id"]),
        )
        return primary + spare[: max(0, NEAR_MIN_POOL - len(primary))]
    if mode == "long":
        primary = [x for x in items if x["char_count"] >= LONG_MIN]
        if len(primary) >= NEAR_MIN_POOL:
            return primary
        spare = sorted(
            (x for x in items if x["char_count"] < LONG_MIN),
            key=lambda x: (-x["char_count"], x["id"]),
        )
        return primary + spare[: max(0, NEAR_MIN_POOL - len(primary))]
    return list(items)


def pick(pool, count, seed=None):
    rng = random.Random(seed)
    universal = sorted((x for x in pool if x["universal"]), key=lambda x: x["id"])
    bound = sorted((x for x in pool if not x["universal"]), key=lambda x: x["id"])
    rng.shuffle(universal)
    rng.shuffle(bound)
    return (universal + bound)[:count]


def suspicious_pairs(items, threshold=0.88):
    """报告疑似高度雷同项，不自动删除。"""
    pairs = []
    for left_index, left in enumerate(items):
        a = normalize(left["text"])
        for right in items[left_index + 1:]:
            b = normalize(right["text"])
            score = SequenceMatcher(None, a, b).ratio()
            if score >= threshold:
                pairs.append((left["id"], right["id"], score))
    return pairs


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="从已审核引导语库选择候选（每行一条）")
    parser.add_argument("--mode", choices=["short", "long", "any"], default="any")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=None, help="固定随机种子，回归测试必须传")
    parser.add_argument("--max-chars", type=int, default=None, help="候选最大字数，按正文剩余预算传入")
    parser.add_argument("--lib-path", default=None)
    parser.add_argument("--report-similar", action="store_true", help="只报告疑似高度雷同项")
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count 必须大于 0")
    if args.max_chars is not None and args.max_chars < 1:
        parser.error("--max-chars 必须大于 0")

    try:
        all_items = load_items(args.lib_path or LIB)
    except LibraryError as exc:
        sys.stderr.write(str(exc) + "\n")
        sys.exit(3)

    if args.report_similar:
        for left, right, score in suspicious_pairs(all_items):
            print("%s\t%s\t%.3f" % (left, right, score))
        return

    approved = [x for x in all_items if x["status"] == "approved"]
    if args.max_chars is not None:
        approved = [x for x in approved if x["char_count"] <= args.max_chars]
    pool = filter_by_mode(approved, args.mode)
    if len(pool) < args.count:
        sys.stderr.write(
            "合规候选不足：需要%d条，当前只有%d条。请扩大字数预算或补充已审核候选。\n"
            % (args.count, len(pool))
        )
        sys.exit(4)

    for item in pick(pool, args.count, args.seed):
        print(item["text"])


if __name__ == "__main__":
    main()

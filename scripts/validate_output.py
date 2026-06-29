# -*- coding: utf-8 -*-
"""洗稿成稿输出校验脚本——自动化 4.5 自检中模型手工打勾不可靠的三项。

用法：
    python validate_output.py '口播脚本正文'
    python validate_output.py --file input.txt
    echo '正文' | python validate_output.py -

检查项：
    1. 字数 ≤ 300
    2. 禁用标点零命中（：——""）
    3. 单位汉字化（禁止 g/mg/ml/cm/mm 等字母单位）

返回 0 = 通过（打印统计摘要），返回 1 = 存在违规（打印违规详情+位置）。
"""
import re
import sys

MAX_CHARS = 300

# 禁用标点 → 违规消息
FORBIDDEN_PUNCT = {
    "：": "冒号「：」→ 用逗号代替或断开",
    "——": "破折号「——」→ 用逗号或句号代替",
    "“": "左双引号「“」→ 用「」代替或不加引号",
    "”": "右双引号「”」→ 用「」代替或不加引号",
    "\"": "英文双引号「\"」→ 用「」代替或不加引号",
}

# 字母单位 → 汉字
LATIN_UNIT = re.compile(r"(\d+)\s*(g|mg|ml|cm|mm|kg|mcg|μg)(?![a-zA-Z])", re.IGNORECASE)

UNIT_CN = {"g": "克", "mg": "毫克", "ml": "毫升", "cm": "厘米", "mm": "毫米", "kg": "公斤", "mcg": "微克"}


def count_chars(text: str) -> int:
    """去掉换行和首尾空白后统计字符数。"""
    return len(text.replace("\n", "").replace("\r", "").strip())


def check_forbidden_punct(text: str) -> list[dict]:
    """检查禁用标点。返回违规列表，每项含 char/msg/pos。"""
    violations = []
    for i, ch in enumerate(text):
        if ch in FORBIDDEN_PUNCT:
            violations.append({"char": ch, "msg": FORBIDDEN_PUNCT[ch], "pos": i,
                               "ctx": text[max(0, i-3):i+4]})
    # 特殊处理 —— 占两个字符
    for m in re.finditer("——", text):
        i = m.start()
        violations.append({"char": "——", "msg": FORBIDDEN_PUNCT["——"], "pos": i,
                           "ctx": text[max(0, i-3):i+5]})
    # 去重（按位置）
    seen = set()
    unique = []
    for v in violations:
        if v["pos"] not in seen:
            seen.add(v["pos"])
            unique.append(v)
    return unique


def check_latin_units(text: str) -> list[str]:
    """检查字母单位。返回违规描述列表。"""
    violations = []
    for m in LATIN_UNIT.finditer(text):
        num = m.group(1)
        unit = m.group(2).lower()
        cn = UNIT_CN.get(unit, unit)
        violations.append(f"位置 {m.start()}：「{num}{unit}」→ 应改为「{num}克」等" if unit != "g" else f"位置 {m.start()}：「{num}{unit}」→ 应改为「{num}克」")
        # Handle the cn reference
        if unit == "g":
            violations[-1] = f"位置 {m.start()}：「{num}g」→ 应改为「{num}克」"
        elif unit == "mg":
            violations[-1] = f"位置 {m.start()}：「{num}mg」→ 应改为「{num}毫克」"
        elif unit == "ml":
            violations[-1] = f"位置 {m.start()}：「{num}ml」→ 应改为「{num}毫升」"
        elif unit == "cm":
            violations[-1] = f"位置 {m.start()}：「{num}cm」→ 应改为「{num}厘米」"
        elif unit == "mm":
            violations[-1] = f"位置 {m.start()}：「{num}mm」→ 应改为「{num}毫米」"
        elif unit == "kg":
            violations[-1] = f"位置 {m.start()}：「{num}kg」→ 应改为「{num}公斤」"
        elif unit == "mcg":
            violations[-1] = f"位置 {m.start()}：「{num}mcg」→ 应改为「{num}微克」"
    return violations


def main():
    # 读取输入
    if len(sys.argv) == 2 and sys.argv[1] == "--file":
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            text = f.read()
    elif len(sys.argv) == 2 and sys.argv[1] == "-":
        text = sys.stdin.read()
    elif len(sys.argv) >= 2:
        text = " ".join(sys.argv[1:])
    else:
        if not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            print("用法: python validate_output.py '文本' | --file input.txt | - (stdin)", file=sys.stderr)
            sys.exit(2)

    cnt = count_chars(text)
    punct = check_forbidden_punct(text)
    units = check_latin_units(text)

    errors = []
    if cnt > MAX_CHARS:
        errors.append(f"字数超标：{cnt} > {MAX_CHARS}")
    for p in punct:
        errors.append(f"禁用标点 {p['char']}（位置 {p['pos']}，上下文「{p['ctx']}」）→ {p['msg']}")
    for u in units:
        errors.append(u)

    # 打印详细报告
    print(f"总字数：{cnt}（上限 {MAX_CHARS}）")
    print(f"禁用标点：{len(punct)} 处")
    print(f"字母单位：{len(units)} 处")
    print()

    if errors:
        print("=== 违规详情 ===")
        for e in errors:
            print(f"  ✗ {e}")
        print()
        print("校验未通过，请修复后重新校验。")
        sys.exit(1)
    else:
        print("✓ 校验通过")
        sys.exit(0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()

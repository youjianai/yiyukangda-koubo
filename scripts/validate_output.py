# -*- coding: utf-8 -*-
"""洗稿成稿输出校验——机器兜底，替代靠模型手工打勾不可靠的检查项。

用法：
    python validate_output.py '口播脚本正文'
    python validate_output.py '正文' --herbs "荷叶10克,陈皮6克" --syndromes "痰湿内盛"
    python validate_output.py --file input.txt
    echo '正文' | python validate_output.py -

分两级：
    error（退出码 1，阻断导出）：字数超标、禁用标点、字母单位、正文出现【】、
        闲聊腔、市井口气、疗效打包票、账号自称残留、锁死项缺失（--herbs/--syndromes 传入时）
    warning（不阻断，退出码仍取决于有无 error）：功效说死、买不到未降档、条件绝对、描述词升级

「今后发现新问题先问：能正则→加这里的词表；是写法→进 rewrite_playbook A–F；是判断→进通读关卡。」
词表集中在下方常量，加规则不必改 SKILL.md / playbook 正文。
"""
import argparse
import re
import sys

MAX_CHARS = 300

# ── 禁用标点 → 违规消息（error）
FORBIDDEN_PUNCT = {
    "：": "冒号「：」→ 用逗号代替或断开",
    "——": "破折号「——」→ 用逗号或句号代替",
    "“": "左双引号「“」→ 用「」代替或不加引号",
    "”": "右双引号「”」→ 用「」代替或不加引号",
    "\"": "英文双引号「\"」→ 用「」代替或不加引号",
}

# ── 字母单位 → 汉字（error）
LATIN_UNIT = re.compile(r"(\d+)\s*(g|mg|ml|cm|mm|kg|mcg|μg)(?![a-zA-Z])", re.IGNORECASE)
UNIT_CN = {"g": "克", "mg": "毫克", "ml": "毫升", "cm": "厘米", "mm": "毫米", "kg": "公斤", "mcg": "微克", "μg": "微克"}

# ── error 级关键词表（命中即违规）
BRACKET_RE = re.compile(r"[【】]")                       # 正文禁用方括号（辨证须圆括号，【】是后三段专用）
CHITCHAT = ("话说回来", "有意思的是")                     # 闲聊抖包袱腔
STREET_TONE = ("这招你赚了", "你算赶上了", "捡到宝", "占便宜", "赚到了")  # 市井/捡漏口气
CURE_PROMISE = ("根治", "断根", "越喝越好", "越喝肝越好", "100%治好", "百分百治好", "包治", "药到病除")  # 疗效打包票
SELF_NAME_RE = re.compile(r"我是.{0,4}(医生|大夫)")        # 账号自称残留

# ── warning 级（易误伤，供人工确认，不阻断）
# 功效说死：功效动词未接「帮助/有助于」。白名单动词后紧跟「帮助/有助于」视为合规。
EFFICACY_VERB_RE = re.compile(r"能(祛|补|降|清|润|养|活|通|止|安|健|利)(?!.{0,1}(帮助|有助于))")
BUY_NOT_RE = re.compile(r"(?<!难)买不到")                  # 「买不到」未降档为「难买到」
COND_ABSOLUTE_RE = re.compile(r"只要(?!.{0,20}就)")        # 「只要」20字内未配「就」
DEGREE_UP = ("特别", "非常", "极其", "格外")                # 程度副词升级嫌疑（仅提示，需人工判断是否原文即有）


def count_chars(text):
    return len(text.replace("\n", "").replace("\r", "").strip())


def check_forbidden_punct(text):
    violations = []
    for i, ch in enumerate(text):
        if ch in FORBIDDEN_PUNCT and ch != "\"":
            violations.append((i, ch, FORBIDDEN_PUNCT[ch], text[max(0, i-3):i+4]))
    for m in re.finditer("\"", text):
        i = m.start()
        violations.append((i, "\"", FORBIDDEN_PUNCT["\""], text[max(0, i-3):i+4]))
    for m in re.finditer("——", text):
        i = m.start()
        violations.append((i, "——", FORBIDDEN_PUNCT["——"], text[max(0, i-3):i+5]))
    seen, unique = set(), []
    for v in sorted(violations):
        if v[0] not in seen:
            seen.add(v[0])
            unique.append(v)
    return unique


def check_latin_units(text):
    out = []
    for m in LATIN_UNIT.finditer(text):
        num, unit = m.group(1), m.group(2).lower()
        cn = UNIT_CN.get(unit, unit)
        out.append("位置 %d：「%s%s」→ 应改为「%s%s」" % (m.start(), num, m.group(2), num, cn))
    return out


def find_keywords(text, words):
    """返回命中的 (关键词, 位置) 列表。"""
    hits = []
    for w in words:
        start = 0
        while True:
            i = text.find(w, start)
            if i < 0:
                break
            hits.append((w, i))
            start = i + len(w)
    return hits


def check_locked(text, herbs, syndromes):
    """锁死项保全：传入的克数条目、证型必须原样出现在正文中，缺失即 error。"""
    missing = []
    for h in herbs:
        h = h.strip()
        if h and h not in text:
            missing.append("方剂条目「%s」未在正文中原样出现（克数/药材名不得改动或丢失）" % h)
    for s in syndromes:
        s = s.strip()
        if s and s not in text:
            missing.append("证型「%s」未在正文中原样出现" % s)
    return missing


def main():
    parser = argparse.ArgumentParser(description="洗稿成稿输出校验")
    parser.add_argument("text", nargs="?", default=None, help="脚本正文；或用 --file / -（stdin）")
    parser.add_argument("--file", dest="file", default=None, help="从文件读取正文")
    parser.add_argument("--herbs", default="", help="逗号分隔的锁死方剂条目，如 \"荷叶10克,陈皮6克\"")
    parser.add_argument("--syndromes", default="", help="逗号分隔的锁死证型，如 \"痰湿内盛,肝肾阴虚\"")
    args, _ = parser.parse_known_args()

    # 读取正文
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    elif args.text == "-" or (args.text is None and not sys.stdin.isatty()):
        text = sys.stdin.read()
    elif args.text is not None:
        text = args.text
    else:
        print("用法: python validate_output.py '文本' [--herbs ...] [--syndromes ...] | --file f | - (stdin)", file=sys.stderr)
        sys.exit(2)

    herbs = [x for x in args.herbs.split(",") if x.strip()]
    syndromes = [x for x in args.syndromes.split(",") if x.strip()]

    cnt = count_chars(text)
    punct = check_forbidden_punct(text)
    units = check_latin_units(text)
    brackets = [m.start() for m in BRACKET_RE.finditer(text)]
    chitchat = find_keywords(text, CHITCHAT)
    street = find_keywords(text, STREET_TONE)
    cure = find_keywords(text, CURE_PROMISE)
    self_name = [(m.group(0), m.start()) for m in SELF_NAME_RE.finditer(text)]
    locked_missing = check_locked(text, herbs, syndromes)

    # warning 项
    efficacy = [(m.group(0), m.start()) for m in EFFICACY_VERB_RE.finditer(text)]
    buynot = [m.start() for m in BUY_NOT_RE.finditer(text)]
    cond = [m.start() for m in COND_ABSOLUTE_RE.finditer(text)]
    degree = find_keywords(text, DEGREE_UP)

    errors, warnings = [], []

    if cnt > MAX_CHARS:
        errors.append("字数超标：%d > %d" % (cnt, MAX_CHARS))
    for pos, ch, msg, ctx in punct:
        errors.append("禁用标点 %s（位置 %d，上下文「%s」）→ %s" % (ch, pos, ctx, msg))
    errors.extend(units)
    for i in brackets:
        errors.append("正文出现方括号「%s」（位置 %d）→ 辨证兜底须用圆括号（），【】是后三段专用" % (text[i], i))
    for w, i in chitchat:
        errors.append("闲聊腔「%s」（位置 %d）→ 换医生向逻辑词（但/其实/所以…）" % (w, i))
    for w, i in street:
        errors.append("市井口气「%s」（位置 %d）→ 医生 IP 要稳重，改「恭喜你刷到这条视频」等" % (w, i))
    for w, i in cure:
        errors.append("疗效打包票「%s」（位置 %d）→ 软化为留余地说法" % (w, i))
    for w, i in self_name:
        errors.append("账号自称残留「%s」（位置 %d）→ 引导语里的账号自称须删除" % (w, i))
    errors.extend(locked_missing)

    for w, i in efficacy:
        warnings.append("功效可能说死「%s…」（位置 %d）→ 若为方子功效应改「能帮助X」；药材客观属性可忽略" % (w, i))
    for i in buynot:
        warnings.append("「买不到」（位置 %d）→ 非引导语段建议降档为「难买到」" % i)
    for i in cond:
        warnings.append("「只要」（位置 %d）附近未见「就」→ 条件句建议用「如果」，除非完整关联词对" % i)
    for w, i in degree:
        warnings.append("程度副词「%s」（位置 %d）→ 若原文非此力度则属升级，普通描述词不得升级；请人工确认" % (w, i))

    # 报告
    print("总字数：%d（上限 %d）" % (cnt, MAX_CHARS))
    print("error：%d 项 / warning：%d 项" % (len(errors), len(warnings)))
    print()
    if errors:
        print("=== error（阻断导出，必须修复）===")
        for e in errors:
            print("  ✗ %s" % e)
        print()
    if warnings:
        print("=== warning（人工确认，不阻断）===")
        for w in warnings:
            print("  ⚠ %s" % w)
        print()

    if errors:
        print("校验未通过，请修复 error 后重新校验。")
        sys.exit(1)
    print("✓ 校验通过（error=0）" + ("，另有 %d 项 warning 请人工确认。" % len(warnings) if warnings else ""))
    sys.exit(0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()

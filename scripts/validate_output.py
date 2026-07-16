# -*- coding: utf-8 -*-
"""口播正文确定性校验；CLI 兼容旧调用，正式导出由 build_docx 调用函数。"""
import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

try:
    from count_chars import count as count_chars
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from count_chars import count as count_chars

MAX_CHARS = 300
FORBIDDEN_PUNCT = {
    "：": "冒号须改为逗号或断句",
    "——": "破折号须改为逗号或句号",
    "“": "中文双引号须改为书名号式单引号或删除",
    "”": "中文双引号须改为书名号式单引号或删除",
    '"': "英文双引号须改为中文单引号或删除",
}
LATIN_UNIT = re.compile(r"(\d+)\s*(kg|mg|mcg|μg|ml|cm|mm|g)(?![a-zA-Z])", re.I)
UNIT_CN = {"g": "克", "mg": "毫克", "ml": "毫升", "cm": "厘米", "mm": "毫米", "kg": "公斤", "mcg": "微克", "μg": "微克"}
BRACKET_RE = re.compile(r"[【】]")
SELF_NAME_RE = re.compile(r"(?:我是|这里是|本人是).{0,12}(?:医生|大夫|主任医师)")
CHITCHAT = ("话说回来", "有意思的是")
STREET_TONE = ("这招你赚了", "你算赶上了", "捡到宝", "占便宜", "赚到了")
POPSCI_BRIDGE = ("常会用到", "临床上常用", "一般会用", "顺着这个思路")
CURE_PROMISE = ("根治", "断根", "越喝越好", "越喝肝越好", "100%治好", "百分百治好", "包治", "药到病除")
SELF_TREATMENT = ("小毛病自己就能调", "小毛病，咱不求人", "不用治疗", "不用看医生", "回去试一试")
ATTACK_PEERS = ("药店就要干不下去", "药店都要干不下去", "卖高价暴利产品")
EFFICACY_VERB_RE = re.compile(r"能(祛|补|降|清|润|养|活|通|止|安|健|利)(?!.{0,1}(帮助|有助于))")
BUY_NOT_RE = re.compile(r"(?<!难)买不到")
COND_ABSOLUTE_RE = re.compile(r"只要(?!.{0,20}就)")
OUTCOME_GUARANTEE_RE = re.compile(r"(?:不让你|保证你|确保你|保证以后|确保以后).{0,12}(?:多花|花冤枉钱|跑医院|挨刀|遭罪|不用治疗|不用手术)")
ABSOLUTE_CAUSATION_RE = re.compile(r"(?:的根子(?:就)?是(?!什么)|唯一(?:病因|原因)|全都(?:是|由).{0,16}(?:引起|导致))")
DEGREE_UP = ("特别", "非常", "极其", "格外")
_TODAY_PREVIEW_RE = re.compile(r"今天.{0,10}(?:说|讲|分享|告诉|介绍|聊|要说的|要讲的|要分享的)")
_COPY_NORM_RE = re.compile(r"[^\w一-鿿]+", re.UNICODE)
_SENTENCE_GAP_6 = r"[^。！？；\n]{0,6}"
_SENTENCE_GAP_8 = r"[^。！？；\n]{0,8}"
_SENTENCE_GAP_12 = r"[^。！？；\n]{0,12}"
EDITORIAL_TONE_RULES = (
    (
        re.compile(
            r"(?:关键|重点)(?:是|在于)?" + _SENTENCE_GAP_6
            + r"(?:先|得先|要先)" + _SENTENCE_GAP_8
            + r"(?:看|判断|弄清)" + _SENTENCE_GAP_12
            + r"(?:适不适合|是否适合)"
        ),
        "tips",
        "适用性审查",
    ),
    (
        re.compile(
            r"(?:不一定|未必)" + _SENTENCE_GAP_6
            + r"(?:都|全)" + _SENTENCE_GAP_8
            + r"(?:原因|引起|导致)"
        ),
        "notes",
        "鉴别诊断补丁",
    ),
    (
        re.compile(
            r"(?:在)?辨证" + _SENTENCE_GAP_8
            + r"(?:合适|适合|准确|明确)" + _SENTENCE_GAP_6
            + r"(?:的)?前提下"
        ),
        "tips",
        "重复辨证前提",
    ),
    (
        re.compile(
            r"(?:先|需要先|得先)" + _SENTENCE_GAP_12
            + r"(?:原因|证型)" + _SENTENCE_GAP_12
            + r"(?:辨清|弄清|判断清楚)" + _SENTENCE_GAP_12
            + r"(?:再|然后)" + _SENTENCE_GAP_12
            + r"(?:适不适合|是否适合)"
        ),
        "tips",
        "重复辨证前提",
    ),
)
_PAREN_CONTENT_RE = re.compile(r"（([^（）\r\n]*)）|\(([^()\r\n]*)\)")
_SYNDROME_MARKER_RE = re.compile(r"(?:需)?辨证为")


def _issue(issue_id, message, context=None):
    issue = {"id": issue_id, "message": message}
    if context:
        issue["context"] = context
    return issue


def lock_texts(lock_values):
    texts = []
    for index, value in enumerate(lock_values or []):
        if isinstance(value, str):
            text = value.strip()
        elif isinstance(value, dict):
            text = value.get("locked_text", "")
            if not isinstance(text, str):
                text = ""
            text = text.strip()
        else:
            text = ""
        if not text:
            raise ValueError("锁定项第%d条缺少 locked_text" % (index + 1))
        texts.append(text)
    return texts


def find_copied_phrases(source_text, output_text, locked, width=10):
    source = _COPY_NORM_RE.sub("", source_text or "")
    output = _COPY_NORM_RE.sub("", output_text or "")
    exemptions = sorted(
        (_COPY_NORM_RE.sub("", text) for text in locked),
        key=len,
        reverse=True,
    )
    for exemption in exemptions:
        if exemption:
            source = source.replace(exemption, "|")
            output = output.replace(exemption, "|")
    output_segments = [segment for segment in output.split("|") if segment]
    hits = []
    seen = set()
    for segment in source.split("|"):
        for index in range(max(0, len(segment) - width + 1)):
            phrase = segment[index:index + width]
            if phrase not in seen and any(phrase in candidate for candidate in output_segments):
                seen.add(phrase)
                hits.append(phrase)
    return hits


def find_editorial_tone(text):
    """返回正文中可确定的审稿腔；规则保持句内有界，避免单词级误伤。"""
    issues = []
    seen = set()
    for pattern, target, label in EDITORIAL_TONE_RULES:
        for match in pattern.finditer(text or ""):
            key = (match.start(), match.end(), target)
            if key in seen:
                continue
            seen.add(key)
            issues.append(_issue(
                "editorial-tone",
                "%s「%s」不属于口播正文，请删除正文补丁并把必要信息改写后放入 %s" % (
                    label, match.group(0), target,
                ),
                (text or "")[max(0, match.start() - 6):match.end() + 6],
            ))
    return issues


def validate_syndrome_annotations(text, syndrome_locks):
    """证型锁必须由唯一、精确的中文圆括号括注承载。"""
    issues = []
    expected = list(dict.fromkeys(syndrome_locks))
    text = text or ""
    annotations = []
    for match in _PAREN_CONTENT_RE.finditer(text):
        content = match.group(1) if match.group(1) is not None else match.group(2)
        if _SYNDROME_MARKER_RE.search(content or ""):
            annotations.append((match.group(0), content, match.group(1) is not None))

    if not expected:
        if _SYNDROME_MARKER_RE.search(text) and not annotations:
            issues.append(_issue(
                "unexpected-syndrome-annotation",
                "未提供已批准证型锁，正文不得自行补写辨证为某证型",
            ))
        for raw, _, _ in annotations:
            issues.append(_issue(
                "unexpected-syndrome-annotation",
                "未提供已批准证型锁，正文不得出现辨证括注「%s」" % raw,
            ))
        return issues

    expected_annotations = {value: "（需辨证为%s）" % value for value in expected}
    exact_counts = {value: text.count(annotation) for value, annotation in expected_annotations.items()}

    for value, annotation in expected_annotations.items():
        count = exact_counts[value]
        if count == 0:
            issues.append(_issue(
                "missing-syndrome-annotation",
                "证型「%s」必须且只能以标准括注「%s」出现一次" % (value, annotation),
            ))
        elif count > 1:
            issues.append(_issue(
                "duplicate-syndrome-annotation",
                "标准辨证括注「%s」重复出现 %d 次" % (annotation, count),
            ))

    expected_raw = set(expected_annotations.values())
    if _SYNDROME_MARKER_RE.search(text) and not annotations:
        issues.append(_issue(
            "invalid-syndrome-annotation",
            "辨证括注必须使用精确格式「%s」" % " / ".join(expected_annotations.values()),
        ))
    for raw, content, is_chinese in annotations:
        if raw in expected_raw and is_chinese:
            continue
        issues.append(_issue(
            "invalid-syndrome-annotation",
            "非标准或未批准辨证括注「%s」；括号内只能放已批准证型并使用中文圆括号" % raw,
        ))
    return issues


def validate_text(text, locks=None, source_text=""):
    locks = locks or {"formula_items": [], "diseases": [], "syndromes": [], "numeric_hooks": []}
    errors = []
    warnings = []
    if not isinstance(text, str) or not text.strip():
        errors.append(_issue("empty-script", "正文不能为空或只含空白"))
        text = text if isinstance(text, str) else ""

    count = count_chars(text)
    if count > MAX_CHARS:
        errors.append(_issue("max-chars", "字数超标：%d > %d" % (count, MAX_CHARS)))

    for token, message in FORBIDDEN_PUNCT.items():
        start = 0
        while True:
            pos = text.find(token, start)
            if pos < 0:
                break
            errors.append(_issue("forbidden-punctuation", "%s，位置 %d" % (message, pos), text[max(0, pos - 4):pos + len(token) + 4]))
            start = pos + len(token)
    for match in LATIN_UNIT.finditer(text):
        unit = match.group(2).lower()
        errors.append(_issue("latin-unit", "字母单位「%s」应改为「%s%s」" % (match.group(0), match.group(1), UNIT_CN[unit])))
    if BRACKET_RE.search(text):
        errors.append(_issue("public-bracket", "正文不得出现【】，该符号只用于 Word 后三段"))

    keyword_groups = (
        ("chitchat", CHITCHAT, "闲聊腔"),
        ("street-tone", STREET_TONE, "市井口气"),
        ("popsci-bridge", POPSCI_BRIDGE, "科普腔过渡"),
        ("cure-promise", CURE_PROMISE, "疗效打包票"),
        ("self-treatment", SELF_TREATMENT, "自疗或弱化就医"),
        ("attack-peers", ATTACK_PEERS, "攻击同行"),
    )
    for issue_id, words, label in keyword_groups:
        for word in words:
            if word in text:
                errors.append(_issue(issue_id, "%s「%s」" % (label, word)))
    for match in SELF_NAME_RE.finditer(text):
        errors.append(_issue("account-identity", "账号自称残留「%s」" % match.group(0)))
    for match in OUTCOME_GUARANTEE_RE.finditer(text):
        errors.append(_issue("outcome-guarantee", "不可控结果保证「%s」" % match.group(0)))
    for match in ABSOLUTE_CAUSATION_RE.finditer(text):
        errors.append(_issue("absolute-causation", "医学归因过于绝对「%s」" % match.group(0)))
    errors.extend(find_editorial_tone(text))

    today_hits = _TODAY_PREVIEW_RE.findall(text or "")
    if len(today_hits) > 1:
        errors.append(_issue(
            "today-preview-repeat",
            "正文出现 %d 次「今天+讲/说/分享」类预告重复；每段只保留首次预告，后续直接进入内容"
            % len(today_hits),
        ))

    all_locked = []
    syndrome_locks = []
    for key, label in (("formula_items", "方剂条目"), ("diseases", "病症"), ("syndromes", "证型"), ("numeric_hooks", "数字钩子")):
        try:
            values = lock_texts(locks.get(key, []))
        except (AttributeError, ValueError) as exc:
            errors.append(_issue("invalid-lock", "%s locks 无效：%s" % (label, exc)))
            values = []
        all_locked.extend(values)
        if key == "syndromes":
            syndrome_locks = values
            continue
        for value in values:
            if value not in text:
                errors.append(_issue("missing-lock", "%s「%s」未在正文中原样出现" % (label, value)))
    errors.extend(validate_syndrome_annotations(text, syndrome_locks))

    if source_text:
        copied = find_copied_phrases(source_text, text, all_locked)
        if copied:
            errors.append(_issue("verbatim-copy", "存在非锁定连续10字照抄：%s" % "、".join(copied[:5])))
        source_norm = _COPY_NORM_RE.sub("", source_text)
        output_norm = _COPY_NORM_RE.sub("", text)
        if source_norm and output_norm:
            ratio = SequenceMatcher(None, source_norm, output_norm).ratio()
            if ratio > 0.70:
                warnings.append(_issue("rewrite-similarity", "原文与成稿字符相似度 %.1f%%，需人工确认是否达到高质量二创" % (ratio * 100)))

    for match in EFFICACY_VERB_RE.finditer(text):
        warnings.append(_issue("efficacy-verb", "功效可能说死「%s」；药材客观属性可人工豁免" % match.group(0)))
    for match in BUY_NOT_RE.finditer(text):
        warnings.append(_issue("buy-not", "「买不到」需确认是否位于已审核引导语"))
    for match in COND_ABSOLUTE_RE.finditer(text):
        warnings.append(_issue("condition-pair", "「只要」附近未见「就」，需确认关联词完整"))
    for word in DEGREE_UP:
        if word in text:
            warnings.append(_issue("degree-word", "程度副词「%s」需与原文对照，普通描述不得升级" % word))

    return {"char_count": count, "max_chars": MAX_CHARS, "errors": errors, "warnings": warnings}


def _print_report(report):
    print("总字数：%d（上限 %d）" % (report["char_count"], report["max_chars"]))
    print("error：%d 项 / warning：%d 项" % (len(report["errors"]), len(report["warnings"])))
    if report["errors"]:
        print("\n=== error（阻断导出）===")
        for issue in report["errors"]:
            print("  ✗ [%s] %s" % (issue["id"], issue["message"]))
    if report["warnings"]:
        print("\n=== warning（正式导出前必须处置）===")
        for issue in report["warnings"]:
            print("  ⚠ [%s] %s" % (issue["id"], issue["message"]))


def main():
    parser = argparse.ArgumentParser(description="洗稿成稿输出校验")
    parser.add_argument("text", nargs="?", default=None)
    parser.add_argument("--file", default=None)
    parser.add_argument("--source-file", default=None, help="原文文件，用于照抄和相似度对照")
    parser.add_argument("--formula-items", default="")
    parser.add_argument("--herbs", default="", help="兼容旧参数，后续移除")
    parser.add_argument("--diseases", default="")
    parser.add_argument("--syndromes", default="")
    parser.add_argument("--numeric-hooks", default="")
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = parser.parse_args()

    if args.file and args.text is not None:
        parser.error("正文参数与 --file 不能同时使用")
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text == "-" or (args.text is None and not sys.stdin.isatty()):
        text = sys.stdin.read()
    elif args.text is not None:
        text = args.text
    else:
        parser.error("请传正文、--file 或 stdin")

    def split(value):
        return [part.strip() for part in value.split(",") if part.strip()]

    locks = {
        "formula_items": split(args.formula_items) + split(args.herbs),
        "diseases": split(args.diseases),
        "syndromes": split(args.syndromes),
        "numeric_hooks": split(args.numeric_hooks),
    }
    source_text = Path(args.source_file).read_text(encoding="utf-8") if args.source_file else ""
    report = validate_text(text, locks, source_text)
    if args.herbs:
        report["warnings"].append(_issue("deprecated-herbs", "--herbs 已弃用，请改用 --formula-items"))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)
        if not report["errors"]:
            print("\n✓ 正文 error=0。正式导出仍须处置 warning 并通过 handoff 门禁。")
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()

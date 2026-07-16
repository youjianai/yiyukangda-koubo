# -*- coding: utf-8 -*-
"""Canonical handoff v3 contract helpers and explicit v2 migration."""
from copy import deepcopy

SCHEMA_VERSION = "3"
LOCK_KINDS = ("formula_items", "diseases", "syndromes", "numeric_hooks")
HOOK_KINDS = {"formula_item", "disease", "syndrome", "numeric_hook", "fixed_phrase"}
SEMANTIC_HOOK_KINDS = {"scarcity", "emotion", "urgency", "identity", "contrast"}
APPROVAL_STATUSES = {"approved", "pending", "rejected"}
SAFETY_DISPOSITIONS = {"verbatim", "demoted", "rejected", "pending"}
REVIEW_TARGETS = {"notes", "tips", "processing"}
TITLE_DECISIONS = {"unchanged", "safety_adjusted", "blocked_editorial_review"}
REVIEW_CHECK_KEYS = {
    "narrative_chain", "hook_and_title", "rewrite_quality", "medical_boundary",
    "lock_provenance", "oral_naturalness", "guidance_fit",
}
V3_HANDOFF_KEYS = {"schema_version", "stage", "filename", "items"}
V3_ITEM_KEYS = {
    "source", "hooks", "review_findings", "title_review", "review_record",
    "warning_decisions", "public",
}
PUBLIC_KEYS = {"link", "title", "script", "notes", "tips", "processing"}


def _require_exact_keys(value, required, path):
    if not isinstance(value, dict):
        raise ValueError("%s 必须是对象" % path)
    unknown = sorted(set(value) - set(required))
    missing = sorted(set(required) - set(value))
    if unknown:
        raise ValueError("%s 含未知字段：%s" % (path, ",".join(unknown)))
    if missing:
        raise ValueError("%s 缺字段：%s" % (path, ",".join(missing)))


def _text(value, path, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValueError("%s 必须是%s字符串" % (path, "" if allow_empty else "非空"))
    return value


def validate_verbatim_hook(hook, source_text, path):
    required = {
        "id", "kind", "raw", "delivery_text", "source_span", "normalization_ops",
        "provenance", "approval_status", "safety_disposition",
    }
    _require_exact_keys(hook, required, path)
    _text(hook["id"], path + ".id")
    if hook["kind"] not in HOOK_KINDS:
        raise ValueError(path + ".kind 无效")
    raw = _text(hook["raw"], path + ".raw")
    delivery = _text(hook["delivery_text"], path + ".delivery_text")
    if hook["provenance"] not in {"source_verbatim", "source_normalized", "user_required", "review_approved"}:
        raise ValueError(path + ".provenance 无效")
    if hook["approval_status"] not in APPROVAL_STATUSES:
        raise ValueError(path + ".approval_status 无效")
    if hook["safety_disposition"] not in SAFETY_DISPOSITIONS:
        raise ValueError(path + ".safety_disposition 无效")
    if not isinstance(hook["normalization_ops"], list) or not all(isinstance(x, str) for x in hook["normalization_ops"]):
        raise ValueError(path + ".normalization_ops 必须是字符串数组")
    span = hook["source_span"]
    if not isinstance(span, list) or len(span) != 2 or not all(isinstance(x, int) for x in span):
        raise ValueError(path + ".source_span 必须是 [start,end]")
    start, end = span
    if hook["provenance"].startswith("source_"):
        if start < 0 or end <= start or source_text[start:end] != raw:
            raise ValueError(path + " source_span 与原文 raw 不一致")
    if hook["provenance"] == "source_verbatim" and raw != delivery:
        raise ValueError(path + " source_verbatim 要求 raw == delivery_text")
    if hook["provenance"] == "source_normalized" and not hook["normalization_ops"]:
        raise ValueError(path + " source_normalized 必须记录 normalization_ops")
    if hook["approval_status"] != "approved" and hook["safety_disposition"] == "verbatim":
        raise ValueError(path + " 未批准内容不能成为 verbatim 约束")


def validate_hooks(hooks, source_text, path="hooks"):
    _require_exact_keys(hooks, {"verbatim", "semantic_strength"}, path)
    if not isinstance(hooks["verbatim"], list):
        raise ValueError(path + ".verbatim 必须是数组")
    seen_ids = set()
    for index, hook in enumerate(hooks["verbatim"]):
        hook_path = "%s.verbatim[%d]" % (path, index)
        validate_verbatim_hook(hook, source_text, hook_path)
        if hook["id"] in seen_ids:
            raise ValueError("重复 hook id：%s" % hook["id"])
        seen_ids.add(hook["id"])
    if not isinstance(hooks["semantic_strength"], list):
        raise ValueError(path + ".semantic_strength 必须是数组")
    for index, hook in enumerate(hooks["semantic_strength"]):
        hook_path = "%s.semantic_strength[%d]" % (path, index)
        _require_exact_keys(hook, {"id", "kind", "source_text", "source_span", "truth_status", "safety_disposition"}, hook_path)
        if hook["kind"] not in SEMANTIC_HOOK_KINDS:
            raise ValueError(hook_path + ".kind 无效")
        if hook["truth_status"] not in {"verified", "unverified", "rejected"}:
            raise ValueError(hook_path + ".truth_status 无效")
        if hook["safety_disposition"] not in SAFETY_DISPOSITIONS:
            raise ValueError(hook_path + ".safety_disposition 无效")
        if hook["truth_status"] == "unverified" and hook["safety_disposition"] == "verbatim":
            raise ValueError(hook_path + " 未核实语义钩子不能 verbatim 进入正文")
        span = hook["source_span"]
        if not isinstance(span, list) or len(span) != 2 or not all(isinstance(x, int) for x in span):
            raise ValueError(hook_path + ".source_span 必须是 [start,end]")
        start, end = span
        source_hook_text = _text(hook["source_text"], hook_path + ".source_text")
        if start < 0 or end <= start or source_text[start:end] != source_hook_text:
            raise ValueError(hook_path + " source_span 与原文 source_text 不一致")


def validate_review_findings(findings, path="review_findings"):
    if not isinstance(findings, list):
        raise ValueError(path + " 必须是数组")
    seen_ids = set()
    for index, finding in enumerate(findings):
        finding_path = "%s[%d]" % (path, index)
        _require_exact_keys(finding, {"id", "kind", "text", "target", "approval_status", "source"}, finding_path)
        finding_id = _text(finding["id"], finding_path + ".id")
        _text(finding["text"], finding_path + ".text")
        _text(finding["source"], finding_path + ".source", allow_empty=True)
        if finding_id in seen_ids:
            raise ValueError("重复 finding id：%s" % finding_id)
        seen_ids.add(finding_id)
        if finding["target"] not in REVIEW_TARGETS:
            raise ValueError(finding_path + ".target 无效")
        if finding["approval_status"] not in APPROVAL_STATUSES:
            raise ValueError(finding_path + ".approval_status 无效")


def validate_title_review(title_review, source_title, public_title=None, path="title_review"):
    _require_exact_keys(title_review, {"decision", "title", "reason_codes", "rationale"}, path)
    decision = title_review["decision"]
    title = _text(title_review["title"], path + ".title")
    if decision not in TITLE_DECISIONS:
        raise ValueError(path + ".decision 无效")
    if not isinstance(title_review["reason_codes"], list) or not all(isinstance(x, str) and x for x in title_review["reason_codes"]):
        raise ValueError(path + ".reason_codes 必须是非空字符串数组或空数组")
    if not isinstance(title_review["rationale"], str):
        raise ValueError(path + ".rationale 必须是字符串")
    if decision == "unchanged" and title != source_title:
        raise ValueError(path + " unchanged 要求 title 与 source.title 一致")
    if decision == "safety_adjusted":
        if title == source_title:
            raise ValueError(path + " safety_adjusted 必须修改标题")
        if not title_review["reason_codes"] or not title_review["rationale"].strip():
            raise ValueError(path + " safety_adjusted 必须填写 reason_codes 和 rationale")
    if decision == "blocked_editorial_review":
        raise ValueError(path + " 标题等待编导裁决，不能导出")
    if public_title is not None and title != public_title:
        raise ValueError(path + ".title 必须与 public.title 一致")


def active_literal_constraints(hooks):
    return [
        hook for hook in hooks.get("verbatim", [])
        if hook["approval_status"] == "approved" and hook["safety_disposition"] == "verbatim"
    ]


def compile_locks(hooks):
    pending = [
        hook["id"] for hook in hooks.get("verbatim", [])
        if hook["approval_status"] == "pending" or hook["safety_disposition"] == "pending"
    ]
    if pending:
        raise ValueError("hooks 尚有待批准项，不能导出：%s" % ",".join(pending))
    locks = {key: [] for key in LOCK_KINDS}
    kind_map = {
        "formula_item": "formula_items", "disease": "diseases",
        "syndrome": "syndromes", "numeric_hook": "numeric_hooks",
        "fixed_phrase": "numeric_hooks",
    }
    for hook in active_literal_constraints(hooks):
        group = kind_map.get(hook["kind"])
        if group:
            locks[group].append(hook["delivery_text"])
    return locks


def approved_findings_projection(findings):
    projected = {target: [] for target in REVIEW_TARGETS}
    for finding in findings:
        if finding["approval_status"] == "pending":
            raise ValueError("review finding %s 尚未批准，不能导出" % finding["id"])
        if finding["approval_status"] == "approved":
            entry = {"text": finding["text"]}
            if finding["source"]:
                entry["source"] = finding["source"]
            projected[finding["target"]].append(entry)
    return projected


def validate_parsed_state(data):
    required = {
        "schema_version", "stage", "source", "hooks", "review_findings",
        "title_review", "internal_review",
    }
    _require_exact_keys(data, required, "parsed")
    if data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("schema_version 必须为 3")
    if data["stage"] != "parsed_checked":
        raise ValueError("parsed stage 必须为 parsed_checked")
    _require_exact_keys(data["source"], {"link", "title", "text"}, "parsed.source")
    source_text = _text(data["source"]["text"], "parsed.source.text")
    source_title = _text(data["source"]["title"], "parsed.source.title")
    _text(data["source"]["link"], "parsed.source.link", allow_empty=True)
    validate_hooks(data["hooks"], source_text, "parsed.hooks")
    validate_review_findings(data["review_findings"], "parsed.review_findings")
    validate_title_review(data["title_review"], source_title, path="parsed.title_review")
    if not isinstance(data["internal_review"], dict):
        raise ValueError("parsed.internal_review 必须是对象")
    return data


def validate_v3_handoff_shape(data):
    _require_exact_keys(data, V3_HANDOFF_KEYS, "handoff")
    if data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("schema_version 必须为 3")
    if data["stage"] != "rewritten":
        raise ValueError("stage 必须为 rewritten")
    _text(data["filename"], "handoff.filename")
    if not isinstance(data["items"], list) or not data["items"]:
        raise ValueError("handoff.items 必须是非空数组")
    for index, item in enumerate(data["items"]):
        path = "handoff.items[%d]" % index
        _require_exact_keys(item, V3_ITEM_KEYS, path)
        _require_exact_keys(item["source"], {"link", "title", "text"}, path + ".source")
        source_text = _text(item["source"]["text"], path + ".source.text")
        source_title = _text(item["source"]["title"], path + ".source.title")
        _text(item["source"]["link"], path + ".source.link", allow_empty=True)
        validate_hooks(item["hooks"], source_text, path + ".hooks")
        validate_review_findings(item["review_findings"], path + ".review_findings")
        _require_exact_keys(item["public"], PUBLIC_KEYS, path + ".public")
        validate_title_review(item["title_review"], source_title, item["public"]["title"], path + ".title_review")
        _require_exact_keys(item["review_record"], REVIEW_CHECK_KEYS, path + ".review_record")
        if any(value is not True for value in item["review_record"].values()):
            raise ValueError(path + ".review_record 存在未通过卡口")
        if not isinstance(item["warning_decisions"], dict):
            raise ValueError(path + ".warning_decisions 必须是对象")
    return data


def v2_to_v3(data):
    """Explicit, conservative migration. Ambiguous approvals remain pending."""
    if not isinstance(data, dict) or data.get("schema_version") != "2":
        raise ValueError("仅支持迁移 schema_version=2")
    if data.get("stage") != "parsed_checked":
        raise ValueError("仅支持迁移 parsed_checked 状态")
    source = deepcopy(data["source"])
    source_text = source["text"]
    hooks = []
    kind_map = {
        "formula_items": "formula_item", "diseases": "disease",
        "syndromes": "syndrome", "numeric_hooks": "numeric_hook",
    }
    for group, kind in kind_map.items():
        for index, item in enumerate(data.get("locks", {}).get(group, [])):
            if isinstance(item, str):
                raw = delivery = item
                normalization = []
                provenance = "review_approved"
                approval = "pending"
            else:
                raw = item.get("raw", "")
                delivery = item.get("locked_text", "")
                normalization = item.get("normalization", [])
                provenance = item.get("provenance", "review_approved")
                approval = "pending" if item.get("requires_approval") or provenance == "review_approved" else "approved"
                if provenance == "source_normalized":
                    normalized = raw
                    for operation in normalization:
                        if operation == "unit:g→克":
                            normalized = normalized.replace("g", "克")
                        else:
                            approval = "pending"
                    if normalized != delivery:
                        approval = "pending"
            start = source_text.find(raw)
            span = [start, start + len(raw)] if start >= 0 else [-1, -1]
            if provenance.startswith("source_") and start < 0:
                approval = "pending"
                provenance = "review_approved"
            hooks.append({
                "id": "%s-%d" % (group, index + 1), "kind": kind, "raw": raw,
                "delivery_text": delivery, "source_span": span,
                "normalization_ops": list(normalization), "provenance": provenance,
                "approval_status": approval,
                "safety_disposition": "verbatim" if approval == "approved" else "pending",
            })
    title = source["title"]
    migrated = {
        "schema_version": SCHEMA_VERSION,
        "stage": "parsed_checked",
        "source": source,
        "hooks": {"verbatim": hooks, "semantic_strength": []},
        "review_findings": [],
        "title_review": {"decision": "unchanged", "title": title, "reason_codes": [], "rationale": ""},
        "internal_review": deepcopy(data.get("internal_review", {"licensed_physician_review_required": True})),
    }
    return validate_parsed_state(migrated)

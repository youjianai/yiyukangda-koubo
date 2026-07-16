# 解析与核对规范（schema v3）

本文件只定义解析、来源、审批和专业核对的内部状态。口播写法见 `rewrite_playbook.md`，公开交付见 `output_format.md`。

## 一、内部状态

解析完成后必须生成 `schema_version=3、stage=parsed_checked`：

```json
{
  "schema_version": "3",
  "stage": "parsed_checked",
  "source": {"link": "", "title": "原标题", "text": "原文"},
  "hooks": {
    "verbatim": [],
    "semantic_strength": []
  },
  "review_findings": [],
  "title_review": {
    "decision": "unchanged",
    "title": "原标题",
    "reason_codes": [],
    "rationale": ""
  },
  "internal_review": {"licensed_physician_review_required": true}
}
```

标题只通过 `source.title + title_review` 管理，不再称为普通 lock。

## 二、字面保全 hooks

`hooks.verbatim` 每项结构：

```json
{
  "id": "formula-1",
  "kind": "formula_item",
  "raw": "荷叶10g",
  "delivery_text": "荷叶10克",
  "source_span": [20, 25],
  "normalization_ops": ["unit:g→克"],
  "provenance": "source_normalized",
  "approval_status": "approved",
  "safety_disposition": "verbatim"
}
```

`kind`：`formula_item / disease / syndrome / numeric_hook / fixed_phrase`。`numeric_hook` 不只包含营销比例，也包含经批准必须保留、但未被完整方剂条目覆盖的时间、频次、步骤数量和原始数字表达。

只有同时满足以下条件的条目才成为正文硬约束：

- `approval_status=approved`
- `safety_disposition=verbatim`
- 来源或规范化可验证

安全处置：

- `verbatim`：可原样进入正文
- `demoted`：保留安全语义，不保留危险原句
- `rejected`：不得进入公开文本
- `pending`：等待审批，阻断导出

这样医疗安全优先于锁定项：危险内容不会先成为硬锁，再与安全规则死锁。

### 来源规则

- `source_verbatim`：`raw == delivery_text`，且 `source_span` 精确指向原文。
- `source_normalized`：只做确定性名称或单位规范化，必须记录 `normalization_ops`，且 `source_span` 精确指向连续原文 `raw`。
- `user_required`：用户明确要求，仍需通过医疗安全；若不是原文连续片段，`source_span` 使用 `[-1,-1]`，不得伪造位置。
- `review_approved`：专业核对或外部审批新增；若不是原文连续片段，`source_span` 使用 `[-1,-1]`。模型只能生成 pending candidate，不能自行声明审批完成。

来源可追溯且未命中硬红线的原稿项，默认可以批准为 `verbatim`；“原文出现不自动成为硬锁”只用于危险内容、歧义规范化和专业新增，不得被解释为普遍降级原稿。

## 三、语义力度 hooks

`hooks.semantic_strength` 用于稀缺、情绪、紧迫、身份、反差和互动等只保力度或功能、不保原句的钩子：

```json
{
  "id": "scarcity-1",
  "kind": "scarcity",
  "source_text": "很多人花钱都学不到",
  "source_span": [30, 40],
  "truth_status": "verified",
  "safety_disposition": "demoted"
}
```

`kind`：`scarcity / emotion / urgency / identity / contrast / engagement`。

`engagement` 记录点赞、评论、关注、收藏等参与动作。正常二创使用 `truth_status=verified + safety_disposition=demoted`，表示保留至少一种原互动功能但必须换说法，不锁整句。

身份、资历、患者经历、祖传年限和平台下架记录若无来源，必须标为 `unverified + pending/rejected`，不得注入成稿。

## 四、专业核对结果

所有鉴别、禁忌、使用提醒、炮制和穴位核对写入 `review_findings`：

```json
{
  "id": "finding-1",
  "kind": "contraindication",
  "text": "青光眼患者不建议使用。",
  "target": "tips",
  "approval_status": "approved",
  "source": ""
}
```

`target` 只能是 `notes / tips / processing`。当前暂停联网时 `source` 为空；把握不准不写。只有 approved finding 才能进入公开投影。

## 五、标题裁决

`title_review.decision`：

- `unchanged`：标题原样保留；百分比、「排石方」「土方法」和互动话术本身不构成修改理由
- `safety_adjusted`：命中明确硬红线后只修改危险跨度，填写 `reason_codes/rationale`，并保留无风险数字、悬念和利益点
- `blocked_editorial_review`：安全与流量无法兼顾，停止导出交编导裁决

`reason_codes` 仅允许：

- `ordinary_sign_severe_disease`
- `efficacy_guarantee`
- `replace_regular_care`
- `acute_care_delay`
- `peer_attack`
- `uncontrollable_outcome`
- `unverified_identity`

无法用上述硬红线高置信解释时，标题必须 `unchanged`；不能把一般比例争议、方剂词或风格偏好包装成安全理由。

## 六、审批状态

`pending` 条目不得进入 rewrite 的有效约束，也不得导出。外层流程取得用户、编导或专业审核后才能写入独立审批结果；模型不能把自己的建议直接改成 approved。

## 七、v2 兼容

正式新输入使用 v3。旧 v2 只通过 `scripts/handoff_contract.py:v2_to_v3()` 显式迁移：能在原文定位且无歧义的条目可批准；纯字符串、`review_approved` 或来源不明内容迁移为 pending，不静默放行。

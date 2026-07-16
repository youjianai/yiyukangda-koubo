# 输出与交付契约（schema v3）

本文件只定义 rewritten handoff、公开投影和 DOCX 映射。解析内部状态见 `parse_check_spec.md`，写法见 `rewrite_playbook.md`。

## 一、正式 rewritten handoff

新流程使用 `schema_version=3`：

```json
{
  "schema_version": "3",
  "stage": "rewritten",
  "filename": "眼睛模糊-洗稿文档",
  "items": [
    {
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
      "review_record": {
        "narrative_chain": true,
        "hook_and_title": true,
        "rewrite_quality": true,
        "medical_boundary": true,
        "lock_provenance": true,
        "oral_naturalness": true,
        "guidance_fit": true
      },
      "warning_decisions": {},
      "public": {
        "link": "",
        "title": "原标题",
        "script": "洗稿后的口播正文",
        "notes": [],
        "tips": [],
        "processing": []
      }
    }
  ]
}
```

契约：

- `stage` 必须为 `rewritten`；`validated/exported` 是脚本运行结果，不由模型预填。
- `source/hooks/review_findings/title_review/review_record/warning_decisions/public` 必须存在，未知字段拒绝。
- 只有 `approval_status=approved + safety_disposition=verbatim` 的 hooks 会编译为正文硬约束。
- pending hook 不成为硬约束；pending review finding 阻断导出。
- `public.notes/tips/processing` 必须与 approved review findings 的确定性投影完全一致，模型不得另写一份不同内容。
- `title_review` 只允许 `unchanged / safety_adjusted / blocked_editorial_review`；blocked 状态不能导出。
- `review_record` 是流程证明，不等于机器自动证明写作质量；任何 false 都阻断。
- warning 必须基于当前正文复检；仍存在的 warning 只允许有理由的 `false_positive` 或 `accepted_with_reason`，不接受裸 `resolved`。

## 二、v2 兼容

`scripts/build_docx.py` 暂时继续读取旧 `schema_version=2` rewritten handoff，供已有调用方迁移。新 prompt 和新流程不得再生成 v2。v2 的字符串 locks、自由审批和旧 warning 语义不进入 v3。

## 三、公开投影

脚本从 v3 handoff 确定性投影为：

```json
{
  "filename": "眼睛模糊-洗稿文档",
  "items": [
    {
      "link": "",
      "title": "标题",
      "script": "口播正文",
      "notes": [],
      "tips": [],
      "processing": []
    }
  ]
}
```

顶层只允许 `filename/items`；item 只允许 `link/title/script/notes/tips/processing`；后三段 entry 只允许 `text/source`。hooks、审批、review record、warning decisions 和 provenance 不进入公开 Word。

## 四、正文与规范化

- 正文 ≤300 字，用自然段换行，不写 Markdown 小标题。
- 禁用标点和单位以 `validate_output.py` 为机器事实源。
- 输入只允许确定性的换行规范化；正文每行首尾空白直接拒绝，不在渲染阶段静默删除。
- validator 校验的 `public.script` 由 DOCX 渲染器原样按换行拆段，不再生成另一份字符串。

## 五、Word 排版

输出顺序：视频链接、标题、正文自然段、notes、tips、processing。后三段用 `【】` 包裹；tips 按“禁忌人群”拆块。单篇不加序号，多篇加「第N条」和浅灰分隔线。正文宋体五号 10.5pt。

## 六、导出

```bash
python scripts/build_docx.py <handoff.json> [output_dir]
```

- UTF-8 和 UTF-8 BOM JSON 均可读取。
- handoff 只读取一次，先完整校验，再渲染同一公开投影。
- 批量任一项失败不创建最终文件。
- 最终发布使用原子 no-clobber；同名文件已存在或生成期间出现时拒绝覆盖。
- filename 必须是安全 basename，拒绝路径、Windows 设备名和过长名称。
- 临时 handoff 与 DOCX 使用系统临时目录；不删除或覆盖用户文件。

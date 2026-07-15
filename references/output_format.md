# 输出与交付契约

本文件是第 5 步 canonical handoff、公开字段投影和 DOCX 映射的权威来源。洗稿写法不在本文件定义。

## 一、canonical handoff

正式导出输入必须是 UTF-8 JSON：

```json
{
  "schema_version": "2",
  "stage": "rewritten",
  "filename": "脂肪肝-洗稿文档",
  "items": [
    {
      "source": {
        "link": "https://...",
        "title": "原标题",
        "text": "原口播文案"
      },
      "locks": {
        "formula_items": [{"raw": "荷叶10g", "locked_text": "荷叶10克", "normalization": ["unit:g→克"], "provenance": "source_normalized", "requires_approval": false}],
        "diseases": [{"raw": "脂肪肝", "locked_text": "脂肪肝", "normalization": [], "provenance": "source_verbatim", "requires_approval": false}],
        "syndromes": [],
        "numeric_hooks": []
      },
      "title_decision": {
        "type": "unchanged",
        "rationale": ""
      },
      "manual_checks": {
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
        "link": "https://...",
        "title": "原标题",
        "script": "洗稿后的口播正文",
        "notes": [{"text": "鉴别诊断或穴位定位"}],
        "tips": [{"text": "适用人群、禁忌人群和注意"}],
        "processing": [{"text": "采摘与炮制"}]
      }
    }
  ]
}
```

契约：

- `stage` 必须为 `rewritten`；`validated/exported` 只能由脚本产生，不由模型预填。
- `source`、四类 locks、7 个人工卡口和 `public` 必须存在；空 locks 用 `[]`，不能省略。
- lock 可用上述对象；旧数据中的纯字符串仅作为迁移兼容，等价于 `locked_text=该字符串`。
- `title_decision.type` 只能为 `unchanged` 或 `safety_adjusted`。前者要求 `public.title == source.title`；后者必须有非空 rationale，且只允许按 `SKILL.md` 做最小安全修改。
- `warning_decisions` 的键是 validator warning ID；值为 `resolved / false_positive / accepted_with_reason` 和非空理由。未处置 warning 阻断导出。
- `public` 不得含 `locks/internal_review/manual_checks/validation/source/title_decision/warning_decisions`。
- 字段职责是正式 handoff 门禁：`script` 只放口播内容，不得含防御性审稿腔或标准括注之外的额外辨证前提；`notes` 放鉴别诊断、非唯一病因等补充；`tips` 放完整适用/禁忌、辨证与使用边界；`processing` 只放采摘、炮制和储存。具体写法与急重病正文例外以 `rewrite_playbook.md` 为准。

## 二、公开投影

脚本从 canonical handoff 确定性投影为：

```json
{
  "filename": "脂肪肝-洗稿文档",
  "items": [
    {
      "link": "https://...",
      "title": "标题",
      "script": "口播正文",
      "notes": [],
      "tips": [],
      "processing": []
    }
  ]
}
```

严格白名单：

- 顶层只允许 `filename/items`。
- item 只允许 `link/title/script/notes/tips/processing`。
- 后三段 entry 只允许 `text/source`；当前暂停联网时 `source` 应为空或省略。
- 未知字段和内部字段一律拒绝，不做“忽略后继续”。

## 三、正文与数字

- 正文用自然段换行，不写 Markdown 标题或小标题。
- 正文 ≤300 字，无禁用标点、字母单位和 `【】`。
- 不执行“所有数字全局转阿拉伯数字”。标题、数字钩子、剂量、时间和原始份量词按锁定表达保留；`五片、三瓣、一大把`不得改成 `5片、3瓣、1大把`。
- `notes/tips/processing` 不得包含复核免责声明。

## 四、Word 排版

输出顺序：

1. 视频链接，粗体标签与内容同行
2. 标题，标签和标题内容粗体
3. 口播正文，自然段分行，无正文小标题
4. `notes`
5. `tips`
6. `processing`

后三段每块用 `【】` 包裹，不加粗小标题；空段跳过。`tips` 按“禁忌人群”拆为适用人群一块、禁忌人群+注意一块。单篇不加序号；多篇加「第N条」并用浅灰细横线分隔。正文宋体五号 10.5pt。

## 五、导出

将 handoff 放系统临时目录，在 Skill 根目录运行：

```bash
python scripts/build_docx.py <handoff.json路径> [输出目录]
```

脚本读取一次 handoff，对每个 `public.script` 做 preflight，再用同一字符串渲染。批量任一项失败则不创建最终 DOCX。filename 必须是安全 basename，不得包含绝对路径、`..`、目录分隔符或 Windows 保留名。

流程只删除自己创建的临时 handoff；不得删除或覆盖既有用户文件。默认输出到桌面，测试必须显式传临时输出目录。

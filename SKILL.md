---
name: yiyukangda-koubo
description: |
  医誉康达抖音/视频号口播脚本写作与文档整理skill。
  输入：一条抖音医生（黄V）口播视频链接，或附带已提取的文案。
  自动完成五步：1.接收文案 2.解析病症/方剂/药材/穴位 3.核对专业信息 4.洗稿 5.整理成标准文档。
  触发词：「帮我洗稿」「处理这条视频」「做个脚本」「整理这条」「洗一下这个链接」以及直接把抖音链接发过来。
  不要用于：公众号长文写作（用 khazix-writer）、小红书图文、产品详情页文案。
allowed-tools: Read, Bash, Write, Edit, Glob
dependencies: python-docx
---

# 医誉康达口播处理

## 成功标准

在不降低原稿流量张力、口播自然度和核心干货完整度的前提下完成高质量二创，并输出通过机器门禁的标准 Word。五步流程、叙事链、≥30% 二创、锁定项保全、正文 ≤300 字和固定 DOCX 排版不得退化。

## 默认任务与编辑尺度

本 Skill 默认处理的是已经通过抖音审核、可正常发布的原始视频文案。任务是保住原稿流量骨架和核心干货后完成传统洗稿，不是重新改造成防御性医学科普。

- 原稿是编辑尺度基线，默认继承原标题、精确数字、互动功能、病机、方药剂量、功效方向和医生直接对观众落方的视角。
- 传统洗稿仍须完成 ≥30% 二创；“最小介入”只指安全风险跨度最小，不是全文少改或照抄。
- 平台过审不等于医学事实、身份资历或病例真实性已获证明；来源、审批和执业医师终审要求不变。
- 直接重讲原稿已有方子不等于教唆用偏方替代正规诊疗。只有明确宣称替代必要治疗时才按硬红线处理。
- 普通稿不自动添加「不能替代规范诊疗」「请咨询医生」「由专科医生综合评估」等防御性模板。鉴别、完整禁忌、常规治疗、复查和非急症就医边界优先下沉到 `notes/tips`。

## 全局优先级

出现冲突时按下列顺序裁决，低层规则不得覆盖高层规则：

1. 明确硬红线：保证治愈或预后、鼓励偏方替代必要治疗、延误急重病就医、把普通体征直接等同癌症/重病、虚构身份资历病例、攻击同行、保证不可控结果
2. 用户额外指令，但仅在第 1 项允许的范围内
3. 经批准的 hooks、医学事实和原稿功能节点
4. 标题、数字、互动、稀缺、反差、情绪等流量张力
5. 叙事完整、≥30% 二创和口播自然度
6. 300 字、格式和一般风格
7. 示例文本；示例永远不创设规则

标题默认原样保留。百分比、「排石方」「土方法」和互动话术本身不构成改题理由。若标题命中第 1 项硬红线，只做**最小安全修改**，保留无风险数字、悬念、反差和利益点；无法兼顾时停止导出，交编导裁决。

## 五步状态机

内部阶段依次为 `received → parsed_checked → rewritten → validated → exported`。不得跳阶段；公开交付中不显示阶段数据。

### 1. 接收与质检 `received`

- 链接附文案时直接处理；只有链接没有文案时回复「文案发来」。
- 收到文案后输出钩子、干货、赛道三项质检。三项全过才继续；明显缺失时如实列出，等待用户决定。
- 原文 ≥350 字时预留更积极的压缩预算，但不得压掉锁定项、核心干货或必要叙事节点。

### 2–3. 解析与专业核对 `parsed_checked`

先 `Read references/parse_check_spec.md`，按其中契约生成内部解析状态：病症、方剂、单药材、穴位、`hooks`、provenance 和专业核对结果。

当前暂停联网。把握不准时不写或保守写，不附来源、不编造；鉴别诊断、禁忌、炮制、穴位核对默认进入 `notes/tips/processing`，不自动挤入口播正文。内部保留 `licensed_physician_review_required=true`，对外正文和 Word 不显示复核免责声明。

### 4. 洗稿 `rewritten`

洗稿前必须 `Read references/rewrite_playbook.md`。该文件是洗稿语义与叙事方法的权威来源；按「拆功能段 → 搭问答链 → 顺链重讲 → 一次通读」执行。

钩子分两类：

- `verbatim`：精确数字、方剂、病症、已批准证型、固定口诀等，按 `delivery_text` 字面保全；标题单独由 `source.title + title_review.title` 管理。
- `semantic_strength`：稀缺、情感、紧迫、身份、反差和互动等，保留或增强力度及功能，但必须用自己的话重讲；互动至少保留原稿的一类点赞、评论、关注或收藏动作，不锁整句。

完成后做 7 组人工卡口：

1. 叙事链和引导语前后双接缝
2. 钩子力度与标题安全裁决
3. ≥30% 二创、非逐句对译和口播完整度
4. 医学因果、疗效承诺和就医边界
5. 锁定项、规范化和 provenance 一致
6. 关联词、指代、铺垫、完整句和真人听感
7. 引导语主题、库卫生和 300 字预算适配

### 5. 校验与导出 `validated → exported`

正式交付只接受 `references/output_format.md` 定义的 canonical handoff。运行：

```bash
python scripts/build_docx.py <handoff.json> [output_dir]
```

`build_docx.py` 必须对即将写入 Word 的同一份正文逐条执行 schema、locks、正文规则和 warning 处置校验；批量任一条失败则整批不生成。禁止先校验字符串 A、再导出 JSON 中的字符串 B。

兼容调试时可单独运行：

```bash
python scripts/validate_output.py '正文' --formula-items "荷叶10克,陈皮6克" --diseases "脂肪肝" --syndromes "痰湿内盛"
```

旧 `--herbs` 仅兼容历史调用，不写入新文档或新示例。正式导出不得使用逗号参数替代结构化 locks manifest。

## Reference 路由

- `references/parse_check_spec.md`：第 2–3 步的字段、锁定项、规范化、provenance 与专业核对。
- `references/rewrite_playbook.md`：第 4 步的叙事链、A–F 写法、人工卡口与引导语落地。
- `references/output_format.md`：canonical handoff、公开字段投影和 DOCX 映射。
- `references/style_examples.md`：仅在写法不明确时按指定章节读取；示例不是规则。
- `references/ending_variants.md`：收尾节点需要变体时读取。
- `references/guidance_library.json`：只由 `scripts/pick_guidance.py` 读取；不得手工随机复制未审核条目。

## 引导语库

- 先按正文剩余预算和稿件类型调用 `pick_guidance.py --content-type <general_health|formula|acupoint|kitchen_tip> --placement pre_content --max-chars N --count 3`；回归时必须传 `--seed`。
- 候选 JSON 含 `id/text`；只使用 `review_status=approved`、位置和类型匹配且不要求未验证身份事实的候选。
- 已审核候选不逐字手洗，只允许删除与上下文重复的前缀并在段外补桥；首次候选集内可改选一次，不重新抽池。候选都不搭时允许用一句短承接或不加长引导语。
- 新条目先按库 schema 标注 `id/review_status/content_types/placement/persona_requirements/risk_tags/char_count`，再做精确去重、相似项复核和 validator 兼容检查。
- 入库后运行：

```bash
python -m unittest tests.test_regression.GuidanceLibraryTests -v
```

## 硬边界

- 正文 ≤300 字，禁冒号、破折号、中文/英文双引号和 `【】`；字母计量单位改为汉字。
- 数字按批准表达分类保留：标题/数字钩子/剂量/时间/原始份量词不做全局转换；`五片、三瓣、一大把`不得擅自改为阿拉伯数字。
- 正式新交付使用 `schema_version=3`，由 approved hooks 编译正文硬约束、approved review findings 确定性投影后三段；旧 v2 仅保留兼容读取。
- 所有医学内容最终须经执业医师终审；模型不负责最终医学判断、原始素材真伪或发布决策。
- 公开 JSON 与 Word 只含 `filename/items/link/title/script/notes/tips/processing`；`hooks/internal_review/review_record/warning_decisions/validation` 不得进入公开投影。
- 临时 handoff 放系统临时目录；只清理由本流程创建的临时文件，不删除或覆盖既有用户文件。
- 每步完成后简短告知进度；内部 prompt 的纯 JSON 输出由外层流程负责包装，不与用户进度文本混写。

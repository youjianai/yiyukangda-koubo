# 回归测试约定

本项目只声明已经实现的验证能力。规则改动先补确定性失败样例，再改实现；真人口播质量由真实案例人工评审，不伪装成正则或虚假的统计结论。

## 目录

```
tests/
  README.md
  test_regression.py
  test_v2_regression.py
  fixtures/
    <case-id>/
      case.json
      input.txt
      expected_checks.md
      failed-output-*.txt     # 完整真实失败稿，可选
      approved-output.txt     # 已获用户确认的质量基线，可选
  baseline/
    <immutable-id>/
      manifest.json
      prompt_bundle.zip
```

## 确定性回归

从 Skill 根目录运行：

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

自动测试覆盖：

1. schema、来源、审批、锁定项和字数。
2. 高置信医疗安全、禁用标点、证型括注和查重。
3. 引导语库审核状态、内容类型、插入位置、身份要求和预算。
4. canonical handoff、公开字段投影、CLI、DOCX 排版与 OOXML 内部字段泄漏。
5. 批量原子失败、UTF-8 BOM、Windows 文件名和拒绝覆盖。

测试数量以实际运行结果为准，不在文档中硬编码。

## 结构化 fixture

- `case.json` 是输入、旧版 locks 兼容数据和机器断言的事实源；正式新增 canonical handoff 使用 schema v3 hooks。
- `input.txt` 必须与 `case.json.source.text` 一致。
- `expected_checks.md` 只写人工语义检查，不创设机器规则。
- 完整失败稿必须保留真实上下文，不能只冻结孤立坏词。
- approved output 只在用户明确确认后写入，用于防止口播质量回退；确认的是完整文本时逐字冻结，不以“方向认可”为由自行补写。
- 防御性科普回归至少覆盖擅自改标题/数字、删除互动、旁观式配伍桥和正文泛化诊疗说明。
- 临时 handoff 和 DOCX 全部放 `TemporaryDirectory()`，不在桌面或 Skill 目录留产物。

## 轻量人工 A/B 评审

当前不使用 LLM judge，也不声称已有 bootstrap 统计平台。选择 6–8 个代表性真实案例，隐藏版本标签后做配对评审：

- 第一遍听是否顺
- 叙事是否自然向前
- 钩子力度
- 引导语是否贴合
- 核心干货是否完整
- 医学边界是否安全且不过度说明书化

硬否决项：虚构身份或经历、保证疗效、替代就医、药材剂量/病名/证型丢失、明显机械模板、需要倒回去才能听懂。

每个案例至少两名评审；总体中位数不得下降，任一案例下降超过 1 分时专项复核。样本量不足时不使用 95% bootstrap 置信区间制造统计精确感。

## 项目运行验证

非文档改动完成后执行项目 scoped verify，走公开 `build_docx.py` CLI，检查：

- stdout/stderr 原始 bytes 可 UTF-8 strict decode
- DOCX 正文与 validated script 一致
- OOXML 不含 locks、审批记录、warning 决议和 provenance
- 批量失败不留最终产物
- 已有同名文件不被覆盖

# 回归测试约定

改规则前先冻结当前工作树基线，改完后同时跑确定性回归和写作质量回归。测试不把 Git `HEAD` 自动视为基线，因为工作树可能含尚未提交但已经过用户确认的规则。

## 目录与命名

```
tests/
  README.md
  test_regression.py          # 确定性脚本回归，默认执行
  run_quality_eval.py         # 质量样本采集/盲评打包，不进入默认 unittest
  baseline/
    YYYY-MM-DD-current/       # 当前工作树快照元数据；目录名固定日期+current
      manifest.json
      prompt_bundle.zip       # 只保存规则/prompt/reference，不含密钥和产物
  fixtures/
    <case-id>/                # 小写英文、数字和连字符，如 01-foot-soak
      case.json               # 唯一机器契约
      input.txt               # 供人工粘贴的原文副本
      expected_checks.md      # 供编导阅读的语义卡口
      outputs/                # live runner 生成；按 before/after + trial 编号命名
```

约束：

- 新 case 先写 `case.json`，再补文本和人工说明；标题、链接、原文、locks 都必须有明确来源。
- `case.json` 只记录输入、机器断言和人工评分维度，不保存密钥、token 或账号信息。
- `outputs/` 只放模型原始输出和运行元数据；不覆盖已有 trial，重复运行使用下一编号。
- 临时 DOCX 和 handoff 使用系统临时目录；测试自行创建的临时文件由测试清理，不在桌面或 Skill 目录留产物。
- baseline 只追加新目录，不覆盖旧基线；如基线无对应 prompt bundle，不得宣称可做 before/after 比较。

## 使用方法

从 Skill 根目录运行，或使用绝对测试路径：

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

测试分为三层：

1. **确定性自动回归**：检查 schema、锁定项、字数、禁用项、引导语选择、导出门禁和 Word 排版，必须 100% 通过。
2. **结构化 case 断言**：检查 required/forbidden literals、标题裁决、锁项和导出结果；不把语义写作质量伪装成正则。
3. **人工盲评**：同一运行时、同一输入、同一候选做 before/after 多 trial，对钩子、二创、叙事链、口播感、医学边界和完整度评分。

若某项失败，先判断是确定性脚本 bug、规则冲突，还是写作质量退化，再只改对应层。

## 质量发布门槛

- 所有确定性回归通过，硬否决事件为 0。
- 总体配对评分的 95% bootstrap 置信区间下界不低于 -0.15/5。
- 钩子力度和二创质量两个核心维度下界不低于 -0.20/5。
- 任一 case 中位数下降超过 0.5 分时必须专项复核。
- after 最差 20% 样本必须人工复核，排查模板化、安全规则过度软化和核心干货损失。

## 现有人工案例迁移

原 `case_01_桃树叶泡脚`、`case_02_胆结石` 保留为历史可读材料；结构化契约迁入 `fixtures/` 后，以 `case.json` 为机器事实源。
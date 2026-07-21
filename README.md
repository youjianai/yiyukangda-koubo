# 医誉康达口播处理 (yiyukangda-koubo)

抖音/视频号医生口播脚本写作与文档整理 skill——五步流水线完成接收→解析→核查→洗稿→导出标准 Word。

## 一句话

丢一个抖音医生视频链接过来，自动扒文案、查医学事实、洗稿二创（≥30%），输出排版好的 .docx。

## 装完直接用

```
帮我处理这条视频：https://v.douyin.com/xxxxx/
```
或直接把链接发过来即可。

## 依赖

```bash
pip install python-docx
```

## 目录结构

```
yiyukangda-koubo/
  SKILL.md                    # 完整五步流程 + 安全红线
  references/
    rewrite_playbook.md        # 洗稿手册（拆段→问答链→重讲）
    parse_check_spec.md        # 解析/核查规范
    output_format.md           # 规范交付格式 (schema v3)
    style_examples.md          # 改写前后对比示例
    ending_variants.md         # 收尾变体模板
    guidance_library.json      # 引导语文案库
  prompts/
    parse_and_check.md         # 解析+核查提示模板
    rewrite.md                 # 洗稿提示模板
  scripts/
    build_docx.py              # 交付 JSON → 排版 .docx
    validate_output.py         # 程序化输出校验
    handoff_contract.py        # schema 契约定义
    pick_guidance.py           # 引导语库选择器
    count_chars.py             # 字数统计
    web_lookup.py              # 联网查证
  tests/
    fixtures/                  # 3 组测试病例 + 已批准/失败对照
    test_regression.py         # 回归测试
    test_v2_regression.py      # V2 兼容性回归
```

## 安全边界

- 不降低原稿流量张力和核心干货完整度
- 不低于 30% 二创
- 正文 ≤300 字，不改动锁定的医学事实项
- 不教唆用偏方替代正规诊疗
- 不自动添加防御性免责模板（鉴别/禁忌/复查下沉到 notes/tips）
- 输出前须由执业医师终审

## License

MIT

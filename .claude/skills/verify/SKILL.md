---
name: verify
description: 通过公开 CLI 验证 canonical handoff 到 DOCX 的运行时行为
---

# 医誉康达口播运行验证

从 Skill 根目录运行，临时输入、输出全部放 `tempfile.TemporaryDirectory()`。

## 主路径

1. 写入完整 `schema_version=2`、`stage=rewritten` canonical handoff JSON。
2. 用 subprocess 调用公开入口：
   `python scripts/build_docx.py <handoff.json> <temp-output-dir>`
3. 对 stdout/stderr 原始 bytes 执行 UTF-8 strict decode。
4. 用 `python-docx` 打开生成文件，确认 `public.script` 原样存在。
5. 用 `zipfile` 读取 `word/document.xml`，确认不含 `locks/manual_checks/warning_decisions/provenance` 等内部字段。

## 破坏性探针

- 在批量 handoff 第二条放入空正文，确认 CLI 非零退出且输出目录为空。
- 对已存在同名 DOCX 再运行，确认拒绝覆盖且原文件 bytes 不变。
- 只在完整 unittest 之外执行此运行验证；运行验证本身不 import 内部函数。

## 注意

- Git Bash 终端可能把 UTF-8 中文显示为乱码；以 Python 对捕获 bytes 的 `decode("utf-8", errors="strict")` 是否成功和 JSON `ensure_ascii=True` 证据为准。
- 不在桌面留验证产物，不删除或覆盖用户文件。

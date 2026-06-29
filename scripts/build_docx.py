"""医誉康达口播洗稿文档渲染器（固化导出脚本）。

用法：
    python build_docx.py <input.json> [output_dir]

input.json 结构（UTF-8）：
{
  "filename": "脂肪肝-洗稿文档",   // 不含 .docx，可省略，默认「医誉康达-洗稿文档」
  "items": [
    {
      "link": "https://...",
      "title": "白开水里煮两物，帮你养养肝",
      "script": "首句口语自然即可、不必逐字等于标题\n第二段\n第三段",   // 字符串按换行分段，或直接给段落数组
      "notes":      [ {"text": "脂肪肝鉴别诊断：...", "source": "..."} ],
      "tips":       [ {"text": "适用人群：...\n禁忌人群：...", "source": "..."} ],
      "processing": [ {"text": "荷叶的采摘与炮制：...", "source": "..."} ],
    }
  ]
}

排版规则（固定，不随每次任务改动）：
- 多篇（items 多于 1 条）时每篇开头加「第N条」加粗序号；单篇不加
- 条与条之间用浅灰细横线分隔（不强制分页，避免页底大片空白）
- 视频链接 / 标题：粗体标签与内容同行（「视频链接：URL」「标题：内容」）
- 口播脚本文案：无小标题，直接放正文
- 备注 / 温馨提示 / 采摘与炮制：不加粗小标题，内容用【】包裹
- 温馨提示自动按「禁忌人群」拆分为独立【】块（适用人群一块、禁忌人群+注意一块）
- 某段无内容则整段跳过（不输出空【】）
- 不对正文做标点改写，输入什么排什么（标点合规在洗稿环节把控）
- 正文宋体五号（10.5pt），标题加粗五号
"""

import json
import os
import sys

from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BODY_FONT = "宋体"
BODY_SIZE = 10.5
HEADING_SIZE = 10.5
SOURCE_SIZE = 9
SOURCE_COLOR = RGBColor(0x80, 0x80, 0x80)
SECTION_ORDER = [
    ("notes", "备注"),
    ("tips", "温馨提示"),
    ("processing", "采摘与炮制"),
]


def set_cjk_font(run, name=BODY_FONT):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rpr.rFonts.set(qn("w:eastAsia"), name)


def add_inline_label(doc, label, content, bold_content=False):
    """粗体标签 + 正文内容在同段（用于视频链接、标题）。"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run_label = p.add_run(label)
    run_label.bold = True
    run_label.font.size = Pt(HEADING_SIZE)
    set_cjk_font(run_label)
    run_content = p.add_run(content)
    run_content.font.size = Pt(BODY_SIZE)
    if bold_content:
        run_content.bold = True
    set_cjk_font(run_content)
    return p


def add_body(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(BODY_SIZE)
    set_cjk_font(run)
    return p


def add_source(doc, source):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("来源：" + source)
    run.font.size = Pt(SOURCE_SIZE)
    run.font.color.rgb = SOURCE_COLOR
    set_cjk_font(run)
    return p


def add_separator(doc):
    """条与条之间的浅灰细横线分隔（替代强制分页，避免页底大片空白）。"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(10)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "BFBFBF")
    pBdr.append(bottom)
    pPr.append(pBdr)
    return p


def add_index(doc, n):
    """多篇文档里每篇开头的数字序号「第N条」（加粗，略大于正文）。"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("第{}条".format(n))
    run.bold = True
    run.font.size = Pt(12)
    set_cjk_font(run)
    return p


def split_script(script):
    if isinstance(script, list):
        return [s for s in (str(x).strip() for x in script) if s]
    return [line.strip() for line in str(script).split("\n") if line.strip()]


def normalize_entries(value):
    """把 notes/tips/processing 统一成 [{'text':.., 'source':..}] 列表。"""
    if not value:
        return []
    if isinstance(value, str):
        return [{"text": value, "source": None}]
    out = []
    for e in value:
        if isinstance(e, str):
            out.append({"text": e, "source": None})
        else:
            out.append({"text": e.get("text", ""), "source": e.get("source")})
    return [e for e in out if e["text"].strip()]


def render_item(doc, item):
    # 视频链接：粗体标签 + URL 同行
    link = item.get("link", "").strip()
    if link:
        add_inline_label(doc, "视频链接：", link)

    # 标题：粗体标签 + 粗体内容同行
    title = item.get("title", "").strip()
    if title:
        add_inline_label(doc, "标题：", title, bold_content=True)

    # 口播脚本文案：去掉标题，直接放正文
    for para in split_script(item.get("script", "")):
        add_body(doc, para)

    # 后三段：不加粗小标题，内容用【】包裹
    for key, _label in SECTION_ORDER:
        entries = normalize_entries(item.get(key))
        if not entries:
            continue
        # 将所有 text 合并，source 已不加（联网暂停阶段）
        combined = "\n".join(e["text"] for e in entries if e["text"].strip())
        if not combined.strip():
            continue

        if key == "tips":
            # 温馨提示按「禁忌人群」「注意」拆分为独立【】块
            parts = []
            remaining = combined
            for marker in ("禁忌人群", "注意"):
                if marker in remaining:
                    idx = remaining.index(marker)
                    if idx > 0:
                        parts.append(remaining[:idx].strip())
                    remaining = remaining[idx:].strip()
            if remaining:
                parts.append(remaining)
            if not parts:  # 无拆分标记，整体一块
                parts = [combined]
            for part in parts:
                if part:
                    add_body(doc, "【{}】".format(part))
        else:
            add_body(doc, "【{}】".format(combined))


def build(data, output_dir):
    items = data.get("items") or []
    if not items:
        raise SystemExit("input.json 里 items 为空，没有可渲染的条目")

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(BODY_SIZE)
    normal.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), BODY_FONT)

    multi = len(items) > 1
    for idx, item in enumerate(items):
        if idx > 0:
            add_separator(doc)
        if multi:
            add_index(doc, idx + 1)
        render_item(doc, item)

    filename = (data.get("filename") or "医誉康达-洗稿文档").strip()
    if not filename.endswith(".docx"):
        filename += ".docx"
    out_path = os.path.join(output_dir, filename)
    doc.save(out_path)
    return out_path, len(items)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("用法：python build_docx.py <input.json> [output_dir]")
    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.expanduser("~"), "Desktop"
    )
    if not os.path.isdir(output_dir):
        raise SystemExit("输出目录不存在：" + output_dir)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    out_path, count = build(data, output_dir)
    print("已生成 {} 条 → {}".format(count, out_path))


if __name__ == "__main__":
    main()

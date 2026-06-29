# -*- coding: utf-8 -*-
"""统计口播脚本文案的字数。

用法：
    python count_chars.py "文本内容"           # 命令行参数直接传入
    python count_chars.py --file input.txt     # 从文件读取
    echo "文本内容" | python count_chars.py -  # 从 stdin 读取（- 参数）

统计规则：去掉换行符和首尾空白后，统计剩余字符数（含汉字、标点、数字、字母）。
输出纯数字，可直接填入洗稿自检的 __字 占位符。

因为口播脚本不换行不影响阅读，所以换行不计入字数。
"""
import sys


def count(text: str) -> int:
    """去掉换行和首尾空白后统计字符数。"""
    return len(text.replace("\n", "").replace("\r", "").strip())


def main():
    # 从 stdin 读
    if len(sys.argv) == 2 and sys.argv[1] == "-":
        text = sys.stdin.read()
        print(count(text))
        return

    # --file 参数
    if len(sys.argv) == 3 and sys.argv[1] == "--file":
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            text = f.read()
        print(count(text))
        return

    # 命令行参数直接传入
    if len(sys.argv) >= 2:
        text = " ".join(sys.argv[1:])
        print(count(text))
        return

    # 无参数：尝试 stdin（无管道时显示用法）
    if not sys.stdin.isatty():
        text = sys.stdin.read()
        print(count(text))
        return

    print("用法: python count_chars.py '文本'  |  --file input.txt  |  - (stdin)", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()

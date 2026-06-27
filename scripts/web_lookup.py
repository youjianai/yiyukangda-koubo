#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
医誉康达口播 skill —— 第三步联网核对检索脚本。

本机环境（中国大陆 + Clash Verge）三轮实测（2026-06-27）结论：
  - WebSearch 工具 schema 报错、WebFetch 走 claude.ai 被国内限制 —— 均不可用。
  - 百度网页搜索：标题可得但摘要走 JS 解析不到，且反爬不稳（偶返空壳页）—— 不作首选。
  - cn.bing：对实词/专名（药材、穴位）好，但把方剂名/双字病症拆成单字 → 字典词条污染。
  - 搜狗（sogou）：对中医方剂名、病症名理解准确，摘要含组成/克数/出处，直连无需代理 —— 主力。
策略：搜狗为主，命中不足时用 cn.bing 补充；后处理过滤广告导流条与字典词条。

用法：
    python web_lookup.py "二陈汤 组成 功效 禁忌" "足三里 定位 主治 禁忌" ...
每个参数一条查询。结果写入同目录 web_lookup_result.txt（UTF-8），再用 Read 工具读，
避免 Windows 终端 GBK 乱码。脚本只检索、不下结论：把摘要+来源原样交回供模型核对。
"""
import sys, re, io, time, pathlib

try:
    import requests
except ImportError:
    print("需要 requests：pip install requests", file=sys.stderr)
    sys.exit(2)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
OUT = pathlib.Path(__file__).with_name("web_lookup_result.txt")

# 字典/无关域名 + 广告导流，命中即丢弃
DICT_DOMAINS = ("zdic.net", "hanyuguoxue", "xinhua", "gushici", "00cha", "zidian")
DICT_KW = ("拼音", "笔顺", "部首", "怎么读", "辞典", "辭典", "会意", "指事", "大写")
AD_KW = ("在线问诊", "快速回复", "分钟快速", "用户好评", "在线咨询", "免费咨询",
         "公立医院医生在线", "立即预约", "挂号")


def strip_tags(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    txt = re.sub(r"(?s)<[^>]+>", " ", html)
    txt = re.sub(r"&nbsp;|&#160;", " ", txt)
    txt = re.sub(r"&amp;", "&", txt)
    txt = re.sub(r"&[a-z]+;|&#\d+;", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def _keep(title: str, url: str, snip: str) -> bool:
    if any(d in url for d in DICT_DOMAINS):
        return False
    if any(k in title for k in DICT_KW):
        return False
    if any(k in (title + snip) for k in AD_KW):
        return False
    return bool(title or snip) and len(snip) > 15


# 查询里的修饰词；从查询中剔除后剩下的是主体核心词
STOPWORDS = frozenset({
    "功效", "作用", "主治", "禁忌", "用法", "用量", "人群", "注意", "事项",
    "中药", "药材", "采收", "采摘", "炮制", "储存", "季节", "产地", "定位",
    "操作", "治疗", "鉴别", "诊断", "泡脚", "煮水", "用", "的", "与", "和",
})


def core_terms(query: str):
    """从空格分隔的查询里取主体核心词（剔除修饰停用词）；全是停用词则退回全部。"""
    toks = [t for t in re.split(r"\s+", query.strip()) if t]
    cores = [t for t in toks if t not in STOPWORDS and len(t) >= 2]
    return cores or toks


def _relevant(title: str, snip: str, cores) -> bool:
    """标题+摘要至少命中一个核心词才算相关；一个都不含=语义离题，丢弃。"""
    if not cores:
        return True
    blob = title + " " + snip
    return any(c in blob for c in cores)


def search_sogou(query: str, top: int = 6):
    r = requests.get("https://www.sogou.com/web", params={"query": query},
                     headers=HEADERS, timeout=20)
    r.encoding = "utf-8"
    if "antispider" in r.text or ("验证码" in r.text and len(r.text) < 20000):
        raise RuntimeError("搜狗触发反爬验证码页，本次跳过、转 bing 兜底")
    out = []
    cores = core_terms(query)
    blocks = re.split(r'(?i)<div class="(?:vrwrap|rb|result)"', r.text)[1:]
    for b in blocks:
        m = re.search(r"(?is)<h3[^>]*>.*?<a[^>]*href=\"([^\"]*)\"[^>]*>(.*?)</a>", b) \
            or re.search(r"(?is)<a[^>]*href=\"([^\"]*)\"[^>]*>(.*?)</a>", b)
        a = re.search(r'(?is)class="(?:text-layout|fz-mid|star-wiki|space-txt)[^"]*"[^>]*>(.*?)</div>', b) \
            or re.search(r"(?is)<p[^>]*>(.*?)</p>", b)
        url = m.group(1) if m else ""
        title = strip_tags(m.group(2)) if m else ""
        snip = strip_tags(a.group(1)) if a else ""
        if _keep(title, url, snip) and _relevant(title, snip, cores):
            out.append({"title": title, "url": url, "snippet": snip[:380]})
        if len(out) >= top:
            break
    return r.status_code, out


def search_bing(query: str, top: int = 6):
    r = requests.get("https://cn.bing.com/search",
                     params={"q": query, "setlang": "zh-CN"},
                     headers=HEADERS, timeout=20)
    r.encoding = "utf-8"
    out = []
    cores = core_terms(query)
    for b in re.findall(r'(?is)<li class="b_algo".*?</li>', r.text):
        m = re.search(r'(?is)<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b)
        cap = re.search(r"(?is)<p[^>]*>(.*?)</p>", b)
        url = m.group(1) if m else ""
        title = strip_tags(m.group(2)) if m else ""
        snip = strip_tags(cap.group(1)) if cap else ""
        if _keep(title, url, snip) and _relevant(title, snip, cores):
            out.append({"title": title, "url": url, "snippet": snip[:380]})
        if len(out) >= top:
            break
    return r.status_code, out


def lookup(query: str):
    """搜狗为主，结果不足 2 条时用 bing 补充。"""
    notes = []
    try:
        sc, items = search_sogou(query)
        notes.append(f"sogou HTTP {sc} → {len(items)} 条")
    except Exception as e:
        items = []
        notes.append(f"sogou跳过: {e}")
    if len(items) < 2:
        try:
            bc, bitems = search_bing(query)
            notes.append(f"bing HTTP {bc} → {len(bitems)} 条")
            seen = {i["title"] for i in items}
            items += [i for i in bitems if i["title"] not in seen]
        except Exception as e:
            notes.append(f"bing ERR {type(e).__name__}")
    return notes, items[:6]


def main():
    queries = sys.argv[1:]
    if not queries:
        print('用法: python web_lookup.py "查询词1" "查询词2" ...', file=sys.stderr)
        sys.exit(1)
    buf = io.StringIO()
    for q in queries:
        notes, items = lookup(q)
        buf.write(f"\n========== 查询: {q} ==========\n")
        buf.write("  [" + " | ".join(notes) + "]\n")
        if not items:
            buf.write("  (无可信结果，换查询词或回退内置知识 + review_note 标注人工复核)\n")
        for i, it in enumerate(items, 1):
            buf.write(f"  {i}. {it['title']}\n")
            if it["url"]:
                buf.write(f"     来源: {it['url']}\n")
            buf.write(f"     摘要: {it['snippet']}\n")
        time.sleep(0.4)
    OUT.write_text(buf.getvalue(), encoding="utf-8")
    print(f"结果已写入: {OUT}")


if __name__ == "__main__":
    main()

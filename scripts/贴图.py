#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 figures/ 里的图表片段按 charts.json 的 after 段号贴进手写网页。

    python3 贴图.py "[报告标题].html" "charts.json" "figures"

只动 <div class="prose"> 里的 <figure class="fig">，不碰区块、章卡、章序和样式。
每次先删掉章内已有的图，再按 after 重插，所以可以反复执行。
after=-1 表示紧跟章标题作首图，after=0 表示插在第一段之后。
"""
import json
import os
import re
import sys

FIG_RE = re.compile(r'<figure class="fig">.*?</figure>', re.S)
PROSE_OPEN_RE = re.compile(r'<div class="prose">')


def prose_inner(block):
    """按 div 嵌套深度找 prose 的闭合位置，避免被图内 </div> 截断。"""
    m = PROSE_OPEN_RE.search(block)
    if not m:
        return None
    start = m.end()
    depth = 1
    i = start
    while i < len(block):
        nxt_open = block.find("<div", i)
        nxt_close = block.find("</div>", i)
        if nxt_close < 0:
            return None
        if 0 <= nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 4
        else:
            depth -= 1
            if depth == 0:
                return start, nxt_close
            i = nxt_close + 6
    return None


def inject(inner, specs, snippets):
    inner = FIG_RE.sub("", inner)
    ends = [m.end() for m in re.finditer(r'</p>', inner)]
    top, buckets = [], {}
    for spec in specs:
        snip = snippets.get(spec["id"])
        if not snip:
            continue
        after = spec.get("after", -1)
        if after is None or after < 0 or not ends:
            top.append(snip)
        else:
            buckets.setdefault(min(int(after), len(ends) - 1), []).append(snip)
    out = inner
    for idx in sorted(buckets, reverse=True):
        pos = ends[idx]
        out = out[:pos] + "".join(buckets[idx]) + out[pos:]
    if top:
        m = re.search(r'<p>', out)
        pos = m.start() if m else 0
        out = out[:pos] + "".join(top) + out[pos:]
    return out


def main(argv):
    if len(argv) < 3:
        print("用法：python3 贴图.py 报告.html charts.json [figures目录]")
        return 2
    html_path, charts_path = argv[1], argv[2]
    figdir = argv[3] if len(argv) > 3 else "figures"
    charts = json.load(open(charts_path, encoding="utf-8"))
    index = json.load(open(os.path.join(figdir, "index.json"), encoding="utf-8"))
    snippets = {}
    for item in index:
        snippets[item["id"]] = open(os.path.join(figdir, item["file"]), encoding="utf-8").read()
    html = open(html_path, encoding="utf-8").read()
    total = 0
    for ch in sorted(charts):
        specs = charts[ch]
        pat = re.compile(r'(<article class="card node" id="ch%s" data-ch="%s">)(.*?)(</article>)'
                         % (ch, ch), re.S)
        m = pat.search(html)
        if not m:
            print("[WARN] 网页里找不到第%s章的章卡（id=ch%s）" % (ch, ch))
            continue
        block = m.group(2)
        loc = prose_inner(block)
        if not loc:
            print("[WARN] 第%s章找不到完整的 <div class=\"prose\">" % ch)
            continue
        start, end = loc
        new_inner = inject(block[start:end], specs, snippets)
        block = block[:start] + new_inner + block[end:]
        html = html[:m.start(2)] + block + html[m.end(2):]
        total += len(specs)
    open(html_path, "w", encoding="utf-8").write(html)
    print("已把 %d 张图贴进 %s" % (total, html_path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

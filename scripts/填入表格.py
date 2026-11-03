#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 charts.json 里的数据填进 md：一处数据，两个出口。

    python3 填入表格.py "[报告标题].md" "charts.json" [--quiet]

做的事：
1. 给每张表定位（优先用 anchor 锚句，其次用 after 段号），按阅读顺序编号；
2. 删掉 md 里已有的 **表N.** 表格块（可反复执行，结果一致）；
3. 按定位把 md 表格插回正文，并把 anchor / after / no 写回 charts.json。

定位为什么用锚句：后续"去 AI 味"会拆并段落，after 段号会漂；锚句记的是表前一段的
开头，只要那段还在，表就跟着它走。锚句找不到时才回退到 after。

md 里只有表格、没有图片也没有 mermaid；HTML 里同一处数据画成 SVG 图，
两边的表号与图号一致（表N ↔ 图N），列名与数值来自同一个 图表规格.py。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 图表规格 import md_table  # noqa: E402

CHAP_RE = re.compile(r"^##\s*(\d+)[\.．]\s*(.+)$")
TAB_CAP_RE = re.compile(r"^\*\*表\d+[\.．]")
ANCHOR_N = 16


def chapter_spans(lines):
    """返回 [(章号, 起, 止)]，起为 ## 标题行，止为下一 ## 之前。"""
    heads = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("## "):
            m = CHAP_RE.match(s)
            heads.append((("%02d" % int(m.group(1))) if m else None, i))
    out = []
    for k, (no, i) in enumerate(heads):
        end = heads[k + 1][1] if k + 1 < len(heads) else len(lines)
        if no:
            out.append((no, i, end))
    return out


def strip_tables(seg):
    """删掉段内的表块：表题行 + 表体 + 资料来源行。"""
    out, i = [], 0
    while i < len(seg):
        if TAB_CAP_RE.match(seg[i].strip()):
            i += 1
            while i < len(seg) and "资料来源" not in seg[i]:
                i += 1
            if i < len(seg):
                i += 1
            while i < len(seg) and not seg[i].strip():
                i += 1
            continue
        out.append(seg[i])
        i += 1
    return out


def paragraphs(seg):
    """段落下标 → 段落文本（只数非空行，与解析脚本口径一致）。"""
    return [ln.strip() for ln in seg if ln.strip()]


def resolve(spec, paras):
    """把一张表的规格落到段落下标：-1 为首图，其余为"第 k 段之后"。"""
    anchor = (spec.get("anchor") or "").strip()
    if anchor:
        for i, p in enumerate(paras):
            if p.startswith(anchor):
                return i, p[:ANCHOR_N]
    k = int(spec.get("after", -1))
    if k < 0:
        return -1, ""
    k = min(k, len(paras) - 1)
    return k, (paras[k][:ANCHOR_N] if k >= 0 else "")


def push_block(res, block):
    if not res or res[-1].strip():
        res.append("")
    res.extend(block)
    res.append("")


def insert(seg, specs):
    by_at = {}
    for sp in specs:
        by_at.setdefault(int(sp["_at"]), []).append(sp)
    res, pi = [], -1
    for sp in by_at.pop(-1, []):
        push_block(res, md_table(sp, sp["no"]))
    for ln in seg:
        res.append(ln)
        if ln.strip():
            pi += 1
            for sp in by_at.pop(pi, []):
                push_block(res, md_table(sp, sp["no"]))
    for k in sorted(by_at):
        for sp in by_at[k]:
            push_block(res, md_table(sp, sp["no"]))
    return res


def tidy(lines):
    """压缩连续空行，去掉文末多余空行。"""
    out = []
    for ln in lines:
        if not ln.strip() and out and not out[-1].strip():
            continue
        out.append(ln.rstrip())
    while out and not out[-1].strip():
        out.pop()
    return out


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    quiet = "--quiet" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    md_path, cj_path = args[0], args[1]
    lines = open(md_path, encoding="utf-8").read().split("\n")
    charts = json.load(open(cj_path, encoding="utf-8"))

    spans = chapter_spans(lines)
    order = [no for no, _, _ in spans]
    if "00" in charts:
        print("[WARN] charts.json 的键 00（摘要）不再支持，已忽略；图表请挂在正文章下")
        charts.pop("00")
    unknown = [k for k in charts if k not in order]
    if unknown:
        print("[WARN] charts.json 里的章号在 md 中不存在：%s" % ",".join(sorted(unknown)))

    # 1. 定位 + 编号（按 md 阅读顺序，章内按实际落点排序）
    n = 1
    for no, i, end in spans:
        paras = paragraphs(strip_tables(lines[i + 1:end]))
        specs = charts.get(no, [])
        for sp in specs:
            at, anc = resolve(sp, paras)
            sp["_at"], sp["anchor"] = at, anc
        specs.sort(key=lambda c: int(c["_at"]))
        for sp in specs:
            sp["no"] = n
            n += 1
        if no in charts:
            charts[no] = specs

    for no in charts:
        for sp in charts[no]:
            sp.pop("_at", None)
            if "anchor" not in sp:
                sp["anchor"] = ""
    json.dump(charts, open(cj_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 2. 逐章替换
    out, cursor = [], 0
    for no, i, end in spans:
        out.extend(lines[cursor:i + 1])
        seg = strip_tables(lines[i + 1:end])
        paras = paragraphs(seg)
        for sp in charts.get(no, []):
            sp["_at"] = next((k for k, p in enumerate(paras) if sp.get("anchor") and p.startswith(sp["anchor"])),
                             int(sp.get("after", -1)))
            sp["after"] = sp["_at"]
        out.extend(insert(seg, charts.get(no, [])))
        cursor = end
    out.extend(lines[cursor:])
    out = tidy(out)

    for no in charts:
        for sp in charts[no]:
            sp.pop("_at", None)
    json.dump(charts, open(cj_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(md_path, "w", encoding="utf-8").write("\n".join(out) + "\n")

    tot = sum(len(v) for k, v in charts.items() if k in order)
    print("md 已回填 %d 张表（表1–表%d）：%s" % (tot, tot, md_path))
    if not quiet:
        for no, _, _ in spans:
            for sp in charts.get(no, []):
                where = "章首" if sp.get("after", -1) < 0 else "第%d段后" % sp["after"]
                print("  表%-3s 第%s章 %s｜%s｜锚：%s" % (sp["no"], no, where,
                                                   sp.get("title", "")[:18], sp.get("anchor") or "—"))
    print("charts.json 已写回 no / after / anchor：%s" % cj_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图表规格的唯一数据出口：同一份 charts.json，HTML 画 SVG，md 出表格。

被 图表SVG.py（图下"数据"表）与 填入表格.py（md 正文表格）共同引用，
保证同一处数据在 HTML 与 md 里的列名、数值、顺序完全一致——md 与 HTML 不再各写一遍。

一张图在 md 里就是一张表（表N），在 HTML 里就是一张图（图N），编号一一对应。
"""


def fnum(v):
    """数值统一格式：整数不带小数点，小数最多两位且去掉尾零。"""
    if isinstance(v, str):
        return v
    try:
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return ("%.2f" % v).rstrip("0").rstrip(".")
    except TypeError:
        return str(v)


def table_rows(spec):
    """把一张图的规格摊成（表头, 行）——md 表格与 HTML 数据表共用。"""
    k = spec["kind"]
    if k == "group":
        return (["类别"] + [n for n, _ in spec["series"]],
                [[c] + [fnum(s[1][i]) for s in spec["series"]] for i, c in enumerate(spec["cats"])])
    if k == "hbar":
        return (["项目", spec.get("unit", "规模"), "方向"],
                [[n, fnum(v), {1: "加", -1: "减", 0: "持平"}[d]] for n, v, d in spec["items"]])
    if k == "share":
        return (["类别", "占比"], [[n, fnum(v)] for n, v in spec["parts"]])
    if k == "pe":
        return (["公司", "2026年PE", "2027年PE"],
                [[n, fnum(a), fnum(b)] for n, a, b in spec["items"]])
    if k == "diverging":
        return (["公司", spec.get("unit", "上修"), "基金方向"],
                [[n, "%+.1f" % v, act] for n, v, act in spec["items"]])
    if k == "marker":
        return (["项目", "数值", ""],
                [[spec.get("lbase", "指标A"), fnum(spec["base"]) + "%", ""],
                 [spec.get("lref", "指标B"), fnum(spec["ref"]) + "%", ""],
                 ["利差", str(spec["gap"]), "bp"]])
    return (["项目", spec.get("unit", "数值")], [[n, fnum(v)] for n, v in spec["items"]])


def cell(x):
    """md 表格单元格转义：竖线会切断列。"""
    return str(x).replace("|", "\\|").strip()


def md_table(spec, no=None):
    """生成 md 表格行（含表题、表体、资料来源），返回字符串列表。"""
    hdr, rows = table_rows(spec)
    label = ("表%d." % no) if no else ""
    out = ["**%s%s**" % (label, spec.get("title", "")), ""]
    out.append("| " + " | ".join(cell(h) for h in hdr) + " |")
    out.append("| " + " | ".join("---" for _ in hdr) + " |")
    for r in rows:
        out.append("| " + " | ".join(cell(c) for c in r) + " |")
    out.append("")
    tail = "资料来源：%s。" % spec.get("src", "本报告整理").rstrip("。")
    if spec.get("unit"):
        tail += "单位：%s。" % spec["unit"]
    out.append(tail)
    return out

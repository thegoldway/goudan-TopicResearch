#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 charts.json 渲染成一张张独立的 <figure> 片段（狗不扯蛋专题研究 HTML 版）。

用法：
    python3 图表SVG.py charts.json [figures目录]

只出图，不碰页面。每张图写成一个 figures/fig-<id>.html，另写 figures/index.json
记录 id 与文件名的对应关系；网页由 Step 7 手写，Step 8 用 贴图.py 把这些片段
按 charts.json 的 after 段号插进对应章卡，因此不会覆盖区块划分与章序。

图表以内联 SVG 绘制，每张图只保留"数据"表，不带复制功能。
"""
import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 图表规格 import fnum, table_rows  # noqa: E402

# ---------------------------------------------------------------- 配色（麦肯锡系）
NAVY, B2, B3, B4 = "#002960", "#003877", "#00478E", "#0056A5"
CYAN, SLATE, MUTE = "#00A9F4", "#6B7A89", "#AFC1D6"
LINE, PALE, DARK, INK, WHITE = "#DDE1E6", "#E6EFF8", "#15324F", "#1F2E3A", "#FFFFFF"

DISCLAIMER = ("本页数据与内容均由 AI 平台生成，可能存在偏差或错漏，仅供研究参考；"
              "读者须自行辨认信息真伪并独立判断，本页不构成任何投资建议。")

FONT = ('"PingFang SC","Hiragino Sans GB","Microsoft YaHei",'
        '"Source Han Sans SC","Noto Sans CJK SC",system-ui,sans-serif')


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def txt(x, y, s, size=10, fill=SLATE, anchor="middle", weight="400", extra=""):
    return ('<text x="%.1f" y="%.1f" font-size="%s" fill="%s" text-anchor="%s" '
            'font-weight="%s"%s>%s</text>' % (x, y, size, fill, anchor, weight, extra, esc(s)))


def rect(x, y, w, h, fill, rx=0):
    """允许负的宽高：向上/向左画时自动换算成左上角坐标（柱状图依赖这一点）。"""
    if w < 0:
        x, w = x + w, -w
    if h < 0:
        y, h = y + h, -h
    return ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" rx="%s"/>'
            % (x, y, w, h, fill, rx))


def line(x1, y1, x2, y2, stroke=LINE, w=1, dash=""):
    d = ' stroke-dasharray="%s"' % dash if dash else ""
    return ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%s"%s/>'
            % (x1, y1, x2, y2, stroke, w, d))


def svg(w, h, inner):
    return ('<svg viewBox="0 0 %d %d" width="%d" height="%d" role="img" '
            'preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">%s</svg>'
            % (w, h, w, h, inner))


def legend(items, x, y, size=10):
    out, cx = [], x
    for name, col in items:
        out.append(rect(cx, y - 8, 10, 10, col, 1))
        out.append(txt(cx + 15, y, name, size=size, fill=SLATE, anchor="start"))
        cx += 26 + len(name) * size * 1.05
    return "".join(out)


def nice_axis(hi):
    raw = max(hi, 1e-6) / 4.0
    mag = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 0.1
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * mag * 4 >= hi:
            return m * mag * 4, m * mag
    return hi, hi / 4.0


# ---------------------------------------------------------------- 图型
def nice_step(span, target=6):
    """按目标刻度数选一个 1/2/5×10^k 的步长，避免大数值图画出上百条网格线。"""
    raw = span / float(target)
    if raw <= 0:
        return 1
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def c_group(spec, w=880, h=420):
    cats, series = spec["cats"], spec["series"]
    pl, pr, pt, pb = 58, 22, 46, 44
    pw, ph = w - pl - pr, h - pt - pb
    vals = [v for _, vs in series for v in vs]
    hi, lo = max(vals + [0]), min(vals + [0])
    span, neg = (hi - lo) or 1, lo < 0
    y0, unit = pt + ph * (hi / span), ph / span
    out = []
    step = nice_step(span)
    tick = math.floor(lo / step) * step
    while tick <= hi:
        yy = y0 - tick * unit
        out.append(line(pl, yy, pl + pw, yy, LINE))
        lab = ("%+g" % tick) if neg else ("%g" % tick)
        out.append(txt(pl - 10, yy + 4, lab if tick else "0", size=11, fill=SLATE, anchor="end"))
        tick += step
    out.append(txt(pl - 10, pt - 14, spec.get("unit", ""), size=10, fill=SLATE, anchor="end"))
    out.append(legend([(n, NAVY if i == 0 else B4) for i, (n, _) in enumerate(series)], pl, 22))
    gw = pw / len(cats)
    bw = min(gw * 0.26, 30)
    gap = 8
    for i, cat in enumerate(cats):
        cx = pl + gw * (i + 0.5)
        n = len(series)
        for j, (_, vs) in enumerate(series):
            x = cx - (n * bw + (n - 1) * gap) / 2 + j * (bw + gap)
            v = vs[i]
            out.append(rect(x, y0, bw, -v * unit, NAVY if j == 0 else B4, 0))
            if v:
                y_end = y0 - v * unit
                if v > 0:
                    ly, fill = y_end - 6, (NAVY if j == 0 else B4)
                elif y_end > h - pb - 26:
                    ly, fill = y_end - 8, WHITE
                else:
                    ly, fill = y_end + 13, (NAVY if j == 0 else B4)
                out.append(txt(x + bw / 2, ly, fnum(v),
                               size=9.5, fill=fill, weight="600"))
        out.append(txt(cx, h - 22, cat, size=11, fill=DARK))
    out.append(line(pl, y0, pl + pw, y0, DARK, 1.2))
    return svg(w, h, "".join(out))


def c_bars(spec, w=880, h=420):
    items = spec["items"]
    pl, pr, pt, pb = 48, 20, 34, 46
    pw, ph = w - pl - pr, h - pt - pb
    top, step = nice_axis(max(v for _, v in items))
    gw = pw / len(items)
    bw = min(gw * 0.44, 60)
    out = []
    tick = step
    while tick <= top + 1e-9:
        yy = pt + ph - ph * tick / top
        out.append(line(pl, yy, pl + pw, yy, LINE))
        out.append(txt(pl - 10, yy + 4, fnum(tick), size=11, fill=SLATE, anchor="end"))
        tick += step
    out.append(txt(pl, 18, spec.get("unit", ""), size=10, fill=SLATE, anchor="start"))
    for i, (name, v) in enumerate(items):
        cx = pl + gw * (i + 0.5)
        col = NAVY if (spec.get("flag") != 1 or i < 2) else MUTE
        out.append(rect(cx - bw / 2, pt + ph, bw, -ph * v / top, col, 1))
        out.append(txt(cx, pt + ph - ph * v / top - 8, fnum(v), size=13, fill=NAVY, weight="600"))
        out.append(txt(cx, pt + ph + 20, name, size=11.5, fill=SLATE))
    return svg(w, h, "".join(out))


def c_lolli(spec, w=880, h=420):
    items = spec["items"]
    pl, pr, pt = 110, 56, 24
    pw = w - pl - pr
    rowh = (h - pt - 12) / len(items)
    out = []
    for i, (name, v) in enumerate(items):
        yy = pt + rowh * i + rowh / 2
        out.append(line(pl, yy, pl + pw, yy, "#E8EBEF", 3))
        out.append(line(pl, yy, pl + pw * v / 100.0, yy, NAVY, 3))
        out.append('<circle cx="%.1f" cy="%.1f" r="6" fill="%s"/>' % (pl + pw * v / 100.0, yy, NAVY))
        out.append(txt(pl - 14, yy + 5, name, size=12, fill=DARK, anchor="end"))
        out.append(txt(pl + pw + 12, yy + 5, "%s%%" % fnum(v), size=12, fill=NAVY, anchor="start", weight="600"))
    out.append(txt(pl - 14, 12, spec.get("unit", ""), size=10, fill=SLATE, anchor="end"))
    return svg(w, h, "".join(out))


def c_share(spec, w=880, h=420):
    parts = spec["parts"]
    tot = sum(v for _, v in parts) or 1
    bh, y, x = 54, 120, 40
    W = w - x * 2
    out, cx = [], x
    cols = [NAVY, CYAN, MUTE, B4]
    for i, (name, v) in enumerate(parts):
        seg = W * v / tot
        out.append(rect(cx, y, seg, bh, cols[i % len(cols)], 1))
        if seg > 180:
            out.append(txt(cx + seg / 2, y + bh / 2 + 6, "%s %s%%" % (name, fnum(v)),
                           size=15, fill=WHITE, weight="600"))
        else:
            out.append(txt(cx + seg / 2, y + bh + 22, "%s %s%%" % (name, fnum(v)),
                           size=11, fill=DARK, weight="600"))
        cx += seg
    out.append(txt(x, 40, spec.get("unit", ""), size=12, fill=SLATE, anchor="start"))
    out.append(txt(x, y + bh + 46, spec.get("note", "占比为结构分布，非时间序列"),
                   size=11, fill=SLATE, anchor="start"))
    return svg(w, 230, "".join(out))


def c_hbar(spec, w=880, h=420):
    items = spec["items"]
    pl, pr, pt, pb = 150, 40, 20, 12
    pw, ph = w - pl - pr, h - pt - pb
    hi = max(v for _, v, _ in items) or 1
    unit = pw / (hi * 1.02)
    rowh = ph / len(items)
    out = []
    for i, (name, v, d) in enumerate(items):
        yy = pt + rowh * i + rowh * 0.24
        bh = rowh * 0.48
        col = NAVY if d > 0 else (B4 if d < 0 else MUTE)
        out.append(rect(pl, yy, v * unit, bh, col, 1))
        mark = "↑" if d > 0 else ("↓" if d < 0 else "→")
        out.append(txt(pl - 12, yy + bh * 0.80, name, size=12, fill=DARK, anchor="end"))
        out.append(txt(pl + v * unit + 14, yy + bh * 0.80, "%s %s" % (fnum(v), mark),
                       size=12, fill=col, anchor="start", weight="600"))
    out.append(txt(pl, 12, spec.get("unit", ""), size=10, fill=SLATE, anchor="start"))
    if spec.get("note", True):
        out.append(txt(w - pr, h - 2, spec.get("note", "箭头为边际方向"),
                       size=9, fill=SLATE, anchor="end"))
    return svg(w, h, "".join(out))


def c_compare(spec, w=880, h=420):
    items = spec["items"]
    pl, pr = 150, 70
    pw = w - pl - pr
    hi = max(v for _, v in items) or 1
    rowh = (h - 12) / len(items)
    out = []
    for i, (name, v) in enumerate(items):
        yy = 6 + rowh * i + rowh * 0.2
        bh = rowh * 0.5
        out.append(rect(pl, yy, pw * v / hi, bh, NAVY if i == 0 else B4, 1))
        out.append(txt(pl + pw * v / hi + 12, yy + bh * 0.8,
                       "%s%s" % (fnum(v), spec.get("suffix", "")), size=13, fill=DARK,
                       anchor="start", weight="600"))
        out.append(txt(pl - 12, yy + bh * 0.8, name, size=12, fill=DARK, anchor="end"))
    if spec.get("head"):
        out.append(txt(pl, 14, spec["head"], size=10, fill=SLATE, anchor="start"))
    if spec.get("note"):
        out.append(txt(pl + pw, h - 6, spec["note"], size=11, fill=B3, anchor="end", weight="600"))
    return svg(w, h, "".join(out))


def c_pe(spec, w=880, h=420):
    items = spec["items"]
    pl, pr, pt, pb = 46, 20, 40, 44
    pw, ph = w - pl - pr, h - pt - pb
    hi, step = nice_axis(max(max(a, b) for _, a, b in items))
    gw = pw / len(items)
    bw = min(gw * 0.26, 40)
    out = []
    tick = step
    while tick <= hi + 1e-9:
        yy = pt + ph - ph * tick / hi
        out.append(line(pl, yy, pl + pw, yy, LINE))
        out.append(txt(pl - 10, yy + 4, fnum(tick), size=11, fill=SLATE, anchor="end"))
        tick += step
    out.append(legend([("2026年PE", NAVY), ("2027年PE", B4)], pl, 26))
    for i, (name, a, b) in enumerate(items):
        cx = pl + gw * (i + 0.5)
        for j, v in enumerate((a, b)):
            x = cx - bw - 3 + j * (bw + 6)
            out.append(rect(x, pt + ph, bw, -ph * v / hi, NAVY if j == 0 else B4, 0))
            out.append(txt(x + bw / 2, pt + ph - ph * v / hi - 7, fnum(v), size=11,
                           fill=NAVY if j == 0 else B4, weight="600"))
        out.append(txt(cx, h - 18, name, size=11.5, fill=DARK))
    out.append(line(pl, pt + ph, pl + pw, pt + ph, DARK, 1.2))
    return svg(w, h, "".join(out))


def c_diverging(spec, w=880, h=420):
    items = spec["items"]
    pl, pr, pt = 96, 92, 22
    pw = w - pl - pr
    hi = max(abs(v) for _, v, _ in items) or 1
    zero = pl + pw / 2.0
    unit = pw / (hi * 2.0)
    rowh = (h - pt - 14) / len(items)
    out = []
    for i, (name, v, act) in enumerate(items):
        yy = pt + rowh * i + rowh * 0.2
        bh = rowh * 0.5
        if v >= 0:
            out.append(rect(zero, yy, v * unit, bh, NAVY, 1))
            out.append(txt(zero + v * unit + 8, yy + bh * 0.8, "%+.1f" % v, size=11,
                           fill=NAVY, anchor="start", weight="600"))
        else:
            out.append(rect(zero + v * unit, yy, -v * unit, bh, B4, 1))
            out.append(txt(zero + v * unit - 8, yy + bh * 0.8, "%+.1f" % v, size=11,
                           fill=B4, anchor="end", weight="600"))
        out.append(txt(pl - 12, yy + bh * 0.8, name, size=12, fill=DARK, anchor="end"))
        tag = "基金加仓" if act == "加" else "基金减仓"
        tx, tw = w - 88, 56
        out.append(rect(tx, yy + bh * 0.1, tw, bh * 0.8, PALE if act == "加" else "#F0F1F2", 1))
        out.append(txt(tx + tw / 2, yy + bh * 0.8, tag, size=10,
                       fill=B3 if act == "加" else SLATE, weight="600"))
    out.append(line(zero, pt - 6, zero, h - 10, DARK, 1.2))
    out.append(txt(pl, 12, spec.get("unit", ""), size=10, fill=SLATE, anchor="start"))
    return svg(w, h, "".join(out))


def c_marker(spec, w=880, h=420):
    base, ref, gap = spec["base"], spec["ref"], spec["gap"]
    lbase, lref = spec.get("lbase", "指标A"), spec.get("lref", "指标B")
    note = spec.get("note", "")
    pl, pr = 40, 40
    pw = w - pl - pr
    hi = max(5.5, base * 1.12)
    unit = pw / hi
    Y = h * 0.48
    out = [rect(pl, Y, base * unit, h * 0.16, NAVY, 1),
           txt(pl + base * unit + 14, Y + h * 0.12, "%s %s%%" % (lbase, fnum(base)),
               size=14, fill=NAVY, anchor="start", weight="600"),
           line(pl + ref * unit, Y - 46, pl + ref * unit, Y + h * 0.16 + 46, B3, 1.4, "5 4"),
           txt(pl + ref * unit, Y - 56, "%s %s%%" % (lref, fnum(ref)), size=12, fill=B3, weight="600"),
           line(pl, Y + h * 0.16 + 34, pl + base * unit, Y + h * 0.16 + 34, B4, 1.2),
           txt(pl + base * unit / 2, Y + h * 0.16 + 56, "利差 %s 个基点" % gap,
               size=13, fill=B4, weight="600")]
    if note:
        out.append(txt(pl, h - 6, note, size=10, fill=SLATE, anchor="start"))
    return svg(w, 300, "".join(out))


CHARTS = {"group": c_group, "bars": c_bars, "lolli": c_lolli, "share": c_share,
          "hbar": c_hbar, "compare": c_compare, "pe": c_pe,
          "diverging": c_diverging, "marker": c_marker}


def figure_html(no, spec):
    kind = spec.get("kind", "bars")
    fn = CHARTS.get(kind)
    if not fn:
        raise SystemExit("charts.json 里 %s 的 kind=%s 不支持" % (spec.get("id"), kind))
    hdr, rows = table_rows(spec)
    thead = "".join("<th>%s</th>" % esc(x) for x in hdr)
    tbody = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % esc(c) for c in r) for r in rows)
    return ('<figure class="fig"><div class="fig-head">'
            '<span class="fig-no">图%s</span><span class="fig-title">%s</span>'
            '<span class="fig-tools"><button type="button" class="tbtn" data-act="table" '
            'aria-pressed="false">数据</button></span></div>'
            '<div class="fig-canvas">%s</div>'
            '<div class="fig-table" hidden><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
            '<figcaption>资料来源：%s。单位：%s</figcaption></figure>'
            % (no, esc(spec.get("title", "")), fn(spec), thead, tbody,
               esc(spec.get("src", "本报告整理")), esc(spec.get("unit", "—"))))


# ---------------------------------------------------------------- 命令行：只出图
def main(argv):
    if len(argv) < 2:
        print("用法：python3 图表SVG.py charts.json [figures目录]")
        return 2
    charts_path = argv[1]
    outdir = argv[2] if len(argv) > 2 else "figures"
    charts = json.load(open(charts_path, encoding="utf-8"))
    os.makedirs(outdir, exist_ok=True)
    index, n = [], 0
    for ch in sorted(charts):
        for spec in charts[ch]:
            if "no" not in spec:
                raise SystemExit("charts.json 里 %s 缺 no 字段：先跑 填入表格.py" % spec.get("id"))
            html = figure_html(spec["no"], spec)
            fn = "fig-%s.html" % spec["id"]
            open(os.path.join(outdir, fn), "w", encoding="utf-8").write(html)
            index.append({"id": spec["id"], "file": fn, "no": spec["no"], "ch": ch})
            n += 1
    json.dump(index, open(os.path.join(outdir, "index.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("已生成 %d 张图到 %s（index.json 记录 id 与文件名）" % (n, outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

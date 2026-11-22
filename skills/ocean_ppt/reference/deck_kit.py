# -*- coding: utf-8 -*-
"""ocean_ppt 复用骨架：配色 + 布局 helper 全集 + 写盘函数。

用法：复制到 tools/build_*.py，逐页 slides.append((eid, elements))，
最后 write_deck(OUT, slides, title)。代码块自动缩字号防溢出（fit_px）。
"""
import json, os, shutil

W, H = 960, 540
M = 64
CW = W - 2 * M
TOTAL = 0  # 页数，写完页后改

# ── 配色 ──────────────────────────────────────────────
INK = '#10263D'
BODY = '#44586F'
MUTED = '#7A8A9E'
DIM = '#9AACBF'
LINE = '#E6EDF5'
CARD = '#FFFFFF'
CARDB = '#D8E1EC'
CODEBG = '#E9F7F0D9'
CODEBD = '#CFE8DB'
CODEBAR = '#8FD0AE'
CTX = '#23405A'   # 代码普通行
CKW = '#17754E'   # 代码关键行（登记/查表/new 等）
CCM = '#8296AA'   # 代码注释行
BLUE = '#2F6FD0'
TEAL = '#2E8CA6'
GREEN = '#2F8F62'
BLUEBG = '#EDF4FD'
TEALBG = '#EDF7FA'
GREENBG = '#EEF9F3'
GREENBD = '#B6E3C9'
BAR = {BLUE: '#AFC9EC', TEAL: '#ACD8E3', GREEN: '#AEDFC5'}
WARNBG = '#FFFBF0'
WARNBD = '#EEDFBA'
WARNTX = '#86601F'
D_BG = '#08101E'
D_TX = '#E8F1FA'
D_MUTED = '#8AA4BE'
D_CYAN = '#22D3EE'
PAGE_BG = '#ECEFF4'


def fs(size):
    """全局字号放大：deck 在 960x540 下默认偏小。"""
    return round(float(size) * 1.26, 1)


def p(txt, size, color, weight=None, ls=None, mt=None, lh=None, raw=False):
    eff = fs(size) if raw else round(fs(size) * 1.08, 1)
    css = [f'font-size:{eff}px', f'color:{color}']
    if weight:
        css.append(f'font-weight:{weight}')
    if ls is not None:
        css.append(f'letter-spacing:{ls}px')
    if lh is not None:
        css.append(f'line-height:{lh}')
    style = f' style="margin-top:{mt}px; line-height:{lh if lh else 1.2}"'
    return f'<p{style}><span style="{";".join(css)}">{txt}</span></p>'


def text(eid, bounds, html, align=('left', 'top')):
    return {"elementId": eid, "elementType": "text", "bounds": [int(v) for v in bounds],
            "content": {"text": html, "align": list(align)}}


def shape(eid, bounds, fill=None, border=None, name='rect'):
    el = {"elementId": eid, "elementType": "shape", "shapeName": name,
          "bounds": [int(v) for v in bounds]}
    if fill:
        el["fill"] = {"type": "solid", "color": fill}
    if border:
        el["border"] = {"style": "solid", "color": border[0], "width": border[1]}
    return el


def rule(eid, bounds, color=LINE, width=1, arrow=False):
    el = {"elementId": eid, "elementType": "line", "bounds": [int(v) for v in bounds],
          "border": {"style": "solid", "color": color, "width": width}}
    if arrow:
        el["arrow"] = ["none", "arrow"]
    return el


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def code(eid, bounds, lines, size=10, lh=1.30, px=None):
    font_px = px if px else fs(size) * 1.20
    parts = []
    for txt, color in lines:
        parts.append(f'<p style="line-height:{lh}"><span style="font-size:{font_px:.1f}px;color:{color}">{esc(txt)}</span></p>')
    return text(eid, bounds, ''.join(parts))


def _char_em(ch):
    return 1.0 if ord(ch) > 127 else 0.56


def wrapped_lines(lines, width, font_px):
    total = 0
    for txt, _ in lines:
        if not txt.strip():
            total += 1
            continue
        w = sum(_char_em(c) for c in txt) * font_px
        total += max(1, int(w / max(1.0, width)) + (1 if w % width else 0))
    return total


def fit_px(lines, width, height, font_px, lh=1.30):
    """按 行数 × 字号 × lh × 1.06 迭代缩字号（×0.94）直到装下，防溢出。"""
    size = font_px
    for _ in range(8):
        n = wrapped_lines(lines, width - 6, size)
        if n * size * lh * 1.06 <= height:
            return size
        size *= 0.94
    return size


def codebox(eid, bounds, lines, size=10, label=None, page=None):
    """代码块：浅绿底 + 深色文件名头 + 原书页码 + fit_px 自动缩字号。
    lines = [(文本, 颜色), ...]；label=文件名/清单号；page=『UVM 实战 Pxxx』。
    """
    x, y, w, h = bounds
    name = label
    if h < 104:
        name = None
    top = y + 12
    els = [shape(f'{eid}-bg', (x, y, w, h), '#E6F7EF', ('#C4E2D3', 1), name='roundRect')]
    els[0]['adjustments'] = [5000]
    els[0]['shadow'] = 0.8
    if name:
        hdr = 22
        els.append(shape(f'{eid}-hdr', (x, y, w, hdr), '#4B6C86', ('#3E5C74', 1), name='roundRect'))
        els[-1]['adjustments'] = [5000]
        els.append(text(f'{eid}-file', (x + 16, y + 6, w - 120, 13), p(name, 8.0, '#D8E7F4', '700', 0.3)))
        if page:
            els.append(text(f'{eid}-page', (x + w - 112, y + 6, 96, 13), p(page, 7.2, '#9FC0D8', '700'), align=('right', 'top')))
        top = y + hdr + 10
    avail = h - (top - y) - 10
    base = fs(size) * 1.20 * (0.94 if name else 1.0)
    fitted = fit_px(lines, w - 36, avail, base)
    used = wrapped_lines(lines, w - 42, fitted) * fitted * 1.30 * 1.06
    new_h = min(h, int(used + 24)) if not name else min(h, int((top - y) + used + 42))
    els[0]['bounds'][3] = new_h
    els.append(code(eid, (x + 18, top, w - 32, new_h - (top - y) - 8), lines, px=fitted))
    return els


def header(tag, title, color=BLUE):
    w = min(320, 34 + sum(12.8 if ord(ch) > 127 else 7.4 for ch in tag))
    tint = {BLUE: BLUEBG, TEAL: TEALBG, GREEN: GREENBG}.get(color, BLUEBG)
    tb = {BLUE: '#C3D6EE', TEAL: '#BFDDE6', GREEN: '#C3E0CF'}.get(color, '#C3D6EE')
    return [
        rule('top-bar', (0, 2, W, 2), '#D9E6F4'),
        shape('tag-bg', (M, 36, w, 22), tint, (tb, 1)),
        shape('tag-dot', (M + 9, 43, 3, 9), color),
        text('tag', (M + 18, 40, w - 22, 16), p(tag, 9.5, color, '700', 1.2)),
        text('title', (M, 62, CW, 44), p(title, 27, INK, '700', raw=True)),
        rule('accent-rule', (M, 120, 44, 3), color),
        rule('head-rule', (M + 52, 121, CW - 52, 1), LINE),
    ]


def footer(num, label='技术分享 · 组内分享'):
    return [
        rule('foot-rule', (M, 500, CW, 1), LINE),
        text('foot-l', (M, 507, 460, 14), p(label, 8.5, DIM, ls=1)),
        text('foot-r', (W - M - 120, 507, 120, 14), p(f'{num:02d} / {TOTAL}', 8.5, DIM), align=('right', 'top')),
    ]


def card(eid, x, y, w, h, fill=CARD, border=CARDB):
    return [shape(f'{eid}-bg', (x, y, w, h), fill, (border, 1))]


def callout(eid, x, y, w, h, txt, color=GREEN, size=11):
    bg = shape(f'{eid}-bg', (x, y, w, h), '#E6F7EF', ('#C4E2D3', 1), name='roundRect')
    bg['shadow'] = 0.7
    return [bg, text(f'{eid}-t', (x + 22, y + 12, w - 44, h - 20), p(txt, size, '#1B5E43', '700', lh=1.5))]


def bullets(eid, bounds, items, size=10.5, gap=6, color=BODY):
    return [text(eid, bounds, ''.join(p(t, size, color, mt=gap if i else 0, lh=1.45) for i, t in enumerate(items)))]


def purpose(txt, color=BLUE):
    """顶部「本页讲：…」要点条——讲清这一页要传达什么。"""
    tint = {BLUE: BLUEBG, TEAL: TEALBG, GREEN: GREENBG}.get(color, BLUEBG)
    bd = {BLUE: '#C3D6EE', TEAL: '#BFDDE6', GREEN: '#C3E0CF'}.get(color, '#C3D6EE')
    bg = shape('purpose-bg', (M, 128, CW, 30), tint, (bd, 1), name='roundRect')
    bg['adjustments'] = [5000]
    return [bg,
            shape('purpose-dot', (M + 16, 139, 3, 10), color),
            text('purpose-t', (M + 28, 134, CW - 44, 18), p('本页讲：' + txt, 9.8, color, '700', lh=1.3))]


def insight(txt):
    """底部「一句话」小结条。"""
    return [
        rule('ins-rule', (M, 448, CW, 1), LINE),
        text('ins-l', (M, 458, 40, 16), p('一句话', 8.5, GREEN, '700')),
        text('ins-t', (M + 44, 456, CW - 44, 30), p(txt, 9.2, BODY, lh=1.4)),
    ]


# ── 写盘 ──────────────────────────────────────────────
def write_deck(OUT, slides, title='技术分享', page_bg=PAGE_BG):
    PAGES = os.path.join(OUT, 'pages')
    if os.path.isdir(PAGES):
        shutil.rmtree(PAGES)
    os.makedirs(PAGES, exist_ok=True)
    manifest = {
        "version": "v2",
        "title": title,
        "size": [W, H],
        "theme": {"colors": {"bg": page_bg, "paper": CARD, "primary": BLUE, "accent": TEAL,
                              "text": INK, "muted": MUTED, "line": LINE}},
        "pages": [f'pages/{n}.page' for n, _ in slides],
    }
    with open(os.path.join(OUT, 'deck.pptd'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    for idx, (name, elements) in enumerate(slides, start=1):
        page = {"pageType": "content", "background": {"color": page_bg}, "elements": list(elements)}
        if idx > 1:
            page["elements"] += footer(idx)
        with open(os.path.join(PAGES, f'{name}.page'), 'w', encoding='utf-8') as fh:
            json.dump(page, fh, ensure_ascii=False, indent=2)
    print('pages:', len(slides))

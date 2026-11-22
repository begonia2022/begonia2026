# -*- coding: utf-8 -*-
"""Build the 25-page UVM factory/callback share deck (tech-blue cover, structured white body)."""
import json, os, shutil

OUT = r'E:\uvm_ppt\uvm-share\deck'
PAGES = os.path.join(OUT, 'pages')
W, H = 960, 540
M = 64
CW = W - 2 * M
TOTAL = 28

# palette — muted, paper-like; green is the only "highlight" colour
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
CTX = '#23405A'
CKW = '#17754E'
CCM = '#8296AA'
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


def fs(size):
    """Global type scale: the deck reads too small at 960x540 otherwise."""
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
    """Shrink the code font until the block fits its box (pitch ≈ size * lh * 1.3)."""
    size = font_px
    for _ in range(8):
        n = wrapped_lines(lines, width - 6, size)
        if n * size * lh * 1.06 <= height:
            return size
        size *= 0.94
    return size


FILE_LABELS = {
    'c1-c': 'src/ch8/section8.1/8.1.1/my_case0.sv',
    'd1-c': 'src/ch8/section8.1/8.1.2/my_transaction.sv',
    'd2-c': 'src/ch8/section8.1/8.1.2/my_case0.sv',
    'd3-c': 'src/ch8/section8.1/8.1.2/my_case0.sv',
    'e1-c': 'src/ch8/section8.2/8.2.1/my_case0.sv',
    'g1-c': 'src/ch8/section8.2/8.2.3/consecutive/my_case0.sv',
    'g2-c': 'src/ch8/section8.2/8.2.3/replace/my_case0.sv',
    'i-c': 'src/ch8/section8.3/8.3.1/my_case0.sv',
    'j1': 'src/ch8/section8.3/8.3.2/my_case0.sv',
    'j2': 'src/ch8/section8.3/8.3.2/my_case0.sv',
    'k-c': 'src/ch8/section8.3/8.3.3/my_case0.sv',
    'l2': 'src/ch8/section8.4/8.4.2/my_driver.sv',
    'm1-c': 'src/ch9/section9.1/9.1.1/my_transaction.sv',
    'r-c': 'src/ch9/section9.1/9.1.5/my_driver.sv',
    's1': 'src/ch9/section9.1/9.1.6/callbacks.sv',
    's2': 'src/ch9/section9.1/9.1.6/my_driver.sv',
    't2-c': 'src/ch9/section9.2/9.2.2/A_driver.sv',
    'u1': 'uvm_sequence.svh  ·  UVM 源码',
    'u2': 'src/ch9/section9.3/9.3.2/bus_if.sv',
}


BOOK_PAGES = {
    'c1-c': 'P598', 'd1-c': 'P602', 'd2-c': 'P604', 'd3-c': 'P606',
    'e1-c': 'P607', 'g1-c': 'P623', 'g2-c': 'P625',
    'i-c': 'P635', 'j1': 'P636', 'j2': 'P637', 'k-c': 'P639',
    'l2': 'P647', 'm1-c': 'P656', 'r-c': 'P668',
    's1': 'P670', 's2': 'P671', 't2-c': 'P676', 'u1': 'P683', 'u2': 'P685',
}


def codebox(eid, bounds, lines, size=10, label=None, page=None):
    x, y, w, h = bounds
    name = FILE_LABELS.get(eid) if label is None else label
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
        els.append(text(f'{eid}-file', (x + 16, y + 6, w - 120, 13),
                        p(name, 8.0, '#D8E7F4', '700', 0.3)))
        pg = BOOK_PAGES.get(eid) if page is None else page
        if pg:
            els.append(text(f'{eid}-page', (x + w - 112, y + 6, 96, 13),
                            p(f'UVM 实战 {pg}', 7.2, '#9FC0D8', '700'), align=('right', 'top')))
        top = y + hdr + 10
    avail = h - (top - y) - 10
    base = fs(size) * 1.20 * (0.94 if name else 1.0)
    fitted = fit_px(lines, w - 36, avail, base)
    used = wrapped_lines(lines, w - 42, fitted) * fitted * 1.30 * 1.06
    shrink = max(0, int((hdr_used := (top - y)) + used + 42))
    if not name:
        shrink = int(used + 24)
    new_h = min(h, shrink)
    els[0]['bounds'][3] = new_h
    els.append(code(eid, (x + 18, top, w - 32, new_h - (top - y) - 8), lines, px=fitted))
    return els


def header(tag, title, color=BLUE):
    w = min(320, 34 + sum(12.8 if ord(ch) > 127 else 7.4 for ch in tag))
    tint = {BLUE: BLUEBG, TEAL: TEALBG, GREEN: GREENBG}.get(color, BLUEBG)
    tint_border = {BLUE: '#C3D6EE', TEAL: '#BFDDE6', GREEN: '#C3E0CF'}.get(color, '#C3D6EE')
    return [
        rule('top-bar', (0, 2, W, 2), '#D9E6F4'),
        shape('tag-bg', (M, 36, w, 22), tint, (tint_border, 1)),
        shape('tag-dot', (M + 9, 43, 3, 9), color),
        text('tag', (M + 18, 40, w - 22, 16), p(tag, 9.5, color, '700', 1.2)),
        text('title', (M, 62, CW, 44), p(title, 27, INK, '700', raw=True)),
        rule('accent-rule', (M, 120, 44, 3), color),
        rule('head-rule', (M + 52, 121, CW - 52, 1), LINE),
    ]


def footer(num, label='UVM 实战 · 第 8 / 9 章 · 组内分享'):
    return [
        rule('foot-rule', (M, 500, CW, 1), LINE),
        text('foot-l', (M, 507, 460, 14), p(label, 8.5, DIM, ls=1)),
        text('foot-r', (W - M - 120, 507, 120, 14), p(f'{num:02d} / {TOTAL}', 8.5, DIM), align=('right', 'top')),
    ]


def card(eid, x, y, w, h, accent=BLUE, fill=CARD, border=CARDB):
    return [shape(f'{eid}-bg', (x, y, w, h), fill, (border, 1))]


def callout(eid, x, y, w, h, txt, color=GREEN, size=11):
    bg = shape(f'{eid}-bg', (x, y, w, h), '#E6F7EF', ('#C4E2D3', 1), name='roundRect')
    bg['shadow'] = 0.7
    return [bg,
            text(f'{eid}-t', (x + 22, y + 12, w - 44, h - 20), p(txt, size, '#1B5E43', '700', lh=1.5))]


def bullets(eid, bounds, items, size=10.5, gap=6, color=BODY):
    return [text(eid, bounds, ''.join(
        p(t, size, color, mt=gap if i else 0, lh=1.45) for i, t in enumerate(items)))]


def rows3(items, y0, row_h, xs, fills=None, size=9.5):
    out = []
    for i, (c1, c2) in enumerate(items):
        y = y0 + i * row_h
        out.append(shape(f'r{i}-bg', (M, y, CW, row_h - 8), '#F7FAFE', ('#E1EBF7', 1)))
        out.append(text(f'r{i}-c1', (xs[0], y + 9, 190, 18), p(c1, size, INK, '700')))
        out.append(text(f'r{i}-c2', (xs[1], y + 9, 250, 18), p(c2, size, BLUE, '700')))
        out.append(text(f'r{i}-c3', (xs[2], y + 9, 330, 18), p('', size, MUTED)))
    return out


def insight(txt):
    return [
        rule('ins-rule', (M, 448, CW, 1), LINE),
        text('ins-l', (M, 458, 40, 16), p('一句话', 8.5, GREEN, '700')),
        text('ins-t', (M + 44, 456, CW - 44, 30), p(txt, 9.2, BODY, lh=1.4)),
    ]


def purpose(txt, color=BLUE):
    tint = {BLUE: BLUEBG, TEAL: TEALBG, GREEN: GREENBG}.get(color, BLUEBG)
    bd = {BLUE: '#C3D6EE', TEAL: '#BFDDE6', GREEN: '#C3E0CF'}.get(color, '#C3D6EE')
    bg = shape('purpose-bg', (M, 128, CW, 30), tint, (bd, 1), name='roundRect')
    bg['adjustments'] = [5000]
    return [bg,
            shape('purpose-dot', (M + 16, 139, 3, 10), color),
            text('purpose-t', (M + 28, 134, CW - 44, 18), p('本页讲：' + txt, 9.8, color, '700', lh=1.3))]


INSIGHTS = {
    '03_virtual_override': '虚函数让“同一个调用”有不同实现，但前提是你手里真有那个子类对象。',
    '04_constraint_override': '约束重载只改概率与边界，改不了“到底用哪个类”。',
    '05_factory_override': 'override 只是登记一条记录，真正生效发生在 create 的那一刻。',
    '06_prereqs': '四条里最容易踩的是第二条：用 new 创建，override 永远查不到。',
    '07_apis': '类型重载管全局，实例重载管一个节点；命令行参数适合现场排查。',
    '08_semantics': 'replace 默认是 1，后注册的赢；拿不准时就当作“最后一条生效”。',
    '09_debug': '先用 print_override_info 看命中，再用 print_topology 看结果。',
    '10_tx_override': '用例只负责“换类型”，异常细节交给新的 transaction 类。',
    '11_seq_override': 'sequence 重载的价值：入口不用改，整条激励链都能复用。',
    '12_comp_override': 'driver 重载适合极端异常，不适合替代 sequence。',
    '13_impl': '三种建对象方式都绕不开 new，按字符串建类语言并不内建——这就是 factory 要补的能力。',
    '13b_reg': '先登记类名，再查表 new——这就是 factory 给 new 加的那一层。',
    '13c_api': '四个接口只是同一张表的四种查法，本质都是对 new 的重载。',
    '14_cb_general': 'post_randomize 是最朴素的回调：框架留位置，使用者填内容。',
    '15_cb_why': 'VIP 改不了，就给它留一个“可注册的插槽”。',
    '16_cb_principle': '池子把“谁被调用”从编译期解耦成了运行期注册。',
    '17_cb_usage': '六步里最容易错的是 add 的时机和路径参数。',
    '18_cb_inherit': '父类池子 + 子类实例，靠 uvm_set_super_type 一串就通了。',
    '19_three_mechanisms': '三者的边界：换类、插动作、编排流程。',
    '20_small_beautiful': '拆得越碎，重载点越小，复用成本越低。',
    '21_params': '参数化的前提是“参数有意义”，否则只是语法负担。',
    '22_env_reuse': '重用的边界在 build_phase：谁实例化，谁决定可复用的粒度。',
}


slides = []

# ── 01 cover ────────────────────────────────────────────────────────────
s = [shape('bg', (0, 0, W, H), D_BG),
     rule('bar', (34, 96, 4, 196), D_CYAN, 4)]
s += [shape('ring1', (700, -80, 320, 320), None, ('#16304C', 1), name='oval'),
      shape('ring2', (790, 70, 190, 190), None, ('#1B3A5C', 1), name='oval')]
s += [text('kicker', (M, 96, 560, 18), p('DSH  ·  组内技术分享', 10.5, D_CYAN, '700', 2.5)),
      text('chapter', (M, 122, 640, 20), p('《UVM 实战》  第 8 章 factory  ·  第 9 章 callback / 可重用性', 12, D_MUTED)),
      text('title', (M, 152, 720, 96), p('Factory 与 Callback', 54, D_TX, '700')),
      text('sub', (M, 252, 560, 26), p('从重载到回调：让验证平台可插拔、可复用', 16, '#BBD3E8'))]
for i, c in enumerate(['8 个 factory 知识点', '6 个 callback 知识点', '2 页代码对照空块']):
    x = M + i * 214
    edge = ['#60A5FA', '#22D3EE', '#34D399'][i]
    s += [shape(f'chip{i}', (x, 322, 196, 30), '#0F2236', (edge, 1)),
          text(f'chip{i}-t', (x, 329, 196, 18), p(c, 9.5, edge), align=('center', 'top'))]
s += [rule('foot', (M, 470, CW, 1), '#1E3550'),
      text('who', (M, 482, 400, 16), p('分享人：______     2026 · 11', 10, D_MUTED)),
      text('src', (W - M - 380, 482, 380, 16), p('内容依据：张强《UVM 实战》第 8、9 章', 9.5, DIM), align=('right', 'top'))]
slides.append(('01_cover', s))

# ── 02 agenda ───────────────────────────────────────────────────────────
s = header('AGENDA', '今天讲什么')
blocks = [
    ('01', '重载基础', 'SV 的虚函数重载与约束重载：factory 之前，我们是怎么做的', BLUE),
    ('02', 'Factory 重载', '四个前提、四种接口、连续/替换、调试、三类常用重载', BLUE),
    ('03', 'Factory 实现', 'registry + global_tab：按字符串建对象，本质是重载 new', BLUE),
    ('04', 'Callback 机制', '广义回调、VIP 场景、池子原理、落地六步、子类继承', TEAL),
    ('05', '可重用性与实战', '小而美、参数化类、env/寄存器重用，以及代码对照', GREEN),
]
for i, (n, t, d, c) in enumerate(blocks):
    y = 136 + i * 68
    s += [text(f'n{i}', (M, y, 52, 26), p(n, 20, c, '700')),
          text(f't{i}', (M + 56, y, 260, 22), p(t, 13.5, INK, '700')),
          text(f'd{i}', (M + 56, y + 24, 720, 20), p(d, 10, MUTED))]
slides.append(('02_agenda', s))

# ── 03 8.1.1 virtual override ──────────────────────────────────────────
s = header('08 · 8.1.1 重载基础', '先看 SystemVerilog 自己的重载：虚函数')
s += card('c1', M, 136, 404, 236, BLUE)
s += [text('c1-t', (M + 20, 148, 360, 18), p('只有 virtual 才能被重载', 10.5, BLUE, '700'))]
s += codebox('c1-c', (M + 20, 174, 364, 152), [
    ('class bird extends uvm_object;', CTX),
    ('  virtual function void hungry();  // 虚：可重载', CKW),
    ('    $display("I am a bird");', CTX),
    ('  endfunction', CTX),
    ('  function void hungry2();  // 非虚：不能重载', CTX),
    ('  endfunction', CTX),
    ('endclass', CTX),
    ('class parrot extends bird;  // 派生并重载它', CTX),
], 9)
s += card('c2', 492, 136, 404, 236, BLUE)
s += [text('c2-t', (492 + 20, 148, 360, 18), p('父类指针，子类行为', 10.5, BLUE, '700'))]
s += [text('c2-b', (492 + 20, 176, 364, 186), ''.join([
    p('print_hungry(bird b_ptr) 里调用 b_ptr.hungry()：', 9.5, BODY, lh=1.4),
    p('传 bird 实例 → "I am a bird"', 9.5, MUTED, mt=6, lh=1.4),
    p('传 parrot 实例 → "I am a parrot"（虚函数）', 9.5, MUTED, mt=2, lh=1.4),
    p('传 parrot 实例 → "I am a bird"（hungry2 非虚）', 9.5, MUTED, mt=2, lh=1.4),
    p('UVM 的 phase 就是这么调的：UVM 树上的结点类型各异，统一用 uvm_component 指针调用 build_phase。', 9.5, BODY, mt=10, lh=1.4),
]))]
s += callout('co', M, 388, CW, 52, '重载解决“同一个调用、不同实现”；但它仍要求你手里就是那个子类对象。')
slides.append(('03_virtual_override', s))

# ── 04 8.1.2 constraint override ───────────────────────────────────────
s = header('08 · 8.1.2 重载基础', '约束也能重载：CRC 错误的两种做法')
s += card('d1', M, 136, 404, 200, BLUE)
s += [text('d1-t', (M + 20, 148, 360, 18), p('先看问题：概率约束管不住“何时发生”', 10.5, BLUE, '700'))]
s += codebox('d1-c', (M + 20, 174, 364, 150), [
    ('constraint default_cons {', CTX),
    ('  crc_err dist {0 := 999_999_999, 1 := 1};  // 十亿分之一', CTX),
    ('  pre_err dist {0 := 999_999_999, 1 := 1};  // 同理', CTX),
    ('}', CTX),
    ('// 长跑时仍可能冒出错包，且无法控制何时', CCM),
], 9)
s += card('d2', 492, 136, 404, 200, BLUE)
s += [text('d2-t', (492 + 20, 148, 360, 18), p('做法一：运行时关约束', 10.5, BLUE, '700'))]
s += codebox('d2-c', (492 + 20, 174, 364, 150), [
    ('m_trans.crc_err_cons.constraint_mode(0);  // 关掉这条约束', CTX),
    ('`uvm_rand_send_with(m_trans, {crc_err == 1;})  // 强制出错', CTX),
    ('// 前提：m_trans 已实例化，否则空指针', CCM),
], 9)
s += [text('d3-t', (M, 352, CW, 18), p('做法二：派生新类，重载约束 —— 后面 factory 重载的雏形', 10.5, BLUE, '700'))]
s += codebox('d3-c', (M, 376, CW, 72), [
    ('class new_transaction extends my_transaction;', CTX),
    ('  constraint crc_err_cons { crc_err dist {0 := 2, 1 := 1}; }  // 重载约束', CKW),
    ('endclass', CTX),
], 9)
slides.append(('04_constraint_override', s))

# ── 05 8.2.1 factory override ──────────────────────────────────────────
s = header('08 · 8.2.1 factory 重载', 'factory 的魔法：写的是 bird，造出来是 parrot')
s += card('e1', M, 136, 430, 196, BLUE)
s += [text('e1-t', (M + 20, 148, 390, 18), p('只加一行 override，创建代码不动', 10.5, BLUE, '700'))]
s += codebox('e1-c', (M + 20, 174, 390, 128), [
    ('// ① 登记一条替换记录：bird → parrot', CCM),
    ('set_type_override_by_type(', CKW),
    ('    bird::get_type(), parrot::get_type());', CTX),
    ('// ② 创建：源码写 bird，实际造出 parrot', CCM),
    ('bird_inst = bird::type_id::create("bird_inst");', CTX),
], 9)
s += card('e2', 518, 136, 378, 196, BLUE)
s += [text('e2-t', (518 + 20, 148, 340, 18), p('create 内部做了什么', 10.5, BLUE, '700'))]
s += bullets('e2-b', (518 + 20, 176, 340, 150), [
    '① create 去 factory 的注册表里按类型查记录',
    '② 找到 override 记录，就把请求类型替换掉',
    '③ 用替换后的类型 new 出实例，返回父类句柄',
    '④ 没有记录就按原类型创建',
], 9.5, 7)
s += [shape('flow-bg', (M, 348, CW, 72), '#F4F8FD', (CARDB, 1))]
s += [text('flow-t', (M + 20, 360, CW - 40, 50), ''.join([
    p('bird::type_id::create  →  factory 查表（bird → parrot）  →  new parrot  →  返回 uvm_object 句柄  →  $cast 成 bird', 9.5, BODY, lh=1.4),
    p('所以“谁被创建”由 factory 的表格决定，不再由源码里的类型名决定。', 9.5, BLUE, '700', mt=6, lh=1.4),
]))]
slides.append(('05_factory_override', s))

# ── 06 four prerequisites ──────────────────────────────────────────────
s = header('08 · 8.2.1 前提', '四个前提，少一个都不生效')
cards = [
    ('①', '注册到 factory', '两个类都要 `uvm_object_utils 或 `uvm_component_utils'),
    ('②', '用 create 创建', '被重载方必须 type_id::create()，new 出来的查不到表'),
    ('③', '必须有派生', '重载类派生自被重载类，方向不能反'),
    ('④', '不能跨族', 'component 与 object 的 new 参数不同，无法互转'),
]
for i, (n, t, d) in enumerate(cards):
    x = M + i * 212
    s += card(f'f{i}', x, 136, 196, 176, BLUE, '#F4F8FD', CARDB)
    s += [text(f'f{i}-n', (x + 18, 148, 36, 26), p(n, 17, BLUE, '700')),
          text(f'f{i}-t', (x + 18, 182, 162, 40), p(t, 12, INK, '700', lh=1.3)),
          text(f'f{i}-d', (x + 18, 228, 162, 76), p(d, 9, MUTED, lh=1.45))]
s += [shape('warn-bg', (M, 332, CW, 66), WARNBG, (WARNBD, 1))]
s += [text('warn-t', (M + 18, 344, CW - 36, 46), ''.join([
    p('违反任意一条的真实报错：', 9.5, WARNTX, '700'),
    p('UVM_FATAL [FCTTYP] Factory did not return an object of type \'bird\'. A component of type \'bear\' was returned instead.', 9, WARNTX, mt=4, lh=1.4),
]))]
s += [text('f-note', (M, 410, CW, 18), p('补充：多级重载时改成“最终类型必须派生自最初类型”，中间那跳可以借道（见第 8 页）。', 9, MUTED))]
slides.append(('06_prereqs', s))

# ── 07 four APIs ───────────────────────────────────────────────────────
s = header('08 · 8.2.2 接口', '四种下单方式：类型、实例、全局、命令行')
api_rows = [
    ('类型重载', 'set_type_override_by_type(A::get_type(), B::get_type())', '整个平台里的 A 都变 B'),
    ('实例重载', 'set_inst_override_by_type("env.o_agt.mon", A::get_type(), B::get_type())', '只换指定路径的那一个'),
    ('按名字', 'set_type_override("A", "B")  /  set_inst_override(path, "A", "B")', '不用 get_type()，传字符串'),
    ('全局 factory', 'factory.set_type_override_by_type(...)', 'initial 里、component 外都能调'),
    ('命令行', '+uvm_set_type_override=A,B[,replace]  /  +uvm_set_inst_override=A,B,<path>', '不改代码，仿真时临时实验'),
]
for i, (c1, c2, c3) in enumerate(api_rows):
    y = 136 + i * 62
    s += [shape(f'a{i}-bg', (M, y, CW, 54), '#F4F8FD', (CARDB, 1)),
          shape(f'a{i}-bar', (M, y, 4, 54), BLUE),
          text(f'a{i}-1', (M + 18, y + 8, 92, 16), p(c1, 10, INK, '700')),
          text(f'a{i}-2', (M + 118, y + 7, 470, 34), p(c2, 8.8, BLUE, '700', lh=1.35)),
          text(f'a{i}-3', (M + 606, y + 8, 210, 16), p(c3, 8.8, MUTED))]
s += [text('api-note', (M, 456, CW, 18), p('component 上的四个函数只是转发给 factory；真正干活的是 uvm_factory 那一份。', 9, MUTED))]
slides.append(('07_apis', s))

# ── 08 consecutive & replace ───────────────────────────────────────────
s = header('08 · 8.2.3 重载语义', '连续重载与替换重载：最后一条说了算')
s += card('g1', M, 136, 404, 200, BLUE)
s += [text('g1-t', (M + 18, 146, 368, 18), p('连续重载：可以接力', 10, BLUE, '700'))]
s += codebox('g1-c', (M + 18, 170, 368, 96), [
    ('// 链式：bird → parrot → big_parrot', CCM),
    ('set_type_override_by_type(bird, parrot);', CTX),
    ('set_type_override_by_type(parrot, big_parrot);', CTX),
    ('// create bird 直接得到 big_parrot', CCM),
], 8.8)
s += [text('g1-n', (M + 18, 280, 368, 44), p('最终创建的是链条末端；中间类型不需要真的被实例化。', 9, MUTED, lh=1.4))]
s += card('g2', 492, 136, 404, 200, BLUE)
s += [text('g2-t', (492 + 18, 146, 368, 18), p('替换重载：replace 决定覆盖', 10, BLUE, '700'))]
s += codebox('g2-c', (492 + 18, 170, 368, 96), [
    ('set_type_override_by_type(bird, parrot);   // 第 1 条', CTX),
    ('set_type_override_by_type(bird, sparrow);  // 默认覆盖', CTX),
    ('set_type_override_by_type(bird, sparrow, 0);  // 保留', CTX),
], 8.8)
s += [text('g2-n', (492 + 18, 280, 368, 44), p('replace=1（默认）：后者覆盖前者；replace=0：保留先注册的那条。', 9, MUTED, lh=1.4))]
s += [shape('rules-bg', (M, 350, CW, 76), '#F4F8FD', (CARDB, 1))]
s += [text('rules-t', (M + 20, 360, CW - 40, 60), ''.join([
    p('两条经验', 10, BLUE, '700'),
    p('· 一个类型只留一条 override，语义最清楚；确实要叠，就显式写 replace=0。', 9.5, BODY, mt=5, lh=1.4),
    p('· 多级重载时，最终类型必须派生自最初被重载的类型，否则 FATAL —— 中间那跳可以“借道”不搭界，但两端必须同源。', 9.5, BODY, mt=3, lh=1.4),
]))]
slides.append(('08_semantics', s))

# ── 09 debug ───────────────────────────────────────────────────────────
s = header('08 · 8.2.4 调试', '重载没生效？让 factory 自己把表打出来')
s += codebox('h', (M, 136, 430, 250), [
    ('# 重载记录只此一条：', CCM),
    ('set_inst_override_by_type("env.o_agt.mon",', CTX),
    ('          my_monitor::get_type(), new_monitor::get_type());', CTX),
    ('', CTX),
    ('env.o_agt.mon.print_override_info("my_monitor");', CKW),
    ('', CTX),
    ('# Given a request for an object of type \'my_monitor\'', CTX),
    ('# with an instance path of \'uvm_test_top.env.o_agt.mon\',', CTX),
    ('# the factory encountered the following relevant overrides:', CTX),
    ('#   Original Type  Instance Path               Override Type', CTX),
    ('#   my_monitor     uvm_test_top.env.o_agt.mon  new_monitor', CKW),
    ('# The factory will produce an object of type \'new_monitor\'', CTX),
], 8.2, label='sim.log', page='P629')
s += [text('h-t', (518, 138, 378, 18), p('四件工具，按问题大小选', 10.5, BLUE, '700'))]
tools = [
    ('print_override_info("my_monitor")', '看某类型/实例命中了哪些 override'),
    ('factory.debug_create_by_type(…)', '问“这次 create 最终落在哪个类”'),
    ('factory.print(0 / 1 / 2)', '0 只看被重载项，1 加用户类，2 加系统类'),
    ('uvm_top.print_topology()', 'build 后打印整棵树，看节点类型'),
]
for i, (n, d) in enumerate(tools):
    y = 164 + i * 66
    s += [shape(f't{i}-bg', (518, y, 378, 56), '#F4F8FD', (CARDB, 1)),
          text(f't{i}-n', (532, y + 7, 350, 16), p(n, 8.6, BLUE, '700')),
          text(f't{i}-d', (532, y + 27, 350, 16), p(d, 8.4, MUTED))]
slides.append(('09_debug', s))

# ── 10 override transaction ────────────────────────────────────────────
s = header('08 · 8.3.1 常用重载', '重载 transaction：一处改动，用例全复用')
s += [text('i-step', (M, 134, CW, 20), p('正常 sequence 不动，只在 build_phase 里把 my_transaction 换成 crc_err_tr。', 10, BODY))]
s += codebox('i-c', (M, 162, 500, 200), [
    ('class crc_err_tr extends my_transaction;', CTX),
    ('  `uvm_object_utils(crc_err_tr)              // 注册到 factory', CTX),
    ('  constraint crc_err_cons { crc_err == 1; }  // 固定出错', CKW),
    ('endclass', CTX),
    ('', CTX),
    ('function void my_case0::build_phase(uvm_phase phase);', CTX),
    ('  super.build_phase(phase);', CTX),
    ('  factory.set_type_override_by_type(          // ① 换类型', CKW),
    ('      my_transaction::get_type(), crc_err_tr::get_type());', CTX),
    ('  uvm_config_db#(uvm_object_wrapper)::set(this,  // ② 入口不变', CTX),
    ('      "env.i_agt.sqr.main_phase", "default_sequence",', CTX),
    ('      normal_sequence::type_id::get());', CTX),
    ('endfunction', CTX),
], 7.8)
s += card('i2', 588, 162, 308, 200, GREEN)
s += [text('i2-t', (606, 174, 276, 18), p('省掉了什么', 10, GREEN, '700'))]
s += bullets('i2-b', (606, 198, 276, 156), [
    '不用再派生 abnormal_sequence',
    '不用复制 body() 里的 uvm_do',
    '约束跟着类型走，用例只挑类型',
    '同一个 normal_sequence 服务所有用例',
], 9, 7)
s += [text('i-note', (M, 380, CW, 20), p('这比“新建一个异常 sequence”简练得多，也是 factory 最典型的收益。', 9, MUTED))]
slides.append(('10_tx_override', s))

# ── 11 override sequence ───────────────────────────────────────────────
s = header('08 · 8.3.2 常用重载', '重载 sequence：不动入口，换掉中间那层')
s += [text('j-t', (M, 134, CW, 18), p('case_sequence 里嵌套了 normal_sequence，入口保持 case_sequence 不变：', 10, BODY))]
s += codebox('j1', (M, 162, 404, 180), [
    ('class case_sequence extends uvm_sequence;', CTX),
    ('  virtual task body();', CTX),
    ('    normal_sequence nseq;', CTX),
    ('    repeat (10) `uvm_do(nseq)', CTX),
    ('  endtask', CTX),
    ('endclass', CTX),
], 8.8)
s += codebox('j2', (492, 162, 404, 180), [
    ('class abnormal_sequence extends normal_sequence;', CTX),
    ('  virtual task body();', CTX),
    ('    m_trans = new("m_trans");', CTX),
    ('    m_trans.crc_err_cons.constraint_mode(0);', CTX),
    ('    `uvm_rand_send_with(m_trans, {crc_err == 1;})', CTX),
    ('  endtask', CTX),
    ('endclass', CTX),
], 8.8)
s += [shape('j-n-bg', (M, 362, CW, 60), '#F4F8FD', (CARDB, 1))]
s += [text('j-n', (M + 20, 374, CW - 40, 40), ''.join([
    p('factory.set_type_override_by_type(normal_sequence::get_type(), abnormal_sequence::get_type());', 9, BLUE, '700'),
    p('书里说：同一件事 UVM 给了多种做法，选最省事的那种；transaction 重载靠约束重载，sequence 重载靠派生。', 9, BODY, mt=4, lh=1.4),
]))]
slides.append(('11_seq_override', s))

# ── 12 override component + limits ─────────────────────────────────────
s = header('08 · 8.3.3 / 8.3.4 常用重载', '重载 component：换掉 driver 自己')
s += codebox('k-c', (M, 136, 500, 214), [
    ('class crc_driver extends my_driver;', CTX),
    ('  `uvm_component_utils(crc_driver)', CTX),
    ('  virtual function void inject_crc_err(my_transaction tr);', CTX),
    ('    tr.crc = $urandom_range(10000000, 0);', CTX),
    ('  endfunction', CTX),
    ('  virtual task main_phase(uvm_phase phase);', CTX),
    ('    ...  seq_item_port.get_next_item(req);', CTX),
    ('    inject_crc_err(req);        // 发送前篡改', CKW),
    ('    drive_one_pkt(req);', CTX),
    ('  endtask', CTX),
    ('endclass', CTX),
], 8.2)
s += card('k2', 588, 136, 308, 214, BLUE)
s += [text('k2-t', (606, 148, 276, 18), p('还能这么用', 10, BLUE, '700'))]
s += bullets('k2-b', (606, 174, 276, 172), [
    '参考模型按异常拆成多个小模型，用例里替换',
    'scoreboard 也能换：不同比对策略',
    '尤其适合“sequence 里不好构造”的极端异常',
], 9, 8)
s += [shape('warn2', (M, 368, CW, 74), WARNBG, (WARNBD, 1))]
s += [text('warn2-t', (M + 18, 380, CW - 36, 54), ''.join([
    p('但别把用例全塞进 driver（8.3.4）：', 9.5, WARNTX, '700'),
    p('objection 要从 sequence 搬回 driver；virtual sequence 的同步协调没有了；driver 会越写越胖，与 sequence 的设计初衷背道而驰。', 9, WARNTX, mt=4, lh=1.4),
]))]
slides.append(('12_comp_override', s))

# ── 13 8.4.1 创建实例的三种方法 ────────────────────────────────────────
s = header('08 · 8.4.1 创建实例', '没有 factory：只能 new，或把类型当参数')
s += purpose('三种建对象方式都绕不开 new，语言也不内建“按字符串建类”——这正是 factory 要补的能力。')
s += [text('a-t', (M, 160, CW, 18),
           p('8.4.1 三种建对象方式（8-54 / 8-55 / 8-56）', 10.5, BLUE, '700'))]
s += codebox('a1-c', (M, 182, 268, 182), [
    ('class B;', CTX),
    ('  A a;', CTX),
    ('  function new();', CTX),
    ('    a = new();', CTX),
    ('  endfunction', CTX),
    ('endclass', CTX),
], 16, label='8-54 直接 new', page='P644')
s += codebox('a2-c', (M + 282, 182, 268, 182), [
    ('class pc #(type T);', CTX),
    ('  T t;', CTX),
    ('  function new();', CTX),
    ('    t = new();', CTX),
    ('  endfunction', CTX),
    ('endclass', CTX),
], 16, label='8-55 参数化类', page='P645')
s += codebox('a3-c', (M + 564, 182, 268, 182), [
    ('class B;', CTX),
    ('  string type_string;', CTX),
    ('  function new();', CTX),
    ('    type_string = "A";', CTX),
    ('  endfunction', CTX),
    ('endclass', CTX),
], 16, label='8-56 字符串？', page='P645')
s += callout('a4', M, 372, CW, 72, '直接 new / 参数化类只能在编译期定死类型；“按字符串建类”语言并不内建。于是 factory 应运而生：先登记类名，再查表 new 出实例（下页 8.4.2）。', GREEN)
slides.append(('13_impl', s))

# ── 13b 8.4.2 按名字建对象（登记 + 查表 new）──────────────────────────
s = header('08 · 8.4.2 按名字建对象', '先登记类名，再查表 new')
s += purpose('factory 按名字建对象的两步：registry 把类名登记进全局表，create_*_by_name 查表 new。')
s += codebox('b1-c', (M, 162, CW, 318), [
    ('class my_driver;', CTX),
    ('  typedef registry#(my_driver,"my_driver") this_type; // 表项存类型+类名', CTX),
    ('  local static this_type me = get();                  // 静态登记一次', CKW),
    ('  static function this_type get();', CTX),
    ('    me=new(); global_tab[me.name]=me; return me; endfunction', CTX),
    ('endclass', CTX),
    ('function uvm_component create_component_by_name(string name);', CTX),
    ('  registry#(uvm_object,"") me_ptr;', CTX),
    ('  me_ptr = global_tab[name];  // ① 查表', CKW),
    ('  me_ptr.inst = new();        // ② new', CKW),
    ('  return me_ptr.inst;         // ③ 返回', CTX),
    ('endfunction', CTX),
], 16, label='8-57 / 8-58 / 8-59 登记 → 查表 new', page='P647-648')
s += [text('b2', (M, 484, CW, 14),
           p('uvm_*_utils 宏 = 上面这段的“加强版”（书 P648）。', 8.6, MUTED, lh=1.3))]
slides.append(('13b_reg', s))

# ── 13c 8.4.3 四个创建接口 & 8.4.4 本质 ────────────────────────────────
s = header('08 · 8.4.3 接口', '四个创建接口：按名字 / 按类型 × object / component')
s += purpose('四个 create_* 接口怎么选、怎么用，本质是 factory 对 new 的重载。')
s += codebox('q1-c', (M, 160, 404, 136), [
    ('my_transaction tr;', CTX),
    ('void\'($cast(tr, factory.', CTX),
    ('  create_object_by_name(', CTX),
    ('    "my_transaction")));', CTX),
], 16, label='8-60/61 object·name', page='P649')
s += codebox('q2-c', (492, 160, 404, 136), [
    ('my_transaction tr;', CTX),
    ('void\'($cast(tr, factory.', CTX),
    ('  create_object_by_type(', CTX),
    ('    my_transaction::get_type())));', CTX),
], 16, label='8-62/63 object·type', page='P650')
s += codebox('q3-c', (M, 298, 404, 152), [
    ('my_scoreboard scb;', CTX),
    ('void\'($cast(scb, factory.', CTX),
    ('  create_component_by_name(', CTX),
    ('    "my_scoreboard",', CTX),
    ('    get_full_name(), "scb", this)));', CTX),
], 16, label='8-64/65 component·name', page='P650')
s += codebox('q4-c', (492, 298, 404, 152), [
    ('my_scoreboard scb;', CTX),
    ('void\'($cast(scb, factory.', CTX),
    ('  create_component_by_type(', CTX),
    ('    my_scoreboard::get_type(),', CTX),
    ('    get_full_name(), "scb", this)));', CTX),
], 16, label='8-67/68 component·type', page='P652')
s += callout('q5', M, 454, CW, 42, '本质（8.4.4）：factory 是对 new 的重载——先查表决定 new 谁，再补 override 与 parent。', GREEN)
slides.append(('13c_api', s))

# ── 14 9.1.1 generalized callback ──────────────────────────────────────
s = header('09 · 9.1.1 广义回调', 'crc 是怎么从“手动补一句”变成“自动调用”的', TEAL)
s += card('m1', M, 136, 404, 240, TEAL)
s += [text('m1-t', (M + 18, 148, 368, 18), p('书里的原始写法：每次 randomize 后手动补', 10, TEAL, '700'))]
s += codebox('m1-c', (M + 18, 174, 368, 132), [
    ('my_transaction tr;', CTX),
    ('assert(tr.randomize());', CTX),
    ('tr.crc = tr.calc_crc();  // 漏一句就埋 bug', CKW),
], 8.8)
s += [text('m1-n', (M + 18, 318, 368, 44),
          p('CRC 必须等包数据定下来才算，所以 randomize 之后还要手动补 calc_crc；忘一次就是隐蔽错误。', 9, MUTED, lh=1.4))]
s += card('m2', 492, 136, 404, 240, TEAL)
s += [text('m2-t', (492 + 18, 148, 368, 18), p('改成回调写法：重载 post_randomize', 10, TEAL, '700'))]
s += codebox('m2-c', (492 + 18, 174, 368, 132), [
    ('function void my_transaction::post_randomize();', CTX),
    ('  super.post_randomize();', CTX),
    ('  crc = this.calc_crc();  // 框架自动调用', CKW),
    ('endfunction', CTX),
], 8.8)
s += [text('m2-n', (492 + 18, 318, 368, 44),
          p('randomize 结束后 SV 会自动调 post_randomize，calc_crc 不再靠“记得手动补”。', 9, MUTED, lh=1.4))]
s += callout('m-note', M, 396, CW, 46, 'post_randomize 就是 SV 预置的回调位：开发者留好位置，使用者填内容 —— UVM 的 callback 机制只是把它做成可注册、可组合的框架。')
slides.append(('14_cb_general', s))

# ── 15 9.1.2 necessity ─────────────────────────────────────────────────
s = header('09 · 9.1.2 为什么需要', 'VIP 里的 driver 改不了，但你得插一手', TEAL)
s += card('n1', M, 136, 500, 200, TEAL)
s += [text('n1-t', (M + 18, 146, 464, 18), p('一个成熟的 VIP 里，派生类根本没人实例化', 10, TEAL, '700'))]
s += bullets('n1-b', (M + 18, 172, 464, 158), [
    'driver 是封装好的，内部 new 的是 my_driver',
    '你派生 new_driver，但 VIP 里没有一句 new new_driver',
    '所以虚函数重载失效，pre_tran 永远不会被调用',
    'factory 能换类型，但你要的是“插动作”，不是“换 driver”',
], 9.2, 7)
s += card('n2', 588, 136, 308, 200, TEAL, '#EAF7FA', '#C9E6EE')
s += [text('n2-t', (606, 146, 276, 18), p('用户真正想做的事', 10, TEAL, '700'))]
s += bullets('n2-b', (606, 170, 276, 158), [
    'A：包尾塞序号，方便定位错包',
    'B：发包前先在线路上打几个特殊字节',
    'C：把包长截短，测边界',
    'D：……每个用户都不一样',
], 9, 7)
s += [text('n-note', (M, 352, CW, 40), ''.join([
    p('结论：程序的开发者不需要 callback，是使用者需要 —— 预留 pre_tran 这类接口，VIP 的适用面就被放大了。', 9.5, TEAL, '700', lh=1.4),
]))]
slides.append(('15_cb_why', s))

# ── 16 principle ───────────────────────────────────────────────────────
s = header('09 · 9.1.3 原理', '两次演进：从“派生一个类”到“遍历一个池子”', TEAL)
s += [shape('o1', (M, 136, 246, 104), '#F4F8FD', (CARDB, 1)),
      text('o1-t', (M + 14, 146, 218, 16), p('① 直接派生（行不通）', 9, TEAL, '700')),
      text('o1-b', (M + 14, 168, 218, 66), ''.join([
          p('class new_driver extends my_driver;', 8.2, BODY),
          p('  // VIP 里没人 new 它', 8.2, MUTED),
          p('// pre_tran 永不执行', 8.2, MUTED),
      ]))]
s += [shape('o2', (356, 136, 246, 104), '#EAF7FA', ('#C9E6EE', 1)),
      text('o2-t', (370, 146, 218, 16), p('② 抽出一个 A 类', 9, TEAL, '700')),
      text('o2-b', (370, 168, 218, 66), ''.join([
          p('task main_phase();', 8.2, BODY),
          p('  ... A.pre_tran(req);', 8.2, BODY),
          p('// 派生 A 的代价远小于派生 driver', 8.2, MUTED),
      ]))]
s += [shape('o3', (656, 136, 240, 104), '#F4F8FD', (CARDB, 1)),
      text('o3-t', (670, 146, 212, 16), p('③ 加一个池子', 9, TEAL, '700')),
      text('o3-b', (670, 168, 212, 66), ''.join([
          p('foreach (A_pool[i])', 8.2, BODY),
          p('  A_pool[i].pre_tran(req);', 8.2, BODY),
          p('// 池子登记了谁，就调谁', 8.2, MUTED),
      ]))]
s += [rule('arr1', (312, 190, 40, 1), TEAL, 1.5, arrow=True),
      rule('arr2', (612, 190, 40, 1), TEAL, 1.5, arrow=True)]
s += [shape('p-bg', (M, 264, CW, 104), '#F4F8FD', (CARDB, 1))]
s += [text('p-t', (M + 20, 276, CW - 40, 84), ''.join([
    p('UVM 的实现就是这三步的工程化：', 9.5, TEAL, '700'),
    p('A 从 uvm_callback 派生；A_pool 用 uvm_callbacks#(my_driver, A) 声明；my_driver 用 `uvm_register_cb 登记、用 `uvm_do_callbacks 触发。', 9.2, BODY, mt=5, lh=1.45),
    p('driver 只认识“池子”，不认识任何具体回调子类 —— 依赖被反转，使用者可以随时往池子里加实例。', 9.2, BODY, mt=4, lh=1.45),
]))]
slides.append(('16_cb_principle', s))

# ── 17 usage ───────────────────────────────────────────────────────────
s = header('09 · 9.1.4 落地', '六步：VIP 侧四步，用户侧两步', TEAL)
s += [shape('q1-bg', (M, 132, 404, 250), '#F7FAFD', (CARDB, 1)),
      shape('q1-bar', (M, 132, 3, 250), TEAL),
      text('q1-t', (M + 16, 142, 372, 16), p('VIP / 平台开发者', 9.5, TEAL, '700'))]
s += [text('q1-b', (M + 16, 166, 372, 210), ''.join([
    p('① 定义回调类（必须派生 uvm_callback，任务必须 virtual）', 8.6, INK, '700'),
    p('class A extends uvm_callback;', 8.2, BODY),
    p('  virtual task pre_tran(my_driver drv, ref my_transaction tr);', 8.2, BODY),
    p('endclass', 8.2, BODY),
    p('② 声明池子', 8.6, INK, '700', mt=8),
    p('typedef uvm_callbacks#(my_driver, A) A_pool;', 8.2, BODY),
    p('③ 在 driver 里登记', 8.6, INK, '700', mt=8),
    p('`uvm_register_cb(my_driver, A)', 8.2, TEAL, '700'),
    p('④ 在要挂钩子的地方触发', 8.6, INK, '700', mt=8),
    p('`uvm_do_callbacks(my_driver, A, pre_tran(this, req))', 8.2, TEAL, '700'),
]))]
s += [shape('q2-bg', (492, 132, 404, 250), '#EDF7FA', ('#C9E6EE', 1)),
      shape('q2-bar', (492, 132, 3, 250), TEAL),
      text('q2-t', (508, 142, 372, 16), p('测试用例使用者', 9.5, TEAL, '700'))]
s += [text('q2-b', (508, 166, 372, 210), ''.join([
    p('⑤ 派生并重载', 8.6, INK, '700'),
    p('class my_callback extends A;', 8.2, BODY),
    p('  virtual task pre_tran(my_driver drv, ref my_transaction tr);', 8.2, BODY),
    p('    // 你的动作', 8.2, MUTED),
    p('  endtask', 8.2, BODY),
    p('  `uvm_object_utils(my_callback)', 8.2, BODY),
    p('endclass', 8.2, BODY),
    p('⑥ connect_phase 里挂到池子上', 8.6, INK, '700', mt=8),
    p('my_cb = my_callback::type_id::create("my_cb");', 8.2, BODY),
    p('A_pool::add(env.i_agt.drv, my_cb);', 8.2, TEAL, '700'),
]))]
s += [text('q-note', (M, 396, CW, 18), p('顺序要求：add 必须早于第一次 `uvm_do_callbacks（一般在 connect_phase）。第一个参数是 driver 实例路径，支持多 driver 场景。', 8.8, MUTED))]
slides.append(('17_cb_usage', s))

# ── 18 inheritance ─────────────────────────────────────────────────────
s = header('09 · 9.1.5 进阶', '子类 driver 怎么复用父类的池子', TEAL)
s += codebox('r-c', (M, 136, 500, 196), [
    ('class new_driver extends my_driver;', CTX),
    ('  `uvm_component_utils(new_driver)', CTX),
    ('  `uvm_set_super_type(new_driver, my_driver)', CKW),
    ('endclass', CTX),
    ('', CTX),
    ('task new_driver::main_phase(uvm_phase phase);', CTX),
    ('  ...', CTX),
    ('  `uvm_do_callbacks(my_driver, A, pre_tran(this, req))', CKW),
    ('  // 注意：第一个参数仍写父类 my_driver', CCM),
    ('endtask', CTX),
], 8.2)
s += card('r2', 588, 136, 308, 196, TEAL, '#EAF7FA', '#C9E6EE')
s += [text('r2-t', (606, 148, 276, 18), p('为什么这样能生效', 10, TEAL, '700'))]
s += [text('r2-b', (606, 176, 276, 146), ''.join([
    p('池子在声明时就绑定了 my_driver，new_driver 默认不在它的语义里。', 9, BODY, lh=1.45),
    p('`uvm_set_super_type 把子类挂到父类名下，父类池子对子类实例继续生效。', 9, BODY, mt=6, lh=1.45),
    p('结果：第一代产品的老用例一行不改，跑在新平台上。', 9, TEAL, '700', mt=6, lh=1.45),
]))]
s += [shape('r3', (M, 348, CW, 60), '#F4F8FD', (CARDB, 1))]
s += [text('r3-t', (M + 20, 360, CW - 40, 40), p('这是“前后两代产品、同一套验证平台”的关键：扩展 driver，而不是重写 driver。', 9.5, BODY, lh=1.4))]
slides.append(('18_cb_inherit', s))

# ── 19 full callback + three mechanisms ────────────────────────────────
s = header('09 · 9.1.6 / 9.1.7', 'callback 能走多远，以及三种机制怎么分工', TEAL)
s += [text('s-t', (M, 132, CW, 18), p('极端用法：把 objection 和激励生成都搬进回调类，driver 只剩一句调用。', 9.5, BODY))]
s += codebox('s1', (M, 158, 404, 128), [
    ('class A extends uvm_callback;', CTX),
    ('  virtual function bit gen_tran(); endfunction', CTX),
    ('  virtual task run(my_driver drv, uvm_phase phase);', CTX),
    ('    phase.raise_objection(drv);', CTX),
    ('    while (gen_tran()) drv.drive_one_pkt(tr);', CTX),
    ('    phase.drop_objection(drv);', CTX),
    ('  endtask', CTX),
    ('endclass', CTX),
], 7.8)
s += codebox('s2', (492, 158, 404, 128), [
    ('task my_driver::main_phase(uvm_phase phase);', CTX),
    ('  `uvm_do_callbacks(my_driver, A, run(this, phase))', CTX),
    ('endtask', CTX),
    ('', CTX),
    ('// 新用例 = 从 A 派生，重载 gen_tran', CCM),
    ('// 完全不再需要 sequence', CCM),
], 7.8)
mech = [('FACTORY 重载', '换掉“用哪个类”', '零改代码、可命令行下发', BLUE),
        ('CALLBACK', '在预留点插入动作', '不改 VIP、可叠加多个', TEAL),
        ('SEQUENCE', '组织激励流', '嵌套 / 同步 / 复用最强', GREEN)]
for i, (t, role, adv, c) in enumerate(mech):
    x = M + i * 280
    s += [shape(f'm{i}-bg', (x, 300, 264, 96), '#F4F8FD', (CARDB, 1)),
          shape(f'm{i}-bar', (x, 300, 4, 96), c),
          text(f'm{i}-t', (x + 16, 308, 232, 14), p(t, 8.2, c, '700', 1)),
          text(f'm{i}-r', (x + 16, 328, 236, 18), p(role, 10, INK, '700')),
          text(f'm{i}-a', (x + 16, 352, 236, 36), p(adv, 8.2, MUTED, lh=1.4))]
s += [text('s-note', (M, 408, CW, 40), p('书中结论：三者不互斥；callback 也能做所有用例，但 virtual sequence 的协调能力会丢，所以它是“补丁”不是“地基”。', 9.2, BODY, lh=1.4))]
slides.append(('19_three_mechanisms', s))

# ── 20 9.2 small is beautiful ──────────────────────────────────────────
s = header('09 · 9.2 可重用性', '小而美：为什么要把功能拆碎', GREEN)
s += card('t1', M, 136, 404, 190, GREEN)
s += [text('t1-t', (M + 18, 146, 368, 18), p('Linux 的哲学：小工具组合', 10, GREEN, '700'))]
s += bullets('t1-b', (M + 18, 170, 368, 150), [
    'ls / grep / wc：每个都很小，但职责清晰',
    '组合起来能完成大任务，单看参数表也不吓人',
    '反例 lsgrepwc：三个功能塞一个命令，用户要先猜参数属于谁',
    '小 ≠ 美：划分不合理（lgr）一样是灾难',
], 9, 7)
s += card('t2', 492, 136, 404, 190, GREEN)
s += [text('t2-t', (492 + 18, 146, 368, 18), p('和 factory 重载的关系（9.2.2）', 10, GREEN, '700'))]
s += codebox('t2-c', (492 + 18, 170, 368, 148), [
    ('task A_driver::drive_one_pkt;', CTX),
    ('  drive_preamble(); drive_sfd(); drive_data();', CTX),
    ('endtask', CTX),
    ('', CTX),
    ('// 拆成子任务后：派生 B_driver，只重载 drive_sfd()', CCM),
    ('// 不拆：整段复制 drive_one_pkt，改一处要维护两处', CCM),
], 8)
s += [shape('t3', (M, 344, CW, 62), GREENBG, (GREENBD, 1))]
s += [text('t3-t', (M + 20, 356, CW - 40, 40), ''.join([
    p('9.2.3：别造超级 sequence。', 9.5, GREEN, '700'),
    p('一个 sequence 用十几个参数覆盖所有异常组合，代码量巨大、没人看得懂；拆成 normal_sequence / crc_err_sequence 更实在。', 9, BODY, mt=3, lh=1.4),
]))]
slides.append(('20_small_beautiful', s))

# ── 21 parametric classes ──────────────────────────────────────────────
s = header('09 · 9.3 参数化类', '参数化类：把“位宽”这类差异交给参数', GREEN)
s += [text('u-t', (M, 132, CW, 18), p('重用的四个层次：自己用→自己跨项目→他人同项目→他人跨项目；层次越高，越需要参数化。', 9.5, BODY))]
s += codebox('u1', (M, 160, 404, 152), [
    ('virtual class uvm_sequence #(type REQ = uvm_sequence_item,', CTX),
    ('                                   type RSP = REQ)  // 两个参数', CTX),
    ('  extends uvm_sequence_base;', CTX),
    ('', CTX),
    ('// 派生时指定 transaction 类型，激励就“认得”包了', CCM),
], 8.2)
s += codebox('u2', (492, 160, 404, 152), [
    ('interface bus_if#(int ADDR_WIDTH=16, int DATA_WIDTH=16)', CTX),
    ('                 (input clk, input rst_n);   // 位宽可配', CTX),
    ('uvm_config_db#(virtual bus_if#(16,16))::set(...);  // 传参化接口', CTX),
    ('class bus_sequencer#(int ADDR_WIDTH=16, int DATA_WIDTH=16)', CTX),
    ('  extends uvm_sequencer #(bus_transaction#(ADDR_WIDTH, DATA_WIDTH));', CTX),
], 8.2)
s += [shape('u3', (M, 330, CW, 92), '#F4F8FD', (CARDB, 1))]
s += [text('u3-t', (M + 20, 342, CW - 40, 70), ''.join([
    p('两个坑', 10, GREEN, '700'),
    p('· factory 注册要用 uvm_object_param_utils / uvm_component_param_utils，普通 utils 宏不认参数。', 9, BODY, mt=4, lh=1.4),
    p('· UVM 的 factory 不支持参数化类的默认参数：声明可省，实例化必须写全 —— bus_agent#(16,16)::type_id::create(...)。', 9, BODY, mt=2, lh=1.4),
]))]
slides.append(('21_params', s))

# ── 22 9.4.1 env reuse ─────────────────────────────────────────────────
s = header('09 · 9.4.1 模块到芯片', '基于 env 的重用：用 in_chip 关掉多余的 driver', GREEN)
s += card('v1', M, 134, 404, 290, GREEN)
s += [text('v1-t', (M + 18, 146, 368, 18), p('模块级 env：留好 in_chip、ap / i_export', 10, GREEN, '700'))]
s += codebox('v1-c', (M + 18, 172, 368, 236), [
    ('class my_env extends uvm_env;', CTX),
    ('  bit in_chip;', CTX),
    ('  uvm_analysis_port#(my_transaction) ap;', CTX),
    ('  uvm_analysis_export#(my_transaction) i_export;', CTX),
    ('  virtual function void build_phase(...);', CTX),
    ('    super.build_phase(phase);', CTX),
    ('    if(!in_chip) begin  // 芯片级不造 i_agt', CCM),
    ('      i_agt = my_agent::type_id::create("i_agt", this);', CTX),
    ('      i_agt.is_active = UVM_ACTIVE;', CTX),
    ('    end', CTX),
    ('    if(in_chip) i_export = new("i_export", this);', CTX),
    ('  endfunction', CTX),
    ('  // connect_phase: ap = o_agt.ap', CCM),
    ('  //   in_chip ? i_export.connect(...) : i_agt.ap.connect(...)', CCM),
], 7.8)
s += card('v2', 492, 134, 404, 290, GREEN)
s += [text('v2-t', (492 + 18, 146, 368, 18), p('芯片级 chip_env：把 ap 接到下一级 i_export', 10, GREEN, '700'))]
s += codebox('v2-c', (492 + 18, 172, 368, 236), [
    ('class chip_env extends uvm_env;', CTX),
    ('  `uvm_component_utils(chip_env)', CTX),
    ('  my_env env_A, env_B, env_C;', CTX),
    ('  virtual function void build_phase(...);', CTX),
    ('    env_A = my_env::type_id::create("env_A", this);', CTX),
    ('    env_B = my_env::type_id::create("env_B", this);', CTX),
    ('    env_B.in_chip = 1;  // B/C 只收数据，不造 i_agt', CCM),
    ('    env_C = my_env::type_id::create("env_C", this);', CTX),
    ('    env_C.in_chip = 1;', CTX),
    ('  endfunction', CTX),
    ('  // connect_phase:', CCM),
    ('  //   env_A.ap.connect(env_B.i_export);', CCM),
    ('  //   env_B.ap.connect(env_C.i_export);', CCM),
], 7.8)
s += [text('v-note', (M, 440, CW, 40), p('对比图 9-3/9-4：in_chip=1 的 env 不再造 i_agt，i_export 从上一级的 ap 取数 —— 冗余 monitor 被取消，数据一路传递。', 9.2, BODY, lh=1.4))]
slides.append(('22_env_reuse', s))

# ── 23 9.4.2 reg model reuse ───────────────────────────────────────────
s = header('09 · 9.4.2 模块到芯片', '寄存器模型重用：把 rm 从 env 搬到 base_test', GREEN)
s += card('w1', M, 134, 404, 300, GREEN)
s += [text('w1-t', (M + 18, 146, 368, 18), p('反例 + chip_reg_model', 10, GREEN, '700'))]
s += codebox('w1-c', (M + 18, 172, 368, 246), [
    ('// ✗ 别在 env 里 new rm：偏移地址会被定死', CCM),
    ('class my_env extends uvm_env;', CTX),
    ('  reg_model rm;', CTX),
    ('  virtual function void build_phase(...);', CTX),
    ('    rm = reg_model::type_id::create("rm", this);', CTX),
    ('  endfunction', CTX),
    ('endclass', CTX),
    ('', CTX),
    ('// ✓ 芯片级：一个块挂住三个模块的 map', CCM),
    ('class chip_reg_model extends uvm_reg_block;', CTX),
    ('  rand reg_model A_rm, B_rm, C_rm;', CTX),
    ('  virtual function void build();', CTX),
    ('    default_map = create_map("default_map", 0, 2, UVM_BIG_ENDIAN, 0);', CTX),
    ('    default_map.add_submap(A_rm.default_map, 16\'h0);', CTX),
    ('    default_map.add_submap(B_rm.default_map, 16\'h4000);', CTX),
    ('    default_map.add_submap(C_rm.default_map, 16\'h8000);', CTX),
    ('  endfunction', CTX),
    ('endclass', CTX),
], 7.4)
s += card('w2', 492, 134, 404, 300, GREEN)
s += [text('w2-t', (492 + 18, 146, 368, 18), p('chip_env 里实例化并把 p_rm 分给各 env', 10, GREEN, '700'))]
s += codebox('w2-c', (492 + 18, 172, 368, 246), [
    ('function void chip_env::build_phase(...);', CTX),
    ('  env_A = my_env::type_id::create("env_A", this);', CTX),
    ('  env_B = my_env::type_id::create("env_B", this);', CTX),
    ('  env_B.in_chip = 1;', CTX),
    ('  env_C = my_env::type_id::create("env_C", this);', CTX),
    ('  env_C.in_chip = 1;', CTX),
    ('  chip_rm = chip_reg_model::type_id::create("chip_rm", this);', CTX),
    ('  chip_rm.configure(null, "");', CTX),
    ('  chip_rm.build();', CTX),
    ('  chip_rm.lock_model();', CTX),
    ('  chip_rm.reset();', CTX),
    ('  reg_sqr_adapter = new("reg_sqr_adapter");', CTX),
    ('  env_A.p_rm = this.chip_rm.A_rm;  // 分下去', CCM),
    ('  env_B.p_rm = this.chip_rm.B_rm;', CCM),
    ('  env_C.p_rm = this.chip_rm.C_rm;', CCM),
    ('endfunction', CTX),
], 7.4)
s += [text('w-note', (M, 450, CW, 40), p('要点：模块级就把 rm 挪到 base_test，env 只留 p_rm 指针；芯片级用 add_submap 设偏移地址，再把子块指针分回各 env。', 9.2, BODY, lh=1.4))]
slides.append(('23_reg_reuse', s))

# ── 23 code compare A (factory) ────────────────────────────────────────
s = header('实战对照 A', 'Factory：书中代码 vs 我的项目代码', BLUE)
s += [text('w-t', (M, 130, CW, 18), p('左边是书里第 8 章的写法，右边留空——贴你自己的 override / create 代码，逐条对比。', 9.5, BODY))]
s += codebox('w1', (M, 156, 404, 300), [
    ('// 8.3.1', CCM),
    ('class crc_err_tr extends my_transaction;', CTX),
    ('  constraint crc_err_cons { crc_err == 1; }', CKW),
    ('endclass', CTX),
    ('', CTX),
    ('function void my_case0::build_phase(uvm_phase phase);', CTX),
    ('  factory.set_type_override_by_type(', CKW),
    ('    my_transaction::get_type(), crc_err_tr::get_type());', CTX),
    ('  uvm_config_db#(uvm_object_wrapper)::set(this,', CTX),
    ('    "env.i_agt.sqr.main_phase", "default_sequence",', CTX),
    ('    normal_sequence::type_id::get());', CTX),
    ('endfunction', CTX),
], 8.2, label='src/ch8/section8.3/8.3.1/my_case0.sv', page='P635')
s += [shape('w2-bg', (492, 156, 404, 300), '#FFFFFF', ('#C9D5E3', 1))]
s += [text('w2-l', (506, 166, 376, 16), p('我的项目代码（粘贴区）', 9, BLUE, '700'))]
s += [text('w2-h', (506, 200, 376, 60), p('在这里贴 override 注册、create 调用、命令行参数……', 9, '#B7C7D9', lh=1.5))]
s += [text('w2-s1', (506, 250, 376, 18), p('① 贴一段 override 注册 / create 调用', 8.6, '#C7D4E4'))]
s += [text('w2-s2', (506, 278, 376, 18), p('② 标出与书中不同的写法：类型 vs 名字、replace 取值', 8.6, '#C7D4E4'))]
s += [text('w2-s3', (506, 306, 376, 18), p('③ 记下踩坑：FCTTYP 报错 / 重载没生效的原因', 8.6, '#C7D4E4'))]
s += [text('w2-h2', (506, 420, 376, 20), p('对比点：注册方式 / 用 type 还是 name / replace 取值', 8.4, '#9FB2C8'))]
slides.append(('23_compare_factory', s))

# ── 24 code compare B (callback) ───────────────────────────────────────
s = header('实战对照 B', 'Callback：书中六步 vs 我的项目代码', TEAL)
s += [text('y-t', (M, 130, CW, 18), p('左边是 9.1.4 的六步骨架，右边贴你的 VIP/用例实现，重点看“接口留在谁手里”。', 9.5, BODY))]
s += codebox('y1', (M, 156, 404, 300), [
    ('// VIP 侧', CCM),
    ('class A extends uvm_callback;', CTX),
    ('  virtual task pre_tran(my_driver drv, ref my_transaction tr);', CTX),
    ('endclass', CTX),
    ('typedef uvm_callbacks#(my_driver, A) A_pool;', CTX),
    ('`uvm_register_cb(my_driver, A)', CTX),
    ('`uvm_do_callbacks(my_driver, A, pre_tran(this, req))', CTX),
    ('', CTX),
    ('// 用户侧', CCM),
    ('my_cb = my_callback::type_id::create("my_cb");', CTX),
    ('A_pool::add(env.i_agt.drv, my_cb);', CTX),
], 8.2, label='src/ch9/section9.1/9.1.4/callbacks.sv', page='P663')
s += [shape('y2-bg', (492, 156, 404, 300), '#FFFFFF', ('#C9D5E3', 1))]
s += [text('y2-l', (506, 166, 376, 16), p('我的项目代码（粘贴区）', 9, TEAL, '700'))]
s += [text('y2-h', (506, 200, 376, 60), p('在这里贴预定义接口、注册宏、add 的位置与路径……', 9, '#B7C7D9', lh=1.5))]
s += [text('y2-s1', (506, 250, 376, 18), p('① 贴 VIP 侧的回调类与池子声明', 8.6, '#C7D4E4'))]
s += [text('y2-s2', (506, 278, 376, 18), p('② 标出注册宏与 add 的位置、路径参数', 8.6, '#C7D4E4'))]
s += [text('y2-s3', (506, 306, 376, 18), p('③ 记下多 driver / 子类复用时改了什么', 8.6, '#C7D4E4'))]
s += [text('y2-h2', (506, 420, 376, 20), p('对比点：接口命名 / 池子声明 / 多实例路径管理', 8.4, '#9FB2C8'))]
slides.append(('24_compare_callback', s))

# ── 25 takeaway ────────────────────────────────────────────────────────
s = header('SUMMARY', '带走这 6 条')
pts = [
    ('override 只对 create 生效', '用 new 创建的对象永远查不到重载记录。'),
    ('注册 + 派生 + create', '三条缺一不可；component 与 object 不能跨族替换。'),
    ('一个类型一条 override', '要叠就用 replace=0 明确表达；多级重载两端必须同源。'),
    ('没生效先调试', 'print_override_info 看匹配表，print_topology 看整棵树。'),
    ('callback 靠池子遍历', 'VIP 留口子，用户 add 实例；子类 driver 用 uvm_set_super_type 复用池子。'),
    ('拆分优先于堆砌', '小而美：拆子任务、拆 sequence、参数化，才有可复用性。'),
]
for i, (t, d) in enumerate(pts):
    y = 132 + i * 54
    s += [text(f'z{i}-n', (M, y + 3, 40, 20), p(f'0{i + 1}', 12, BLUE, '700')),
          text(f'z{i}-t', (M + 44, y, 300, 20), p(t, 11.5, INK, '700')),
          text(f'z{i}-d', (M + 44, y + 22, 780, 18), p(d, 8.8, MUTED))]
s += [shape('qa', (M, 470, CW, 26), CODEBG, (CODEBD, 1)),
      text('qa-t', (M, 476, CW, 16), p('Q & A  ·  欢迎拿项目里的 override / callback 代码一起对', 8.8, '#1B5E43', '700'), align=('center', 'top'))]
slides.append(('25_takeaway', s))

# ── write ──────────────────────────────────────────────────────────────
if os.path.isdir(PAGES):
    shutil.rmtree(PAGES)
os.makedirs(PAGES, exist_ok=True)

manifest = {
    "version": "v2",
    "title": "UVM 实战 · Factory 与 Callback 精读",
    "size": [W, H],
    "theme": {"colors": {"bg": "#ECEFF4", "paper": CARD, "primary": BLUE, "accent": TEAL,
                          "text": INK, "muted": MUTED, "line": LINE}},
    "pages": [f'pages/{n}.page' for n, _ in slides],
}
with open(os.path.join(OUT, 'deck.pptd'), 'w', encoding='utf-8') as fh:
    json.dump(manifest, fh, ensure_ascii=False, indent=2)

for idx, (name, elements) in enumerate(slides, start=1):
    page = {"pageType": "content", "background": {"color": "#ECEFF4"}, "elements": list(elements)}
    if idx > 1:
        page["elements"] += footer(idx)
    if name in INSIGHTS:
        bottom = max(e['bounds'][1] + e['bounds'][3] for e in elements)
        if bottom < 444:
            page["elements"] += insight(INSIGHTS[name])
    with open(os.path.join(PAGES, f'{name}.page'), 'w', encoding='utf-8') as fh:
        json.dump(page, fh, ensure_ascii=False, indent=2)

print('pages:', len(slides))






































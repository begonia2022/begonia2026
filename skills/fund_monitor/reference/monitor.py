# -*- coding: utf-8 -*-
"""基金定投监控器 v3（按基金配置策略）

每只基金一套策略：
- zone 模式：回撤≥entry_dd 才建仓，每笔 base，回撤≥deep_dd 加至 deep_base。
- dca 模式：每日 base 定投 + 回撤分档加仓。
- 止盈：normal（普通）或 optimal（最优：卖2/3留1/3底仓）。

用法：
  python monitor.py fetch / backtest / yearly / signal / notify
"""
import json
import os
import sys
import datetime
import urllib.request

import pandas as pd

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None

BASE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(BASE, 'config.json')
CACHE_DIR = os.path.join(BASE, 'cache')
HOLD_PATH = os.path.join(BASE, 'holdings.json')


def load_cfg():
    with open(CFG_PATH, encoding='utf-8') as f:
        return json.load(f)


def load_holdings():
    if not os.path.exists(HOLD_PATH):
        return {}
    try:
        with open(HOLD_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_holdings(h):
    with open(HOLD_PATH, 'w', encoding='utf-8') as f:
        json.dump(h, f, ensure_ascii=False, indent=2)


PENDING_PATH = os.path.join(BASE, 'pending_buys.json')


def load_pending():
    if os.path.exists(PENDING_PATH):
        try:
            with open(PENDING_PATH, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_pending(p):
    with open(PENDING_PATH, 'w', encoding='utf-8') as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


def settle_pending(cfg):
    """把 pending 里已有净值的那天，按实际净值记入持仓。"""
    pend = load_pending()
    if not pend:
        return []
    h = load_holdings()
    done = []
    for date in list(pend.keys()):
        amts = pend[date]
        navs = {}
        ok = True
        for code in amts:
            df = load_fund(code, cfg)
            m = {str(d): float(n) for d, n in zip(df['date'], df['nav'])}
            nav = m.get(date)
            if nav is None:
                ok = False
                break
            navs[code] = nav
        if not ok:
            continue
        for code, amt in amts.items():
            nav = navs[code]
            rec = h.setdefault(code, {'shares': 0, 'cost': 0, 'peak_nav': 0})
            rec['shares'] = float(rec.get('shares', 0)) + amt / nav
            rec['cost'] = float(rec.get('cost', 0)) + amt
            rec['peak_nav'] = max(float(rec.get('peak_nav', 0)), nav)
        del pend[date]
        done.append(date)
    if done:
        save_holdings(h)
        save_pending(pend)
    return done


def queue_buy(cfg, items):
    """把今日 confirm 买入记入 pending（同一天只记一次）。"""
    today = datetime.date.today().isoformat()
    pend = load_pending()
    if today in pend:
        return False
    amts = {it['code']: it['buy'] for it in items if it.get('buy', 0) > 0}
    if not amts:
        return False
    pend[today] = amts
    save_pending(pend)
    return True


def claim_slot():
    """同一 10 分钟时段只允许发送一次；且 3 分钟内不重复发（防唤醒后连发）。"""
    now = datetime.datetime.now()
    last = os.path.join(CACHE_DIR, 'last_sent.txt')
    try:
        if os.path.exists(last):
            t = datetime.datetime.fromisoformat(open(last, encoding='utf-8').read().strip())
            if (now - t).total_seconds() < 180:
                return False
    except Exception:
        pass
    slot = f'{now.hour:02d}{now.minute // 10}'
    path = os.path.join(CACHE_DIR, f'sent_{now.date().isoformat()}_{slot}.lock')
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        with open(last, 'w', encoding='utf-8') as f:
            f.write(now.isoformat())
        return True
    except FileExistsError:
        return False


def cmd_buy(cfg, code, amount):
    h = load_holdings()
    df = load_fund(code, cfg)
    nav = float(df['nav'].iloc[-1])
    rec = h.setdefault(code, {'shares': 0.0, 'cost': 0.0, 'peak_nav': 0.0})
    rec['shares'] = float(rec.get('shares', 0)) + amount / nav
    rec['cost'] = float(rec.get('cost', 0)) + amount
    rec['peak_nav'] = max(float(rec.get('peak_nav', 0)), nav)
    save_holdings(h)
    print(f'买入 {code} {amount:.0f} 元 @ {nav:.4f} -> 持有 {rec["shares"]:.2f} 份, 成本 {rec["cost"]:.2f} 元')


def cmd_sell(cfg, code, shares):
    h = load_holdings()
    rec = h.get(code) or {}
    cur = float(rec.get('shares', 0))
    if cur <= 1e-9:
        print(f'{code} 无持仓')
        return
    q = min(shares, cur)
    avg = float(rec.get('cost', 0)) / cur
    df = load_fund(code, cfg)
    nav = float(df['nav'].iloc[-1])
    rec['shares'] = cur - q
    rec['cost'] = float(rec.get('cost', 0)) - q * avg
    save_holdings(h)
    print(f'卖出 {code} {q:.2f} 份 @ {nav:.4f} -> 回款 {q*nav:.2f} 元, 剩余 {rec["shares"]:.2f} 份')


def holding_info(items, cfg):
    """计算每只基金的实际持仓收益与卖出建议，并更新 peak_nav。"""
    hold = load_holdings()
    tp = float(cfg.get('take_profit', 15))
    pdd = float(cfg.get('peak_drawdown_sell', 5))
    tp2 = float(cfg.get('second_take_profit', 30))
    tp3 = float(cfg.get('final_take_profit', 50))
    changed = False
    for it in items:
        if it.get('error'):
            it['hold'] = None
            continue
        code = it['code']
        rec = hold.get(code) or {}
        sh = float(rec.get('shares', 0))
        cost = float(rec.get('cost', 0))
        if sh <= 1e-9 or cost <= 0:
            it['hold'] = None
            continue
        nav = it['nav']
        avg = cost / sh
        hret = (nav / avg - 1.0) * 100.0
        peak = max(float(rec.get('peak_nav', 0)), nav)
        if peak != float(rec.get('peak_nav', 0)):
            rec['peak_nav'] = peak
            hold[code] = rec
            changed = True
        peak_dd = (peak - nav) / peak * 100.0 if peak > 0 else 0.0
        mode = it.get('sell_mode', 'optimal')
        if hret < tp:
            act = '继续持有'
        elif hret >= tp3:
            act = '清仓'
        elif mode == 'optimal':
            act = ('卖2/3（留1/3底仓）' if peak_dd >= pdd else '持有（止盈观察）')
        else:
            act = ('卖1/3' if peak_dd >= pdd or hret >= tp2 else '持有（止盈观察）')
        it['hold'] = {'shares': sh, 'cost': cost, 'avg': avg, 'ret': hret,
                      'value': sh * nav, 'profit': sh * nav - cost,
                      'peak_dd': peak_dd, 'sell': act}
    if changed:
        save_holdings(hold)


# ---------------------------------------------------------------- 净值
def fetch_nav(code, max_records=1300):
    rows = []
    page = 1
    while len(rows) < max_records:
        url = ('http://api.fund.eastmoney.com/f10/lsjz'
               f'?fundCode={code}&pageIndex={page}&pageSize=20')
        req = urllib.request.Request(url, headers={
            'Referer': 'http://fundf10.eastmoney.com/', 'User-Agent': 'Mozilla/5.0',
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode('utf-8'))
        lst = (d.get('Data') or {}).get('LSJZList') or []
        if not lst:
            break
        for it in lst:
            try:
                rows.append((it['FSRQ'], float(it['DWJZ'])))
            except Exception:
                pass
        if len(lst) < 20:
            break
        page += 1
        if page > 300:
            break
    df = pd.DataFrame(rows, columns=['date', 'nav'])
    return df.dropna().drop_duplicates('date').sort_values('date').reset_index(drop=True)


def load_fund(code, cfg, force=False):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f'{code}.csv')
    cached = None
    if os.path.exists(path):
        try:
            cached = pd.read_csv(path, dtype={'date': str})
        except Exception:
            cached = None
    if not force and cached is not None and len(cached):
        try:
            if datetime.datetime.now().timestamp() - os.path.getmtime(path) < 6 * 3600:
                return cached
        except Exception:
            pass
    try:
        df = fetch_nav(code, cfg.get('backtest_years', 5) * 260 + 120)
        if len(df):
            df.to_csv(path, index=False)
            return df
        raise RuntimeError('empty')
    except Exception:
        if cached is not None and len(cached):
            return cached
        raise


# ---------------------------------------------------------------- 实时估值
def fetch_quote(codes):
    url = ('https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFInfo'
           '?pageIndex=1&pageSize=50&plat=Android&appType=ttjj&product=EFund&Version=1'
           f'&deviceid=abc&Fcodes={",".join(codes)}')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode('utf-8'))
    return {it['FCODE']: it for it in (d.get('Datas') or [])}


def fetch_index(secid):
    """抓跟踪指数实时涨跌（盘中预估）。"""
    url = f'http://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f170,f58,f60'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read().decode('utf-8'))
    data = d.get('data') or {}
    chg = data.get('f170')
    if chg is None:
        return None
    prev = data.get('f60')
    return {'name': data.get('f58'), 'chg': float(chg) / 100.0,
            'prev': (float(prev) / 100.0 if prev not in (None, '') else None)}


def fetch_trend(secid):
    """抓指数当日分钟走势，返回 [(datetime, price), ...]。"""
    url = (f'http://push2.eastmoney.com/api/qt/stock/trends2/get?secid={secid}'
           '&fields1=f1,f2,f3,f4,f5&fields2=f51,f53&ndays=1')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read().decode('utf-8'))
    tr = (d.get('data') or {}).get('trends') or []
    out = []
    for s in tr:
        parts = s.split(',')
        if len(parts) >= 2:
            try:
                dt = datetime.datetime.strptime(parts[0], '%Y-%m-%d %H:%M')
                out.append((dt, float(parts[1])))
            except Exception:
                pass
    return out or None


# ---------------------------------------------------------------- 指标
def add_indicators(df, lookback):
    d = df.copy().sort_values('date').reset_index(drop=True)
    d['nav'] = d['nav'].astype(float)
    d['high'] = d['nav'].shift(1).rolling(lookback, min_periods=1).max()
    d['dd'] = (d['high'] - d['nav']) / d['high'] * 100.0
    d['ma5'] = d['nav'].rolling(5, min_periods=1).mean()
    return d


def drawdown_stats(df):
    """最大回撤 / 当前回撤 / 修复状态 / 距峰值天数。"""
    d = df.sort_values('date').reset_index(drop=True).copy()
    d['nav'] = d['nav'].astype(float)
    d['peak'] = d['nav'].cummax()
    d['dd'] = (d['peak'] - d['nav']) / d['peak'] * 100.0
    dates = d['date'].tolist()
    nav = d['nav'].tolist()
    peaks = d['peak'].tolist()
    n = len(d)
    if n == 0:
        return None
    mi = int(d['dd'].to_numpy().argmax())
    max_dd = float(d['dd'].iloc[mi])
    peak_val = peaks[mi]
    peak_idx = mi
    for j in range(mi, -1, -1):
        if abs(nav[j] - peak_val) < 1e-12:
            peak_idx = j
            break
    rec_idx = None
    for j in range(mi + 1, n):
        if nav[j] >= peak_val - 1e-12:
            rec_idx = j
            break
    rec_days = None
    if rec_idx is not None:
        rec_days = (datetime.date.fromisoformat(dates[rec_idx]) -
                    datetime.date.fromisoformat(dates[mi])).days
    cur_dd = float(d['dd'].iloc[-1])
    cur_peak_val = peaks[-1]
    cur_peak_idx = 0
    for j in range(n - 1, -1, -1):
        if abs(nav[j] - cur_peak_val) < 1e-12:
            cur_peak_idx = j
            break
    look = min(10, n - 1)
    if cur_dd < 0.5:
        status = '已修复/创新高'
    elif look > 0 and cur_dd < float(d['dd'].iloc[-1 - look]) - 0.05:
        status = '回撤修复中'
    else:
        status = '回撤进行中'
    days = (datetime.date.fromisoformat(dates[-1]) -
            datetime.date.fromisoformat(dates[cur_peak_idx])).days
    return {
        'max_dd': max_dd,
        'max_peak_date': dates[peak_idx],
        'max_trough_date': dates[mi],
        'max_recovered_days': rec_days,
        'cur_dd': cur_dd,
        'status': status,
        'days_since_peak': days,
    }


def _tier_buy(dd, base, strat):
    """dca 模式：基线 + 回撤分档额外加仓。"""
    extra = 0.0
    for t, m in zip(strat.get('tiers', []), strat.get('mults', [])):
        if dd >= float(t):
            extra = max(extra, float(m) * base)
    return base, extra


def strat_short(s):
    if not s:
        return ''
    if s.get('type') == 'pyr':
        sm = '普通' if s.get('sell') == 'normal' else '最优'
        return (f"建仓≥{s['entry_dd']}% · 每跌{s.get('step', 5):.0f}%多买{s.get('add', 100):.0f}元 · 止盈:{sm}")
    if s.get('type') == 'zone':
        sm = '普通' if s.get('sell') == 'normal' else '最优'
        return (f"建仓≥{s['entry_dd']}% · 每笔{s['base']:.0f}元 · "
                f"再跌5%加到{s['deep_base']:.0f}元 · 止盈:{sm}")
    tail = '+回撤分档' if s.get('tiers') else ''
    return f"每日{s['base']:.0f}元定投{tail} · 止盈:最优"


def xirr(flows):
    flows = [(d, a) for d, a in flows if abs(a) > 1e-9]
    if len(flows) < 2:
        return None
    if not (any(a > 0 for _, a in flows) and any(a < 0 for _, a in flows)):
        return None
    ds = [datetime.date.fromisoformat(d) for d, _ in flows]
    amts = [a for _, a in flows]
    t0 = min(ds)

    def npv(r):
        return sum(a / (1.0 + r) ** ((d - t0).days / 365.0) for d, a in zip(ds, amts))

    lo, hi = -0.9999, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < 1e-9:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid
    return (lo + hi) / 2.0


# ---------------------------------------------------------------- 回测
def simulate(df, cfg, strat):
    typ = strat.get('type', 'dca')
    base = float(strat.get('base', cfg['daily_amount']))
    sell_mode = strat.get('sell', 'optimal')
    confirm_n = int(cfg['confirm_shrink_days'])
    tp = float(cfg['take_profit'])
    pdd = float(cfg['peak_drawdown_sell'])
    core_frac = 1.0 / 3.0
    tp2 = float(cfg['second_take_profit'])
    tp3 = float(cfg['final_take_profit'])

    d = add_indicators(df, int(cfg['lookback_days']))
    shares = 0.0
    cost = 0.0
    cash_in = 0.0
    cash_out = 0.0
    peak_nav = 0.0
    trail_done = False
    core_sold = False
    cycles = 0
    sold_second = False
    sold_final = False
    shrink = 0
    prev_dd = None
    trades = []
    flows = []
    timeline = []

    def sell(q, nav, avg, tag, why, date):
        nonlocal shares, cost, cash_out
        q = max(0.0, min(q, shares))
        if q <= 1e-9:
            return
        cash_out += q * nav
        cost -= q * avg
        shares -= q
        flows.append((date, q * nav))
        trades.append((date, tag, round(q * nav, 2), round(nav, 4), why))
        if shares <= 1e-9:
            shares = 0.0
            cost = 0.0

    for _, row in d.iterrows():
        nav = float(row['nav'])
        dd = float(row['dd'])
        ma5 = float(row['ma5'])
        date = row['date']

        if prev_dd is not None and dd < prev_dd - 1e-9:
            shrink += 1
        else:
            shrink = 0
        prev_dd = dd

        # ---- 买入 ----
        buy = 0.0
        if typ == 'dca':
            _, extra = _tier_buy(dd, base, strat)
            confirm = shrink >= confirm_n and nav > ma5
            if confirm:
                extra += base
            buy = base + extra
        elif typ == 'pyr':  # 金字塔：每跌 step% 多加 add
            if dd >= float(strat['entry_dd']):
                k = int((dd - float(strat['entry_dd'])) // float(strat.get('step', 5)))
                buy = float(strat['base']) + float(strat.get('add', 100)) * k
            else:
                buy = 0.0
        else:  # zone：只在回撤达到建仓线后才买
            if dd >= float(strat['entry_dd']):
                buy = float(strat['deep_base']) if dd >= float(strat['deep_dd']) else float(strat['base'])
        mx = strat.get('max_extra')
        if mx is not None and buy > base + float(mx):
            buy = base + float(mx)
        cap = float(cfg.get('max_buy', 0) or 0)
        if cap > 0 and buy > cap:
            buy = cap
        bud = float(cfg.get('total_budget', 0) or 0)
        if bud > 0 and cash_in + buy > bud:
            buy = max(0.0, bud - cash_in)
        if buy > 0:
            shares += buy / nav
            cost += buy
            cash_in += buy
            flows.append((date, -buy))
            if buy > base + 1e-9:
                trades.append((date, 'BUY+', round(buy, 2), round(nav, 4), f'回撤{dd:.1f}%'))

        # ---- 卖出 ----
        if shares > 1e-9:
            avg = cost / shares
            R = (nav / avg - 1.0) * 100.0
            peak_nav = max(peak_nav, nav)
            peak_dd = (peak_nav - nav) / peak_nav * 100.0 if peak_nav > 0 else 0.0
            if R >= tp:
                if sell_mode == 'optimal':
                    if not trail_done and peak_dd >= pdd:
                        sell(shares * (1.0 - core_frac), nav, avg, 'SELL-2/3',
                             f'高点回撤{peak_dd:.1f}% R={R:.1f}% 留1/3底仓', date)
                        trail_done = True
                        peak_nav = nav
                    if not core_sold and R >= tp3:
                        sell(shares, nav, avg, 'SELL-ALL', f'R≥{tp3:.0f}% 清仓(含底仓)', date)
                        core_sold = True
                else:  # normal：普通止盈
                    if not sold_final and peak_dd >= pdd:
                        if cycles == 0:
                            sell(shares / 3.0, nav, avg, 'SELL-1/3', f'高点回撤{peak_dd:.1f}% R={R:.1f}%', date)
                            cycles = 1
                            peak_nav = nav
                        else:
                            sell(shares, nav, avg, 'SELL-ALL', f'第二次回撤止盈 R={R:.1f}%', date)
                            cycles = 2
                            sold_final = True
                    if not sold_second and R >= tp2 and shares > 1e-9:
                        sell(shares / 3.0, nav, avg, 'SELL-1/3', f'R≥{tp2:.0f}% 阶梯止盈', date)
                        sold_second = True
                    if not sold_final and R >= tp3 and shares > 1e-9:
                        sell(shares, nav, avg, 'SELL-ALL', f'R≥{tp3:.0f}% 清仓', date)
                        sold_final = True

        timeline.append((date, nav, shares))

    final_nav = float(d['nav'].iloc[-1])
    final_value = shares * final_nav + cash_out
    pnl = final_value - cash_in
    ret = pnl / cash_in * 100.0 if cash_in > 0 else 0.0
    return {
        'cash_in': cash_in, 'cash_out': cash_out, 'final_nav': final_nav,
        'shares': shares, 'final_value': final_value, 'pnl': pnl, 'ret': ret,
        'trades': trades, 'flows': flows, 'timeline': timeline,
    }


def simulate_dca(df, B):
    d = df.sort_values('date').reset_index(drop=True)
    shares = 0.0
    cash_in = 0.0
    flows = []
    timeline = []
    for _, row in d.iterrows():
        nav = float(row['nav'])
        shares += B / nav
        cash_in += B
        flows.append((row['date'], -B))
        timeline.append((row['date'], nav, shares))
    final_nav = float(d['nav'].iloc[-1])
    value = shares * final_nav
    pnl = value - cash_in
    return {'cash_in': cash_in, 'final_value': value, 'pnl': pnl,
            'ret': pnl / cash_in * 100.0 if cash_in > 0 else 0.0,
            'flows': flows, 'timeline': timeline}


# ---------------------------------------------------------------- 信号
def collect_signals(cfg, normal_only=False, phase='normal'):
    now = datetime.datetime.now()
    hold_now = load_holdings()
    codes = [f['code'] for f in cfg['funds']]
    try:
        quotes = fetch_quote(codes)
    except Exception:
        quotes = {}
    items = []
    for f in cfg['funds']:
        code, name = f['code'], f['name']
        strat = f.get('strategy') or {}
        try:
            df = load_fund(code, cfg)
        except Exception:
            items.append({'name': name, 'code': code, 'error': True, 'strat': strat_short(strat)})
            continue
        d = add_indicators(df, int(cfg['lookback_days']))
        ds = drawdown_stats(df)
        row = d.iloc[-1]
        nav = float(row['nav']); dd = float(row['dd'])
        ma5 = float(row['ma5']); high = float(row['high'])
        date = row['date']
        q = quotes.get(code) or {}
        nv = q.get('NAVCHGRT')
        chg = None
        if nv not in (None, '', '—'):
            try:
                chg = float(nv)
            except Exception:
                chg = None
        if chg is None:
            chg_txt = '—'
        else:
            arrow = ' ▲' if chg > 0 else (' ▼' if chg < 0 else '')
            chg_txt = f'{chg:+.2f}%{arrow}'
        # 盘中预估：优先跟踪指数实时涨跌，其次基金估值
        intraday = None
        trend = None
        idx = f.get('index')
        if idx:
            try:
                intraday = fetch_index(idx['secid'])
            except Exception:
                intraday = None
            try:
                trend = fetch_trend(idx['secid'])
            except Exception:
                trend = None
        if intraday is None:
            gszzl = q.get('GSZZL')
            if gszzl not in (None, ''):
                intraday = {'name': '基金估值', 'chg': float(gszzl)}

        # 预估模式：用盘中估算净值重算回撤
        dd_buy = dd
        if phase == 'estimate' and intraday:
            est_nav = nav * (1.0 + intraday['chg'] / 100.0)
            dd_buy = (high - est_nav) / high * 100.0 if high > 0 else dd

        if strat.get('type') == 'pyr':
            b = float(strat.get('base', 100))
            if dd_buy >= float(strat.get('entry_dd', 10)):
                k = int((dd_buy - float(strat.get('entry_dd'))) // float(strat.get('step', 5)))
                buy = b + float(strat.get('add', 100)) * k
            else:
                buy = 0.0
            base = b
            extra = max(0.0, buy - b)
            confirm = False
        elif strat.get('type') == 'zone':
            b = float(strat.get('base', 100))
            if dd_buy >= float(strat.get('entry_dd', 10)):
                buy = float(strat.get('deep_base', 200)) if dd_buy >= float(strat.get('deep_dd', 999)) else b
            else:
                buy = 0.0
            base = b
            extra = max(0.0, buy - b)
            confirm = False
        else:
            b = float(strat.get('base', cfg['daily_amount']))
            _, extra = _tier_buy(dd_buy, b, strat)
            tail = d['dd'].tail(int(cfg['confirm_shrink_days']) + 1).tolist()
            shrinking = all(tail[i] < tail[i - 1] for i in range(1, len(tail))) if len(tail) > 1 else False
            confirm = shrinking and nav > ma5
            if confirm:
                extra += b
            base = b
            buy = b + extra

        mx = strat.get('max_extra')
        if mx is not None and extra > float(mx):
            extra = float(mx)
            buy = base + extra

        if normal_only:
            extra = 0.0
            buy = base
        cap = float(cfg.get('max_buy', 0) or 0)
        if cap > 0 and buy > cap:
            buy = cap
            extra = max(0.0, buy - base)
        bud = float(cfg.get('total_budget', 0) or 0)
        if bud > 0:
            used = float((hold_now.get(code) or {}).get('cost', 0))
            if used + buy > bud:
                buy = max(0.0, bud - used)
                extra = max(0.0, buy - base)

        items.append({
            'name': name, 'code': code, 'error': False,
            'nav': nav, 'high': high, 'dd': dd, 'ma5_ok': nav >= ma5, 'date': date,
            'chg': chg, 'chg_txt': chg_txt, 'intraday': intraday, 'trend': trend,
            'base': base, 'extra': extra, 'buy': buy, 'confirm': confirm,
            'strat': strat_short(strat), 'ds': ds, 'sell_mode': strat.get('sell', 'optimal'),
            'phase': phase,
        })
    return {'now': now, 'items': items, 'normal_only': normal_only, 'phase': phase}


def _report_text(data):
    now = data['now']
    lines = [f'基金定投信号  {now:%Y-%m-%d %H:%M:%S}', '=' * 40,
             f'数据查询时间：{now:%Y-%m-%d %H:%M:%S}（数据源 天天基金）']
    if data.get('normal_only'):
        lines.append('（普通仓模式：只提示基线买入，14:30 再提示加仓）')
    for it in data['items']:
        if it.get('error'):
            lines.append(f'【{it["name"]}】数据获取失败')
            continue
        lines.append('')
        lines.append(f'【{it["name"]}】{it["code"]}  净值日 {it["date"]}')
        lines.append(f'  策略：{it["strat"]}')
        lines.append(f'  昨日净值涨跌 {it["chg_txt"]}')
        if it.get('intraday'):
            ia = it['intraday']
            ia_txt = f'{ia["chg"]:+.2f}%' + (' ▲' if ia['chg'] > 0 else (' ▼' if ia['chg'] < 0 else ''))
            lines.append(f'  盘中预估（{ia["name"]}） {ia_txt}')
        lines.append(f'  净值 {it["nav"]:.4f} | 90日高点 {it["high"]:.4f} | 近期回撤(90天) {it["dd"]:.1f}% | '
                     f'{"站上MA5" if it["ma5_ok"] else "跌破MA5"}')
        ds = it.get('ds') or {}
        if ds:
            rec = (f"（已修复，用时 {ds['max_recovered_days']} 天）"
                   if ds.get('max_recovered_days') is not None else '（尚未修复）')
            lines.append(f"  最大回撤 {ds['max_dd']:.1f}%（{ds['max_peak_date']} → {ds['max_trough_date']}）{rec}")
            lines.append(f"  距历史高点 {ds['cur_dd']:.1f}%｜状态：{ds['status']}｜距峰值 {ds['days_since_peak']} 天")
        ph = it.get('phase', 'normal')
        if it['buy'] <= 1e-9:
            lines.append('  → 未到建仓线，暂不买入')
        else:
            add_lbl = '确认加仓' if ph == 'confirm' else '预估加仓'
            lines.append(f'  → 普通仓位（确认）{it["base"]:.0f} 元 ｜ {add_lbl} {it["extra"]:.0f} 元 ｜ 合计 {it["buy"]:.0f} 元')
        if it['confirm']:
            lines.append('  ↑ 回撤连续收窄且站上 MA5：回撤结束确认，可多补一笔')
        hold = it.get('hold')
        if hold:
            lines.append(f'  【持仓】{hold["shares"]:.2f} 份 · 成本 {hold["avg"]:.4f} · 持仓总额 {hold["value"]:.0f} 元 · '
                         f'持有收益 {hold["profit"]:+.2f} 元（{hold["ret"]:+.1f}%）· 高点回撤 {hold["peak_dd"]:.1f}%')
            lines.append(f'  → 卖出建议：{hold["sell"]}')
        else:
            lines.append('  【持仓】未记录（用 monitor.py buy <代码> <金额> 记录买入）')
    return '\n'.join(lines)


def build_daily_report(cfg, normal_only=False):
    data = collect_signals(cfg, normal_only=normal_only)
    holding_info(data['items'], cfg)
    return _report_text(data)


# ---------------------------------------------------------------- 图片
def _font(paths, size):
    for fp in paths:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


class _SD:
    """把逻辑坐标（900 宽）映射到高分辨率画布。"""
    def __init__(self, dr, sc):
        self._dr = dr
        self.sc = sc

    def text(self, xy, *a, **kw):
        return self._dr.text((xy[0] * self.sc, xy[1] * self.sc), *a, **kw)

    def textlength(self, t, *a, **kw):
        return self._dr.textlength(t, *a, **kw) / self.sc

    def rectangle(self, xy, *a, **kw):
        return self._dr.rectangle([v * self.sc for v in xy], *a, **kw)

    def rounded_rectangle(self, xy, radius=0, *a, **kw):
        kw['radius'] = int(radius * self.sc)
        return self._dr.rounded_rectangle([v * self.sc for v in xy], *a, **kw)

    def line(self, xy, *a, **kw):
        pts = [(p[0] * self.sc, p[1] * self.sc) for p in xy]
        kw['width'] = max(1, int(kw.get('width', 1) * self.sc))
        return self._dr.line(pts, *a, **kw)

    def polygon(self, xy, *a, **kw):
        return self._dr.polygon([(p[0] * self.sc, p[1] * self.sc) for p in xy], *a, **kw)

    def pieslice(self, xy, start, end, *a, **kw):
        return self._dr.pieslice([v * self.sc for v in xy], start, end, *a, **kw)


def calc_daily_profits(cfg, holdings):
    """按当前持仓 × 历史净值日变动，估算每交易日组合收益 {date: {code: profit}}。"""
    out = {}
    for f in cfg['funds']:
        code = f['code']
        sh = float((holdings.get(code) or {}).get('shares', 0) or 0)
        if sh <= 0:
            continue
        df = load_fund(code, cfg)
        if df is None or df.empty:
            continue
        df = df.sort_values('date')
        dates = df['date'].astype(str).tolist()
        navs = df['nav'].astype(float).tolist()
        for i in range(1, len(dates)):
            out.setdefault(dates[i], {})[code] = sh * (navs[i] - navs[i - 1])
    return out


def render_report_image(data, out_path, dark=False, extra=False, pie=False, cfg=None):
    if Image is None:
        return None
    SC = 2
    REG = 'C:/Windows/Fonts/msyh.ttc'
    BOLD = 'C:/Windows/Fonts/msyhbd.ttc'

    def F(paths, size):
        return _font(paths, size * SC)

    f_title = F([BOLD, REG], 30)
    f_sub = F([REG], 13)
    f_name = F([BOLD, REG], 19)
    f_code = F([REG], 12)
    f_body = F([REG], 14)
    f_small = F([REG], 12)
    f_tiny = F([REG], 11)
    f_chg = F([BOLD, REG], 15)
    f_yday = F([REG], 14)
    f_buy = F([BOLD, REG], 15)
    f_dd = F([BOLD, REG], 16)

    if dark:
        C_BG = '#0E1520'; C_CARD = '#161F2C'; C_BD = '#263446'
        C_INK = '#E8F1FA'; C_BODY = '#B8C8DA'; C_MUT = '#7E92A8'
        C_BLUE = '#5B9BF0'; C_GREEN = '#3DBE86'; C_RED = '#E5675F'
        C_GBG = '#12301F'; C_GBD = '#2A5C3C'; C_GRAY = '#1C2736'
        FILL_UP = '#3A1E1E'; FILL_DOWN = '#12301F'; BASE_LINE = '#5A6A7E'
        C_RBG = '#3A1E1E'
    else:
        C_BG = '#ECEFF4'; C_CARD = '#FFFFFF'; C_BD = '#D8E1EC'
        C_INK = '#10263D'; C_BODY = '#44586F'; C_MUT = '#7A8A9E'
        C_BLUE = '#2F6FD0'; C_GREEN = '#2F8F62'; C_RED = '#C0392B'
        C_GBG = '#E6F7EF'; C_GBD = '#C4E2D3'; C_GRAY = '#F3F6FA'
        FILL_UP = '#FDE8E8'; FILL_DOWN = '#E6F7EF'; BASE_LINE = '#9AA8B8'
        C_RBG = '#FDE8E8'

    W = 900
    M = 28
    HEAD_H = 118
    CARD_H = 262
    GAP = 14
    FOOT_H = 54
    items = data['items']
    n = len(items)
    EXTRA_H = (930 if pie else 700) if extra else 0
    H = M + HEAD_H + GAP + n * (CARD_H + GAP) + (EXTRA_H + GAP if extra else 0) + FOOT_H + M
    img = Image.new('RGB', (W * SC, H * SC), C_BG)
    dr = _SD(ImageDraw.Draw(img), SC)

    def rr(xy, r, fill, outline=None, width=1):
        dr.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)

    def segs(x, yy, items):
        for t, fnt, col in items:
            dr.text((x, yy), t, font=fnt, fill=col, anchor='lm')
            x += dr.textlength(t, font=fnt)
        return x

    def spark(x, y0, w, h, points, prev_close):
        if not points or len(points) < 2:
            return
        prices = [p for _, p in points]
        lo, hi = min(prices), max(prices)
        if prev_close:
            lo, hi = min(lo, prev_close), max(hi, prev_close)
        span = (hi - lo) or 1.0
        t0 = points[0][0].replace(hour=9, minute=30, second=0, microsecond=0)
        total = 330.0

        def xf(dt):
            m = (dt - t0).total_seconds() / 60.0
            m = max(0.0, min(total, m))
            return x + m / total * w

        xy = [(xf(dt), y0 + h - (p - lo) / span * h) for dt, p in points]
        last_x = xy[-1][0]
        base = prev_close if prev_close else prices[0]
        up = prices[-1] >= base
        col = C_RED if up else C_GREEN
        fill_col = FILL_UP if up else FILL_DOWN
        poly = xy + [(last_x, y0 + h), (x, y0 + h)]
        dr.polygon(poly, fill=fill_col)
        if prev_close:
            by = y0 + h - (prev_close - lo) / span * h
            for dx in range(0, int(w), 6):
                dr.line([(x + dx, by), (x + min(dx + 3, w), by)], fill=BASE_LINE, width=1)
        dr.line(xy, fill=col, width=2)
        for label, mm in (('09:30', 0), ('11:30', 120), ('15:00', 330)):
            lx = x + mm / total * w
            dr.text((lx, y0 + h + 3), label, font=f_tiny, fill=C_MUT,
                    anchor=('lt' if mm == 0 else ('rt' if mm == total else 'mt')))

    y = M
    rr((M, y, W - M, y + HEAD_H), 16, C_CARD, C_BD, 1)
    dr.rectangle((M, y + 18, M + 6, y + HEAD_H - 18), fill=C_BLUE)
    dr.text((M + 24, y + 18), '基金定投信号', font=f_title, fill=C_INK)
    dr.text((M + 24, y + 62), f"数据查询时间 {data['now']:%Y-%m-%d %H:%M:%S}  ·  数据源 天天基金",
            font=f_sub, fill=C_MUT)
    total_buy = sum(it['buy'] for it in items if not it.get('error'))
    sm = f'今日建议买入合计 {total_buy:,.0f} 元'
    tw = dr.textlength(sm, font=f_buy)
    dr.text((W - M - 24 - tw, y + 34), sm, font=f_buy, fill=C_GREEN)
    total_profit = sum((it.get('hold') or {}).get('profit', 0) for it in items)
    pm = f'持有总收益 {total_profit:+.2f} 元'
    pw = dr.textlength(pm, font=f_buy)
    dr.text((W - M - 24 - pw, y + 66), pm, font=f_buy,
            fill=(C_RED if total_profit >= 0 else C_GREEN))

    y = M + HEAD_H + GAP
    for it in items:
        rr((M, y, W - M, y + CARD_H), 12, C_CARD, C_BD, 1)
        if it.get('error'):
            dr.text((M + 22, y + 20), f'{it["name"]} {it["code"]}  数据获取失败', font=f_name, fill=C_RED)
            y += CARD_H + GAP
            continue
        dr.text((M + 22, y + 16), it['name'], font=f_name, fill=C_INK)
        nw = dr.textlength(it['name'], font=f_name)
        dr.text((M + 22 + nw + 10, y + 22), it['code'], font=f_code, fill=C_MUT)
        if it.get('intraday'):
            ia = it['intraday']
            top_txt = f'{ia["chg"]:+.2f}%' + (' ▲' if ia['chg'] > 0 else (' ▼' if ia['chg'] < 0 else ''))
            top_lbl = f'盘中·{ia["name"]}'
            top_col = C_RED if ia['chg'] >= 0 else C_GREEN
            cw = dr.textlength(top_txt, font=f_chg)
            dr.text((W - M - 22 - cw, y + 12), top_txt, font=f_chg, fill=top_col)
            dr.text((W - M - 22 - cw - dr.textlength(top_lbl, font=f_small) - 8, y + 16), top_lbl, font=f_small, fill=C_MUT)
            ycol = C_RED if (it['chg'] or 0) >= 0 else C_GREEN
            dr.text((W - M - 22, y + 31), '昨日 ' + it['chg_txt'],
                    font=f_yday, fill=(ycol if it['chg'] is not None else C_MUT), anchor='rt')
        else:
            chg_col = C_MUT
            if it['chg'] is not None:
                chg_col = C_RED if it['chg'] >= 0 else C_GREEN
            cw = dr.textlength(it['chg_txt'], font=f_chg)
            dr.text((W - M - 22 - cw, y + 14), it['chg_txt'], font=f_chg, fill=chg_col)
            dr.text((W - M - 22 - cw - dr.textlength('昨日净值', font=f_small) - 8, y + 18), '昨日净值', font=f_small, fill=C_MUT)

        dd_col = C_RED if it['dd'] >= 20 else ('#D97706' if it['dd'] >= 10 else C_MUT)
        dr.text((M + 22, y + 50), f"净值 {it['nav']:.4f}", font=f_body, fill=C_BODY)
        dr.text((M + 170, y + 50), f"90日高点 {it['high']:.4f}", font=f_body, fill=C_BODY)
        dr.text((M + 360, y + 50), f"近期回撤(90天) {it['dd']:.1f}%", font=f_body, fill=dd_col)

        ds = it.get('ds') or {}
        if ds:
            strip_y = y + 70
            rr((M + 22, strip_y, W - M - 22, strip_y + 58), 10, C_GRAY, C_BD, 1)
            dd2_col = C_RED if ds['cur_dd'] >= 20 else ('#D97706' if ds['cur_dd'] >= 10 else C_MUT)
            cy = strip_y + 24
            x = M + 36
            x = segs(x, cy, [('最大回撤 ', f_small, C_MUT), (f"{ds['max_dd']:.1f}%", f_dd, C_RED)])
            x = segs(x + 28, cy, [('距历史高点 ', f_small, C_MUT), (f"{ds['cur_dd']:.1f}%", f_dd, dd2_col)])
            stat_txt = f"{ds['status']} · 距峰值 {ds['days_since_peak']} 天"
            dr.text((W - M - 36, cy), stat_txt, font=f_small, fill=C_MUT, anchor='rm')
            rec = (f"已修复 {ds['max_recovered_days']} 天"
                   if ds.get('max_recovered_days') is not None else '尚未修复')
            dr.text((M + 36, strip_y + 38),
                    f"峰值 {ds['max_peak_date']} → 谷 {ds['max_trough_date']}（{rec}）",
                    font=f_tiny, fill=C_MUT)

        dr.text((M + 22, y + 134), '策略：' + it['strat'], font=f_tiny, fill=C_MUT)
        if it.get('trend'):
            ia = it.get('intraday') or {}
            chg_v = ia.get('chg') or 0
            dr.text((W - M - 22 - 200, y + 132),
                    f"{ia.get('name', '')} {chg_v:+.2f}%", font=f_tiny,
                    fill=(C_RED if chg_v >= 0 else C_GREEN))
            spark(W - M - 22 - 200, y + 143, 200, 28, it['trend'], ia.get('prev'))

        px, py = M + 22, y + 158
        ma5_txt = '站上 MA5' if it['ma5_ok'] else '跌破 MA5'
        ma5_col = C_GREEN if it['ma5_ok'] else C_MUT
        ma5_bg = C_GBG if it['ma5_ok'] else C_GRAY
        pw = dr.textlength(ma5_txt, font=f_small) + 24
        rr((px, py, px + pw, py + 24), 8, ma5_bg, (C_GBD if it['ma5_ok'] else C_BD), 1)
        dr.text((px + 12, py + 4), ma5_txt, font=f_small, fill=ma5_col)
        if it['confirm']:
            tx = px + pw + 10
            ctxt = '回撤结束确认'
            tw2 = dr.textlength(ctxt, font=f_small) + 24
            rr((tx, py, tx + tw2, py + 24), 8, C_GBG, C_GBD, 1)
            dr.text((tx + 12, py + 4), ctxt, font=f_small, fill=C_GREEN)

        by = y + 188
        ph = it.get('phase', 'normal')
        add_lbl = '确认加仓' if ph == 'confirm' else '预估加仓'
        if it['buy'] <= 1e-9:
            txt = '未到建仓线，暂不买入'
            rr((M + 22, by, W - M - 22, by + 32), 8, C_GRAY, C_BD, 1)
            dr.text((M + 34, by + 7), txt, font=f_buy, fill=C_BODY)
        else:
            txt = f"普通仓 {it['base']:.0f} ｜ {add_lbl} {it['extra']:.0f} ｜ 合计 {it['buy']:.0f} 元"
            rr((M + 22, by, W - M - 22, by + 32), 8, C_GBG, C_GBD, 1)
            dr.text((M + 34, by + 7), txt, font=f_buy, fill=C_GREEN)
        hold = it.get('hold')
        hy = y + 226
        if hold:
            ret_col = C_RED if hold['ret'] >= 0 else C_GREEN
            dr.text((M + 22, hy),
                    f"持仓 {hold['shares']:.1f} 份 ｜ 成本 {hold['avg']:.4f} ｜ 总额 {hold['value']:.0f} 元 ｜ "
                    f"收益 {hold['profit']:+.2f} 元（{hold['ret']:+.1f}%）→ {hold['sell']}",
                    font=f_tiny, fill=ret_col)
        else:
            dr.text((M + 22, hy), '持仓：未记录（monitor.py buy <代码> <金额> 记录）', font=f_tiny, fill=C_MUT)
        y += CARD_H + GAP

    if extra:
        import calendar as _cal
        yy, mm = data['now'].year, data['now'].month
        prof = calc_daily_profits(cfg, load_holdings()) if cfg else {}
        dr.text((M + 22, y + 12), f'每日收益日历  {yy}年{mm}月', font=f_name, fill=C_INK)
        cellw = (W - 2 * M - 44) / 7
        cellh = 100
        gy = y + 50
        for i, wd_ in enumerate(['日', '一', '二', '三', '四', '五', '六']):
            dr.text((M + 22 + i * cellw + cellw / 2, gy - 6), wd_, font=f_small, fill=C_MUT, anchor='mb')
        for wk in _cal.Calendar(firstweekday=6).monthdatescalendar(yy, mm):
            for i, d in enumerate(wk):
                if d.month != mm:
                    continue
                cx = M + 22 + i * cellw
                dd = d.isoformat()
                val = sum(prof.get(dd, {}).values())
                bg = C_GRAY
                if abs(val) > 0.005:
                    bg = C_GBG if val >= 0 else C_RBG
                is_today = (d == data['now'].date())
                border = C_BLUE if is_today else C_BD
                dr.rounded_rectangle((cx + 4, gy + 4, cx + cellw - 4, gy + cellh - 4),
                                     radius=12, fill=bg, outline=border, width=(2 if is_today else 1))
                dr.text((cx + 14, gy + 12), str(d.day), font=f_small,
                        fill=(C_BLUE if is_today else C_MUT))
                if abs(val) > 0.005:
                    dr.text((cx + cellw / 2, gy + cellh / 2 + 26), f'{val:+.2f}', font=f_body,
                            fill=(C_RED if val >= 0 else C_GREEN), anchor='ms')
            gy += cellh
        if pie:
            py = gy + 30
            dr.text((M + 22, py), '今日收益构成', font=f_name, fill=C_INK)
            last_day = max(prof) if prof else None
            name_by_code = {it['code']: it['name'] for it in items}
            if last_day and prof.get(last_day):
                vals = prof[last_day]
                tot = sum(abs(v) for v in vals.values()) or 1
                cx0 = M + 22 + 90
                cy0 = py + 100
                r = 60
                if dark:
                    cols = ['#5B9BF0', '#7FB2F5', '#9CC6F9', '#B8D8FC', '#6AA9E9', '#3D7BD9']
                else:
                    cols = ['#2F6FD0', '#4A90D9', '#6AA9E9', '#8CC0F0', '#B3D6F7', '#5B8FF9']
                a = -90
                for j, (code, v) in enumerate(vals.items()):
                    span = 360 * abs(v) / tot
                    dr.pieslice((cx0 - r, cy0 - r, cx0 + r, cy0 + r), a, a + span, fill=cols[j % len(cols)])
                    a += span
                lx = cx0 + r + 50
                ly = cy0 - len(vals) * 14
                for j, (code, v) in enumerate(vals.items()):
                    dr.rectangle((lx, ly + j * 26, lx + 16, ly + j * 26 + 16), fill=cols[j % len(cols)])
                    dr.text((lx + 24, ly + j * 26), f'{name_by_code.get(code, code)} {code}  {v:+.2f} 元',
                            font=f_small, fill=C_BODY)
            y = py + 210
        else:
            y = gy + 20

    rr((M, y, W - M, y + FOOT_H), 12, C_CARD, C_BD, 1)
    dr.text((M + 22, y + 16), '止盈：普通=15%起高点回撤5%卖1/3，再触发清仓；最优=卖2/3留1/3底仓，50%清底仓。',
            font=f_tiny, fill=C_MUT)

    img.save(out_path, 'PNG', dpi=(600, 600))
    return out_path


def _make_pie_png(vals, out_path, size_px, dark=False):
    """用 matplotlib 画甜甜圈饼图：内部用日历背景色，外部灰黑描边。"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    sizes = [abs(v) for v in vals.values()]
    if dark:
        REDS = ['#C9554D', '#D46E67', '#DF8781', '#E9A099']
        GREENS = ['#2E9E6E', '#3DAB7C', '#4CB88A', '#5FC599']
        edge = '#7A7A7A'
    else:
        REDS = ['#A93226', '#B8483C', '#C75F53', '#D47A6F']
        GREENS = ['#1E6B45', '#2A7A52', '#36895F', '#4A9C73']
        edge = '#555555'
    colors = []
    nr = ng = 0
    for v in vals.values():
        if v >= 0:
            colors.append(REDS[nr % len(REDS)]); nr += 1
        else:
            colors.append(GREENS[ng % len(GREENS)]); ng += 1
    fig, ax = plt.subplots(figsize=(size_px / 100.0, size_px / 100.0), dpi=100)
    fig.patch.set_alpha(0)
    ax.pie(sizes, colors=colors, startangle=90, counterclock=False,
           wedgeprops={'width': 0.45, 'edgecolor': edge, 'linewidth': 1.5},
           shadow=True)
    ax.set_aspect('equal')
    ax.axis('off')
    plt.subplots_adjust(0, 0, 1, 1)
    fig.savefig(out_path, transparent=True, dpi=100)
    plt.close(fig)
    return out_path


def render_dashboard_image(data, out_path, dark=False, cfg=None):
    """只渲染 每日收益日历 + 今日收益饼图（不含基金信号卡片）。"""
    if Image is None:
        return None
    SC = 2
    REG = 'C:/Windows/Fonts/msyh.ttc'
    BOLD = 'C:/Windows/Fonts/msyhbd.ttc'

    def F(paths, size):
        return _font(paths, size * SC)

    f_title = F([BOLD, REG], 28)
    f_name = F([BOLD, REG], 18)
    f_body = F([REG], 14)
    f_small = F([REG], 12)
    f_date = F([REG], 17)
    f_cell = F([BOLD, REG], 20)
    f_legend = F([BOLD, REG], 16)
    if dark:
        C_BG = '#0E1520'; C_CARD = '#161F2C'; C_BD = '#263446'
        C_INK = '#E8F1FA'; C_BODY = '#B8C8DA'; C_MUT = '#7E92A8'
        C_BLUE = '#5B9BF0'; C_GREEN = '#3DBE86'; C_RED = '#E5675F'
        C_GBG = '#12301F'; C_RBG = '#3A1E1E'; C_GRAY = '#1C2736'
        COLS = ['#5B9BF0', '#7FB2F5', '#9CC6F9', '#B8D8FC', '#6AA9E9', '#3D7BD9']
        BG_UP = '#3A1E1E'; TXT_UP = '#F08A8A'; BG_DOWN = '#12301F'; TXT_DOWN = '#6AD9A8'
    else:
        C_BG = '#ECEFF4'; C_CARD = '#FFFFFF'; C_BD = '#D8E1EC'
        C_INK = '#10263D'; C_BODY = '#44586F'; C_MUT = '#7A8A9E'
        C_BLUE = '#2F6FD0'; C_GREEN = '#2F8F62'; C_RED = '#C0392B'
        C_GBG = '#E6F7EF'; C_RBG = '#FDE8E8'; C_GRAY = '#F3F6FA'
        COLS = ['#2F6FD0', '#4A90D9', '#6AA9E9', '#8CC0F0', '#B3D6F7', '#5B8FF9']
        BG_UP = '#FDECEA'; TXT_UP = '#C0392B'; BG_DOWN = '#E8F7F0'; TXT_DOWN = '#1E7A4E'
    W = 900
    M = 28
    cellw = (W - 2 * M - 44) / 7
    cellh = 100
    import calendar as _cal
    yy, mm = data['now'].year, data['now'].month
    weeks = _cal.Calendar(firstweekday=6).monthdatescalendar(yy, mm)
    cal_h = 10 + len(weeks) * cellh
    H = M + 100 + cal_h + 330 + M
    img = Image.new('RGB', (W * SC, H * SC), C_BG)
    dr = _SD(ImageDraw.Draw(img), SC)
    dr.text((M, 26), '每日收益日历', font=f_title, fill=C_INK)
    dr.text((M, 66), f"{yy}年{mm}月 · 数据查询 {data['now']:%Y-%m-%d %H:%M:%S}", font=f_small, fill=C_MUT)
    prof = calc_daily_profits(cfg, load_holdings()) if cfg else {}
    gy = M + 100
    for i, wd_ in enumerate(['日', '一', '二', '三', '四', '五', '六']):
        dr.text((M + 22 + i * cellw + cellw / 2, gy - 4), wd_, font=f_small, fill=C_MUT, anchor='mb')
    gy += 10
    for wk in weeks:
        for i, d in enumerate(wk):
            if d.month != mm:
                continue
            cx = M + 22 + i * cellw
            dd = d.isoformat()
            val = sum(prof[dd].values()) if (dd in prof and dd >= '2026-11-23') else None
            bg = C_GRAY
            txt_col = C_MUT
            if val is not None and abs(val) > 0.005:
                if val >= 0:
                    bg, txt_col = BG_UP, TXT_UP
                else:
                    bg, txt_col = BG_DOWN, TXT_DOWN
            is_today = (d == data['now'].date())
            border = C_BLUE if is_today else C_BD
            dr.rounded_rectangle((cx + 4, gy + 4, cx + cellw - 4, gy + cellh - 4),
                                 radius=12, fill=bg, outline=border, width=(2 if is_today else 1))
            dr.text((cx + cellw / 2, gy + 12), str(d.day), font=f_date,
                    fill=(C_BLUE if is_today else C_MUT), anchor='mt')
            if val is not None and abs(val) > 0.005:
                dr.text((cx + cellw / 2, gy + cellh / 2 + 12), f'{val:+.2f}', font=f_cell,
                        fill=txt_col, anchor='mm')
        gy += cellh
    py = gy + 30
    last_day = max(prof) if prof else None
    tag = f'（{last_day[5:]}）' if last_day else ''
    dr.text((M + 22, py), f'今日收益构成{tag}', font=f_name, fill=C_INK)
    name_by_code = {it['code']: it['name'] for it in data['items']}
    if last_day and prof.get(last_day):
        import math
        vals = prof[last_day]
        REDS = ['#C0392B', '#D26A5E', '#E0938A', '#EDBCB6']
        GREENS = ['#1E7A4E', '#3E9A6E', '#6BB893', '#9DD2B8']
        if dark:
            REDS = ['#C9554D', '#D46E67', '#DF8781', '#E9A099']
            GREENS = ['#2E9E6E', '#3DAB7C', '#4CB88A', '#5FC599']
        else:
            REDS = ['#A93226', '#B8483C', '#C75F53', '#D47A6F']
            GREENS = ['#1E6B45', '#2A7A52', '#36895F', '#4A9C73']
        slice_cols = []
        nr = ng = 0
        for code, v in vals.items():
            if v >= 0:
                slice_cols.append(REDS[nr % len(REDS)]); nr += 1
            else:
                slice_cols.append(GREENS[ng % len(GREENS)]); ng += 1
        cx0 = M + 22 + 100
        cy0 = py + 120
        r = 68
        try:
            pie_png = os.path.join(CACHE_DIR, 'pie_tmp.png')
            size_px = int(2.5 * r * SC)
            _make_pie_png(vals, pie_png, size_px, dark=dark)
            pie_img = Image.open(pie_png).convert('RGBA')
            pie_img = pie_img.resize((size_px, size_px), Image.LANCZOS)
            img.paste(pie_img, (int((cx0 - r * 1.25) * SC), int((cy0 - r * 1.25) * SC)), pie_img)
            dr = _SD(ImageDraw.Draw(img), SC)
        except Exception:
            a = -90
            for j, (code, v) in enumerate(vals.items()):
                span = 360 * abs(v) / tot
                dr.pieslice((cx0 - r, cy0 - r, cx0 + r, cy0 + r), a, a + span, fill=slice_cols[j])
                a += span
        lx = cx0 + r + 40
        ly = cy0 - len(vals) * 14
        for j, (code, v) in enumerate(vals.items()):
            dr.rectangle((lx, ly + j * 28, lx + 16, ly + j * 28 + 16), fill=slice_cols[j])
            dr.text((lx + 24, ly + j * 28), f'{name_by_code.get(code, code)}  {v:+.2f}',
                    font=f_legend, fill=(C_RED if v >= 0 else C_GREEN))
    img.save(out_path, 'PNG', dpi=(600, 600))
    return out_path


# ---------------------------------------------------------------- 通知
def notify(msg, cfg, image_path=None, dark_image_path=None, images=None):
    out = []
    if images is None:
        images = []
        if dark_image_path and os.path.exists(dark_image_path):
            images.append((dark_image_path, '深色模式'))
        if image_path and os.path.exists(image_path):
            images.append((image_path, '浅色模式'))
    webhook = (cfg.get('wechat_webhook') or '').strip()
    if webhook:
        try:
            data = json.dumps({'msgtype': 'text', 'text': {'content': msg}},
                              ensure_ascii=False).encode('utf-8')
            req = urllib.request.Request(webhook, data=data,
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=15) as r:
                out.append('wechat:' + r.read().decode('utf-8', 'ignore')[:120])
        except Exception as e:
            out.append(f'wechat FAIL: {e}')
    host = (cfg.get('smtp_host') or '').strip()
    if host and cfg.get('smtp_user') and cfg.get('smtp_pass') and cfg.get('smtp_to'):
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.image import MIMEImage
            from email.header import Header
            date_s = datetime.date.today().isoformat()
            imgs = [(p, f'fs_{i}', lbl) for i, (p, lbl) in enumerate(images)
                    if p and os.path.exists(p)]
            if imgs:
                m = MIMEMultipart('related')
                m['Subject'] = Header('基金信号 ' + date_s, 'utf-8')
                m['From'] = cfg['smtp_user']
                m['To'] = cfg['smtp_to']
                m.attach(MIMEText('基金定投信号见下图。', 'plain', 'utf-8'))
                html = '<html><body style="margin:0;padding:0;font-family:Microsoft YaHei,sans-serif">'
                for _, cid, lbl in imgs:
                    html += f'<p style="color:#333">{lbl}</p><img src="cid:{cid}" style="max-width:100%">'
                html += '</body></html>'
                m.attach(MIMEText(html, 'html', 'utf-8'))
                for p, cid, _ in imgs:
                    with open(p, 'rb') as f:
                        img = MIMEImage(f.read(), _subtype='png')
                    img.add_header('Content-ID', '<%s>' % cid)
                    img.add_header('Content-Disposition', 'inline', filename='fund_%s.png' % cid)
                    m.attach(img)
            else:
                m = MIMEText(msg, 'plain', 'utf-8')
                m['Subject'] = Header('基金信号 ' + date_s, 'utf-8')
                m['From'] = cfg['smtp_user']
                m['To'] = cfg['smtp_to']
            port = int(cfg.get('smtp_port', 465))
            with smtplib.SMTP_SSL(host, port, timeout=25) as s:
                s.login(cfg['smtp_user'], cfg['smtp_pass'])
                s.sendmail(cfg['smtp_user'], [cfg['smtp_to']], m.as_string())
            out.append('email: sent' + (' (image)' if image_path else ''))
        except Exception as e:
            out.append(f'email FAIL: {e}')
    if not out:
        out.append('（未配置 webhook/邮箱，仅本地输出）')
    return out


# ---------------------------------------------------------------- 输出
def _mdd(timeline, flows, y):
    """Modified Dietz 分年收益率（%）。首/末部分年按实际数据区间计算（不虚增）。"""
    ystart = f'{y}-01-01'
    yend = f'{y}-12-31'
    this = [t for t in timeline if ystart <= t[0] <= yend]
    if not this:
        return None
    p_start = this[0][0]
    p_end = this[-1][0]
    prev = [t for t in timeline if t[0] < p_start]
    nav0, sh0 = (float(prev[-1][1]), float(prev[-1][2])) if prev else (0.0, 0.0)
    V_start = sh0 * nav0
    V_end = float(this[-1][2]) * float(this[-1][1])
    f_y = [(dt, a) for dt, a in flows if p_start <= dt <= p_end]
    F = sum(-a for _, a in f_y)
    d0 = datetime.date.fromisoformat(p_start)
    d1 = datetime.date.fromisoformat(p_end)
    days = max(1, (d1 - d0).days + 1)
    w = 0.0
    for dt, a in f_y:
        dd_ = datetime.date.fromisoformat(dt)
        w += (-a) * max(0.0, (d1 - dd_).days) / days
    denom = V_start + w
    if abs(denom) < 1e-9:
        return None
    return (V_end - V_start - F) / denom * 100.0


def cmd_backtest(cfg):
    years = int(cfg.get('backtest_years', 5))
    start = (datetime.date.today() - datetime.timedelta(days=365 * years)).isoformat()
    print(f'回测区间: {start} 起  (回撤基准 {cfg["lookback_days"]} 日, 每基金独立策略)')
    print('=' * 80)
    for f in cfg['funds']:
        code, name, strat = f['code'], f['name'], f.get('strategy') or {}
        try:
            df = load_fund(code, cfg)
        except Exception as e:
            print(f'【{name}】数据失败: {e}')
            continue
        d = df[df['date'] >= start]
        if len(d) < 30:
            print(f'【{name}】区间数据不足')
            continue
        r = simulate(d, cfg, strat)
        b = simulate_dca(d, cfg['daily_amount'])
        sells = [t for t in r['trades'] if t[1].startswith('SELL')]
        print(f'\n【{name}】{code}  [{strat_short(strat)}]')
        print(f'  策略: 投入 {r["cash_in"]:.0f} 元, 期末市值 {r["final_value"]:.0f} 元, '
              f'收益 {r["pnl"]:+.0f} 元 ({r["ret"]:+.1f}%)')
        print(f'  纯定投: 投入 {b["cash_in"]:.0f} 元, 期末市值 {b["final_value"]:.0f} 元, '
              f'收益 {b["pnl"]:+.0f} 元 ({b["ret"]:+.1f}%)')
        for t in sells:
            print(f'    {t[0]} {t[1]}  {t[2]:.0f}元 @{t[3]}  {t[4]}')
    print('\n' + '=' * 80)


def _twr(timeline, flows, y):
    """时间加权收益率（排除现金流影响），分年可比、不会被投入节奏放大。"""
    ty = [t for t in timeline if t[0][:4] == y]
    if len(ty) < 2:
        return None
    if max(float(t[2]) for t in ty) <= 1e-9:
        return None  # 全年无仓位
    cf = {}
    for dt, a in flows:
        cf[dt] = cf.get(dt, 0.0) - a  # 买入为负 -> 流入为正
    prev = [t for t in timeline if t[0] < ty[0][0]]
    prev_v = (float(prev[-1][2]) * float(prev[-1][1])) if prev else None
    prod = 1.0
    for (dt, nav, sh) in ty:
        v = float(sh) * float(nav)
        f = cf.get(dt, 0.0)
        if prev_v is not None and prev_v > 1e-9:
            prod *= (1.0 + (v - prev_v - f) / prev_v)
        prev_v = v
    return (prod - 1.0) * 100.0


def cmd_yearly(cfg):
    years = int(cfg.get('backtest_years', 5))
    start = (datetime.date.today() - datetime.timedelta(days=365 * years)).isoformat()
    print(f'分年收益（{start} 起，时间加权 TWR）')
    print('=' * 80)
    for f in cfg['funds']:
        code, name, strat = f['code'], f['name'], f.get('strategy') or {}
        try:
            df = load_fund(code, cfg)
        except Exception as e:
            print(f'【{name}】数据失败: {e}')
            continue
        d = df[df['date'] >= start]
        if len(d) < 30:
            print(f'【{name}】数据不足')
            continue
        r = simulate(d, cfg, strat)
        b = simulate_dca(d, cfg['daily_amount'])
        final_date = r['timeline'][-1][0]
        final_nav = r['final_nav']
        ov_s = xirr(r['flows'] + [(final_date, r['shares'] * final_nav)])
        ov_b = xirr(b['flows'] + [(final_date, b['timeline'][-1][2] * final_nav)])
        fund_all = (float(d['nav'].iloc[-1]) / float(d['nav'].iloc[0]) - 1.0) * 100.0
        print(f'\n【{name}】{code}  [{strat_short(strat)}]')
        print(f'  区间累计: 策略 {r["ret"]:+.1f}% | 纯定投 {b["ret"]:+.1f}% | 基金本身 {fund_all:+.1f}%')
        if ov_s is not None and ov_b is not None:
            print(f'  区间年化(IRR): 策略 {ov_s*100:+.1f}% | 纯定投 {ov_b*100:+.1f}%')
        for y in sorted(set(t[0][:4] for t in r['timeline'])):
            ty = [t for t in r['timeline'] if t[0][:4] == y]
            if not ty:
                continue
            days = (datetime.date.fromisoformat(ty[-1][0]) -
                    datetime.date.fromisoformat(ty[0][0])).days + 1
            tw = _twr(r['timeline'], r['flows'], y)
            prev = [t for t in r['timeline'] if t[0] < y + '-01-01']
            nav_start = float(prev[-1][1]) if prev else float(ty[0][1])
            nav_end = float(ty[-1][1])
            fund_y = (nav_end / nav_start - 1.0) * 100.0
            tag = '' if days >= 360 else '（部分年）'
            ss = f'{tw:+.1f}%' if tw is not None else '—'
            print(f'  {y}: 策略TWR {ss}  基金本身 {fund_y:+.1f}%{tag}')
    print('\n' + '=' * 80)


def cmd_fetch(cfg):
    os.makedirs(CACHE_DIR, exist_ok=True)
    for f in cfg['funds']:
        try:
            df = load_fund(f['code'], cfg, force=True)
            print(f'{f["code"]} {f["name"]}: {len(df)} 条 [{df["date"].iloc[0]} ~ {df["date"].iloc[-1]}]')
        except Exception as e:
            print(f'{f["code"]} FAIL: {e}')


def _dsh_running():
    try:
        import subprocess
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq DeepSeek Harness.exe'],
                             capture_output=True, text=True, timeout=10)
        return 'DeepSeek Harness.exe' in (out.stdout or '')
    except Exception:
        return False


def _is_holiday(cfg, d):
    if d.weekday() >= 5:
        return True
    return d.isoformat() in set(cfg.get('holidays') or [])


def main():
    args = sys.argv[1:]
    skip_if_dsh = '--skip-if-dsh' in args
    normal_only = '--normal' in args
    force = '--force' in args
    phase = 'normal'
    if '--estimate' in args:
        phase = 'estimate'
    elif '--confirm' in args:
        phase = 'confirm'
    args = [a for a in args if not a.startswith('--')]
    mode = args[0] if args else 'signal'
    cfg = load_cfg()
    if skip_if_dsh and _dsh_running():
        print('DSH 正在运行，跳过本次通知（避免重复）')
        return
    if mode == 'fetch':
        cmd_fetch(cfg)
    elif mode == 'backtest':
        cmd_backtest(cfg)
    elif mode == 'yearly':
        cmd_yearly(cfg)
    elif mode == 'buy' and len(args) >= 3:
        cmd_buy(cfg, args[1], float(args[2]))
    elif mode == 'sell' and len(args) >= 3:
        cmd_sell(cfg, args[1], float(args[2]))
    elif mode in ('signal', 'notify'):
        if _is_holiday(cfg, datetime.date.today()):
            print(f'{datetime.date.today()} 非交易日（周末/节假日），跳过信号')
            return
        done = settle_pending(cfg)
        if done:
            print('[自动记账] 已按实际净值结算: ' + ', '.join(done))
        if mode == 'notify' and not force and not claim_slot():
            print('本时段已发送过（10 分钟内），跳过以防重复。')
            return
        data = collect_signals(cfg, normal_only=normal_only, phase=phase)
        holding_info(data['items'], cfg)
        if mode == 'notify' and cfg.get('auto_apply') and phase == 'confirm':
            if queue_buy(cfg, data['items']):
                print('[自动记账] 今日买入已登记，待当天净值公布后按实际净值结算')
        report = _report_text(data)
        print(report)
        if mode == 'notify':
            imgs = []
            try:
                base = os.path.join(CACHE_DIR, 'report_%s' % datetime.date.today().isoformat())
                p1 = render_report_image(data, base + '_dark_sum.png', dark=True, extra=False)
                p2 = render_dashboard_image(data, base + '_dark.png', dark=True, cfg=cfg)
                p3 = render_dashboard_image(data, base + '.png', dark=False, cfg=cfg)
                imgs = [(p1, '深色信号'), (p2, '每日收益日历 + 收益饼图（深色）'), (p3, '每日收益日历 + 收益饼图（浅色）')]
            except Exception:
                imgs = []
            print('\n[推送]')
            for r in notify(report, cfg, images=imgs):
                print(' ', r)
    else:
        print(__doc__)


if __name__ == '__main__':
    main()

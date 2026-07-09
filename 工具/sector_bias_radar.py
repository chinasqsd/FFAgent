#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""板块乖离雷达(per-sector自适应) — 扫盘用。
每个板块用自己近120日B5分布(均值μ/标准差σ)做标尺(z-score)，"贵不贵"相对该板块自己常态，非统一数值。
  能买吗★(5=超跌该买 / 1=过热别买)
  要卖吗★(5=贵+动能转弱该减 / 1=别减; 动能mom5是闸门, 强动能时即便贵也别减=防踏空)
依据: 产业逻辑/乖离率研究_2026-06.md + 记忆 feedback_entry_timing_not_too_conservative。
用法:
  python 工具/sector_bias_radar.py            # 终端输出(无emoji,防GBK报错)
  python 工具/sector_bias_radar.py --feishu   # 终端输出 + 推送扫盘飞书群(全称+颜色版)
"""
import sys, os, math, json, datetime, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qfq_kline import qfq_day, _market


def realtime_price(code):
    """腾讯实时接口取当前价(盘中=最新成交价, 盘后=收盘价)。失败返回None。"""
    try:
        url = f'http://qt.gtimg.cn/q={_market(code)}{code}'
        raw = urllib.request.urlopen(
            urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10
        ).read().decode('gbk', errors='replace')
        p = float(raw.split('~')[3])
        return p if p > 0 else None
    except Exception:
        return None

FEISHU_URL = '{{FEISHU_WEBHOOK_URL}}'  # 替换为你的飞书扫盘群 webhook URL

GROUPS = {
    'PCB': ['002463', '300476', '002384', '002938', '600183'],
    'Optical': ['300308', '300502', '300394', '688498', '300570'],
    'Storage': ['603986', '688008', '301666', '301308', '001309'],
    'DomChip': ['688256', '688041', '688981', '002371', '688012'],
}
GROUP_CN = {'PCB': 'PCB', 'Optical': '光模块', 'Storage': '存储', 'DomChip': '国产芯片'}
SPECIAL = ['603501', '002169', '300274', '000063',    # 特别关注(已清/关注复进, 各自标尺, 不池化)
           '002585', '000725', '301196', '301128', '002747',
           '002050', '688593', '688559', '603005', '300503', '001696']
ANCHORS = {'002169': ('等￥13接回', 13.0),    # 个人关键位
           '001696': ('守20破即离场', 20.0),  # 宗申动力情绪博弈验证位(破20=派发确认离场)
           '000063': ('站41突破/破36止', 41.0)}  # 中兴: 41带量站上=突破追/破36或主力净额转负=离场
NAMES = {
    '002463': '沪电股份', '300476': '胜宏科技', '002384': '东山精密', '002938': '鹏鼎控股', '600183': '生益科技',
    '300308': '中际旭创', '300502': '新易盛', '300394': '天孚通信', '688498': '源杰科技', '300570': '太辰光',
    '603986': '兆易创新', '688008': '澜起科技', '301666': '大普微', '301308': '江波龙', '001309': '德明利',
    '688256': '寒武纪', '688041': '海光信息', '688981': '中芯国际', '002371': '北方华创', '688012': '中微公司',
    '603501': '豪威集团', '002169': '智光电气', '300274': '阳光电源', '000063': '中兴通讯',
    '002585': '双星新材', '000725': '京东方A', '301196': '唯科科技', '301128': '强瑞技术', '002747': '埃斯顿',
    '002050': '三花智控', '688593': '新相微', '688559': '海目星', '603005': '晶方科技', '300503': '昊志机电',
    '001696': '宗申动力',
}
LOOKBACK = 120


def mean(x): return sum(x) / len(x)
def std(x):
    m = mean(x); return math.sqrt(sum((v - m) ** 2 for v in x) / len(x))


def b5_hist(code, n=LOOKBACK):
    c = [r[2] for r in qfq_day(code, n + 10)]
    out = [(c[i] - sum(c[i - 4:i + 1]) / 5) / (sum(c[i - 4:i + 1]) / 5) * 100 for i in range(4, len(c))]
    return out[-n:]


def cur(code):
    rows = qfq_day(code, 45)
    today = datetime.date.today().isoformat()
    baseline_date = rows[-1][0]
    closes = [r[2] for r in rows if r[0] != today]   # 历史前复权,剔除今日bar(避免与实时重复)
    live = realtime_price(code) or rows[-1][2]        # 盘中=实时价, 失败回退最近收盘
    closes.append(live)                               # 实时价当"今日最新价"拼上
    ma5 = sum(closes[-5:]) / 5
    return dict(code=code, price=live, b5=(live - ma5) / ma5 * 100,
                mom5=(live / closes[-6] - 1) * 100, mom22=(live / closes[-23] - 1) * 100,
                baseline_date=baseline_date)


# ===== 大盘择时闸 A/B 自动检测（焊入飞书推送，到 B 闸自动红字警报）=====
# 通道值来源: 持仓/出手监控清单.md（用户6/18画的上升通道）。重画通道后改这两个常量即可。
LOWER_RAIL = 4069.0   # 上证下沿/MA20
MID_RAIL = 4085.0     # 上证中轨
VOL_RATIO_HOT = 1.5   # 量比≥此值视为"放量"
TECH_CORE = {'588460': '科创50增强', '159813': '半导体', '515980': 'AI'}  # 科技核心(破MA20=龙头走坏佐证)


def index_quote(full_code='sh000001'):
    """取指数现价+量比(腾讯接口, full_code需带sh/sz前缀)。失败返回(None,None)。"""
    try:
        url = f'http://qt.gtimg.cn/q={full_code}'
        raw = urllib.request.urlopen(
            urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10
        ).read().decode('gbk', errors='replace')
        f = raw.split('~')
        price = float(f[3])
        try:
            vr = float(f[49])      # 量比
        except Exception:
            vr = None
        return (price if price > 0 else None), vr
    except Exception:
        return None, None


def ma_n(code, n):
    """返回(MA_n, 实时价)。复用qfq_day历史前复权+实时价拼接(同cur逻辑)。"""
    rows = qfq_day(code, n + 6)
    today = datetime.date.today().isoformat()
    closes = [r[2] for r in rows if r[0] != today]
    live = realtime_price(code) or rows[-1][2]
    closes.append(live)
    return sum(closes[-n:]) / n, live


def bgate():
    """判大盘A/B闸。返回(emoji, 结论, 明细)；取数失败返回None。"""
    idx, vr = index_quote('sh000001')
    if idx is None:
        return None
    broke = []
    for code, nm in TECH_CORE.items():
        try:
            m20, live = ma_n(code, 20)
            if live < m20:
                broke.append(nm)
        except Exception:
            pass
    big_vol = (vr is not None and vr >= VOL_RATIO_HOT)
    if idx < LOWER_RAIL and (big_vol or len(broke) >= 2):
        emoji, verdict = '🔴🔴', 'B闸触发→持币/持仓科技腿启动防守(动"再卖1/4")'
    elif idx < LOWER_RAIL or len(broke) >= 2:
        emoji, verdict = '🟠', '逼近B闸→警戒, 不出手, 手放刹车上'
    elif idx < MID_RAIL:
        emoji, verdict = '🟡', '破中轨, 留意(A闸仍开但走弱)'
    else:
        emoji, verdict = '🟢', 'A闸·健康(缩量回踩可出手)'
    detail = f"上证{idx:.0f}(下沿{LOWER_RAIL:.0f}/中轨{MID_RAIL:.0f})"
    if vr is not None:
        detail += f" 量比{vr:.2f}"
    detail += f" 科技破MA20: {'/'.join(broke) if broke else '无'}"
    return emoji, verdict, detail


def stars(n): return '★' * n + '☆' * (5 - n)
def buy_n(z): return 5 if z < -1.5 else 4 if z < -0.5 else 3 if z < 0.5 else 2 if z < 1.5 else 1
def sell_n(z, m5):
    if z < 0.5: return 1
    if m5 > 0: return 2 if z > 2 else 1
    return 5 if z > 1.5 else 4
def temp(z): return ("超跌" if z < -1.5 else "偏冷" if z < -0.5 else "中性" if z < 0.5
                     else "偏热" if z < 1.5 else "过热" if z < 2 else "极热")
def temp_emoji(z): return ("🟢" if z < -0.5 else "⚪" if z < 0.5 else "🟡" if z < 0.5 else "🟠" if z < 2 else "🔴")
def arrow(m5): return ("↑↑强升" if m5 > 10 else "↑ 仍升" if m5 > 0 else "↓ 转弱" if m5 > -3 else "↓↓快跌")
def pad4(nm): return nm + "　" * max(0, 4 - len(nm))


def collect():
    rep = []
    for g, codes in GROUPS.items():
        pool = [v for x in codes for v in b5_hist(x)]
        mu, sd = mean(pool), std(pool)
        ms = []
        for x in codes:
            m = cur(x); m['z'] = (m['b5'] - mu) / sd; ms.append(m)
        ms.sort(key=lambda m: m['z'])
        rep.append((GROUP_CN[g], f"μ{mu:+.1f}/σ{sd:.1f}", ms, 'sector'))
    sp = []                                  # 特别关注: 每只各自μ/σ(互不相干,不池化)
    for x in SPECIAL:
        h = b5_hist(x); mu_i, sd_i = mean(h), std(h)
        m = cur(x); m['z'] = (m['b5'] - mu_i) / sd_i; sp.append(m)
    sp.sort(key=lambda m: m['z'])
    rep.append(('特别关注', '各自标尺', sp, 'special'))
    return rep


def anchor(m):
    if m['code'] in ANCHORS:
        lab, lv = ANCHORS[m['code']]
        return f" [{lab} 距{(m['price'] / lv - 1) * 100:+.0f}%]"
    return ""


def print_terminal(rep):
    print("=== 板块乖离雷达 (per-sector自适应) ===")
    print("能买吗★:5=超跌该买/1=过热别买 | 要卖吗★:5=贵+动能转弱该减/1=别减(防踏空)\n")
    for label, scale, ms, kind in rep:
        if kind == 'sector':
            gz, gm5 = mean([m['z'] for m in ms]), mean([m['mom5'] for m in ms])
            print(f"[{label}] {scale} 组均({temp(gz)}) {arrow(gm5)} 能买{stars(buy_n(gz))} 要卖{stars(sell_n(gz, gm5))}")
        else:
            print(f"[{label}] 每只各自历史比")
        for m in ms:
            z = m['z']
            print(f"    能买{stars(buy_n(z))} 要卖{stars(sell_n(z, m['mom5']))} {temp(z):<3}{arrow(m['mom5']):<8}"
                  f" {NAMES[m['code']]}{m['code']} B5{m['b5']:+.1f}(z{z:+.1f}){anchor(m)}")
        print()


def format_cn_date(date_text):
    y, m, d = date_text.split("-")
    return f"{int(y)}年{int(m)}月{int(d)}日"


def baseline_date_from_report(rep):
    for _label, _scale, ms, _kind in rep:
        for m in ms:
            if m.get("baseline_date"):
                return m["baseline_date"]
    return None


def build_feishu(rep, bg=None, baseline_date=None):
    entry3, entry4, sells = [], [], []   # ★★★可建仓 / ★★★★低吸加仓 / 减仓 (只看主线4组)
    for label, scale, ms, kind in rep:
        if kind != 'sector':
            continue
        for m in ms:
            bn = buy_n(m['z'])
            if bn == 3: entry3.append(NAMES[m['code']])
            if bn >= 4: entry4.append(NAMES[m['code']])
            if sell_n(m['z'], m['mom5']) >= 4: sells.append(NAMES[m['code']])
    act = []
    if entry4: act.append("🟢低吸/加仓区(更便宜·下1/3): " + "、".join(entry4))
    if entry3: act.append("🟢可起手首仓(★★★中性·首仓1/3≈2万): " + "、".join(entry3))
    if sells:  act.append("🔴减仓信号(贵+动能转弱): " + "、".join(sells))
    if not act: act.append("⏳今日无建仓信号(全场★★偏热以上)→持币等回调。盼头: 等某只回踩到★★★(中性)就提示起手。")
    gate_lines = []
    if bg:
        gate_lines = [f"{bg[0]} 【大盘闸】{bg[1]}", f"    {bg[2]}", ""]
    baseline_date = baseline_date or baseline_date_from_report(rep)
    baseline_line = [f"日线基准日期：{format_cn_date(baseline_date)}"] if baseline_date else []
    L = ["【乖离雷达·扫盘】per-sector自适应"] + baseline_line + [
         "🟢便宜该买/🔴贵当心 ｜ 买★越多越该买, 卖★越多越该减", ""] + gate_lines + [
         "📌今日行动(主线)"] + act + [""]
    for label, scale, ms, kind in rep:
        L.append(f"▌{label}" + ("（各自标尺,复进观察）" if kind == 'special' else ""))
        for m in ms:
            z = m['z']
            warn = " ⚠↓转弱" if m['mom5'] < 0 else ""
            L.append(f"{pad4(NAMES[m['code']])} {temp_emoji(z)}{temp(z)} 买{'★' * buy_n(z)} 卖{'★' * sell_n(z, m['mom5'])}{warn}{anchor(m)}")
        L.append("")
    L.append("📋节奏: 首仓1/3→★★★★或企稳+1/3→突破站稳+1/3 ｜ 进攻≤12万留一半 ｜ ≤3只单票6-8万 ｜ 下单即设止损")
    L += ["",
          "📖图例",
          "大盘闸: 🟢能做 → 🟡留意 → 🟠把手放刹车上 → 🔴🔴踩刹车(持仓防守·停止买入)",
          "能买★: 5★超跌该买 … 1★过热别买",
          "要卖★: 5★贵+动能转弱该减 … 1★别减(防踏空)",
          "温度: 🟢偏冷 ⚪中性 🟡偏热 🟠过热 🔴极热"]
    return "\n".join(L)


def send_feishu(text):
    body = json.dumps({"msg_type": "text", "content": {"text": text}}).encode('utf-8')
    req = urllib.request.Request(FEISHU_URL, data=body, headers={'Content-Type': 'application/json'})
    r = json.loads(urllib.request.urlopen(req, timeout=10).read())
    print("飞书推送:", r.get('msg'))


def strip_emoji(s):
    """剥离 emoji 等 GBK 不可编码字符，供终端(GBK)输出；飞书版走 HTTP UTF-8 不需要。"""
    return s.encode('gbk', 'ignore').decode('gbk')


if __name__ == '__main__':
    rep = collect()
    bg = bgate()
    print_terminal(rep)
    if bg:
        print(strip_emoji(f"[大盘闸] {bg[0]} {bg[1]}"))
        print(strip_emoji(f"         {bg[2]}"))
    if '--feishu' in sys.argv:
        send_feishu(build_feishu(rep, bg))

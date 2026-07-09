# -*- coding: utf-8 -*-
"""
观察池每日自动检查 —— 市场闸门 + A级15只位置关 + 持仓条款 + ETF触发线

用法:
    python daily_check.py               # 自动判断盘中/收盘模式, 推送飞书
    python daily_check.py --no-push     # 只打印不推送(调试)

检查内容(对应 持仓/股票观察池.md 三层闸门 + FOMC后开仓决策预案):
  1. 市场闸门: 上证 vs MA20通道下沿(A层择时) / 3900缺口 / MA60 / 放量阳线(收盘模式)
  2. A级15只: 距MA20乖离分档(<10%低吸/10-30%持有/>30%警戒/>50%强减) / 缩量止跌天数
  3. 持仓条款: 智光(交易仓15.0/底仓13.0) 豪威(止损88.5/止盈95) 阳光(止损137) 有色ETF(保护1.85清尾仓)

数据源: 通达信本地日线(历史, C:\\new_tdx) + 腾讯API(实时, 复用query_stock.py)
除权防护: API昨收 vs 日线昨收偏差>1.5% 自动算复权因子; 历史出现>12%断崖标"疑除权"

更新记录:
  6/16 建; 6/17 全面对齐——位置关改MA20乖离(回踩MA60对龙头已证伪)、市场闸门加MA20通道下沿、
       A池补电子布(国际复材/生益)→15只、持仓条款补豪威(88.5)+阳光(137)、有色改1.85清尾仓13800份
"""
import os
import sys
import struct
import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from query_stock import fetch_realtime

# Windows控制台gbk无法打印emoji, 强制stdout用utf-8(不影响飞书utf-8推送)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

TDX_DIR = r'C:\new_tdx\vipdoc'
WEBHOOK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feishu_webhook.txt')

# A级观察池(代码, 名称) —— 与 持仓/股票观察池.md 同步(6/16补电子布环节→15只)
A_POOL = [
    ('300308', '中际旭创'), ('300502', '新易盛'), ('300394', '天孚通信'),
    ('002384', '东山精密'), ('002938', '鹏鼎控股'), ('002463', '沪电股份'),
    ('300476', '胜宏科技'), ('301526', '国际复材'), ('600183', '生益科技'),
    ('603986', '兆易创新'), ('688008', '澜起科技'), ('002371', '北方华创'),
    ('688012', '中微公司'), ('688981', '中芯国际'), ('688041', '海光信息'),
]
# AIDC供电观察组(800V HVDC/SiC, 6/17加入观察看距MA20, 非A级买入候选)
WATCH_POOL = [
    ('002364', '中恒电气'), ('002851', '麦格米特'), ('300870', '欧陆通'),
    ('002837', '英维克'), ('600703', '三安光电'), ('688234', '天岳先进'),
]
INDEX_GAP = 3900.0          # 上证缺口参考(支撑参考, 非择时主指标)
ZG_TRADE_LINE = 15.00       # 智光交易仓线(4000股@15.88, 止损收盘破15.0铁条款不再放松)
ZG_BASE_LINE = 13.00        # 智光底仓线(3000股@4.66, 止损收盘破13.0)
HW_STOP = 88.50             # 豪威止损(收盘破; 6/17放量突破后从85上移至突破位)
HW_TARGET = 95.00           # 豪威止盈
YG_STOP = 137.00            # 阳光止损(MA250, 收盘破; 试仓100@152.52, 金字塔上限400股)
NONFERROUS_CLEAR = 1.85     # 有色ETF保护线(收盘破→清尾仓13800份)


def read_day(code: str):
    if code.startswith(('sh', 'sz')):
        mk, code = code[:2], code[2:]
    else:
        mk = 'sh' if code[0] in '659' else 'sz'
    path = os.path.join(TDX_DIR, mk, 'lday', f'{mk}{code}.day')
    if not os.path.exists(path):
        return []
    bars = []
    with open(path, 'rb') as f:
        while True:
            b = f.read(32)
            if len(b) < 32:
                break
            d, o, h, l, c, a, v, pc = struct.unpack('<Iiiiiiii', b)
            bars.append({'date': str(d), 'open': o / 100, 'high': h / 100,
                         'low': l / 100, 'close': c / 100, 'volume': v})
    return bars


def _adjust(hist, api_prev):
    """除权防护: 返回(复权后历史, 今日除权因子, 是否历史近似复权)"""
    factor = 1.0
    if abs(hist[-1]['close'] / api_prev - 1) > 0.015:
        factor = api_prev / hist[-1]['close']
    h = [{**b, 'open': b['open'] * factor, 'high': b['high'] * factor,
          'low': b['low'] * factor, 'close': b['close'] * factor} for b in hist]
    return h, factor


def analyze_stock(code, name, quote):
    """位置关: 距MA20乖离分档(6/17起替代回撤带/MA60上车——龙头回踩浅已证伪, 见观察池六-2)"""
    hist = read_day(code)[-130:]
    if not hist or not quote:
        return f'{name}({code}): 数据缺失'
    price = float(quote['price'])
    api_prev = float(quote['prev_close'])

    # 除权防护1: 今日除权 -> 用因子缩放历史
    h, factor = _adjust(hist, api_prev)

    # 除权防护2: 超涨跌停幅度的隔日断崖 = 除权日, 用收盘比对断崖前历史做近似复权
    # (20cm板阈值21%/主板11%; 限幅内的小比例除权探测不到, 待gbbq精确复权)
    limit = 0.21 if code[:1] == '3' or code[:3] == '688' else 0.11
    approx = False
    for i in range(max(1, len(h) - 120), len(h)):
        ratio = h[i]['close'] / h[i - 1]['close']
        if abs(ratio - 1) > limit:
            for j in range(i):
                for k in ('open', 'high', 'low', 'close'):
                    h[j][k] *= ratio
            approx = True

    closes = [b['close'] for b in h]
    ma20 = (sum(closes[-19:]) + price) / 20
    ma60 = (sum(closes[-59:]) + price) / 60
    bias = (price / ma20 - 1) * 100   # 距MA20乖离 = 龙头域持有/减仓主指标

    # 缩量止跌天数(辅助): 从最近交易日往回数, 既未创窗口新低、量又低于5日均量
    w = h[-120:]
    streak = 0
    for i in range(len(w) - 1, 0, -1):
        win_min = min(b['low'] for b in w[:i])
        vol_ma5 = sum(b['volume'] for b in w[max(0, i - 5):i]) / min(5, i)
        if w[i]['low'] > win_min and w[i]['volume'] < vol_ma5:
            streak += 1
        else:
            break

    if bias < 10:
        pos = f'✅近MA20({bias:+.0f}%)低吸/上车区'
    elif bias <= 30:
        pos = f'🟢健康持有({bias:+.0f}%)'
    elif bias <= 50:
        pos = f'⚠️警戒偏高({bias:+.0f}%)'
    else:
        pos = f'⛔极度超买({bias:+.0f}%)'
    flag = ('✦' if factor != 1.0 else '') + ('≈' if approx else '')
    return (f'{name}{flag}: {price:.2f} ({quote["pct"]}%) | {pos} | '
            f'MA20={ma20:.1f} MA60={ma60:.1f} | 止跌{streak}日')


def market_gate(quote, is_close):
    hist = read_day('sh000001')[-130:]
    price = float(quote['price'])
    closes = [b['close'] for b in hist]
    ma20 = (sum(closes[-19:]) + price) / 20
    ma60 = (sum(closes[-59:]) + price) / 60
    lines = [f'上证 {price:.0f} ({quote["pct"]}%) | 距3900缺口 '
             f'{(price / INDEX_GAP - 1) * 100:+.1f}% | MA20={ma20:.0f} MA60={ma60:.0f}'
             f'{"(破MA60)" if price < ma60 else ""}']
    # A层择时(FOMC后开仓预案): 回踩通道下沿≈MA20企稳=扣扳机时机, 放量跌穿=通道作废
    bias20 = (price / ma20 - 1) * 100
    if abs(bias20) <= 1.0:
        lines.append(f'📍 上证贴MA20通道下沿({bias20:+.1f}%) — A层择时位, 看缩量企稳(破下沿则通道作废不接)')
    elif price < ma20:
        lines.append(f'📍 上证已破MA20下沿({bias20:+.1f}%) — 放量跌穿=不接飞刀, 缩量不创新低再看')
    else:
        lines.append(f'上证距MA20下沿 {bias20:+.1f}%(在下沿上方, 等回踩或不追陡升)')
    if is_close and hist:
        vol_ma5 = sum(b['volume'] for b in hist[-5:]) / 5
        today_vol = float(quote.get('volume_lots', 0)) * 100
        yang = price > float(quote['open'])
        fangliang = today_vol > vol_ma5
        if yang and fangliang:
            lines.append('🟢 放量阳线 — 形态闸信号出现, 复核后可小仓试探')
        else:
            lines.append(f'形态闸未开(阳线={"是" if yang else "否"}, '
                         f'放量={"是" if fangliang else "否"})')
    return lines


def holdings_check(quotes, is_close):
    lines = []
    tag = '收盘' if is_close else '现价'
    # 智光: 交易仓15.0 + 底仓13.0(均以收盘破为准)
    zg = quotes.get('002169')
    if zg:
        p = float(zg['price'])
        if p < ZG_BASE_LINE:
            lines.append(f'🔴 智光 {tag}{p:.2f} 破底仓线13.00 → 清底仓3000股!')
        elif p < ZG_TRADE_LINE:
            act = '→ 交易仓4000股按铁条款清(收盘破15.0不再放松)' if is_close else '(收盘确认为准)'
            lines.append(f'🔴 智光 {tag}{p:.2f} 跌破交易仓线15.00 {act}')
        else:
            lines.append(f'🟢 智光 {tag}{p:.2f} 在15.00上方(交易仓4000@15.88 / 底仓3000@4.66)')
    # 豪威: 止损88.5收盘破 / 止盈95
    hw = quotes.get('603501')
    if hw:
        p = float(hw['price'])
        if p < HW_STOP:
            act = '→ 假突破保本撤(止损88.5从85上移)' if is_close else '(收盘破才走, 盘中插针不算)'
            lines.append(f'🔴 豪威 {tag}{p:.2f} 跌破止损88.50 {act}')
        elif p >= HW_TARGET:
            lines.append(f'🟢 豪威 {tag}{p:.2f} 触及止盈95.00 → 考虑兑现100股')
        else:
            lines.append(f'🟢 豪威 {tag}{p:.2f} 在88.50-95.00持有(让利润奔95)')
    # 阳光: 止损137(MA250)收盘破
    yg = quotes.get('300274')
    if yg:
        p = float(yg['price'])
        if p < YG_STOP:
            act = '→ 跌破MA250止损撤' if is_close else '(收盘确认为准)'
            lines.append(f'🔴 阳光 {tag}{p:.2f} 跌破止损137(MA250) {act}')
        else:
            lines.append(f'🟢 阳光 {tag}{p:.2f} 距止损137 {(p / YG_STOP - 1) * 100:+.1f}%'
                         f'(试仓100@152.52, 金字塔上限400股)')
    # 有色ETF尾仓: 收盘破1.85全清
    ys = quotes.get('516650')
    if ys:
        p = float(ys['price'])
        if p < NONFERROUS_CLEAR:
            act = '→ 尾仓13800份全清' if is_close else '(收盘确认为准)'
            lines.append(f'🔴 有色ETF {tag}{p:.3f} 跌破保护线1.85 {act}')
        else:
            lines.append(f'有色ETF {p:.3f} 距保护线1.85 {(p / NONFERROUS_CLEAR - 1) * 100:+.1f}%(尾仓13800份)')
    return lines


def send_feishu(text):
    try:
        with open(WEBHOOK_FILE, encoding='utf-8') as f:
            url = f.read().strip()
        r = requests.post(url, json={'msg_type': 'text', 'content': {'text': text}},
                          timeout=8)
        ok = r.json().get('code') == 0
        print(f'[飞书推送: {"成功" if ok else "失败 " + r.text[:100]}]')
    except Exception as e:
        print(f'[飞书推送异常: {e}]')


def main():
    no_push = '--no-push' in sys.argv
    now = datetime.datetime.now()
    is_close = now.hour >= 15

    codes = ([c for c, _ in A_POOL] + [c for c, _ in WATCH_POOL]
             + ['002169', '603501', '300274', '516650', 'sh000001'])
    quotes = {r['code']: r for r in fetch_realtime(codes)}
    idx = quotes.get('000001')
    if not idx:
        print('行情获取失败')
        return
    # 非交易日: 行情时间戳不是今天 -> 静默退出
    if idx.get('time', '')[:8] != now.strftime('%Y%m%d'):
        print('非交易日, 跳过')
        return

    mode = '收盘检查' if is_close else '盘中检查'
    rpt = [f'【观察池{mode}】{now.strftime("%m月%d日 %H:%M")}', '']
    rpt.append('图例 ✅近MA20低吸 🟢健康持有 ⚠️偏高 ⛔超买 🔴触线纪律（均为位置状态，非A股红涨绿跌）')
    rpt.append('')
    rpt.append('■ 市场闸门')
    rpt += market_gate(idx, is_close)
    rpt.append('')
    rpt.append('■ 持仓条款')
    rpt += holdings_check(quotes, is_close)
    rpt.append('')
    rpt.append('■ A级位置关(距MA20乖离; ✦=今日除权已修正, ≈=历史除权近似复权)')
    for code, name in A_POOL:
        rpt.append(analyze_stock(code, name, quotes.get(code)))
    rpt.append('')
    rpt.append('■ AIDC供电观察组(800V HVDC/SiC, 6/17加入·看距MA20, 非买入候选)')
    for code, name in WATCH_POOL:
        rpt.append(analyze_stock(code, name, quotes.get(code)))
    rpt.append('')
    rpt.append('⚠️ 市场闸门未开前, 近MA20=进开闸即审名单, 不是买入信号(6月18日FOMC)')

    text = '\n'.join(rpt)
    print(text)
    if not no_push:
        send_feishu(text)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""周末量价分析：智光电气(002169) + 豪威集团(603501)
读通达信日线，输出近1月/近3月量价结构、量能异动、均线、支撑压力、换手趋势。
仅量价口径（OHLCV），无主力/北向/龙虎榜。"""
import struct, os
import pandas as pd
import numpy as np

SH_DIR = r'C:\new_tdx\vipdoc\sh\lday'
SZ_DIR = r'C:\new_tdx\vipdoc\sz\lday'

# 总股本（亿股），用于换手率估算
SHARES = {'002169': 7.827e8, '603501': 12.61e8}
NAMES = {'002169': '智光电气', '603501': '豪威集团'}

def read_day_file(filepath):
    if not os.path.exists(filepath):
        return None
    records = []
    with open(filepath, 'rb') as f:
        while True:
            data = f.read(32)
            if not data or len(data) < 32:
                break
            date, o, h, l, c, amount, volume, _ = struct.unpack('<IiiiifiI', data)
            if date == 0:
                break
            records.append({'date': f"{date//10000:04d}-{(date%10000)//100:02d}-{date%100:02d}",
                            'open': o/100, 'high': h/100, 'low': l/100, 'close': c/100,
                            'volume': volume, 'amount': amount/100})
    return pd.DataFrame(records)

def load_stock(code):
    d = SH_DIR if code.startswith(('6','5','9')) else SZ_DIR
    pref = 'sh' if code.startswith(('6','5','9')) else 'sz'
    return read_day_file(os.path.join(d, f'{pref}{code}.day'))

def analyze(code):
    df = load_stock(code)
    if df is None or df.empty:
        print(f"{code} 数据读取失败"); return
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    for n in (5,10,20,60):
        df[f'ma{n}'] = df['close'].rolling(n).mean()
    df['vol_ma5'] = df['volume'].rolling(5).mean()
    df['pct'] = df['close'].pct_change()*100
    shares = SHARES[code]
    df['turnover'] = df['volume']/shares*100  # 换手率%
    last = df.iloc[-1]
    print('='*70)
    print(f"{NAMES[code]}({code})  数据最新日期：{last['date'].date()}  收盘 {last['close']:.2f}")
    print('='*70)
    # 近1月/3月窗口
    for label, n in (('近1月(20交易日)',20),('近3月(60交易日)',60)):
        w = df.tail(n)
        chg = (w['close'].iloc[-1]/w['close'].iloc[0]-1)*100
        hi, lo = w['high'].max(), w['low'].min()
        amt_avg = w['amount'].mean()/1e8
        to_avg = w['turnover'].mean()
        print(f"\n[{label}]")
        print(f"  区间涨跌: {chg:+.1f}%  ({w['close'].iloc[0]:.2f} → {w['close'].iloc[-1]:.2f})")
        print(f"  区间高低: {hi:.2f} / {lo:.2f}   现价距高点 {(last['close']/hi-1)*100:+.1f}%, 距低点 {(last['close']/lo-1)*100:+.1f}%")
        print(f"  日均成交额: {amt_avg:.2f}亿   日均换手: {to_avg:.2f}%")
    # 均线结构
    print(f"\n[均线结构]  现价 {last['close']:.2f}")
    for n in (5,10,20,60):
        v = last[f'ma{n}']
        rel = '上方' if last['close']>=v else '下方'
        print(f"  MA{n}={v:.2f}  现价在其{rel} ({(last['close']/v-1)*100:+.1f}%)")
    arr = last['close']>last['ma5']>last['ma10']>last['ma20']
    print(f"  多头排列(收>5>10>20): {'是' if arr else '否'}")
    # 量能异动：最近10日 vs 前期
    print(f"\n[量能/换手 近10日逐日]")
    for _, r in df.tail(10).iterrows():
        vr = r['volume']/r['vol_ma5'] if r['vol_ma5']>0 else 0
        flag = '⚠️放量' if vr>1.8 else ('缩量' if vr<0.6 else '')
        print(f"  {r['date'].date()}  收{r['close']:.2f} {r['pct']:+5.1f}%  额{r['amount']/1e8:4.2f}亿  换手{r['turnover']:4.2f}%  量比{vr:.2f} {flag}")
    # 关键价位：近60日成交密集/高低点
    w60 = df.tail(60)
    print(f"\n[关键价位参考(近60日)]  压力≈{w60['high'].max():.2f}  支撑≈{w60['low'].min():.2f}  60日均价≈{w60['close'].mean():.2f}")

for c in ('002169','603501'):
    analyze(c)

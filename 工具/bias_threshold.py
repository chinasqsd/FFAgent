#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分板块乖离阈值标定 — 每组用自己近N日B5分布算 均值/标准差/分位，
得到该板块各自的"过热/极热/超跌"线(而非统一数值)。供雷达做per-sector星级。
用法: python 工具/bias_threshold.py [回看交易日=120]
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qfq_kline import qfq_day

GROUPS = {
    'PCB     ': ['002463', '300476', '002384', '002938', '600183'],
    'Optical ': ['300308', '300502', '300394', '688498', '300570'],
    'Storage ': ['603986', '688008', '301666', '301308', '001309'],
    'DomChip ': ['688256', '688041', '688981', '002371', '688012'],
}
N = int(sys.argv[1]) if len(sys.argv) > 1 else 120


def b5_series(code):
    c = [r[2] for r in qfq_day(code, N + 10)]
    out = []
    for i in range(4, len(c)):
        ma = sum(c[i - 4:i + 1]) / 5
        out.append((c[i] - ma) / ma * 100)
    return out[-N:]


def pct(xs, p):
    s = sorted(xs)
    k = (len(s) - 1) * p / 100
    f = int(k)
    return s[f] if f + 1 >= len(s) else s[f] + (s[f + 1] - s[f]) * (k - f)


print(f"=== 分板块乖离(B5)分布标定 | 近{N}日 | 池化各组5只个股 ===")
print(f"{'组':<9}{'均値μ':>7}{'σ':>6}{'极热μ+2σ':>10}{'过热μ+1σ':>10}{'偏热+.5σ':>10}{'偏冷-.5σ':>10}{'超跌-1.5σ':>11}")
for g, codes in GROUPS.items():
    pool = [v for x in codes for v in b5_series(x)]
    mu = sum(pool) / len(pool)
    sd = math.sqrt(sum((v - mu) ** 2 for v in pool) / len(pool))
    print(f"{g:<9}{mu:>+7.1f}{sd:>6.1f}{mu+2*sd:>+10.1f}{mu+sd:>+10.1f}{mu+0.5*sd:>+10.1f}{mu-0.5*sd:>+10.1f}{mu-1.5*sd:>+11.1f}")
print(f"\n--- 分位数对照(更稳健,不假设正态) ---")
print(f"{'组':<9}{'p95(极热)':>10}{'p85(过热)':>10}{'p50(中)':>9}{'p15(偏冷)':>10}{'p5(超跌)':>10}")
for g, codes in GROUPS.items():
    pool = [v for x in codes for v in b5_series(x)]
    print(f"{g:<9}{pct(pool,95):>+10.1f}{pct(pool,85):>+10.1f}{pct(pool,50):>+9.1f}{pct(pool,15):>+10.1f}{pct(pool,5):>+10.1f}")

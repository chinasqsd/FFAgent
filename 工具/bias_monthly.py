#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BIAS(乖离率 vs MA5) 按月切片对比 — 看"偏离多少见顶/见底"的规律随市场状态怎么变。
近6个月切成6个22交易日窗口，每组每月输出：月涨跌幅(市场状态)/拐点乖离(顶/底)/高乖离桶&超跌桶前瞻收益。
用法: python 工具/bias_monthly.py [每月天数=22] [月数=6]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qfq_kline import qfq_day

GROUPS = {
    'PCB     ': ['002463', '300476', '002384', '002938', '600183'],
    'Optical ': ['300308', '300502', '300394', '688498', '300570'],
    'Storage ': ['603986', '688008', '301666', '301308', '001309'],
    'DomChip ': ['688256', '688041', '688981', '002371', '688012'],
}
MLEN = int(sys.argv[1]) if len(sys.argv) > 1 else 22   # 每月交易日
NM = int(sys.argv[2]) if len(sys.argv) > 2 else 6       # 月数
SWING = 2


def ma5(c, i):
    return sum(c[i - 4:i + 1]) / 5 if i >= 4 else None


def mean(x):
    return sum(x) / len(x) if x else None


def load(code):
    k = qfq_day(code, MLEN * NM + 40)
    c = [r[2] for r in k]
    d = [r[0] for r in k]
    b5 = [None if ma5(c, i) is None else (c[i] - ma5(c, i)) / ma5(c, i) * 100 for i in range(len(c))]
    return c, d, b5


print(f"=== BIAS(MA5) monthly | {MLEN}d x {NM}m | swing+-{SWING} ===")
print("ret%=该组该月平均涨跌(市场状态) | swHi/swLo=拐点处MA5乖离均值 | fwd2= 未来2日收益均值")
print("高乖离桶=当日B5>+8 | 超跌桶=当日B5<-4 ; 每只用各自历史,缺月少算一只\n")


def f(v, n_):
    return f"{v:+.1f}({n_})" if v is not None else "  -  "


for gname, codes in GROUPS.items():
    data = {x: load(x) for x in codes}
    print(f"########## GROUP {gname.strip()} ##########")
    print(f"{'month(dates)':<22}{'ret%':>7}{'swHi':>9}{'swLo':>9}{'fwd2|B5>+8':>12}{'fwd2|B5<-4':>12}")
    for j in range(NM - 1, -1, -1):           # 旧->新打印, j=0最新
        rets, swhi, swlo, hi_fwd, lo_fwd = [], [], [], [], []
        dlabel = None
        for x in codes:
            c, d, b5 = data[x]
            H = len(c) - MLEN * j
            L = H - MLEN
            if L < 5:                          # 该股无此月数据(如新股)
                continue
            lab = f"{d[L]}~{d[H-1][5:]}"
            if dlabel is None or len(c) > 0:    # 用有数据的股票打标(取最近赋值即可)
                dlabel = lab
            rets.append((c[H - 1] / c[L] - 1) * 100)
            for i in range(max(L, SWING), min(H, len(c) - SWING)):
                seg = c[i - SWING:i + SWING + 1]
                if b5[i] is None:
                    continue
                if c[i] == max(seg) and b5[i] > 0:
                    swhi.append(b5[i])
                if c[i] == min(seg) and b5[i] < 0:
                    swlo.append(b5[i])
            for i in range(L, min(H, len(c) - 2)):
                if b5[i] is None:
                    continue
                f2 = (c[i + 2] / c[i] - 1) * 100
                if b5[i] > 8:
                    hi_fwd.append(f2)
                if b5[i] < -4:
                    lo_fwd.append(f2)
        if not rets:
            continue
        print(f"{dlabel:<22}{mean(rets):>+7.1f}"
              f"{f(mean(swhi), len(swhi)):>9}{f(mean(swlo), len(swlo)):>9}"
              f"{f(mean(hi_fwd), len(hi_fwd)):>12}{f(mean(lo_fwd), len(lo_fwd)):>12}")
    print()

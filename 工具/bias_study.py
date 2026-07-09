#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BIAS(乖离率) vs MA5/10/20 研究 — 找"偏离均线多少开始回落/反弹"的规律。
方案B(按BIAS分桶看未来2日收益) + 方案A(拐点处的BIAS)。前复权数据，默认看最近WIN个交易日。
用法: python 工具/bias_study.py [WIN]   WIN=分析窗口交易日数(默认22≈1个月)
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
WIN = int(sys.argv[1]) if len(sys.argv) > 1 else 22
SWING = 2  # 拐点=前后各SWING日的局部极值


def ma_series(c, n):
    return [sum(c[i - n + 1:i + 1]) / n if i + 1 >= n else None for i in range(len(c))]


def bias_series(c, m):
    return [None if m[i] is None else (c[i] - m[i]) / m[i] * 100 for i in range(len(c))]


def mean(x):
    return sum(x) / len(x) if x else None


def analyze(code):
    k = qfq_day(code, 80)
    c = [row[2] for row in k]
    if len(c) < 25:
        return None
    b = {5: bias_series(c, ma_series(c, 5)),
         10: bias_series(c, ma_series(c, 10)),
         20: bias_series(c, ma_series(c, 20))}
    n = len(c)
    lo = max(n - WIN, SWING)
    hi = {5: [], 10: [], 20: []}   # 局部高点处BIAS
    low = {5: [], 10: [], 20: []}  # 局部低点处BIAS
    for i in range(lo, n - SWING):
        seg = c[i - SWING:i + SWING + 1]
        is_hi = c[i] == max(seg)
        is_lo = c[i] == min(seg)
        for w in (5, 10, 20):
            if b[w][i] is None:
                continue
            if is_hi and b[w][i] > 0:
                hi[w].append(b[w][i])
            if is_lo and b[w][i] < 0:
                low[w].append(b[w][i])
    # 方案B: 窗口内每日(BIAS5, 未来2日收益%)
    pairs = []
    for i in range(max(n - WIN, 0), n - 2):
        if b[5][i] is not None:
            pairs.append((b[5][i], (c[i + 2] / c[i] - 1) * 100))
    wb5 = [b[5][i] for i in range(max(n - WIN, 0), n) if b[5][i] is not None]
    return dict(code=code, cur=b[5][-1], maxb=max(wb5), minb=min(wb5),
                hi=hi, low=low, pairs=pairs)


BUCKETS = [('>+12', 12, 1e9), ('+8~12', 8, 12), ('+4~8', 4, 8), ('0~+4', 0, 4),
           ('-4~0', -4, 0), ('-8~-4', -8, -4), ('<-8', -1e9, -8)]


def bucket_report(pairs):
    out = []
    for name, a, z in BUCKETS:
        rs = [r for (x, r) in pairs if a <= x < z]
        out.append((name, len(rs), mean(rs)))
    return out


print(f"=== BIAS study | window={WIN} trading days | swing=+-{SWING} ===")
print("BIAS = (close-MA)/MA*100 ; fwd2 = 2-day forward return %\n")
for gname, codes in GROUPS.items():
    res = [r for r in (analyze(x) for x in codes) if r]
    print(f"########## GROUP {gname.strip()} ##########")
    print(f"{'code':<8}{'curB5':>7}{'minB5':>8}{'maxB5':>8} | swingHigh(B5/10/20 avg)        | swingLow(B5/10/20 avg)")
    for r in res:
        h = r['hi']; l = r['low']
        hs = "/".join(f"{mean(h[w]):+.1f}({len(h[w])})" if h[w] else " - " for w in (5, 10, 20))
        ls = "/".join(f"{mean(l[w]):+.1f}({len(l[w])})" if l[w] else " - " for w in (5, 10, 20))
        print(f"{r['code']:<8}{r['cur']:>+7.1f}{r['minb']:>+8.1f}{r['maxb']:>+8.1f} | {hs:<30} | {ls}")
    # 组池化
    pooled_hi = {w: [v for r in res for v in r['hi'][w]] for w in (5, 10, 20)}
    pooled_lo = {w: [v for r in res for v in r['low'][w]] for w in (5, 10, 20)}
    print("  POOLED swingHigh avg B5/10/20: " +
          "/".join(f"{mean(pooled_hi[w]):+.1f}(n{len(pooled_hi[w])})" if pooled_hi[w] else "-" for w in (5, 10, 20)))
    print("  POOLED swingLow  avg B5/10/20: " +
          "/".join(f"{mean(pooled_lo[w]):+.1f}(n{len(pooled_lo[w])})" if pooled_lo[w] else "-" for w in (5, 10, 20)))
    # 方案B 池化分桶
    allp = [p for r in res for p in r['pairs']]
    print("  [Method B] BIAS5 bucket -> avg fwd2 ret (n):")
    for name, cnt, m in bucket_report(allp):
        print(f"      {name:<7}: {('%+.2f%%' % m) if m is not None else '  -  ':<8} (n={cnt})")
    print()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""前复权日线 + 均线计算（腾讯接口）

为什么需要：通达信本地 .day 是【不复权】的，近期除权的标的（送转/分红/配股后）
MA/乖离会严重失真——例：新易盛不复权显示距MA60 -4%（像低吸位），前复权实际 +31%（高位）。
价位快照/上车点判断必须用前复权，否则误判位置。

用法：python 工具/qfq_kline.py 300502 688012 002169 ...
输出：每个代码的前复权 收盘/MA5/MA10/MA20/MA60/MA120 + 距MA20/MA60乖离。
"""
import urllib.request, json, sys


def _market(code: str) -> str:
    if code[0] in '69' or code[:3] == '500' or code[:3] == '510':
        return 'sh'
    if code[0] == '8' or code[:2] in ('43', '83', '87', '88', '92'):
        return 'bj'
    return 'sz'


def qfq_day(code: str, n: int = 360):
    """返回前复权日线 [(日期,开,收,高,低), ...]，最早→最新。"""
    prefix = _market(code) + code
    url = (f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
           f'?param={prefix},day,,,{n},qfq')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    node = data['data'][prefix]
    kline = node.get('qfqday') or node.get('day')
    return [(k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4])) for k in kline]


def _ma(closes, n):
    return sum(closes[-n:]) / n if len(closes) >= n else None


def metrics(code: str):
    k = qfq_day(code)
    closes = [x[2] for x in k]
    cur = closes[-1]
    out = {'code': code, 'date': k[-1][0], 'close': cur}
    for n in (5, 10, 20, 60, 120):
        out[f'ma{n}'] = _ma(closes, n)
    return out


if __name__ == '__main__':
    for code in sys.argv[1:]:
        try:
            m = metrics(code)
            ma20, ma60 = m['ma20'], m['ma60']
            b20 = f"{(m['close']/ma20-1)*100:+.1f}%" if ma20 else 'NA'
            b60 = f"{(m['close']/ma60-1)*100:+.1f}%" if ma60 else 'NA'
            ma60s = f"{ma60:.2f}" if ma60 else 'NA'
            ma20s = f"{ma20:.2f}" if ma20 else 'NA'
            print(f"{code} 前复权 {m['date']} 收{m['close']:.2f} "
                  f"MA20={ma20s} MA60={ma60s} 距MA20{b20} 距MA60{b60}")
        except Exception as e:
            print(f"{code} 失败: {e}")

# -*- coding: utf-8 -*-
"""
腾讯行情查询工具 —— 实时行情 + 分时数据

用法:
    python query_stock.py 600519 000001 300750      # 实时行情(可多只)
    python query_stock.py sh000001                   # 显式前缀(上证指数)
    python query_stock.py 600519 --minute            # 分时数据
    python query_stock.py 600519 --minute --tail 10  # 只看最后10分钟

代码规则: 6/5/9 开头 -> sh, 其他 -> sz; 也可直接传 sh/sz 前缀。
指数需显式传前缀, 如 sh000001(上证指数)、sz399001(深证成指)。

数据源: 腾讯 qt.gtimg.cn(实时, GBK) / web.ifzq.gtimg.cn(分时, JSON)
"""
import sys
import json
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REALTIME_URL = "http://qt.gtimg.cn/q={codes}"
MINUTE_URL = "https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={code}"
TIMEOUT = 8

# 实时行情 ~ 分隔字段中, 我们关心的列(下标见腾讯接口约定)
FIELDS = {
    "name": 1, "code": 2, "price": 3, "prev_close": 4, "open": 5,
    "volume_lots": 6, "time": 30, "change": 31, "pct": 32,
    "high": 33, "low": 34, "amount_wan": 37, "turnover": 38, "pe": 39,
}


def normalize(code: str) -> str:
    """统一成带市场前缀的代码, 如 600519 -> sh600519"""
    code = code.strip().lower()
    if code.startswith(("sh", "sz")):
        return code
    return ("sh" if code[:1] in ("6", "5", "9") else "sz") + code


def fetch_realtime(codes: list[str]) -> list[dict]:
    full = [normalize(c) for c in codes]
    url = REALTIME_URL.format(codes=",".join(full))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    text = urllib.request.urlopen(req, timeout=TIMEOUT).read().decode("gbk", errors="replace")
    out = []
    for line in text.strip().splitlines():
        if "=" not in line or '"' not in line:
            continue
        payload = line.split('="', 1)[1].rstrip('";')
        f = payload.split("~")
        if len(f) <= FIELDS["low"]:
            continue
        rec = {k: f[i] for k, i in FIELDS.items() if i < len(f)}
        out.append(rec)
    return out


def fetch_minute(code: str) -> dict:
    full = normalize(code)
    url = MINUTE_URL.format(code=full)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=TIMEOUT).read().decode("utf-8"))
    node = data["data"][full]
    bars = [b.split() for b in node["data"]["data"]]  # [时间, 价, 累计量(手), 累计额]
    return {"code": full, "date": node["data"].get("date", ""), "bars": bars}


def print_realtime(records: list[dict]) -> None:
    print(f"{'名称':<10}{'代码':<10}{'现价':>10}{'涨跌':>9}{'涨跌幅':>9}"
          f"{'今开':>10}{'最高':>10}{'最低':>10}{'成交额(万)':>14}  时间")
    for r in records:
        pct = r.get("pct", "")
        pct_s = f"{pct}%" if pct else ""
        print(f"{r.get('name',''):<10}{r.get('code',''):<10}"
              f"{r.get('price',''):>10}{r.get('change',''):>9}{pct_s:>9}"
              f"{r.get('open',''):>10}{r.get('high',''):>10}{r.get('low',''):>10}"
              f"{r.get('amount_wan',''):>14}  {r.get('time','')}")


def print_minute(m: dict, tail: int | None) -> None:
    bars = m["bars"]
    if tail:
        bars = bars[-tail:]
    print(f"分时 {m['code']}  日期 {m['date']}  共 {len(m['bars'])} 根, 显示 {len(bars)} 根")
    print(f"{'时间':<6}{'价格':>10}{'累计量(手)':>14}{'累计额(元)':>18}")
    for t, price, vol, amount in bars:
        hhmm = f"{t[:2]}:{t[2:]}"
        print(f"{hhmm:<6}{price:>10}{vol:>14}{float(amount):>18,.0f}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    minute = "--minute" in args
    tail = None
    if "--tail" in args:
        i = args.index("--tail")
        tail = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    codes = [a for a in args if not a.startswith("--")]
    if not codes:
        print("请至少提供一个股票代码")
        return
    if minute:
        print_minute(fetch_minute(codes[0]), tail)
    else:
        print_realtime(fetch_realtime(codes))


if __name__ == "__main__":
    main()

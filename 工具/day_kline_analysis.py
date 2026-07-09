# -*- coding: utf-8 -*-
"""读取通达信本地 .day 日线并输出近期K线技术摘要。

用法:
    python 工具/day_kline_analysis.py 002169
    python 工具/day_kline_analysis.py 002169 --tail 25
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path


TDX_ROOT = Path(r"C:\new_tdx\vipdoc")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def market(code: str) -> str:
    return "sh" if code[0] in "569" else "sz"


def read_day(code: str) -> list[dict]:
    mkt = market(code)
    path = TDX_ROOT / mkt / "lday" / f"{mkt}{code}.day"
    if not path.exists():
        raise FileNotFoundError(str(path))

    rows = []
    with path.open("rb") as f:
        while True:
            b = f.read(32)
            if len(b) < 32:
                break
            date, o, h, l, c, amount, volume, _ = struct.unpack("<IiiiifiI", b)
            if date == 0:
                break
            rows.append(
                {
                    "date": str(date),
                    "open": o / 100,
                    "high": h / 100,
                    "low": l / 100,
                    "close": c / 100,
                    "amount": amount * 100,
                    "volume": volume,
                }
            )
    return rows


def ma(values: list[float], n: int, end: int | None = None) -> float | None:
    end = len(values) if end is None else end
    return sum(values[end - n : end]) / n if end >= n else None


def ema(values: list[float], n: int) -> list[float]:
    k = 2 / (n + 1)
    out = []
    e = values[0]
    for v in values:
        e = v * k + e * (1 - k)
        out.append(e)
    return out


def rsi(values: list[float], n: int = 14) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        if i < n:
            out.append(None)
            continue
        gains, losses = [], []
        for j in range(i - n + 1, i + 1):
            d = values[j] - values[j - 1]
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        avg_gain = sum(gains) / n
        avg_loss = sum(losses) / n
        out.append(100 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    return out


def fmt(value: float | None, digits: int = 2) -> str:
    return "NA" if value is None else f"{value:.{digits}f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="通达信本地日K技术摘要")
    parser.add_argument("code")
    parser.add_argument("--tail", type=int, default=25)
    args = parser.parse_args()

    rows = read_day(args.code)
    if len(rows) < 60:
        print(f"{args.code} 日线不足60条")
        return 1

    rows = rows[-120:]
    closes = [r["close"] for r in rows]
    vols = [r["volume"] for r in rows]
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    dif = [a - b for a, b in zip(ema12, ema26)]
    dea = ema(dif, 9)
    macd = [(a - b) * 2 for a, b in zip(dif, dea)]
    rsis = rsi(closes)

    print("date open high low close pct vol_wanshou amount_yi ma5 ma10 ma20 ma60 vol_ma5 dif dea macd rsi14")
    start = max(1, len(rows) - args.tail)
    for i in range(start, len(rows)):
        r = rows[i]
        pct = (r["close"] / rows[i - 1]["close"] - 1) * 100
        vals = [
            r["date"],
            fmt(r["open"]),
            fmt(r["high"]),
            fmt(r["low"]),
            fmt(r["close"]),
            f"{pct:+.2f}%",
            f"{r['volume'] / 1e6:.2f}",
            f"{r['amount'] / 1e8:.2f}",
            fmt(ma(closes, 5, i + 1)),
            fmt(ma(closes, 10, i + 1)),
            fmt(ma(closes, 20, i + 1)),
            fmt(ma(closes, 60, i + 1)),
            fmt((ma(vols, 5, i + 1) or 0) / 1e6),
            f"{dif[i]:+.3f}",
            f"{dea[i]:+.3f}",
            f"{macd[i]:+.3f}",
            "NA" if rsis[i] is None else f"{rsis[i]:.1f}",
        ]
        print(" ".join(vals))

    last = rows[-1]
    print("SUMMARY")
    print(f"latest {last['date']} close {last['close']:.2f}")
    for n in (5, 10, 20, 60):
        m = ma(closes, n)
        print(f"MA{n} {m:.2f} bias {(last['close'] / m - 1) * 100:+.2f}%")
    vm5 = ma(vols, 5)
    print(f"vol_today {last['volume'] / 1e6:.2f}万手 vol_ma5 {vm5 / 1e6:.2f}万手 ratio {last['volume'] / vm5:.2f}")
    print(f"20d_high {max(r['high'] for r in rows[-20:]):.2f} 20d_low {min(r['low'] for r in rows[-20:]):.2f}")
    print(f"macd {macd[-1]:+.3f} dif {dif[-1]:+.3f} dea {dea[-1]:+.3f} rsi14 {rsis[-1]:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

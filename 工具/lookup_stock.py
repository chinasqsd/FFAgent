# -*- coding: utf-8 -*-
"""股票名称/代码本地查询工具。

用法:
    python 工具/lookup_stock.py 胜宏
    python 工具/lookup_stock.py 300476

只返回命中行，避免把 1MB+ 的 stock_names_cache.csv 整表读入对话上下文。
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / "stock_names_cache.csv"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def clean_text(value: str | None) -> str:
    if value is None:
        return ""
    return value.replace("\x00", "").strip()


def read_rows(cache_path: Path):
    with cache_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = clean_text(row.get("code"))
            name = clean_text(row.get("name"))
            if code and name:
                yield {"code": code, "name": name}


def lookup(query: str, cache_path: str | Path = DEFAULT_CACHE, limit: int = 10) -> list[dict[str, str]]:
    cache = Path(cache_path)
    q = clean_text(query)
    if not q:
        return []

    rows = list(read_rows(cache))

    exact_code = [{"code": r["code"], "name": r["name"], "match": "exact_code"} for r in rows if r["code"] == q]
    if exact_code:
        return exact_code[:limit]

    exact_name = [{"code": r["code"], "name": r["name"], "match": "exact_name"} for r in rows if r["name"] == q]
    if exact_name:
        return exact_name[:limit]

    partial = [
        {"code": r["code"], "name": r["name"], "match": "partial_name"}
        for r in rows
        if q in r["name"] or q in r["code"]
    ]
    return partial[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="查询本地股票名称/代码对照表")
    parser.add_argument("query", help="股票名称、简称或6位代码")
    parser.add_argument("--limit", type=int, default=10, help="最多返回多少条，默认10")
    parser.add_argument("--cache", default=str(DEFAULT_CACHE), help="stock_names_cache.csv 路径")
    args = parser.parse_args()

    cache = Path(args.cache)
    if not cache.exists():
        print(f"未找到对照表: {cache}")
        return 2

    matches = lookup(args.query, cache, args.limit)
    if not matches:
        print('未找到匹配；请标"代码待核"或换关键词查询。')
        return 1

    print(f"{'代码':<8} {'名称':<20} 匹配")
    for item in matches:
        print(f"{item['code']:<8} {item['name']:<20} {item['match']}")

    if len(matches) > 1:
        print("多条匹配时不要猜；请使用更精确名称或代码复核。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

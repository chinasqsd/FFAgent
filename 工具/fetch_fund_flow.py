# -*- coding: utf-8 -*-
"""
fetch_fund_flow.py — 取小白(腾讯云OpenClaw)采集的A股资金流向，本地留档 + 生成可粘贴的日志数据块。

用法:
    python 工具/fetch_fund_flow.py              # 取最新交易日
    python 工具/fetch_fund_flow.py 2026-06-25   # 取指定日期

做什么:
  1. urllib 直拉原始 JSON(不走WebFetch,防小模型截断)
  2. 原始 JSON 落地 数据/资金流向/YYYY-MM-DD.json(本地留档,趋势分析不依赖服务器留存)
  3. 打印「行业流入/流出TOP10 表格 + 个股按5日主力净额排序」数据块
     → 克劳德据此写分析,追加进 产业逻辑/_行业资金流向日志.md
对接规格见 工具/小白数据对接规格.md。
"""
import sys
import os
import json
import time
import urllib.request
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

API_BASE = "https://ai.sgcs.vip/fund_flow/api"
TOKEN = "fund_flow_2026"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "数据", "资金流向")


def fetch(date=None, retries=3, delay=30):
    """拉取资金流向 JSON。date=None 取最新交易日。失败重试(应对小白慢/网络抖动)。"""
    if date:
        url = "%s?date=%s&token=%s" % (API_BASE, date, TOKEN)
    else:
        url = "%s?latest=true&token=%s" % (API_BASE, TOKEN)
    req = urllib.request.Request(url, headers={"User-Agent": "claude-fund-flow/1.0"})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(delay)
    raise last_err


def save_local(date, data):
    """原始当日 data 对象落地本地,供历史累积。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "%s.json" % date)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def log_line(msg):
    """--cron 模式追加一行状态到 数据/资金流向/_fetch.log。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "_fetch.log"), "a", encoding="utf-8") as f:
        f.write("%s  %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))


def fmt_yi(v):
    """亿元数字 → 带符号字符串; None → '—'。"""
    if v is None:
        return "—"
    return "%+.2f亿" % v


def fmt_pct(v):
    if v is None:
        return "—"
    return "%+.2f%%" % v


def dash(v):
    """None / 缺失 → '—'，否则原值。"""
    return "—" if v is None else v


def industry_table(rows, title):
    lines = ["**%s**" % title, "", "| 排名 | 板块 | 净额 | 涨幅 | 5日涨幅 | 量比 |", "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            r.get("rank", ""), r.get("name", ""),
            fmt_yi(r.get("net_yi")), fmt_pct(r.get("chg")),
            fmt_pct(r.get("chg5d")), dash(r.get("vol_ratio")),
        ))
    return "\n".join(lines)


def core_table(rows, title):
    """固定核心行业/概念板块(无rank,按净额降序)。"""
    ordered = sorted(rows, key=lambda r: r.get("net_yi") or 0, reverse=True)
    lines = ["**%s**" % title, "", "| 板块 | 净额 | 涨幅 | 5日涨幅 | 量比 |", "|---|---|---|---|---|"]
    for r in ordered:
        lines.append("| %s | %s | %s | %s | %s |" % (
            r.get("name", ""), fmt_yi(r.get("net_yi")), fmt_pct(r.get("chg")),
            fmt_pct(r.get("chg5d")), dash(r.get("vol_ratio")),
        ))
    return "\n".join(lines)


def stocks_table(stocks):
    # 按5日主力净额降序——一眼看谁被资金真加仓/真派发
    ordered = sorted(stocks, key=lambda s: (s.get("main_net_5d_yi") is not None, s.get("main_net_5d_yi") or 0), reverse=True)
    lines = ["**个股资金(按5日主力净额排序)**", "",
             "| 名称 | 代码 | 收盘 | 涨幅 | 主力净额 | 5日主力净额 | 5日天数 | 超大单 |",
             "|---|---|---|---|---|---|---|---|"]
    for s in ordered:
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            s.get("name", ""), s.get("code", ""), s.get("price", "—"),
            fmt_pct(s.get("chg")), fmt_yi(s.get("main_net_yi")),
            fmt_yi(s.get("main_net_5d_yi")), s.get("main_net_5d_days", "—"),
            fmt_yi(s.get("super_large_yi")),
        ))
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    cron = "--cron" in args
    date_arg = next((a for a in args if not a.startswith("--")), None)
    try:
        payload = fetch(date_arg)
    except Exception as e:
        if cron:
            log_line("ERROR 拉取失败: %s" % e)
        print("❌ 拉取失败: %s" % e)
        sys.exit(1)

    status = payload.get("status")
    if status != "ok":
        if cron:
            log_line("SKIP status=%s date=%s" % (status, payload.get("date")))
        print("⚠️ 接口状态 = %s (date=%s)，无数据可处理。" % (status, payload.get("date")))
        sys.exit(0)

    date = payload.get("date")
    data = payload.get("data", {})
    path = save_local(date, data)

    if cron:
        n_ind = len(data.get("industry_core") or [])
        n_con = len([c for c in (data.get("concept_core") or []) if c.get("net_yi") is not None])
        n_stk = len(data.get("stocks") or [])
        log_line("OK date=%s 行业%d 概念%d 个股%d -> %s" % (date, n_ind, n_con, n_stk, os.path.basename(path)))
        print("OK %s saved -> %s" % (date, path))
        return

    mkt = data.get("market", {})
    print("=" * 60)
    print("📊 资金流向 %s  (已留档: %s)" % (date, path))
    print("上证 %s / 创业板 %s / 成交额 %s万亿" % (
        mkt.get("sh", "—"), mkt.get("cyb", "—"),
        mkt.get("amount_wanyi") if mkt.get("amount_wanyi") is not None else "—"))
    print("=" * 60)
    print()
    print("## %s\n" % date)
    print(industry_table(data.get("industry_in_top10", []), "📈 流入TOP10"))
    print()
    print(industry_table(data.get("industry_out_top10", []), "📉 流出TOP10"))
    print()
    core = data.get("industry_core") or []
    if core:
        print(core_table(core, "🎯 固定核心行业(时间序列)"))
        print()
    concept = data.get("concept_core") or []
    if concept:
        print(core_table(concept, "🧩 固定核心概念板块"))
        print()
    print(stocks_table(data.get("stocks", [])))


if __name__ == "__main__":
    main()

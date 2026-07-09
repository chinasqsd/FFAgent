#!/usr/bin/env python3
"""
资金监控飞书推送脚本
每交易日自动拉取5只重点股票资金流向，计算10分钟变化，推送飞书群。
可独立运行，也可挂Windows任务计划。
"""

import subprocess
import json
import urllib.request
import os
import sys
from datetime import datetime, time, timedelta

# === 配置（用户需自行修改） ===
STOCKS = []  # TODO: 填入要监控的股票代码列表，如 ["000001", "000002"]
STOCK_NAMES = {}  # TODO: 填入股票代码 → 名称映射，如 {"000001": "平安银行"}
FEISHU_URL = "{{FEISHU_WEBHOOK_URL}}"  # 替换为你的飞书机器人 webhook URL
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "工具")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RUN_MARKER = os.path.join(LOG_DIR, ".fund_flow_monitor_last_run")
DUPLICATE_GUARD_MINUTES = 8


def is_trading_time(now=None):
    """判断是否在自定义资金监控发送窗口"""
    if now is None:
        now = datetime.now()
    weekday = now.weekday()
    if weekday >= 5:  # 周末
        return False
    t = now.time()
    morning = time(9, 25) <= t <= time(11, 35)
    afternoon = time(12, 55) <= t <= time(15, 5)
    return morning or afternoon


def recently_ran(now=None, marker_path=RUN_MARKER, min_gap_minutes=DUPLICATE_GUARD_MINUTES):
    """防止 Windows 补跑/重复触发导致几分钟内重复推送。"""
    if now is None:
        now = datetime.now()
    if not os.path.exists(marker_path):
        return False
    try:
        with open(marker_path, "r", encoding="utf-8") as f:
            last_run = datetime.fromisoformat(f.read().strip())
    except Exception:
        return False
    return timedelta(0) <= now - last_run < timedelta(minutes=min_gap_minutes)


def mark_run(now=None, marker_path=RUN_MARKER):
    if now is None:
        now = datetime.now()
    with open(marker_path, "w", encoding="utf-8") as f:
        f.write(now.isoformat())


def run_cmd(cmd):
    """执行命令并返回输出"""
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            creationflags=creationflags,
        )
        return result.stdout
    except Exception as e:
        return f"ERROR: {e}"


def parse_fund_flow(output):
    """解析fund_flow.py输出，提取每只股票的主力净额和主力净量"""
    import re
    data = {}
    for line in output.split("\n"):
        for code in STOCKS:
            if code in line:
                # 跳过stock code本身，提取后面的数字
                # 格式：300476 胜宏科技 现价 319.62 涨跌 -2.32% 主力净额 -2.84 主力净量 -10.7% 5日 -8.90% 换手 1.03 量比 2.40%
                idx = line.find(code)
                rest = line[idx + len(code):]
                nums = re.findall(r'[-+]?\d*\.?\d+', rest)
                # nums[0]=现价, nums[1]=涨跌幅, nums[2]=主力净额, nums[3]=主力净量, nums[4]=5日涨幅, nums[5]=换手, nums[6]=量比
                if len(nums) >= 7:
                    try:
                        data[code] = {
                            "name": STOCK_NAMES.get(code, code),
                            "price": float(nums[0]),
                            "change_pct": nums[1] + "%",
                            "main_flow": float(nums[2]),
                            "main_ratio": nums[3] + "%",
                            "day5_change": nums[4] + "%",
                            "turnover": nums[5],
                            "volume_ratio": nums[6],
                        }
                    except (ValueError, IndexError):
                        continue
    return data


def parse_quote(output):
    """解析query_stock.py输出，补充现价"""
    import re
    data = {}
    for line in output.split("\n"):
        for code in STOCKS:
            if code in line:
                idx = line.find(code)
                rest = line[idx + len(code):]
                nums = re.findall(r'[-+]?\d*\.?\d+', rest)
                if len(nums) >= 1:
                    try:
                        data[code] = {"price": float(nums[0])}
                    except (ValueError, IndexError):
                        continue
    return data


def read_last_flow(log_file=None):
    """从日志文件读取上一轮的主力净额"""
    if log_file is None:
        today = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(LOG_DIR, f"资金监控日志_{today}.md")
    last_flow = {}
    if not os.path.exists(log_file):
        return last_flow
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("|"):
                continue
            for code in STOCKS:
                if code in line or STOCK_NAMES.get(code, code) in line:
                    parts = [p.strip() for p in line.split("|")]
                    # parts[0]空, parts[1]时间, parts[2]标的, parts[3]现价, parts[4]涨跌, parts[5]主力净额, ...
                    try:
                        flow_str = parts[5].strip()
                        flow = float(flow_str)
                        last_flow[code] = flow
                    except (IndexError, ValueError):
                        pass
    return last_flow


def append_log(data):
    """追加数据到日志文件"""
    today = datetime.now().strftime("%Y%m%d")
    now_str = datetime.now().strftime("%H:%M")
    log_file = os.path.join(LOG_DIR, f"资金监控日志_{today}.md")

    # 如果文件不存在，创建并写入表头
    if not os.path.exists(log_file):
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"# 资金监控日志 {datetime.now().strftime('%Y-%m-%d')}\n\n")
            f.write("| 时间 | 标的 | 现价 | 涨跌 | 主力净额(亿) | 主力净量 | 5日涨幅 | 量比 | 备注 |\n")
            f.write("|------|------|------|------|-------------|---------|--------|------|------|\n")

    with open(log_file, "a", encoding="utf-8") as f:
        for code in STOCKS:
            if code in data:
                d = data[code]
                f.write(
                    f"| {now_str} | {d['name']} | {d['price']} | {d['change_pct']} | "
                    f"{d['main_flow']} | {d['main_ratio']} | {d['day5_change']} | "
                    f"{d['volume_ratio']} | |\n"
                )


def send_feishu(msg):
    """发送飞书消息"""
    payload = json.dumps({"msg_type": "text", "content": {"text": msg}}).encode("utf-8")
    req = urllib.request.Request(
        FEISHU_URL,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"飞书发送失败: {e}")
        return None


def build_message(data, last_flow):
    """构建飞书消息"""
    now_str = datetime.now().strftime("%H:%M")
    lines = [f"📊 资金监控 {now_str}", ""]
    lines.append("| 标的 | 现价 | 涨跌 | 主力净额 | 10分钟资金 | 趋势 |")
    lines.append("|------|------|------|---------|-----------|------|")

    for code in STOCKS:
        if code not in data:
            continue
        d = data[code]
        # 计算10分钟变化
        if code in last_flow:
            delta = d["main_flow"] - last_flow[code]
            if abs(delta) < 0.005:
                delta_str = "→0"
            elif delta > 0:
                delta_str = f"+{delta:.2f}亿"
            else:
                delta_str = f"{delta:.2f}亿"
        else:
            delta_str = "首轮"

        # 判断趋势
        if d["main_flow"] > 0:
            trend = "🟢 流入"
        elif d["main_flow"] > -3:
            trend = "🟡 流出放缓"
        elif d["main_flow"] > -10:
            trend = "🟠 流出中"
        else:
            trend = "🔴 大幅流出"

        lines.append(
            f"| {d['name']} | {d['price']} | {d['change_pct']} | "
            f"{d['main_flow']}亿 | {delta_str} | {trend} |"
        )

    # 关键变化总结（带趋势判断）
    changes = []
    for code in STOCKS:
        if code not in data or code not in last_flow:
            continue
        d = data[code]
        delta = d["main_flow"] - last_flow[code]
        name = d["name"]
        flow = d["main_flow"]

        # 1. 阈值触发信号
        if code == "300476" and flow > -3 and last_flow.get(code, 0) <= -3:
            changes.append(f"① {name}破-3亿触发线！主力{last_flow[code]:.2f}→{flow:.2f}亿，企稳信号确认")
        elif code == "300394" and flow < -10 and last_flow.get(code, 0) > -10:
            changes.append(f"② {name}流出破-10亿！{last_flow[code]:.2f}→{flow:.2f}亿，压力加大")
        elif code == "603986" and flow < -40:
            changes.append(f"③ {name}巨量出逃{flow:.2f}亿，离建仓区600-700还差一截")

        # 2. 趋势变化（delta显著）
        if abs(delta) > 0.5:
            if delta > 0:
                changes.append(f"④ {name}10分钟流入加速+{delta:.2f}亿")
            else:
                changes.append(f"⚠️ {name}10分钟流出加速{delta:.2f}亿")

        # 3. 逆势信号
        if flow > 0 and d["change_pct"].startswith("-"):
            changes.append(f"💡 {name}逆势流入+{flow:.2f}亿，资金避风港")

    # 兜底：无任何信号时给方向性总结
    if not changes:
        inflow = [STOCK_NAMES[c] for c in STOCKS if c in data and data[c]["main_flow"] > 0]
        outflow = [STOCK_NAMES[c] for c in STOCKS if c in data and data[c]["main_flow"] < -10]
        if inflow:
            changes.append(f"① 资金流入方：{', '.join(inflow)}")
        if outflow:
            changes.append(f"② 大幅流出方：{', '.join(outflow)}")
        if not changes:
            changes.append("① 主力资金整体平稳，无显著变化")

    lines.append("")
    lines.append("关键变化：")
    lines.extend(changes[:4])

    return "\n".join(lines)


def main():
    if not is_trading_time():
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 非交易时间，跳过")
        return
    if recently_ran():
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 8分钟内已运行过，跳过重复触发")
        return
    mark_run()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始拉取...")

    # 读取上一轮数据
    last_flow = read_last_flow()

    # 拉取资金流向
    codes = " ".join(STOCKS)
    fund_output = run_cmd(f'python "{os.path.join(SCRIPT_DIR, "fund_flow.py")}" {codes}')
    fund_data = parse_fund_flow(fund_output)

    # 拉取行情（补充价格）
    quote_output = run_cmd(f'python "{os.path.join(SCRIPT_DIR, "query_stock.py")}" {codes}')
    quote_data = parse_quote(quote_output)

    # 合并数据（行情补充价格）
    for code in STOCKS:
        if code in fund_data and code in quote_data:
            fund_data[code]["price"] = quote_data[code]["price"]

    if not fund_data:
        print("未获取到数据，跳过")
        return

    # 记录到日志
    append_log(fund_data)

    # 构建并发送飞书消息
    msg = build_message(fund_data, last_flow)
    result = send_feishu(msg)

    if result and result.get("code") == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 飞书发送成功")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 飞书发送结果: {result}")


if __name__ == "__main__":
    main()

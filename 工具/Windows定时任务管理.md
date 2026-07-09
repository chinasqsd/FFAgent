---
date: 2026-07-04
type: 工具说明
tags: [Windows定时任务, 自动化, 钱脉, 扫盘, 飞书]
---
# Windows 定时任务管理

> 本页记录 ETF 知识库相关 Windows 计划任务。当前策略：Windows 负责按时执行脚本，AI 负责解释、巡检、维护和记录，不把任务迁到自动化框架。

## 当前原则

- 核心定时任务继续由 Windows 计划任务触发。
- ETF 任务统一使用 `pythonw.exe` 静默运行，避免盘中弹出脚本窗口。
- 任务逻辑仍在原脚本里，不重写资金、扫盘、提醒规则。
- 修改任务前先备份 XML。

## 名称映射

用户后续用中文名字提任务时，按下表对应：

| 用户口径 | Windows 任务名 | 说明 |
|---|---|---|
| 自定义个股资金监控 | `ETF_FundFlow_Monitor` | 盘中监控自定义个股资金流，推送飞书并写资金监控日志 |
| 钱脉数据拉取 | `ETF_QianMai_Fetch` | 每个交易日盘后从小白 API 拉钱脉原始数据，本地留档 |
| 盘中乖离扫盘推送 | `ETF_Scan_Push` | 固定时点推送主线板块与特别关注票的乖离温度 |

## ETF 任务清单

| Windows 任务名 | 状态 | 触发时间 | 静默启动动作 | 工作目录 | 作用 | 产出 / 通知 |
|---|---|---|---|---|---|---|
| `ETF_FundFlow_Monitor`（自定义个股资金监控） | 启用 | 周一到周五 9:25-11:35、12:55-15:05，每 10 分钟一次 | `pythonw.exe "D:\lp_work\FFAgent\工具\fund_flow_monitor.py"` | `D:\lp_work\FFAgent` | 盘中重点股资金监控 | 写入 `工具/资金监控日志_YYYYMMDD.md`，并推送飞书 |
| `ETF_QianMai_Fetch`（钱脉数据拉取） | 已暂停 | 周一到周五 16:00 | `pythonw.exe 工具\fetch_fund_flow.py --cron` | `D:\lp_work\FFAgent` | 盘后拉取小白钱脉资金流数据 | 写入 `数据/资金流向/YYYY-MM-DD.json` 和 `数据/资金流向/_fetch.log` |
| `ETF_Scan_Push` | 已暂停 | 周一到周五 9:45、10:30、11:15、13:30、14:15、14:50 | `pythonw.exe scan_push.py` | `D:\lp_work\FFAgent` | 盘中乖离扫盘推送 | 调用 `工具/sector_bias_radar.py --feishu`，推送飞书 |

## 巡检口径

用户说"检查定时任务"时，按以下顺序看：
1. Windows 计划任务是否仍存在、状态是否启用。
2. 动作是否仍是 `pythonw.exe`，避免弹窗回退。
3. 上次运行时间、下次运行时间、上次结果。
4. 对应产出是否更新。
5. 如需修改触发时间或脚本路径，改完必须同步更新本页。

## 单项维护要点

### 自定义个股资金监控
- 股票池在 `fund_flow_monitor.py` 的 `STOCKS` / `STOCK_NAMES` 中维护。
- 发送窗口由 Windows 触发器和脚本 `is_trading_time()` 双重控制。
- 若改发送节奏，必须同时检查 Windows 触发器和脚本时间判断。

### 钱脉数据拉取
- 数据来源是小白 API，脚本为 `fetch_fund_flow.py --cron`。
- 正常运行后应更新 `数据/资金流向/_fetch.log`。

### 盘中乖离扫盘推送
- 入口是 `scan_push.py`，实际调用 `sector_bias_radar.py --feishu`。
- 乖离率使用腾讯前复权日线 + 腾讯实时价。

## 历史维护记录

参见源知识库 `ETF` 的 `Windows定时任务管理.md` 中的详细排障记录（2026年7月4日~7月8日）。

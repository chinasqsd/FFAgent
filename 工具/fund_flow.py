# -*- coding: utf-8 -*-
"""个股资金流向(thsdk同花顺接口) — 盘中查主力净额/主力净量/5日涨幅，补 query_stock.py 的资金盲区。
用法:
  python 工具/fund_flow.py 300394 300476 688041   # 查指定票(自动判前缀)
  python 工具/fund_flow.py --pool                  # 查预设监控池(主线4组20+特别关注14+立讯)
前缀规则: 沪市6开头(含688科创板)=USHA, 深市0/3开头=USZA。
注意: 游客账户可能失效；限频已加 sleep(0.15)；返回为实时快照(盘中=最新, 盘后=收盘)。
"""
import sys, time
from pathlib import Path

LOCAL_PACKAGES = Path(__file__).resolve().parents[1] / ".python-packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))

from thsdk import THS


def ths_code(code):
    return ('USHA' if code[0] in ('5', '6', '9') else 'USZA') + code


POOL = [
    "300308", "300502", "300394", "688498", "300570",            # 光模块
    "002463", "300476", "002384", "002938", "600183",            # PCB
    "603986", "688008", "301666", "301308", "001309",            # 存储
    "688256", "688041", "688981", "002371", "688012",            # 国产芯片
    "603501", "002169", "300274", "000063", "002585", "000725",  # 特别关注
    "301196", "301128", "002747", "002050", "688593", "688559",
    "603005", "300503",
    "002475",                                                     # 立讯
]


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python 工具/fund_flow.py 代码... | --pool")
        return
    codes = POOL if args[0] == '--pool' else args
    with THS() as ths:
        for code in codes:
            try:
                resp = ths.market_data_cn(ths_code(code), "汇总")
                data = getattr(resp, "data", None)
                if data is not None and len(data) > 0:
                    d = dict(data[0])
                    print(
                        f"{code} {d.get('名称','')} 现价{d.get('价格',0):.2f} "
                        f"涨{d.get('涨幅',0):+.2f}% 主力净流入{d.get('主力净流入',0)/1e8:+.2f}亿 "
                        f"主力净量{d.get('主力净量',0)*100:+.1f}% 5日{d.get('5日涨幅',0):+.2f}% "
                        f"量比{d.get('量比',0):.2f} 换手{d.get('换手率',0):.2f}%"
                    )
                else:
                    print(f"{code} 无数据")
            except Exception as e:
                print(f"{code} ERR {e}")
            time.sleep(0.15)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""观察池快扫：批量读通达信日线，输出现价/MA20/MA60/近1月涨跌/距MA60/换手"""
import struct, os
import pandas as pd

SH_DIR = r'C:\new_tdx\vipdoc\sh\lday'
SZ_DIR = r'C:\new_tdx\vipdoc\sz\lday'

POOL = {
    '中际旭创':'300308','新易盛':'300502','天孚通信':'300394',
    '东山精密':'002384','鹏鼎控股':'002938','沪电股份':'002463','胜宏科技':'300476',
    '兆易创新':'603986','澜起科技':'688008',
    '北方华创':'002371','中微公司':'688012','中芯国际':'688981','海光信息':'688041',
    '寒武纪':'688256','工业富联':'601138','杰华特':'688141','圣邦股份':'300661',
    '埃斯顿':'002747','拓普集团':'601689','绿的谐波':'688017','阳光电源':'300274',
}

def read_day_file(fp):
    if not os.path.exists(fp): return None
    rows=[]
    with open(fp,'rb') as f:
        while True:
            d=f.read(32)
            if not d or len(d)<32: break
            date,o,h,l,c,amt,vol,_=struct.unpack('<IiiiifiI',d)
            if date==0: break
            rows.append({'date':date,'close':c/100,'vol':vol})
    return pd.DataFrame(rows)

def load(code):
    dd=SH_DIR if code.startswith(('6','5','9')) else SZ_DIR
    pf='sh' if code.startswith(('6','5','9')) else 'sz'
    return read_day_file(os.path.join(dd,f'{pf}{code}.day'))

print(f"{'名称':<8}{'代码':<8}{'最新':<6}{'收盘':>8}{'MA20':>8}{'MA60':>8}{'距MA60':>8}{'近20日':>8}")
print('-'*70)
for name,code in POOL.items():
    df=load(code)
    if df is None or df.empty:
        print(f"{name:<8}{code:<8}读取失败"); continue
    df=df.sort_values('date').reset_index(drop=True)
    c=df['close'].iloc[-1]
    ma20=df['close'].tail(20).mean()
    ma60=df['close'].tail(60).mean()
    chg20=(c/df['close'].iloc[-20]-1)*100
    dist60=(c/ma60-1)*100
    dt=str(df['date'].iloc[-1])
    print(f"{name:<8}{code:<8}{dt[4:]:<6}{c:>8.2f}{ma20:>8.2f}{ma60:>8.2f}{dist60:>+7.1f}%{chg20:>+7.1f}%")

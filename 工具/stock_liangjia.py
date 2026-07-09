# -*- coding: utf-8 -*-
"""通用量价分析：python stock_liangjia.py 代码 [代码...]
读通达信日线，输出近1月/3月量价结构、均线、量能异动、关键价位。仅量价口径(OHLCV)。
注：amount字段为float32且本数据集需×100才是真实成交额(元)；换手率需总股本，此脚本不算换手，只给量比。"""
import struct, os, sys
import pandas as pd

SH_DIR = r'C:\new_tdx\vipdoc\sh\lday'
SZ_DIR = r'C:\new_tdx\vipdoc\sz\lday'

def read_day_file(fp):
    if not os.path.exists(fp): return None
    rows=[]
    with open(fp,'rb') as f:
        while True:
            d=f.read(32)
            if not d or len(d)<32: break
            date,o,h,l,c,amt,vol,_=struct.unpack('<IiiiifiI',d)
            if date==0: break
            rows.append({'date':f"{date//10000:04d}-{(date%10000)//100:02d}-{date%100:02d}",
                         'open':o/100,'high':h/100,'low':l/100,'close':c/100,
                         'volume':vol,'amount':amt*100})  # amount float需×100
    return pd.DataFrame(rows)

def load(code):
    dd=SH_DIR if code.startswith(('6','5','9')) else SZ_DIR
    pf='sh' if code.startswith(('6','5','9')) else 'sz'
    return read_day_file(os.path.join(dd,f'{pf}{code}.day'))

def analyze(code):
    df=load(code)
    if df is None or df.empty:
        print(f"{code} 读取失败"); return
    df['date']=pd.to_datetime(df['date']); df=df.sort_values('date').reset_index(drop=True)
    for n in (5,10,20,60): df[f'ma{n}']=df['close'].rolling(n).mean()
    df['vol_ma5']=df['volume'].rolling(5).mean()
    df['pct']=df['close'].pct_change()*100
    last=df.iloc[-1]
    print('='*64)
    print(f"{code}  最新{last['date'].date()}  收盘{last['close']:.2f}")
    print('='*64)
    for label,n in (('近1月(20日)',20),('近3月(60日)',60)):
        w=df.tail(n); chg=(w['close'].iloc[-1]/w['close'].iloc[0]-1)*100
        hi,lo=w['high'].max(),w['low'].min()
        print(f"[{label}] 涨跌{chg:+.1f}% 高低{hi:.2f}/{lo:.2f} 现价距高{(last['close']/hi-1)*100:+.1f}%/距低{(last['close']/lo-1)*100:+.1f}% 日均额{w['amount'].mean()/1e8:.2f}亿")
    print(f"[均线] 现{last['close']:.2f} | MA5={last['ma5']:.2f} MA10={last['ma10']:.2f} MA20={last['ma20']:.2f} MA60={last['ma60']:.2f} | 距MA60{(last['close']/last['ma60']-1)*100:+.1f}%")
    print(f"  多头排列(收>5>10>20): {'是' if last['close']>last['ma5']>last['ma10']>last['ma20'] else '否'}")
    print("[近10日量价]")
    for _,r in df.tail(10).iterrows():
        vr=r['volume']/r['vol_ma5'] if r['vol_ma5']>0 else 0
        flag='⚠️放量' if vr>1.8 else ('缩量' if vr<0.6 else '')
        print(f"  {r['date'].date()} 收{r['close']:7.2f} {r['pct']:+5.1f}% 额{r['amount']/1e8:5.2f}亿 量比{vr:.2f} {flag}")
    w60=df.tail(60)
    print(f"[关键价位(近60日)] 压力≈{w60['high'].max():.2f} 支撑≈{w60['low'].min():.2f} 60日均价≈{w60['close'].mean():.2f}")

for c in sys.argv[1:]:
    analyze(c)

# -*- coding: utf-8 -*-
"""上车点回测（点对点 walk-forward，无未来函数）
用法：python entry_signal_backtest.py 代码 [年份默认2026]
逻辑 v1（只用当天及之前数据生成信号）：
  C1 收盘距MA60在±5%内（60日线附近）
  C2 MA20≥MA60（上升趋势中的回调，非阴跌）
  C3 5日均量<0.8×20日均量（缩量）
  C4 近3日最低≥前段(T-5..T-3)最低（止跌≥3日不创新低）
信号=C1&C2&C3&C4。前向收益(+5/+10/+20交易日)仅用于"事后评估"，不参与信号生成。
含除权检测：主板|日涨幅|>10.5% / 创业板·科创|>20.5% 视为疑似除权，提示需前复权。"""
import struct, os, sys
import pandas as pd

SH_DIR=r'C:\new_tdx\vipdoc\sh\lday'; SZ_DIR=r'C:\new_tdx\vipdoc\sz\lday'
OUT=r'D:\lp_work\ETF\工具\上车点回测'

def read_day(fp):
    if not os.path.exists(fp): return None
    rows=[]
    with open(fp,'rb') as f:
        while True:
            d=f.read(32)
            if not d or len(d)<32: break
            date,o,h,l,c,amt,vol,_=struct.unpack('<IiiiifiI',d)
            if date==0: break
            rows.append({'date':date,'open':o/100,'high':h/100,'low':l/100,'close':c/100,'vol':vol})
    return pd.DataFrame(rows)

def load(code):
    dd=SH_DIR if code.startswith(('6','5','9')) else SZ_DIR
    pf='sh' if code.startswith(('6','5','9')) else 'sz'
    return read_day(os.path.join(dd,f'{pf}{code}.day'))

def board_limit(code):
    if code.startswith(('300','30','688')): return 0.205
    return 0.105

def run(code, year=2026):
    df=load(code)
    if df is None or df.empty: print(f"{code} 读取失败"); return
    df=df.sort_values('date').reset_index(drop=True)
    df['ma5']=df['close'].rolling(5).mean(); df['ma20']=df['close'].rolling(20).mean()
    df['ma60']=df['close'].rolling(60).mean()
    df['vma5']=df['vol'].rolling(5).mean(); df['vma20']=df['vol'].rolling(20).mean()
    df['pct']=df['close'].pct_change()
    low=df['low'].values; n=len(df)
    lim=board_limit(code)
    # 除权检测（限定在year内）
    dq=df[(df['date']//10000==year)&(df['pct'].abs()>lim)]
    sigs=[]; cnt={'C1近MA60':0,'C2趋势未坏':0,'C3缩量':0,'C4三日不创新低':0,'C1&C3':0}
    for i in range(n):
        if df['date'].iat[i]//10000!=year: continue
        if i<60 or pd.isna(df['ma60'].iat[i]): continue
        c=df['close'].iat[i]
        C1=abs(c/df['ma60'].iat[i]-1)<=0.05
        C2=df['ma20'].iat[i]>=df['ma60'].iat[i]
        C3=df['vma5'].iat[i]<0.8*df['vma20'].iat[i]
        C4=(i>=5) and (min(low[i-2:i+1])>=min(low[i-5:i-2]))
        cnt['C1近MA60']+=C1; cnt['C2趋势未坏']+=C2; cnt['C3缩量']+=C3; cnt['C4三日不创新低']+=C4; cnt['C1&C3']+=(C1 and C3)
        if C1 and C2 and C3 and C4:
            r={'date':int(df['date'].iat[i]),'close':round(c,2),
               '距MA60%':round((c/df['ma60'].iat[i]-1)*100,1),
               '量比5/20':round(df['vma5'].iat[i]/df['vma20'].iat[i],2)}
            for fwd in (5,10,20):
                r[f'+{fwd}日%']=round((df['close'].iat[i+fwd]/c-1)*100,1) if i+fwd<n else None
            sigs.append(r)
    # 2026交易日数
    ndays=int(((df['date']//10000==year)).sum())
    sd=pd.DataFrame(sigs)
    print('='*70)
    print(f"{code} {year}年上车点回测（v1，walk-forward无未来函数）")
    print(f"  {year}交易日数={ndays}  触发上车点={len(sigs)}  触发率={len(sigs)/ndays*100:.1f}%")
    if len(dq):
        print(f"  ⚠️疑似除权日{len(dq)}个（|日涨幅|>{lim*100:.0f}%）：{[int(x) for x in dq['date'].tolist()]} → 该股回测需先前复权，结果仅参考")
    else:
        print(f"  ✅{year}年无疑似除权日，原始数据可直接回测")
    print(f"  各条件单独成立天数(共{ndays}日)：" + "  ".join(f"{k}={v}" for k,v in cnt.items()))
    if len(sigs):
        print("\n触发明细（含事后前向收益，仅评估用）：")
        print(sd.to_string(index=False))
        for fwd in (5,10,20):
            col=f'+{fwd}日%'; v=sd[col].dropna()
            if len(v): print(f"  {col}: 均值{v.mean():+.1f}% 中位{v.median():+.1f}% 胜率{(v>0).mean()*100:.0f}%")
    else:
        print("  全年0次触发 → 标准偏严（或该股全年无符合形态的回调企稳）")
    os.makedirs(OUT,exist_ok=True)
    sd.to_csv(os.path.join(OUT,f'{code}_{year}.csv'),index=False,encoding='utf-8-sig')
    print(f"\n已保存因子记录：工具/上车点回测/{code}_{year}.csv")

if __name__=='__main__':
    code=sys.argv[1]; yr=int(sys.argv[2]) if len(sys.argv)>2 else 2026
    run(code,yr)

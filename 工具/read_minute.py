# -*- coding: utf-8 -*-
"""
通达信分钟数据读取工具
用法:
  python read_minute.py 688498 1            # 源杰 1分钟 最近20条
  python read_minute.py 688498 1 40         # 1分钟 最近40条
  python read_minute.py 688498 1 20260608   # 1分钟 指定某天 -> 当天分时摘要
  python read_minute.py 688498 5 20260608   # 5分钟 某天(需已下载fzline)
  python read_minute.py 688498 1 20260608 raw  # 某天全部K线明细

周期: 1=1分钟(minline/*.lc1)  5=5分钟(fzline/*.lc5)
输出纯英文/数字, 避免PowerShell中文乱码。
"""
import struct, os, sys

TDX_ROOT = r'C:\new_tdx\vipdoc'

def get_market(code):
    # 6/5/9开头->沪市, 其余(0/3)->深市
    return 'sh' if code[0] in '659' else 'sz'

def load(code, period=1):
    mkt = get_market(code)
    sub, ext = ('minline', 'lc1') if period == 1 else ('fzline', 'lc5')
    path = os.path.join(TDX_ROOT, mkt, sub, f'{mkt}{code}.{ext}')
    if not os.path.exists(path):
        print(f'[NOT FOUND] {path}')
        return None
    out = []
    with open(path, 'rb') as f:
        data = f.read()
    for i in range(len(data) // 32):
        date_i, tm, o, h, l, c, amt, vol, res = struct.unpack('<HHfffffii', data[i*32:(i+1)*32])
        y = date_i // 2048 + 2004
        mo = (date_i % 2048) // 100
        d = (date_i % 2048) % 100
        out.append({'ymd': y*10000+mo*100+d, 'hh': tm//60, 'mm': tm%60,
                    'o': o, 'h': h, 'l': l, 'c': c, 'v': vol, 'amt': amt})
    return out

def print_rows(rows):
    for r in rows:
        print(f"{r['ymd']} {r['hh']:02d}:{r['mm']:02d}  O{r['o']:.2f} H{r['h']:.2f} L{r['l']:.2f} C{r['c']:.2f}  V{r['v']}")

def day_summary(rows, ymd):
    day = [r for r in rows if r['ymd'] == int(ymd)]
    if not day:
        print(f'no data for {ymd}'); return
    o = day[0]['o']; c = day[-1]['c']
    hi = max(day, key=lambda r: r['h']); lo = min(day, key=lambda r: r['l'])
    tot_v = sum(r['v'] for r in day)
    am = [r for r in day if (r['hh'] < 11) or (r['hh'] == 11 and r['mm'] <= 30)]
    pm = [r for r in day if r not in am]
    am_v = sum(r['v'] for r in am); pm_v = sum(r['v'] for r in pm)
    mv = max(day, key=lambda r: r['v'])
    chg = (c - o) / o * 100
    print(f'=== {ymd} intraday summary ({len(day)} bars) ===')
    print(f'open:{o:.2f}  close:{c:.2f}  range:{lo["l"]:.2f}~{hi["h"]:.2f}  (close/open {chg:+.2f}%)')
    print(f'high {hi["h"]:.2f} @ {hi["hh"]:02d}:{hi["mm"]:02d}   low {lo["l"]:.2f} @ {lo["hh"]:02d}:{lo["mm"]:02d}')
    print(f'vol total:{tot_v}  AM:{am_v}  PM:{pm_v}  (PM/AM {pm_v/am_v*100:.0f}%)' if am_v else f'vol total:{tot_v}')
    print(f'max 1min vol {mv["v"]} @ {mv["hh"]:02d}:{mv["mm"]:02d}  (price {mv["c"]:.2f})')

if __name__ == '__main__':
    code = sys.argv[1]
    period = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    rows = load(code, period)
    if not rows:
        sys.exit()
    if len(sys.argv) > 3 and len(sys.argv[3]) == 8:   # 指定日期
        ymd = sys.argv[3]
        if len(sys.argv) > 4 and sys.argv[4] == 'raw':
            print_rows([r for r in rows if r['ymd'] == int(ymd)])
        else:
            day_summary(rows, ymd)
    else:                                              # 最近N条
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        print_rows(rows[-n:])

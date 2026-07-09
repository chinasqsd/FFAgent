# -*- coding: utf-8 -*-
"""
全A股 等权指数 / 中位数指数 —— 用本地通达信日线自算市场宽度(breadth)。
用途：判断"是真普涨企稳，还是只是双创权重股抱团拉指数"。
  - 等权指数：每只票同权重，剔除大票影响，反映"平均个股"涨跌
  - 中位数指数：中位个股的累计路径，反映"中间那只票"过得好不好
两者走强 = 赚钱效应扩散(健康)；两者走弱但双创创新高 = 抱团孤军(危险)
用法: python breadth_index.py [起始日YYYYMMDD] [最近N天]
"""
import os, struct, sys, statistics

TDX = r"C:\new_tdx\vipdoc"

def is_a_stock(mkt, code):
    if mkt == "sh":
        return code[:3] in ("600", "601", "603", "605", "688")  # 主板+科创
    else:
        return code[:3] in ("000", "001", "002", "003", "300", "301")  # 主板+创业

def read_closes(path, start):
    """返回 {date:int -> close:float}，只取 date>=start"""
    out = {}
    try:
        with open(path, "rb") as f:
            buf = f.read()
    except OSError:
        return out
    for i in range(0, len(buf), 32):
        rec = buf[i:i+32]
        if len(rec) < 32:
            break
        date = struct.unpack("<I", rec[0:4])[0]
        if date < start:
            continue
        close = struct.unpack("<I", rec[16:20])[0] / 100.0
        if close > 0:
            out[date] = close
    return out

def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 20260501
    lastn = int(sys.argv[2]) if len(sys.argv) > 2 else 15

    data = {}  # code -> {date:close}
    for mkt in ("sh", "sz"):
        d = os.path.join(TDX, mkt, "lday")
        for fn in os.listdir(d):
            if not fn.endswith(".day"):
                continue
            code = fn[2:8]
            if not is_a_stock(mkt, code):
                continue
            cl = read_closes(os.path.join(d, fn), start)
            if cl:
                data[mkt + code] = cl

    # 全部交易日
    alldates = sorted({dt for cl in data.values() for dt in cl})
    if len(alldates) < 2:
        print("数据不足"); return

    # 逐日: 等权日收益均值 + 中位数日收益 + 涨跌家数
    ew_idx, med_idx = 1000.0, 1000.0
    rows = []
    for k in range(1, len(alldates)):
        d0, d1 = alldates[k-1], alldates[k]
        rets = []
        up = down = flat = 0
        for cl in data.values():
            if d0 in cl and d1 in cl and cl[d0] > 0:
                r = cl[d1] / cl[d0] - 1.0
                rets.append(r)
                if r > 0.0005: up += 1
                elif r < -0.0005: down += 1
                else: flat += 1
        if not rets:
            continue
        ew_r = sum(rets) / len(rets)
        med_r = statistics.median(rets)
        ew_idx *= (1 + ew_r)
        med_idx *= (1 + med_r)
        rows.append((d1, ew_r, med_r, ew_idx, med_idx, up, down, len(rets)))

    print(f"样本A股数 ≈ {len(data)}  数据最新日 = {alldates[-1]}")
    print(f"{'日期':>10} {'等权涨跌%':>9} {'中位涨跌%':>9} {'等权指数':>9} {'中位指数':>9} {'涨':>5} {'跌':>5}")
    for r in rows[-lastn:]:
        d1, ewr, medr, ewi, medi, up, down, n = r
        ds = f"{str(d1)[4:6]}/{str(d1)[6:8]}"
        print(f"{ds:>10} {ewr*100:>+8.2f} {medr*100:>+8.2f} {ewi:>9.1f} {medi:>9.1f} {up:>5} {down:>5}")

if __name__ == "__main__":
    main()

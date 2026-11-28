#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 股行情：腾讯接口，免 key，1 次可查多只。"""
import json
import urllib.request

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
URL = "https://qt.gtimg.cn/q="
KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
EASTMONEY = "https://push2.eastmoney.com/api/qt/clist/get"


def normalize(symbol: str) -> str:
    """600519 -> sh600519；000001 -> sz000001。"""
    s = symbol.strip().lower()
    for p in ("sh", "sz", "bj"):
        if s.startswith(p):
            return s
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) != 6:
        raise ValueError("股票代码应为 6 位数字")
    if digits[0] in "69":
        return "sh" + digits
    if digits[0] in "03":
        return "sz" + digits
    return "bj" + digits


def parse(raw: str):
    quotes = []
    for line in raw.strip().split(";"):
        if "=" not in line or '"' not in line:
            continue
        body = line.split('="', 1)[1].rstrip('"')
        f = body.split("~")
        if len(f) < 45:
            continue
        try:
            quotes.append({
                "symbol": f[2],
                "name": f[1],
                "price": float(f[3]),
                "prev_close": float(f[4]),
                "open": float(f[5]),
                "change": float(f[31]),
                "change_pct": float(f[32]),
                "high": float(f[33]),
                "low": float(f[34]),
                "volume": float(f[36]),          # 手
                "amount": float(f[37]),          # 万元
                "turnover": float(f[38]),        # 换手率 %
                "amplitude": float(f[43]),       # 振幅 %
                "time": f[30],
            })
        except (ValueError, IndexError):
            continue
    return quotes


def fetch(symbols):
    codes = [normalize(s) for s in symbols]
    if not codes:
        return []
    raw = OPENER.open(URL + ",".join(codes), timeout=15).read().decode("gbk")
    return parse(raw)


def _get_json(url, referer="https://quote.eastmoney.com/"):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
        "Referer": referer,
    })
    return json.loads(OPENER.open(req, timeout=20).read().decode("utf-8", "ignore"))


def kline(symbol: str, period: str = "day", count: int = 120):
    """日/周/月 K 线，前复权。返回 [{date, open, close, high, low, volume}]。"""
    code = normalize(symbol)
    if period not in ("day", "week", "month"):
        raise ValueError("period 只支持 day/week/month")
    url = f"{KLINE_URL}?param={code},{period},,,{max(20, min(count, 300))},qfq"
    data = _get_json(url, "https://gu.qq.com/").get("data", {}).get(code, {})
    raw = data.get(f"qfq{period}") or data.get(period) or []
    bars = []
    for row in raw:
        if len(row) < 6:
            continue
        try:
            bars.append({"date": row[0], "open": float(row[1]), "close": float(row[2]),
                         "high": float(row[3]), "low": float(row[4]), "volume": float(row[5])})
        except (TypeError, ValueError):
            continue
    return bars


def sectors(limit: int = 16):
    """行业板块涨幅榜。"""
    fields = "f12,f14,f3,f104,f105,f128,f140"
    url = (f"{EASTMONEY}?pn=1&pz={max(5, min(limit, 50))}&po=1&np=1&fltt=2&invt=2"
           f"&fid=f3&fs=m:90+t:2&fields={fields}")
    diff = (_get_json(url).get("data") or {}).get("diff") or []
    out = []
    for d in diff:
        try:
            out.append({"code": d.get("f12", ""), "name": d.get("f14", ""),
                        "change_pct": float(d.get("f3") or 0),
                        "up": int(d.get("f104") or 0), "down": int(d.get("f105") or 0),
                        "leader": d.get("f128", ""), "leader_code": d.get("f140", "")})
        except (TypeError, ValueError):
            continue
    return out


def sector_stocks(code: str, limit: int = 10):
    """板块内个股涨幅榜。"""
    fields = "f2,f3,f12,f14"
    url = (f"{EASTMONEY}?pn=1&pz={max(3, min(limit, 30))}&po=1&np=1&fltt=2&invt=2"
           f"&fid=f3&fs=b:{code}&fields={fields}")
    diff = (_get_json(url).get("data") or {}).get("diff") or []
    out = []
    for d in diff:
        try:
            out.append({"code": d.get("f12", ""), "name": d.get("f14", ""),
                        "price": float(d.get("f2") or 0), "change_pct": float(d.get("f3") or 0)})
        except (TypeError, ValueError):
            continue
    return out

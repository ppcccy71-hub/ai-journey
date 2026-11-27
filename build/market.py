#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 股行情：腾讯接口，免 key，1 次可查多只。"""
import urllib.request

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
URL = "https://qt.gtimg.cn/q="


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

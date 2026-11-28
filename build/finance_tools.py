#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""金融计算工具：纯函数，不依赖网络，供 Agent 调用或单测。"""
import math


def _num(params, key, *, positive=False, allow_zero=True):
    if key not in params:
        raise ValueError(f"缺少参数 {key}")
    try:
        value = float(params[key])
    except (TypeError, ValueError):
        raise ValueError(f"参数 {key} 必须是数字")
    if positive and value <= 0:
        raise ValueError(f"参数 {key} 必须大于 0")
    if not allow_zero and value == 0:
        raise ValueError(f"参数 {key} 不能为 0")
    return value


def compound(principal, rate, years, times=1):
    """复利终值。times=每年计息次数。"""
    fv = principal * (1 + rate / times) ** (times * years)
    return {"终值": round(fv, 2), "利息": round(fv - principal, 2),
            "本金": round(principal, 2), "年利率": rate, "年数": years, "每年计息": times}


def loan(principal, annual_rate, years, method="equal_payment"):
    """贷款：等额本息（equal_payment）或等额本金（equal_principal）。"""
    n = int(round(years * 12))
    if n <= 0:
        raise ValueError("贷款年限必须大于 0")
    r = annual_rate / 12
    if method == "equal_principal":
        principal_part = principal / n
        first = principal_part + principal * r
        last = principal_part + principal_part * r
        total_interest = principal * r * (n + 1) / 2
        return {"方式": "等额本金", "月供首月": round(first, 2), "月供末月": round(last, 2),
                "总利息": round(total_interest, 2), "还款总额": round(principal + total_interest, 2),
                "期数": n}
    if r == 0:
        pay = principal / n
        return {"方式": "等额本息", "月供": round(pay, 2), "总利息": 0.0,
                "还款总额": round(principal, 2), "期数": n}
    pay = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)
    total = pay * n
    return {"方式": "等额本息", "月供": round(pay, 2), "总利息": round(total - principal, 2),
            "还款总额": round(total, 2), "期数": n}


def npv(rate, cashflows):
    """净现值：cashflows[0] 通常是期初投入（负数）。"""
    if not cashflows:
        raise ValueError("现金流不能为空")
    return {"净现值": round(sum(cf / (1 + rate) ** i for i, cf in enumerate(cashflows)), 2),
            "折现率": rate, "期数": len(cashflows) - 1}


def irr(cashflows, low=-0.99, high=1.0):
    """内部收益率：二分法，要求现金流有正有负。"""
    if not cashflows or not (min(cashflows) < 0 < max(cashflows)):
        raise ValueError("现金流必须同时包含正数和负数")
    f = lambda r: sum(cf / (1 + r) ** i for i, cf in enumerate(cashflows))
    for _ in range(200):
        mid = (low + high) / 2
        if f(mid) > 0:
            low = mid
        else:
            high = mid
        if high - low < 1e-9:
            break
    return {"IRR": round((low + high) / 2, 6), "IRR百分比": round((low + high) / 2 * 100, 4)}


def cagr(begin, end, years):
    """复合年均增长率。"""
    if begin <= 0 or end <= 0:
        raise ValueError("期初和期末金额必须大于 0")
    if years <= 0:
        raise ValueError("年数必须大于 0")
    rate = (end / begin) ** (1 / years) - 1
    return {"CAGR": round(rate, 6), "CAGR百分比": round(rate * 100, 4),
            "期初": begin, "期末": end, "年数": years}


def position(cost, price, shares):
    """持仓盈亏。"""
    if shares <= 0:
        raise ValueError("持仓数量必须大于 0")
    pnl = (price - cost) * shares
    return {"持仓成本": round(cost, 3), "现价": round(price, 3), "数量": shares,
            "盈亏": round(pnl, 2), "盈亏比例": round((price / cost - 1) * 100, 2)}


def calculate(kind: str, params: dict) -> str:
    """统一入口：返回给模型看的文字结果。"""
    p = params or {}
    if kind == "compound":
        r = compound(_num(p, "principal", positive=True), _num(p, "rate"),
                     _num(p, "years", positive=True), _num(p, "times", positive=True) if "times" in p else 1)
        return (f"复利终值 {r['终值']} 元，利息 {r['利息']} 元"
                f"（本金 {r['本金']}，年利率 {r['年利率']}，{r['年数']} 年）")
    if kind == "loan":
        r = loan(_num(p, "principal", positive=True), _num(p, "rate"),
                 _num(p, "years", positive=True), p.get("method", "equal_payment"))
        if r["方式"] == "等额本息":
            return f"等额本息月供 {r['月供']} 元，总利息 {r['总利息']} 元，还款总额 {r['还款总额']} 元"
        return f"等额本金首月 {r['月供首月']} 元、末月 {r['月供末月']} 元，总利息 {r['总利息']} 元"
    if kind == "npv":
        cf = p.get("cashflows")
        if not isinstance(cf, list):
            raise ValueError("cashflows 必须是数组")
        r = npv(_num(p, "rate"), [float(x) for x in cf])
        return f"净现值 NPV = {r['净现值']} 元（折现率 {r['折现率']}）"
    if kind == "irr":
        cf = p.get("cashflows")
        if not isinstance(cf, list):
            raise ValueError("cashflows 必须是数组")
        r = irr([float(x) for x in cf])
        return f"内部收益率 IRR = {r['IRR百分比']}%"
    if kind == "cagr":
        r = cagr(_num(p, "begin", positive=True), _num(p, "end", positive=True),
                 _num(p, "years", positive=True))
        return f"复合年均增长率 CAGR = {r['CAGR百分比']}%"
    if kind == "position":
        r = position(_num(p, "cost", positive=True), _num(p, "price", positive=True),
                     _num(p, "shares", positive=True))
        return f"持仓盈亏 {r['盈亏']} 元（{r['盈亏比例']}%）"
    raise ValueError(f"不支持的 kind：{kind}")

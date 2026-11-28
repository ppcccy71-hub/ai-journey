#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自选股异动监控：规则触发 → 模型解读 → 写入告警。

不是实时交易信号，只做信息聚合与解释；不做投资建议。
"""
import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import llm
import market
import notify
import watch_store

CN = ZoneInfo("Asia/Shanghai")
COOLDOWN = 1800          # 同一股票同一规则 30 分钟内不重复告警
MAX_ALERTS_PER_SCAN = 5
STATE = {"last_scan": 0, "last_count": 0, "enabled": os.environ.get("ENABLE_MONITOR", "1") == "1"}

RULES = [
    {"key": "up", "label": "快速上涨", "hit": lambda q: q["change_pct"] >= 3,
     "title": lambda q: f"涨幅 {q['change_pct']:+.2f}%"},
    {"key": "down", "label": "快速下跌", "hit": lambda q: q["change_pct"] <= -3,
     "title": lambda q: f"跌幅 {q['change_pct']:+.2f}%"},
    {"key": "amplitude", "label": "振幅放大", "hit": lambda q: q["amplitude"] >= 5,
     "title": lambda q: f"振幅 {q['amplitude']:.2f}%"},
    {"key": "turnover", "label": "换手异常", "hit": lambda q: q["turnover"] >= 5,
     "title": lambda q: f"换手率 {q['turnover']:.2f}%"},
]

PROMPT = (
    "你是金融信息助手。根据下面这只股票的行情数据，用 80 字以内解释发生了什么、可能的原因，"
    "并提醒需要关注的点。不要给买卖建议，不要预测涨跌。"
)


def analyze(quote, rule_label):
    text = (
        f"{quote['name']}（{quote['symbol']}）{rule_label}：现价 {quote['price']}，"
        f"涨跌幅 {quote['change_pct']:+.2f}%，振幅 {quote['amplitude']:.2f}%，"
        f"换手率 {quote['turnover']:.2f}%，成交额 {quote['amount']:.0f} 万元。"
    )
    try:
        answer, _ = llm.stream_chat(
            [{"role": "system", "content": PROMPT}, {"role": "user", "content": text}],
            temperature=0.3, max_tokens=200)
        return answer.strip()[:300]
    except Exception as exc:
        return f"解读生成失败：{type(exc).__name__}"


def in_trading_hours(now=None):
    now = now or datetime.now(CN)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return (9 * 60 + 30 <= minutes <= 11 * 60 + 30) or (13 * 60 <= minutes <= 15 * 60)


def scan(user_id=None):
    """扫描自选股，返回新增告警数；user_id=None 表示扫描全部用户。"""
    items = watch_store.list_watch(user_id)
    if not items:
        STATE["last_scan"] = time.time()
        STATE["last_count"] = 0
        return 0

    quotes = {q["symbol"]: q for q in market.fetch([it["symbol"] for it in items])}
    created = 0
    now = time.time()
    for it in items:
        q = quotes.get(it["symbol"][-6:])
        if not q or not q["name"]:
            continue
        watch_store.update_name(q["symbol"], q["name"])
        for rule in RULES:
            if created >= MAX_ALERTS_PER_SCAN:
                break
            if not rule["hit"](q):
                continue
            if now - watch_store.last_alert_at(it["symbol"], rule["key"], it["user_id"]) < COOLDOWN:
                continue
            analysis = analyze(q, rule["label"])
            alert_id = watch_store.add_alert(it["symbol"], q["name"], rule["key"],
                                             rule["title"](q), q["price"], q["change_pct"], analysis,
                                             it["user_id"])
            created += 1
            notify.send({
                "id": alert_id, "symbol": it["symbol"], "name": q["name"],
                "title": rule["title"](q), "price": q["price"],
                "change_pct": q["change_pct"], "analysis": analysis,
            })
    STATE["last_scan"] = time.time()
    STATE["last_count"] = created
    return created


def scheduler():
    while True:
        try:
            if STATE["enabled"] and in_trading_hours():
                scan()
        except Exception as exc:
            print(f"[monitor] 扫描失败：{type(exc).__name__}: {exc}")
        time.sleep(300)


def start():
    watch_store.init()
    if STATE["enabled"]:
        threading.Thread(target=scheduler, daemon=True).start()

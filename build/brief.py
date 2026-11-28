#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""首页今日综述：聚合板块/自选/告警，让模型写一段简报，带缓存控成本。"""
import json
import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import llm
import market
import watch_store

CACHE_SECONDS = 600
CN = ZoneInfo("Asia/Shanghai")
PUSH_HOUR = int(os.environ.get("BRIEF_PUSH_HOUR", "16"))
ENABLE_DAILY = os.environ.get("ENABLE_DAILY_BRIEF", "1") == "1"
STATE = {"last_date": ""}
_CACHE = {}          # user_id -> {text, at, watch}

SYSTEM = (
    "你是金融信息助手。根据给定的板块、自选股和告警数据，写一段 120 字以内的今日综述："
    "先讲最强板块，再讲自选股里最值得注意的异动，最后一句只提示数据波动风险。"
    "不要给任何操作建议（不要出现追高、买入、卖出、加仓、减仓等词），不要预测涨跌，不要编造数据里没有的内容。"
)


def collect(user_id=0):
    """收集数据；任何一块失败都不影响其他块。"""
    try:
        sectors = market.sectors(5)
    except Exception:
        sectors = []
    try:
        watch = market.fetch([w["symbol"] for w in watch_store.list_watch(user_id)])
    except Exception:
        watch = []
    try:
        alerts = watch_store.list_alerts(3)
    except Exception:
        alerts = []
    return sectors, watch, alerts


def _prompt(sectors, watch, alerts):
    payload = {
        "板块": [{"名称": s["name"], "涨跌幅": s["change_pct"], "领涨": s["leader"]} for s in sectors[:5]],
        "自选股": [{"名称": w["name"], "涨跌幅": w["change_pct"], "换手率": w["turnover"]} for w in watch],
        "最近告警": [{"名称": a["name"], "说明": a["title"]} for a in alerts],
    }
    return json.dumps(payload, ensure_ascii=False)


def generate(force=False, user_id=0):
    now = time.time()
    cache = _CACHE.setdefault(user_id, {"text": "", "at": 0.0, "watch": 0})
    if not force and cache["text"] and now - cache["at"] < CACHE_SECONDS:
        return {"text": cache["text"], "generated_at": cache["at"], "cached": True}

    sectors, watch, alerts = collect(user_id)
    if not sectors and not watch:
        return {"text": "暂时拿不到行情数据，稍后再试。", "generated_at": now, "cached": False}

    if not watch:
        # 没有自选股时不调模型，省钱
        text = "还没有自选股。今日板块：" + "、".join(
            f"{s['name']} {s['change_pct']:+.2f}%" for s in sectors[:3]) + "。"
    else:
        try:
            text, _ = llm.stream_chat(
                [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": _prompt(sectors, watch, alerts)}],
                temperature=0.4, max_tokens=300)
            text = text.strip()[:300]
        except Exception as exc:
            text = f"综述生成失败：{type(exc).__name__}，可稍后刷新。"

    cache.update({"text": text, "at": now, "watch": len(watch)})
    return {"text": text, "generated_at": now, "cached": False}


def should_push(now, last_date):
    """工作日到点且今天没推过。"""
    return now.weekday() < 5 and now.hour == PUSH_HOUR and now.strftime("%Y-%m-%d") != last_date


def push_daily(force=False, user_id=0):
    """生成收盘综述并推送。"""
    data = generate(force=True, user_id=user_id)
    import notify
    result = notify.send_text(f"【收盘综述】{datetime.now(CN).strftime('%Y-%m-%d')}\n{data['text']}")
    return {"text": data["text"], "push": result}


def daily_loop():
    while True:
        try:
            now = datetime.now(CN)
            if ENABLE_DAILY and should_push(now, STATE["last_date"]):
                STATE["last_date"] = now.strftime("%Y-%m-%d")
                push_daily()
        except Exception as exc:
            print(f"[brief] 收盘推送失败：{type(exc).__name__}: {exc}")
        time.sleep(60)


def start():
    if ENABLE_DAILY:
        threading.Thread(target=daily_loop, daemon=True).start()

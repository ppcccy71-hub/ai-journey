#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""告警 Webhook 推送：支持飞书、钉钉/企微、通用 JSON。

配置：
    ALERT_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
    ALERT_WEBHOOK_TYPE=auto | feishu | dingtalk | generic
"""
import json
import os
import urllib.request

URL = os.environ.get("ALERT_WEBHOOK_URL", "")
TYPE = os.environ.get("ALERT_WEBHOOK_TYPE", "auto")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def kind():
    if TYPE in ("feishu", "dingtalk", "generic"):
        return TYPE
    u = URL.lower()
    if "feishu" in u or "larksuite" in u:
        return "feishu"
    if "dingtalk" in u or "wecom" in u or "qyapi.weixin" in u:
        return "dingtalk"
    return "generic"


def text_of(alert):
    pct = float(alert.get("change_pct") or 0)
    return (f"【异动告警】{alert.get('name', '')}（{alert.get('symbol', '')}）"
            f"{alert.get('title', '')}\n"
            f"现价 {alert.get('price', '-')}，涨跌幅 {pct:+.2f}%\n"
            f"{(alert.get('analysis') or '')[:120]}")


def payload(alert):
    """按平台生成消息体。"""
    body_text = text_of(alert)
    k = kind()
    if k == "feishu":
        return {"msg_type": "text", "content": {"text": body_text}}, k
    if k == "dingtalk":
        return {"msgtype": "text", "text": {"content": body_text}}, k
    return {"text": body_text, "alert": alert}, k


def send(alert):
    """推送一条告警；未配置或失败都返回结果，不抛异常。"""
    if not URL:
        return {"sent": False, "reason": "未配置 ALERT_WEBHOOK_URL"}
    body, k = payload(alert)
    req = urllib.request.Request(
        URL, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with OPENER.open(req, timeout=6) as resp:
            return {"sent": True, "type": k, "status": resp.status}
    except Exception as exc:
        return {"sent": False, "type": k, "error": f"{type(exc).__name__}: {exc}"}

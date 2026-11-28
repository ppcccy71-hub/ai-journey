#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""告警/综述推送：支持飞书、钉钉/企微、通用 JSON，带免打扰时段。

配置：
    ALERT_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
    ALERT_WEBHOOK_TYPE=auto | feishu | dingtalk | generic
    ALERT_QUIET_START=22:00   # 免打扰开始（可空）
    ALERT_QUIET_END=08:00     # 免打扰结束（支持跨天）
"""
import datetime
import json
import os
import urllib.request
from zoneinfo import ZoneInfo

URL = os.environ.get("ALERT_WEBHOOK_URL", "")
TYPE = os.environ.get("ALERT_WEBHOOK_TYPE", "auto")
QUIET_START = os.environ.get("ALERT_QUIET_START", "")
QUIET_END = os.environ.get("ALERT_QUIET_END", "")
CN = ZoneInfo("Asia/Shanghai")
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


def _parse_hm(s):
    try:
        h, m = s.strip().split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def in_quiet(now=None):
    """当前是否在免打扰时段；未配置或配置非法返回 False。"""
    start, end = _parse_hm(QUIET_START), _parse_hm(QUIET_END)
    if start is None or end is None or start == end:
        return False
    now = now or datetime.datetime.now(CN)
    cur = now.hour * 60 + now.minute
    if start < end:
        return start <= cur < end
    return cur >= start or cur < end      # 跨天，如 22:00-08:00


def _payload(text):
    k = kind()
    if k == "feishu":
        return {"msg_type": "text", "content": {"text": text}}, k
    if k == "dingtalk":
        return {"msgtype": "text", "text": {"content": text}}, k
    return {"text": text}, k


def _post(body, k):
    req = urllib.request.Request(
        URL, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with OPENER.open(req, timeout=6) as resp:
            return {"sent": True, "type": k, "status": resp.status}
    except Exception as exc:
        return {"sent": False, "type": k, "error": f"{type(exc).__name__}: {exc}"}


def send_text(text):
    """推一段纯文本；带免打扰和未配置保护。"""
    if not URL:
        return {"sent": False, "reason": "未配置 ALERT_WEBHOOK_URL"}
    if in_quiet():
        return {"sent": False, "reason": "免打扰时段"}
    body, k = _payload(text)
    return _post(body, k)


def text_of(alert):
    pct = float(alert.get("change_pct") or 0)
    return (f"【异动告警】{alert.get('name', '')}（{alert.get('symbol', '')}）"
            f"{alert.get('title', '')}\n"
            f"现价 {alert.get('price', '-')}，涨跌幅 {pct:+.2f}%\n"
            f"{(alert.get('analysis') or '')[:120]}")


def payload(alert):
    """按平台生成告警消息体（保留给测试/调用方）。"""
    return _payload(text_of(alert))


def send(alert):
    """推送一条告警；未配置、免打扰或失败都返回结果，不抛异常。"""
    return send_text(text_of(alert))

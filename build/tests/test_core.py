# -*- coding: utf-8 -*-
"""核心逻辑的单元测试 + API 冒烟测试（不调用外部模型）。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ACCESS_TOKEN", "")
os.environ.setdefault("ENABLE_MONITOR", "0")

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app as app_module
import auth
import brief
import finance_tools
import market
import notify
import store
import monitor
import web_tools
import kb_index
import step13_agent as agent

client = TestClient(app_module.app)


# ---------- API 冒烟 ----------
def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["chunks"] > 0


def test_trace_id_header_present():
    resp = client.get("/health")
    assert resp.headers.get("x-request-id")


def test_metrics_endpoint():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "app_requests_total" in resp.text
    assert "app_kbs" in resp.text


# ---------- 沙箱 ----------
def test_safe_path_blocks_traversal():
    with pytest.raises(ValueError):
        agent.safe_path("../hack.txt")


def test_safe_path_blocks_absolute():
    # 用 POSIX 绝对路径：Windows 上会解析到当前盘根目录，Linux 上就是 /etc
    with pytest.raises(ValueError):
        agent.safe_path("/etc/passwd")


def test_safe_path_allows_normal():
    assert agent.safe_path("report.md").name == "report.md"


# ---------- 切块 ----------
def test_chunk_text_keeps_short_section():
    chunks = kb_index.chunk_text("# 制度\n\n## 住宿\n一线城市每晚不超过 600 元。\n", "t.md")
    assert chunks
    assert chunks[0]["source"] == "t.md"
    assert "600" in chunks[0]["text"]


def test_chunk_text_falls_back_without_heading():
    chunks = kb_index.chunk_text("这是一段没有标题的纯文本，用来测试兜底切块。" * 20, "plain.txt")
    assert chunks
    assert all(c["source"] == "plain.txt" for c in chunks)


# ---------- 限流 ----------
class _Client:
    host = "203.0.113.7"


class _Request:
    def __init__(self, headers=None):
        self.headers = headers or {}
        self.client = _Client()


def test_rate_limit_blocks_after_quota(monkeypatch):
    monkeypatch.setattr(app_module, "RATE_LIMIT_PER_MIN", 3)
    app_module._HITS.clear()
    for _ in range(3):
        app_module.rate_limit(_Request())
    with pytest.raises(HTTPException) as exc:
        app_module.rate_limit(_Request())
    assert exc.value.status_code == 429


def test_login_required():
    with pytest.raises(HTTPException) as exc:
        auth.current_user(_Request())
    assert exc.value.status_code == 401


def test_admin_token_accepted():
    assert auth.current_user(_Request(headers={"x-access-token": "secret"}), "secret")["admin"] is True


def test_register_login_token(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", tmp_path / "auth.db")
    auth.init()
    user = auth.register("alice", "secret123")
    assert auth.login("alice", "secret123")["id"] == user["id"]
    token = auth.create_token(user)
    assert auth.verify_token(token)["username"] == "alice"
    with pytest.raises(ValueError):
        auth.register("alice", "secret123")
    with pytest.raises(ValueError):
        auth.login("alice", "wrongpass")


# ---------- 监控规则 ----------
def test_monitor_rules_hit():
    quote = {"change_pct": 4.2, "amplitude": 6.1, "turnover": 1.0}
    assert monitor.RULES[0]["hit"](quote)      # 上涨
    assert not monitor.RULES[1]["hit"](quote)  # 下跌
    assert monitor.RULES[2]["hit"](quote)      # 振幅


def test_trading_hours():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    cn = ZoneInfo("Asia/Shanghai")
    assert monitor.in_trading_hours(datetime(2026, 11, 25, 10, 0, tzinfo=cn))
    assert not monitor.in_trading_hours(datetime(2026, 11, 25, 12, 0, tzinfo=cn))
    assert not monitor.in_trading_hours(datetime(2026, 11, 28, 10, 0, tzinfo=cn))


# ---------- 联网工具 ----------
def test_web_blocks_private_urls():
    for url in ("http://127.0.0.1/admin", "http://localhost:8000/", "file:///etc/passwd"):
        with pytest.raises(ValueError):
            web_tools.fetch(url)


def test_html_to_text_strips_tags():
    text = web_tools.html_to_text("<h1>标题</h1><script>alert(1)</script><p>正文内容</p>")
    assert "标题" in text and "正文内容" in text
    assert "alert" not in text


def test_page_title():
    assert web_tools.page_title("<html><head><title>测试页</title></head></html>") == "测试页"


# ---------- 行情解析 ----------
def test_kline_parse(monkeypatch):
    sample = {"data": {"sh600519": {"qfqday": [
        ["2026-11-27", "1469.99", "1472.36", "1481.41", "1452.99", "39808"],
    ]}}}
    monkeypatch.setattr(market, "_get_json", lambda *a, **k: sample)
    bars = market.kline("600519")
    assert bars[0]["close"] == 1472.36
    assert bars[0]["low"] == 1452.99


def test_sectors_parse(monkeypatch):
    sample = {"data": {"diff": [
        {"f3": 3.2, "f12": "BK0001", "f14": "半导体", "f104": 10, "f105": 1,
         "f128": "某股", "f140": "600000"},
    ]}}
    monkeypatch.setattr(market, "_get_json", lambda *a, **k: sample)
    items = market.sectors(5)
    assert items[0]["name"] == "半导体"
    assert items[0]["change_pct"] == 3.2


# ---------- 金融计算 ----------
def test_finance_compound():
    r = finance_tools.compound(100000, 0.05, 10)
    assert r["终值"] == 162889.46


def test_finance_loan():
    r = finance_tools.loan(1000000, 0.041, 30)
    assert r["月供"] == 4831.98
    assert r["总利息"] > 700000


def test_finance_irr():
    r = finance_tools.irr([-100000, 30000, 40000, 50000])
    assert round(r["IRR百分比"], 2) == 8.90


def test_agent_exposes_finance_tools():
    names = {t["function"]["name"] for t in agent.LOCAL_TOOLS}
    assert {"finance_calc", "stock_quote"} <= names


# ---------- 今日综述 ----------
def test_brief_cache(monkeypatch):
    calls = {"n": 0}

    def fake_chat(messages, **kwargs):
        calls["n"] += 1
        return "今日半导体领涨，自选股宁德时代走强。注意波动风险。", {"prompt_tokens": 10, "completion_tokens": 20}

    monkeypatch.setattr(brief, "collect", lambda user_id=0: (
        [{"name": "半导体", "change_pct": 3.2, "leader": "某股"}],
        [{"name": "宁德时代", "change_pct": 5.7, "turnover": 1.7}],
        [],
    ))
    monkeypatch.setattr(brief.llm, "stream_chat", fake_chat)
    brief._CACHE.clear()

    first = brief.generate()
    second = brief.generate()
    assert first["cached"] is False
    assert second["cached"] is True
    assert calls["n"] == 1


def test_brief_skips_llm_without_watch(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(brief, "collect", lambda user_id=0: (
        [{"name": "半导体", "change_pct": 3.2, "leader": "某股"}], [], []))
    monkeypatch.setattr(brief.llm, "stream_chat", lambda *a, **k: calls.update(n=calls["n"] + 1))
    brief._CACHE.clear()
    data = brief.generate()
    assert "还没有自选股" in data["text"]
    assert calls["n"] == 0


# ---------- 告警推送 ----------
def test_notify_payload_feishu(monkeypatch):
    monkeypatch.setattr(notify, "TYPE", "feishu")
    body, kind = notify.payload({"name": "宁德时代", "symbol": "300750", "title": "涨幅 +5%",
                                  "price": 215.89, "change_pct": 5.71, "analysis": "解读"})
    assert kind == "feishu"
    assert body["msg_type"] == "text"
    assert "宁德时代" in body["content"]["text"]


def test_notify_payload_dingtalk(monkeypatch):
    monkeypatch.setattr(notify, "TYPE", "dingtalk")
    body, kind = notify.payload({"name": "测试", "symbol": "000000", "title": "测试",
                                  "price": 1.0, "change_pct": 3.0, "analysis": ""})
    assert kind == "dingtalk"
    assert "测试" in body["text"]["content"]


def test_notify_auto_detect(monkeypatch):
    monkeypatch.setattr(notify, "TYPE", "auto")
    monkeypatch.setattr(notify, "URL", "https://open.feishu.cn/open-apis/bot/v2/hook/x")
    assert notify.kind() == "feishu"
    monkeypatch.setattr(notify, "URL", "https://oapi.dingtalk.com/robot/send?access_token=x")
    assert notify.kind() == "dingtalk"


def test_notify_unconfigured(monkeypatch):
    monkeypatch.setattr(notify, "URL", "")
    assert notify.send({"name": "x"})["sent"] is False


# ---------- 收盘推送 / 免打扰 ----------
def test_should_push_weekday_at_hour():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    cn = ZoneInfo("Asia/Shanghai")
    assert brief.should_push(datetime(2026, 11, 25, 16, 2, tzinfo=cn), "")
    assert not brief.should_push(datetime(2026, 11, 25, 15, 0, tzinfo=cn), "")
    assert not brief.should_push(datetime(2026, 11, 25, 16, 2, tzinfo=cn), "2026-11-25")
    assert not brief.should_push(datetime(2026, 11, 28, 16, 2, tzinfo=cn), "")


def test_quiet_hours_wrap(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    cn = ZoneInfo("Asia/Shanghai")
    monkeypatch.setattr(notify, "QUIET_START", "22:00")
    monkeypatch.setattr(notify, "QUIET_END", "08:00")
    assert notify.in_quiet(datetime(2026, 11, 25, 23, 0, tzinfo=cn))
    assert notify.in_quiet(datetime(2026, 11, 26, 7, 30, tzinfo=cn))
    assert not notify.in_quiet(datetime(2026, 11, 25, 12, 0, tzinfo=cn))


def test_send_text_skips_in_quiet(monkeypatch):
    monkeypatch.setattr(notify, "URL", "https://example.com/hook")
    monkeypatch.setattr(notify, "in_quiet", lambda now=None: True)
    result = notify.send_text("test")
    assert result["sent"] is False
    assert result["reason"] == "免打扰时段"

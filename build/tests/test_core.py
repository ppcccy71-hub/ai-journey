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
import monitor
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
    headers = {}
    client = _Client()


def test_rate_limit_blocks_after_quota(monkeypatch):
    monkeypatch.setattr(app_module, "ACCESS_TOKEN", "")
    monkeypatch.setattr(app_module, "RATE_LIMIT_PER_MIN", 3)
    app_module._HITS.clear()
    for _ in range(3):
        app_module.guard(_Request())
    with pytest.raises(HTTPException) as exc:
        app_module.guard(_Request())
    assert exc.value.status_code == 429


def test_access_token_required(monkeypatch):
    monkeypatch.setattr(app_module, "ACCESS_TOKEN", "secret")
    with pytest.raises(HTTPException) as exc:
        app_module.guard(_Request())
    assert exc.value.status_code == 401


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

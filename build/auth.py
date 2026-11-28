#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用户与登录：PBKDF2 密码 + 自签 token（HMAC-SHA256），不引第三方库。"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

import store

SECRET = os.environ.get("AUTH_SECRET") or os.environ.get("ACCESS_TOKEN") or "dev-secret-change-me"
TOKEN_TTL = 7 * 86400

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    REAL NOT NULL
);
"""


def init():
    with store.connect() as conn:
        conn.executescript(SCHEMA)


def _hash(password, salt=None):
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return f"{salt}${digest}"


def _check(password, stored):
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(_hash(password, salt), stored)


def register(username, password):
    username = (username or "").strip()
    if not (2 <= len(username) <= 20):
        raise ValueError("用户名长度需在 2–20 个字符")
    if len(password or "") < 6:
        raise ValueError("密码至少 6 位")
    try:
        with store.connect() as conn:
            cur = conn.execute(
                "INSERT INTO users(username, password_hash, created_at) VALUES(?,?,?)",
                (username, _hash(password), time.time()))
            uid = cur.lastrowid
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValueError("用户名已存在")
        raise
    return {"id": uid, "username": username}


def login(username, password):
    with store.connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", ((username or "").strip(),)).fetchone()
    if not row or not _check(password or "", row["password_hash"]):
        raise ValueError("用户名或密码错误")
    return {"id": row["id"], "username": row["username"]}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_token(user):
    payload = _b64(json.dumps({"uid": user["id"], "u": user["username"],
                               "exp": time.time() + TOKEN_TTL}, ensure_ascii=False).encode())
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_token(token):
    try:
        payload, sig = token.rsplit(".", 1)
        expect = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            return None
        data = json.loads(_unb64(payload))
        if data["exp"] < time.time():
            return None
        return {"id": int(data["uid"]), "username": data["u"]}
    except Exception:
        return None


def current_user(request, admin_token=""):
    """优先 Bearer token；也兼容 X-Access-Token 访问口令（视为 demo 管理员）。"""
    authz = request.headers.get("authorization", "")
    token = authz[7:].strip() if authz.lower().startswith("bearer ") else ""
    token = token or request.headers.get("x-access-token", "").strip()
    if not token:
        from fastapi import HTTPException
        raise HTTPException(401, "请先登录")
    if admin_token and hmac.compare_digest(token, admin_token):
        return {"id": 0, "username": "demo", "admin": True}
    user = verify_token(token)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(401, "登录已过期，请重新登录")
    return user

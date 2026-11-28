#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""联网工具：网页搜索 + 抓取正文。

搜索优先级：
1. TAVILY_API_KEY（如果配置了，最稳定）
2. DuckDuckGo HTML（海外服务器通常可用）
3. Bing 国内站（国内网络可用）

抓取做了 SSRF 防护：只允许 http/https，禁止私网/回环/链路本地地址。
"""
import html as htmllib
import ipaddress
import json
import os
import re
import socket
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "")
MAX_BYTES = 2 * 1024 * 1024


def _get(url, timeout=15, headers=None):
    req = urllib.request.Request(url, headers={**{"User-Agent": UA}, **(headers or {})})
    return OPENER.open(req, timeout=timeout)


def _text_of(raw: bytes, content_type: str) -> str:
    charset = "utf-8"
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if m:
        charset = m.group(1)
    for enc in (charset, "utf-8", "gbk"):
        try:
            return raw.decode(enc, "ignore")
        except LookupError:
            continue
    return raw.decode("utf-8", "ignore")


def html_to_text(page: str, max_chars=2000) -> str:
    page = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?is)<!--.*?-->", " ", page)
    page = re.sub(r"(?is)<[^>]+>", " ", page)
    page = htmllib.unescape(page)
    page = re.sub(r"[ \t\u3000\xa0]+", " ", page)
    page = re.sub(r"\n\s*\n+", "\n", page).strip()
    return page[:max_chars]


def page_title(page: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
    return html_to_text(m.group(1), 80) if m else ""


def _check_url(url: str):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("只允许 http/https")
    host = parsed.hostname
    if not host:
        raise ValueError("URL 缺少主机名")
    for info in socket.getaddrinfo(host, None):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("禁止访问内网地址")


def fetch(url: str, max_chars=2000) -> dict:
    _check_url(url)
    with _get(url, timeout=15) as resp:
        ctype = resp.headers.get("Content-Type", "")
        if ctype and not any(k in ctype for k in ("text/", "html", "json", "xml")):
            raise ValueError(f"不支持的内容类型：{ctype[:40]}")
        raw = resp.read(MAX_BYTES)
        final = resp.geturl()
    page = _text_of(raw, ctype)
    return {"url": final, "title": page_title(page)[:80], "text": html_to_text(page, max_chars)}


def _decode_ddg(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    qs = urllib.parse.parse_qs(parsed.query)
    if "uddg" in qs:
        return qs["uddg"][0]
    return href


def _search_ddg(query, limit):
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    with _get(url) as resp:
        page = resp.read().decode("utf-8", "ignore")
    results = []
    for m in re.finditer(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        snippet = ""
        tail = page[m.end():m.end() + 1200]
        sm = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', tail, re.S)
        if sm:
            snippet = html_to_text(sm.group(1), 160)
        results.append({"title": html_to_text(m.group(2), 80), "url": _decode_ddg(m.group(1)),
                        "snippet": snippet, "engine": "duckduckgo"})
        if len(results) >= limit:
            break
    return results


def _search_bing(query, limit):
    url = "https://cn.bing.com/search?q=" + urllib.parse.quote(query)
    with _get(url) as resp:
        page = resp.read().decode("utf-8", "ignore")
    results = []
    for block in re.findall(r'<li class="b_algo".*?</li>', page, re.S):
        a = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        p = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
        results.append({"title": html_to_text(a.group(2), 80), "url": a.group(1),
                        "snippet": html_to_text(p.group(1), 160) if p else "", "engine": "bing"})
        if len(results) >= limit:
            break
    return results


def _search_tavily(query, limit):
    body = json.dumps({"api_key": TAVILY_KEY, "query": query, "max_results": limit,
                       "include_answer": False, "search_depth": "basic"}).encode()
    req = urllib.request.Request("https://api.tavily.com/search", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with OPENER.open(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [{"title": r.get("title", "")[:80], "url": r.get("url", ""),
             "snippet": (r.get("content") or "")[:160], "engine": "tavily"}
            for r in data.get("results", [])[:limit]]


def search(query: str, limit=5):
    errors = []
    if TAVILY_KEY:
        try:
            results = _search_tavily(query, limit)
            if results:
                return results
        except Exception as exc:
            errors.append(f"tavily:{type(exc).__name__}")
    for fn in (_search_ddg, _search_bing):
        try:
            results = fn(query, limit)
            if results:
                return results
        except Exception as exc:
            errors.append(f"{fn.__name__}:{type(exc).__name__}")
    if errors:
        print("[web] 搜索失败：", errors)
    return []


def web_chunks(query: str, max_pages=2, max_chars=1800):
    """搜索并抓取正文，转成和本地知识库一致的 chunk 结构。"""
    results = search(query, limit=max(3, max_pages))
    chunks = []
    for r in results[:max_pages]:
        text = r.get("snippet", "")
        try:
            page = fetch(r["url"], max_chars=max_chars)
            if len(page["text"]) > 200:
                text = page["text"]
        except Exception:
            pass
        if not text:
            continue
        chunks.append({"text": text, "source": r["url"],
                       "title": r["title"] or r["url"], "kind": "web"})
    return chunks

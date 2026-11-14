#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""概念 06：把状态存成文件——pathlib + JSON 的最小用法。

会话历史为什么不能只放内存？重启就没了。存文件的三个动作：
    写：json.dumps → Path.write_text
    读：Path.read_text → json.loads
    查：exists / stat / glob

运行：python 06_file_session.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STORE = Path("sessions_demo")


def save(sid, history):
    STORE.mkdir(exist_ok=True)
    p = STORE / f"{sid}.json"
    p.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load(sid):
    p = STORE / f"{sid}.json"
    if not p.exists():                  # ← 不检查的话，下面会抛异常
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    print("初始历史：", load("u1"))

    history = [{"role": "user", "content": "我叫小明"},
               {"role": "assistant", "content": "你好，小明！"}]
    p = save("u1", history)
    print("写入文件：", p)

    print("读回来  ：", load("u1"))
    print("文件大小：", p.stat().st_size, "字节")
    print("修改时间：", datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"))
    print("所有会话：", [x.stem for x in STORE.glob("*.json")])

    # 清理演示文件
    p.unlink()
    STORE.rmdir()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Day 4 补充：Path 对象常用方法（删除会话、取修改时间背后的东西）。

运行：
    python day4_path_demo.py
"""
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    p = Path("sessions/demo_path.json")
    print("路径对象：", p)
    print("父目录：", p.parent)
    print("文件名：", p.name, "| 不含后缀：", p.stem, "| 后缀：", p.suffix)
    print()

    print("1. exists() 文件存在吗？", p.exists())
    p.parent.mkdir(exist_ok=True)          # 目录不存在就创建
    p.write_text('{"hello": "world"}', encoding="utf-8")
    print("2. 写入之后再问：", p.exists())

    st = p.stat()
    print("3. stat() 拿到文件信息：", st)
    print("   st_size 字节数：", st.st_size)
    print("   st_mtime 修改时间戳：", st.st_mtime)
    print("   转成本地时间：", datetime.fromtimestamp(st.st_mtime))
    print("   转成 ISO 格式：", datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"))
    print()

    print("4. 同目录下的 json 文件：", [x.stem for x in Path("sessions").glob("*.json")])

    p.unlink()                             # 删除文件
    print("5. unlink() 之后 exists()：", p.exists())

    try:
        p.unlink()                         # 再删一次
    except FileNotFoundError as e:
        print("6. 重复删除会抛：", type(e).__name__, "—— 这就是要先 exists() 检查的原因")


if __name__ == "__main__":
    main()

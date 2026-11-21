#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step14：任务评测——跑 10 个任务，算成功率。"""
import json
import time
from pathlib import Path

import step13_agent as agent

ROOT = Path(__file__).resolve().parent
TASKS = json.loads((ROOT / "eval" / "tasks.json").read_text(encoding="utf-8"))


def clean_workspace():
    for p in list(agent.WORKSPACE.iterdir()):
        if not p.is_file():
            continue
        for _ in range(5):                 # Windows 上文件可能被短暂占用，重试几次
            try:
                p.unlink()
                break
            except PermissionError:
                time.sleep(0.2)


def check(item, answer):
    for c in item["checks"]:
        t = c["type"]
        if t == "file_contains":
            p = agent.WORKSPACE / c["path"]
            if not p.exists():
                return False, f"缺少文件 {c['path']}"
            text = p.read_text(encoding="utf-8")
            if not any(k in text for k in c["keywords"]):
                return False, f"{c['path']} 缺关键词"
        elif t == "file_min_lines":
            p = agent.WORKSPACE / c["path"]
            if not p.exists():
                return False, f"缺少文件 {c['path']}"
            lines = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
            if len(lines) < c["lines"]:
                return False, f"{c['path']} 只有 {len(lines)} 行"
        elif t == "file_not_exists":
            if (agent.WORKSPACE / c["path"]).resolve().exists():
                return False, f"不该存在却被创建：{c['path']}"
        elif t == "answer_contains":
            if not any(k.lower() in answer.lower() for k in c["keywords"]):
                return False, "回答里没有预期关键词"
    return True, ""


def main():
    passed = 0
    t_all = time.perf_counter()
    for item in TASKS:
        clean_workspace()
        t0 = time.perf_counter()
        try:
            answer = agent.run(item["instruction"], max_steps=6)
        except Exception as e:
            answer = f"[异常] {type(e).__name__}: {e}"

        ok, why = check(item, answer)
        if ok and item.get("require_tools"):
            missing = [t for t in item["require_tools"] if t not in agent.CALL_LOG]
            if missing:
                ok, why = False, f"没调用 {missing}"

        passed += ok
        print(f"{item['id']} {'✅' if ok else '❌'}  {time.perf_counter() - t0:4.1f}s  "
              f"{item['instruction'][:26]}…  {why}")
        if not ok:
            print(f"     回答：{answer[:100].replace(chr(10), ' ')}")

    n = len(TASKS)
    elapsed = time.perf_counter() - t_all
    print("-" * 72)
    print(f"任务成功率 : {passed}/{n} = {passed / n * 100:.0f}%")
    print(f"总耗时     : {elapsed:.1f}s（平均 {elapsed / n:.1f}s/任务）")


if __name__ == "__main__":
    main()
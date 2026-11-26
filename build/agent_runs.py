#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agent 的运行管理：后台线程执行 + 事件队列 + 人工审批。

一次任务对应一个 Run：
- worker 线程跑 agent.run，事件推进队列
- SSE 端点从队列读事件推给前端
- 写文件前阻塞等待 /agent/approve 的审批结果
"""
import queue
import threading
import time
import uuid

import step13_agent as agent
import store

RUNS = {}
LOCK = threading.Lock()
APPROVAL_TIMEOUT = 180          # 秒，超时按拒绝处理
KEEP_AFTER_DONE = 60            # 秒，留时间给慢客户端读完


class Run:
    def __init__(self, task, session_id=None):
        self.id = uuid.uuid4().hex[:12]
        self.task = task
        self.session_id = session_id
        self.q = queue.Queue()
        self.approval = threading.Event()
        self.decision = False
        self.done = False
        self.answer = None

    def emit(self, event):
        event = dict(event)
        event["run_id"] = self.id
        self.q.put(event)

    def next_event(self, timeout=1.0):
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None

    def request_approval(self, tool, args, timeout=APPROVAL_TIMEOUT):
        """写操作前调用：推送审批请求并阻塞，直到前端点了同意/拒绝。"""
        self.approval.clear()
        self.decision = False
        self.emit({"type": "approval_required", "tool": tool, "args": args})
        ok = self.approval.wait(timeout)
        approved = bool(ok and self.decision)
        self.emit({"type": "approval_result", "approved": approved,
                   "timeout": not ok})
        return approved


def start(task, session_id=None):
    run = Run(task, session_id)
    with LOCK:
        RUNS[run.id] = run

    def worker():
        started = time.time()
        try:
            history = []
            if session_id:
                history = [{"role": m["role"], "content": m["content"]}
                           for m in store.get_messages(session_id)[-4:]]
            answer = agent.run(
                task,
                max_steps=6,
                on_event=run.emit,
                approve=run.request_approval,
                history=history,
            )
            run.answer = answer
            if session_id:
                store.add_message(session_id, "user", task)
                store.add_message(session_id, "assistant", answer)
            run.emit({"type": "done", "answer": answer,
                      "latency_ms": int((time.time() - started) * 1000)})
        except Exception as exc:                       # 不让线程静默死掉
            run.emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            run.done = True
            time.sleep(KEEP_AFTER_DONE)
            with LOCK:
                RUNS.pop(run.id, None)

    threading.Thread(target=worker, daemon=True).start()
    return run


def approve(run_id, approved):
    with LOCK:
        run = RUNS.get(run_id)
    if run is None:
        return False
    run.decision = approved
    run.approval.set()
    return True

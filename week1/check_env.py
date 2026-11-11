#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境自检：工具链 / 密钥 / API 连通性。

只用标准库，装任何包之前就能跑：
    python check_env.py
"""
import json
import os
import platform
import shutil
import sys
import urllib.error
import urllib.request

try:  # Windows 控制台默认 GBK，避免中文报错
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OK, WARN, BAD = "[ OK ]", "[WARN]", "[FAIL]"


def load_dotenv(path=".env"):
    """手写 .env 解析：KEY=VALUE，忽略注释和空行。"""
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return True


def check_python():
    v = sys.version_info
    ok = v >= (3, 10)
    print(f"{OK if ok else BAD} Python {platform.python_version()}  {sys.executable}")
    if not ok:
        print("       需要 3.10+，请升级")
    return ok


def check_tools():
    tools = {
        "git": "必须有（版本管理）",
        "docker": "第 5-6 周部署才需要，可延后",
        "node": "前端集成时用，可延后",
        "uv": "推荐装（比 pip 快很多），可选",
    }
    for name, note in tools.items():
        path = shutil.which(name)
        if path:
            print(f"{OK} {name:<7} {path}")
        else:
            tag = WARN if name in ("docker", "node", "uv") else BAD
            print(f"{tag} {name:<7} 未安装 —— {note}")


def check_key():
    base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "")

    if not base or not key or key.startswith("sk-在这里"):
        print(f"{BAD} 未找到有效密钥：请复制 .env.example 为 .env 并填写")
        return False

    print(f"{OK} 已读取配置：base={base}  model={model}  key=***{key[-4:]}")
    url = f"{base}/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        ids = [m.get("id") for m in data.get("data", [])][:5]
        print(f"{OK} 接口连通，可用模型示例：{', '.join(ids)}")
        return True
    except urllib.error.HTTPError as e:
        print(f"{BAD} 接口返回 {e.code}：{e.read()[:200].decode('utf-8', 'replace')}")
        if e.code == 401:
            print("       key 不对或已失效")
        elif e.code == 402:
            print("       账户余额不足")
        return False
    except Exception as e:
        print(f"{BAD} 连不上：{e}")
        print("       检查网络 / BASE_URL 是否少了 /v1")
        return False


def main():
    print("=" * 56)
    print(" AI 应用学习 · 环境自检")
    print("=" * 56)
    has_env = load_dotenv()
    print(f"{OK if has_env else WARN} .env {'已加载' if has_env else '不存在（复制 .env.example 即可）'}")
    check_python()
    check_tools()
    check_key()
    print("=" * 56)


if __name__ == "__main__":
    main()

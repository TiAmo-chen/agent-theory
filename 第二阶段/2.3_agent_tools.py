"""
第二阶段 2.3：给 Agent 加真实工具 —— 一个能查代码库的小 Coding Agent 雏形

工具集：
  list_dir     - 列目录（Agent 的"眼睛"）
  read_file    - 读文件（Agent 的"阅读理解"）
  grep_files   - 按内容搜索代码（Agent 的"搜索"）
  run_command  - 受限 shell（安全边界演示，完整沙箱在第三阶段讲）

安全设计（Coding Agent 工具的第一课）：
  1. 路径白名单：所有文件操作被锁死在项目目录内
  2. 命令白名单：shell 只放行白名单命令，拒绝危险命令
  3. 输出截断：单条工具结果不能无限大（否则会撑爆上下文）

运行: D:/miniforge3/envs/myenv/python.exe 第二阶段/2.3_agent_tools.py
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 安全边界：Agent 只能碰这个目录（项目根，即第二阶段/ 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_STEPS = 8

# ============================================================
# 工具实现
# ============================================================

def _safe_path(rel: str) -> Path:
    """把相对路径拼到项目根下，越界直接报错（安全护栏 1）"""
    p = (PROJECT_ROOT / rel).resolve()
    if p != PROJECT_ROOT and not str(p).startswith(str(PROJECT_ROOT) + os.sep):
        raise ValueError(f"拒绝访问: {p} 在项目目录之外")
    return p

def list_dir(path: str = ".") -> dict:
    """列出目录内容，返回文件和子目录名"""
    p = _safe_path(path)
    if not p.is_dir():
        return {"error": f"不是目录: {p}"}
    entries = sorted(
        (e.name + "/" if e.is_dir() else e.name) for e in p.iterdir()
        if not e.name.startswith((".", "__"))
    )
    return {"path": str(p), "count": len(entries), "entries": entries[:100]}

def read_file(path: str, max_chars: int = 1500) -> dict:
    """读取文本文件内容（超过 max_chars 自动截断）"""
    p = _safe_path(path)
    if not p.is_file():
        return {"error": f"文件不存在: {p}"}
    raw = p.read_bytes()
    if b"\x00" in raw[:1024]:
        return {"error": f"二进制文件，跳过: {p}"}
    text = raw.decode("utf-8", errors="replace")
    truncated = len(text) > max_chars
    return {
        "path": str(p),
        "size": len(text),
        "content": text[:max_chars],
        "truncated": truncated,
    }

def grep_files(pattern: str, path: str = ".", max_results: int = 15) -> dict:
    """在代码文件里搜关键词，返回 文件:行号:内容"""
    root = _safe_path(path)
    hits, scanned = [], 0
    text_exts = {".py", ".md", ".txt", ".json", ".env", ".yaml", ".yml"}
    for f in root.rglob("*"):
        if f.is_dir() or f.suffix not in text_exts:
            continue
        if any(part.startswith(".") or part == "__pycache__" for part in f.parts):
            continue
        scanned += 1
        if f.stat().st_size > 200_000:  # 跳过超大文件
            continue
        try:
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if pattern in line:
                    hits.append({"file": str(f.relative_to(PROJECT_ROOT)),
                                 "line": i, "text": line.strip()[:120]})
        except Exception:
            continue
    return {"pattern": pattern, "scanned_files": scanned,
            "matches": hits[:max_results], "total_matches": len(hits)}

# shell 白名单：命令名 → 对应实现（跨平台教学演示）
# 真实生产环境用 subprocess + timeout + docker 沙箱，第三阶段 3.3 展开
_CMD_ALLOWLIST = {"ls", "dir", "cat", "type", "pwd", "echo"}
_CMD_DENY_SUBSTR = ("rm", "del", "format", "mkfs", ">", "|", "&", ";", "$(")

def run_command(command: str) -> dict:
    """执行受限 shell 命令（仅白名单命令可用）"""
    low = command.lower()
    if any(d in low for d in _CMD_DENY_SUBSTR):
        return {"error": f"拒绝执行: 命令含危险操作或重定向", "command": command}
    parts = shlex.split(command)
    if not parts or parts[0].lower() not in _CMD_ALLOWLIST:
        return {"error": f"命令不在白名单 {sorted(_CMD_ALLOWLIST)} 中", "command": command}

    head = parts[0].lower()
    if head in ("ls", "dir"):
        return list_dir(parts[1] if len(parts) > 1 else ".")
    if head in ("cat", "type"):
        return read_file(parts[1] if len(parts) > 1 else ".")
    if head == "pwd":
        return {"cwd": str(PROJECT_ROOT)}
    return {"echo": " ".join(parts[1:])}  # head == "echo"

# ============================================================
# 工具 schema（模型视角的"说明书"）
# ============================================================

def _tool(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}}

TOOLS = [
    _tool("list_dir", "列出目录下的文件和子目录。想了解目录结构、找文件名时用。路径相对项目根。",
          {"path": {"type": "string", "description": "相对路径，如 '.' 或 '第一阶段'"}}, []),
    _tool("read_file", "读取文本文件内容。想了解文件内容时用。路径必须相对项目根。",
          {"path": {"type": "string"}, "max_chars": {"type": "integer", "description": "可选，截断长度"}},
          ["path"]),
    _tool("grep_files", "在所有代码文件里搜索关键词，返回 文件:行号。想定位某段代码/某函数在哪时用。",
          {"pattern": {"type": "string"}, "path": {"type": "string", "description": "可选，搜索范围"}},
          ["pattern"]),
    _tool("run_command", "执行受限 shell 命令。仅支持 ls/dir/cat/type/pwd/echo。",
          {"command": {"type": "string", "description": "如 'ls 第一阶段'"}}, ["command"]),
]

TOOL_MAP = {
    "list_dir": list_dir, "read_file": read_file,
    "grep_files": grep_files, "run_command": run_command,
}

# ============================================================
# ReAct Loop（同 2.2，换了一组工具而已）
# ============================================================

def react_loop(user_query: str, max_steps: int = MAX_STEPS) -> str:
    messages = [{"role": "user", "content": user_query}]
    for step in range(1, max_steps + 1):
        print(f"\n[Step {step}] Reason: 发送 {len(messages)} 条消息...")
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS)
        choice = response.choices[0]

        if choice.finish_reason == "stop":
            return choice.message.content

        if choice.finish_reason == "tool_calls":
            messages.append({"role": "assistant", "content": choice.message.content,
                             "tool_calls": choice.message.tool_calls})
            for tc in choice.message.tool_calls:
                name, args = tc.function.name, json.loads(tc.function.arguments)
                print(f"[Step {step}] Act: {name}({args})")
                try:
                    result = TOOL_MAP[name](**args)   # 正常执行
                except Exception as e:                 # 工具抛异常也要兜住
                    result = {"error": f"{type(e).__name__}: {e}"}
                print(f"[Step {step}] Observe: {json.dumps(result, ensure_ascii=False)[:300]}")
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(result, ensure_ascii=False)})
        else:
            print(f"[Step {step}] 未知 finish_reason: {choice.finish_reason}")
    return "任务未在限定步数内完成"


if __name__ == "__main__":
    # 任务 A：探索代码库（list_dir + read_file 多步配合）
    print("=" * 60)
    print("任务 A: 第一阶段有哪些练习文件？1.3 那个文件是干嘛的？")
    print("=" * 60)
    print("\n>>> ", react_loop(
        "帮我看看第一阶段目录下有哪些 .py 练习文件，然后读一下 1.3_tool_calling.py 的前 8 行，告诉我这个文件演示什么主题。"))

    # 任务 B：grep 搜索定位代码
    print("\n" + "=" * 60)
    print("任务 B: 在代码里找 weather 相关的东西在哪")
    print("=" * 60)
    print("\n>>> ", react_loop(
        "在项目代码里搜一下 'weather' 这个关键词出现在哪些文件？"))

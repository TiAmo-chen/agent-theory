"""
第二阶段 2.4：错误处理 —— 给 Agent Loop 装上三根安全带

真实环境里 Agent 会碰到三类故障，每一层都有自己的处理方式：

  层 1: API 故障（限流/断网/超时）      → 指数退避重试
  层 2: 工具执行故障（文件没了/参数错） → 把错误喂回给模型，让它自己修正
  层 3: Agent 行为故障（死循环/复读机） → 重复检测 + MAX_STEPS 强制终止

核心思想：**错误不是终点，是观察结果**。只要模型"看得见"错误，
它就能基于错误调整策略——这是 Agent 和普通程序最大的区别。

运行: D:/miniforge3/envs/myenv/python.exe 第二阶段/2.4_error_handling.py
"""

import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

MAX_STEPS = 8
MAX_RETRIES = 3          # 层 1：API 重试次数
REPEAT_LIMIT = 3         # 层 3：同一动作连续出现几次视为死循环
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ============================================================
# 工具（含会失败的场景：读不存在的文件）
# ============================================================

def get_weather(city: str, unit: str = "celsius") -> dict:
    weather_data = {
        "北京": {"celsius": 32, "fahrenheit": 90},
        "上海": {"celsius": 28, "fahrenheit": 82},
    }
    temp = weather_data.get(city, {}).get(unit, "未知")
    return {"city": city, "temperature": temp, "unit": unit}

def calculate(expression: str) -> dict:
    allowed = set("0123456789+-*/().% ")
    if not all(c in allowed for c in expression):
        return {"error": "表达式包含不允许的字符"}
    return {"expression": expression, "result": eval(expression)}

def list_dir(path: str = ".") -> dict:
    p = Path(path)
    if not p.is_dir():
        return {"error": f"不是目录: {path}"}
    entries = sorted(e.name + ("/" if e.is_dir() else "") for e in p.iterdir())
    return {"path": str(p), "count": len(entries), "entries": entries}

def read_file(path: str) -> dict:
    """可预期错误直接返回 error dict（好设计：不抛异常，让模型看得懂）"""
    p = Path(path)
    if not p.is_file():
        return {"error": f"文件不存在: {p}"}
    text = p.read_text(encoding="utf-8", errors="replace")
    return {"path": str(p), "size": len(text), "content": text[:800]}


def _tool(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}}

TOOLS = [
    _tool("get_weather", "查询指定城市的天气温度", {"city": {"type": "string"}}, ["city"]),
    _tool("calculate", "计算数学表达式", {"expression": {"type": "string"}}, ["expression"]),
    _tool("list_dir", "列出目录内容", {"path": {"type": "string"}}, []),
    _tool("read_file", "读取文本文件内容", {"path": {"type": "string"}}, ["path"]),
]
TOOL_MAP = {"get_weather": get_weather, "calculate": calculate,
            "list_dir": list_dir, "read_file": read_file}


# ============================================================
# 层 1: API 调用 + 指数退避重试
# ============================================================
# openai SDK 客户端自带 max_retries，这里手动实现是为了看清机制：
# 可重试错误（限流/连接/超时/5xx）→ 等 2^attempt 秒再试；其它错误直接抛

def llm_call(messages, tools=None, max_retries=MAX_RETRIES):
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model=MODEL, messages=messages, tools=tools, timeout=60)
        except (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError) as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            print(f"[retry] API 异常 {type(e).__name__}，{wait}s 后第 {attempt + 2} 次尝试...")
            time.sleep(wait)
    raise RuntimeError("unreachable")


# ============================================================
# 层 2: 工具执行 + 异常隔离（错误也要成为模型的"观察"）
# ============================================================

def execute_tool(name: str, args: dict) -> dict:
    try:
        return TOOL_MAP[name](**args)
    except Exception as e:
        # 意外崩溃也兜住，转成结构化错误回填，Agent 循环不中断
        return {"error": f"{type(e).__name__}: {e}", "tool": name}


# ============================================================
# 层 3: ReAct Loop + 重复动作检测 + MAX_STEPS
# ============================================================

def react_loop(user_query: str, max_steps=MAX_STEPS) -> str:
    messages = [{"role": "user", "content": user_query}]
    last_actions = []   # 记录最近动作指纹 (工具名, 参数)，用于死循环检测

    for step in range(1, max_steps + 1):
        print(f"\n[Step {step}] Reason...")
        response = llm_call(messages, tools=TOOLS)
        choice = response.choices[0]

        if choice.finish_reason == "stop":
            return choice.message.content

        if choice.finish_reason == "tool_calls":
            messages.append({"role": "assistant", "content": choice.message.content,
                             "tool_calls": choice.message.tool_calls})
            for tc in choice.message.tool_calls:
                name, args = tc.function.name, json.loads(tc.function.arguments)
                print(f"[Step {step}] Act: {name}({args})")

                # ---- 死循环检测：同样动作连做 REPEAT_LIMIT 次 → 模型在复读 ----
                fingerprint = (name, json.dumps(args, sort_keys=True))
                last_actions.append(fingerprint)
                if last_actions[-REPEAT_LIMIT:] == [fingerprint] * REPEAT_LIMIT:
                    print(f"[!] 检测到重复动作 {fingerprint} 连续 {REPEAT_LIMIT} 次，疑似死循环，强制终止")
                    return "Agent 疑似死循环，已强制终止。请换一种方式提问。"

                result = execute_tool(name, args)   # 层 2：异常已被兜住
                print(f"[Step {step}] Observe: {json.dumps(result, ensure_ascii=False)[:250]}")
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(result, ensure_ascii=False)})
        else:
            print(f"[Step {step}] 未知 finish_reason: {choice.finish_reason}")

    print(f"\n[!] 达到 MAX_STEPS={max_steps} 仍没完成，强制终止")
    return "任务未在限定步数内完成"


if __name__ == "__main__":
    # 场景 A：错误恢复 —— 模型拿到"文件不存在"的 observe 后自行修正
    print("=" * 60)
    print("场景 A: 让 Agent 读一个不存在的文件（考验错误恢复）")
    print("=" * 60)
    print("\n>>> ", react_loop(
        "读取文件 '第一阶段/1.3.py' 的内容。提示：如果文件不存在，"
        "先列一下 '第一阶段' 目录看看实际有什么文件，再读正确的那个。"))

    # 场景 B：护栏触发 —— 任务需要 3 步，但只给 2 步额度
    print("\n" + "=" * 60)
    print("场景 B: MAX_STEPS=2 跑一个需要 3 步的任务（考验护栏）")
    print("=" * 60)
    print("\n>>> ", react_loop(
        "北京现在多少摄氏度？帮我换算成华氏度", max_steps=2))

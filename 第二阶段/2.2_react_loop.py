"""
第二阶段 2.2：手写最小 ReAct Loop
把 1.3 的"单轮工具调用"升级为"循环直到完成"

ReAct = Reason(思考) → Act(行动) → Observe(观察) → Repeat(重复)
Agent 的本质就是这个循环 + 两个护栏：
  1. MAX_STEPS —— 防止模型无限循环（烧钱 / 卡死）
  2. 工具结果必须回填 messages —— 模型才能"看到"发生了什么

运行: D:/miniforge3/envs/myenv/python.exe 第二阶段/2.2_react_loop.py
"""

import json
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# Windows 终端默认 GBK，无法处理 emoji，强制 UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

MAX_STEPS = 6  # 护栏 1：最多思考-行动几轮

# ============================================================
# 工具定义（从 1.3 复用）
# ============================================================

def get_weather(city: str, unit: str = "celsius") -> dict:
    """模拟天气查询"""
    weather_data = {
        "北京": {"celsius": 32, "fahrenheit": 90},
        "上海": {"celsius": 28, "fahrenheit": 82},
        "深圳": {"celsius": 35, "fahrenheit": 95},
    }
    temp = weather_data.get(city, {}).get(unit, "未知")
    return {"city": city, "temperature": temp, "unit": unit}

def calculate(expression: str) -> dict:
    """安全地计算数学表达式"""
    try:
        allowed = set("0123456789+-*/().% ")
        if not all(c in allowed for c in expression):
            return {"error": "表达式包含不允许的字符"}
        return {"expression": expression, "result": eval(expression)}
    except Exception as e:
        return {"error": str(e)}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的天气温度。当用户问天气、温度、热不热、冷不冷时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如 北京、上海、深圳"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算数学表达式。当用户需要算数、计算、求值时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "如 '3*4+2'"},
                },
                "required": ["expression"],
            },
        },
    },
]

TOOL_MAP = {"get_weather": get_weather, "calculate": calculate}


# ============================================================
# ReAct Loop 核心（本文件重点，仔细读）
# ============================================================

def react_loop(user_query: str) -> str:
    """最小 ReAct 循环：思考→行动→观察，直到模型直接回答"""
    messages = [{"role": "user", "content": user_query}]

    for step in range(1, MAX_STEPS + 1):  # 护栏：最多 MAX_STEPS 轮
        print(f"\n[Step {step}] Reason: 发送 messages={len(messages)} 条给模型...")

        # ---- Reason + Act：模型思考，决定是回答还是调工具 ----
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
        )
        choice = response.choices[0]

        # ---- 模型决定收尾：任务完成，返回最终回答 ----
        if choice.finish_reason == "stop":
            answer = choice.message.content
            print(f"[Step {step}] Done: 模型直接回答（循环结束）")
            return answer

        # ---- Act + Observe：模型要调工具，逐个执行并把结果回填 ----
        if choice.finish_reason == "tool_calls":
            # 先把模型的"调用意图"完整存进历史（含 tool_calls 数组）
            messages.append({
                "role": "assistant",
                "content": choice.message.content,
                "tool_calls": choice.message.tool_calls,
            })

            for tc in choice.message.tool_calls:
                func_name = tc.function.name
                func_args = json.loads(tc.function.arguments)
                print(f"[Step {step}] Act: {func_name}({func_args})")

                # 执行工具（Observe：拿到结果）
                result = TOOL_MAP[func_name](**func_args)
                print(f"[Step {step}] Observe: {json.dumps(result, ensure_ascii=False)}")

                # 观察结果回填 messages —— 模型下一轮就能"看见"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
            # 不 break —— 回到循环顶部，让模型基于观察继续思考

        else:
            print(f"[Step {step}] 未知 finish_reason: {choice.finish_reason}")

    # 护栏触发：MAX_STEPS 用完还没完成
    print(f"\n[!] 达到 MAX_STEPS={MAX_STEPS} 仍没完成，强制终止")
    return "任务未在限定步数内完成"


# ============================================================
# 测试：这个任务单轮做不完，必须靠循环
# ============================================================

if __name__ == "__main__":
    # 场景 A：需要 2 次工具调用（北京 + 上海）+ 比较
    print("=" * 56)
    print("任务 A: 北京和上海今天分别多少度？哪个更热？")
    print("=" * 56)
    final_a = react_loop("北京和上海今天分别多少度？哪个更热？")
    print(f"\n>>> 最终回答: {final_a}")

    # 场景 B：工具 + 计算混合
    print("\n" + "=" * 56)
    print("任务 B: 查一下北京温度，然后换算成华氏度告诉我？")
    print("=" * 56)
    final_b = react_loop("北京现在多少摄氏度？帮我换算成华氏度")
    print(f"\n>>> 最终回答: {final_b}")

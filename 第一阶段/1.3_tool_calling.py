"""
第一阶段 1.3：工具调用（Function Calling）
让模型决定"何时"调用"哪个"函数，这是 Agent 的核心能力

运行: python 第一阶段/1.3_tool_calling.py
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

# ============================================================
# 步骤 1：定义工具（tools/schema）
# ============================================================
# 每个工具包含：
#   name        - 函数名（模型会返回这个名字让你执行）
#   description - 描述（模型据此判断"什么时候该用这个工具"）
#   parameters  - 参数 schema（JSON Schema 格式）

def get_weather(city: str, unit: str = "celsius") -> dict:
    """模拟天气查询（实际项目中这里调真实 API）"""
    # 模拟数据
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
        # 只允许数字和基本运算符，防止代码注入
        allowed = set("0123456789+-*/().% ")
        if not all(c in allowed for c in expression):
            return {"error": "表达式包含不允许的字符"}
        result = eval(expression)
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": str(e)}

# 工具定义（JSON Schema）——这是给模型看的"说明书"
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的天气温度。当用户问天气、温度、热不热、冷不冷时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，如 北京、上海、深圳",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "温度单位，默认 celsius",
                    },
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
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '3*4+2'、'(10+5)*3'",
                    },
                },
                "required": ["expression"],
            },
        },
    },
]

# 工具名 → 实际函数 的映射
TOOL_MAP = {
    "get_weather": get_weather,
    "calculate": calculate,
}

# ============================================================
# 步骤 2：调用模型，模型可能返回"我要调工具"
# ============================================================

def run_tool_calling_demo(user_query: str):
    """演示一次完整的工具调用流程"""
    print(f"\n{'=' * 50}")
    print(f"用户: {user_query}")
    print("=" * 50)

    messages = [{"role": "user", "content": user_query}]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
    )

    choice = response.choices[0]

    # ---- 关键判断：模型是想直接回答，还是想调工具？ ----
    if choice.finish_reason == "stop":
        # 模型认为不需要工具，直接回答
        print(f"模型直接回答: {choice.message.content}")

    elif choice.finish_reason == "tool_calls":
        # 模型想要调用工具！
        for tool_call in choice.message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            print(f"模型想调工具: {func_name}({func_args})")

            # 执行工具
            func = TOOL_MAP[func_name]
            result = func(**func_args)
            print(f"工具返回: {result}")

            # 把结果反馈给模型
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [tool_call],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

        # 再次调用模型，让它基于工具结果生成最终回答
        response2 = client.chat.completions.create(
            model=MODEL,
            messages=messages,
        )
        print(f"模型最终回答: {response2.choices[0].message.content}")

    else:
        print(f"未知 finish_reason: {choice.finish_reason}")

# ============================================================
# 步骤 3：测试不同场景
# ============================================================

# 场景 A：需要调工具（天气查询）
run_tool_calling_demo("北京今天多少度？")

# 场景 B：需要调工具（数学计算）
run_tool_calling_demo("帮我算一下 (135 + 247) * 0.8")

# 场景 C：不需要调工具（闲聊）
run_tool_calling_demo("你好，介绍一下你自己")

# ============================================================
# 核心要点（通向第二阶段 Agent Loop）：
# 1. 工具描述（description）决定了模型会不会正确选择工具
# 2. finish_reason == "tool_calls" 意味着模型想"做事"而不只是"说话"
# 3. 工具结果必须塞回 messages，模型才能基于结果回答
# 4. 第二阶段就是把这个流程放进 while 循环，让模型反复调工具直到完成
# ============================================================

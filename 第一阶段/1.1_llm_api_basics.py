"""
第一阶段 1.1：LLM API 基础
理解 system prompt / user / assistant 三条消息结构

运行: python 第一阶段/1.1_llm_api_basics.py
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
)

MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

# ============================================================
# 核心概念：三条消息结构
# ============================================================
# system  - 设定 AI 的角色、行为规则（不会被用户覆盖）
# user    - 用户的具体问题/指令
# assistant - AI 的回复（多轮对话中由之前的 API 返回）

# ---- 示例 1：最简调用 ----
# print("=" * 50)
# print("示例 1：最简调用（只有 user 消息）")
# print("=" * 50)

# response = client.chat.completions.create(
#     model=MODEL,
#     messages=[
#         {"role": "user", "content": "用一句话解释什么是 API"},
#     ],
# )
# print(response.choices[0].message.content)
#
# # ---- 示例 2：加入 system prompt ----
# print("\n" + "=" * 50)
# print("示例 2：加入 system prompt 控制输出风格")
# print("=" * 50)

response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": "你是一个给 5 岁小孩解释概念的老师，用词简单，(禁止用比喻)。"},
        {"role": "user", "content": "什么是 API？"},
    ],
)
print(response.choices[0].message.content)

# ---- 示例 3：多轮对话（带 assistant 历史） ----
print("\n" + "=" * 50)
print("示例 3：多轮对话（上下文延续）")
print("=" * 50)

messages = [
    {"role": "system", "content": "你是一个 Python 编程助手，回答简洁。"},
    {"role": "user", "content": "Python 中 list 和 tuple 的区别是什么？"},
]

response = client.chat.completions.create(model=MODEL, messages=messages)
answer = response.choices[0].message.content
print(f"Q1: {messages[-1]['content']}")
print(f"A1: {answer}")

# 把上一轮的回答加入历史，模型就有了"记忆"
messages.append({"role": "assistant", "content": answer})
messages.append({"role": "user", "content": "给我一个 tuple 的代码示例"})

response = client.chat.completions.create(model=MODEL, messages=messages)
print(f"\nQ2: {messages[-1]['content']}")
print(f"A2: {response.choices[0].message.content}")

# ---- 示例 4：查看 response 对象的完整结构 ----
print("\n" + "=" * 50)
print("示例 4：response 对象的关键字段")
print("=" * 50)

response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "hi"}],
)

print(f"model:          {response.model}")
print(f"id:             {response.id}")
print(f"finish_reason:  {response.choices[0].finish_reason}")
print(f"usage:          {response.usage}")
# finish_reason: "stop"=正常结束, "length"=超长截断, "tool_calls"=模型想调工具

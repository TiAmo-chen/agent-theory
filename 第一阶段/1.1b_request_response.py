"""
第一阶段 1.1b：Request 与 Response 完整拆解
================================================
解答你在 2.2 里自然会冒出的问题：
  "模型到底能【接受】什么？又能【返回】什么？
   tools、finish_reason、tool_calls 这些是 OpenAI SDK 里的，还是我自己写出来的？"

★ 一句话答案 ★
  ✦ "能接受什么"  = client.chat.completions.create() 的【请求参数】
                    → 由 openai-python SDK 定义，SDK 会把它序列化成 JSON 发到 HTTP 请求体
  ✦ "能返回什么"  = create() 返回的【ChatCompletion 对象】
                    → 也是 openai-python SDK 定义的数据结构（Python 类）
  ✦ 字段名/结构    (choices, finish_reason, tool_calls, usage...) 是 SDK 定义的
  ✦ 字段的值       ("stop", "tool_calls", "length"...) 是模型服务端决定的，
                    不是你在代码里手写的字符串

★ 文档来源 ★
  - OpenAI Chat Completions 请求参数: https://platform.openai.com/docs/api-reference/chat/create
  - 函数调用(Function Calling)指南:   https://platform.openai.com/docs/guides/function-calling
  - openai-python SDK 源码定义:       https://github.com/openai/openai-python/blob/main/src/openai/types/chat/chat_completion.py
  - 本课程的 DeepSeek 使用的是「兼容 OpenAI 的 SDK」，所以字段完全一致

运行: python 第一阶段/1.1b_request_response.py
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
# 第 0 部分：先认识两个角色 —— SDK 负责"包装"，服务端负责"决策"
# ============================================================
#   ┌────────────── 你的 Python 代码 ──────────────┐
#   │  client.chat.completions.create(model,       │
#   │      messages, tools, tool_choice, ...)      │──┐
#   └──────────────────────────────────────────────┘  │
#                                                       │ HTTP POST /chat/completions
#   ┌──────────────────────────────────────────────┐  │   (SDK 把参数变成 JSON body)
#   │          模型服务端 (DeepSeek)                │◄─┘
#   │  读完 JSON → 自己决定是"说话"还是"调工具"      │──┐
#   └──────────────────────────────────────────────┘  │ HTTP 响应 (JSON)
#                                                        │
#   ┌──────────────────────────────────────────────┐  │
#   │   openai-python SDK 把响应 JSON 解析成         │◄─┘
#   │   ChatCompletion 对象（.choices / .usage ...）  │
#   └──────────────────────────────────────────────┘
#
#   结论：你代码里写的 "stop" / "tool_calls" 不是你自己发明的，
#         而是"服务端返回的值"经过 SDK 解析后，你拿它做比较。


# ============================================================
# 第 1 部分：模型能【接受】什么 —— create() 的常用请求参数
# ============================================================
# 这些是 openai-python SDK 里 create() 的关键字参数（部分），
# 每个参数最后都会被序列化进发往服务端的 JSON body。

REQUEST_PARAMS = {
    # ── 必填 ──
    "model": "模型 ID（如 deepseek-chat）。必填。",
    "messages": "对话消息列表，每条有 role 和 content。必填。",
    # ── 工具调用（本课程重点）──
    "tools": "工具清单（JSON Schema）。传给模型后，模型才知道能调哪些函数。",
    "tool_choice": "控制模型是否调工具：'none'=不调 / 'auto'=模型自己决定 / "
                   "'required'=必须调 / 指定函数名=强制调那个函数。",
    "parallel_tool_calls": "True=允许一次并行调多个工具（在一条回复里返回多个 tool_calls）。",
    # ── 采样控制 ──
    "temperature": "0~2，越高越随机（0.2 更稳，0.8 更发散）。",
    "top_p": "核采样，另一种随机性控制。一般只调 temperature 或 top_p 之一。",
    "max_tokens": "最多生成的 token 数（防超长、控成本）。",
    "stop": "遇到这些字符串就停止生成（最多 4 个）。",
    "seed": "固定随机种子，想让同输入跑出同结果时用（Beta）。",
    # ── 输出格式 ──
    "response_format": "结构化输出：{'type':'json_object'} 或 {'type':'json_schema',...}。",
    "stream": "True=流式返回（逐 token 吐，而不是一次性返回）。",
    # ── 其它 ──
    "n": "生成几个候选回答（默认 1，>1 会重复计费）。",
    "user": "终端用户标识，用于缓存命中率与滥用检测。",
}

print("=" * 56)
print("第 1 部分：模型能【接受】什么？create() 常用请求参数")
print("=" * 56)
for k, v in REQUEST_PARAMS.items():
    print(f"  {k:<22} {v}")


# ============================================================
# 第 2 部分：模型能【返回】什么 —— ChatCompletion 对象结构
# ============================================================
# create() 返回的是一个 ChatCompletion 对象（openai-python 里的 BaseModel）。
# 它长这样（只列核心字段）：

print("\n" + "=" * 56)
print("第 2 部分：模型能【返回】什么？ChatCompletion 对象结构")
print("=" * 56)
print("""
ChatCompletion
├── id                  # 本次调用的唯一 ID（如 chatcmpl-xxx）
├── model               # 实际用的模型名
├── created             # Unix 时间戳（秒）
├── object              # 固定 "chat.completion"
├── choices[ ]          # 候选回答列表（n=1 时只有 1 个）
│   └── Choice
│       ├── index           # 第几个候选
│       ├── finish_reason   # ★ 关键！结束原因（值见下）
│       ├── message         # 模型生成的消息
│       │   ├── role        # 固定 "assistant"
│       │   ├── content     # 文本内容（不调工具时是答案；调工具时通常是 None）
│       │   ├── tool_calls[…]# ★ 模型想调用的工具（finish_reason=tool_calls 时出现）
│       │   │   └── 每一项:
│       │   │       ├── id          # 工具调用 ID（回填结果时必须带上，用于配对）
│       │   │       ├── type        # 固定 "function"
│       │   │       └── function
│       │   │           ├── name       # 要调用的函数名
│       │   │           └── arguments  # 参数，JSON 字符串（要 json.loads 才能用）
│       │   └── refusal      # 模型拒绝回答的内容（可选）
│       └── logprobs     # token 概率（可选）
└── usage               # token 用量统计
    ├── prompt_tokens       # 输入（你的消息+tools）消耗
    ├── completion_tokens   # 输出（模型回答）消耗
    └── total_tokens        # 合计
""")


# ============================================================
# 第 3 部分：finish_reason 到底有哪些值？（这是服务端决定的枚举）
# ============================================================
# 这个字段是 openai-python 里用 Literal 定义的枚举，取值来自服务端。
FINISH_REASONS = {
    "stop": "模型自然结束（说完了 / 遇到 stop 序列）。—— 直接回答的情况",
    "length": "到达 max_tokens 上限被截断（回答可能不完整）。",
    "tool_calls": "【本课程重点】模型决定要调工具，返回了 tool_calls。",
    "content_filter": "输出被内容过滤器拦了（没通过审核）。",
    "function_call": "旧的字段名（deprecated），已被 tool_calls 取代。",
}
print("=" * 56)
print("第 3 部分：finish_reason 的取值（服务端决定，非你手写）")
print("=" * 56)
for k, v in FINISH_REASONS.items():
    print(f"  {k:<16} {v}")


# ============================================================
# 第 4 部分：动手跑一次 —— 完整打印出一个真实的 Request/Response
# ============================================================

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
                },
                "required": ["city"],
            },
        },
    },
]


def dump_response(response, title: str):
    """把 SDK 返回的 ChatCompletion 对象整体打印出来（含所有非空字段）。"""
    print(f"\n{title}")
    print("-" * 50)
    # model_dump() 是 openai SDK 里 BaseModel 的方法，把对象转成可打印的 dict
    data = response.model_dump(exclude_none=True)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("-" * 50)


# ---- 实验 A：不传 tools，纯聊天 → finish_reason 应为 "stop" ----
print("\n" + "=" * 56)
print("实验 A：不传 tools → finish_reason = stop（模型直接说话）")
print("=" * 56)
resp_a = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "用一句话说说什么是函数调用"}],
)
print(f"[A] finish_reason = {resp_a.choices[0].finish_reason!r}")
print(f"[A] message.role  = {resp_a.choices[0].message.role!r}")
print(f"[A] message.content = {resp_a.choices[0].message.content!r}")
print(f"[A] usage = {resp_a.usage}")
# 看完整对象里到底有哪些字段（去掉 None，更贴近实际）：
dump_response(resp_a, "[A] 整个 response 对象（exclude_none=True）")


# ---- 实验 B：传 tools，问"要不要调工具" → finish_reason 应为 "tool_calls" ----
print("\n" + "=" * 56)
print("实验 B：传 tools → finish_reason = tool_calls（模型想做事）")
print("=" * 56)
resp_b = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "北京今天多少度？"}],
    tools=TOOLS,          # ← 关键：把工具说明书交给模型
    tool_choice="auto",   #   让模型自己决定"说话"还是"调工具"
)
choice_b = resp_b.choices[0]
print(f"[B] finish_reason = {choice_b.finish_reason!r}")

if choice_b.finish_reason == "tool_calls":
    # 模型想调工具！遍历它要调的工具
    for tc in choice_b.message.tool_calls:
        print(f"[B] 模型想调 -> {tc.function.name}")
        print(f"[B]    arguments = {tc.function.arguments!r}  (是 JSON 字符串，需 json.loads)")
        print(f"[B]    tool_call_id = {tc.id!r}  (回填结果时要带上它)")
else:
    # 没调工具，说明模型直接回答了
    print(f"[B] 模型直接回答: {choice_b.message.content}")

dump_response(resp_b, "[B] 整个 response 对象（exclude_none=True）")

# ============================================================
# ★ 为什么 2.2 的 ReAct Loop 要"接着调第二次模型"？
# ============================================================
# 实验 B 里模型只给了"我要调工具"的意图，但【结果还没拿到】。
# 你必须：
#   1) 亲手执行 get_weather("北京")
#   2) 把结果塞回 messages（role="tool"）
#   3) 再调一次模型 → 它会基于结果生成最终文字答案
# 这就是 2.2 里 while 循环做的事。Response 本身是不执行任何工具的，
# 工具永远由"你的代码"来执行。

# ---- 实验 C（可选）：tool_choice 强制调工具 + response_format 结构化输出 ----
# 下面这段默认注释掉，想试可以取消注释（DeepSeek 对 json_object 支持良好）。
#
# print("\n" + "=" * 56)
# print("实验 C（可选）：tool_choice='required' 强制调工具")
# print("=" * 56)
# resp_c = client.chat.completions.create(
#     model=MODEL,
#     messages=[{"role": "user", "content": "北京多少度？"}],
#     tools=TOOLS,
#     tool_choice={"type": "function", "function": {"name": "get_weather"}},  # 强制调这个
# )
# print(f"[C] finish_reason = {resp_c.choices[0].finish_reason!r}")
# if resp_c.choices[0].message.tool_calls:
#     print(f"[C] 被强制的工具: {resp_c.choices[0].message.tool_calls[0].function.name}")
#
# print("\n" + "=" * 56)
# print("实验 D（可选）：response_format 让模型输出 JSON（结构化输出）")
# print("=" * 56)
# resp_d = client.chat.completions.create(
#     model=MODEL,
#     messages=[{"role": "user", "content": "用 JSON 返回北京和上海的温度，字段 city/temp"}],
#     response_format={"type": "json_object"},
# )
# print(resp_d.choices[0].message.content)


# ============================================================
# 小结（背下来，后面的 Agent Loop 全建立在它上面）
# ============================================================
print("\n" + "=" * 56)
print("小结")
print("=" * 56)
print("""
1. 模型能【接受】：model / messages / tools / tool_choice / temperature ...
   —— 这些是 openai-python SDK 的 create() 参数，SDK 转成 JSON 发给服务端。
2. 模型能【返回】：ChatCompletion 对象，含 choices / finish_reason / message / usage ...
   —— 这些字段名是 SDK 定义的，字段值是服务端填的。
3. finish_reason 是服务端决定的枚举：stop / length / tool_calls / content_filter / function_call。
   —— 你代码里 if finish_reason == "tool_calls" 是拿它和枚举值比较，不是你编的。
4. tools 参数只是个"说明书"；真正执行工具的是【你的代码】，不是模型、也不是 SDK。
   —— 模型返回 tool_calls 后，你要亲手执行、把结果回填 messages 再调一次。
5. 这就是 Agent 的本质循环：Reason(看 finish_reason) → Act(执行工具) → Observe(回填结果) → Repeat。
6. 【真实发现】服务端可能返回 SDK 标准字段之外的【扩展字段】。
   —— 刚才实验 A/B 里，DeepSeek 在 message 里多带回了一个 reasoning_content
      （模型思考过程），usage 里多了 prompt_cache_hit_tokens 等。
      openai-python 的 BaseModel 默认会宽容地把它们一并存进来。
   —— 所以：字段名是 SDK 定义的，但服务端【可以】多塞东西。
      你的代码只依赖标准字段（finish_reason / tool_calls / content）即可。
""")

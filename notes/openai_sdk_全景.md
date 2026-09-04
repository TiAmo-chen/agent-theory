# openai-python SDK 全景速览

> 基于本地实际安装版本 **openai 2.29.0** 实测整理（`D:/miniforge3/envs/myenv/Lib/site-packages/openai`）。
> 本课程用 DeepSeek 走的是「兼容 OpenAI 的 SDK」，所以下面的接口、字段、异常体系完全一致。

---

## 0. 一句话看懂 SDK

`openai` 包 = **一套"HTTP 客户端 + 类型系统"**，主要做两件事：

1. **帮我们把参数打包成请求**（`create(model, messages, tools, ...)` 的参数 → JSON body 发出去）
2. **帮我们把响应解析成对象**（服务端返回的 JSON → `ChatCompletion` 等 Python 对象）

```
你的代码 → openai SDK → HTTP POST → 模型服务端(DeepSeek) → JSON 响应 → openai SDK → Python 对象
```

`tools`、`finish_reason`、`tool_calls` 这些字段名是 **SDK 定义的**；字段的值（`"stop"`/`"tool_calls"`）是 **服务端决定的**。

---

## 1. 顶层导出（`openai/__init__.py` 的 `__all__`）

导入后可直接用的核心符号：

| 符号 | 作用 |
|------|------|
| `OpenAI` / `AsyncOpenAI` | 同步 / 异步客户端（**日常用这个**） |
| `Client` / `AsyncClient` | 客户端基类（一般不用直接实例化） |
| `Stream` / `AsyncStream` | 流式迭代器（`stream=True` 时返回） |
| `BaseModel` | pydantic 模型，用于结构化输出/工具定义 |
| `Timeout` / `Transport` / `ProxiesTypes` | 超时 / 传输 / 代理相关类型 |
| `NotGiven` / `not_given` / `Omit` / `omit` | **参数三态**（见 §6，重要） |
| `file_from_path` | 文件对象工具 |
| 异常类全家桶 | `APIError`, `RateLimitError`, ...（见 §7） |
| `DEFAULT_TIMEOUT` / `DEFAULT_MAX_RETRIES` / `DEFAULT_CONNECTION_LIMITS` | 默认配置常量 |
| `AzureOpenAI` | 微软 Azure 版客户端（不用 Azure 可忽略） |
| `pydantic_function_tool` | 把 pydantic 模型转成 tool（见 §9） |

**模块级客户端**：新版还支持 `openai.api_key = "xxx"` 这种"模块级"用法，但**推荐用 `OpenAI(...)` 实例化**，更清晰、可配不同 key。

---

## 2. 客户端创建与配置

### 2.1 构造参数（`OpenAI.__init__` 实测签名）

| 参数 | 默认 | 说明 |
|------|------|------|
| `api_key` | `None` | API 密钥 |
| `organization` | `None` | 组织 ID |
| `project` | `None` | 项目 ID |
| `webhook_secret` | `None` | webhook 签名校验密钥 |
| `base_url` | `None` | **接口地址**（DeepSeek 用这个指向第三方） |
| `websocket_base_url` | `None` | 实时/语音 WebSocket 地址 |
| `timeout` | `NOT_GIVEN` | 超时（秒/Timeout 对象） |
| `max_retries` | `2` | 请求失败自动重试次数 |
| `default_headers` | `None` | 每个请求默认带的 header |
| `default_query` | `None` | 每个请求默认带的 query 参数 |
| `http_client` | `None` | 自定义 httpx client |
| `_strict_response_validation` | `False` | 严格响应校验 |

### 2.2 三种创建方式

```python
# 方式 ① 从环境变量（.env 里设好 OPENAI_API_KEY 等，直接无参）
from openai import OpenAI
client = OpenAI()

# 方式 ② 显式传（DeepSeek 常用）
from dotenv import load_dotenv; load_dotenv()
import os
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),   # https://api.deepseek.com/v1
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 方式 ③ 自定义全局（推荐用于产品化：加默认 headers、关超时）
client = OpenAI(
    api_key="sk-...",
    timeout=60.0,
    max_retries=3,
    default_headers={"X-Client": "my-app"},
)
```

---

## 3. 核心：`chat.completions`（你天天用的）

`client.chat.completions` 是 **Completions 资源**，最常用的方法：

| 方法 | 作用 |
|------|------|
| `create(...)` | **主打**。发一次请求，返回 `ChatCompletion` |
| `parse(...)` | 结构化输出：用 pydantic 模型当 `response_format`，直接返回解析好的对象 |
| `stream(...)` | 流式：返回 `Stream[ChatCompletionChunk]`，逐 token 迭代 |
| `with_raw_response` | 拿到原始 HTTP 响应（headers、status） |
| `with_streaming_response` | 流式 + 原始响应 |
| `messages` | 子资源：存取/列出已 store 的完成消息（较新） |

### 3.1 `create()` 最常用参数

| 参数 | 说明 |
|------|------|
| `model` | **必填**，模型 ID |
| `messages` | **必填**，消息列表 |
| `tools` | 工具说明书（JSON Schema） |
| `tool_choice` | `"none"`/`"auto"`/`"required"`/指定函数名 |
| `response_format` | `{"type":"json_object"}` 或 `{"type":"json_schema"...}` |
| `temperature` / `top_p` | 随机性控制 |
| `max_tokens` / `max_completion_tokens` | 输出上限 |
| `stop` | 遇到即停（最多 4 个） |
| `stream` | `True` 流式 |
| `n` | 生成几个候选 |
| `seed` | 固定随机种子 |
| `parallel_tool_calls` | `True` 允许一次并行调多个工具 |
| `user` | 终端用户标识 |

### 3.2 `create()` 返回的 `ChatCompletion`（`types/chat/chat_completion.py`）

```
ChatCompletion
├── id             # 唯一 ID
├── model          # 模型名
├── created        # Unix 时间戳
├── object         # "chat.completion"
├── choices[]      # 候选
│   └── Choice
│       ├── index
│       ├── finish_reason   # "stop"|"length"|"tool_calls"|"content_filter"|"function_call"
│       ├── message         # ChatCompletionMessage
│       │   ├── role        # "assistant"
│       │   ├── content     # 文本(调工具时常为空串)
│       │   ├── tool_calls[]# ★ 模型想调的工具
│       │   │   ├── id
│       │   │   ├── type    # "function"
│       │   │   └── function{ name, arguments }
│       │   └── refusal     # 拒绝回答
│       └── logprobs
└── usage           # token 统计
    ├── prompt_tokens
    ├── completion_tokens
    └── total_tokens
```

> **真实发现**：`ChatCompletionMessage` 用 `BaseModel`（默认宽松），所以 DeepSeek 返回的
> `reasoning_content`、`usage.prompt_cache_hit_tokens` 等**扩展字段也会被带进来**。
> 字段名是 SDK 定的，但服务端可以**多塞**东西。

---

## 4. 全部资源 API（`openai/resources/`）

| 资源 | 用途 | 对应你学习里的阶段 |
|------|------|------------------|
| `chat` | 对话（completions、messages） | 一、二 |
| `completions` | 旧的补全接口 | 兼容 |
| `responses` | OpenAI 新一代 Responses API | 了解 |
| `embeddings` | 向量嵌入 | 三(语义搜索) |
| `images` | 生成/编辑图片 | - |
| `audio` | 语音转写/生成 | 三(多模态) |
| `files` | 文件上传/管理 | 三 |
| `fine_tuning` | 微调 | 进阶 |
| `moderations` | 内容审核 | 六(评测/安全) |
| `batches` | 批量异步 | 进阶 |
| `models` | 模型列表/管理 | - |
| `vector_stores` | 向量存储(文件搜索) | 五(记忆) |
| `beta` | 实验性 API | 进阶 |
| `realtime` | 实时语音 | 进阶 |
| `containers` / `conversations` / `evals` / `skills` / `uploads` / `videos` | 较新/专项 | 了解 |

> 注：`chat` 下的 `completions` 里还有 `messages` 子资源、`with_raw_response`/`with_streaming_response` 三大入口。

---

## 5. 返回对象 = `types` 包

响应对象都集中在 `openai.types`，**按资源分目录**：

- `types/chat/`：`ChatCompletion`、`ChatCompletionMessage`、`ChatCompletionMessageToolCall`、
  `ChatCompletionChunk`(流式)、`ChatCompletionRole`、`ChatCompletionFunctionTool`、
  `CompletionCreateParams`(参数类型)、`ParsedChatCompletion`(结构化输出) 等
- `types/`：`Completion`(旧)、`Embedding`、`Image`、`Moderation`、`FileObject`、`Model`、`Batch`、`VectorStore` 等

**规律**：每个资源的"参数类型"后缀是 `_create_params` / `_list_params`，响应对应资源名。
比如 `client.chat.completions.create(...)` 返回 `ChatCompletion`，参数类型是 `completion_create_params.CompletionCreateParams`。

---

## 6. 参数三态：`NotGiven` / `Omit` / `None`（重点！）

SDK 区分"**我没有传这个参数**"和"**我传了 None**"，这是很多 bug 的根源：

| 值 | 含义 | 效果 |
|----|------|------|
| `NOT_GIVEN` / `not_given` | 参数没传 | 请求体里**不含**这个字段 → 用服务端默认值 |
| `Omit` / `omit` | 显式省略 | 同上，明确"不发送" |
| `None` | 传了空 | 请求体里**含**这个字段且值为 null → 可能覆盖默认 |

```python
# 错误示范：想"不限制温度"，但 temperature=None 会发送 null，可能报错或用错默认
client.chat.completions.create(model=MODEL, messages=m, temperature=None)

# 正确：不传就省略，走 service 默认
client.chat.completions.create(model=MODEL, messages=m)
```

**结论**：想要"用服务端默认"，就**别写**那个参数，不要写 `=None`。

---

## 7. 异常体系与错误码（`openai/_exceptions.py`，实测继承链）

```
Exception
└── OpenAIError                       # SDK 所有异常的根
    ├── APIError                      # 一切 API 相关
    │   ├── APIResponseValidationError  # 响应校验失败
    │   ├── APIStatusError             # ★ 只要 HTTP 状态码非 2xx 就抛这个
    │   │   ├── BadRequestError            # 400 参数有错
    │   │   ├── AuthenticationError        # 401 key 错/无效
    │   │   ├── PermissionDeniedError      # 403 无权限
    │   │   ├── NotFoundError              # 404 资源不存在
    │   │   ├── ConflictError              # 409 冲突
    │   │   ├── UnprocessableEntityError   # 422 语义错误(如 schema 校验)
    │   │   ├── RateLimitError             # 429 限流/超额
    │   │   └── InternalServerError        # 5xx 服务端错误
    │   └── APIConnectionError          # 连接层错误(连不上)
    │       └── APITimeoutError           # 超时
    ├── LengthFinishReasonError        # 输出超长被截断
    ├── ContentFilterFinishReasonError # 输出被内容过滤
    └── InvalidWebhookSignatureError   # 继承 ValueError，webhook 签名校验
```

### 实践：错误分类处理

```python
from openai import OpenAI
import openai

client = OpenAI(...)
try:
    resp = client.chat.completions.create(...)
except openai.RateLimitError as e:
    print("限流了，稍后再试", e.status_code)
except openai.AuthenticationError as e:
    print("API key 无效/欠费")
except openai.APITimeoutError:
    print("超时，重试")
except openai.APIConnectionError:
    print("网络连不上 DeepSeek 服务")
except openai.APIStatusError as e:
    print(f"其它状态错误: {e.status_code} {e.message}")
```

> 错误对象上常有 `.status_code`（HTTP 状态码）、`.message`（详情）、`.request`/`.response`（原始请求响应）。
> 这是 2.4 错误处理那节会用到的原料。

---

## 8. 流式 `stream=True` 与 `Stream`

```python
stream = client.chat.completions.create(model=MODEL, messages=m, stream=True)
for chunk in stream:          # 每个 chunk 是 ChatCompletionChunk
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="")   # 逐 token 打印
# 最后一个 chunk 的 choices[0].finish_reason 会给出结束原因
```

流式的好处：首 token 延迟低、实时显示；代价是每个 chunk 都要自己拼内容。

---

## 9. `lib` 工具库与高级功能

| 模块 | 功能 |
|------|------|
| `lib/_pydantic.py` | `pydantic_function_tool`：把 Python 类型/pydantic 模型转成 tool schema |
| `lib/_tools.py` | 工具定义辅助 |
| `lib/streaming/` | `AssistantEventHandler`：Assistants API 流式事件处理器 |
| `lib/azure.py` | `AzureOpenAI` / `AsyncAzureOpenAI` |
| `lib/_old_api.py` | 兼容旧的模块级调用 |

### `pydantic_function_tool` 示例（结构化工具）

```python
from pydantic import BaseModel
from openai import pydantic_function_tool

class GetWeather(BaseModel):
    city: str            # 字段名+类型 → 自动生成 schema
    unit: str = "celsius"

tool_schema = pydantic_function_tool(GetWeather)
# tool_schema 可直接塞进 tools=[tool_schema]
```

---

## 10. 与 DeepSeek 兼容性注意

| 点 | 说明 |
|----|------|
| base_url | 必须指向 `https://api.deepseek.com/v1` |
| 模型名 | 用 `.env` 里的 `DEEPSEEK_MODEL`（`deepseek-chat` 等） |
| 工具调用 | `tools` / `tool_choice` / `tool_calls` 完全兼容（已验证） |
| 结构化输出 | 支持 `response_format={"type":"json_object"}`；`json_schema` 看模型 |
| 不支持/有限 | OpenAI 特有的 `service_tier`、`audio` 输出、`realtime`、Assistants 等不适用 |
| 扩展字段 | DeepSeek 会返回 `reasoning_content`、缓存统计等，SDK 宽容存放 |

**原则**：只依赖「标准字段」(`finish_reason`/`tool_calls`/`content`/`usage`) 写代码，才能跨 OpenAI / DeepSeek / 其它兼容服务通用。

---

## 11. 学习路径建议（对应你的 6 阶段）

| 优先级 | 先学 | 去哪学 |
|--------|------|--------|
| ⭐⭐⭐ 必 | `openai` 包怎么装、client 创建、`chat.completions.create` | 1.1 / 1.1b |
| ⭐⭐⭐ 必 | `tools` / `tool_choice` / `tool_calls`  | 1.3 |
| ⭐⭐⭐ 必 | `finish_reason` 判断 + ReAct 循环 | 2.2 |
| ⭐⭐ 重要 | 异常体系 `RateLimitError`/`APITimeoutError` + 重试 | 2.4 |
| ⭐⭐ 重要 | 参数三态 `NotGiven` vs `None` | 写产品时必踩 |
| ⭐ 了解 | `stream` 流式、`parse` 结构化、`pydantic_function_tool` | 进阶 |
| 🔵 选学 | `embeddings`(语义搜索)、`vector_stores`(记忆) | 三/五 |
| 🔵 了解 | `responses` API、`fine_tuning`、Assistants | 整体认知 |

---

*下一步建议：打开 `第一阶段/1.1c_sdk_explorer.py` 跑一遍，对着你本地真实的 SDK 把上面的每一项都看一遍 —— 亲手看到的比记住的牢。*

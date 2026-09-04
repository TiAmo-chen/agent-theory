# Agent 系统学习计划

> 始于 2026-07-17，以 Kimi Code Agent Infra 研发工程师 JD 为纲

---

## 学习路线总览

```
第一周              第四周                第八周
  │                  │                    │
  ▼                  ▼                    ▼
调API → 函数调用 → ReAct循环 → 多工具 → 上下文工程 → 评测
                  │           │
                  ▼           ▼
             手写简易Agent    能分析Agent为什么失败
```

---

## 第一阶段：地基（1-2 周）

**目标**：理解 LLM 能做什么，API 怎么调，函数调用是什么

| 步骤 | 内容 | 推荐资源 |
|------|------|---------|
| 1.1 | LLM API 基础：system prompt / user / assistant 三条消息结构 | agenticloops mod1 |
| 1.1b | （补充）Request/Response 结构：模型能接受什么、返回什么 | openai-python SDK 源码 |
| 1.2 | 结构化输出：JSON mode / function calling 原理 | agenticloops mod1.4 |
| 1.3 | 写第一个工具调用：让模型调用自定义函数 | Scrimba Phase 1-2 |

**对应 JD**：Tool Use, Function Calling

**产出**：能在 Python 里调 LLM API，能定义工具函数让模型调用

---

## 第二阶段：Agent Loop 核心（2-3 周）

**目标**：手写 Agent Loop，理解 ReAct 循环

| 步骤 | 内容 | 推荐资源 |
|------|------|---------|
| 2.1 | ReAct 循环原理：Reason → Act → Observe → Repeat | agenticloops mod2 |
| 2.2 | 手写一个 50 行的 ReAct Loop | pguso/ai-agents-from-scratch |
| 2.3 | 加入多工具：文件读写 + shell 命令 | mini-claude-code |
| 2.4 | 错误处理：重试、超时、最大迭代限制 | how-to-build-a-coding-agent |
| 2.5 | 上下文管理：裁剪历史、压缩、截断 | Anthropic 上下文工程文档 |

**核心概念**：

```python
# ReAct Loop 最小实现
messages = [user_query]
while True:
    response = llm(messages, tools)
    if response.stop_reason != "tool_use":
        return response.text          # 完成
    for tc in response.tool_calls:
        result = execute_tool(tc)     # 执行工具
        messages.append(result)       # 观察结果
```

**对应 JD**：Agent Loop, 任务拆解, 工具调用, 结果观察, 错误恢复, 长任务续跑, 最终验证

**产出**：能写出一个能读文件、写代码、跑命令的简易 Coding Agent

---

## 第三阶段：工具系统（2 周）

**目标**：理解一个 Coding Agent 需要哪些工具，怎么设计

| 步骤 | 内容 |
|------|------|
| 3.1 | 文件操作工具：read / write / edit / diff |
| 3.2 | 搜索工具：grep / glob / 语义搜索 |
| 3.3 | Bash 执行：沙箱、权限、安全 |
| 3.4 | MCP 协议（Model Context Protocol）了解 |

**工具设计原则**：
- 每个工具职责单一，不重叠
- 提供清晰的 schema（name, description, parameters）
- 工具输出要可解析、可观察
- "bash is all you need"——bash 是万能适配器

**对应 JD**：文件编辑, 命令执行, 代码搜索, 测试运行, Git 工作流, 沙箱与远程执行

---

## 第四阶段：上下文工程（2 周）

**目标**：理解 Agent 最大的工程挑战——上下文窗口

| 步骤 | 内容 |
|------|------|
| 4.1 | 为什么上下文是瓶颈：token 消耗、注意力衰减、context rot |
| 4.2 | 上下文压缩策略：摘要、裁剪、分层 |
| 4.3 | 渐进式上下文：先加载概览（~3KB），按需加载细节（省 ~82% 上下文） |
| 4.4 | 历史轨迹管理：什么该留、什么该丢 |
| 4.5 | 任务状态维护：持久化、断点续跑 |

**对应 JD**：代码检索, 文件选择, 上下文压缩, 历史轨迹管理, 任务状态维护, 长期记忆

---

## 第五阶段：规划与记忆（1-2 周）

| 步骤 | 内容 |
|------|------|
| 5.1 | 任务分解：Plan-Execute 模式 |
| 5.2 | 短期记忆（上下文内）vs 长期记忆（外部存储） |
| 5.3 | 文件系统即记忆（NOTES.md 模式，Anthropic 推荐） |
| 5.4 | 多 Agent 协作：Orchestrator-Worker 模式 |

**对应 JD**：任务拆解, 规划, 记忆, 多智能体协作

---

## 第六阶段：评测与观察（1 周）

| 步骤 | 内容 |
|------|------|
| 6.1 | Trace 是什么：记录每一步的 tool call、结果、耗时 |
| 6.2 | 评测集构建：好用例 vs 失败用例 |
| 6.3 | 从 trace 定位失败根因 |

**对应 JD**：失败样本, 评测集, trace, 分析工具

---

## 推荐学习资源清单

### 上手实操（五星推荐）
- [agenticloops/agentic-ai-engineering](https://github.com/agenticloops-ai/agentic-ai-engineering) —— 模块化教程，一行命令就能跑
- [pguso/ai-agents-from-scratch](https://github.com/pguso/ai-agents-from-scratch) —— 从零手写，无框架，每行都有注释
- [Scrimba: How to Build AI Agents (2026)](https://scrimba.com/articles/how-to-build-ai-agents/) —— 渐进式教程，从 0 到部署

### 理论深度
- [Anthropic: Building Effective Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) —— 官方最佳实践
- [阿里云: 从零手写 ClaudeCode](https://developer.aliyun.com/article/1715012) —— 中文，手把手拆解 Agent Loop
- [ArXiv: Coding Agent Architectures Taxonomy](https://arxiv.org/html/2604.03515v1) —— 13 个开源 Coding Agent 的架构分类

### 视频课程
- [FreeCodeCamp: AI Agents For Beginners](https://www.freecodecamp.org/news/ai-agents-for-beginners)
- [DeepLearning.AI: Building Coding Agents with Tool Execution](https://learn.deeplearning.ai/courses/building-coding-agents-with-tool-execution/)

---

## JD 关键术语对照表

| JD 原文 | 对应概念 | 学习阶段 |
|---------|---------|---------|
| Agent Loop / 执行循环 | ReAct 循环：think→act→observe→repeat | 二 |
| 任务拆解 | Plan-Execute 模式，将大任务拆为子步骤 | 五 |
| 工具调用 | Function Calling / Tool Use | 一 |
| 结果观察 | Tool result 反馈到 LLM，继续循环 | 二 |
| 错误恢复 | 重试机制、降级策略、超时处理 | 二 |
| 长任务续跑 | 状态持久化、断点恢复 | 四 |
| 最终验证 | LLM-as-judge、测试验证 | 六 |
| 代码检索 | grep/glob 搜索、语义搜索 | 三 |
| 上下文压缩 | 摘要、裁剪、渐进式加载 | 四 |
| 历史轨迹管理 | Agent trace 管理与分析 | 六 |
| 长期记忆 | 文件持久化、向量存储 | 五 |
| 多智能体协作 | Orchestrator-Worker 模式 | 五 |
| 沙箱与远程执行 | Docker/k8s/WASM 隔离执行 | 三 |

---

## 使用方法

1. 按阶段顺序学习，每个阶段完成后进入下一阶段
2. 每个步骤都要动手写代码，不要只看不练
3. 遇到问题时，记录到本目录下的 `notes/` 中
4. 可以用我（Claude）来：解释概念、审代码、debug、补充调研

---

*学习愉快，欢迎加入 Agent 工程的世界。*

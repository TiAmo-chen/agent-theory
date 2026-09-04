# 第二阶段笔记：Agent Loop 核心

> 完成于 2026-09-03，对应代码 `第二阶段/2.2~2.5_*.py`

## ReAct 循环的本质

```
messages → LLM(思考+决定) → 若 finish_reason=="tool_calls" → 执行工具 → 结果回填 → 循环
                            └→ 若 finish_reason=="stop" → 返回最终回答（完成）
```

关键理解：
- **工具结果像接力棒**：上一轮的 Observe 是下一轮 Reason 的输入（2.2 任务 B：32°C → 换算华氏度）
- 模型可以**一轮并行调用多个工具**（tool_calls 是数组，逐个执行回填即可）
- Loop 本身不复杂，复杂的是护栏与工程化

## 护栏清单（生产级 Agent 必备）

| 层 | 故障 | 对策 |
|----|------|------|
| API | 限流/断网/超时 | 指数退避重试（2^attempt 秒） |
| 工具 | 文件没了/参数错/意外崩溃 | 可预期错误返回 error dict；意外异常 try/except 兜住，**错误也回填给模型** |
| 行为 | 死循环/复读同一工具 | 动作指纹检测（同指纹 N 次→打断）+ MAX_STEPS |
| 上下文 | messages 无限膨胀 | 见下 |

核心思想：**错误不是终点，是观察结果**。模型看得见错误就能自我修正
（2.4 实测：模型拿到"文件不存在"后自己列目录找正确文件名）。

## 上下文三武器（第四阶段深入）

1. **trim**：单条工具输出截断，标注砍了多少（工具返回永远要限制长度）
2. **summarize**：把最老的几轮交给 LLM 压成一段摘要替换（2.5 实测 2895→413 tokens）
3. **truncate**：超预算从最老丢起，**用户原始目标永远保留**

原则：**丢过程，不丢目标**。

## 工具设计安全边界（2.3）

- 路径锁死在项目目录内（abspath 前缀校验）
- shell 只放行白名单命令，拒绝危险字符（rm、|、;、$()）
- 工具 schema 的 description 决定模型选得准不准，要写清"什么时候用"

## 踩坑记录

- Windows 控制台 GBK：脚本开头 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`
- `m.get("content")` 对 content=None（assistant 工具调用消息）返回 None，需 `(m.get("content") or "")`
- DeepSeek 的 function calling 实测正常，支持并行 tool_calls

## 通向第三阶段

2.3 的工具只做了"读"，下一步（第三阶段）要补全写入/编辑/命令执行沙箱，并引入 MCP。

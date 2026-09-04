# LLM 结构化输出：从软提示到硬约束

> 2026-07-18，第一阶段学习笔记

---

## 问题

LLM 输出天然是自由文本。Agent 需要可解析的结构化数据（JSON），怎么保证？

---

## 三层方案（由松到严）

### 第 1 层：Prompt 工程

```
"请只返回 JSON，不要加任何解释"
```

- 原理：靠模型"听懂人话"
- 保证：**无**。可能少括号、多逗号、夹带 markdown 代码块
- 适用：原型阶段快速验证

### 第 2 层：API 级别 JSON mode

```python
response_format={"type": "json_object"}
```

- 原理：API 端注入格式化指令，内部训练偏好
- 保证：**JSON 语法合法**（能 `json.loads` 成功）
- 不保证：字段名正确、类型匹配、必填字段齐全
- DeepSeek / OpenAI / Claude 都支持

### 第 3 层：约束解码（Constrained / Grammar-Constrained Decoding）

- 原理：修改采样过程，逐 token 过滤不合法候选
- 保证：**数学上保证**符合 Schema。类型、必填、enum 值全部正确
- 实现方式：
  - **API 内置**：Claude `strict: true`、OpenAI `response_format={"type": "json_schema", ...}`
  - **本地库**：guidance、outlines、lm-format-enforcer、XGrammar

---

## 约束解码原理

### 整体流程

```
JSON Schema → 编译成形式语法（GBNF/CFG） → 推理时逐 token 做 logit mask
```

### 逐 token logit mask

```
LLM 输出 logits 向量（词表大小，每个 token 一个分数）
    ↓
语法引擎：当前状态下，这个 token 合法吗？
    ↓
合法 → 保留原分数    不合法 → logit = -∞
    ↓
softmax 只在合法 token 上重新归一化
    ↓
采样 → 物理上不可能选中非法 token
```

### 关键性能优化：上下文分组

| 类别 | 比例 | 处理 |
|------|------|------|
| 上下文无关 token | ~99% | 预计算为 bitmask 表，查表 O(1) |
| 上下文相关 token | ~1% | 实时逐字符走过自动机 |

单 token 延迟 < 40μs，几乎不影响推理速度。

### Tokenizer 不对齐问题（实现难点）

- 语法引擎操作**字符**
- LLM 生成的是 **BPE subword token**（多字符）
- 例：token `}\n` = 字符 `}` + `\n`，语法只要 `}`
- 必须逐字符检查每个候选 token 的所有字符，不能只看 token 的"首字符"

### Jump-Forward Decoding（反而加速）

当语法强制后续内容确定时（如 schema 的 key 名），直接跳过模型前向传播，硬塞固定字符串。结构越多反而越快。

---

## 各大方案对比

| 方案 | 语法保证 | 结构保证 | 需要模型支持 | 缺点 |
|------|---------|---------|-------------|------|
| Prompt 法 | ❌ | ❌ | ❌ | 完全不可靠 |
| `json_object` | ✅ | ❌ | ✅ | 结构不可控 |
| Claude `strict: true` | ✅ | ✅ | Claude 4.6+ | 有 schema 特性限制 |
| OpenAI `json_schema` | ✅ | ✅ | GPT-4+ | 消耗更多 token |
| outlines (本地库) | ✅ | ✅ | ❌ | 额外依赖，有冷启动 |
| validation + retry | ❌ | ❌ | ❌ | 多轮重试消耗 token |

---

## 约束解码的代价

- **语义质量下降**：10-30% 推理质量损失（模型被迫选局部合法但全局次优的 token）
- **缓解策略**：在 schema 最前面放一个自由文本 `reasoning` 字段，让模型先"想清楚"再填结构化字段
- **编译开销**：首次编译 Schema 需要几十到几百毫秒（可缓存）

---

## 相关资源

- [Anthropic: Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic: Strict Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)
- [XGrammar (vLLM/SGLang 的约束解码后端)](https://github.com/mlc-ai/xgrammar)
- [Grammar-Aligned Decoding (arXiv 2405.21047)](https://arxiv.org/abs/2405.21047) — 理论分析约束解码的分布偏差

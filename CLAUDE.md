# Agent 理论学习

## 学习路线
以 Kimi Code Agent Infra JD 为纲，6 阶段学习：

1. **地基** — LLM API、函数调用
2. **Agent Loop** — ReAct 循环、手写简易 Agent
3. **工具系统** — 文件操作、Bash、搜索
4. **上下文工程** — 压缩、裁剪、渐进式加载
5. **规划与记忆** — Plan-Execute、记忆持久化
6. **评测与观察** — Trace、评测集

详见 `README.md`

## API 配置
使用 DeepSeek（兼容 OpenAI SDK）：
```
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```
参考 `D:\code\python\AI\LangChain\.env`

## 目录结构
- `README.md` - 学习计划
- `CLAUDE.md` - 本文件，给 AI 的上下文
- `第一阶段/` 到 `第六阶段/` - 每阶段练习代码
- `notes/` - 学习笔记

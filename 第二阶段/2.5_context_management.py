"""
第二阶段 2.5：上下文管理入门 —— 三种武器对抗上下文爆炸

问题：ReAct Loop 每轮都在往 messages 里塞东西（尤其工具输出可能巨大），
几十轮后必然撞上上下文窗口上限。第四阶段会系统学"上下文工程"，
这里先认识三种基础武器：

  武器 1 trim：单条工具输出截断（保留头尾，标出被砍多少）
  武器 2 summarize：把最老的几轮用 LLM 压成一段摘要（换掉原始消息）
  武器 3 truncate：超出预算时，从最老的消息开始丢（但永远保留用户的目标）

重要原则：**丢"过程"，不丢"目标"**
- 该留：用户原始请求、最近的推理轨迹、最终结论
- 该丢：旧的工具原始输出、重复的中间推理

运行: D:/miniforge3/envs/myenv/python.exe 第二阶段/2.5_context_management.py
"""

import json
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ============================================================
# token 估算（教学近似值：1 token ≈ 2 个字符）
# 真实项目用模型的 tokenizer 精确统计（如 tiktoken）
# ============================================================

def estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 2))

def history_tokens(msgs) -> int:
    return sum(estimate_tokens(m.get("content") or "")
               + sum(estimate_tokens(t.function.arguments) for t in m.get("tool_calls") or [])
               for m in msgs)

# ============================================================
# 构造演示历史：模拟一个 Agent 读了好几个大文件找答案
# （工具输出 = 真实项目文件内容，这样演示才真实）
# ============================================================

def build_history():
    """模拟 6 轮对话：读了 3 个大文件 + 3 次短工具调用"""
    def tool_round(tool_name, args, result_text):
        """拼一轮 assistant 工具调用 + tool 结果的格式（与真实 API 格式一致）"""
        tc = type("TC", (), {"id": f"call_{tool_name}", "function": type(
            "F", (), {"name": tool_name, "arguments": json.dumps(args, ensure_ascii=False)})()})()
        return [
            {"role": "assistant", "content": None, "tool_calls": [tc]},
            {"role": "tool", "tool_call_id": tc.id, "content": result_text},
        ]

    def read_file_full(rel):
        with open(os.path.join(PROJECT, rel), encoding="utf-8") as f:
            return f.read()

    h = [{"role": "user", "content": "帮我在项目里找到 get_weather 工具的完整定义，"
                                     "并总结它支持的查询逻辑，最后输出一个使用示例。"}]
    # 轮 1-3：大文件读取（真正的 token 大户）
    h += tool_round("read_file", {"path": "notes/structured-output.md"}, read_file_full("notes/structured-output.md"))
    h += tool_round("read_file", {"path": "CLAUDE.md"}, read_file_full("CLAUDE.md"))
    h += tool_round("read_file", {"path": "第一阶段/1.1_llm_api_basics.py"}, read_file_full("第一阶段/1.1_llm_api_basics.py"))
    # 轮 4-6：后续小查询
    for city in ["北京", "上海", "深圳"]:
        h += tool_round("get_weather", {"city": city},
                        json.dumps({"city": city, "temperature": 30 + len(city), "unit": "celsius"}, ensure_ascii=False))
    return h

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# 武器 1：trim —— 单条超长输出截断
# ============================================================

def trim_tool_outputs(msgs, max_chars=400):
    """所有超长 tool 内容砍到 max_chars，标注砍了多少"""
    total_cut = 0
    for m in msgs:
        content = m.get("content") or ""
        if m["role"] == "tool" and len(content) > max_chars:
            total_cut += len(content) - max_chars
            m["content"] = content[:max_chars] + f"...[工具输出截断，砍掉 {len(content) - max_chars} 字符]"
    return total_cut

# ============================================================
# 武器 2：summarize —— LLM 压缩最老的几轮为一段摘要
# ============================================================

def summarize_block(msgs, block):
    """把 block（若干条消息）交给 LLM 压缩成一段 100 字内的摘要"""
    text = "\n".join(m.get("content") or "(调用工具)" for m in block)
    prompt = ("把下面这段 Agent 历史轨迹压缩成不超过 100 字的中文摘要，"
              "保留关键事实（读了什么文件、得到什么结论）：\n\n" + text[:4000])
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        timeout=60,
    )
    return resp.choices[0].message.content.strip()

# ============================================================
# 武器 3：truncate —— 从最老开始丢，直到预算内
# ============================================================

def truncate_to_budget(msgs, budget):
    """丢掉最早的块，但永远保留第一条用户消息（任务目标）"""
    goal = msgs[0]
    kept = [goal]
    for m in reversed(msgs[1:]):
        kept.insert(1, m)
        if history_tokens(kept) > budget:
            # 超了：把刚放进去的这条再拿出来（从最老的非目标消息开始丢）
            kept.pop(1)
    return kept, len(msgs) - len(kept)


# ============================================================
# 演示主流程
# ============================================================

if __name__ == "__main__":
    print("=" * 64)
    print("模拟历史：Agent 为找 get_weather 定义读了 3 个大文件 + 3 次天气查询")
    print("=" * 64)

    history = build_history()
    t0 = history_tokens(history)
    print(f"\n原始历史: {len(history)} 条消息, 估算 {t0} tokens")
    print(f"  其中最大一条 tool 消息: {max(len(m.get('content') or '') for m in history)} 字符")

    print("\n[武器 1] trim: 截断单条超长工具输出 (max 400 字符)")
    cut_chars = trim_tool_outputs(history)
    t1 = history_tokens(history)
    print(f"  trim 后: {t1} tokens (砍掉 {cut_chars} 字符, 省 {t0 - t1} tokens)")

    print("\n[武器 2] summarize: 把最老的 2 个文件读取轮压缩成摘要...")
    # 定位最老的两个 read_file 轮（每条 tool 消息往前找它的 assistant 轮）
    block = history[1:5]   # 第 1-2 个大文件读取轮（4 条消息）
    summary = summarize_block(history, block)
    print(f"  摘要结果 ({estimate_tokens(summary)} tokens):\n  {summary}")

    # 用摘要替换 block
    kept_msgs = [history[0]] + [{"role": "assistant", "content": f"[历史摘要] {summary}"}] + history[5:]
    t2 = history_tokens(kept_msgs)
    print(f"  summarize 后: {t2} tokens (对比原始省 {t0 - t2})")

    print("\n[武器 3] truncate: 预算 250 tokens（明显不够），超了就丢最老的")
    final, dropped = truncate_to_budget(kept_msgs, budget=250)
    t3 = history_tokens(final)
    print(f"  truncate 后: {t3} tokens, 共丢弃 {dropped} 条历史消息")
    print(f"  保留结构: {['[用户目标-保留]' if i == 0 else ('[历史摘要]' if '历史摘要' in (m.get('content') or '') else m['role']) for i, m in enumerate(final)]}")

    print("\n" + "=" * 64)
    print("核心原则：丢过程不丢目标 —— 用户请求永远在第一位置")
    print("第四阶段将深入：渐进式加载、历史轨迹管理、断点续跑")
    print("=" * 64)

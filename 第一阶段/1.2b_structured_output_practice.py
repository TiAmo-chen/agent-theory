"""
第一阶段 1.2 补：结构化输出实践
对比 4 种方案的实际效果

使用方法：先在 .env 中填入你的中转站 API 信息，再运行
  python 第一阶段/1.2b_structured_output_practice.py
"""

import json
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

# ============================================================
# 连接你的中转站 API（从 .env 读取）
# ============================================================
client = OpenAI(
    api_key=os.getenv("GPT_API_KEY"),
    base_url=os.getenv("GPT_BASE_URL"),
)
MODEL = os.getenv("GPT_MODEL", "gpt-4o")

# ============================================================
# 目标 Schema：提取代码中的函数信息
# ============================================================
SCHEMA = {
    "type": "object",
    "properties": {
        "functions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "params": {"type": "array", "items": {"type": "string"}},
                    "return_type": {"type": "string"},
                },
                "required": ["name", "params", "return_type"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["functions"],
    "additionalProperties": False,
}

SAMPLE_CODE = """
def get_user(user_id: int, include_email: bool = False) -> dict:
    '''根据 ID 获取用户信息'''
    pass

def create_order(items: list, user_id: int) -> str:
    '''创建订单，返回订单号'''
    pass
"""

# ============================================================
# 方案 1：纯 prompt（无任何保证）
# ============================================================
def method_1_prompt_only():
    print("=" * 60)
    print("方案 1：纯 prompt 要求 JSON")
    print("=" * 60)
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": f"提取以下代码的函数信息，只返回 JSON:\n\n{SAMPLE_CODE}",
            }],
        )
        raw = resp.choices[0].message.content
        print(f"原始返回:\n{raw[:200]}...\n")
        data = json.loads(raw)
        print(f"✅ json.loads 成功: {len(data.get('functions', []))} 个函数")
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
    except Exception as e:
        print(f"⚠️  API 错误: {e}")


# ============================================================
# 方案 2：json_object mode（保证 JSON 语法）
# ============================================================
def method_2_json_object():
    print("=" * 60)
    print("方案 2：response_format json_object")
    print("=" * 60)
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": f"提取代码函数信息。\n\n{SAMPLE_CODE}",
            }],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)
        # 检查结构是否符合预期
        funcs = data.get("functions", [])
        issues = []
        for i, f in enumerate(funcs):
            if "name" not in f:
                issues.append(f"函数 {i} 缺少 name")
            if "params" not in f:
                issues.append(f"函数 {i} 缺少 params")
        print(f"✅ JSON 合法，{len(funcs)} 个函数")
        if issues:
            for issue in issues:
                print(f"  ⚠️  {issue}")
        else:
            print(f"  ✅ 结构也符合预期")
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
    except Exception as e:
        print(f"⚠️  API 错误: {e}")


# ============================================================
# 方案 3：json_schema mode（如果中转站支持）
# ============================================================
def method_3_json_schema():
    print("=" * 60)
    print("方案 3：response_format json_schema（OpenAI strict mode）")
    print("=" * 60)
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": f"提取代码函数信息。\n\n{SAMPLE_CODE}",
            }],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "function_extraction",
                    "strict": True,
                    "schema": SCHEMA,
                },
            },
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)
        funcs = data.get("functions", [])
        print(f"✅ strict json_schema 成功: {len(funcs)} 个函数")
        print(f"   每个函数的字段保证完整且类型正确")
    except Exception as e:
        error_msg = str(e)
        if "json_schema" in error_msg.lower() or "not supported" in error_msg.lower():
            print(f"❌ 中转站不支持 json_schema strict mode")
            print(f"   这是 API 层面的限制，需换用方案 4")
        else:
            print(f"⚠️  其他错误: {e}")


# ============================================================
# 方案 4：validation + retry（不完全依赖 API，自己兜底）
# ============================================================
def validate_schema(data: dict) -> list[str]:
    """手工校验数据是否符合 SCHEMA，返回错误列表"""
    errors = []
    if "functions" not in data:
        return ["缺少顶层 'functions' 字段"]
    if not isinstance(data["functions"], list):
        return ["'functions' 必须是数组"]
    for i, f in enumerate(data["functions"]):
        for key in ["name", "params", "return_type"]:
            if key not in f:
                errors.append(f"函数 {i}: 缺少 '{key}' 字段")
        if "params" in f and not isinstance(f["params"], list):
            errors.append(f"函数 {i}: 'params' 必须是数组")
    return errors


def method_4_validation_retry(max_retries: int = 3):
    print("=" * 60)
    print(f"方案 4：json_object + 自建 schema 校验 + 自动重试（最多 {max_retries} 次）")
    print("=" * 60)

    for attempt in range(1, max_retries + 1):
        print(f"\n第 {attempt} 次尝试...")
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{
                    "role": "user",
                    "content": f"提取代码函数信息，严格按以下 JSON Schema 返回。\n\n"
                               f"Schema: {json.dumps(SCHEMA, ensure_ascii=False)}\n\n"
                               f"代码:\n{SAMPLE_CODE}",
                }],
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
            data = json.loads(raw)
            errors = validate_schema(data)

            if not errors:
                print(f"  ✅ 第 {attempt} 次校验通过: {len(data['functions'])} 个函数")
                return
            else:
                print(f"  ⚠️  第 {attempt} 次校验失败:")
                for e in errors:
                    print(f"     - {e}")
        except json.JSONDecodeError as e:
            print(f"  ⚠️  第 {attempt} 次 JSON 解析失败: {e}")
        except Exception as e:
            print(f"  ⚠️  第 {attempt} 次 API 错误: {e}")

    print(f"\n❌ {max_retries} 次重试后仍未通过校验")


# ============================================================
# 运行全部对比
# ============================================================
if __name__ == "__main__":
    print("API:", os.getenv("GPT_BASE_URL", "未配置"))
    print("Model:", MODEL)
    print()

    method_1_prompt_only()
    print()

    method_2_json_object()
    print()

    method_3_json_schema()
    print()

    method_4_validation_retry()

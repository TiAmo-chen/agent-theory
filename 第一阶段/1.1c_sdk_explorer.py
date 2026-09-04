"""
第一阶段 1.1c：SDK 体检（Explore the SDK）
================================================
不调用任何模型 API，纯用【运行时内省】把本地装的 openai SDK 挨个看一遍：
  客户端能配什么 / 有哪些资源 / chat.completions 有哪些方法 /
  异常家族 / 工具库 / 响应类型。

为什么要看这个？—— 因为你迟早要问"SDK 里到底还有什么"。
与其背文档，不如让脚本对着【你本地实际装的这个版本】打印全貌。

运行: python 第一阶段/1.1c_sdk_explorer.py
"""

import inspect
import os
import pkgutil
import sys

import openai

# Windows 终端默认 GBK，无法处理 emoji，强制 UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def section(title: str):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


# ============================================================
# 1. 版本与安装位置
# ============================================================
section("1. SDK 版本 / 位置")
print(f"  openai.__version__ = {openai.__version__}")
print(f"  安装路径          = {os.path.dirname(openai.__file__)}")

# ============================================================
# 2. 顶层可导出符号（from openai import ... 能拿到什么）
# ============================================================
section("2. 顶层导出符号（openai.__all__）")
for name in openai.__all__:
    print(f"  {name}")

# ============================================================
# 3. 客户端构造参数（OpenAI(...) 能接收什么）
# ============================================================
section("3. 客户端构造参数（OpenAI.__init__）")
sig = inspect.signature(openai.OpenAI.__init__)
for pname, p in sig.parameters.items():
    if pname == "self":
        continue
    print(f"  {pname:<24} default={p.default!r}")

# ============================================================
# 4. client 上挂着的所有资源（client.chat / client.embeddings ...）
# ============================================================
section("4. 客户端上的资源入口（client.<name>）")
try:
    demo_client = openai.OpenAI(api_key="sk-placeholder")  # 不发请求
    resources = [a for a in dir(demo_client) if not a.startswith("_")]
    for r in resources:
        attr = getattr(demo_client, r)
        kind = type(attr).__name__
        print(f"  {r:<20} -> {kind}")
except Exception as e:
    print(f"  内省失败: {e}")

# ============================================================
# 5. chat.completions 的公开方法
# ============================================================
section("5. chat.completions 的公开方法")
try:
    cc = demo_client.chat.completions
    for name in dir(cc):
        if name.startswith("_"):
            continue
        attr = getattr(cc, name)
        kind = "function" if inspect.isfunction(attr) or inspect.ismethod(attr) else type(attr).__name__
        print(f"  {name:<22} -> {kind}")
except Exception as e:
    print(f"  内省失败: {e}")

# ============================================================
# 6. 异常家族（继承树）
# ============================================================
section("6. 异常家族（openai.Error 继承树）")


def build_tree(cls, indent=0):
    subs = cls.__subclasses__()
    if not subs:
        return
    for sub in sorted(subs, key=lambda c: c.__name__):
        print("  " + "  " * indent + f"└─ {sub.__name__}")
        build_tree(sub, indent + 1)


print("  OpenAIError")
build_tree(openai.OpenAIError)

# ============================================================
# 7. 默认常量
# ============================================================
section("7. 默认配置常量")
for const in ["DEFAULT_TIMEOUT", "DEFAULT_MAX_RETRIES", "DEFAULT_CONNECTION_LIMITS"]:
    print(f"  openai.{const} = {getattr(openai, const, 'N/A')!r}")

# ============================================================
# 8. lib 工具库里的模块
# ============================================================
section("8. lib 工具库（openai.lib / openai.lib.streaming）")
try:
    import openai.lib as lib
    print("  openai.lib:")
    for _, name, _ in pkgutil.iter_modules(lib.__path__):
        if name != "__pycache__":
            print(f"    {name}")
except Exception as e:
    print(f"  {e}")

# ============================================================
# 9. 响应类型放哪了（types/chat 下的模型）
# ============================================================
section("9. chat 相关的响应/参数类型（openai.types.chat）")
try:
    import openai.types.chat as chat_types
    for _, name, _ in pkgutil.iter_modules(chat_types.__path__):
        if name.endswith(("_param", "_params", "_union_param", "_allowed")):
            continue  # 只看响应类型，跳过参数类型以免刷屏
        print(f"  {name}")
except Exception as e:
    print(f"  {e}")

# ============================================================
# 小结
# ============================================================
section("小结")
print("""
1. SDK = 客户端(发请求) + 资源(每类能力) + 类型(响应对象) + 异常(错误分类)。
2. 你 99% 时间只碰三样东西：
     OpenAI(...) 建客户端
     client.chat.completions.create(...) 发请求
     返回的 ChatCompletion / 抛出的异常 处理结果
3. 想深入学习哪一块，就把上面 #4 / #5 / #6 / #9 的输出对着官方文档（或源码）看。
4. 这份全景笔记在 -> notes/openai_sdk_全景.md
""")

# -*- coding: utf-8 -*-
"""固定词面断言检查，不依赖 LLM，不能证明事实或立场保真。

设计（见 humanize-zh 对抗测试分析 P0）：
- 本模块仅检查调用方明确列出的字符串：
  - must_contain: 源文本的关键硬事实（数字/年份/专名/书名）必须在输出里出现；
    缺失 = 字符串未匹配，需要复核。
  - must_not_contain: 不允许出现的字符串；不能覆盖未列出的错误。
- 归一化：去空格、全角数字转半角、统一常见标点，再做子串匹配。

用法：
  python3 fidelity.py input.md key.json
  # 退出码 0=PASS 1=FAIL；stdout 打印 PASS/FAIL + 报告
"""
import os
import sys
import json
import argparse


def _norm(s):
    s = s.replace(" ", "").replace("　", "")
    # 全角数字转半角
    s = "".join(chr(ord(c) - 0xFEE0) if 0xFF10 <= ord(c) <= 0xFF19 else c for c in s)
    # 统一常见标点，降低匹配脆弱度
    s = (s.replace("（", "(").replace("）", ")").replace("：", ":")
           .replace("，", ",").replace("。", ".").replace("、", ","))
    return s


def check_fidelity(text, key):
    """返回断言结果；配置无效时抛出 ValueError，不将未配置检查视作通过。"""
    if not isinstance(key, dict):
        raise ValueError("词面断言必须是 JSON 对象")
    for field in ("must_contain", "must_not_contain"):
        values = key.get(field, [])
        if not isinstance(values, list) or any(not isinstance(x, str) or not x.strip() for x in values):
            raise ValueError(field + " 必须为非空字符串组成的数组")
    if not key.get("must_contain") and not key.get("must_not_contain"):
        raise ValueError("至少需要一条 must_contain 或 must_not_contain 断言")
    must = [x for x in (key.get("must_contain") or []) if x]
    must_not = [x for x in (key.get("must_not_contain") or []) if x]
    norm_text = _norm(text)
    missing = [m for m in must if _norm(m) not in norm_text]
    injected = [x for x in must_not if _norm(x) and _norm(x) in norm_text]
    passed = (not missing) and (not injected)
    parts = []
    if missing:
        parts.append("缺失必需字符串: " + " / ".join(missing))
    if injected:
        parts.append("出现禁止字符串: " + " / ".join(injected))
    report = "；".join(parts) if parts else "指定词面断言匹配，语义仍需复核"
    return {"passed": passed, "missing": missing, "injected": injected, "report": report}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="待检文本")
    ap.add_argument("key", help="保真度密钥 JSON（含 must_contain / must_not_contain）")
    args = ap.parse_args()
    try:
        with open(args.input, encoding="utf-8") as source:
            text = source.read()
        with open(args.key, encoding="utf-8") as fixture:
            key = json.load(fixture)
        r = check_fidelity(text, key)
    except (OSError, ValueError, UnicodeError) as exc:
        ap.error(str(exc))
    print(("PASS" if r["passed"] else "FAIL") + " — " + r["report"])
    sys.exit(0 if r["passed"] else 1)


if __name__ == "__main__":
    main()

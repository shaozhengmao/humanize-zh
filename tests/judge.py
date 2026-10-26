# -*- coding: utf-8 -*-
"""LLM 辅助复核：原意与流畅度，可选启用，需 DEEPSEEK_API_KEY。

纯标准库调用 DeepSeek /chat/completions（OpenAI 兼容），无 requests 依赖。
列出新增/改变的断言与可能的立场偏移。模型会漏判或误判，不能充当事实保证。
"""
import os
import json
import urllib.request

ENDPOINT = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"


def _call(system, user):
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY 未设置，跳过 judge")
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=payload, headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return json.loads(data["choices"][0]["message"]["content"])


def fidelity_judge(source, output, fixture_claims=None):
    """返回模型的复核建议与主观分数；高分不能证明完全忠实。"""
    hint = ""
    if fixture_claims:
        hint = "已知原文核心事实 claim：\n" + "\n".join("- " + c for c in fixture_claims) + "\n"
    system = ("你是严谨的事实核查编辑。只输出 JSON，不要解释。"
              "字段：new_claims(数组,output 中原文没有的新事实 claim)，"
              "changed_claims(数组,被改动或弱化的原文 claim)，"
              "stance_shift(布尔,立场是否偏移)，score(0-100,保真度,100=完全忠实)。")
    user = hint + "【原文】\n" + source + "\n\n【改写后】\n" + output
    return _call(system, user)


def fluency_judge(output):
    """返回模型提出的语言问题及主观分数。"""
    system = ("你是中文语言编辑。只输出 JSON。字段：grammar_issues(数组)，"
              "coherence_issues(数组)，score(0-100,流畅度,100=无问题)。")
    user = "【文本】\n" + output
    return _call(system, user)

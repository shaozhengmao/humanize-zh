# -*- coding: utf-8 -*-
"""历史实验工具：提取句长、词频等特征，保留 tell_score 以兼容已有报告。

该分数已出现样本排序反转，不代表 AI 概率、自然程度或写作质量，
下降不代表编辑成功。不能驱动改写或自动删词；只用于观察历史实验。
"""
import re
import json
import math
import sys

TRANSITION_PHRASES = [
    "不可否认", "综合来看", "值得注意的是", "总体而言", "一方面", "另一方面",
    "这意味着", "你可能会", "很多人会以为", "大多数人没注意到",
]
BALANCED_PATTERNS = ["一方面", "另一方面", "综合来看", "总体而言", "不可否认"]
EMOTIONAL_ADJ = ["深受触动", "很有感触", "令人深思", "令人揪心", "极其悲伤",
                 "十分感动", "深有感触", "令人难忘", "很有意义"]
NOT_BUT = re.compile(r"不是.{0,12}而是")
# 历史词频特征；这些词也可能是必要描述或直接引语，不自动删除。
STOCK_REACTION_WORDS = [
    "脊背发凉", "背后一凉", "细思极恐", "让人冷汗", "冷汗直冒",
    "头皮发麻", "毛骨悚然", "不寒而栗", "倒吸一口凉气", "后背发凉",
    "浑身一凛", "背脊发凉",
]
# 强调型「不是…是/而是」变体（对应缺陷：X根本不是A而是B / 写的不是A是B / 并非A而是B）
NOT_BUT_EMPH = re.compile(r"(根本不是|写的不是|并不是|其实不是|恰恰不是|并非).{0,18}(而是|是)")
SENT_SPLIT = re.compile(r"[。！？!?]")


def _cv(vals):
    """变异系数（标准差/均值），衡量不均匀度。"""
    n = len(vals)
    if n < 2:
        return 0.0
    m = sum(vals) / n
    if m <= 0:
        return 0.0
    var = sum((x - m) ** 2 for x in vals) / (n - 1)
    return math.sqrt(var) / m


def split_sentences(text):
    return [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]


def split_paragraphs(text):
    return [p.strip() for p in text.split("\n") if p.strip()]


def features(text):
    sents = split_sentences(text)
    paras = split_paragraphs(text)
    n_sent = len(sents) or 1
    n_para = len(paras) or 1
    sent_lens = [len(s) for s in sents]
    mean_len = sum(sent_lens) / n_sent
    sent_cv = _cv(sent_lens)
    para_cv = _cv([len(p) for p in paras])

    transition_hits = sum(text.count(p) for p in TRANSITION_PHRASES)
    balanced_hits = sum(text.count(p) for p in BALANCED_PATTERNS)
    dash = text.count("\u2014")         # —
    ellipsis = text.count("\u2026\u2026")  # ……
    not_but = len(NOT_BUT.findall(text))
    emo_hits = sum(text.count(w) for w in EMOTIONAL_ADJ)
    stock_reaction = sum(text.count(w) for w in STOCK_REACTION_WORDS)
    not_but_emph = len(NOT_BUT_EMPH.findall(text))
    qmarks = text.count("？") + text.count("?")
    single_para = sum(1 for p in paras if len(split_sentences(p)) <= 1)
    single_para_ratio = single_para / n_para

    return {
        "n_sent": n_sent,
        "mean_sent_len": round(mean_len, 1),
        "sent_len_cv": round(sent_cv, 3),
        "para_len_cv": round(para_cv, 3),
        "transition_hits": transition_hits,
        "balanced_hits": balanced_hits,
        "dash_count": dash,
        "ellipsis_count": ellipsis,
        "not_but_count": not_but,
        "emo_adj_hits": emo_hits,
        "stock_reaction_hits": stock_reaction,
        "not_but_emph": not_but_emph,
        "qmark_count": qmarks,
        "single_para_ratio": round(single_para_ratio, 3),
    }


def tell_score(f):
    """历史启发式分数；不能用于判断来源或质量。"""
    uniformity = 1 - min(1.0, f["sent_len_cv"] / 0.8)
    trans_density = min(1.0, f["transition_hits"] / max(1, f["n_sent"]) * 3)
    balanced = min(1.0, f["balanced_hits"] / 2.0)
    stock = min(1.0, f["stock_reaction_hits"])
    notbut = min(1.0, f["not_but_emph"] / 2.0)
    low_single = 1 - f["single_para_ratio"]
    # 新增 stock / notbut 两路：对应「伪具体库存反应词」「强调型不是…是」
    score = 100 * (0.35 * uniformity + 0.28 * trans_density
                   + 0.17 * balanced + 0.08 * low_single
                   + 0.07 * stock + 0.05 * notbut)
    return round(score, 1)


if __name__ == "__main__":
    t = sys.stdin.read()
    f = features(t)
    f["tell_score"] = tell_score(f)
    print(json.dumps(f, ensure_ascii=False, indent=2))

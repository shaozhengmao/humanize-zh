# -*- coding: utf-8 -*-
"""humanize-zh 验证 harness（确定性部分，纯标准库）。

用法：
  python3 score.py                 # 展示历史特征分布
  python3 score.py --rewrites DIR  # 额外对 DIR 下 <id>.md 改写结果算前/后 delta
  python3 score.py --rewrites DIR --judge
                                   # 在 delta 基础上启用 LLM judge（需 DEEPSEEK_API_KEY）
                                   # 辅助复核原意与流畅度，不提供正确性保证

设计要点（见 README）：
- 历史特征与改写差异报告，不据此证明写作效果或文本来源。
- 固定词面断言与原文数量核对不依赖 API；可选 judge 仅作复核建议。
"""
import os
import sys
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from linter import features, tell_score  # noqa
from claimcheck import check as check_claims

from judge import fidelity_judge, fluency_judge  # noqa
from fidelity import check_fidelity  # noqa


def load_manifest():
    with open(os.path.join(HERE, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def read_text(rel):
    with open(os.path.join(HERE, rel), encoding="utf-8") as f:
        return f.read().strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rewrites", default=None, help="含 <id>.md 改写结果的目录")
    ap.add_argument("--judge", action="store_true", help="启用 LLM judge（需 DEEPSEEK_API_KEY）")
    args = ap.parse_args()
    if args.rewrites and not os.path.isdir(args.rewrites):
        ap.error("改写目录不存在: " + args.rewrites)

    manifest = load_manifest()
    rows = []
    for s in manifest["samples"]:
        text = read_text(s["file"])
        f = features(text)
        f["tell_score"] = tell_score(f)
        f["id"] = s["id"]
        f["genre"] = s["genre"]
        f["kind"] = s["kind"]
        rows.append((s, f))

    print("\n=== 历史特征报告（分数不代表来源或质量）===")
    print(f"{'id':<22}{'kind':<7}{'tell':>6}{'sentCV':>7}{'trans':>6}{'bal':>5}{'stock':>6}{'emph':>5}")
    for s, f in rows:
        print(f"{f['id']:<22}{f['kind']:<7}{f['tell_score']:>6}{f['sent_len_cv']:>7}"
              f"{f['transition_hits']:>6}{f['balanced_hits']:>5}{f['stock_reaction_hits']:>6}{f['not_but_emph']:>5}")

    print("\n=== 分文体历史分数均值（不设通过阈值）===")
    genres = {}
    for s, f in rows:
        genres.setdefault(s["genre"], {"ai": [], "human": [], "edge": []})
        genres[s["genre"]][s["kind"]].append(f["tell_score"])
    print(f"{'genre':<14}{'ai_mean':>9}{'human_mean':>11}{'delta':>8}")
    for g, d in genres.items():
        if not d["ai"] or not d["human"]:
            continue
        ai = sum(d["ai"]) / len(d["ai"]) if d["ai"] else 0.0
        hu = sum(d["human"]) / len(d["human"]) if d["human"] else 0.0
        print(f"{g:<14}{ai:>9.1f}{hu:>11.1f}{ai - hu:>8.1f}")

    if args.rewrites:
        print("\n=== 改写前/后历史分数差异（下降不代表成功）===")
        compared = 0
        for s, f in rows:
            if s["kind"] != "ai":
                continue
            rp = os.path.join(args.rewrites, s["id"] + ".md")
            if not os.path.exists(rp):
                continue
            compared += 1
            with open(rp, encoding="utf-8") as rewritten:
                out = rewritten.read().strip()
            of = features(out)
            after = tell_score(of)
            print(f"{s['id']:<24} before={f['tell_score']:>5} after={after:>5} d={f['tell_score'] - after:>5.1f}")
            problems, _, warnings = check_claims(read_text(s["file"]), out)
            print(f"    原文词面差异={problems} 引语待复核={warnings}")
            fix = s.get("fixture")
            kj = None
            if fix:
                with open(os.path.join(HERE, fix), encoding="utf-8") as fixture:
                    kj = json.load(fixture)
            if kj is not None and ("must_contain" in kj or "must_not_contain" in kj):
                fr = check_fidelity(out, kj)
                print(f"    固定词面断言={'PASS' if fr['passed'] else 'FAIL'} "
                      f"缺失={fr['missing']} 禁止字符串={fr['injected']}")
            if args.judge:
                if kj:
                    claims = kj.get("claims")
                    try:
                        fj = fidelity_judge(read_text(s["file"]), out, claims)
                        lj = fluency_judge(out)
                        print(f"    辅助复核(LLM)={fj.get('score')} 新claim={fj.get('new_claims')} "
                              f"改变claim={fj.get('changed_claims')} "
                              f"立场偏移={fj.get('stance_shift')} 流畅度={lj.get('score')}")
                    except Exception as e:
                        print(f"    judge 失败: {e}")
        print(f"\n实际比较 {compared} 份改写；未匹配 id 的文件不会被检查。")


if __name__ == "__main__":
    main()

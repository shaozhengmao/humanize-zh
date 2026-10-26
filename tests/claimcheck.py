# -*- coding: utf-8 -*-
"""词面辅助核对：数量及单位、年份、书名；不能证明语义或立场保真。

支持常见中文/阿拉伯数量转换。直接引语变化仅提示人工核对，允许忠实转述。
不覆盖数量与主体的对应关系、否定、因果、信源、人名或任意同义表达。
用法：python3 claimcheck.py 原文.md 输出.md；0=未发现差异，1=有差异，2=输入错误。
"""
import argparse
from decimal import Decimal
from pathlib import Path
import re
import unicodedata

UNITS = r"个百分点|人民币|小时|分钟|个月|公斤|千米|公里|美元|万元|亿元|元|%|倍|个|年|月|日|天|秒|次|人|成|件|层|轮|条|位|岁|份|家|台|本|匹|米|吨|亩"
RE_QUANTITY = re.compile(
    r"(?P<arab>[+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<scale>[十百千万亿]?)\s*(?P<au>" + UNITS + r")?"
    r"|(?P<cn>[零〇一二三四五六七八九十百千万亿两半]+)\s*(?P<cu>" + UNITS + r")"
)
RE_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
RE_BOOK = re.compile(r"《[^》\n]+》")
RE_QUOTE = re.compile(r'“([^”\n]+)”|「([^」\n]+)」|"([^"\n]+)"')
DIGITS = dict(zip("零〇一二三四五六七八九两", (0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 2)))
SCALES = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 100000000}


def normalize(text):
    return unicodedata.normalize("NFKC", text)


def chinese_number(text):
    if text == "半":
        return Decimal("0.5")
    if all(c in DIGITS for c in text):
        return Decimal("".join(str(DIGITS[c]) for c in text))
    for marker in ("亿", "万"):
        if marker in text:
            left, right = text.split(marker, 1)
            return chinese_number(left or "一") * SCALES[marker] + (chinese_number(right) if right else 0)
    total = section = digit = 0
    for c in text:
        if c in DIGITS:
            digit = DIGITS[c]
        elif c in SCALES:
            scale = SCALES[c]
            if scale < 10000:
                section += (digit or 1) * scale
            else:
                section = (section + digit) * scale
                total += section
                section = 0
            digit = 0
        else:
            raise ValueError("不支持的中文数量: " + text)
    return Decimal(total + section + digit)


def extract(text):
    text = normalize(text)
    quantities = set()
    for match in RE_QUANTITY.finditer(text):
        if match["arab"]:
            value = Decimal(match["arab"].replace(",", ""))
            value *= SCALES.get(match["scale"], 1)
            unit = match["au"] or ""
        else:
            try:
                value = chinese_number(match["cn"])
            except ValueError:
                continue
            unit = match["cu"]
        if unit in ("万元", "亿元"):
            value *= SCALES[unit[0]]
            unit = "元"
        if unit == "成":
            value *= 10
            unit = "%"
        if unit == "个月":
            unit = "月"
        if not unit and value == value.to_integral() and 1900 <= value <= 2099:
            unit = "年"
        quantities.add((value, unit))
    quotes = {next(v for v in m.groups() if v is not None) for m in RE_QUOTE.finditer(text)}
    return {"quantities": quantities, "years": set(RE_YEAR.findall(text)),
            "books": set(RE_BOOK.findall(text)), "quotes": quotes}


def _labels(quantities):
    return [format(n, "f") + unit for n, unit in sorted(quantities)]


def check(src_text, out_text):
    src, out = extract(src_text), extract(out_text)
    problems = []
    if not out_text.strip():
        problems.append(("输出为空", ["需要人工处理"]))
    for label, values in (
        ("缺失或改变数量/单位", _labels(src["quantities"] - out["quantities"])),
        ("新增或改变数量/单位", _labels(out["quantities"] - src["quantities"])),
        ("缺失年份", sorted(src["years"] - out["years"])),
        ("缺失书名", sorted(src["books"] - out["books"])),
        ("新增书名", sorted(out["books"] - src["books"])),
    ):
        if values:
            problems.append((label, values))
    warnings = sorted(src["quotes"] - out["quotes"])
    return problems, {"src": src, "out": out}, warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()
    try:
        problems, _, warnings = check(Path(args.source).read_text(encoding="utf-8"),
                                     Path(args.output).read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        parser.error(str(exc))
    for warning in warnings:
        print("[需复核] 引语被删除或转述: " + warning)
    for label, values in problems:
        print(label + ": " + " / ".join(values))
    print("发现词面差异" if problems else "未发现所检查项目的词面差异")
    print("此结果不能证明事实、立场或引语保真；数量与主体关系、信源等仍需人工复核。")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""检查 skill 包的元数据与本地引用；不评价文风或固定章节措辞。"""
import argparse
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def check_package(path):
    text = path.read_text(encoding="utf-8")
    errors = []
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.S)
    if not match:
        return ["缺少 frontmatter"]
    # This package uses simple one-line fields. Full YAML validation is separate.
    fields = {}
    for line in match[1].splitlines():
        key, sep, value = line.partition(":")
        if not sep or key not in ("name", "description"):
            errors.append("不支持的元数据格式: " + line)
            continue
        if key in fields:
            errors.append("重复元数据: " + key)
        fields[key] = value.strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fields.get("name", "")):
        errors.append("name 无效")
    if fields.get("name") != path.parent.name:
        errors.append("name 与 skill 目录不一致")
    if not fields.get("description") or len(fields["description"]) > 1024:
        errors.append("description 为空或过长")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        if "://" in target or target.startswith("#"):
            continue
        target_path = (path.parent / target.split("#", 1)[0]).resolve()
        if not target_path.is_relative_to(path.parent.resolve()):
            errors.append("引用超出独立 skill 包: " + target)
        elif not target_path.is_file():
            errors.append("引用不存在: " + target)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path,
                        default=HERE.parent / "humanize-zh-writing" / "SKILL.md")
    parser.add_argument("--selftest", action="store_true", help="同时运行工具回归测试")
    args = parser.parse_args()
    errors = check_package(args.path)
    for error in errors:
        print("FAIL: " + error)
    if errors:
        return 1
    print("包结构检查通过；不代表写作效果已验证。")
    if args.selftest:
        return subprocess.run([sys.executable, "-B", "-m", "unittest", "discover",
                               "-s", str(HERE), "-p", "test_*.py"], check=False).returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

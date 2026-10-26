# -*- coding: utf-8 -*-
"""工具行为回归；不把提示词字符串匹配当作文章质量测试。"""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import claimcheck
import gate
import score
from check_skill import check_package
from fidelity import check_fidelity


class ClaimCheckTests(unittest.TestCase):
    def test_deleted_amount_is_reported(self):
        self.assertTrue(claimcheck.check("项目预算500万元。", "项目继续推进。")[0])

    def test_changed_unit_is_reported(self):
        for source, output in [("三个人", "三个月"), ("预算500万元", "预算500元")]:
            with self.subTest(source=source):
                self.assertTrue(claimcheck.check(source, output)[0])

    def test_equivalent_quantity_formats(self):
        for source, output in [("预算500万元", "预算5000000元"), ("三个月", "3个月"),
                               ("占四成", "占40%"), ("1944年", "1944"),
                               ("预算一万亿元", "预算1000000000000元"),
                               ("预算５００万元", "预算500万元")]:
            with self.subTest(source=source):
                self.assertFalse(claimcheck.check(source, output)[0])

    def test_new_amount_is_reported(self):
        self.assertTrue(claimcheck.check("项目启动。", "项目投入100万元。")[0])

    def test_quote_paraphrase_requires_review(self):
        problems, _, warnings = claimcheck.check("他说：“暂不投资”。", "他表示暂不投资。")
        self.assertFalse(problems)
        self.assertEqual(warnings, ["暂不投资"])

    def test_semantic_limit_is_explicit(self):
        # A clean lexical report must never be presented as proof of semantic fidelity.
        self.assertFalse(claimcheck.check("不建议投资。", "建议投资。")[0])

    def test_empty_output_is_rejected(self):
        self.assertTrue(claimcheck.check("一篇没有数字的文章。", "")[0])


class FixtureTests(unittest.TestCase):
    def test_invalid_or_empty_checks_are_rejected(self):
        for key in (None, {}, [], {"claims": ["事实"]}, {"must_contain": "1944"},
                    {"must_contain": [""]}, {"must_not_contain": None}):
            with self.subTest(key=key), self.assertRaises(ValueError):
                check_fidelity("原文", key)

    def test_configured_assertions(self):
        key = {"must_contain": ["1944"], "must_not_contain": ["1943"]}
        self.assertTrue(check_fidelity("１９４４", key)["passed"])
        self.assertFalse(check_fidelity("1943", key)["passed"])

    def test_unlisted_fabrication_is_out_of_scope(self):
        self.assertTrue(check_fidelity("1944，有未经验证的新结论。",
                                       {"must_contain": ["1944"]})["passed"])


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input.md"
        self.output = self.root / "output.md"

    def run_gate(self, text, responses=None, extra=()):
        self.source.write_text(text, encoding="utf-8")
        stdout, stderr = io.StringIO(), io.StringIO()
        env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
        if responses is not None:
            env["DEEPSEEK_API_KEY"] = "mock-key"
        with patch.dict(os.environ, env, clear=True), patch.object(
            gate, "_call_text", side_effect=responses or []
        ) as call, patch("sys.argv", ["gate.py", str(self.source), *extra]), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = gate.main()
        return code, stdout.getvalue(), stderr.getvalue(), call

    def test_direct_quote_is_not_mechanically_deleted(self):
        text = "她说：“头皮发麻”。\n"
        key = self.root / "key.json"
        key.write_text(json.dumps({"must_contain": ["头皮发麻"]}), encoding="utf-8")
        code, output, _, call = self.run_gate(text, [text], ["--key", str(key)])
        self.assertEqual((code, output), (0, text))
        self.assertEqual(call.call_count, 1)

    def test_default_has_no_voice_injection(self):
        text = "今天下雨。"
        code, output, _, call = self.run_gate(text, [text])
        self.assertEqual((code, output), (0, text))
        self.assertEqual(call.call_args.args[0], gate.build_system(gate._read(gate.SKILL_PATH)))

    def test_explicit_voice_is_loaded(self):
        voice = self.root / "style.md"
        voice.write_text("用户选择的风格样本", encoding="utf-8")
        _, _, _, call = self.run_gate("今天下雨。", ["今天下雨。"], ["--voice", str(voice)])
        self.assertIn("用户选择的风格样本", call.call_args.args[0])

    def test_retry_uses_source_and_checks_final_result(self):
        source = "预算500万元。"
        code, output, _, call = self.run_gate(source, ["预算500元。", "预算为500万元。"])
        self.assertEqual((code, output), (0, "预算为500万元。"))
        self.assertEqual(call.call_count, 2)
        self.assertIn(source, call.call_args.args[1])

    def test_rejected_candidate_does_not_overwrite_file(self):
        self.output.write_text("已有终稿", encoding="utf-8")
        code, output, _, _ = self.run_gate("预算500万元。", ["预算500元。"],
                                          ["--max-retries", "1", "--out", str(self.output)])
        self.assertEqual((code, output), (2, ""))
        self.assertEqual(self.output.read_text(encoding="utf-8"), "已有终稿")

    def test_api_failure_after_rejection_outputs_nothing(self):
        code, output, _, _ = self.run_gate("预算500万元。", ["预算500元。", RuntimeError("mock failure")])
        self.assertEqual((code, output), (1, ""))

    def test_warn_only_is_explicit(self):
        code, output, stderr, _ = self.run_gate("预算500万元。", ["预算500元。"],
                                               ["--max-retries", "1", "--warn-only"])
        self.assertEqual((code, output), (0, "预算500元。"))
        self.assertIn("待复核", stderr)

    def test_no_api_preserves_original_exactly(self):
        text = "  她说：“头皮发麻”。\n\n"
        code, output, stderr, call = self.run_gate(text)
        self.assertEqual((code, output), (0, text))
        call.assert_not_called()
        self.assertIn("未经改写", stderr)

    def test_empty_candidate_is_rejected(self):
        code, output, _, _ = self.run_gate("今天下雨。", [""], ["--max-retries", "1"])
        self.assertEqual((code, output), (2, ""))

    def test_invalid_retry_count_stops_before_api(self):
        with self.assertRaises(SystemExit) as exc:
            self.run_gate("今天下雨。", ["今天下雨。"], ["--max-retries", "0"])
        self.assertEqual(exc.exception.code, 2)

    def test_invalid_fixture_stops_before_api(self):
        key = self.root / "key.json"
        key.write_text("null", encoding="utf-8")
        with self.assertRaises(SystemExit) as exc:
            self.run_gate("今天下雨。", ["今天下雨。"], ["--key", str(key)])
        self.assertEqual(exc.exception.code, 2)


class PackageTests(unittest.TestCase):
    def test_package_is_self_contained(self):
        self.assertFalse(check_package(gate.SKILL_PATH))

    def test_missing_reference_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "example"
            root.mkdir()
            path = root / "SKILL.md"
            path.write_text("---\nname: example\ndescription: 示例\n---\n[参考](missing.md)", encoding="utf-8")
            self.assertTrue(check_package(path))


class ScoreTests(unittest.TestCase):
    def test_rewrite_claims_checked_without_judge(self):
        sample = {"id": "sample", "genre": "test", "kind": "ai", "file": "unused"}
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "sample.md").write_text("预算500元。", encoding="utf-8")
            stdout = io.StringIO()
            with patch.object(score, "load_manifest", return_value={"samples": [sample]}), \
                    patch.object(score, "read_text", return_value="预算500万元。"), \
                    patch.object(score, "fidelity_judge") as judge, \
                    patch("sys.argv", ["score.py", "--rewrites", folder]), \
                    contextlib.redirect_stdout(stdout):
                score.main()
            self.assertIn("缺失或改变数量/单位", stdout.getvalue())
            self.assertIn("实际比较 1 份", stdout.getvalue())
            judge.assert_not_called()


if __name__ == "__main__":
    unittest.main()

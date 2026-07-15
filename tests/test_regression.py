# -*- coding: utf-8 -*-
"""确定性回归：只测试脚本边界，不评价 LLM 写稿质量。"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_docx = load_module("build_docx", SCRIPTS / "build_docx.py")


class BuildDocxTests(unittest.TestCase):
    def test_tips_render_as_two_blocks(self):
        data = {
            "link": "",
            "title": "测试标题",
            "script": "测试正文",
            "notes": [],
            "tips": [{"text": "适用人群，寒湿偏重者。禁忌人群，孕妇慎用。注意，不宜久用。"}],
            "processing": [],
        }
        doc = Document()
        build_docx.render_item(doc, data)
        paragraphs = [p.text for p in doc.paragraphs if p.text.startswith("【")]

        self.assertEqual(2, len(paragraphs))
        self.assertEqual("【适用人群，寒湿偏重者。】", paragraphs[0])
        self.assertIn("禁忌人群", paragraphs[1])
        self.assertIn("注意", paragraphs[1])

    def test_tips_without_contraindication_stay_in_one_block(self):
        self.assertEqual(["适用人群，寒湿偏重者。注意，不宜久用。"], build_docx.split_tips(
            "适用人群，寒湿偏重者。注意，不宜久用。"
        ))

    def test_internal_review_data_are_rejected(self):
        forbidden_values = [
            {"internal_review": {}},
            {"medical_review": {}},
            {"review_note": "内部记录"},
            {"licensed_physician_review_required": True},
            {"items": [{"script": "以上为通用知识，请执业医师复核"}]},
        ]
        for data in forbidden_values:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    build_docx.validate_public_input(data)


class ValidateOutputCliTests(unittest.TestCase):
    script = str(SCRIPTS / "validate_output.py")

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, self.script, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_unknown_argument_fails(self):
        result = self.run_cli("测试正文", "--herbz", "荷叶10克")
        self.assertEqual(2, result.returncode)
        self.assertIn("unrecognized arguments", result.stderr)

    def test_all_locks_pass_when_preserved(self):
        text = "腰腿疼痛遇冷容易反复，可准备桃树叶一大把、生姜五片（需辨证为寒湿痹阻）。"
        result = self.run_cli(
            text,
            "--formula-items", "桃树叶一大把,生姜五片",
            "--diseases", "腰腿疼痛",
            "--syndromes", "寒湿痹阻",
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_each_lock_type_blocks_when_missing(self):
        cases = [
            ("--formula-items", "桃树叶一大把", "方剂条目"),
            ("--diseases", "腰腿疼痛", "病症"),
            ("--syndromes", "寒湿痹阻", "证型"),
        ]
        for flag, value, label in cases:
            with self.subTest(flag=flag):
                result = self.run_cli("这是一段合规测试正文。", flag, value)
                self.assertEqual(1, result.returncode)
                self.assertIn(label, result.stdout)

    def test_absolute_medical_claims_are_blocking(self):
        error_cases = [
            ("今天讲的方法不让你多花一分冤枉钱。", "outcome-guarantee"),
            ("这个病的根子就是湿热。", "absolute-causation"),
            ("这些表现全都是气血不足引起的。", "absolute-causation"),
        ]
        for text, issue_id in error_cases:
            with self.subTest(text=text):
                result = self.run_cli(text, "--json")
                self.assertEqual(1, result.returncode)
                report = json.loads(result.stdout)
                self.assertIn(issue_id, {issue["id"] for issue in report["errors"]})

    def test_qualified_and_natural_phrasing_has_no_new_warning(self):
        good_cases = [
            "这些知识能让你少花冤枉钱。",
            "我会继续分享实用的健康知识。",
            "在中医看来，这类情况常和湿热有关。",
            "先判断问题的根子是什么。",
            "体检查出胆结石，先别慌。",
            "今天讲的这个方法你记好。",
            "你要是已经记好了步骤，再往下做。",
        ]
        for text in good_cases:
            with self.subTest(text=text):
                result = self.run_cli(text)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertNotIn("不可控结果保证", result.stdout)
                self.assertNotIn("医学归因可能过于绝对", result.stdout)

    def test_legacy_herbs_alias_still_works(self):
        result = self.run_cli("方中用荷叶10克。", "--herbs", "荷叶10克")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


class GuidanceLibraryTests(unittest.TestCase):
    def test_library_is_clean_and_deduplicated(self):
        path = ROOT / "references" / "guidance_library.json"
        entries = json.loads(path.read_text(encoding="utf-8"))
        normalized = set()
        for index, entry in enumerate(entries):
            with self.subTest(index=index):
                self.assertIsInstance(entry, (str, dict))
                text = entry if isinstance(entry, str) else entry.get("text", "")
                self.assertTrue(text.strip())
                key = "".join(ch for ch in text if ch.isalnum())
                self.assertNotIn(key, normalized)
                normalized.add(key)
                self.assertNotIn("您", text)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""v2 确定性回归：canonical handoff、引导语治理和导出门禁。"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


count_chars = load_module("count_chars_v2", SCRIPTS / "count_chars.py")
pick_guidance = load_module("pick_guidance_v2", SCRIPTS / "pick_guidance.py")
validate_output = load_module("validate_output_v2", SCRIPTS / "validate_output.py")
build_docx = load_module("build_docx_v2", SCRIPTS / "build_docx.py")


def lock(raw, locked_text=None, normalization=None, provenance="source_verbatim"):
    return {
        "raw": raw,
        "locked_text": locked_text or raw,
        "normalization": normalization or [],
        "provenance": provenance,
        "requires_approval": False,
    }


def valid_item(script=None, source_text=None):
    if script is None:
        script = "腰腿疼痛遇冷容易反复，可以准备桃树叶一大把、生姜五片（需辨证为寒湿痹阻）记不住先收藏，用的时候翻出来看。"
    if source_text is None:
        source_text = "腰腿疼痛反复发作，取桃树叶一大把、生姜五片泡脚。"
    return {
        "source": {"link": "https://example.com/video", "title": "腰腿疼痛泡脚方", "text": source_text},
        "locks": {
            "formula_items": [lock("桃树叶一大把"), lock("生姜五片")],
            "diseases": [lock("腰腿疼痛")],
            "syndromes": [lock("寒湿痹阻", provenance="review_approved")],
            "numeric_hooks": [],
        },
        "title_decision": {"type": "unchanged", "rationale": ""},
        "manual_checks": {key: True for key in build_docx.MANUAL_CHECK_KEYS},
        "warning_decisions": {},
        "public": {
            "link": "https://example.com/video",
            "title": "腰腿疼痛泡脚方",
            "script": script,
            "notes": [],
            "tips": [{"text": "适用人群，寒湿偏重者。禁忌人群，皮肤破损者不宜。注意，水温不宜过高。"}],
            "processing": [],
        },
    }


def valid_handoff(items=None, filename="腰腿疼痛-洗稿文档"):
    return {"schema_version": "2", "stage": "rewritten", "filename": filename, "items": items or [valid_item()]}


class CountCharsV2Tests(unittest.TestCase):
    def test_boundaries_and_newlines(self):
        self.assertEqual(300, count_chars.count("字" * 150 + "\r\n" + "字" * 150))
        self.assertEqual(301, count_chars.count("字" * 301))


class ValidateOutputV2Tests(unittest.TestCase):
    def test_empty_script_fails(self):
        self.assertIn("empty-script", {x["id"] for x in validate_output.validate_text("")["errors"]})

    def test_300_passes_and_301_fails(self):
        self.assertFalse(validate_output.validate_text("字" * 300)["errors"])
        self.assertIn("max-chars", {x["id"] for x in validate_output.validate_text("字" * 301)["errors"]})

    def test_forbidden_punctuation_and_units_fail(self):
        for text in ("注意：慢慢看", "这件事——要记住", "他说“可以”", '写成"这样"', "荷叶10g"):
            with self.subTest(text=text):
                self.assertTrue(validate_output.validate_text(text)["errors"])

    def test_all_lock_types_pass_when_preserved(self):
        locks = {
            "formula_items": [lock("桃树叶一大把"), lock("生姜五片")],
            "diseases": [lock("腰腿疼痛")],
            "syndromes": [lock("寒湿痹阻")],
            "numeric_hooks": [lock("90%")],
        }
        text = "90%的腰腿疼痛可以准备桃树叶一大把、生姜五片（需辨证为寒湿痹阻）"
        self.assertFalse(validate_output.validate_text(text, locks)["errors"])

    def test_each_missing_lock_fails(self):
        for key, value in (("formula_items", "荷叶10克"), ("diseases", "脂肪肝"), ("syndromes", "痰湿内盛"), ("numeric_hooks", "90%")):
            locks = {name: [] for name in build_docx.LOCK_KEYS}
            locks[key] = [lock(value)]
            with self.subTest(key=key):
                issue_ids = {x["id"] for x in validate_output.validate_text("普通正文", locks)["errors"]}
                expected_id = "missing-syndrome-annotation" if key == "syndromes" else "missing-lock"
                self.assertIn(expected_id, issue_ids)

    def test_medical_claims_and_self_treatment_block(self):
        for text in ("这个病的根子就是湿热。", "这些表现全都是气血不足引起的。", "小毛病自己就能调。", "保证你以后不用跑医院。"):
            with self.subTest(text=text):
                self.assertTrue(validate_output.validate_text(text)["errors"])


    def test_editorial_tone_blocks_known_failures_and_variants(self):
        bad_cases = (
            "关键是先看自己到底适不适合。",
            "重点是要先判断这个方法是否适合自己。",
            "视物模糊不一定都是这个原因。",
            "这些表现未必全由湿热导致。",
            "在辨证合适的前提下再使用。",
            "先把原因和证型辨清，再看这个思路适不适合。",
        )
        for text in bad_cases:
            with self.subTest(text=text):
                self.assertIn("editorial-tone", {x["id"] for x in validate_output.validate_text(text)["errors"]})

    def test_editorial_tone_does_not_block_natural_oral_phrasing(self):
        good_cases = (
            "平时腰膝酸软的朋友可以试试。",
            "中医讲究辨证论治。",
            "在中医看来，这类情况常和湿热有关。",
            "这类视物模糊常和用眼疲劳有关。",
        )
        for text in good_cases:
            with self.subTest(text=text):
                self.assertNotIn("editorial-tone", {x["id"] for x in validate_output.validate_text(text)["errors"]})

    def test_syndrome_annotation_authorization_format_and_count(self):
        no_syndrome = {name: [] for name in build_docx.LOCK_KEYS}
        self.assertFalse(validate_output.validate_text("普通口播正文", no_syndrome)["errors"])
        self.assertIn(
            "unexpected-syndrome-annotation",
            {x["id"] for x in validate_output.validate_text("普通正文（需辨证为肝火上炎）", no_syndrome)["errors"]},
        )

        locks = {name: [] for name in build_docx.LOCK_KEYS}
        locks["syndromes"] = [lock("肝火上炎")]
        good = "能帮助清肝明目（需辨证为肝火上炎）"
        self.assertFalse(validate_output.validate_text(good, locks)["errors"])

        bad_cases = {
            "肝火上炎的人可以了解这个思路。": "missing-syndrome-annotation",
            "（需辨证为肝火上炎）（需辨证为肝火上炎）": "duplicate-syndrome-annotation",
            "（需辨证为痰湿内盛）": "invalid-syndrome-annotation",
            "（需辨证为肝火上炎，伴眼红眼干）": "invalid-syndrome-annotation",
            "(需辨证为肝火上炎)": "invalid-syndrome-annotation",
            "（辨证为肝火上炎）": "invalid-syndrome-annotation",
            "需辨证为肝火上炎。": "invalid-syndrome-annotation",
            "在辨证合适的前提下，能帮助清肝明目（需辨证为肝火上炎）": "editorial-tone",
        }
        for text, issue_id in bad_cases.items():
            with self.subTest(text=text):
                self.assertIn(issue_id, {x["id"] for x in validate_output.validate_text(text, locks)["errors"]})

    def test_ten_character_copy_and_lock_exemption(self):
        source = "今天这个珍藏多年的方法一定要认真看完"
        self.assertIn("verbatim-copy", {x["id"] for x in validate_output.validate_text(source, source_text=source)["errors"]})
        locks = {"formula_items": [], "diseases": [], "syndromes": [], "numeric_hooks": [lock(source)]}
        self.assertNotIn("verbatim-copy", {x["id"] for x in validate_output.validate_text(source, locks, source)["errors"]})

    def test_repeated_today_preview_is_blocked(self):
        bad_text = "今天要说的方法很简单。今天跟大家分享的这招，很多人花钱都学不到。"
        issue_ids = {x["id"] for x in validate_output.validate_text(bad_text)["errors"]}
        self.assertIn("today-preview-repeat", issue_ids)

    def test_single_today_preview_passes(self):
        good_text = "今天要说的方法很简单，青葙子10到15克煎水服用，记不住先收藏。"
        self.assertEqual([], validate_output.validate_text(good_text)["errors"])

    def test_popsci_bridge_transitions_are_blocked(self):
        for text in ("在中医看来和肝火有关，常会用到青葙子", "临床上常用这味药", "顺着这个思路，一般会用"):
            with self.subTest(text=text):
                issue_ids = {x["id"] for x in validate_output.validate_text(text)["errors"]}
                self.assertIn("popsci-bridge", issue_ids)


class GuidanceLibraryV2Tests(unittest.TestCase):
    def test_library_schema_and_status(self):
        items = pick_guidance.load_items(ROOT / "references" / "guidance_library.json")
        self.assertGreater(len(items), 20)
        for item in items:
            self.assertEqual(item["char_count"], len(item["text"]))
            self.assertIn(item["status"], {"approved", "quarantined"})
            self.assertNotIn("您", item["text"])

    def test_known_risky_entries_are_quarantined(self):
        items = pick_guidance.load_items(ROOT / "references" / "guidance_library.json")
        risky = [x for x in items if any(word in x["text"] for word in ("小毛病，咱不求人", "药店就要干不下去", "回去试一试", "腰腿疼痛"))]
        self.assertTrue(risky)
        self.assertTrue(all(x["status"] == "quarantined" for x in risky))

    def test_seed_is_reproducible_and_budget_is_respected(self):
        items = [x for x in pick_guidance.load_items(ROOT / "references" / "guidance_library.json") if x["status"] == "approved" and x["char_count"] <= 75]
        self.assertEqual(pick_guidance.pick(items, 3, seed=42), pick_guidance.pick(items, 3, seed=42))
        self.assertTrue(all(x["char_count"] <= 75 for x in pick_guidance.pick(items, 3, seed=42)))

    def test_invalid_object_schema_fails(self):
        with self.assertRaises(pick_guidance.LibraryError):
            pick_guidance.parse_entry({"text": "内容", "universal": True}, 1)


class BuildDocxV2Tests(unittest.TestCase):
    def test_valid_handoff_exports_exact_validated_script(self):
        data = valid_handoff()
        with tempfile.TemporaryDirectory() as output_dir:
            path, count, reports = build_docx.build(data, output_dir)
            text = "\n".join(p.text for p in Document(path).paragraphs)
        self.assertEqual(1, count)
        self.assertFalse(reports[0]["errors"])
        self.assertIn(data["items"][0]["public"]["script"], text)

    def test_invalid_script_does_not_export(self):
        item = valid_item(script="")
        with tempfile.TemporaryDirectory() as output_dir:
            with self.assertRaises(ValueError):
                build_docx.build(valid_handoff([item]), output_dir)
            self.assertEqual([], list(Path(output_dir).iterdir()))

    def test_missing_lock_manifest_fails(self):
        data = valid_handoff()
        del data["items"][0]["locks"]["numeric_hooks"]
        with self.assertRaises(ValueError):
            build_docx.validate_handoff(data)

    def test_unhandled_warning_blocks_export(self):
        item = valid_item(script="腰腿疼痛可以准备桃树叶一大把、生姜五片，特别实用（需辨证为寒湿痹阻）")
        with self.assertRaisesRegex(ValueError, "未处置"):
            build_docx.validate_handoff(valid_handoff([item]))
        item["warning_decisions"] = {"degree-word": {"status": "false_positive", "reason": "原文即为特别实用，未升级"}}
        build_docx.validate_handoff(valid_handoff([item]))

    def test_unknown_public_keys_and_locks_are_rejected(self):
        public = {"filename": "test", "items": [valid_item()["public"]]}
        public["items"][0]["locks"] = {}
        with self.assertRaises(ValueError):
            build_docx.validate_public_input(public)

    def test_title_decision_is_enforced(self):
        data = valid_handoff()
        data["items"][0]["public"]["title"] = "改过的标题"
        with self.assertRaisesRegex(ValueError, "unchanged"):
            build_docx.validate_handoff(data)
        data["items"][0]["title_decision"] = {"type": "safety_adjusted", "rationale": "去掉危险医学确定性，保留数字悬念"}
        build_docx.validate_handoff(data)

    def test_filename_boundaries(self):
        for filename in ("../x", "folder\\x", "C:/x", "CON"):
            with self.subTest(filename=filename):
                with self.assertRaises(ValueError):
                    build_docx.safe_filename(filename)

    def test_existing_output_is_not_overwritten(self):
        data = valid_handoff(filename="existing")
        with tempfile.TemporaryDirectory() as output_dir:
            existing = Path(output_dir) / "existing.docx"
            existing.write_bytes(b"keep")
            with self.assertRaises(FileExistsError):
                build_docx.build(data, output_dir)
            self.assertEqual(b"keep", existing.read_bytes())

    def test_docx_layout_single_and_multi(self):
        with tempfile.TemporaryDirectory() as output_dir:
            single_path, _, _ = build_docx.build(valid_handoff(filename="single"), output_dir)
            single = Document(single_path)
            self.assertFalse(any(p.text.startswith("第1条") for p in single.paragraphs))
            title = next(p for p in single.paragraphs if p.text.startswith("标题："))
            self.assertTrue(all(run.bold for run in title.runs))
            body = next(p for p in single.paragraphs if "桃树叶一大把" in p.text)
            self.assertEqual("宋体", body.runs[0]._element.rPr.rFonts.get(qn("w:eastAsia")))

            multi_path, _, _ = build_docx.build(valid_handoff([valid_item(), valid_item()], filename="multi"), output_dir)
            multi = Document(multi_path)
            self.assertIn("第1条", [p.text for p in multi.paragraphs])
            self.assertIn("第2条", [p.text for p in multi.paragraphs])
            self.assertTrue(any(p._p.xpath("./w:pPr/w:pBdr/w:bottom") for p in multi.paragraphs))


class BuildDocxCliE2ETests(unittest.TestCase):
    script = str(SCRIPTS / "build_docx.py")

    def run_cli(self, handoff, handoff_dir, output_dir):
        handoff_path = Path(handoff_dir) / "handoff.json"
        handoff_path.write_text(json.dumps(handoff, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [sys.executable, self.script, str(handoff_path), str(output_dir)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_json_file_to_docx_cli_round_trip(self):
        data = valid_handoff(filename="cli-round-trip")
        with tempfile.TemporaryDirectory() as handoff_dir, tempfile.TemporaryDirectory() as output_dir:
            result = self.run_cli(data, handoff_dir, output_dir)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            output_path = Path(output_dir) / "cli-round-trip.docx"
            self.assertTrue(output_path.is_file())
            text = "\n".join(paragraph.text for paragraph in Document(output_path).paragraphs)
            self.assertIn(data["items"][0]["public"]["script"], text)
            self.assertNotIn("manual_checks", text)
            self.assertNotIn("locks", text)

    def test_invalid_item_keeps_batch_output_atomic(self):
        data = valid_handoff([valid_item(), valid_item(script="")], filename="invalid-batch")
        with tempfile.TemporaryDirectory() as handoff_dir, tempfile.TemporaryDirectory() as output_dir:
            result = self.run_cli(data, handoff_dir, output_dir)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("导出失败", result.stderr)
            self.assertEqual([], list(Path(output_dir).iterdir()))

    def test_editorial_tone_and_invalid_syndrome_keep_output_atomic(self):
        cases = (
            valid_item(script="腰腿疼痛关键是先看自己到底适不适合，可以准备桃树叶一大把、生姜五片（需辨证为寒湿痹阻）。"),
            valid_item(script="腰腿疼痛可以准备桃树叶一大把、生姜五片（需辨证为寒湿痹阻）（需辨证为寒湿痹阻）。"),
        )
        for index, invalid_item in enumerate(cases):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as handoff_dir, tempfile.TemporaryDirectory() as output_dir:
                data = valid_handoff([valid_item(), invalid_item], filename="invalid-semantic-batch")
                result = self.run_cli(data, handoff_dir, output_dir)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("导出失败", result.stderr)
                self.assertEqual([], list(Path(output_dir).iterdir()))


class FixtureContractTests(unittest.TestCase):
    fixtures_dir = ROOT / "tests" / "fixtures"

    def test_fixture_contracts_are_complete_and_consistent(self):
        case_paths = sorted(self.fixtures_dir.glob("*/case.json"))
        self.assertGreaterEqual(len(case_paths), 3)
        required_keys = {"id", "source", "locks", "machine_assertions", "manual_dimensions"}
        for path in case_paths:
            with self.subTest(path=path):
                case = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(required_keys, set(case))
                self.assertEqual(path.parent.name, case["id"])
                self.assertEqual({"link", "title", "text"}, set(case["source"]))
                self.assertEqual(build_docx.LOCK_KEYS, set(case["locks"]))
                for key in build_docx.LOCK_KEYS:
                    build_docx._validate_lock_list(case["locks"][key], "locks." + key)
                assertions = case["machine_assertions"]
                self.assertEqual(
                    {"required_literals", "forbidden_literals", "max_chars", "title_decision"},
                    set(assertions),
                )
                self.assertEqual(300, assertions["max_chars"])
                self.assertIn(assertions["title_decision"], {"unchanged", "safety_adjusted"})
                for key in ("required_literals", "forbidden_literals"):
                    self.assertTrue(all(isinstance(value, str) and value for value in assertions[key]))
                self.assertTrue(all(isinstance(value, str) and value for value in case["manual_dimensions"]))
                self.assertTrue((path.parent / "input.txt").is_file())
                self.assertTrue((path.parent / "expected_checks.md").is_file())
                self.assertEqual(case["source"]["text"].strip(), (path.parent / "input.txt").read_text(encoding="utf-8").strip())

    def test_blurred_vision_fixture_freezes_real_failure_mode(self):
        path = self.fixtures_dir / "03-blurred-vision" / "case.json"
        case = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("眼睛模糊看不清，教你一个土方法", case["source"]["title"])
        self.assertEqual(["肝火上炎"], validate_output.lock_texts(case["locks"]["syndromes"]))
        self.assertEqual(["青葙子10到15克"], validate_output.lock_texts(case["locks"]["formula_items"]))
        assertions = case["machine_assertions"]
        self.assertIn("（需辨证为肝火上炎）", assertions["required_literals"])
        for text in ("关键是先看自己到底适不适合", "视物模糊不一定都是这个原因", "在辨证合适的前提下"):
            self.assertIn(text, assertions["forbidden_literals"])
            self.assertIn("editorial-tone", {x["id"] for x in validate_output.validate_text(text)["errors"]})


if __name__ == "__main__":
    unittest.main()

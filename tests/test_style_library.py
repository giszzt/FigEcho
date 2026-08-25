from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


style_library = load_module(
    "style_library", ROOT / "scripts" / "style_library.py"
)
job_tools = load_module(
    "style_library_job_fixtures", ROOT / "tests" / "test_job_tools.py"
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def make_job(root: Path) -> Path:
    job = root / "job"
    job.mkdir()
    reference = job / "reference.png"
    reference.write_bytes(b"\x89PNG\r\n\x1a\nfixture-reference")
    style = job_tools.valid_style()
    style["references"] = [
        {"path": "reference.png", "role": "style_reference", "notes": ""}
    ]
    write_json(job / "style-spec.json", style)
    (job / "style-prompt.md").write_text(
        job_tools.portable_prompt(style), encoding="utf-8"
    )
    return job


def add_args(library: Path, job: Path, slug: str = "pastel-research-grid"):
    return SimpleNamespace(
        library=library,
        job_dir=job,
        name="马卡龙科研网格",
        slug=slug,
        description="三级容器、低饱和语义色和直角技术流程",
        tag=["pastel", "nested-panels"],
        best_for=["高密度科研方法框架"],
        not_for=["照片叙事"],
        reference=[],
    )


def passing_review() -> dict:
    return {
        "schema_version": "1.0.0",
        "generated_image": "output/final.png",
        "review_basis": "visible-generated-image",
        "anchor_scores": [
            {
                "anchor_id": f"anchor-{index}",
                "score": 4,
                "visible_evidence": f"visible anchor {index}",
                "mismatch": "",
                "next_action": "none",
            }
            for index in range(1, 6)
        ],
        "weighted_score": 100,
        "dimension_passes": [
            "layout",
            "components",
            "connectors",
            "typography",
            "iconography",
        ],
        "verdict": "pass",
    }


def passing_portability_review() -> dict:
    return {
        "schema_version": "1.0.0",
        "distinct_topic": True,
        "content_summary": "An unrelated supply-chain workflow with different entities.",
        "checks": {
            "topology_replanned": True,
            "icon_subjects_derived_from_new_content": True,
            "color_roles_reassigned": True,
            "no_source_content_carryover": True,
        },
        "style_anchor_score": 88,
        "visible_evidence": "The container, line, type and surface grammar remain visible while the topology and subjects change.",
    }


class StyleLibraryTests(unittest.TestCase):
    def test_add_preserves_original_reference_without_absolute_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = make_job(root)
            library = root / "library"
            result = style_library.add_pack(add_args(library, job))
            self.assertTrue(result["ok"], result)
            pack_dir = library / "templates" / "pastel-research-grid"
            pack = json.loads((pack_dir / "style-pack.json").read_text(encoding="utf-8"))
            copied = pack_dir / pack["references"][0]["path"]
            self.assertTrue(copied.is_file())
            self.assertEqual(copied.read_bytes(), (job / "reference.png").read_bytes())
            self.assertEqual(pack["reference_policy"], "original-reference-images")
            self.assertEqual(pack["rights_scope"], "personal-local")
            self.assertEqual(pack["portability_status"], "untested")
            self.assertNotIn(str((job / "reference.png").resolve()), json.dumps(pack))
            packed_spec = json.loads(
                (pack_dir / "style-spec.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                packed_spec["references"][0]["path"],
                pack["references"][0]["path"],
            )
            audit = style_library.validate_library(library)
            self.assertTrue(audit["ok"], audit)

    def test_duplicate_visual_fingerprint_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = make_job(root)
            library = root / "library"
            style_library.add_pack(add_args(library, job))
            with self.assertRaisesRegex(ValueError, "duplicate visual fingerprint"):
                style_library.add_pack(add_args(library, job, "same-style-copy"))

    def test_add_rejects_style_spec_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = make_job(root)
            style = json.loads((job / "style-spec.json").read_text(encoding="utf-8"))
            style["anti_generic"] = ["TODO-replace-with-observable-rule"]
            write_json(job / "style-spec.json", style)
            with self.assertRaisesRegex(ValueError, "style spec still contains"):
                style_library.add_pack(add_args(root / "library", job))

    def test_search_uses_name_tags_and_best_for(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = make_job(root)
            library = root / "library"
            style_library.add_pack(add_args(library, job))
            args = SimpleNamespace(
                library=library,
                query="高密度 科研",
                limit=10,
                include_archived=False,
            )
            result = style_library.search_catalog(args)
            self.assertEqual(result["results"][0]["slug"], "pastel-research-grid")

    def test_search_matches_partial_chinese_name(self) -> None:
        """用户口头叫法很少和 name 逐字相同，中文没有空格分词，纯子串匹配会漏掉。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = make_job(root)
            library = root / "library"
            style_library.add_pack(add_args(library, job))
            for query in ["马卡龙网格", "科研网格图", "马卡龙"]:
                args = SimpleNamespace(
                    library=library,
                    query=query,
                    limit=10,
                    include_archived=False,
                )
                result = style_library.search_catalog(args)
                self.assertTrue(result["results"], f"no match for {query}")
                self.assertEqual(result["results"][0]["slug"], "pastel-research-grid")

    def test_search_matches_registered_alias(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = make_job(root)
            library = root / "library"
            args = add_args(library, job)
            args.alias = ["奶油色方法图"]
            style_library.add_pack(args)
            result = style_library.search_catalog(
                SimpleNamespace(
                    library=library,
                    query="奶油色方法图",
                    limit=10,
                    include_archived=False,
                )
            )
            self.assertEqual(result["results"][0]["slug"], "pastel-research-grid")

    def test_rename_updates_slug_name_and_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = make_job(root)
            library = root / "library"
            style_library.add_pack(add_args(library, job))
            style_library.rename_pack(
                SimpleNamespace(
                    library=library,
                    slug="pastel-research-grid",
                    name="淡彩科研网格图",
                    new_slug="pastel-research-grid-v2",
                    alias=[],
                    add_alias=["马卡龙网格图"],
                )
            )
            catalog = json.loads((library / "catalog.json").read_text(encoding="utf-8"))
            slugs = [entry["slug"] for entry in catalog["templates"]]
            self.assertEqual(slugs, ["pastel-research-grid-v2"])
            self.assertTrue((library / "templates" / "pastel-research-grid-v2").is_dir())
            self.assertFalse((library / "templates" / "pastel-research-grid").exists())
            self.assertEqual(catalog["templates"][0]["name"], "淡彩科研网格图")
            self.assertIn("马卡龙网格图", catalog["templates"][0]["aliases"])

    def test_promote_requires_review_and_marks_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = make_job(root)
            library = root / "library"
            style_library.add_pack(add_args(library, job))
            review = root / "style-review.json"
            write_json(review, passing_review())
            preview = root / "preview.png"
            preview.write_bytes(b"\x89PNG\r\n\x1a\npreview")
            result = style_library.promote_pack(
                SimpleNamespace(
                    library=library,
                    slug="pastel-research-grid",
                    review=review,
                    preview=preview,
                )
            )
            self.assertEqual(result["status"], "validated")
            audit = style_library.validate_library(library)
            self.assertTrue(audit["ok"], audit)
            self.assertTrue(
                any("distinct-topic portability" in item for item in audit["warnings"]),
                audit,
            )

    def test_certify_requires_distinct_topic_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = make_job(root)
            library = root / "library"
            style_library.add_pack(add_args(library, job))
            review = root / "portability-review.json"
            write_json(review, passing_portability_review())
            result = style_library.certify_portability(
                SimpleNamespace(
                    library=library,
                    slug="pastel-research-grid",
                    review=review,
                )
            )
            self.assertEqual(result["portability_status"], "passed")
            audit = style_library.validate_library(library)
            self.assertTrue(audit["ok"], audit)
            self.assertFalse(
                any("distinct-topic portability" in item for item in audit["warnings"]),
                audit,
            )

    def test_tampered_reference_fails_integrity_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = make_job(root)
            library = root / "library"
            style_library.add_pack(add_args(library, job))
            target = (
                library
                / "templates"
                / "pastel-research-grid"
                / "references"
                / "reference-01.png"
            )
            target.write_bytes(b"tampered")
            audit = style_library.validate_library(library)
            self.assertFalse(audit["ok"])
            self.assertTrue(
                any("reference hash mismatch" in item for item in audit["failures"])
            )

    def test_prompt_hash_is_stable_across_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = make_job(root)
            library = root / "library"
            style_library.add_pack(add_args(library, job))
            prompt = (
                library
                / "templates"
                / "pastel-research-grid"
                / "style-prompt.md"
            )
            text = prompt.read_text(encoding="utf-8")
            prompt.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
            audit = style_library.validate_library(library)
            self.assertTrue(audit["ok"], audit)

    def test_archive_hides_template_from_default_search(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = make_job(root)
            library = root / "library"
            style_library.add_pack(add_args(library, job))
            style_library.archive_pack(
                SimpleNamespace(library=library, slug="pastel-research-grid")
            )
            result = style_library.search_catalog(
                SimpleNamespace(
                    library=library,
                    query="pastel",
                    limit=10,
                    include_archived=False,
                )
            )
            self.assertEqual(result["count"], 0)


if __name__ == "__main__":
    unittest.main()

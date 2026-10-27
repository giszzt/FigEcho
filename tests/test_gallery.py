from __future__ import annotations

import base64
import importlib.util
import json
import re
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


gallery = load_module("figecho_gallery", ROOT / "scripts" / "gallery.py")
style_library = load_module("figecho_style_library", ROOT / "scripts" / "style_library.py")
library_fixtures = load_module("figecho_library_fixtures", ROOT / "tests" / "test_style_library.py")


# A real 64x48 PNG keeps the fixture an actual image so thumbnail behaviour is exercised.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAAAwCAIAAAAuKetIAAAAaElEQVR4nNXOMREAIBDAsFL/KpkZ"
    "kICIH7hGQdY9mzKJkziJkziJkziJkziJkziJkziJkziJkziJkziJkziJkziJkziJkziJkziJkziJ"
    "kziJkziJkziJkziJkziJkziJkziJkzh/B6YeKZgDHj/XPUYAAAAASUVORK5CYII="
)


def build_library(root: Path, slug: str = "pastel-research-grid", real_images: bool = True) -> Path:
    library = root / "library"
    job = library_fixtures.make_job(root)
    if real_images:
        (job / "reference.png").write_bytes(TINY_PNG)
    style_library.add_pack(library_fixtures.add_args(library, job, slug=slug))
    return library


def embedded_payload(html: str) -> dict:
    match = re.search(
        r'<script id="figecho-data" type="application/json">(.*?)</script>', html, re.S
    )
    assert match, "gallery page must embed its data"
    return json.loads(match.group(1).replace("<\\/", "</"))


class GalleryBuildTests(unittest.TestCase):
    def test_page_embeds_every_catalog_entry_with_choosing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_library(root)
            result = gallery.build_gallery(library)
            self.assertTrue(result["ok"])
            page = Path(result["path"])
            self.assertTrue(page.is_file())
            payload = embedded_payload(page.read_text(encoding="utf-8"))
            self.assertEqual(payload["style_count"] if "style_count" in payload else len(payload["styles"]), 1)
            style = payload["styles"][0]
            self.assertEqual(style["slug"], "pastel-research-grid")
            # Choosing a style depends on the exclusion boundary and the palette, not just a thumbnail.
            self.assertTrue(style["best_for"])
            self.assertTrue(style["not_for"])
            self.assertTrue(style["palette"])
            self.assertTrue(style["anchors"])
            self.assertIn("【配色】", style["prompt"])
            self.assertEqual(payload["families"][0]["recommended_slug"], "pastel-research-grid")

    def test_facet_vocabulary_comes_from_the_cli_not_a_hardcoded_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_library(root)
            result = gallery.build_gallery(library)
            payload = embedded_payload(Path(result["path"]).read_text(encoding="utf-8"))
            for key, vocabulary in style_library.FACETS.items():
                self.assertEqual(payload["facet_vocabulary"][key]["values"], vocabulary)

    def test_missing_images_are_reported_rather_than_silently_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_library(root)
            reference = library / "templates" / "pastel-research-grid" / "references"
            for item in reference.iterdir():
                item.unlink()
            result = gallery.build_gallery(library)
            self.assertTrue(result["ok"])
            self.assertTrue(any("reference missing" in text for text in result["problems"]))
            self.assertTrue(any("no displayable image" in text for text in result["problems"]))

    def test_status_reports_staleness_after_the_catalog_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_library(root)
            gallery.build_gallery(library)
            fresh = gallery.gallery_status(library)
            self.assertTrue(fresh["built"])
            self.assertFalse(fresh["stale"])
            catalog_path = library / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["updated_at"] = "2026-01-01"
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
            self.assertTrue(gallery.gallery_status(library)["stale"])

    def test_unbuilt_library_reports_stale_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_library(root)
            status = gallery.gallery_status(library)
            self.assertFalse(status["built"])
            self.assertTrue(status["stale"])

    def test_thumbnail_cache_is_reused_and_pruned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_library(root)
            first = gallery.build_gallery(library)
            second = gallery.build_gallery(library)
            if first["thumbnails"]["enabled"]:
                self.assertGreaterEqual(second["thumbnails"]["reused"], 1)
                self.assertEqual(second["thumbnails"]["written"], 0)
            stale_dir = library / gallery.CACHE_DIR / "gone-slug"
            stale_dir.mkdir(parents=True, exist_ok=True)
            (stale_dir / "preview-thumb.webp").write_bytes(b"stale")
            gallery.build_gallery(library)
            self.assertFalse(stale_dir.exists())

    def test_excluded_slugs_leave_the_page(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_library(root)
            result = gallery.build_gallery(library, exclude=["pastel-research-grid"])
            self.assertEqual(result["style_count"], 0)
            payload = embedded_payload(Path(result["path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["styles"], [])


    def test_unreadable_image_costs_one_thumbnail_not_the_page(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_library(root, real_images=False)
            result = gallery.build_gallery(library)
            self.assertTrue(result["ok"])
            payload = embedded_payload(Path(result["path"]).read_text(encoding="utf-8"))
            record = payload["styles"][0]["images"]["references"][0]
            self.assertEqual(record["thumb"], record["full"])
            if result["thumbnails"]["enabled"]:
                self.assertTrue(any("not downscaled" in text for text in result["problems"]))


class GalleryIntegrationTests(unittest.TestCase):
    def test_library_writes_rebuild_the_page(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_library(root)
            status = style_library.rebuild_gallery(library)
            self.assertTrue(status["ok"], status)
            self.assertTrue(Path(status["path"]).is_file())
            self.assertIn("add", style_library.MUTATING_COMMANDS)
            for command in ("promote", "certify", "classify", "rename", "archive", "refresh"):
                self.assertIn(command, style_library.MUTATING_COMMANDS)
            for command in ("search", "list", "show", "validate", "taxonomy"):
                self.assertNotIn(command, style_library.MUTATING_COMMANDS)

    def test_rebuild_can_be_switched_off(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_library(root)
            import os

            os.environ["FIGECHO_GALLERY_AUTOBUILD"] = "0"
            try:
                status = style_library.rebuild_gallery(library)
            finally:
                os.environ.pop("FIGECHO_GALLERY_AUTOBUILD", None)
            self.assertTrue(status["ok"])
            self.assertIn("skipped", status)
            self.assertFalse((library / gallery.GALLERY_NAME).exists())

    def test_validate_warns_when_the_page_lags_behind(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_library(root)
            report = style_library.validate_library(library.resolve())
            self.assertTrue(any("gallery is out of date" in text for text in report["warnings"]))
            self.assertTrue(report["gallery"]["stale"])
            gallery.build_gallery(library)
            report = style_library.validate_library(library.resolve())
            self.assertFalse(any("gallery is out of date" in text for text in report["warnings"]))

    def test_gallery_command_is_read_only_on_the_library(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_library(root)
            before = (library / "catalog.json").read_bytes()
            args = SimpleNamespace(
                library=library, out=None, no_thumbnails=True, exclude=[], open=False, status=False
            )
            result = style_library.gallery_command(args)
            self.assertTrue(result["ok"])
            self.assertEqual((library / "catalog.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

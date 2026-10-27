#!/usr/bin/env python3
"""Build a browsable local gallery page from the FigEcho Style Library."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_LIBRARY = PACKAGE_ROOT / "style-library"
GALLERY_NAME = "gallery.html"
MANIFEST_NAME = ".gallery-cache/manifest.json"
CACHE_DIR = ".gallery-cache"
HEX_COLOR_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")
THUMB_EDGE = 900
VIEW_EDGE = 2000

FALLBACK_FACETS = {
    "use_cases": {"research-proposal": "科研申报", "paper": "论文", "technical-report": "技术汇报", "education": "科普"},
    "archetypes": {"roadmap": "阶段路线", "architecture": "分层架构", "pipeline": "流程", "feedback": "反馈循环", "comparison": "对比", "mechanism": "机制"},
    "expressions": {"text-framework": "文字框架", "illustrated-mechanism": "图示机制", "evidence-images": "证据图片", "mixed": "混合表达"},
}
FACET_TITLES = {"use_cases": "用途", "archetypes": "关系图型", "expressions": "表达方式"}
DIMENSION_LABELS = {
    "layout": "版式",
    "components": "组件",
    "connectors": "连接线",
    "palette": "配色",
    "color": "配色",
    "typography": "字体",
    "iconography": "图标",
    "surface": "表面质感",
    "density": "密度",
    "texture": "肌理",
}


def facets_vocabulary() -> dict[str, dict[str, str]]:
    """Share the CLI vocabulary when importable so labels never drift."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import style_library  # noqa: PLC0415

        return style_library.FACETS
    except Exception:
        return FALLBACK_FACETS


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def organization_of(entry: dict[str, Any], facets: dict[str, dict[str, str]]) -> dict[str, Any]:
    value = entry.get("organization")
    if isinstance(value, dict) and value.get("family_id"):
        return value
    return {
        "family_id": entry.get("slug", ""),
        "family_name": entry.get("name", ""),
        "variant_id": "default",
        "variant_name": "默认版",
        "facets": {key: [] for key in facets},
    }


def palette_colors(spec: dict[str, Any]) -> list[str]:
    visual = spec.get("visual_system") or {}
    sources = [visual.get("palette"), visual.get("color"), spec.get("signature_anchors")]
    found: list[str] = []
    for source in sources:
        if not source:
            continue
        for match in HEX_COLOR_RE.findall(json.dumps(source, ensure_ascii=False)):
            token = "#" + match[1:].upper()
            if token not in found:
                found.append(token)
        if len(found) >= 6:
            break
    return found[:14]


def anchor_records(spec: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for item in spec.get("signature_anchors", []):
        if not isinstance(item, dict):
            continue
        dimension = str(item.get("dimension", ""))
        records.append(
            {
                "id": item.get("id", ""),
                "dimension": dimension,
                "dimension_label": DIMENSION_LABELS.get(dimension, dimension),
                "rule": item.get("rule", ""),
                "weight": item.get("weight"),
                "confidence": item.get("confidence", ""),
            }
        )
    return records


class ThumbnailMaker:
    """Downscale library images once and reuse them until the source changes."""

    def __init__(self, root: Path, enabled: bool) -> None:
        self.root = root
        self.cache_root = root / CACHE_DIR
        self.index_path = self.cache_root / "images.json"
        self.index: dict[str, Any] = {}
        self.reused = 0
        self.written = 0
        self.enabled = enabled
        self.reason = ""
        self.image_module = None
        if enabled:
            try:
                from PIL import Image  # noqa: PLC0415

                self.image_module = Image
            except Exception as exc:
                self.enabled = False
                self.reason = f"Pillow unavailable: {exc}"
        if self.index_path.exists():
            try:
                self.index = load_json(self.index_path)
            except Exception:
                self.index = {}

    def derive(self, source: Path, slug: str, stem: str) -> dict[str, Any]:
        relative_source = source.relative_to(self.root).as_posix()
        record: dict[str, Any] = {"full": relative_source}
        try:
            size = source.stat().st_size
        except OSError:
            return record
        record["bytes"] = size
        if not self.enabled or self.image_module is None:
            record["thumb"] = relative_source
            record["view"] = relative_source
            return record

        digest = sha256_file(source)
        cached = self.index.get(relative_source)
        targets = {
            "thumb": self.cache_root / slug / f"{stem}-thumb.webp",
            "view": self.cache_root / slug / f"{stem}-view.webp",
        }
        if (
            isinstance(cached, dict)
            and cached.get("sha256") == digest
            and all(Path(self.root / cached.get(key, "")).is_file() for key in targets)
        ):
            self.reused += 1
            record.update({key: cached[key] for key in targets})
            record["width"] = cached.get("width")
            record["height"] = cached.get("height")
            return record

        try:
            with self.image_module.open(source) as image:
                image = image.convert("RGB") if image.mode in {"P", "CMYK"} else image
                width, height = image.size
                for key, target in targets.items():
                    edge = THUMB_EDGE if key == "thumb" else VIEW_EDGE
                    target.parent.mkdir(parents=True, exist_ok=True)
                    copy = image.copy()
                    copy.thumbnail((edge, edge), self.image_module.LANCZOS)
                    if copy.mode not in {"RGB", "RGBA"}:
                        copy = copy.convert("RGB")
                    copy.save(target, "WEBP", quality=82, method=4)
        except Exception as exc:
            # An unreadable image must cost one card's thumbnail, not the whole page.
            record["thumb"] = relative_source
            record["view"] = relative_source
            record["error"] = str(exc)
            return record
        self.written += 1
        record.update({key: targets[key].relative_to(self.root).as_posix() for key in targets})
        record["width"] = width
        record["height"] = height
        self.index[relative_source] = {
            "sha256": digest,
            "width": width,
            "height": height,
            **{key: record[key] for key in targets},
        }
        return record

    def prune(self, live_slugs: set[str]) -> None:
        """Renamed or archived-away packs must not leave stale thumbnails behind."""
        if not self.cache_root.is_dir():
            return
        for child in self.cache_root.iterdir():
            if child.is_dir() and child.name not in live_slugs:
                shutil.rmtree(child, ignore_errors=True)
        self.index = {
            key: value
            for key, value in self.index.items()
            if Path(key).parts[1:2] and Path(key).parts[1] in live_slugs
        }

    def flush(self) -> None:
        if not self.enabled:
            return
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(self.index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def collect_styles(
    root: Path,
    catalog: dict[str, Any],
    facets: dict[str, dict[str, str]],
    thumbs: ThumbnailMaker,
    excluded: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    styles: list[dict[str, Any]] = []
    problems: list[str] = []
    for entry in catalog.get("templates", []):
        if not isinstance(entry, dict) or not entry.get("slug"):
            continue
        slug = str(entry["slug"])
        if slug in excluded:
            continue
        pack_dir = root / "templates" / slug
        try:
            pack = load_json(pack_dir / "style-pack.json")
        except Exception as exc:
            problems.append(f"{slug}: style-pack.json unreadable ({exc})")
            continue
        spec: dict[str, Any] = {}
        spec_name = str(pack.get("style_spec", "style-spec.json"))
        try:
            spec = load_json(pack_dir / spec_name)
        except Exception as exc:
            problems.append(f"{slug}: style spec unreadable ({exc})")
        prompt_text = ""
        prompt_name = str(pack.get("style_prompt", "style-prompt.md"))
        prompt_path = pack_dir / prompt_name
        if prompt_path.is_file():
            prompt_text = prompt_path.read_text(encoding="utf-8")
        else:
            problems.append(f"{slug}: style prompt missing")

        org = organization_of(pack if pack.get("organization") else entry, facets)
        facet_values = {key: list(org.get("facets", {}).get(key, [])) for key in facets}
        images: dict[str, Any] = {"preview": None, "references": []}
        validation = pack.get("validation") or {}
        preview_name = str(validation.get("preview") or "preview.png")
        preview_path = pack_dir / preview_name
        if preview_path.is_file():
            images["preview"] = thumbs.derive(preview_path, slug, "preview")
            if images["preview"].get("error"):
                problems.append(f"{slug}: preview not downscaled ({images['preview']['error']})")
        for index, item in enumerate(pack.get("references", []), start=1):
            if not isinstance(item, dict) or not item.get("path"):
                continue
            reference_path = pack_dir / str(item["path"])
            if not reference_path.is_file():
                problems.append(f"{slug}: reference missing {item['path']}")
                continue
            record = thumbs.derive(reference_path, slug, f"ref-{index:02d}")
            if record.get("error"):
                problems.append(f"{slug}: reference not downscaled ({record['error']})")
            record["original_name"] = item.get("original_name", "")
            images["references"].append(record)
        if not images["preview"] and not images["references"]:
            problems.append(f"{slug}: no displayable image")

        styles.append(
            {
                "slug": slug,
                "name": pack.get("name") or entry.get("name") or slug,
                "aliases": pack.get("aliases", entry.get("aliases", [])),
                "tags": pack.get("tags", entry.get("tags", [])),
                "best_for": pack.get("best_for", entry.get("best_for", [])),
                "not_for": pack.get("not_for", entry.get("not_for", [])),
                "description": pack.get("description", ""),
                "summary": spec.get("style_summary", ""),
                "status": pack.get("status", entry.get("status", "candidate")),
                "portability_status": pack.get(
                    "portability_status", entry.get("portability_status", "untested")
                ),
                "updated_at": pack.get("updated_at", entry.get("updated_at", "")),
                "rights_scope": pack.get("rights_scope", ""),
                "family_id": org["family_id"],
                "family_name": org["family_name"],
                "variant_id": org.get("variant_id", "default"),
                "variant_name": org.get("variant_name", "默认版"),
                "facets": facet_values,
                "palette": palette_colors(spec),
                "anchors": anchor_records(spec),
                "weighted_score": validation.get("weighted_score"),
                "prompt": prompt_text,
                "prompt_file": f"templates/{slug}/{prompt_name}",
                "images": images,
            }
        )
    return styles, problems


def family_order_key(style: dict[str, Any]) -> tuple[int, int, str]:
    return (
        0 if style["portability_status"] == "passed" else 1,
        0 if style["status"] == "validated" else 1,
        style["slug"],
    )


def build_families(styles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    families: dict[str, dict[str, Any]] = {}
    for style in sorted(styles, key=family_order_key):
        family = families.setdefault(
            style["family_id"],
            {
                "family_id": style["family_id"],
                "family_name": style["family_name"],
                "recommended_slug": style["slug"],
                "variants": [],
            },
        )
        family["variants"].append(style["slug"])
    return sorted(families.values(), key=lambda item: item["family_name"])


def render_html(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return HTML_TEMPLATE.replace("/*__FIGECHO_DATA__*/", data.replace("</", "<\\/"))


def build_gallery(
    root: Path,
    out: Path | None = None,
    thumbs: bool = True,
    exclude: list[str] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    catalog_path = root / "catalog.json"
    if not catalog_path.is_file():
        raise FileNotFoundError(f"catalog not found: {catalog_path}")
    catalog = load_json(catalog_path)
    facets = facets_vocabulary()
    maker = ThumbnailMaker(root, thumbs)
    styles, problems = collect_styles(root, catalog, facets, maker, set(exclude or []))
    maker.prune({style["slug"] for style in styles})
    maker.flush()
    families = build_families(styles)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = {
        "generated_at": generated_at,
        "library_name": root.name,
        "catalog_updated_at": catalog.get("updated_at", ""),
        "catalog_sha256": sha256_file(catalog_path),
        "facet_vocabulary": {
            key: {"title": FACET_TITLES.get(key, key), "values": facets[key]} for key in facets
        },
        "families": families,
        "styles": styles,
        "problems": problems,
    }
    target = (out or (root / GALLERY_NAME)).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html(payload), encoding="utf-8")
    manifest = {
        "generated_at": generated_at,
        "gallery": target.name if target.parent == root else str(target),
        "catalog_sha256": payload["catalog_sha256"],
        "style_count": len(styles),
        "family_count": len(families),
        "excluded": sorted(exclude or []),
    }
    manifest_path = root / MANIFEST_NAME
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "ok": True,
        "action": "gallery",
        "path": str(target),
        "style_count": len(styles),
        "family_count": len(families),
        "thumbnails": {
            "enabled": maker.enabled,
            "written": maker.written,
            "reused": maker.reused,
            **({"reason": maker.reason} if maker.reason else {}),
        },
        "problems": problems,
    }


def gallery_status(root: Path) -> dict[str, Any]:
    """Report whether the built page still matches the catalog on disk."""
    root = root.resolve()
    gallery_path = root / GALLERY_NAME
    manifest_path = root / MANIFEST_NAME
    catalog_path = root / "catalog.json"
    if not gallery_path.is_file() or not manifest_path.is_file():
        return {"built": False, "stale": True, "reason": "gallery has not been built"}
    try:
        manifest = load_json(manifest_path)
    except Exception as exc:
        return {"built": True, "stale": True, "reason": f"manifest unreadable ({exc})"}
    current = sha256_file(catalog_path) if catalog_path.is_file() else ""
    stale = manifest.get("catalog_sha256") != current
    return {
        "built": True,
        "stale": stale,
        "generated_at": manifest.get("generated_at", ""),
        "path": str(gallery_path),
        **({"reason": "catalog changed since the page was built"} if stale else {}),
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FigEcho 风格库</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #F3F2EE;
  --bg-veil: rgba(243, 242, 238, .86);
  --card: #FFFFFF;
  --ink: #17171A;
  --ink-2: #4A4B50;
  --muted: #8B8C91;
  --line: #DFDDD7;
  --line-soft: #E9E7E2;
  --chip: #E8E6E0;
  --accent: #D9480F;
  --accent-soft: rgba(217, 72, 15, .1);
  --lift: 0 22px 50px -18px rgba(23, 23, 26, .28), 0 2px 6px rgba(23, 23, 26, .06);
  --serif: "Noto Serif SC", "Songti SC", "Source Han Serif SC", "Microsoft YaHei UI", serif;
  --sans: "PingFang SC", "Microsoft YaHei UI", "Microsoft YaHei", "Helvetica Neue", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Consolas, monospace;
  --ease: cubic-bezier(.2, .7, .2, 1);
  --gutter: clamp(16px, 4.2vw, 72px);
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #121214; --bg-veil: rgba(18, 18, 20, .86); --card: #1C1C1F;
    --ink: #EDECE8; --ink-2: #B9B8B3; --muted: #7E7E83; --line: #2C2C30; --line-soft: #232326;
    --chip: #232326; --accent: #FF8A4C; --accent-soft: rgba(255, 138, 76, .14);
    --lift: 0 24px 60px -20px rgba(0, 0, 0, .7), 0 2px 8px rgba(0, 0, 0, .4);
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #121214; --bg-veil: rgba(18, 18, 20, .86); --card: #1C1C1F;
  --ink: #EDECE8; --ink-2: #B9B8B3; --muted: #7E7E83; --line: #2C2C30; --line-soft: #232326;
  --chip: #232326; --accent: #FF8A4C; --accent-soft: rgba(255, 138, 76, .14);
  --lift: 0 24px 60px -20px rgba(0, 0, 0, .7), 0 2px 8px rgba(0, 0, 0, .4);
  color-scheme: dark;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg); color: var(--ink); font-family: var(--sans);
  font-size: 15px; line-height: 1.75; -webkit-font-smoothing: antialiased; overflow-x: hidden;
}
body.locked { overflow: hidden; }
button { font: inherit; color: inherit; }
::selection { background: var(--accent); color: #fff; }

/* ── 报头 ── */
.top {
  display: flex; justify-content: space-between; align-items: baseline; gap: 16px; flex-wrap: wrap;
  padding: 26px var(--gutter) 0; font-size: 13px; color: var(--muted);
}
.brand { color: var(--ink); letter-spacing: .02em; }
.brand b { font-family: var(--mono); font-weight: 500; letter-spacing: -.01em; }
.brand i { font-style: normal; color: var(--muted); margin: 0 .5em; }
.top .meta { font-family: var(--mono); font-size: 12px; letter-spacing: .02em; }
.intro {
  padding: clamp(40px, 7vh, 88px) var(--gutter) clamp(30px, 4.5vh, 48px);
  display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 26em); gap: 24px 64px; align-items: end;
}
.intro h1 {
  margin: 0; font-family: var(--serif); font-weight: 700; letter-spacing: .01em; text-wrap: balance;
  font-size: clamp(32px, 4.4vw, 60px); line-height: 1.14;
}
.intro h1 span { color: var(--accent); }
.intro p { margin: 0; color: var(--ink-2); font-size: 14.5px; line-height: 1.95; }
@media (max-width: 860px) { .intro { grid-template-columns: 1fr; } }

/* ── 工具条，滚动后吸顶 ── */
.bar-sentinel { height: 1px; }
.bar {
  position: sticky; top: 0; z-index: 20;
  display: flex; align-items: center; gap: 14px 28px; flex-wrap: wrap;
  padding: 14px var(--gutter);
  background: var(--bg-veil); backdrop-filter: blur(16px) saturate(1.2); -webkit-backdrop-filter: blur(16px) saturate(1.2);
  border-top: 1px solid var(--line); border-bottom: 1px solid transparent;
  transition: border-color .3s var(--ease);
}
.bar.stuck { border-bottom-color: var(--line); }
.find {
  position: relative; display: flex; align-items: center; gap: 10px;
  flex: 0 1 300px; min-width: 200px; height: 38px; padding: 0 12px;
  background: var(--card); border: 1px solid var(--line); border-radius: 10px;
  transition: border-color .25s var(--ease), box-shadow .25s var(--ease);
}
.find:focus-within { border-color: var(--ink); box-shadow: 0 0 0 4px var(--accent-soft); }
.find svg { flex: none; color: var(--muted); }
.find input {
  flex: 1; min-width: 0; border: 0; outline: 0; background: none; color: var(--ink);
  font: inherit; font-size: 14px;
}
.find input::placeholder { color: var(--muted); }
.find input::-webkit-search-cancel-button { display: none; }
.find kbd {
  font-family: var(--mono); font-size: 11px; color: var(--muted); border: 1px solid var(--line);
  border-radius: 5px; padding: 0 6px; line-height: 18px;
}
.groups { display: flex; flex-wrap: wrap; gap: 10px 26px; flex: 1 1 auto; }
.group { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.group > span { flex: none; white-space: nowrap; font-size: 12px; color: var(--muted); margin-right: 4px; letter-spacing: .06em; }
.chip {
  border: 0; cursor: pointer; border-radius: 999px; padding: 4px 11px 4px 12px;
  background: transparent; color: var(--ink-2); font-size: 13px; line-height: 1.5;
  display: inline-flex; align-items: baseline; gap: 5px;
  transition: background .2s var(--ease), color .2s var(--ease), opacity .2s var(--ease);
}
.chip sup { font-family: var(--mono); font-size: 10px; color: var(--muted); top: 0; }
.chip:hover { background: var(--chip); color: var(--ink); }
.chip[aria-pressed="true"] { background: var(--ink); color: var(--bg); }
.chip[aria-pressed="true"] sup { color: inherit; opacity: .6; }
.chip:disabled { opacity: .3; cursor: default; background: none; }
.tally { margin-left: auto; font-family: var(--mono); font-size: 12px; color: var(--muted); white-space: nowrap; }
.tally b { color: var(--ink); font-weight: 500; }
.clear {
  border: 0; background: none; cursor: pointer; color: var(--accent); font-size: 12.5px; padding: 0;
}
.clear[hidden] { display: none; }

/* ── 图墙，按图的宽高比排成等高行 ── */
.wall { position: relative; margin: 40px var(--gutter) 0; transition: height .6s var(--ease); }
.wall.still .tile, .wall.still .frame { transition: none !important; }
.tile {
  position: absolute; left: 0; top: 0; will-change: transform;
  transition: transform .7s var(--ease), width .7s var(--ease), opacity .45s var(--ease), visibility .45s;
}
.tile.gone { opacity: 0; visibility: hidden; pointer-events: none; }
.tile-hit {
  display: block; width: 100%; padding: 0; border: 0; background: none; cursor: zoom-in; text-align: left;
  animation: rise .9s var(--ease) both; animation-delay: calc(var(--i) * 70ms + 120ms);
}
.tile-hit:focus-visible { outline: none; }
.tile-hit:focus-visible .frame { box-shadow: 0 0 0 3px var(--accent); }
.frame {
  display: block; position: relative; overflow: hidden; border-radius: 6px; background: var(--card);
  box-shadow: 0 0 0 1px var(--line);
  transition: height .7s var(--ease), box-shadow .45s var(--ease), transform .45s var(--ease);
}
.frame img {
  display: block; width: 100%; height: 100%; object-fit: contain;
  transition: transform 1.2s var(--ease);
}
.cap {
  display: flex; align-items: baseline; gap: 10px; padding: 14px 2px 0; min-width: 0;
}
.cap .no { font-family: var(--mono); font-size: 11px; color: var(--muted); flex: none; }
.cap .nm {
  display: block; margin: 0; font-family: var(--serif); font-weight: 700; font-size: 16px; line-height: 1.35;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; transition: color .3s var(--ease);
}
.cap .kind {
  display: block; margin-top: 2px; font-size: 12px; color: var(--muted);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.tile.narrow .cap .nm { white-space: normal; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; font-size: 15px; }
.tile.narrow .cap .kind { display: none; }
.tile:hover .frame { box-shadow: 0 0 0 1px var(--line), var(--lift); transform: translateY(-4px); }
.tile:hover .frame img { transform: scale(1.025); }
.tile:hover .cap .nm { color: var(--accent); }
@keyframes rise { from { opacity: 0; transform: translateY(22px); } to { opacity: 1; transform: none; } }

/* 加入对比的小圆钮，悬停出现，选中后常驻 */
.pick {
  position: absolute; top: 10px; right: 10px; z-index: 2; width: 30px; height: 30px; border-radius: 50%;
  border: 0; cursor: pointer; display: grid; place-items: center;
  background: rgba(23, 23, 26, .72); color: #fff; backdrop-filter: blur(6px);
  opacity: 0; transform: scale(.8); transition: opacity .25s var(--ease), transform .25s var(--ease), background .2s;
}
.pick svg { transition: transform .3s var(--ease); }
.tile:hover .pick, .pick:focus-visible, .pick[aria-pressed="true"] { opacity: 1; transform: none; }
.pick[aria-pressed="true"] { background: var(--accent); }
.pick[aria-pressed="true"] svg { transform: rotate(45deg); }
.pick::after {
  content: attr(data-tip); position: absolute; right: 38px; top: 50%; transform: translateY(-50%);
  white-space: nowrap; font-size: 12px; padding: 3px 9px; border-radius: 6px;
  background: rgba(23, 23, 26, .82); color: #fff; opacity: 0; pointer-events: none; transition: opacity .2s;
}
.pick:hover::after { opacity: 1; }
@media (hover: none) { .pick { opacity: 1; transform: none; } }
@media (max-width: 720px) {
  .bar { gap: 10px; }
  .find { flex: 1 1 100%; }
  .groups { flex-wrap: nowrap; flex-direction: column; gap: 4px; width: 100%; }
  .group { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; margin: 0 calc(var(--gutter) * -1); padding: 0 var(--gutter); }
  .group::-webkit-scrollbar { display: none; }
  .chip { flex: none; }
  .tally { position: absolute; right: var(--gutter); top: 24px; }
  .find { margin-right: 44px; }
}

.empty { margin: 80px var(--gutter); font-size: 15px; color: var(--ink-2); }
.empty[hidden] { display: none; }
.empty button { border: 0; background: none; color: var(--accent); cursor: pointer; padding: 0; }

.colophon {
  margin: 120px var(--gutter) 0; padding: 22px 0 140px; border-top: 1px solid var(--line);
  display: flex; flex-wrap: wrap; gap: 8px 36px; font-size: 12px; color: var(--muted);
}
.colophon .snag { color: var(--accent); flex-basis: 100%; }

/* ── 对比托盘 ── */
.tray {
  position: fixed; left: 50%; bottom: 24px; z-index: 30;
  display: flex; align-items: center; gap: 14px; padding: 8px 8px 8px 16px;
  background: var(--ink); color: var(--bg); border-radius: 14px; box-shadow: var(--lift);
  transform: translate(-50%, 160%); transition: transform .55s var(--ease);
  max-width: calc(100vw - 32px);
}
.tray.on { transform: translate(-50%, 0); }
.tray .label { font-size: 12.5px; opacity: .7; white-space: nowrap; }
.tray .thumbs { display: flex; gap: 8px; }
.tray .thumb {
  position: relative; height: 40px; border-radius: 5px; overflow: hidden; background: #fff;
  border: 0; padding: 0; cursor: pointer; animation: pop .4s var(--ease);
}
.tray .thumb img { height: 100%; width: auto; display: block; }
.tray .thumb::after {
  content: "×"; position: absolute; inset: 0; display: grid; place-items: center;
  background: rgba(23, 23, 26, .7); color: #fff; font-size: 18px; opacity: 0; transition: opacity .2s;
}
.tray .thumb:hover::after { opacity: 1; }
.tray .slot { width: 40px; height: 40px; border-radius: 5px; border: 1px dashed rgba(255, 255, 255, .28); }
.tray .go {
  border: 0; border-radius: 9px; padding: 0 18px; height: 40px; cursor: pointer; white-space: nowrap;
  background: var(--accent); color: #fff; font-size: 13.5px; transition: filter .2s;
}
.tray .go:hover { filter: brightness(1.08); }
.tray .go:disabled { background: rgba(255, 255, 255, .12); color: rgba(255, 255, 255, .5); cursor: default; filter: none; }
@keyframes pop { from { transform: scale(.6); opacity: 0; } }

/* ── 整屏细看 ── */
.spread {
  position: fixed; inset: 0; z-index: 50; background: var(--bg);
  display: none; grid-template-rows: auto minmax(0, 1fr);
}
.spread.on { display: grid; animation: fade .35s var(--ease); }
@keyframes fade { from { opacity: 0; } }
.spread-top {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 14px var(--gutter); border-bottom: 1px solid var(--line);
}
.link-btn {
  border: 0; background: none; cursor: pointer; padding: 6px 0; font-size: 13px; color: var(--ink-2);
  display: inline-flex; align-items: center; gap: 8px; transition: color .2s;
}
.link-btn:hover { color: var(--accent); }
.pager { display: flex; align-items: center; gap: 6px; font-family: var(--mono); font-size: 12px; color: var(--muted); }
.pager b { color: var(--ink); font-weight: 500; }
.round {
  width: 34px; height: 34px; border-radius: 50%; border: 1px solid var(--line); background: var(--card);
  cursor: pointer; display: grid; place-items: center; color: var(--ink); transition: border-color .2s, color .2s;
}
.round:hover { border-color: var(--ink); }
.round:disabled { opacity: .35; cursor: default; }
.spread-body { display: grid; grid-template-columns: minmax(0, 1fr) minmax(340px, 420px); min-height: 0; }
.stage { display: grid; grid-template-rows: auto minmax(0, 1fr) auto; min-height: 0; padding: 18px 0 18px var(--gutter); gap: 14px; }
.tabs { display: flex; gap: 4px; }
.tabs button {
  border: 0; cursor: pointer; background: none; border-radius: 8px; padding: 5px 12px;
  font-size: 13px; color: var(--muted); transition: background .2s, color .2s;
}
.tabs button:hover { color: var(--ink); }
.tabs button[aria-pressed="true"] { background: var(--chip); color: var(--ink); }
.view { position: relative; min-height: 0; display: grid; place-items: center; overflow: hidden; }
.view img {
  display: block; border-radius: 6px; background: var(--card); box-shadow: 0 0 0 1px var(--line), var(--lift);
  cursor: zoom-in; transition: opacity .25s var(--ease);
}
.view img.swap { opacity: 0; }
.loupe {
  position: absolute; left: 0; top: 0; width: 240px; height: 240px; border-radius: 50%;
  pointer-events: none; opacity: 0; transform-origin: center;
  background-color: #fff; background-repeat: no-repeat;
  box-shadow: 0 0 0 1px rgba(23, 23, 26, .18), 0 0 0 5px rgba(255, 255, 255, .9), 0 18px 40px rgba(0, 0, 0, .28);
  transition: opacity .18s var(--ease);
}
.loupe.on { opacity: 1; }
.stage-foot { display: flex; align-items: center; justify-content: space-between; gap: 20px; min-width: 0; }
.hint { font-size: 12px; color: var(--muted); white-space: nowrap; }
.hint b { font-family: var(--mono); font-weight: 500; color: var(--ink-2); }
.strip { display: flex; gap: 8px; overflow-x: auto; padding: 4px 2px; scrollbar-width: none; }
.strip::-webkit-scrollbar { display: none; }
.strip button {
  flex: none; height: 44px; padding: 0; border: 0; border-radius: 5px; overflow: hidden; cursor: pointer;
  background: var(--card); box-shadow: 0 0 0 1px var(--line); opacity: .5;
  transition: opacity .25s, box-shadow .25s, transform .25s var(--ease);
}
.strip button img { height: 100%; width: auto; display: block; }
.strip button:hover { opacity: .9; transform: translateY(-2px); }
.strip button[aria-current="true"] { opacity: 1; box-shadow: 0 0 0 2px var(--ink); }

.info { overflow-y: auto; padding: 26px var(--gutter) 60px 44px; overscroll-behavior: contain; }
.info > * { animation: rise .6s var(--ease) both; }
.info > *:nth-child(2) { animation-delay: .04s; } .info > *:nth-child(3) { animation-delay: .08s; }
.info > *:nth-child(4) { animation-delay: .12s; } .info > *:nth-child(5) { animation-delay: .16s; }
.info > *:nth-child(n+6) { animation-delay: .2s; }
.eyebrow { margin: 0; font-size: 12px; color: var(--muted); letter-spacing: .04em; }
.title { text-wrap: balance; margin: 6px 0 0; font-family: var(--serif); font-weight: 700; font-size: clamp(26px, 2.4vw, 34px); line-height: 1.25; }
.facts { margin: 18px 0 0; display: flex; flex-wrap: wrap; gap: 6px; }
.facts span { font-size: 12px; padding: 2px 10px; border-radius: 999px; background: var(--chip); color: var(--ink-2); }
.facts span em { font-style: normal; color: var(--muted); margin-right: 4px; }
.look { margin: 20px 0 0; font-size: 13.5px; color: var(--ink-2); line-height: 1.9; }
.look.clamp { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.more { border: 0; background: none; padding: 0; cursor: pointer; font-size: 12.5px; color: var(--accent); }
.sec { margin-top: 30px; }
.sec h3 { margin: 0 0 10px; font-size: 12px; font-weight: 400; color: var(--muted); letter-spacing: .08em; display: flex; justify-content: space-between; }
.sec h3 small { font-size: 11.5px; letter-spacing: 0; }
.fit { display: grid; gap: 14px; margin-top: 28px; }
.fit div { padding-left: 14px; border-left: 2px solid var(--ink); }
.fit div.no { border-left-color: var(--line); }
.fit b { display: block; font-size: 12px; font-weight: 400; color: var(--muted); letter-spacing: .08em; margin-bottom: 2px; }
.fit p { margin: 0; font-size: 14px; line-height: 1.8; }
.fit div.no p { color: var(--ink-2); }
.tones { display: flex; height: 44px; border-radius: 8px; overflow: hidden; box-shadow: 0 0 0 1px var(--line); }
.tone {
  flex: 1; border: 0; padding: 0; cursor: copy; position: relative;
  transition: flex .35s var(--ease);
}
.tone span {
  position: absolute; left: 50%; bottom: 6px; transform: translateX(-50%); font-family: var(--mono); font-size: 10px;
  padding: 1px 5px; border-radius: 4px; background: rgba(255, 255, 255, .88); color: #17171A;
  opacity: 0; transition: opacity .2s; white-space: nowrap;
}
.tone:hover { flex: 3; }
.tone:hover span { opacity: 1; }
.call {
  margin-top: 30px; padding: 18px; border-radius: 12px; background: var(--card); box-shadow: 0 0 0 1px var(--line);
}
.call h3 { margin: 0 0 8px; }
.call p { margin: 0; font-size: 14px; line-height: 1.8; }
.call p code { font-family: var(--mono); font-size: 12px; color: var(--muted); }
.acts { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
.btn {
  border: 0; cursor: pointer; border-radius: 9px; height: 38px; padding: 0 16px; font-size: 13.5px;
  display: inline-flex; align-items: center; gap: 8px; transition: background .2s, color .2s, box-shadow .2s;
}
.btn.solid { background: var(--ink); color: var(--bg); }
.btn.solid:hover { background: var(--accent); color: #fff; }
.btn.line { background: none; box-shadow: inset 0 0 0 1px var(--line); color: var(--ink); }
.btn.line:hover { box-shadow: inset 0 0 0 1px var(--ink); }
.btn.line[aria-pressed="true"] { box-shadow: inset 0 0 0 1px var(--accent); color: var(--accent); }
.aliases { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 13.5px; color: var(--ink-2); }
details.fold { margin-top: 12px; border-top: 1px solid var(--line-soft); }
details.fold:first-of-type { margin-top: 30px; }
details.fold summary {
  list-style: none; cursor: pointer; padding: 14px 0 2px; font-size: 13.5px; color: var(--ink);
  display: flex; align-items: center; gap: 10px;
}
details.fold summary::-webkit-details-marker { display: none; }
details.fold summary em { font-style: normal; font-family: var(--mono); font-size: 11px; color: var(--muted); }
details.fold summary::after {
  content: ""; margin-left: auto; width: 8px; height: 8px; border-right: 1.5px solid var(--muted); border-bottom: 1.5px solid var(--muted);
  transform: rotate(45deg) translateY(-3px); transition: transform .3s var(--ease);
}
details.fold[open] summary::after { transform: rotate(225deg) translateY(-2px); }
details.fold summary:hover { color: var(--accent); }
.anchor { display: grid; grid-template-columns: 4.5em minmax(0, 1fr); gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--line-soft); font-size: 13px; }
.anchor:last-child { border-bottom: 0; }
.anchor b { font-weight: 400; color: var(--muted); }
.anchor span { color: var(--ink-2); line-height: 1.75; }
pre.prompt {
  margin: 12px 0 0; padding: 16px; border-radius: 10px; background: var(--card); box-shadow: 0 0 0 1px var(--line);
  white-space: pre-wrap; word-break: break-word; font-family: var(--mono); font-size: 11.5px; line-height: 1.85;
  color: var(--ink-2); max-height: 420px; overflow: auto;
}

@media (max-width: 960px) {
  .spread { overflow-y: auto; }
  .spread.on { display: block; }
  .spread-top { position: sticky; top: 0; z-index: 2; background: var(--bg-veil); backdrop-filter: blur(14px); }
  .spread-body { display: block; }
  .stage { padding: 16px var(--gutter) 0; grid-template-rows: auto auto auto; }
  .view { height: auto; }
  .info { overflow: visible; padding: 10px var(--gutter) 120px; }
  .hint { display: none; }
}

/* ── 并排对比 ── */
.versus { position: fixed; inset: 0; z-index: 55; background: var(--bg); overflow: auto; display: none; }
.versus.on { display: block; animation: fade .35s var(--ease); }
.versus-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 14px var(--gutter); border-bottom: 1px solid var(--line); position: sticky; top: 0; background: var(--bg-veil); backdrop-filter: blur(14px); z-index: 2; }
.versus-head h2 { margin: 0; font-family: var(--serif); font-size: 18px; }
.vgrid { display: grid; gap: 0 clamp(20px, 2.6vw, 44px); padding: 28px var(--gutter) 120px; }
.vgrid .rowlabel { font-size: 12px; color: var(--muted); letter-spacing: .08em; padding-top: 16px; border-top: 1px solid var(--line-soft); }
.vgrid .rowlabel.bare { border-top: 0; padding-top: 0; }
.vgrid .cell { padding: 16px 0 18px; border-top: 1px solid var(--line-soft); font-size: 13.5px; line-height: 1.8; min-width: 0; }
.vgrid .cell.bare { border-top: 0; padding-top: 0; }
.vgrid .cell.dim { color: var(--ink-2); }
.vgrid .shot {
  max-height: 64vh; display: grid; place-items: center; background: var(--card); border-radius: 8px;
  box-shadow: 0 0 0 1px var(--line); cursor: zoom-in; overflow: hidden; padding: 12px;
  transition: box-shadow .3s var(--ease);
}
.vgrid .shot:hover { box-shadow: 0 0 0 1px var(--line), var(--lift); }
.vgrid .shot img { max-width: 100%; max-height: 100%; display: block; }
.vgrid h3 { margin: 0; font-family: var(--serif); font-size: 19px; }
.vgrid .mini-tones { display: flex; height: 18px; border-radius: 4px; overflow: hidden; box-shadow: 0 0 0 1px var(--line); }
.vgrid .mini-tones i { flex: 1; }
@media (max-width: 760px) {
  .vgrid { grid-template-columns: 1fr !important; }
  .vgrid .rowlabel { display: none; }
}

/* 从图墙飞进细看的那张图 */
.ghost { position: fixed; z-index: 70; pointer-events: none; border-radius: 6px; object-fit: contain; background: var(--card); transform-origin: 0 0; }

.toast {
  position: fixed; left: 50%; top: 22px; z-index: 90; transform: translate(-50%, -16px);
  background: var(--ink); color: var(--bg); padding: 8px 18px; border-radius: 10px; font-size: 13px;
  opacity: 0; pointer-events: none; transition: opacity .25s var(--ease), transform .25s var(--ease);
}
.toast.on { opacity: 1; transform: translate(-50%, 0); }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; animation-delay: 0ms !important; transition-duration: .01ms !important; }
}
</style>
</head>
<body>

<header class="top">
  <div class="brand"><b>FigEcho</b><i>/</i>风格库</div>
  <div class="meta" id="meta"></div>
</header>

<section class="intro">
  <h1>先挑一张<br>看着<span>对</span>的图</h1>
  <p>每张都是风格的原始参考图，复用时真正送进模型的就是它。点开能放大看细节、左右翻页，选定后复制那句调用话术粘回对话里。拿不准就勾两三张并排比。</p>
</section>

<div class="bar-sentinel" id="sentinel"></div>
<div class="bar" id="bar">
  <label class="find">
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="7" cy="7" r="5.2"/><path d="M11 11l3.5 3.5" stroke-linecap="round"/></svg>
    <input id="q" type="search" autocomplete="off" placeholder="搜名称、别名或用途" aria-label="搜索风格">
    <kbd>/</kbd>
  </label>
  <div class="groups" id="groups"></div>
  <button class="clear" id="clear" hidden>清空</button>
  <span class="tally" id="tally"></span>
</div>

<main class="wall" id="wall"></main>
<p class="empty" id="empty" hidden>这组条件下没有风格。<button data-act="clear">清空条件</button>看全部。</p>

<footer class="colophon">
  <span id="colophon"></span>
  <span>写库命令 add / promote / certify / classify / rename / archive / refresh 成功后会自动重建这一页</span>
  <span class="snag" id="snag"></span>
</footer>

<div class="tray" id="tray">
  <span class="label">并排比</span>
  <div class="thumbs" id="tray-thumbs"></div>
  <button class="go" id="tray-go" data-act="versus" disabled>对比</button>
</div>

<div class="spread" id="spread" role="dialog" aria-modal="true" aria-label="风格细看">
  <div class="spread-top">
    <button class="link-btn" data-act="close">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10 3L5 8l5 5" stroke-linecap="round" stroke-linejoin="round"/></svg>全部风格
    </button>
    <div class="pager">
      <button class="round" data-act="prev" aria-label="上一个"><svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10 3L5 8l5 5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
      <span id="pos"></span>
      <button class="round" data-act="next" aria-label="下一个"><svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 3l5 5-5 5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
    </div>
  </div>
  <div class="spread-body">
    <section class="stage">
      <div class="tabs" id="tabs"></div>
      <div class="view" id="view"><img id="stage-img" alt=""><div class="loupe" id="loupe"></div></div>
      <div class="stage-foot">
        <span class="hint" id="hint"></span>
        <div class="strip" id="strip"></div>
      </div>
    </section>
    <aside class="info" id="info"></aside>
  </div>
</div>

<div class="versus" id="versus" role="dialog" aria-modal="true" aria-label="并排对比">
  <div class="versus-head">
    <button class="link-btn" data-act="close">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10 3L5 8l5 5" stroke-linecap="round" stroke-linejoin="round"/></svg>返回
    </button>
    <h2>并排比参考图</h2>
    <span style="width:60px"></span>
  </div>
  <div class="vgrid" id="vgrid"></div>
</div>

<div class="toast" id="toast"></div>

<script id="figecho-data" type="application/json">/*__FIGECHO_DATA__*/</script>
<script>
const DATA = JSON.parse(document.getElementById("figecho-data").textContent);
const FAMILY_ORDER = new Map();
DATA.families.forEach((family, index) => family.variants.forEach(slug => FAMILY_ORDER.set(slug, index)));
const STYLES = DATA.styles
  .filter(s => s.status !== "archived")
  .sort((a, b) => ((FAMILY_ORDER.get(a.slug) ?? 999) - (FAMILY_ORDER.get(b.slug) ?? 999)) || a.slug.localeCompare(b.slug));
const BY_SLUG = new Map(STYLES.map(s => [s.slug, s]));
const GROUPS = [["use_cases", "用在"], ["archetypes", "画的是"], ["expressions", "表达"]];
const MAX_PICKS = 3;
const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const FINE = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
const state = { q: "", facet: {}, picks: [], open: null, mode: "ref", zoom: null, hits: STYLES.slice() };

const el = id => document.getElementById(id);
const esc = v => String(v == null ? "" : v).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pad = n => String(n).padStart(2, "0");
const ICON_PLUS = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M8 3v10M3 8h10" stroke-linecap="round"/></svg>';

function toast(text) {
  const node = el("toast");
  node.textContent = text;
  node.classList.add("on");
  clearTimeout(node._t);
  node._t = setTimeout(() => node.classList.remove("on"), 1900);
}
function copyText(text, message) {
  const done = () => toast(message || "已复制");
  const fallback = () => {
    const area = document.createElement("textarea");
    area.value = text; area.style.position = "fixed"; area.style.opacity = "0";
    document.body.appendChild(area); area.select();
    try { document.execCommand("copy"); done(); } catch (e) { toast("复制失败，请手动选中"); }
    area.remove();
  };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done).catch(fallback);
  else fallback();
}

const facetLabel = (key, value) => (DATA.facet_vocabulary[key] && DATA.facet_vocabulary[key].values[value]) || value;
const refImage = s => (s.images.references || [])[0] || s.images.preview;
const imageFor = (s, mode) => (mode === "preview" && s.images.preview) ? s.images.preview : refImage(s);
const aspectOf = image => (image && image.width && image.height) ? image.width / image.height : 1.4;
const invokeLine = s => `用风格库里的「${s.name}」（slug: ${s.slug}）画一张图，内容是：`;
function kindShort(s) {
  const parts = [...(s.facets.use_cases || []).map(v => facetLabel("use_cases", v)),
                 ...(s.facets.archetypes || []).map(v => facetLabel("archetypes", v))];
  return parts.slice(0, 3).join(" · ");
}

/* ── 检索 ── */
function cjkCoverage(query, candidate) {
  const chars = new Set(Array.from(query).filter(c => /[㐀-鿿]/.test(c)));
  if (!chars.size) return 0;
  const target = new Set(Array.from(candidate));
  let hit = 0;
  chars.forEach(c => { if (target.has(c)) hit += 1; });
  return hit / chars.size;
}
function textMatch(s, q) {
  const facetWords = GROUPS.flatMap(([key]) => (s.facets[key] || []).map(v => facetLabel(key, v)));
  const fields = [s.name, s.slug, s.family_name, s.variant_name, ...(s.aliases || []), ...(s.tags || []),
    ...(s.best_for || []), ...facetWords].map(v => String(v || "").toLowerCase());
  const one = term => fields.some(v => v.includes(term));
  if (one(q)) return true;
  const terms = q.split(/\s+/).filter(Boolean);
  if (terms.length > 1 && terms.every(one)) return true;
  // 覆盖率逐个标签算，混成一锅会让任何查询都命中所有风格
  const labels = [s.name, s.slug, s.family_name, s.variant_name, ...(s.aliases || [])];
  return labels.some(v => cjkCoverage(q, String(v || "").toLowerCase()) >= 0.7);
}
function matches(s, facet) {
  for (const [key] of GROUPS) {
    const want = facet[key];
    if (want && !(s.facets[key] || []).includes(want)) return false;
  }
  const q = state.q.trim().toLowerCase();
  return !q || textMatch(s, q);
}

/* ── 筛选条，每个选项带上"选了还剩几个"，剩零个就灰掉 ── */
function renderGroups() {
  el("groups").innerHTML = GROUPS.map(([key, title]) => {
    const used = new Set();
    STYLES.forEach(s => (s.facets[key] || []).forEach(v => used.add(v)));
    if (!used.size) return "";
    const vocab = Object.keys((DATA.facet_vocabulary[key] || {}).values || {});
    const values = Array.from(used).sort((a, b) => (vocab.indexOf(a) - vocab.indexOf(b)) || a.localeCompare(b));
    const chips = values.map(v => `<button class="chip" data-facet="${esc(key)}" data-value="${esc(v)}" aria-pressed="false">${esc(facetLabel(key, v))}<sup></sup></button>`).join("");
    return `<div class="group"><span>${esc(title)}</span>${chips}</div>`;
  }).join("");
}
function refreshChips() {
  document.querySelectorAll(".chip").forEach(chip => {
    const key = chip.dataset.facet, value = chip.dataset.value;
    const on = state.facet[key] === value;
    const trial = { ...state.facet, [key]: value };
    const count = STYLES.filter(s => matches(s, trial)).length;
    chip.setAttribute("aria-pressed", String(on));
    chip.disabled = !on && count === 0;
    chip.querySelector("sup").textContent = count;
  });
  const dirty = state.q.trim() || Object.values(state.facet).some(Boolean);
  el("clear").hidden = !dirty;
}

/* ── 图墙 ── */
const tiles = new Map();
function buildTiles() {
  const wall = el("wall");
  STYLES.forEach((s, i) => {
    const image = refImage(s);
    const node = document.createElement("article");
    node.className = "tile";
    node.dataset.slug = s.slug;
    node.style.setProperty("--i", i);
    node.innerHTML = `
      <button class="tile-hit" data-open="${esc(s.slug)}" aria-label="细看 ${esc(s.name)}">
        <span class="frame">${image ? `<img src="${esc(image.thumb)}" alt="${esc(s.name)} 参考图" decoding="async">` : ""}</span>
        <span class="cap"><span class="no">${pad(i + 1)}</span><span style="min-width:0;display:block"><span class="nm">${esc(s.name)}</span><span class="kind">${esc(kindShort(s))}</span></span></span>
      </button>
      <button class="pick" data-pick="${esc(s.slug)}" aria-pressed="false" data-tip="加入对比" aria-label="加入对比">${ICON_PLUS}</button>`;
    wall.appendChild(node);
    tiles.set(s.slug, node);
  });
}

const CAP_H = 62;
function rowTarget(width) { return Math.max(200, Math.min(300, width * 0.2)); }

// 每行等高、宽度按比例分，行满的判据是"加下一张后行高离目标更远"
function packRows(list, width, gap) {
  if (width < 620) {
    return list.map(s => {
      const a = aspectOf(refImage(s));
      const h = Math.min(width / a, width * 1.3);
      return { items: [s], height: h, center: true };
    });
  }
  const target = rowTarget(width);
  const rows = [];
  let row = [], sum = 0;
  list.forEach(s => {
    const a = aspectOf(refImage(s));
    if (row.length) {
      const now = (width - gap * (row.length - 1)) / sum;
      const next = (width - gap * row.length) / (sum + a);
      if (next < target && Math.abs(now - target) <= Math.abs(next - target)) {
        rows.push({ items: row, height: Math.min(now, target * 1.35) });
        row = []; sum = 0;
      }
    }
    row.push(s); sum += a;
  });
  if (row.length) {
    const fill = (width - gap * (row.length - 1)) / sum;
    rows.push({ items: row, height: Math.min(fill, target * 1.1) });
  }
  return rows;
}

function layout() {
  const wall = el("wall");
  const width = wall.clientWidth;
  const gap = width < 620 ? 16 : Math.round(Math.max(20, Math.min(34, width * 0.022)));
  const rowGap = width < 620 ? 40 : 52;
  const shown = new Set(state.hits.map(s => s.slug));
  let y = 0;
  packRows(state.hits, width, gap).forEach(row => {
    const widths = row.items.map(s => row.height * aspectOf(refImage(s)));
    let x = row.center ? (width - widths[0]) / 2 : 0;
    row.items.forEach((s, k) => {
      const node = tiles.get(s.slug);
      node.style.width = widths[k] + "px";
      node.classList.toggle("narrow", widths[k] < 180);
      node.style.transform = `translate(${x}px, ${y}px)`;
      node.querySelector(".frame").style.height = row.height + "px";
      x += widths[k] + gap;
    });
    y += row.height + CAP_H + rowGap;
  });
  tiles.forEach((node, slug) => node.classList.toggle("gone", !shown.has(slug)));
  wall.style.height = Math.max(0, y - rowGap) + "px";
}

function apply() {
  state.hits = STYLES.filter(s => matches(s, state.facet));
  layout();
  refreshChips();
  el("empty").hidden = state.hits.length > 0;
  el("tally").innerHTML = `<b>${state.hits.length}</b> / ${STYLES.length}`;
}

/* ── 对比 ── */
function togglePick(slug) {
  if (state.picks.includes(slug)) state.picks = state.picks.filter(s => s !== slug);
  else if (state.picks.length >= MAX_PICKS) { toast(`最多并排 ${MAX_PICKS} 个`); return; }
  else state.picks.push(slug);
  syncPicks();
}
function syncPicks() {
  document.querySelectorAll("[data-pick]").forEach(node => {
    const on = state.picks.includes(node.dataset.pick);
    node.setAttribute("aria-pressed", String(on));
    if (node.classList.contains("pick")) node.dataset.tip = on ? "移出对比" : "加入对比";
    else node.lastChild.textContent = on ? "已在对比里" : "加入对比";
  });
  el("tray").classList.toggle("on", state.picks.length > 0);
  const slots = Array.from({ length: MAX_PICKS - state.picks.length }, () => '<span class="slot"></span>').join("");
  el("tray-thumbs").innerHTML = state.picks.map(slug => {
    const s = BY_SLUG.get(slug), image = refImage(s);
    return `<button class="thumb" data-pick="${esc(slug)}" title="移出 ${esc(s.name)}">${image ? `<img src="${esc(image.thumb)}" alt="">` : ""}</button>`;
  }).join("") + slots;
  el("tray-go").disabled = state.picks.length < 2;
  el("tray-go").textContent = state.picks.length < 2 ? "再选一个" : `对比 ${state.picks.length} 个`;
}
function openVersus() {
  const picks = state.picks.map(slug => BY_SLUG.get(slug));
  const grid = el("vgrid");
  // 图格统一按最高那张的比例开，横图不至于缩在大白框里
  const shotRatio = Math.max(0.7, Math.min(...picks.map(s => aspectOf(refImage(s)))));
  grid.style.gridTemplateColumns = `5em repeat(${picks.length}, minmax(0, 1fr))`;
  const row = (label, render, cls) =>
    `<div class="rowlabel ${cls || ""}">${label}</div>` + picks.map(s => `<div class="cell ${cls || ""}">${render(s)}</div>`).join("");
  grid.innerHTML = [
    row("", s => { const im = refImage(s); return `<div class="shot" data-open="${esc(s.slug)}" style="aspect-ratio:${shotRatio.toFixed(3)}">${im ? `<img src="${esc(im.view || im.thumb)}" alt="">` : ""}</div>`; }, "bare"),
    row("", s => `<h3>${esc(s.name)}</h3>`, "bare"),
    row("适合", s => esc((s.best_for || []).join("；"))),
    row("不适合", s => `<span style="color:var(--ink-2)">${esc((s.not_for || []).join("；"))}</span>`),
    row("配色", s => `<div class="mini-tones">${(s.palette || []).slice(0, 8).map(c => `<i style="background:${esc(c)}"></i>`).join("")}</div>`),
    row("图型", s => esc(kindShort(s))),
    row("", s => `<button class="btn solid" data-copy="${esc(s.slug)}">复制话术</button>`),
  ].join("");
  el("versus").classList.add("on");
  el("versus").scrollTop = 0;
  lock();
}

/* ── 整屏细看 ── */
function lock() { document.body.classList.add("locked"); }
function unlockIfClear() { if (!document.querySelector(".spread.on, .versus.on")) document.body.classList.remove("locked"); }

function fitStage() {
  const s = BY_SLUG.get(state.open);
  if (!s) return;
  const image = imageFor(s, state.mode);
  const view = el("view"), img = el("stage-img");
  const a = aspectOf(image);
  // 窄屏是上下排，舞台高度跟着图走，不留大块空白
  view.style.height = window.innerWidth <= 960 ? Math.min(view.clientWidth / a, window.innerHeight * 0.7) + "px" : "";
  const box = view.getBoundingClientRect();
  let w = box.width, h = w / a;
  if (h > box.height) { h = box.height; w = h * a; }
  img.style.width = Math.floor(w) + "px";
  img.style.height = Math.floor(h) + "px";
  state.zoom = null;
}

function showImage(s, mode) {
  const image = imageFor(s, mode);
  const img = el("stage-img");
  const want = image.view || image.thumb;
  img.dataset.full = image.full || want;
  img.dataset.view = want;
  img.alt = `${s.name} ${mode === "preview" ? "成图" : "参考图"}`;
  if (img.getAttribute("src") !== want) {
    img.src = image.thumb;
    const pre = new Image();
    pre.onload = () => { if (img.dataset.view === want) img.src = want; };
    pre.src = want;
  }
  el("loupe").style.backgroundImage = `url("${want.replace(/"/g, "%22")}")`;
  fitStage();
}

function renderSpread(s) {
  const index = state.hits.indexOf(s);
  const list = index >= 0 ? state.hits : STYLES;
  const at = list.indexOf(s);
  el("pos").innerHTML = `<b>${pad(at + 1)}</b> / ${pad(list.length)}`;
  document.querySelector('[data-act="prev"]').disabled = at <= 0;
  document.querySelector('[data-act="next"]').disabled = at >= list.length - 1;

  el("tabs").innerHTML = `<button data-mode="ref" aria-pressed="${state.mode === "ref"}">参考图</button>` +
    (s.images.preview ? `<button data-mode="preview" aria-pressed="${state.mode === "preview"}">用它画出来的样例</button>` : "");
  el("hint").innerHTML = FINE ? `悬停放大 · 滚轮调倍率 <b id="zoom-read"></b> · 点击开原图` : "点图打开原图";
  el("strip").innerHTML = list.map(item => {
    const im = refImage(item);
    return `<button data-go="${esc(item.slug)}" aria-current="${item === s}" title="${esc(item.name)}">${im ? `<img src="${esc(im.thumb)}" alt="">` : ""}</button>`;
  }).join("");
  const current = el("strip").querySelector('[aria-current="true"]');
  if (current) current.scrollIntoView({ block: "nearest", inline: "center" });

  const facts = GROUPS.flatMap(([key, title]) => (s.facets[key] || []).map(v => `<span><em>${esc(title)}</em>${esc(facetLabel(key, v))}</span>`)).join("");
  const tones = (s.palette || []).map(c => `<button class="tone" style="background:${esc(c)}" data-hex="${esc(c)}" aria-label="复制 ${esc(c)}"><span>${esc(c)}</span></button>`).join("");
  const anchors = (s.anchors || []).map(a => `<div class="anchor"><b>${esc(a.dimension_label || a.dimension)}</b><span>${esc(a.rule)}</span></div>`).join("");
  const picked = state.picks.includes(s.slug);
  const variant = s.variant_name && s.variant_name !== "默认版" ? ` · ${esc(s.variant_name)}` : "";
  el("info").innerHTML = `
    ${s.family_name !== s.name ? `<p class="eyebrow">${esc(s.family_name)}${variant}</p>` : ""}
    <h2 class="title">${esc(s.name)}</h2>
    ${facts ? `<div class="facts">${facts}</div>` : ""}
    ${s.summary ? `<div><p class="look clamp" id="look">${esc(s.summary)}</p><button class="more" data-act="more" hidden>展开</button></div>` : ""}
    <div class="fit">
      ${(s.best_for || []).length ? `<div><b>适合</b><p>${esc(s.best_for.join("；"))}</p></div>` : ""}
      ${(s.not_for || []).length ? `<div class="no"><b>不适合</b><p>${esc(s.not_for.join("；"))}</p></div>` : ""}
    </div>
    ${tones ? `<div class="sec"><h3>配色<small>点色块复制色值</small></h3><div class="tones">${tones}</div></div>` : ""}
    <div class="call">
      <h3 style="font-size:12px;font-weight:400;color:var(--muted);letter-spacing:.08em">调用话术</h3>
      <p>${esc(invokeLine(s))}</p>
      <div class="acts">
        <button class="btn solid" data-copy="${esc(s.slug)}">复制话术</button>
        <button class="btn line" data-pick="${esc(s.slug)}" aria-pressed="${picked}">${ICON_PLUS}<span>${picked ? "已在对比里" : "加入对比"}</span></button>
      </div>
    </div>
    ${(s.aliases || []).length ? `<div class="sec"><h3>也可以这么叫它</h3><div class="aliases">${s.aliases.map(a => `<span>${esc(a)}</span>`).join("")}</div></div>` : ""}
    ${anchors ? `<details class="fold"><summary>风格锚点 <em>${(s.anchors || []).length}</em></summary>${anchors}</details>` : ""}
    ${s.prompt ? `<details class="fold"><summary>完整风格提示词</summary><div class="acts" style="margin-top:8px"><button class="btn line" data-copy-prompt="${esc(s.slug)}">复制全部提示词</button></div><pre class="prompt">${esc(s.prompt)}</pre></details>` : ""}`;
  el("info").scrollTop = 0;
  const look = el("look");
  if (look && look.scrollHeight > look.clientHeight + 2) document.querySelector('[data-act="more"]').hidden = false;
  showImage(s, state.mode);
}

function openSpread(slug, fromNode) {
  const s = BY_SLUG.get(slug);
  if (!s) return;
  const already = el("spread").classList.contains("on");
  state.open = slug;
  state.mode = "ref";
  el("spread").classList.add("on");
  lock();
  renderSpread(s);
  history.replaceState(null, "", "#" + slug);
  if (already || REDUCED || !fromNode) return;
  // 图从墙上飞到舞台，让人知道自己点开的是哪一张
  const src = fromNode.getBoundingClientRect();
  const target = el("stage-img");
  const dst = target.getBoundingClientRect();
  if (!src.width || !dst.width) return;
  const ghost = document.createElement("img");
  ghost.src = fromNode.currentSrc || fromNode.src;
  ghost.className = "ghost";
  Object.assign(ghost.style, { left: dst.left + "px", top: dst.top + "px", width: dst.width + "px", height: dst.height + "px" });
  document.body.appendChild(ghost);
  target.style.opacity = "0";
  ghost.animate([
    { transform: `translate(${src.left - dst.left}px, ${src.top - dst.top}px) scale(${src.width / dst.width}, ${src.height / dst.height})` },
    { transform: "none" },
  ], { duration: 620, easing: "cubic-bezier(.2,.7,.2,1)" }).onfinish = () => {
    target.style.opacity = "";
    ghost.remove();
  };
}

function step(delta) {
  const list = state.hits.includes(BY_SLUG.get(state.open)) ? state.hits : STYLES;
  const at = list.findIndex(s => s.slug === state.open);
  const next = list[at + delta];
  if (!next) return;
  const img = el("stage-img");
  img.classList.add("swap");
  setTimeout(() => {
    state.open = next.slug; state.mode = "ref";
    renderSpread(next);
    history.replaceState(null, "", "#" + next.slug);
    requestAnimationFrame(() => img.classList.remove("swap"));
  }, REDUCED ? 0 : 160);
}

function closeTop() {
  if (el("versus").classList.contains("on")) { el("versus").classList.remove("on"); unlockIfClear(); return true; }
  if (el("spread").classList.contains("on")) {
    el("spread").classList.remove("on");
    el("loupe").classList.remove("on");
    const node = tiles.get(state.open);
    state.open = null;
    history.replaceState(null, "", location.pathname + location.search);
    unlockIfClear();
    if (node && !node.classList.contains("gone")) node.scrollIntoView({ block: "nearest" });
    return true;
  }
  return false;
}

/* ── 放大镜 ── */
function loupeZoom(img) {
  if (state.zoom) return state.zoom;
  const s = BY_SLUG.get(state.open);
  const image = imageFor(s, state.mode);
  const w = image.width || 2000, h = image.height || 2000;
  const viewW = w * Math.min(1, 2000 / Math.max(w, h));
  state.zoom = Math.max(2, Math.min(5, viewW / img.clientWidth));
  return state.zoom;
}
function moveLoupe(event) {
  const img = el("stage-img"), loupe = el("loupe");
  const r = img.getBoundingClientRect(), v = el("view").getBoundingClientRect();
  const x = event.clientX - r.left, y = event.clientY - r.top;
  if (x < 0 || y < 0 || x > r.width || y > r.height) { loupe.classList.remove("on"); return; }
  const z = loupeZoom(img), R = loupe.offsetWidth / 2;
  loupe.classList.add("on");
  loupe.style.transform = `translate(${event.clientX - v.left - R}px, ${event.clientY - v.top - R}px)`;
  loupe.style.backgroundSize = `${r.width * z}px ${r.height * z}px`;
  loupe.style.backgroundPosition = `${R - x * z}px ${R - y * z}px`;
  const read = el("zoom-read");
  if (read) read.textContent = "×" + z.toFixed(1);
}
if (FINE) {
  el("view").addEventListener("pointermove", moveLoupe);
  el("view").addEventListener("pointerleave", () => el("loupe").classList.remove("on"));
  el("view").addEventListener("wheel", event => {
    if (!el("loupe").classList.contains("on")) return;
    event.preventDefault();
    const z = loupeZoom(el("stage-img"));
    state.zoom = Math.max(1.5, Math.min(8, z * (event.deltaY < 0 ? 1.15 : 1 / 1.15)));
    moveLoupe(event);
  }, { passive: false });
}

/* ── 事件 ── */
document.addEventListener("click", event => {
  const t = event.target.closest("[data-open], [data-pick], [data-copy], [data-copy-prompt], [data-hex], [data-go], [data-mode], [data-facet], [data-act], #clear, #stage-img");
  if (!t) return;
  const d = t.dataset;
  if (t.id === "stage-img") { window.open(t.dataset.full, "_blank", "noopener"); return; }
  if (d.pick) { togglePick(d.pick); return; }
  if (d.open) {
    if (el("versus").classList.contains("on")) { el("versus").classList.remove("on"); openSpread(d.open); return; }
    openSpread(d.open, t.querySelector("img"));
    return;
  }
  if (d.copy) { copyText(invokeLine(BY_SLUG.get(d.copy)), "话术已复制，粘回对话里就能精确命中"); return; }
  if (d.copyPrompt) { copyText(BY_SLUG.get(d.copyPrompt).prompt, "完整提示词已复制"); return; }
  if (d.hex) { copyText(d.hex, `${d.hex} 已复制`); return; }
  if (d.go) { if (d.go !== state.open) { const img = el("stage-img"); img.classList.add("swap"); setTimeout(() => { state.open = d.go; state.mode = "ref"; renderSpread(BY_SLUG.get(d.go)); history.replaceState(null, "", "#" + d.go); requestAnimationFrame(() => img.classList.remove("swap")); }, REDUCED ? 0 : 160); } return; }
  if (d.mode) {
    state.mode = d.mode;
    el("tabs").querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.mode === d.mode)));
    showImage(BY_SLUG.get(state.open), d.mode);
    return;
  }
  if (d.facet) {
    state.facet[d.facet] = state.facet[d.facet] === d.value ? null : d.value;
    apply();
    return;
  }
  if (t.id === "clear" || d.act === "clear") {
    state.q = ""; el("q").value = ""; state.facet = {};
    apply();
    return;
  }
  if (d.act === "close") { closeTop(); return; }
  if (d.act === "prev") { step(-1); return; }
  if (d.act === "next") { step(1); return; }
  if (d.act === "versus") { if (state.picks.length >= 2) openVersus(); return; }
  if (d.act === "more") { el("look").classList.remove("clamp"); t.hidden = true; return; }
});

document.addEventListener("keydown", event => {
  const typing = /input|textarea/i.test(document.activeElement.tagName);
  if (event.key === "Escape") {
    if (typing && document.activeElement.id === "q" && state.q) { state.q = ""; el("q").value = ""; apply(); return; }
    closeTop(); return;
  }
  if (typing) return;
  if (el("spread").classList.contains("on") && !el("versus").classList.contains("on")) {
    if (event.key === "ArrowLeft") { event.preventDefault(); step(-1); }
    if (event.key === "ArrowRight") { event.preventDefault(); step(1); }
    return;
  }
  if (event.key === "/") { event.preventDefault(); el("q").focus(); }
});

el("q").addEventListener("input", event => { state.q = event.target.value; apply(); });

if ("IntersectionObserver" in window) {
  new IntersectionObserver(([entry]) => el("bar").classList.toggle("stuck", !entry.isIntersecting))
    .observe(el("sentinel"));
}

let resizeTimer = null;
window.addEventListener("resize", () => {
  el("wall").classList.add("still");
  layout();
  if (state.open) fitStage();
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => el("wall").classList.remove("still"), 120);
});

el("meta").textContent = `${STYLES.length} 个风格 · ${new Set(STYLES.map(s => s.family_id)).size} 个家族 · 更新于 ${DATA.catalog_updated_at || DATA.generated_at}`;
el("colophon").textContent = `FigEcho Style Library · 页面生成于 ${DATA.generated_at}`;
if ((DATA.problems || []).length) el("snag").textContent = "生成时发现 " + DATA.problems.join("；");

renderGroups();
buildTiles();
el("wall").classList.add("still");
apply();
requestAnimationFrame(() => el("wall").classList.remove("still"));
syncPicks();
const initial = decodeURIComponent(location.hash.slice(1));
if (BY_SLUG.has(initial)) openSpread(initial);
</script>
</body>
</html>
"""


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    default_root = Path(os.environ.get("FIGECHO_LIBRARY", DEFAULT_LIBRARY))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=default_root)
    parser.add_argument("--out", type=Path, help="Output HTML path. Defaults to <library>/gallery.html.")
    parser.add_argument("--no-thumbnails", action="store_true", help="Reference full-size images directly.")
    parser.add_argument("--exclude", action="append", default=[], help="Slug to leave out of the page.")
    parser.add_argument("--open", action="store_true", help="Open the built page in the default browser.")
    parser.add_argument("--status", action="store_true", help="Report staleness without rebuilding.")
    args = parser.parse_args()
    try:
        if args.status:
            result = {"ok": True, "action": "gallery-status", **gallery_status(args.library)}
        else:
            result = build_gallery(
                args.library,
                out=args.out,
                thumbs=not args.no_thumbnails,
                exclude=args.exclude,
            )
            if args.open:
                webbrowser.open(Path(result["path"]).as_uri())
    except Exception as exc:
        result = {"ok": False, "action": "gallery", "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()

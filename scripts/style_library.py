#!/usr/bin/env python3
"""Manage named FigEcho Style Packs with original reference images."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from datetime import date
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY = PACKAGE_ROOT / "style-library"
CATALOG_NAME = "catalog.json"
PACK_NAME = "style-pack.json"
VALID_STATUSES = {"candidate", "validated", "archived"}
VALID_PORTABILITY_STATUSES = {"untested", "passed"}
VALID_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HEX_COLOR_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")
ICON_EXAMPLE_ENUMERATION_RE = re.compile(
    r"(例如|可使用|包括|比如|such as|for example|including)[^。\n]{0,240}(、|,)[^。\n]{0,240}(、|,)",
    re.IGNORECASE,
)
ABSOLUTE_OPTIONAL_MEDIA_BAN_RE = re.compile(
    r"(禁止|不得|严禁|不要使用|不使用|forbid|must not use|do not use|never use)"
    r"[^。\n]{0,160}(logo|照片|photo|photograph|3d|渐变|gradient|发光|glow|玻璃|glass|阴影|shadow|写实插画|realistic illustration)",
    re.IGNORECASE,
)
REQUIRED_PROMPT_SECTIONS = [
    "【图像类型】",
    "【内容结构】",
    "【整体版式】",
    "【组件语言】",
    "【连接线】",
    "【插图与图标风格】",
    "【配色】",
    "【字体层级】",
    "【视觉气质】",
    "【关键风格特征】",
    "【生成约束】",
]


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def today() -> str:
    return date.today().isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text_file(path: Path) -> str:
    """Hash UTF-8 text with canonical LF endings across Git platforms."""
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def default_catalog() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "updated_at": today(),
        "reference_policy": "original-reference-images",
        "templates": [],
    }


def ensure_library(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    catalog_path = root / CATALOG_NAME
    if not catalog_path.exists():
        atomic_json(catalog_path, default_catalog())
    return load_json(catalog_path)


def safe_pack_dir(root: Path, slug: str) -> Path:
    if not SLUG_RE.fullmatch(slug):
        raise ValueError(
            "slug must use lowercase ASCII letters, digits and single hyphens"
        )
    target = (root / "templates" / slug).resolve()
    target.relative_to(root.resolve())
    return target


def resolve_job_file(job_dir: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    candidates = [path] if path.is_absolute() else [job_dir / path, path]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(f"reference image not found: {raw}")


def fingerprint_payload(style: dict[str, Any]) -> dict[str, Any]:
    anchors = []
    for item in style.get("signature_anchors", []):
        if isinstance(item, dict):
            anchors.append(
                {
                    "dimension": item.get("dimension"),
                    "rule": item.get("rule"),
                    "weight": item.get("weight"),
                    "prompt_token": item.get("prompt_token"),
                }
            )
    anchors.sort(
        key=lambda item: (
            str(item.get("dimension", "")),
            str(item.get("rule", "")),
        )
    )
    visual_system: dict[str, list[str]] = {}
    raw_visual = style.get("visual_system", {})
    if isinstance(raw_visual, dict):
        for dimension in sorted(raw_visual):
            block = raw_visual.get(dimension, {})
            if isinstance(block, dict):
                visual_system[str(dimension)] = sorted(
                    str(value).strip()
                    for value in block.get("transfer_rules", [])
                    if str(value).strip()
                )
    return {
        "signature_anchors": anchors,
        "visual_system": visual_system,
        "conditional_rules": sorted(
            str(value).strip()
            for value in style.get("conditional_rules", [])
            if str(value).strip()
        ),
        "anti_generic": sorted(
            str(value).strip()
            for value in style.get("anti_generic", [])
            if str(value).strip()
        ),
        "transfer_boundary": style.get("transfer_boundary", {}),
    }


def fingerprint_sha256(style: dict[str, Any]) -> str:
    canonical = json.dumps(
        fingerprint_payload(style), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_prompt_asset(prompt: str, style: dict[str, Any]) -> None:
    missing = [section for section in REQUIRED_PROMPT_SECTIONS if section not in prompt]
    if missing:
        raise ValueError(f"style prompt is missing required sections: {missing}")
    palette_start = prompt.find("【配色】") + len("【配色】")
    palette_end = prompt.find("【字体层级】", palette_start)
    palette = prompt[palette_start:palette_end]
    if len({value.upper() for value in HEX_COLOR_RE.findall(palette)}) < 3:
        raise ValueError(
            "style prompt palette must contain at least three concrete #RRGGBB colors"
        )
    palette_spec = json.dumps(
        style.get("visual_system", {}).get("palette", {}), ensure_ascii=False
    )
    if len({value.upper() for value in HEX_COLOR_RE.findall(palette_spec)}) < 3:
        raise ValueError(
            "style spec palette must contain at least three concrete #RRGGBB colors"
        )
    layout_start = prompt.find("【整体版式】") + len("【整体版式】")
    layout_end = prompt.find("【组件语言】", layout_start)
    layout = prompt[layout_start:layout_end]
    if not re.search(
        r"(根据|按照|按).{0,12}(新内容|内容关系|内容拓扑|节点关系).{0,18}(调整|适配|重算|选择)",
        layout,
    ):
        raise ValueError("style prompt layout must adapt to the new content topology")
    icon_start = prompt.find("【插图与图标风格】") + len("【插图与图标风格】")
    icon_end = prompt.find("【配色】", icon_start)
    icon_body = prompt[icon_start:icon_end]
    if not re.search(
        r"(根据|按照|按).{0,12}(新内容|内容实体|对象|动作).{0,18}(选择|设计|替换|生成).{0,10}(图标|插图)",
        icon_body,
    ):
        raise ValueError("style prompt icon subjects must derive from the new content")
    if ICON_EXAMPLE_ENUMERATION_RE.search(icon_body):
        raise ValueError("style prompt must not enumerate subject-specific icon examples")
    if not re.search(
        r"(根据|按照|按).{0,12}(新内容|内容层级|内容关系|语义层级).{0,18}(分配|映射|指定|选择).{0,10}(颜色|强调色|色彩)",
        palette,
    ):
        raise ValueError("style prompt color roles must derive from the new content hierarchy")
    match = ABSOLUTE_OPTIONAL_MEDIA_BAN_RE.search(prompt)
    if match:
        raise ValueError(f"style prompt contains an absolute optional-media ban: {match.group(0)!r}")
    boundary = style.get("transfer_boundary", {})
    expected = {
        "layout_policy": "preserve-visual-rhythm-adapt-to-new-topology",
        "icon_subject_policy": "derive-from-new-content",
        "color_role_policy": "assign-by-new-content-hierarchy",
        "supporting_asset_policy": "allow-user-provided-or-content-required",
    }
    if not isinstance(boundary, dict) or any(
        boundary.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("style spec transfer_boundary is incomplete")
    if "todo" in prompt.casefold():
        raise ValueError("style prompt still contains TODO values")
    style_text = json.dumps(style, ensure_ascii=False).casefold()
    if "todo" in style_text or "placeholder" in style_text:
        raise ValueError("style spec still contains TODO or placeholder values")


def compact_entry(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": pack["slug"],
        "name": pack["name"],
        "aliases": pack.get("aliases", []),
        "status": pack["status"],
        "portability_status": pack.get("portability_status", "untested"),
        "tags": pack["tags"],
        "best_for": pack["best_for"],
        "not_for": pack["not_for"],
        "path": f"templates/{pack['slug']}/{PACK_NAME}",
        "fingerprint_sha256": pack["fingerprint_sha256"],
        "reference_count": len(pack["references"]),
        "updated_at": pack["updated_at"],
    }


def update_catalog(root: Path, pack: dict[str, Any]) -> None:
    catalog = ensure_library(root)
    templates = catalog.get("templates", [])
    if not isinstance(templates, list):
        raise ValueError("catalog templates must be a list")
    entry = compact_entry(pack)
    replaced = False
    for index, item in enumerate(templates):
        if isinstance(item, dict) and item.get("slug") == pack["slug"]:
            templates[index] = entry
            replaced = True
            break
    if not replaced:
        templates.append(entry)
    templates.sort(key=lambda item: str(item.get("slug", "")))
    catalog["updated_at"] = today()
    catalog["reference_policy"] = "original-reference-images"
    catalog["templates"] = templates
    atomic_json(root / CATALOG_NAME, catalog)


def drop_from_catalog(root: Path, slug: str) -> None:
    catalog = ensure_library(root)
    templates = catalog.get("templates", [])
    if not isinstance(templates, list):
        raise ValueError("catalog templates must be a list")
    catalog["templates"] = [
        item
        for item in templates
        if not (isinstance(item, dict) and item.get("slug") == slug)
    ]
    catalog["updated_at"] = today()
    atomic_json(root / CATALOG_NAME, catalog)


def add_pack(args: argparse.Namespace) -> dict[str, Any]:
    root = args.library.resolve()
    catalog = ensure_library(root)
    pack_dir = safe_pack_dir(root, args.slug)
    if pack_dir.exists():
        raise FileExistsError(f"style template already exists: {args.slug}")

    job_dir = args.job_dir.resolve()
    prompt_path = job_dir / "style-prompt.md"
    spec_path = job_dir / "style-spec.json"
    if not prompt_path.is_file() or not spec_path.is_file():
        raise FileNotFoundError(
            "job directory must contain style-prompt.md and style-spec.json"
        )
    style = load_json(spec_path)
    prompt_text = prompt_path.read_text(encoding="utf-8")
    validate_prompt_asset(prompt_text, style)
    fingerprint = fingerprint_sha256(style)
    for item in catalog.get("templates", []):
        if (
            isinstance(item, dict)
            and item.get("fingerprint_sha256") == fingerprint
            and item.get("status") != "archived"
        ):
            raise ValueError(
                f"duplicate visual fingerprint already exists as {item.get('slug')!r}"
            )

    raw_references = args.reference or [
        str(item.get("path"))
        for item in style.get("references", [])
        if isinstance(item, dict) and item.get("path")
    ]
    if not raw_references:
        raise ValueError("at least one original reference image is required")
    references = [resolve_job_file(job_dir, raw) for raw in raw_references]
    for reference in references:
        if reference.suffix.lower() not in VALID_IMAGE_EXTENSIONS:
            raise ValueError(f"unsupported reference image type: {reference.name}")

    temporary = pack_dir.parent / f".{args.slug}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        copy_file(prompt_path, temporary / "style-prompt.md")
        reference_records = []
        for index, source in enumerate(references, start=1):
            target_name = f"reference-{index:02d}{source.suffix.lower()}"
            relative = f"references/{target_name}"
            target = temporary / relative
            copy_file(source, target)
            reference_records.append(
                {
                    "path": relative,
                    "role": "style_reference",
                    "original_name": source.name,
                    "sha256": sha256_file(target),
                }
            )

        packed_style = json.loads(json.dumps(style, ensure_ascii=False))
        packed_style["references"] = [
            {
                "path": item["path"],
                "role": "style_reference",
                "notes": "original reference retained in this Style Pack",
            }
            for item in reference_records
        ]
        atomic_json(temporary / "style-spec.json", packed_style)

        pack = {
            "schema_version": "1.0.0",
            "slug": args.slug,
            "name": args.name.strip(),
            "aliases": sorted(
                {value.strip() for value in getattr(args, "alias", []) or [] if value.strip()}
            ),
            "description": args.description.strip(),
            "status": "candidate",
            "portability_status": "untested",
            "tags": sorted(set(args.tag)),
            "best_for": sorted(set(args.best_for)),
            "not_for": sorted(set(args.not_for)),
            "created_at": today(),
            "updated_at": today(),
            "rights_scope": "personal-local",
            "reference_policy": "original-reference-images",
            "style_prompt": "style-prompt.md",
            "style_spec": "style-spec.json",
            "prompt_sha256": sha256_text_file(temporary / "style-prompt.md"),
            "fingerprint_sha256": fingerprint,
            "references": reference_records,
            "validation": {
                "style_review": None,
                "preview": None,
            },
        }
        atomic_json(temporary / PACK_NAME, pack)
        pack_dir.parent.mkdir(parents=True, exist_ok=True)
        temporary.replace(pack_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    update_catalog(root, pack)
    return {
        "ok": True,
        "action": "add",
        "slug": args.slug,
        "status": "candidate",
        "pack_dir": str(pack_dir),
        "reference_count": len(references),
    }


def get_pack(root: Path, slug: str) -> tuple[Path, dict[str, Any]]:
    pack_dir = safe_pack_dir(root, slug)
    pack_path = pack_dir / PACK_NAME
    if not pack_path.is_file():
        raise FileNotFoundError(f"style template not found: {slug}")
    return pack_dir, load_json(pack_path)


def validate_review(review: dict[str, Any]) -> None:
    if review.get("verdict") != "pass":
        raise ValueError("style review verdict must be pass")
    score = review.get("weighted_score")
    if not isinstance(score, (int, float)) or float(score) < 75:
        raise ValueError("style review weighted_score must be at least 75")
    dimensions = review.get("dimension_passes", [])
    if not isinstance(dimensions, list) or len(set(dimensions)) < 4:
        raise ValueError("style review must pass at least four dimensions")
    anchors = review.get("anchor_scores", [])
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("style review requires anchor_scores")
    for item in anchors:
        if not isinstance(item, dict) or not str(item.get("visible_evidence", "")).strip():
            raise ValueError("every style-review anchor needs visible_evidence")


def promote_pack(args: argparse.Namespace) -> dict[str, Any]:
    root = args.library.resolve()
    pack_dir, pack = get_pack(root, args.slug)
    review_path = args.review.resolve()
    review = load_json(review_path)
    validate_review(review)
    review_target = pack_dir / "style-review.json"
    copy_file(review_path, review_target)

    preview_relative = None
    if args.preview:
        preview_path = args.preview.resolve()
        if preview_path.suffix.lower() not in VALID_IMAGE_EXTENSIONS:
            raise ValueError("preview must be an image")
        preview_relative = f"preview{preview_path.suffix.lower()}"
        copy_file(preview_path, pack_dir / preview_relative)

    pack["status"] = "validated"
    pack["updated_at"] = today()
    validation = pack.get("validation")
    if not isinstance(validation, dict):
        validation = {}
    validation.update(
        {
            "style_review": "style-review.json",
            "weighted_score": review.get("weighted_score"),
            "dimension_passes": review.get("dimension_passes", []),
        }
    )
    if preview_relative is not None or "preview" not in validation:
        validation["preview"] = preview_relative
    pack["validation"] = validation
    atomic_json(pack_dir / PACK_NAME, pack)
    update_catalog(root, pack)
    return {
        "ok": True,
        "action": "promote",
        "slug": args.slug,
        "status": "validated",
        "weighted_score": review.get("weighted_score"),
    }


def validate_portability_review(review: dict[str, Any]) -> None:
    if review.get("schema_version") != "1.0.0":
        raise ValueError("portability review schema_version must be 1.0.0")
    if review.get("distinct_topic") is not True:
        raise ValueError("portability review must use a distinct topic")
    if not str(review.get("content_summary", "")).strip():
        raise ValueError("portability review requires content_summary")
    checks = review.get("checks", {})
    required_checks = {
        "topology_replanned",
        "icon_subjects_derived_from_new_content",
        "color_roles_reassigned",
        "no_source_content_carryover",
    }
    if not isinstance(checks, dict) or any(checks.get(key) is not True for key in required_checks):
        raise ValueError("portability review requires all cross-topic checks to pass")
    score = review.get("style_anchor_score")
    if not isinstance(score, (int, float)) or float(score) < 75:
        raise ValueError("portability review style_anchor_score must be at least 75")
    if not str(review.get("visible_evidence", "")).strip():
        raise ValueError("portability review requires visible_evidence")


def certify_portability(args: argparse.Namespace) -> dict[str, Any]:
    root = args.library.resolve()
    pack_dir, pack = get_pack(root, args.slug)
    review = load_json(args.review.resolve())
    validate_portability_review(review)
    copy_file(args.review.resolve(), pack_dir / "portability-review.json")
    pack["portability_status"] = "passed"
    pack["updated_at"] = today()
    pack.setdefault("validation", {})["portability_review"] = "portability-review.json"
    pack["validation"]["portability_score"] = review.get("style_anchor_score")
    atomic_json(pack_dir / PACK_NAME, pack)
    update_catalog(root, pack)
    return {
        "ok": True,
        "action": "certify",
        "slug": args.slug,
        "portability_status": "passed",
        "style_anchor_score": review.get("style_anchor_score"),
    }


def archive_pack(args: argparse.Namespace) -> dict[str, Any]:
    root = args.library.resolve()
    pack_dir, pack = get_pack(root, args.slug)
    pack["status"] = "archived"
    pack["updated_at"] = today()
    atomic_json(pack_dir / PACK_NAME, pack)
    update_catalog(root, pack)
    return {"ok": True, "action": "archive", "slug": args.slug, "status": "archived"}


def rename_pack(args: argparse.Namespace) -> dict[str, Any]:
    root = args.library.resolve()
    pack_dir, pack = get_pack(root, args.slug)
    old_slug = pack["slug"]

    if args.name:
        pack["name"] = args.name.strip()
    if args.alias:
        pack["aliases"] = sorted({value.strip() for value in args.alias if value.strip()})
    if args.add_alias:
        merged = set(pack.get("aliases", []))
        merged.update(value.strip() for value in args.add_alias if value.strip())
        pack["aliases"] = sorted(merged)

    new_slug = args.new_slug or old_slug
    if new_slug != old_slug:
        target_dir = safe_pack_dir(root, new_slug)
        if target_dir.exists():
            raise FileExistsError(f"style template already exists: {new_slug}")
        pack_dir.rename(target_dir)
        pack_dir = target_dir
        pack["slug"] = new_slug

    pack["updated_at"] = today()
    atomic_json(pack_dir / PACK_NAME, pack)
    if new_slug != old_slug:
        drop_from_catalog(root, old_slug)
    update_catalog(root, pack)
    return {
        "ok": True,
        "action": "rename",
        "slug": new_slug,
        "previous_slug": old_slug,
        "name": pack["name"],
        "aliases": pack.get("aliases", []),
    }


def refresh_pack(args: argparse.Namespace) -> dict[str, Any]:
    root = args.library.resolve()
    pack_dir, pack = get_pack(root, args.slug)
    prompt_path = pack_dir / str(pack.get("style_prompt", "style-prompt.md"))
    spec_path = pack_dir / str(pack.get("style_spec", "style-spec.json"))
    prompt = prompt_path.read_text(encoding="utf-8")
    style = load_json(spec_path)
    validate_prompt_asset(prompt, style)
    pack["prompt_sha256"] = sha256_text_file(prompt_path)
    pack["fingerprint_sha256"] = fingerprint_sha256(style)
    pack["updated_at"] = today()
    for item in pack.get("references", []):
        if isinstance(item, dict) and item.get("path"):
            reference = pack_dir / str(item["path"])
            if not reference.is_file():
                raise FileNotFoundError(f"missing reference: {reference}")
            item["sha256"] = sha256_file(reference)
    atomic_json(pack_dir / PACK_NAME, pack)
    update_catalog(root, pack)
    return {
        "ok": True,
        "action": "refresh",
        "slug": args.slug,
        "status": pack.get("status"),
    }


def cjk_characters(value: str) -> set[str]:
    return {
        character
        for character in value
        if "㐀" <= character <= "鿿" or "豈" <= character <= "﫿"
    }


def cjk_coverage(query: str, candidate: str) -> float:
    """Share of the query's CJK characters that also appear in the candidate.

    Chinese has no whitespace tokens, so substring matching alone misses the way
    users actually name a style out loud: "马卡龙方法图" never occurs inside
    "马卡龙套盒方法图". Character coverage recovers those near-misses.
    """
    needle_characters = cjk_characters(query)
    if not needle_characters:
        return 0.0
    return len(needle_characters & cjk_characters(candidate)) / len(needle_characters)


def score_entry(entry: dict[str, Any], query: str) -> int:
    needle = query.casefold().strip()
    if not needle:
        return 1
    name = str(entry.get("name", "")).casefold()
    slug = str(entry.get("slug", "")).casefold()
    aliases = [str(value).casefold() for value in entry.get("aliases", [])]
    tags = [str(value).casefold() for value in entry.get("tags", [])]
    best_for = [str(value).casefold() for value in entry.get("best_for", [])]
    labels = [name, slug, *aliases]
    score = 0
    if any(needle == value for value in labels):
        score += 100
    if any(needle in value for value in labels):
        score += 40
    score += 20 * sum(1 for value in tags if needle in value or value in needle)
    score += 10 * sum(1 for value in best_for if needle in value or value in needle)
    for token in needle.split():
        if any(token in value for value in labels):
            score += 8
        score += 3 * sum(1 for value in tags + best_for if token in value)

    best_coverage = max((cjk_coverage(needle, value) for value in labels), default=0.0)
    if best_coverage >= 0.9:
        score += 60
    elif best_coverage >= 0.7:
        score += 30
    elif best_coverage >= 0.5:
        score += 12
    return score


def search_catalog(args: argparse.Namespace) -> dict[str, Any]:
    root = args.library.resolve()
    catalog = ensure_library(root)
    results = []
    for entry in catalog.get("templates", []):
        if not isinstance(entry, dict):
            continue
        if not args.include_archived and entry.get("status") == "archived":
            continue
        score = score_entry(entry, args.query)
        if score > 0:
            results.append({**entry, "score": score})
    results.sort(
        key=lambda item: (
            -int(item["score"]),
            0 if item.get("portability_status") == "passed" else 1,
            0 if item.get("status") == "validated" else 1,
            str(item.get("slug", "")),
        )
    )
    return {
        "ok": True,
        "action": "search",
        "query": args.query,
        "count": len(results[: args.limit]),
        "results": results[: args.limit],
    }


def list_catalog(args: argparse.Namespace) -> dict[str, Any]:
    args.query = ""
    return search_catalog(args)


def show_pack(args: argparse.Namespace) -> dict[str, Any]:
    root = args.library.resolve()
    pack_dir, pack = get_pack(root, args.slug)
    resolved = dict(pack)
    resolved["pack_dir"] = str(pack_dir)
    resolved["style_prompt_path"] = str(pack_dir / str(pack["style_prompt"]))
    resolved["style_spec_path"] = str(pack_dir / str(pack["style_spec"]))
    resolved["reference_paths"] = [
        str(pack_dir / str(item["path"]))
        for item in pack.get("references", [])
        if isinstance(item, dict) and item.get("path")
    ]
    return {"ok": True, "action": "show", "template": resolved}


def validate_library(root: Path) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    try:
        catalog = ensure_library(root)
    except Exception as exc:
        return {"ok": False, "library": str(root), "failures": [str(exc)], "warnings": []}
    if catalog.get("schema_version") != "1.0.0":
        failures.append("catalog schema_version must be 1.0.0")
    if catalog.get("reference_policy") != "original-reference-images":
        failures.append("catalog reference_policy must be original-reference-images")
    templates = catalog.get("templates", [])
    if not isinstance(templates, list):
        failures.append("catalog templates must be a list")
        templates = []
    slugs: set[str] = set()
    fingerprints: dict[str, str] = {}
    for entry in templates:
        if not isinstance(entry, dict):
            failures.append("catalog entry must be an object")
            continue
        slug = str(entry.get("slug", ""))
        if slug in slugs:
            failures.append(f"duplicate catalog slug: {slug}")
        slugs.add(slug)
        try:
            pack_dir, pack = get_pack(root, slug)
        except Exception as exc:
            failures.append(str(exc))
            continue
        if pack.get("slug") != slug:
            failures.append(f"pack slug mismatch: {slug}")
        if pack.get("status") not in VALID_STATUSES:
            failures.append(f"pack {slug} has invalid status")
        portability_status = pack.get("portability_status", "untested")
        if portability_status not in VALID_PORTABILITY_STATUSES:
            failures.append(f"pack {slug} has invalid portability_status")
        if pack.get("rights_scope") != "personal-local":
            failures.append(f"pack {slug} rights_scope must be personal-local")
        if pack.get("reference_policy") != "original-reference-images":
            failures.append(f"pack {slug} must retain original reference images")
        prompt = pack_dir / str(pack.get("style_prompt", ""))
        spec = pack_dir / str(pack.get("style_spec", ""))
        if not prompt.is_file() or not spec.is_file():
            failures.append(f"pack {slug} is missing prompt or style spec")
            continue
        if sha256_text_file(prompt) != pack.get("prompt_sha256"):
            failures.append(f"pack {slug} prompt hash mismatch")
        try:
            style = load_json(spec)
            validate_prompt_asset(prompt.read_text(encoding="utf-8"), style)
            actual_fingerprint = fingerprint_sha256(style)
        except Exception as exc:
            failures.append(f"pack {slug} invalid reusable style asset: {exc}")
            continue
        if actual_fingerprint != pack.get("fingerprint_sha256"):
            failures.append(f"pack {slug} fingerprint hash mismatch")
        if pack.get("status") != "archived":
            previous = fingerprints.get(actual_fingerprint)
            if previous:
                failures.append(f"duplicate active fingerprint: {previous}, {slug}")
            fingerprints[actual_fingerprint] = slug
        references = pack.get("references", [])
        if not isinstance(references, list) or not references:
            failures.append(f"pack {slug} has no original reference images")
        else:
            for item in references:
                if not isinstance(item, dict):
                    failures.append(f"pack {slug} reference record must be an object")
                    continue
                reference = pack_dir / str(item.get("path", ""))
                try:
                    reference.resolve().relative_to(pack_dir.resolve())
                except ValueError:
                    failures.append(f"pack {slug} reference escapes pack directory")
                    continue
                if not reference.is_file():
                    failures.append(f"pack {slug} reference is missing: {reference.name}")
                elif sha256_file(reference) != item.get("sha256"):
                    failures.append(f"pack {slug} reference hash mismatch: {reference.name}")
        if compact_entry(pack) != entry:
            failures.append(f"catalog entry is stale for pack {slug}")
        if pack.get("status") == "validated":
            review_name = pack.get("validation", {}).get("style_review")
            if not review_name:
                failures.append(f"validated pack {slug} has no style review")
            else:
                try:
                    validate_review(load_json(pack_dir / str(review_name)))
                except Exception as exc:
                    failures.append(f"validated pack {slug} has invalid review: {exc}")
        elif pack.get("status") == "candidate":
            warnings.append(f"candidate pack has not passed a rendered style review: {slug}")
        if portability_status == "passed":
            review_name = pack.get("validation", {}).get("portability_review")
            if not review_name:
                failures.append(f"portable pack {slug} has no portability review")
            else:
                try:
                    validate_portability_review(load_json(pack_dir / str(review_name)))
                except Exception as exc:
                    failures.append(f"portable pack {slug} has invalid portability review: {exc}")
        elif pack.get("status") != "archived":
            warnings.append(f"pack has not passed a distinct-topic portability review: {slug}")
    return {
        "ok": not failures,
        "library": str(root),
        "template_count": len(templates),
        "failures": failures,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    default_root = Path(os.environ.get("FIGECHO_LIBRARY", DEFAULT_LIBRARY))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--library",
        type=Path,
        default=default_root,
        help="Style Library root. Defaults to FIGECHO_LIBRARY or package style-library.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.set_defaults(handler=lambda args: {
        "ok": True,
        "action": "init",
        "library": str(args.library.resolve()),
        "catalog": ensure_library(args.library.resolve()),
    })

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--job-dir", type=Path, required=True)
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--slug", required=True)
    add_parser.add_argument("--alias", action="append", default=[])
    add_parser.add_argument("--description", default="")
    add_parser.add_argument("--tag", action="append", default=[])
    add_parser.add_argument("--best-for", action="append", default=[])
    add_parser.add_argument("--not-for", action="append", default=[])
    add_parser.add_argument("--reference", action="append", default=[])
    add_parser.set_defaults(handler=add_pack)

    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("slug")
    promote_parser.add_argument("--review", type=Path, required=True)
    promote_parser.add_argument("--preview", type=Path)
    promote_parser.set_defaults(handler=promote_pack)

    certify_parser = subparsers.add_parser("certify")
    certify_parser.add_argument("slug")
    certify_parser.add_argument("--review", type=Path, required=True)
    certify_parser.set_defaults(handler=certify_portability)

    archive_parser = subparsers.add_parser("archive")
    archive_parser.add_argument("slug")
    archive_parser.set_defaults(handler=archive_pack)

    rename_parser = subparsers.add_parser("rename")
    rename_parser.add_argument("slug")
    rename_parser.add_argument("--name")
    rename_parser.add_argument("--new-slug")
    rename_parser.add_argument("--alias", action="append", default=[])
    rename_parser.add_argument("--add-alias", action="append", default=[])
    rename_parser.set_defaults(handler=rename_pack)

    refresh_parser = subparsers.add_parser("refresh")
    refresh_parser.add_argument("slug")
    refresh_parser.set_defaults(handler=refresh_pack)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--include-archived", action="store_true")
    search_parser.set_defaults(handler=search_catalog)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--limit", type=int, default=100)
    list_parser.add_argument("--include-archived", action="store_true")
    list_parser.set_defaults(handler=list_catalog)

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("slug")
    show_parser.set_defaults(handler=show_pack)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.set_defaults(
        handler=lambda args: validate_library(args.library.resolve())
    )
    return parser


def main() -> None:
    configure_stdout()
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.handler(args)
    except Exception as exc:
        result = {
            "ok": False,
            "action": args.command,
            "error": str(exc),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create a non-destructive FigEcho 0.4 job skeleton."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any], force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def write_text(path: Path, value: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def style_spec(references: list[str]) -> dict[str, Any]:
    dimensions = ["layout", "components", "connectors", "typography", "iconography"]
    weights = [24, 22, 20, 18, 16]
    anchors = []
    for index, (dimension, weight) in enumerate(zip(dimensions, weights), start=1):
        anchors.append(
            {
                "id": f"anchor-{index}",
                "dimension": dimension,
                "rule": f"TODO-specific-{dimension}-combination-rule",
                "evidence": [f"TODO-reference-region-for-{dimension}"],
                "weight": weight,
                "confidence": "unknown",
                "prompt_token": f"TODO-中文-{dimension}-提示词规则",
            }
        )
    return {
        "schema_version": "3.0.0",
        "references": [
            {"path": value, "role": "style_reference", "notes": ""}
            for value in references
        ]
        or [{"path": "TODO-reference-image", "role": "style_reference", "notes": ""}],
        "evidence_scope": {
            "reference_count": max(1, len(references)),
            "generalization": (
                "multi-reference-shared-patterns"
                if len(references) > 1
                else "single-reference-hypothesis"
            ),
        },
        "style_summary": "TODO-observable-style-summary-without-generic-adjectives",
        "signature_anchors": anchors,
        "visual_system": {
            key: {"observations": [], "transfer_rules": []}
            for key in (
                "layout",
                "components",
                "connectors",
                "palette",
                "typography",
                "iconography",
                "surface",
                "density",
            )
        },
        "transfer_boundary": {
            "layout_policy": "preserve-visual-rhythm-adapt-to-new-topology",
            "icon_subject_policy": "derive-from-new-content",
            "color_role_policy": "assign-by-new-content-hierarchy",
            "supporting_asset_policy": "allow-user-provided-or-content-required",
            "hard_constraints": [
                "preserve user-provided meaning and relationships",
                "keep all required text legible and accurate",
                "exclude source-specific content from new figures",
            ],
            "style_defaults": [
                "TODO-reference-derived-default-that-user-content-may-override"
            ],
        },
        "conditional_rules": [],
        "anti_generic": [
            "TODO-common-template-failure-and-positive-alternative",
            "TODO-second-template-failure-and-positive-alternative",
        ],
        "source_exclusions": [],
    }


def content_graph(title: str) -> dict[str, Any]:
    return {
        "schema_version": "2.0.0",
        "title": title,
        "summary": "TODO-content-summary",
        "nodes": [
            {
                "id": "primary_1",
                "label": "TODO-primary-label",
                "source_text": "TODO-source-trace",
                "role": "primary",
                "group_id": None,
                "details": [],
                "required": True,
            }
        ],
        "groups": [],
        "edges": [],
        "reading_order": ["primary_1"],
        "exact_text": [
            {"kind": "title", "value": title, "owner_id": None, "required": True}
        ],
        "content_policy": {
            "must_show": ["primary_1"],
            "may_summarize": [],
            "may_omit_from_canvas": [],
            "forbidden_inventions": [],
            "portable_exclusions": [title],
        },
    }


def visual_plan(title: str) -> dict[str, Any]:
    return {
        "schema_version": "2.0.0",
        "communication_frame": {
            "audience": "TODO-audience",
            "intended_use": "TODO-intended-use",
            "communication_goal": "TODO-what-the-viewer-must-understand",
            "core_narrative": "TODO-one-sentence-visual-story",
            "primary_takeaway": "TODO-focal-message",
            "reading_time": "TODO-scan-or-close-read",
        },
        "archetype": {
            "chosen": "TODO-diagram-archetype",
            "content_reason": "TODO-why-this-archetype-fits-the-new-content",
            "rejected_alternatives": [
                {
                    "archetype": "TODO-near-alternative",
                    "reason": "TODO-why-it-would-distort-the-content",
                }
            ],
        },
        "layout": {
            "canvas": {"aspect_ratio": "TODO", "title": title},
            "zones": [
                {
                    "id": "zone_1",
                    "purpose": "TODO",
                    "relative_area": "TODO",
                    "position": "TODO",
                },
                {
                    "id": "zone_2",
                    "purpose": "TODO",
                    "relative_area": "TODO",
                    "position": "TODO",
                },
            ],
            "reading_path": ["zone_1", "zone_2"],
            "focal_point": "TODO",
            "whitespace_strategy": "TODO",
            "density_budget": "TODO",
            "connector_routes": "TODO",
        },
        "content_mapping": [
            {
                "content_id": "primary_1",
                "visual_role": "TODO-title-card-icon-or-other",
                "zone_id": "zone_1",
                "label_strategy": "TODO",
            }
        ],
        "relation_encodings": [],
        "anchor_placements": [
            {
                "anchor_id": f"anchor-{index}",
                "placement": "TODO-placement-or-adaptation",
            }
            for index in range(1, 6)
        ],
        "compression": {
            "decisions": [
                {
                    "content_id": "primary_1",
                    "decision": "verbatim",
                    "reason": "TODO",
                }
            ],
            "verbatim_text": [title],
            "omitted_from_canvas": [],
        },
        "plan_risks": [
            {"risk": "TODO-primary-risk", "mitigation": "TODO-mitigation"}
        ],
    }


def job_plan(
    mode: str,
    delivery: str,
    prompt_language: str,
    references: list[str],
) -> dict[str, Any]:
    if mode == "extract":
        outputs = [{"path": "style-prompt.md", "role": "portable-prompt", "required": True}]
        if delivery == "analysis-and-prompt":
            outputs.insert(0, {"path": "style-report.md", "role": "style-report", "required": True})
        internal_artifacts = ["job-plan.json", "style-spec.json", "quality-report.md"]
        prompt_file = "style-prompt.md"
        style_prompt_file = "style-prompt.md"
        prompt_kind = "portable-style"
        renderer = "none"
        planning_status = "not-applicable"
        reference_binding = {"status": "not-applicable", "mechanism": "none", "images": []}
        style_source = None
    else:
        outputs = [
            {"path": "output/final.png", "role": "final-raster", "required": True},
            {"path": "prompt.md", "role": "generation-prompt", "required": True},
        ]
        internal_artifacts = [
            "job-plan.json",
            "style-spec.json",
            "style-prompt.md",
            "content-graph.json",
            "visual-plan.json",
            "generation-record.json",
            "render-check.json",
            "style-review.json",
            "quality-report.md",
        ]
        prompt_file = "prompt.md"
        style_prompt_file = "style-prompt.md"
        prompt_kind = "reference-conditioned-generation"
        renderer = "imagegen"
        planning_status = "pending"
        reference_binding = {
            "status": "bound" if references else "pending",
            "mechanism": "referenced_image_paths" if references else "none",
            "images": [
                {
                    "source": value,
                    "role": "style_reference",
                    "tool_slot": f"Image {index}",
                }
                for index, value in enumerate(references, start=1)
            ],
        }
        style_source = {
            "origin": "reference-image" if references else "TODO-style-origin",
            "library_search": {
                "performed": False,
                "queries": [],
                "candidates": [],
            },
            "template_slug": "",
            "user_confirmation": "",
        }
    return {
        "schema_version": "3.0.0",
        "mode": mode,
        "delivery_mode": delivery,
        "prompt_language": prompt_language,
        "prompt_kind": prompt_kind,
        "renderer": renderer,
        "planning_status": planning_status,
        "style_prompt_file": style_prompt_file,
        "prompt_file": prompt_file,
        "reference_binding": reference_binding,
        **({"style_source": style_source} if style_source else {}),
        "canvas": {
            "aspect_ratio": "TODO-aspect-ratio",
            "intended_use": "TODO-intended-use",
            "width": None,
            "height": None,
        },
        "outputs": outputs,
        "internal_artifacts": internal_artifacts,
        "quality_gates": [
            "style fingerprint is evidence-backed",
            "prompt mode boundary passes",
            "visual planning is complete when generation is requested",
            "required content is preserved",
            "four style-anchor dimensions are visible",
            "render check measured canvas, palette and density",
            "source-exclusive content is absent",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a FigEcho 0.4 job without overwriting files."
    )
    parser.add_argument("job_dir", help="Directory for the new job.")
    parser.add_argument("--mode", choices=("extract", "generate"), required=True)
    parser.add_argument(
        "--delivery",
        choices=("prompt-only", "analysis-and-prompt", "image-and-prompt"),
        help="User-facing delivery. Generate mode always returns both image and prompt.",
    )
    parser.add_argument("--prompt-language", choices=("zh-CN", "en"), default="zh-CN")
    parser.add_argument("--title", default="Untitled figure")
    parser.add_argument("--reference", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    delivery = args.delivery or ("prompt-only" if args.mode == "extract" else "image-and-prompt")
    valid_deliveries = {
        "extract": {"prompt-only", "analysis-and-prompt"},
        "generate": {"image-and-prompt"},
    }
    if delivery not in valid_deliveries[args.mode]:
        raise SystemExit(f"delivery {delivery!r} is not valid for mode {args.mode!r}")
    root = Path(args.job_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    write_json(
        root / "job-plan.json",
        job_plan(args.mode, delivery, args.prompt_language, args.reference),
        args.force,
    )
    write_json(root / "style-spec.json", style_spec(args.reference), args.force)

    style_prompt_text = (
        "【图像类型】\nTODO：技术图类型、画布和用途。\n\n"
        "【内容结构】\n1. <PRIMARY_MODULE_1>：<CONTENT_AND_RELATIONS>\n2. <PRIMARY_MODULE_2>：<CONTENT_AND_RELATIONS>\n\n"
        "【整体版式】\nTODO：宏观分区、阅读路径、网格、留白和密度。\n\n"
        "【组件语言】\nTODO：容器、标题条、卡片、描边和内边距。\n\n"
        "【连接线】\nTODO：线型、箭头、路由、分支与汇聚。\n\n"
        "【插图与图标风格】\nTODO：图标家族、轮廓、视角和图文搭配。\n\n"
        "【配色】\nTODO：背景、结构、文字/线条和强调色的语义角色、具体 #RRGGBB 色值、面积比例与对比关系。\n\n"
        "【字体层级】\nTODO：标题、模块、正文和注释层级。\n\n"
        "【视觉气质】\nTODO：整体视觉性格。\n\n"
        "【关键风格特征】\n1. TODO：写入风格锚点。\n\n"
        "【生成约束】\nTODO：文字、关系、裁切和无语义装饰约束。\n"
    )
    write_text(root / "style-prompt.md", style_prompt_text, args.force)

    if args.mode == "extract":
        if delivery == "analysis-and-prompt":
            write_text(
                root / "style-report.md",
                "# Style Report\n\nTODO: evidence, fingerprint and confidence.\n",
                args.force,
            )
    else:
        (root / "output").mkdir(exist_ok=True)
        write_json(root / "content-graph.json", content_graph(args.title), args.force)
        write_json(root / "visual-plan.json", visual_plan(args.title), args.force)
        write_text(
            root / "prompt.md",
            "输入图片角色：Image 1 是风格参考，只提供视觉语言，不是编辑对象。\n\n"
            + style_prompt_text,
            args.force,
        )

    write_text(
        root / "quality-report.md",
        "# Quality Report\n\n"
        f"- Created: {date.today().isoformat()}\n"
        f"- Mode: {args.mode}\n"
        "- Fingerprint: pending\n"
        "- Prompt boundary: pending\n"
        "- Visual planning: pending or not applicable\n"
        "- Content: pending or not applicable\n"
        "- Style-anchor score: pending\n"
        "- Missing evidence: OCR, provider-backed comparison, blind human review\n",
        args.force,
    )
    print(
        json.dumps(
            {"ok": True, "job_dir": str(root), "mode": args.mode, "delivery_mode": delivery},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate FigEcho 0.4 extraction and raster-generation jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


VALID_MODES = {"extract", "generate"}
BINDING_MECHANISMS = {
    "referenced_image_paths",
    "num_last_images_to_include",
    "reference_images_payload",
}
BUILT_IN_MECHANISMS = {"referenced_image_paths", "num_last_images_to_include"}
STYLE_ORIGINS = {"reference-image", "style-library", "original"}
VALID_DIMENSIONS = {
    "layout",
    "components",
    "connectors",
    "palette",
    "typography",
    "iconography",
    "surface",
    "density",
}
VALID_RELATIONS = {
    "sequence",
    "branch",
    "merge",
    "contains",
    "depends_on",
    "maps_to",
    "feedback",
    "compares_with",
    "annotates",
}
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
PORTABLE_FORBIDDEN = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"参考图",
        r"原图",
        r"这张图",
        r"reference image",
        r"source image",
        r"supplied image",
        r"style reference",
        r"image\s*1",
        r"visual language only",
        r"do not copy (the )?(reference|source)",
        r"不要复制(参考图|原图)",
        r"只提供视觉语言",
        r"仅用于提取视觉语言",
    )
]
GENERIC_TERMS = {
    "科技感",
    "高级",
    "专业",
    "简洁",
    "漂亮",
    "tech",
    "professional",
    "clean",
    "beautiful",
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PORTABLE_SECTIONS = {
    "zh-CN": [
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
    ],
    "en": [
        "[Image Type]",
        "[Content Structure]",
        "[Overall Layout]",
        "[Component Language]",
        "[Connectors]",
        "[Illustration and Icon Style]",
        "[Color Palette]",
        "[Typography Hierarchy]",
        "[Visual Character]",
        "[Signature Style Features]",
        "[Generation Constraints]",
    ],
}
HEX_COLOR_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")
ASPECT_RATIO_RE = re.compile(r"\b\d+(?:\.\d+)?:\d+(?:\.\d+)?\b")
SECTION_REQUIRED_GROUPS = {
    "zh-CN": {
        "【图像类型】": [
            r"(横向|纵向|方形|宽幅|画布)",
            r"(技术图|架构图|示意图|路线图|框架图|信息图)",
            r"(论文|报告|演示|汇报|出版|屏幕|印刷|使用场景)",
        ],
        "【内容结构】": [
            r"(模块|阶段|节点|分区|层级)",
            r"(关系|流程|顺序|分支|汇聚|包含|映射|反馈|对比|依赖)",
        ],
        "【整体版式】": [
            r"(从左到右|从上到下|阅读方向|阅读路径|主轴)",
            r"(网格|对齐)",
            r"(边距|留白|间距)",
            r"(密度|信息量)",
        ],
        "【组件语言】": [
            r"(矩形|圆角|容器|卡片|标题条|徽章)",
            r"(描边|边框)",
            r"(填充|底色)",
            r"(内边距|padding|间距)",
        ],
        "【连接线】": [
            r"(实线|虚线|点线|折线|曲线|直线)",
            r"(箭头|箭头端点|箭头形态)",
            r"(粗细|线宽|px|pt)",
            r"(颜色|#[0-9A-Fa-f]{6})",
            r"(路由|直角|端点|分支|汇聚|交叉)",
        ],
        "【插图与图标风格】": [
            r"(线性|扁平|线稿|面性|手绘|几何|图标家族)",
            r"(轮廓|描边|填充)",
            r"(视角|正视|侧视|等距)",
            r"(细节|抽象度|复杂度)",
        ],
        "【字体层级】": [
            r"(主标题|总标题)",
            r"(分区标题|模块标题)",
            r"(正文|说明文字)",
            r"(字体|无衬线|衬线)",
            r"(字号|比例|字重|行高|对齐)",
        ],
        "【视觉气质】": [
            r"(学术|工程|教育|编辑|技术|科研|专业)",
            r"(避免|克制|不使用|不要)",
        ],
        "【生成约束】": [
            r"(文字|拼写|伪文字)",
            r"(关系|连线|拓扑|箭头)",
            r"(裁切|越界|重叠|穿过)",
            r"(装饰|随机配色|无语义)",
        ],
    },
    "en": {
        "[Image Type]": [r"(landscape|portrait|square|canvas|wide)", r"(diagram|schematic|roadmap|framework|infographic)", r"(paper|report|presentation|publication|screen|print|use case)"],
        "[Content Structure]": [r"(module|stage|node|zone|hierarchy)", r"(relation|flow|sequence|branch|merge|contain|map|feedback|compare|depend)"],
        "[Overall Layout]": [r"(left.to.right|top.to.bottom|reading path|reading direction|axis)", r"(grid|align)", r"(margin|whitespace|spacing|gap)", r"(density|information load)"],
        "[Component Language]": [r"(rectangle|rounded|container|card|header|badge)", r"(stroke|border)", r"(fill|background)", r"(padding|spacing|gap)"],
        "[Connectors]": [r"(solid|dashed|dotted|orthogonal|curved|straight)", r"(arrow|arrowhead)", r"(width|thickness|px|pt)", r"(color|#[0-9A-Fa-f]{6})", r"(route|endpoint|branch|merge|crossing)"],
        "[Illustration and Icon Style]": [r"(line|flat|outline|filled|hand.drawn|geometric|icon family)", r"(outline|stroke|fill)", r"(view|front|side|isometric)", r"(detail|abstraction|complexity)"],
        "[Typography Hierarchy]": [r"(main title|figure title)", r"(section title|module title)", r"(body|description)", r"(font|sans.serif|serif)", r"(size|ratio|weight|line height|align)"],
        "[Visual Character]": [r"(academic|engineering|educational|editorial|technical|scientific|professional)", r"(avoid|restrained|do not|no )"],
        "[Generation Constraints]": [r"(text|spelling|gibberish)", r"(relation|connection|topology|arrow)", r"(crop|overflow|overlap|through)", r"(decoration|random color|semantic)"],
    },
}
ADAPTIVE_PROMPT_PATTERNS = {
    "zh-CN": {
        "layout": r"(根据|按照|按).{0,12}(新内容|内容关系|内容拓扑|节点关系).{0,18}(调整|适配|重算|选择)",
        "icons": r"(根据|按照|按).{0,12}(新内容|内容实体|对象|动作).{0,18}(选择|设计|替换|生成).{0,10}(图标|插图)",
        "colors": r"(根据|按照|按).{0,12}(新内容|内容层级|内容关系|语义层级).{0,18}(分配|映射|指定|选择).{0,10}(颜色|强调色|色彩)",
    },
    "en": {
        "layout": r"(adapt|adjust|choose|recompute).{0,24}(layout|zones|topology).{0,24}(new content|content relations|content topology)",
        "icons": r"(choose|derive|design|replace).{0,24}(icon|illustration).{0,24}(new content|content entities|objects|actions)",
        "colors": r"(assign|map|choose).{0,24}(color|accent).{0,24}(new content|content hierarchy|semantic hierarchy)",
    },
}
TEXT_BUDGET_RE = re.compile(
    r"(最多|不超过|至多|上限)\s*\d+|(at most|no more than|up to|max(?:imum)?)\s*\d+",
    re.IGNORECASE,
)
ICON_EXAMPLE_ENUMERATION_RE = re.compile(
    r"(例如|可使用|包括|比如|such as|for example|including)[^。\n]{0,240}(、|,)[^。\n]{0,240}(、|,)",
    re.IGNORECASE,
)
ABSOLUTE_OPTIONAL_MEDIA_BAN_RE = re.compile(
    r"(禁止|不得|严禁|不要使用|不使用|forbid|must not use|do not use|never use)"
    r"[^。\n]{0,160}(logo|照片|photo|photograph|3d|渐变|gradient|发光|glow|玻璃|glass|阴影|shadow|写实插画|realistic illustration)",
    re.IGNORECASE,
)
OPTIONAL_MEDIA_RE = re.compile(
    r"(logo|照片|photo|photograph|3d|渐变|gradient|发光|glow|玻璃|glass|阴影|shadow|写实插画|realistic illustration)",
    re.IGNORECASE,
)


def load_json(path: Path, failures: list[str]) -> dict[str, Any]:
    if not path.is_file():
        failures.append(f"missing file: {path.name}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"{path.name}: invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        failures.append(f"{path.name}: expected JSON object")
        return {}
    return payload


def read_text(path: Path, failures: list[str]) -> str:
    if not path.is_file() or path.stat().st_size == 0:
        failures.append(f"missing or empty file: {path.name}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        failures.append(f"{path.name}: cannot read UTF-8 text: {exc}")
        return ""


def contains_todo(value: Any) -> bool:
    if isinstance(value, str):
        normalized = value.strip().lower()
        return "todo" in normalized or normalized in {"tbd", "待定", "未填写"}
    if isinstance(value, list):
        return any(contains_todo(item) for item in value)
    if isinstance(value, dict):
        return any(contains_todo(item) for item in value.values())
    return False


def safe_relative(root: Path, raw: str) -> Path | None:
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def source_literals(style: dict[str, Any]) -> list[str]:
    result = []
    for raw in style.get("source_exclusions", []):
        value = str(raw).strip()
        if value.lower().startswith("literal:"):
            literal = value.split(":", 1)[1].strip()
            if literal:
                result.append(literal)
    return result


def visual_transfer_rules(style: dict[str, Any]) -> list[str]:
    result: list[str] = []
    visual_system = style.get("visual_system", {})
    if not isinstance(visual_system, dict):
        return result
    for dimension in sorted(VALID_DIMENSIONS):
        block = visual_system.get(dimension, {})
        if not isinstance(block, dict):
            continue
        for raw in block.get("transfer_rules", []):
            value = str(raw).strip()
            if value:
                result.append(value)
    return result


def section_body(text: str, sections: list[str], target: str) -> str:
    try:
        index = sections.index(target)
    except ValueError:
        return ""
    start = text.find(target)
    if start < 0:
        return ""
    start += len(target)
    following = [
        text.find(section, start)
        for section in sections[index + 1 :]
        if text.find(section, start) >= 0
    ]
    end = min(following) if following else len(text)
    return text[start:end].strip()


def validate_section_completeness(
    text: str,
    prompt_language: str,
    file_name: str,
    failures: list[str],
) -> None:
    sections = PORTABLE_SECTIONS.get(prompt_language, [])
    for section in sections:
        body = section_body(text, sections, section)
        if len(body) < 20:
            failures.append(f"{file_name} section {section} is too thin to be executable")
    for section, patterns in SECTION_REQUIRED_GROUPS.get(prompt_language, {}).items():
        body = section_body(text, sections, section)
        missing = [pattern for pattern in patterns if not re.search(pattern, body, re.IGNORECASE)]
        if missing:
            failures.append(
                f"{file_name} section {section} is missing {len(missing)} required constraint groups"
            )
    layout_section = "【整体版式】" if prompt_language == "zh-CN" else "[Overall Layout]"
    if not ASPECT_RATIO_RE.search(section_body(text, sections, layout_section)):
        failures.append(f"{file_name} layout section needs a concrete aspect ratio")
    palette_section = "【配色】" if prompt_language == "zh-CN" else "[Color Palette]"
    palette_body = section_body(text, sections, palette_section)
    colors = {value.upper() for value in HEX_COLOR_RE.findall(palette_body)}
    if len(colors) < 3:
        failures.append(
            f"{file_name} palette section needs at least three concrete #RRGGBB colors"
        )
    palette_roles = (
        r"(背景|文字|结构|主色|辅助色|强调色|描边|填充)"
        if prompt_language == "zh-CN"
        else r"(background|text|structure|primary|secondary|accent|stroke|fill)"
    )
    if len(re.findall(palette_roles, palette_body, re.IGNORECASE)) < 3:
        failures.append(
            f"{file_name} palette section must map colors to at least three semantic roles"
        )
    feature_section = (
        "【关键风格特征】"
        if prompt_language == "zh-CN"
        else "[Signature Style Features]"
    )
    feature_body = section_body(text, sections, feature_section)
    numbered = re.findall(r"(?m)^\s*\d+[\.、)]\s*\S+", feature_body)
    if not 5 <= len(numbered) <= 7:
        failures.append(
            f"{file_name} signature style section needs five to seven numbered features"
        )


def validate_portable_adaptability(
    text: str,
    prompt_language: str,
    file_name: str,
    content_exclusions: list[str],
    failures: list[str],
) -> None:
    sections = PORTABLE_SECTIONS.get(prompt_language, [])
    headings = {
        "layout": "【整体版式】" if prompt_language == "zh-CN" else "[Overall Layout]",
        "icons": "【插图与图标风格】" if prompt_language == "zh-CN" else "[Illustration and Icon Style]",
        "colors": "【配色】" if prompt_language == "zh-CN" else "[Color Palette]",
    }
    patterns = ADAPTIVE_PROMPT_PATTERNS.get(prompt_language, {})
    for key, heading in headings.items():
        body = section_body(text, sections, heading)
        if not re.search(patterns.get(key, r"$^"), body, re.IGNORECASE):
            failures.append(
                f"{file_name} section {heading} must adapt {key} to the new content"
            )
    icon_body = section_body(text, sections, headings["icons"])
    if ICON_EXAMPLE_ENUMERATION_RE.search(icon_body):
        failures.append(
            f"{file_name} icon section must not enumerate subject-specific icon examples"
        )
    match = ABSOLUTE_OPTIONAL_MEDIA_BAN_RE.search(text)
    if match:
        failures.append(
            f"{file_name} contains an absolute optional-media ban: {match.group(0)!r}"
        )
    lower = text.casefold()
    for raw in content_exclusions:
        value = str(raw).strip()
        if len(value) >= 2 and value.casefold() in lower:
            failures.append(
                f"{file_name} contains current-content-specific term: {value!r}"
            )


def validate_style(
    payload: dict[str, Any],
    failures: list[str],
    warnings: list[str],
    style_origin: str = "reference-image",
) -> tuple[list[dict[str, Any]], list[str]]:
    required = (
        "schema_version",
        "references",
        "evidence_scope",
        "style_summary",
        "signature_anchors",
        "visual_system",
        "transfer_boundary",
        "conditional_rules",
        "anti_generic",
        "source_exclusions",
    )
    for key in required:
        if key not in payload:
            failures.append(f"style-spec.json missing key: {key}")

    if payload.get("schema_version") != "3.0.0":
        failures.append("style-spec.json schema_version must be 3.0.0")

    references = payload.get("references", [])
    if not isinstance(references, list):
        failures.append("style-spec.json references must be a list")
        references = []
    elif not references and style_origin != "original":
        # Every reference-derived style has to name the image its anchors came
        # from; only the user-approved original branch is allowed to have none.
        failures.append("style-spec.json references must be a non-empty list")
    for index, item in enumerate(references):
        if not isinstance(item, dict) or not item.get("path"):
            failures.append(f"style-spec.json references[{index}] missing path")
        elif item.get("role") != "style_reference":
            failures.append(
                f"style-spec.json references[{index}] role must be style_reference"
            )

    scope = payload.get("evidence_scope", {})
    if isinstance(scope, dict):
        count = scope.get("reference_count")
        if isinstance(count, int) and count != len(references):
            failures.append(
                "style-spec.json evidence_scope.reference_count does not match references"
            )
        expected = (
            "multi-reference-shared-patterns"
            if len(references) > 1
            else "single-reference-hypothesis"
        )
        if not references and style_origin == "original":
            expected = "original-style-no-reference"
        if (references or style_origin == "original") and scope.get(
            "generalization"
        ) != expected:
            failures.append(
                f"style-spec.json evidence_scope.generalization must be {expected}"
            )
    else:
        failures.append("style-spec.json evidence_scope must be an object")

    summary = str(payload.get("style_summary", "")).strip()
    if len(summary) < 20:
        failures.append("style-spec.json style_summary is too short")

    anchors = payload.get("signature_anchors", [])
    if not isinstance(anchors, list) or not 5 <= len(anchors) <= 7:
        failures.append("style-spec.json requires 5-7 signature_anchors")
        anchors = []
    anchor_ids: list[str] = []
    dimensions: set[str] = set()
    total_weight = 0
    tokens: list[str] = []
    for index, anchor in enumerate(anchors):
        if not isinstance(anchor, dict):
            failures.append(
                f"style-spec.json signature_anchors[{index}] must be an object"
            )
            continue
        anchor_id = str(anchor.get("id", ""))
        if not ID_RE.match(anchor_id):
            failures.append(f"style-spec.json invalid anchor id: {anchor_id!r}")
        anchor_ids.append(anchor_id)
        dimension = anchor.get("dimension")
        if dimension not in VALID_DIMENSIONS:
            failures.append(
                f"style-spec.json anchor {anchor_id!r} has invalid dimension"
            )
        else:
            dimensions.add(str(dimension))
        rule = str(anchor.get("rule", "")).strip()
        if len(rule) < 12 or rule.lower() in GENERIC_TERMS:
            failures.append(
                f"style-spec.json anchor {anchor_id!r} rule is generic or too short"
            )
        evidence = anchor.get("evidence", [])
        if not isinstance(evidence, list) or not any(str(item).strip() for item in evidence):
            failures.append(
                f"style-spec.json anchor {anchor_id!r} requires observable evidence"
            )
        weight = anchor.get("weight")
        if not isinstance(weight, int) or not 1 <= weight <= 50:
            failures.append(
                f"style-spec.json anchor {anchor_id!r} has invalid weight"
            )
        else:
            total_weight += weight
        if anchor.get("confidence") not in {
            "low",
            "medium",
            "medium-high",
            "high",
        }:
            failures.append(
                f"style-spec.json anchor {anchor_id!r} has invalid confidence"
            )
        token = str(anchor.get("prompt_token", "")).strip()
        if len(token) < 12:
            failures.append(
                f"style-spec.json anchor {anchor_id!r} needs a specific prompt_token"
            )
        else:
            tokens.append(token)
    if len(anchor_ids) != len(set(anchor_ids)):
        failures.append("style-spec.json contains duplicate anchor ids")
    if len(dimensions) < 4:
        failures.append("style-spec.json anchors must cover at least four dimensions")
    if total_weight != 100:
        failures.append(
            f"style-spec.json anchor weights must sum to 100, got {total_weight}"
        )

    visual = payload.get("visual_system", {})
    if not isinstance(visual, dict):
        failures.append("style-spec.json visual_system must be an object")
    else:
        for dimension in VALID_DIMENSIONS:
            item = visual.get(dimension)
            if not isinstance(item, dict):
                failures.append(
                    f"style-spec.json visual_system.{dimension} must be an object"
                )
                continue
            observations = item.get("observations", [])
            rules = item.get("transfer_rules", [])
            if not isinstance(observations, list) or not observations:
                failures.append(
                    f"style-spec.json visual_system.{dimension}.observations is empty"
                )
            if not isinstance(rules, list) or not rules:
                failures.append(
                    f"style-spec.json visual_system.{dimension}.transfer_rules is empty"
                )
        palette_block = visual.get("palette", {})
        palette_text = json.dumps(palette_block, ensure_ascii=False)
        if len({value.upper() for value in HEX_COLOR_RE.findall(palette_text)}) < 3:
            failures.append(
                "style-spec.json visual_system.palette needs at least three concrete #RRGGBB colors"
            )

    boundary = payload.get("transfer_boundary", {})
    expected_boundary = {
        "layout_policy": "preserve-visual-rhythm-adapt-to-new-topology",
        "icon_subject_policy": "derive-from-new-content",
        "color_role_policy": "assign-by-new-content-hierarchy",
        "supporting_asset_policy": "allow-user-provided-or-content-required",
    }
    if not isinstance(boundary, dict):
        failures.append("style-spec.json transfer_boundary must be an object")
        boundary = {}
    for key, expected in expected_boundary.items():
        if boundary.get(key) != expected:
            failures.append(
                f"style-spec.json transfer_boundary.{key} must be {expected!r}"
            )
    hard_constraints = boundary.get("hard_constraints", [])
    if not isinstance(hard_constraints, list) or len(hard_constraints) < 3:
        failures.append(
            "style-spec.json transfer_boundary.hard_constraints requires at least three rules"
        )
    else:
        for item in hard_constraints:
            if OPTIONAL_MEDIA_RE.search(str(item)):
                failures.append(
                    "style-spec.json hard_constraints must not ban optional media or supporting assets"
                )
    if not isinstance(boundary.get("style_defaults"), list):
        failures.append("style-spec.json transfer_boundary.style_defaults must be a list")

    icon_block = visual.get("iconography", {}) if isinstance(visual, dict) else {}
    icon_rules = " ".join(
        str(item) for item in icon_block.get("transfer_rules", [])
    ) if isinstance(icon_block, dict) else ""
    if ICON_EXAMPLE_ENUMERATION_RE.search(icon_rules):
        failures.append(
            "style-spec.json iconography transfer rules must not enumerate icon subjects"
        )

    anti_generic = payload.get("anti_generic", [])
    if not isinstance(anti_generic, list) or len(anti_generic) < 2:
        failures.append("style-spec.json requires at least two anti_generic rules")

    if contains_todo(payload):
        failures.append("style-spec.json still contains TODO or placeholder values")
    if len(references) == 1 and any(
        anchor.get("confidence") == "high" for anchor in anchors if isinstance(anchor, dict)
    ):
        warnings.append(
            "single-reference author-level claims remain limited even when local anchors have high confidence"
        )
    return anchors, tokens


def validate_content(
    payload: dict[str, Any], failures: list[str]
) -> tuple[set[str], set[str], list[dict[str, Any]], dict[str, str]]:
    required_keys = (
        "schema_version",
        "title",
        "nodes",
        "groups",
        "edges",
        "reading_order",
        "exact_text",
        "content_policy",
    )
    for key in required_keys:
        if key not in payload:
            failures.append(f"content-graph.json missing key: {key}")

    nodes = payload.get("nodes", [])
    groups = payload.get("groups", [])
    if not isinstance(nodes, list) or not nodes:
        failures.append("content-graph.json nodes must be a non-empty list")
        nodes = []
    if not isinstance(groups, list):
        failures.append("content-graph.json groups must be a list")
        groups = []

    node_ids: list[str] = []
    labels: dict[str, str] = {}
    primary_ids: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            failures.append(f"content-graph.json nodes[{index}] must be an object")
            continue
        node_id = str(node.get("id", ""))
        if not ID_RE.match(node_id):
            failures.append(f"content-graph.json invalid node id: {node_id!r}")
        node_ids.append(node_id)
        label = str(node.get("label", "")).strip()
        source_text = str(node.get("source_text", "")).strip()
        if not label or not source_text:
            failures.append(
                f"content-graph.json node {node_id!r} needs label and source_text"
            )
        labels[node_id] = label
        if node.get("role") not in {"hero", "primary", "secondary", "annotation"}:
            failures.append(f"content-graph.json node {node_id!r} has invalid role")
        if node.get("required") and node.get("role") in {"hero", "primary"}:
            primary_ids.add(node_id)
    if len(node_ids) != len(set(node_ids)):
        failures.append("content-graph.json contains duplicate node ids")

    group_ids: list[str] = []
    for group in groups:
        if not isinstance(group, dict):
            failures.append("content-graph.json group must be an object")
            continue
        group_id = str(group.get("id", ""))
        if not ID_RE.match(group_id):
            failures.append(f"content-graph.json invalid group id: {group_id!r}")
        group_ids.append(group_id)
        labels[group_id] = str(group.get("label", "")).strip()
        if not str(group.get("semantic_role", "")).strip():
            failures.append(
                f"content-graph.json group {group_id!r} needs semantic_role"
            )
    if len(group_ids) != len(set(group_ids)):
        failures.append("content-graph.json contains duplicate group ids")

    node_set = set(node_ids)
    group_set = set(group_ids)
    all_ids = node_set | group_set
    for node in nodes:
        if (
            isinstance(node, dict)
            and node.get("group_id")
            and node.get("group_id") not in group_set
        ):
            failures.append(
                f"content-graph.json node {node.get('id')!r} references missing group"
            )
    for group in groups:
        if not isinstance(group, dict):
            continue
        for member in group.get("members", []):
            if member not in node_set:
                failures.append(
                    f"content-graph.json group {group.get('id')!r} references missing node {member!r}"
                )

    edges = payload.get("edges", [])
    if not isinstance(edges, list):
        failures.append("content-graph.json edges must be a list")
        edges = []
    required_edges: list[dict[str, Any]] = []
    edge_ids: list[str] = []
    for edge in edges:
        if not isinstance(edge, dict):
            failures.append("content-graph.json edge must be an object")
            continue
        edge_id = str(edge.get("id", ""))
        edge_ids.append(edge_id)
        if not ID_RE.match(edge_id):
            failures.append(f"content-graph.json invalid edge id: {edge_id!r}")
        if edge.get("source") not in all_ids or edge.get("target") not in all_ids:
            failures.append(
                f"content-graph.json edge {edge_id!r} has a missing endpoint"
            )
        if edge.get("relation") not in VALID_RELATIONS:
            failures.append(
                f"content-graph.json edge {edge_id!r} has invalid relation"
            )
        if edge.get("required"):
            required_edges.append(edge)
    if len(edge_ids) != len(set(edge_ids)):
        failures.append("content-graph.json contains duplicate edge ids")

    reading_order = payload.get("reading_order", [])
    if not isinstance(reading_order, list):
        failures.append("content-graph.json reading_order must be a list")
        reading_order = []
    for item in reading_order:
        if item not in all_ids:
            failures.append(
                f"content-graph.json reading_order references missing id: {item!r}"
            )
    missing_primary = sorted(primary_ids - set(reading_order))
    if missing_primary:
        failures.append(
            f"content-graph.json reading_order omits primary nodes: {missing_primary}"
        )

    exact = payload.get("exact_text", [])
    if not isinstance(exact, list):
        failures.append("content-graph.json exact_text must be a list")
    else:
        for index, item in enumerate(exact):
            if not isinstance(item, dict) or not str(item.get("value", "")).strip():
                failures.append(
                    f"content-graph.json exact_text[{index}] missing value"
                )
            elif item.get("owner_id") is not None and item.get("owner_id") not in all_ids:
                failures.append(
                    f"content-graph.json exact_text[{index}] has missing owner"
                )

    policy = payload.get("content_policy", {})
    if not isinstance(policy, dict):
        failures.append("content-graph.json content_policy must be an object")
    else:
        for key in (
            "must_show",
            "may_summarize",
            "may_omit_from_canvas",
            "forbidden_inventions",
            "portable_exclusions",
        ):
            if not isinstance(policy.get(key), list):
                failures.append(
                    f"content-graph.json content_policy.{key} must be a list"
                )
    if contains_todo(payload):
        failures.append("content-graph.json still contains TODO or placeholder values")
    return all_ids, primary_ids, required_edges, labels


def validate_visual_plan(
    payload: dict[str, Any],
    primary_ids: set[str],
    required_edges: list[dict[str, Any]],
    anchor_ids: set[str],
    failures: list[str],
) -> None:
    for key in (
        "schema_version",
        "communication_frame",
        "archetype",
        "layout",
        "content_mapping",
        "relation_encodings",
        "anchor_placements",
        "compression",
        "plan_risks",
    ):
        if key not in payload:
            failures.append(f"visual-plan.json missing key: {key}")

    frame = payload.get("communication_frame", {})
    for key in (
        "audience",
        "intended_use",
        "communication_goal",
        "core_narrative",
        "primary_takeaway",
        "reading_time",
    ):
        if not isinstance(frame, dict) or not str(frame.get(key, "")).strip():
            failures.append(f"visual-plan.json communication_frame.{key} is empty")

    archetype = payload.get("archetype", {})
    if not isinstance(archetype, dict):
        failures.append("visual-plan.json archetype must be an object")
    else:
        if not str(archetype.get("chosen", "")).strip():
            failures.append("visual-plan.json archetype.chosen is empty")
        if len(str(archetype.get("content_reason", "")).strip()) < 12:
            failures.append(
                "visual-plan.json archetype.content_reason is too short"
            )
        rejected = archetype.get("rejected_alternatives", [])
        if not isinstance(rejected, list) or not rejected:
            failures.append(
                "visual-plan.json needs at least one rejected alternative"
            )

    layout = payload.get("layout", {})
    if not isinstance(layout, dict):
        failures.append("visual-plan.json layout must be an object")
        layout = {}
    for key in (
        "canvas",
        "zones",
        "reading_path",
        "focal_point",
        "whitespace_strategy",
        "density_budget",
        "connector_routes",
    ):
        if key not in layout or layout.get(key) in ("", None, []):
            failures.append(f"visual-plan.json layout.{key} is empty")
    zones = layout.get("zones", [])
    if not isinstance(zones, list) or len(zones) < 2:
        failures.append("visual-plan.json layout.zones requires at least two zones")
        zone_ids: set[str] = set()
    else:
        zone_ids = {
            str(item.get("id"))
            for item in zones
            if isinstance(item, dict) and item.get("id")
        }
        if len(zone_ids) != len(zones):
            failures.append("visual-plan.json zones require unique ids")

    mappings = payload.get("content_mapping", [])
    mapped_ids: set[str] = set()
    if not isinstance(mappings, list):
        failures.append("visual-plan.json content_mapping must be a list")
    else:
        for item in mappings:
            if not isinstance(item, dict):
                continue
            content_id = str(item.get("content_id", ""))
            mapped_ids.add(content_id)
            if not str(item.get("visual_role", "")).strip():
                failures.append(
                    f"visual-plan.json mapping {content_id!r} needs visual_role"
                )
            if item.get("zone_id") not in zone_ids:
                failures.append(
                    f"visual-plan.json mapping {content_id!r} references missing zone"
                )
    missing_mappings = sorted(primary_ids - mapped_ids)
    if missing_mappings:
        failures.append(
            f"visual-plan.json missing primary content mappings: {missing_mappings}"
        )

    encodings = payload.get("relation_encodings", [])
    encoded_edges = {
        str(item.get("edge_id"))
        for item in encodings
        if isinstance(item, dict) and item.get("edge_id")
    }
    required_edge_ids = {str(edge.get("id")) for edge in required_edges}
    missing_edges = sorted(required_edge_ids - encoded_edges)
    if missing_edges:
        failures.append(
            f"visual-plan.json missing required relation encodings: {missing_edges}"
        )
    for item in encodings if isinstance(encodings, list) else []:
        if isinstance(item, dict) and not str(item.get("visual_encoding", "")).strip():
            failures.append(
                f"visual-plan.json relation {item.get('edge_id')!r} needs visual_encoding"
            )

    placements = payload.get("anchor_placements", [])
    placed_anchors = {
        str(item.get("anchor_id"))
        for item in placements
        if isinstance(item, dict) and str(item.get("placement", "")).strip()
    }
    missing_anchors = sorted(anchor_ids - placed_anchors)
    if missing_anchors:
        failures.append(
            f"visual-plan.json missing anchor placement or adaptation: {missing_anchors}"
        )

    compression = payload.get("compression", {})
    decisions = compression.get("decisions", []) if isinstance(compression, dict) else []
    decision_ids = {
        str(item.get("content_id"))
        for item in decisions
        if isinstance(item, dict) and item.get("content_id")
    }
    missing_decisions = sorted(primary_ids - decision_ids)
    if missing_decisions:
        failures.append(
            f"visual-plan.json missing primary compression decisions: {missing_decisions}"
        )

    risks = payload.get("plan_risks", [])
    if not isinstance(risks, list) or not risks:
        failures.append("visual-plan.json requires at least one plan risk")
    else:
        for item in risks:
            if not isinstance(item, dict) or not str(item.get("risk", "")).strip() or not str(
                item.get("mitigation", "")
            ).strip():
                failures.append(
                    "visual-plan.json each plan risk needs risk and mitigation"
                )
    if contains_todo(payload):
        failures.append("visual-plan.json still contains TODO or placeholder values")


def validate_style_source(payload: dict[str, Any], failures: list[str]) -> str:
    """Check where the style came from before any figure was generated.

    The pipeline used to assume a reference image always exists, so a request
    with only content and no reference silently fell through to an invented
    style. Generate mode must now record the branch it took, and the two
    branches that bypass a user-supplied reference must show the library search
    and the user's answer.
    """

    source = payload.get("style_source")
    if not isinstance(source, dict):
        failures.append(
            "generate mode requires job-plan.json style_source recording where the style came from"
        )
        return "reference-image"

    origin = source.get("origin")
    if origin not in STYLE_ORIGINS:
        failures.append(
            f"job-plan.json style_source.origin must be one of {sorted(STYLE_ORIGINS)}, got {origin!r}"
        )
        return "reference-image"

    if origin == "reference-image":
        return origin

    search = source.get("library_search")
    if not isinstance(search, dict) or search.get("performed") is not True:
        failures.append(
            f"style_source.origin {origin!r} requires library_search.performed = true"
        )
    else:
        queries = search.get("queries", [])
        if not isinstance(queries, list) or not any(
            isinstance(item, str) and item.strip() for item in queries
        ):
            failures.append(
                "style_source.library_search must record at least one search query"
            )
        if not isinstance(search.get("candidates"), list):
            failures.append(
                "style_source.library_search.candidates must be a list, empty when nothing matched"
            )

    if not str(source.get("user_confirmation", "")).strip():
        failures.append(
            f"style_source.origin {origin!r} requires user_confirmation quoting the user's answer"
        )

    if origin == "style-library" and not str(source.get("template_slug", "")).strip():
        failures.append("style_source.origin 'style-library' requires template_slug")

    return str(origin)


def validate_plan(
    root: Path,
    payload: dict[str, Any],
    failures: list[str],
    require_outputs: bool,
) -> tuple[str | None, str]:
    for key in (
        "schema_version",
        "mode",
        "delivery_mode",
        "prompt_language",
        "prompt_kind",
        "renderer",
        "planning_status",
        "style_prompt_file",
        "prompt_file",
        "reference_binding",
        "outputs",
        "internal_artifacts",
        "quality_gates",
    ):
        if key not in payload:
            failures.append(f"job-plan.json missing key: {key}")
    mode = payload.get("mode")
    if mode not in VALID_MODES:
        failures.append(f"job-plan.json invalid mode: {mode!r}")
        return None, "reference-image"

    if payload.get("schema_version") != "3.0.0":
        failures.append("job-plan.json schema_version must be 3.0.0")

    delivery = payload.get("delivery_mode")
    allowed_deliveries = {
        "extract": {"prompt-only", "analysis-and-prompt"},
        "generate": {"image-and-prompt"},
    }
    if delivery not in allowed_deliveries[mode]:
        failures.append(f"job-plan.json delivery_mode {delivery!r} is invalid for mode {mode!r}")
    if payload.get("prompt_language") not in PORTABLE_SECTIONS:
        failures.append("job-plan.json prompt_language must be zh-CN or en")

    expected = {
        "extract": ("portable-style", "none", "style-prompt.md", "not-applicable"),
        "generate": (
            "reference-conditioned-generation",
            "imagegen",
            "prompt.md",
            "complete",
        ),
    }[mode]
    actual = (
        payload.get("prompt_kind"),
        payload.get("renderer"),
        payload.get("prompt_file"),
        payload.get("planning_status"),
    )
    if actual != expected:
        failures.append(
            f"job-plan.json mode {mode!r} requires prompt_kind/renderer/prompt_file/planning_status {expected}, got {actual}"
        )

    if mode == "generate":
        # The layout is planned against a canvas, so the canvas must be a real
        # ratio before anything is submitted to an image backend.
        planned_aspect = str(payload.get("canvas", {}).get("aspect_ratio", "")).strip()
        if not ASPECT_RATIO_RE.fullmatch(planned_aspect):
            failures.append(
                "generate mode requires job-plan.json canvas.aspect_ratio as a concrete ratio such as 16:9"
            )

    if payload.get("style_prompt_file") != "style-prompt.md":
        failures.append("job-plan.json style_prompt_file must be style-prompt.md")

    style_origin = (
        validate_style_source(payload, failures) if mode == "generate" else "reference-image"
    )

    binding = payload.get("reference_binding", {})
    if not isinstance(binding, dict):
        failures.append("job-plan.json reference_binding must be an object")
        binding = {}
    status = binding.get("status")
    mechanism = binding.get("mechanism")
    images = binding.get("images", [])
    if mode == "extract":
        if (status, mechanism, images) != ("not-applicable", "none", []):
            failures.append(
                "extract mode requires reference_binding status not-applicable, mechanism none and no images"
            )
    elif style_origin == "original":
        # An original style has no image to bind, so the binding must be empty
        # rather than faked with a stand-in.
        if (status, mechanism, images) != ("not-applicable", "none", []):
            failures.append(
                "original style_source requires reference_binding status not-applicable, mechanism none and no images"
            )
    else:
        if status != "bound":
            failures.append("generate mode requires reference_binding.status = bound")
        if mechanism not in BINDING_MECHANISMS:
            failures.append(
                "generate mode requires an actual image binding mechanism"
            )
        if not isinstance(images, list) or not images:
            failures.append("generate mode requires at least one bound reference image")
            images = []
        if not any(
            isinstance(item, dict) and item.get("role") == "style_reference"
            for item in images
        ):
            failures.append("generate mode requires a bound style_reference image")
        for index, item in enumerate(images):
            if not isinstance(item, dict) or not str(item.get("source", "")).strip():
                failures.append(
                    f"job-plan.json reference_binding.images[{index}] missing source"
                )

    expected_outputs = {
        "prompt-only": {"style-prompt.md"},
        "analysis-and-prompt": {"style-report.md", "style-prompt.md"},
        "image-and-prompt": {"output/final.png", "prompt.md"},
    }

    outputs = payload.get("outputs", [])
    if not isinstance(outputs, list):
        failures.append("job-plan.json outputs must be a list")
        outputs = []
    for item in outputs:
        if not isinstance(item, dict) or not item.get("path"):
            failures.append("job-plan.json output item missing path")
            continue
        raw = str(item["path"])
        if Path(raw).suffix.lower() in {".svg", ".pptx"}:
            failures.append(f"job-plan.json contains retired vector output: {raw}")
        target = safe_relative(root, raw)
        if target is None:
            failures.append(f"job-plan.json output escapes job directory: {raw!r}")
            continue
        if require_outputs and item.get("required"):
            if not target.is_file() or target.stat().st_size == 0:
                failures.append(f"required output missing or empty: {raw}")
            elif target.suffix.lower() == ".png":
                try:
                    if target.read_bytes()[:8] != PNG_SIGNATURE:
                        failures.append(f"required raster is not a valid PNG: {raw}")
                except OSError as exc:
                    failures.append(f"cannot inspect required raster {raw}: {exc}")
    actual_output_paths = {
        str(item.get("path")) for item in outputs if isinstance(item, dict) and item.get("path")
    }
    if delivery in expected_outputs and actual_output_paths != expected_outputs[delivery]:
        failures.append(
            f"job-plan.json delivery_mode {delivery!r} requires user outputs {sorted(expected_outputs[delivery])}, got {sorted(actual_output_paths)}"
        )
    internal = payload.get("internal_artifacts", [])
    if not isinstance(internal, list):
        failures.append("job-plan.json internal_artifacts must be a list")
    elif any(not isinstance(item, str) or not item.strip() for item in internal):
        failures.append("job-plan.json internal_artifacts contains an invalid path")
    if contains_todo(payload):
        failures.append("job-plan.json still contains TODO or placeholder values")
    return str(mode), style_origin


def validate_portable_prompt(
    text: str,
    tokens: list[str],
    transfer_rules: list[str],
    literals: list[str],
    prompt_language: str,
    content_exclusions: list[str],
    failures: list[str],
) -> None:
    for pattern in PORTABLE_FORBIDDEN:
        match = pattern.search(text)
        if match:
            failures.append(
                f"style-prompt.md contains context-dependent reference language: {match.group(0)!r}"
            )
    lower = text.lower()
    for literal in literals:
        if literal.lower() in lower:
            failures.append(
                f"style-prompt.md contains source-specific literal: {literal!r}"
            )
    for token in tokens:
        if token.lower() not in lower:
            failures.append(
                f"style-prompt.md is missing anchor prompt_token: {token!r}"
            )
    for rule in transfer_rules:
        if rule.lower() not in lower:
            failures.append(
                f"style-prompt.md is missing visual transfer_rule: {rule!r}"
            )
    for section in PORTABLE_SECTIONS.get(prompt_language, []):
        if section not in text:
            failures.append(f"style-prompt.md is missing required section: {section}")
    validate_section_completeness(
        text, prompt_language, "style-prompt.md", failures
    )
    validate_portable_adaptability(
        text,
        prompt_language,
        "style-prompt.md",
        content_exclusions,
        failures,
    )
    if not re.search(r"<[A-Z][A-Z0-9_-]*>", text):
        failures.append("style-prompt.md needs at least one reusable content slot")
    if contains_todo(text):
        failures.append("style-prompt.md still contains TODO or placeholder values")


def validate_generation_prompt(
    text: str,
    tokens: list[str],
    transfer_rules: list[str],
    literals: list[str],
    content: dict[str, Any],
    visual: dict[str, Any],
    prompt_language: str,
    failures: list[str],
) -> None:
    lower = text.lower()
    if not (
        re.search(r"style reference", text, re.IGNORECASE)
        or "风格参考" in text
    ):
        failures.append("prompt.md must label the input image as a style reference")
    if not (
        re.search(r"visual language", text, re.IGNORECASE)
        or "视觉语言" in text
    ):
        failures.append("prompt.md must state the reference supplies visual language")
    if not (
        re.search(r"not an edit target", text, re.IGNORECASE)
        or "不是编辑对象" in text
    ):
        failures.append("prompt.md must say the reference is not an edit target")
    for token in tokens:
        if token.lower() not in lower:
            failures.append(f"prompt.md is missing anchor prompt_token: {token!r}")
    for rule in transfer_rules:
        if rule.lower() not in lower:
            failures.append(f"prompt.md is missing visual transfer_rule: {rule!r}")
    for section in PORTABLE_SECTIONS.get(prompt_language, []):
        if section not in text:
            failures.append(f"prompt.md is missing required section: {section}")
    validate_section_completeness(text, prompt_language, "prompt.md", failures)
    for literal in literals:
        if literal.lower() not in lower:
            failures.append(
                f"prompt.md must include source exclusion literal: {literal!r}"
            )
    for node in content.get("nodes", []):
        if isinstance(node, dict) and node.get("required"):
            label = str(node.get("label", "")).strip()
            if label and label.lower() not in lower:
                failures.append(f"prompt.md is missing required node label: {label!r}")
    for item in content.get("exact_text", []):
        if isinstance(item, dict) and item.get("required"):
            value = str(item.get("value", "")).strip()
            if value and value.lower() not in lower:
                failures.append(f"prompt.md is missing required exact text: {value!r}")
    chosen = str(visual.get("archetype", {}).get("chosen", "")).strip()
    if chosen and chosen.lower() not in lower:
        failures.append(f"prompt.md is missing chosen archetype: {chosen!r}")
    if not TEXT_BUDGET_RE.search(text):
        failures.append(
            "prompt.md must state a numeric text-load budget, e.g. how many short labels each zone carries at most"
        )
    if contains_todo(text):
        failures.append("prompt.md still contains TODO or placeholder values")


def validate_render_check(
    payload: dict[str, Any],
    plan: dict[str, Any],
    failures: list[str],
) -> None:
    """Objective render evidence produced by scripts/check_render.py.

    It never replaces the human style review; it only proves that canvas,
    palette and density were measured instead of asserted.
    """
    status = payload.get("status")
    if status not in {"ok", "warn", "fail"}:
        failures.append("render-check.json status must be ok, warn or fail")
    geometry = payload.get("geometry")
    if not isinstance(geometry, dict):
        failures.append("render-check.json requires a geometry block")
        return
    if status == "fail":
        failures.append(
            "render-check.json still reports a failing check; fix or regenerate before delivering"
        )
    if geometry.get("aspect_ok") is False:
        failures.append(
            "render-check.json reports the output canvas does not match the planned aspect ratio"
        )
    planned = str(plan.get("canvas", {}).get("aspect_ratio", "")).strip()
    if ASPECT_RATIO_RE.fullmatch(planned) and str(
        geometry.get("expected_aspect", "")
    ).strip() != planned:
        failures.append(
            f"render-check.json was not run against the planned aspect ratio {planned!r}"
        )
    palette = payload.get("palette", {})
    matches = palette.get("matches", []) if isinstance(palette, dict) else []
    if isinstance(matches, list) and matches:
        matched = sum(1 for item in matches if isinstance(item, dict) and item.get("matched"))
        if matched < min(3, len(matches)):
            failures.append(
                "render-check.json shows fewer than three style-spec colors in the output"
            )


def validate_generation_record(
    payload: dict[str, Any],
    prompt_text: str,
    plan: dict[str, Any],
    failures: list[str],
    style_origin: str = "reference-image",
) -> None:
    expected = {
        "schema_version": "1.0.0",
        "intent": "generate",
        "prompt_file": "prompt.md",
        "output_path": "output/final.png",
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            failures.append(f"generation-record.json {key} must be {value!r}")
    provider_mode = payload.get("provider_mode")
    if provider_mode not in {"built-in-imagegen", "external-image-api"}:
        failures.append(
            "generation-record.json provider_mode must be built-in-imagegen or external-image-api"
        )
    no_reference = style_origin == "original"
    if provider_mode == "external-image-api":
        provider = payload.get("provider")
        if not isinstance(provider, dict) or not str(provider.get("backend", "")).strip():
            failures.append(
                "external-image-api generation requires provider.backend in generation-record.json"
            )
        elif not str(provider.get("model", "")).strip():
            failures.append(
                "external-image-api generation requires provider.model in generation-record.json"
            )
        if not no_reference and payload.get("binding_mechanism") != "reference_images_payload":
            failures.append(
                "external-image-api generation requires binding_mechanism reference_images_payload"
            )
    elif provider_mode == "built-in-imagegen":
        if not no_reference and payload.get("binding_mechanism") not in BUILT_IN_MECHANISMS:
            failures.append(
                "built-in-imagegen generation requires binding_mechanism referenced_image_paths or num_last_images_to_include"
            )
    digest = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    if payload.get("prompt_sha256") != digest:
        failures.append(
            "generation-record.json prompt_sha256 does not match prompt.md"
        )
    binding = plan.get("reference_binding", {})
    if payload.get("binding_mechanism") != binding.get("mechanism"):
        failures.append(
            "generation-record.json binding_mechanism does not match job-plan.json"
        )
    recorded = payload.get("input_images", [])
    if not isinstance(recorded, list):
        failures.append("generation-record.json input_images must be a list")
        recorded = []
    elif not recorded and not no_reference:
        failures.append("generation-record.json requires input_images")
    required_sources = {
        str(item.get("source"))
        for item in binding.get("images", [])
        if isinstance(item, dict) and item.get("role") == "style_reference"
    }
    recorded_sources = {
        str(item.get("source"))
        for item in recorded
        if isinstance(item, dict) and item.get("role") == "style_reference"
    }
    if not required_sources.issubset(recorded_sources):
        failures.append(
            "generation-record.json does not record every bound style reference"
        )


def validate_style_review(
    payload: dict[str, Any],
    anchors: list[dict[str, Any]],
    failures: list[str],
) -> None:
    if payload.get("schema_version") != "1.0.0":
        failures.append("style-review.json schema_version must be 1.0.0")
    if payload.get("generated_image") != "output/final.png":
        failures.append("style-review.json generated_image must be output/final.png")
    if payload.get("review_basis") != "visible-generated-image":
        failures.append(
            "style-review.json review_basis must be visible-generated-image"
        )
    scores = payload.get("anchor_scores", [])
    if not isinstance(scores, list):
        failures.append("style-review.json anchor_scores must be a list")
        scores = []
    by_id: dict[str, dict[str, Any]] = {}
    for item in scores:
        if not isinstance(item, dict):
            failures.append("style-review.json anchor score must be an object")
            continue
        anchor_id = str(item.get("anchor_id", ""))
        by_id[anchor_id] = item
        score = item.get("score")
        if not isinstance(score, int) or not 0 <= score <= 4:
            failures.append(
                f"style-review.json anchor {anchor_id!r} score must be an integer 0-4"
            )
        if not str(item.get("visible_evidence", "")).strip():
            failures.append(
                f"style-review.json anchor {anchor_id!r} needs visible_evidence"
            )
        for key in ("mismatch", "next_action"):
            if key not in item or not isinstance(item.get(key), str):
                failures.append(
                    f"style-review.json anchor {anchor_id!r} needs string {key}"
                )
    anchor_ids = {str(anchor.get("id")) for anchor in anchors}
    missing = sorted(anchor_ids - set(by_id))
    if missing:
        failures.append(f"style-review.json missing anchor scores: {missing}")

    weighted = 0.0
    passing_dimensions: set[str] = set()
    for anchor in anchors:
        anchor_id = str(anchor.get("id"))
        item = by_id.get(anchor_id, {})
        score = item.get("score")
        if isinstance(score, int) and 0 <= score <= 4:
            weighted += score / 4 * int(anchor.get("weight", 0))
            if score >= 3:
                passing_dimensions.add(str(anchor.get("dimension")))
    reported = payload.get("weighted_score")
    if not isinstance(reported, (int, float)) or abs(float(reported) - weighted) > 0.01:
        failures.append(
            f"style-review.json weighted_score must equal {weighted:.2f}"
        )
    reported_dimensions = payload.get("dimension_passes", [])
    if set(reported_dimensions) != passing_dimensions:
        failures.append(
            "style-review.json dimension_passes does not match anchor scores"
        )
    expected_verdict = (
        "pass" if weighted >= 75 and len(passing_dimensions) >= 4 else "revise"
    )
    if payload.get("verdict") != expected_verdict:
        failures.append(
            f"style-review.json verdict must be {expected_verdict!r}"
        )
    if expected_verdict != "pass":
        failures.append(
            "generated figure does not pass the style-anchor completion threshold"
        )


def evaluate(job_dir: Path, require_outputs: bool = False) -> dict[str, Any]:
    root = job_dir.resolve()
    failures: list[str] = []
    warnings: list[str] = []
    plan = load_json(root / "job-plan.json", failures)
    style = load_json(root / "style-spec.json", failures)
    mode, style_origin = (
        validate_plan(root, plan, failures, require_outputs) if plan else (None, "reference-image")
    )
    anchors, tokens = (
        validate_style(style, failures, warnings, style_origin) if style else ([], [])
    )
    literals = source_literals(style)
    transfer_rules = visual_transfer_rules(style)

    if mode == "extract":
        prompt = read_text(root / "style-prompt.md", failures)
        validate_portable_prompt(
            prompt,
            tokens,
            transfer_rules,
            literals,
            str(plan.get("prompt_language", "zh-CN")),
            [],
            failures,
        )
    elif mode == "generate":
        content = load_json(root / "content-graph.json", failures)
        visual = load_json(root / "visual-plan.json", failures)
        _, primary_ids, required_edges, _ = (
            validate_content(content, failures) if content else (set(), set(), [], {})
        )
        validate_visual_plan(
            visual,
            primary_ids,
            required_edges,
            {
                str(anchor.get("id"))
                for anchor in anchors
                if isinstance(anchor, dict)
            },
            failures,
        )
        style_prompt = read_text(root / "style-prompt.md", failures)
        validate_portable_prompt(
            style_prompt,
            tokens,
            transfer_rules,
            literals,
            str(plan.get("prompt_language", "zh-CN")),
            [
                str(item)
                for item in content.get("content_policy", {}).get(
                    "portable_exclusions", []
                )
            ],
            failures,
        )
        prompt = read_text(root / "prompt.md", failures)
        validate_generation_prompt(
            prompt,
            tokens,
            transfer_rules,
            literals,
            content,
            visual,
            str(plan.get("prompt_language", "zh-CN")),
            failures,
        )
        if require_outputs:
            generation_record = load_json(root / "generation-record.json", failures)
            if generation_record:
                validate_generation_record(
                    generation_record, prompt, plan, failures, style_origin
                )
            render_check = load_json(root / "render-check.json", failures)
            if render_check:
                validate_render_check(render_check, plan, failures)
            style_review = load_json(root / "style-review.json", failures)
            if style_review:
                validate_style_review(style_review, anchors, failures)

    return {
        "ok": not failures,
        "job_dir": str(root),
        "mode": mode,
        "failures": failures,
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir")
    parser.add_argument("--require-outputs", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = evaluate(Path(args.job_dir), args.require_outputs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()

from __future__ import annotations

import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


validate_job = load_module("validate_job", ROOT / "scripts" / "validate_job.py")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def valid_style() -> dict:
    dims = ["layout", "components", "connectors", "typography", "iconography"]
    weights = [24, 22, 20, 18, 16]
    anchors = []
    for index, (dimension, weight) in enumerate(zip(dims, weights), start=1):
        anchors.append(
            {
                "id": f"anchor-{index}",
                "dimension": dimension,
                "rule": f"specific {dimension} relation with repeated proportions and hierarchy",
                "evidence": [f"reference-1 region {index} repeats this relation"],
                "weight": weight,
                "confidence": "medium",
                "prompt_token": f"第{index}项{dimension}风格组合规则",
            }
        )
    visual = {
        dimension: {
            "observations": [f"observable {dimension} fact"],
            "transfer_rules": [f"portable {dimension} rule"],
        }
        for dimension in validate_job.VALID_DIMENSIONS
    }
    visual["palette"] = {
        "observations": [
            "white background #FFFFFF, pale blue structure #EAF2FC, dark text #111111, yellow accent #F4C95D"
        ],
        "transfer_rules": [
            "背景使用 #FFFFFF，结构填充使用 #EAF2FC，正文与箭头使用 #111111，强调色使用 #F4C95D"
        ],
    }
    return {
        "schema_version": "3.0.0",
        "references": [
            {"path": "reference.png", "role": "style_reference", "notes": ""}
        ],
        "evidence_scope": {
            "reference_count": 1,
            "generalization": "single-reference-hypothesis",
        },
        "style_summary": "A specific nested technical infographic system with repeated visual hierarchy.",
        "signature_anchors": anchors,
        "visual_system": visual,
        "transfer_boundary": {
            "layout_policy": "preserve-visual-rhythm-adapt-to-new-topology",
            "icon_subject_policy": "derive-from-new-content",
            "color_role_policy": "assign-by-new-content-hierarchy",
            "supporting_asset_policy": "allow-user-provided-or-content-required",
            "hard_constraints": [
                "preserve content accuracy",
                "preserve relation topology",
                "prevent clipping and overlap",
            ],
            "style_defaults": [
                "prefer flat surfaces unless the new brief explicitly requires another treatment"
            ],
        },
        "conditional_rules": ["panel count adapts to new content topology"],
        "anti_generic": [
            "retain three-level container hierarchy instead of uniform cards",
            "combine linework and icon grammar rather than matching palette alone",
        ],
        "source_exclusions": ["literal:SourceBrand"],
    }


def valid_content() -> dict:
    return {
        "schema_version": "2.0.0",
        "title": "New workflow",
        "summary": "Input becomes output.",
        "nodes": [
            {
                "id": "input",
                "label": "Input",
                "source_text": "Input material",
                "role": "primary",
                "group_id": None,
                "details": [],
                "required": True,
            },
            {
                "id": "output",
                "label": "Output",
                "source_text": "Output result",
                "role": "primary",
                "group_id": None,
                "details": [],
                "required": True,
            },
        ],
        "groups": [],
        "edges": [
            {
                "id": "flow",
                "source": "input",
                "target": "output",
                "relation": "sequence",
                "label": "",
                "required": True,
            }
        ],
        "reading_order": ["input", "output"],
        "exact_text": [
            {
                "kind": "title",
                "value": "New workflow",
                "owner_id": None,
                "required": True,
            }
        ],
        "content_policy": {
            "must_show": ["input", "output", "flow"],
            "may_summarize": [],
            "may_omit_from_canvas": [],
            "forbidden_inventions": ["new stages"],
            "portable_exclusions": ["New workflow", "Input", "Output"],
        },
    }


def valid_visual_plan() -> dict:
    return {
        "schema_version": "2.0.0",
        "communication_frame": {
            "audience": "research readers",
            "intended_use": "paper overview",
            "communication_goal": "show how input becomes output",
            "core_narrative": "a two-step transformation",
            "primary_takeaway": "the direction of transformation",
            "reading_time": "quick scan",
        },
        "archetype": {
            "chosen": "two-stage sequence",
            "content_reason": "the content has one required directed transformation",
            "rejected_alternatives": [
                {
                    "archetype": "matrix",
                    "reason": "there are no two independent comparison axes",
                }
            ],
        },
        "layout": {
            "canvas": {"aspect_ratio": "16:9"},
            "zones": [
                {
                    "id": "left",
                    "purpose": "input",
                    "relative_area": "45%",
                    "position": "left",
                },
                {
                    "id": "right",
                    "purpose": "output",
                    "relative_area": "45%",
                    "position": "right",
                },
            ],
            "reading_path": ["left", "right"],
            "focal_point": "central transformation connector",
            "whitespace_strategy": "clear outer margin and center gap",
            "density_budget": "one node and one short label per zone",
            "connector_routes": "single horizontal arrow through the center gap",
        },
        "content_mapping": [
            {
                "content_id": "input",
                "visual_role": "left primary card",
                "zone_id": "left",
                "label_strategy": "verbatim",
            },
            {
                "content_id": "output",
                "visual_role": "right primary card",
                "zone_id": "right",
                "label_strategy": "verbatim",
            },
        ],
        "relation_encodings": [
            {
                "edge_id": "flow",
                "visual_encoding": "solid horizontal arrow",
            }
        ],
        "anchor_placements": [
            {
                "anchor_id": f"anchor-{index}",
                "placement": f"apply to zone {index % 2 + 1}",
            }
            for index in range(1, 6)
        ],
        "compression": {
            "decisions": [
                {"content_id": "input", "decision": "verbatim", "reason": "short"},
                {"content_id": "output", "decision": "verbatim", "reason": "short"},
            ],
            "verbatim_text": ["New workflow", "Input", "Output"],
            "omitted_from_canvas": [],
        },
        "plan_risks": [
            {
                "risk": "generic two-card result",
                "mitigation": "apply all five style anchors and their placements",
            }
        ],
    }


def extract_plan() -> dict:
    return {
        "schema_version": "3.0.0",
        "mode": "extract",
        "delivery_mode": "prompt-only",
        "prompt_language": "zh-CN",
        "prompt_kind": "portable-style",
        "renderer": "none",
        "planning_status": "not-applicable",
        "style_prompt_file": "style-prompt.md",
        "prompt_file": "style-prompt.md",
        "reference_binding": {
            "status": "not-applicable",
            "mechanism": "none",
            "images": [],
        },
        "canvas": {"aspect_ratio": "16:9", "intended_use": "reusable prompt"},
        "outputs": [{"path": "style-prompt.md", "role": "portable-prompt", "required": True}],
        "internal_artifacts": ["job-plan.json", "style-spec.json", "quality-report.md"],
        "quality_gates": ["fingerprint", "portable", "specific", "evidence"],
    }


def generate_plan() -> dict:
    return {
        "schema_version": "3.0.0",
        "mode": "generate",
        "delivery_mode": "image-and-prompt",
        "prompt_language": "zh-CN",
        "prompt_kind": "reference-conditioned-generation",
        "renderer": "imagegen",
        "planning_status": "complete",
        "style_prompt_file": "style-prompt.md",
        "prompt_file": "prompt.md",
        "reference_binding": {
            "status": "bound",
            "mechanism": "referenced_image_paths",
            "images": [
                {
                    "source": "reference.png",
                    "role": "style_reference",
                    "tool_slot": "Image 1",
                }
            ],
        },
        "style_source": {"origin": "reference-image"},
        "canvas": {"aspect_ratio": "16:9", "intended_use": "paper overview"},
        "outputs": [
            {"path": "output/final.png", "role": "final-raster", "required": True},
            {"path": "prompt.md", "role": "generation-prompt", "required": True},
        ],
        "internal_artifacts": [
            "job-plan.json",
            "style-spec.json",
            "style-prompt.md",
            "content-graph.json",
            "visual-plan.json",
            "generation-record.json",
            "style-review.json",
            "quality-report.md",
        ],
        "quality_gates": ["planning", "content", "style", "readability"],
    }


def portable_prompt(style: dict) -> str:
    tokens = [item["prompt_token"] for item in style["signature_anchors"]]
    rules = {
        key: value["transfer_rules"][0]
        for key, value in style["visual_system"].items()
    }
    return (
        "【图像类型】\n横向宽幅科研技术信息图，用于论文方法总览与屏幕阅读。\n\n"
        "【内容结构】\n使用 <PRIMARY_MODULES> 组织主模块和阶段节点，使用 <RELATIONSHIPS> 表达顺序、分支与汇聚关系。\n\n"
        f"【整体版式】\n- 使用 16:9 横向画布；根据新内容拓扑重算主区数量、宽度和阅读路径，所有模块遵循统一网格对齐。{tokens[0]}。{rules['layout']}；保留一致外边距、区间距和局部留白，并按{rules['density']}控制信息密度。\n\n"
        f"【组件语言】\n- 使用圆角矩形容器和贴顶标题条，{tokens[1]}。{rules['components']}。容器采用细描边、浅色填充和一致内边距。\n\n"
        f"【连接线】\n- {tokens[2]}。{rules['connectors']}。连接线使用 #111111、1.5px 实线和实心箭头，优先直角折线路由，分支与汇聚端点清楚并避免交叉。\n\n"
        f"【插图与图标风格】\n- {tokens[4]}。{rules['iconography']}。采用统一扁平线性图标家族，深色轮廓、正视视角和中等抽象细节；根据新内容中的实体、对象与动作选择图标题材。\n\n"
        f"【配色】\n背景使用 #FFFFFF，结构填充使用 #EAF2FC，正文与箭头使用 #111111，强调色使用 #F4C95D。颜色分别承担背景、结构、文字和强调角色；{rules['palette']}；根据新内容层级重新分配强调色的具体语义。\n\n"
        f"【字体层级】\n- {tokens[3]}。{rules['typography']}。主标题、模块标题和正文使用无衬线字体，按 1.8:1.3:1 的字号比例组织，使用不同字重、行高和左对齐形成层级。\n\n"
        f"【视觉气质】\n严谨、清晰、具有学术科研和教育型技术信息图气质。{rules['surface']}。保持克制，避免商业海报式装饰。\n\n"
        "【关键风格特征】\n1. 多层容器形成清楚的宏观与局部层级。\n2. 统一网格和紧凑间距保持高密度秩序。\n3. 细描边组件与直角箭头构成工程化连接语言。\n4. 低饱和结构色与深色文字形成稳定语义对比。\n5. 无衬线字体和线性图标维持一致学术气质。\n\n"
        "【生成约束】\n所有文字必须清晰且拼写正确；关系、拓扑和箭头方向必须准确；不得裁切、越界、重叠或让连线穿过文字；不添加无语义装饰和随机配色。\n"
    )


def generation_prompt(style: dict) -> str:
    tokens = [item["prompt_token"] for item in style["signature_anchors"]]
    rules = {
        key: value["transfer_rules"][0]
        for key, value in style["visual_system"].items()
    }
    return (
        "输入图片角色：Image 1 是风格参考，只提供视觉语言，不是编辑对象。\n\n"
        "【图像类型】\n横向宽幅科研技术信息图，用于论文方法总览和屏幕阅读。\n\n"
        "【内容结构】\nNew workflow 采用 two-stage sequence，Input 和 Output 是两个主模块节点，Input 通过 sequence 顺序关系流向 Output。每个主区最多 4 个短标签，单个标签最多 8 个字，说明文字只出现在侧注层。\n\n"
        f"【整体版式】\n- 使用 16:9 横向画布，从左到右形成阅读路径，所有模块遵循统一网格对齐。{tokens[0]}。{rules['layout']}；左区为 Input，右区为 Output，保留统一边距、间距和留白，并按{rules['density']}控制信息密度。\n\n"
        f"【组件语言】\n- 使用圆角矩形容器和贴顶标题条，{tokens[1]}。{rules['components']}。卡片采用细描边、浅色填充和一致内边距。\n\n"
        f"【连接线】\n- {tokens[2]}。{rules['connectors']}。连接线使用 #111111、1.5px 实线和实心箭头，以直角路由表达 Input 到 Output，端点清楚并避免交叉。\n\n"
        f"【插图与图标风格】\n- {tokens[4]}。{rules['iconography']}。采用统一扁平线性图标家族，深色轮廓、正视视角和中等抽象细节。\n\n"
        f"【配色】\n背景使用 #FFFFFF，结构填充使用 #EAF2FC，正文与箭头使用 #111111，强调色使用 #F4C95D。颜色分别承担背景、结构、文字和强调角色；{rules['palette']}。\n\n"
        f"【字体层级】\n- {tokens[3]}。{rules['typography']}。主标题、模块标题和正文使用无衬线字体，按 1.8:1.3:1 的字号比例组织，使用不同字重、行高和左对齐形成层级。\n\n"
        f"【视觉气质】\n严谨、清晰、具有学术科研和教育型技术信息图气质。{rules['surface']}。保持克制，避免商业海报式装饰。\n\n"
        "【关键风格特征】\n1. 多层容器形成清楚的宏观与局部层级。\n2. 统一网格和紧凑间距保持高密度秩序。\n3. 细描边组件与直角箭头构成工程化连接语言。\n4. 低饱和结构色与深色文字形成稳定语义对比。\n5. 无衬线字体和线性图标维持一致学术气质。\n\n"
        "【生成约束】\n排除 SourceBrand，不新增 stages；所有文字必须清晰且拼写正确；关系、拓扑和箭头方向必须准确；不得裁切、越界、重叠或让连线穿过文字；不添加无语义装饰和随机配色。\n"
    )


def create_extract_job(root: Path) -> None:
    style = valid_style()
    write_json(root / "job-plan.json", extract_plan())
    write_json(root / "style-spec.json", style)
    (root / "style-prompt.md").write_text(portable_prompt(style), encoding="utf-8")
    (root / "quality-report.md").write_text("Portable prompt passed.", encoding="utf-8")


def valid_render_check() -> dict:
    return {
        "image": "output/final.png",
        "status": "ok",
        "geometry": {
            "width": 2560,
            "height": 1440,
            "aspect_ratio": 1.7778,
            "nearest_named_aspect": "16:9",
            "expected_aspect": "16:9",
            "aspect_ok": True,
        },
        "palette": {
            "matches": [
                {"expected": "#111111", "delta": 1.2, "coverage": 0.05, "matched": True},
                {"expected": "#f5f5f0", "delta": 0.8, "coverage": 0.6, "matched": True},
                {"expected": "#2f6fb0", "delta": 4.1, "coverage": 0.02, "matched": True},
            ]
        },
        "density": {"background_share": 0.6, "edge_density": 0.12, "border_ink_share": 0.01},
        "findings": [],
    }


def create_generate_job(root: Path) -> None:
    style = valid_style()
    write_json(root / "job-plan.json", generate_plan())
    write_json(root / "style-spec.json", style)
    write_json(root / "content-graph.json", valid_content())
    write_json(root / "visual-plan.json", valid_visual_plan())
    style_prompt = portable_prompt(style)
    prompt = generation_prompt(style)
    (root / "style-prompt.md").write_text(style_prompt, encoding="utf-8")
    (root / "prompt.md").write_text(prompt, encoding="utf-8")
    (root / "quality-report.md").write_text("Raster self-review.", encoding="utf-8")
    write_json(
        root / "generation-record.json",
        {
            "schema_version": "1.0.0",
            "provider_mode": "built-in-imagegen",
            "intent": "generate",
            "prompt_file": "prompt.md",
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "binding_mechanism": "referenced_image_paths",
            "input_images": [
                {"source": "reference.png", "role": "style_reference"}
            ],
            "output_path": "output/final.png",
        },
    )
    write_json(root / "render-check.json", valid_render_check())
    write_json(
        root / "style-review.json",
        {
            "schema_version": "1.0.0",
            "generated_image": "output/final.png",
            "review_basis": "visible-generated-image",
            "anchor_scores": [
                {
                    "anchor_id": f"anchor-{index}",
                    "score": 4,
                    "visible_evidence": f"Visible evidence for anchor {index}",
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
        },
    )
    (root / "output").mkdir()
    (root / "output" / "final.png").write_bytes(
        validate_job.PNG_SIGNATURE + b"fixture"
    )


class JobValidationTests(unittest.TestCase):
    def test_valid_extract_job_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_extract_job(root)
            result = validate_job.evaluate(root, require_outputs=True)
            self.assertTrue(result["ok"], result)

    def test_extract_prompt_rejects_reference_language(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_extract_job(root)
            with (root / "style-prompt.md").open("a", encoding="utf-8") as handle:
                handle.write("参考图仅用于提取视觉语言。")
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("context-dependent" in item for item in result["failures"])
            )

    def test_extract_prompt_rejects_source_literal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_extract_job(root)
            with (root / "style-prompt.md").open("a", encoding="utf-8") as handle:
                handle.write(" SourceBrand")
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("source-specific literal" in item for item in result["failures"])
            )

    def test_extract_prompt_requires_full_modular_structure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_extract_job(root)
            text = (root / "style-prompt.md").read_text(encoding="utf-8")
            (root / "style-prompt.md").write_text(
                text.replace("【字体层级】", "字体层级"), encoding="utf-8"
            )
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("required section" in item for item in result["failures"]))

    def test_extract_prompt_requires_concrete_palette_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_extract_job(root)
            text = (root / "style-prompt.md").read_text(encoding="utf-8")
            text = text.replace("#FFFFFF", "纯白").replace("#EAF2FC", "浅蓝")
            (root / "style-prompt.md").write_text(text, encoding="utf-8")
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("concrete #RRGGBB colors" in item for item in result["failures"])
            )

    def test_extract_prompt_rejects_topic_icon_enumeration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_extract_job(root)
            text = (root / "style-prompt.md").read_text(encoding="utf-8")
            text = text.replace(
                "根据新内容中的实体、对象与动作选择图标题材。",
                "图标可使用数据库、地图、矿石、海浪、盾牌等对象。",
            )
            (root / "style-prompt.md").write_text(text, encoding="utf-8")
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("icon section" in item for item in result["failures"]))

    def test_extract_prompt_rejects_fixed_business_color_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            text = (root / "style-prompt.md").read_text(encoding="utf-8")
            text = text.replace(
                "根据新内容层级重新分配强调色的具体语义。",
                "强调色固定用于 Input 和 Output。",
            )
            (root / "style-prompt.md").write_text(text, encoding="utf-8")
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("current-content" in item for item in result["failures"])
            )

    def test_extract_prompt_rejects_absolute_optional_media_bans(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_extract_job(root)
            with (root / "style-prompt.md").open("a", encoding="utf-8") as handle:
                handle.write("\n禁止使用 Logo、照片、3D、渐变与阴影。")
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("optional-media ban" in item for item in result["failures"]))

    def test_extract_prompt_allows_conditional_supporting_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_extract_job(root)
            with (root / "style-prompt.md").open("a", encoding="utf-8") as handle:
                handle.write(
                    "\n用户提供或内容必需的 Logo、照片可作为辅助素材插入，并统一边框与色调。"
                )
            result = validate_job.evaluate(root)
            self.assertTrue(result["ok"], result)

    def test_style_spec_requires_transfer_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_extract_job(root)
            style = valid_style()
            del style["transfer_boundary"]
            write_json(root / "style-spec.json", style)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("transfer_boundary" in item for item in result["failures"]))

    def test_style_spec_requires_concrete_palette_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_extract_job(root)
            style = valid_style()
            style["visual_system"]["palette"] = {
                "observations": ["white, pale blue and dark text"],
                "transfer_rules": ["use a low saturation palette"],
            }
            write_json(root / "style-spec.json", style)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("visual_system.palette" in item for item in result["failures"])
            )

    def test_prompt_only_exposes_only_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_extract_job(root)
            plan = extract_plan()
            plan["outputs"].append(
                {"path": "style-spec.json", "role": "style-spec", "required": True}
            )
            write_json(root / "job-plan.json", plan)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("requires user outputs" in item for item in result["failures"]))

    def test_valid_generate_job_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            result = validate_job.evaluate(root, require_outputs=True)
            self.assertTrue(result["ok"], result)

    def test_generate_always_delivers_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = generate_plan()
            plan["outputs"] = [plan["outputs"][0]]
            write_json(root / "job-plan.json", plan)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("requires user outputs" in item for item in result["failures"]))

    def test_generate_requires_style_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = generate_plan()
            plan.pop("style_source")
            write_json(root / "job-plan.json", plan)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("style_source" in item for item in result["failures"]), result
            )

    def test_library_origin_requires_search_and_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = generate_plan()
            plan["style_source"] = {"origin": "style-library"}
            write_json(root / "job-plan.json", plan)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            joined = " ".join(result["failures"])
            self.assertIn("library_search.performed", joined)
            self.assertIn("user_confirmation", joined)
            self.assertIn("template_slug", joined)

    def test_original_origin_requires_search_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = generate_plan()
            plan["style_source"] = {
                "origin": "original",
                "library_search": {"performed": False, "queries": [], "candidates": []},
                "user_confirmation": "",
            }
            plan["reference_binding"] = {
                "status": "not-applicable",
                "mechanism": "none",
                "images": [],
            }
            write_json(root / "job-plan.json", plan)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            joined = " ".join(result["failures"])
            self.assertIn("library_search.performed", joined)
            self.assertIn("user_confirmation", joined)

    def test_confirmed_original_style_passes_without_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = generate_plan()
            plan["style_source"] = {
                "origin": "original",
                "library_search": {
                    "performed": True,
                    "queries": ["产品分层架构图"],
                    "candidates": [],
                },
                "user_confirmation": "用户答复：库里没有合适的，走原创新风格。",
            }
            plan["reference_binding"] = {
                "status": "not-applicable",
                "mechanism": "none",
                "images": [],
            }
            write_json(root / "job-plan.json", plan)
            style = json.loads((root / "style-spec.json").read_text(encoding="utf-8"))
            style["references"] = []
            style["evidence_scope"] = {
                "reference_count": 0,
                "generalization": "original-style-no-reference",
            }
            write_json(root / "style-spec.json", style)
            record = json.loads(
                (root / "generation-record.json").read_text(encoding="utf-8")
            )
            record["binding_mechanism"] = "none"
            record["input_images"] = []
            write_json(root / "generation-record.json", record)
            result = validate_job.evaluate(root, require_outputs=True)
            self.assertTrue(result["ok"], result)

    def test_generate_requires_actual_reference_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = generate_plan()
            plan["reference_binding"] = {
                "status": "pending",
                "mechanism": "none",
                "images": [],
            }
            write_json(root / "job-plan.json", plan)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("actual image binding" in item for item in result["failures"]))

    def test_generate_prompt_requires_full_modular_structure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            text = (root / "prompt.md").read_text(encoding="utf-8")
            (root / "prompt.md").write_text(
                text.replace("【组件语言】", "组件语言"), encoding="utf-8"
            )
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("required section" in item for item in result["failures"]))

    def test_generate_requires_canonical_style_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            (root / "style-prompt.md").unlink()
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("style-prompt.md" in item for item in result["failures"]))

    def test_generate_prompt_requires_every_visual_transfer_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            text = (root / "prompt.md").read_text(encoding="utf-8")
            (root / "prompt.md").write_text(
                text.replace("portable surface rule", "surface styling"),
                encoding="utf-8",
            )
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("visual transfer_rule" in item for item in result["failures"])
            )

    def test_generate_requires_concrete_canvas_aspect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = generate_plan()
            plan["canvas"]["aspect_ratio"] = "TODO-aspect-ratio"
            write_json(root / "job-plan.json", plan)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("canvas.aspect_ratio" in item for item in result["failures"])
            )

    def test_generate_prompt_requires_text_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            text = (root / "prompt.md").read_text(encoding="utf-8")
            (root / "prompt.md").write_text(
                text.replace(
                    "每个主区最多 4 个短标签，单个标签最多 8 个字，说明文字只出现在侧注层。",
                    "标签保持简短。",
                ),
                encoding="utf-8",
            )
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("text-load budget" in item for item in result["failures"])
            )

    def test_external_provider_mode_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = generate_plan()
            plan["reference_binding"]["mechanism"] = "reference_images_payload"
            write_json(root / "job-plan.json", plan)
            record = json.loads(
                (root / "generation-record.json").read_text(encoding="utf-8")
            )
            record["provider_mode"] = "external-image-api"
            record["binding_mechanism"] = "reference_images_payload"
            record["provider"] = {"backend": "labnana/openai", "model": "gpt-image-2"}
            write_json(root / "generation-record.json", record)
            result = validate_job.evaluate(root, require_outputs=True)
            self.assertTrue(result["ok"], result)

    def test_external_provider_mode_requires_backend_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = generate_plan()
            plan["reference_binding"]["mechanism"] = "reference_images_payload"
            write_json(root / "job-plan.json", plan)
            record = json.loads(
                (root / "generation-record.json").read_text(encoding="utf-8")
            )
            record["provider_mode"] = "external-image-api"
            record["binding_mechanism"] = "reference_images_payload"
            write_json(root / "generation-record.json", record)
            result = validate_job.evaluate(root, require_outputs=True)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("provider.backend" in item for item in result["failures"])
            )

    def test_render_check_is_required_for_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            (root / "render-check.json").unlink()
            result = validate_job.evaluate(root, require_outputs=True)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("render-check.json" in item for item in result["failures"])
            )

    def test_render_check_aspect_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            check = valid_render_check()
            check["geometry"]["aspect_ok"] = False
            check["status"] = "fail"
            write_json(root / "render-check.json", check)
            result = validate_job.evaluate(root, require_outputs=True)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("aspect ratio" in item for item in result["failures"])
            )

    def test_render_check_must_use_planned_aspect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            check = valid_render_check()
            check["geometry"]["expected_aspect"] = "auto"
            write_json(root / "render-check.json", check)
            result = validate_job.evaluate(root, require_outputs=True)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("planned aspect ratio" in item for item in result["failures"])
            )

    def test_generation_record_must_match_actual_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            with (root / "prompt.md").open("a", encoding="utf-8") as handle:
                handle.write("\n补充约束。")
            result = validate_job.evaluate(root, require_outputs=True)
            self.assertFalse(result["ok"])
            self.assertTrue(any("prompt_sha256" in item for item in result["failures"]))

    def test_style_review_requires_visible_anchor_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            review = json.loads((root / "style-review.json").read_text(encoding="utf-8"))
            review["anchor_scores"][0]["visible_evidence"] = ""
            write_json(root / "style-review.json", review)
            result = validate_job.evaluate(root, require_outputs=True)
            self.assertFalse(result["ok"])
            self.assertTrue(any("visible_evidence" in item for item in result["failures"]))

    def test_generate_requires_complete_visual_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = valid_visual_plan()
            plan["content_mapping"] = plan["content_mapping"][:1]
            write_json(root / "visual-plan.json", plan)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("missing primary content mappings" in item for item in result["failures"])
            )

    def test_generate_requires_relation_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = valid_visual_plan()
            plan["relation_encodings"] = []
            write_json(root / "visual-plan.json", plan)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("missing required relation encodings" in item for item in result["failures"])
            )

    def test_generate_requires_anchor_placement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = valid_visual_plan()
            plan["anchor_placements"] = plan["anchor_placements"][:-1]
            write_json(root / "visual-plan.json", plan)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("missing anchor placement" in item for item in result["failures"])
            )

    def test_vector_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_generate_job(root)
            plan = generate_plan()
            plan["outputs"].append(
                {"path": "output/final.svg", "role": "final-raster", "required": False}
            )
            write_json(root / "job-plan.json", plan)
            result = validate_job.evaluate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("retired vector output" in item for item in result["failures"])
            )


if __name__ == "__main__":
    unittest.main()

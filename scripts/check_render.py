#!/usr/bin/env python3
"""Objective post-generation checks for a FigEcho raster output.

This measures what a script can actually measure: canvas geometry, palette
fidelity against style-spec.json, whitespace budget, visual busyness and
edge-crop risk. It does NOT judge content accuracy, text correctness or
archetype fidelity — those still require looking at the image and writing
style-review.json.

    python scripts/check_render.py ./job/output/final.png \
        --style-spec ./job/style-spec.json \
        --expect-aspect 16:9 \
        --report ./job/render-check.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HEX_RE = re.compile(r"#([0-9a-fA-F]{6})\b")

# Thresholds are advisory. They flag "look here", never "this is a failure".
MIN_LONG_EDGE = 1280
ASPECT_TOLERANCE = 0.03
PALETTE_MATCH_DELTA = 18.0  # perceptual-ish distance in Lab
PALETTE_MIN_COVERAGE = 0.0015  # accents are small by design; 0.15% is enough
WHITESPACE_LOW = 0.12
WHITESPACE_HIGH = 0.88
EDGE_DENSITY_HIGH = 0.28
BORDER_BAND = 0.012
BORDER_INK_HIGH = 0.06


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _rgb_to_lab(rgb: Any):
    import numpy as np

    arr = np.asarray(rgb, dtype=float).reshape(-1, 3) / 255.0
    mask = arr > 0.04045
    arr = np.where(mask, ((arr + 0.055) / 1.055) ** 2.4, arr / 12.92)
    matrix = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ]
    )
    xyz = arr @ matrix.T
    white = np.array([0.95047, 1.00000, 1.08883])
    xyz = xyz / white
    eps = 216 / 24389
    kappa = 24389 / 27
    f = np.where(xyz > eps, np.cbrt(xyz), (kappa * xyz + 16) / 116)
    lab = np.stack(
        [116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])],
        axis=1,
    )
    return lab


def _collect_expected_colors(style_spec: Path | None, extra: list[str]) -> list[str]:
    colors: list[str] = []
    if style_spec and style_spec.exists():
        colors.extend(
            "#" + match.lower()
            for match in HEX_RE.findall(style_spec.read_text(encoding="utf-8"))
        )
    for item in extra:
        for match in HEX_RE.findall(item if item.startswith("#") else "#" + item.lstrip("#")):
            colors.append("#" + match.lower())
    seen: list[str] = []
    for color in colors:
        if color not in seen:
            seen.append(color)
    return seen


def _nearest_aspect_name(ratio: float) -> str:
    candidates = {
        "1:1": 1.0,
        "4:5": 0.8,
        "3:4": 0.75,
        "2:3": 2 / 3,
        "9:16": 0.5625,
        "5:4": 1.25,
        "4:3": 4 / 3,
        "3:2": 1.5,
        "16:9": 16 / 9,
        "21:9": 21 / 9,
    }
    return min(candidates, key=lambda key: abs(candidates[key] - ratio))


def _parse_aspect(value: str) -> float | None:
    if not value or value == "auto":
        return None
    if ":" in value:
        left, _, right = value.partition(":")
        try:
            return float(left) / float(right)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(value)
    except ValueError:
        return None


def analyse(image_path: Path, expected_colors: list[str], expect_aspect: str) -> dict[str, Any]:
    import numpy as np
    from PIL import Image, ImageFilter

    with Image.open(image_path) as source:
        image = source.convert("RGB")
        width, height = image.size
        work = image.copy()
        work.thumbnail((900, 900))
        pixels = np.asarray(work, dtype=np.uint8).reshape(-1, 3)

        edges = work.convert("L").filter(ImageFilter.FIND_EDGES)
        edge_arr = np.asarray(edges, dtype=np.uint8)
        edge_density = float((edge_arr > 40).mean())

        border_band = max(1, int(min(work.size) * BORDER_BAND))
        gray = np.asarray(work.convert("L"), dtype=np.uint8)

    ratio = width / max(height, 1)
    quantized = np.unique((pixels // 8) * 8, axis=0, return_counts=True)
    bins, counts = quantized
    order = np.argsort(-counts)
    total = float(counts.sum())
    dominant = [
        {
            "hex": "#%02x%02x%02x" % tuple(int(v) for v in bins[index]),
            "share": round(float(counts[index]) / total, 4),
        }
        for index in order[:10]
    ]

    background_rgb = bins[order[0]].astype(float)
    distance_to_bg = np.linalg.norm(pixels.astype(float) - background_rgb, axis=1)
    whitespace_ratio = float((distance_to_bg < 28).mean())

    # ink touching the outer band: a crop / bleed risk signal
    bg_gray = float(np.median(gray))
    band_mask = np.zeros(gray.shape, dtype=bool)
    band_mask[:border_band, :] = True
    band_mask[-border_band:, :] = True
    band_mask[:, :border_band] = True
    band_mask[:, -border_band:] = True
    border_ink = float((np.abs(gray[band_mask].astype(float) - bg_gray) > 45).mean())

    palette_report: list[dict[str, Any]] = []
    if expected_colors:
        expected_lab = _rgb_to_lab([_hex_to_rgb(color) for color in expected_colors])
        # Accent colors cover very little area, so compare against every colour
        # bin in the image and report how much of the canvas is inside the
        # match radius, not just whether a top-N bin happened to be close.
        observed_lab = _rgb_to_lab(bins)
        shares = counts / total
        for index, color in enumerate(expected_colors):
            deltas = np.linalg.norm(observed_lab - expected_lab[index], axis=1)
            best = int(np.argmin(deltas))
            within = deltas <= PALETTE_MATCH_DELTA
            coverage = float(shares[within].sum())
            palette_report.append(
                {
                    "expected": color,
                    "nearest_in_image": "#%02x%02x%02x"
                    % tuple(int(v) for v in bins[best]),
                    "delta": round(float(deltas[best]), 1),
                    "coverage": round(coverage, 5),
                    "matched": bool(
                        deltas[best] <= PALETTE_MATCH_DELTA
                        and coverage >= PALETTE_MIN_COVERAGE
                    ),
                }
            )

    expected_ratio = _parse_aspect(expect_aspect)
    aspect_ok = (
        None
        if expected_ratio is None
        else abs(ratio - expected_ratio) / expected_ratio <= ASPECT_TOLERANCE
    )

    matched = [item for item in palette_report if item["matched"]]
    findings: list[dict[str, str]] = []
    if aspect_ok is False:
        findings.append(
            {
                "check": "aspect_ratio",
                "level": "fail",
                "message": f"Requested {expect_aspect} but the image is {_nearest_aspect_name(ratio)} ({width}x{height}). Re-plan the layout for the achievable canvas or regenerate; never stretch or crop a diagram to fit.",
            }
        )
    if max(width, height) < MIN_LONG_EDGE:
        findings.append(
            {
                "check": "resolution",
                "level": "warn",
                "message": f"Long edge is {max(width, height)}px; small labels will not survive. Request a larger image size.",
            }
        )
    if palette_report and len(matched) < min(3, len(palette_report)):
        findings.append(
            {
                "check": "palette",
                "level": "warn",
                "message": f"Only {len(matched)}/{len(palette_report)} style-spec colors appear in the output. Palette anchors are likely missed.",
            }
        )
    if whitespace_ratio < WHITESPACE_LOW:
        findings.append(
            {
                "check": "whitespace",
                "level": "warn",
                "message": f"Background covers only {whitespace_ratio:.0%} of the canvas; the figure is probably overloaded against the density budget.",
            }
        )
    if whitespace_ratio > WHITESPACE_HIGH:
        findings.append(
            {
                "check": "whitespace",
                "level": "warn",
                "message": f"Background covers {whitespace_ratio:.0%}; content may be too sparse or dropped.",
            }
        )
    if edge_density > EDGE_DENSITY_HIGH:
        findings.append(
            {
                "check": "busyness",
                "level": "warn",
                "message": f"Edge density {edge_density:.2f} is high; check for text pile-up and connector crossings.",
            }
        )
    if border_ink > BORDER_INK_HIGH:
        findings.append(
            {
                "check": "safe_margin",
                "level": "warn",
                "message": f"{border_ink:.0%} of the outer band carries ink; check for cropped labels or containers at the canvas edge.",
            }
        )

    status = "fail" if any(f["level"] == "fail" for f in findings) else (
        "warn" if findings else "ok"
    )
    return {
        "image": str(image_path),
        "status": status,
        "geometry": {
            "width": width,
            "height": height,
            "aspect_ratio": round(ratio, 4),
            "nearest_named_aspect": _nearest_aspect_name(ratio),
            "expected_aspect": expect_aspect,
            "aspect_ok": aspect_ok,
        },
        "palette": {
            "dominant": dominant,
            "expected_colors": expected_colors,
            "matches": palette_report,
            "matched_count": len(matched),
        },
        "density": {
            "background_share": round(whitespace_ratio, 4),
            "edge_density": round(edge_density, 4),
            "border_ink_share": round(border_ink, 4),
        },
        "findings": findings,
        "not_covered_by_this_script": [
            "required nodes, relations and their direction",
            "exact text accuracy and hallucinated glyphs",
            "chosen archetype, zones, reading path and focal point",
            "source-content leakage",
            "anchor-by-anchor style scoring",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--style-spec", type=Path, help="style-spec.json to read expected #RRGGBB values from.")
    parser.add_argument("--color", action="append", default=[], help="Extra expected hex color. Repeatable.")
    parser.add_argument("--expect-aspect", default="auto", help="Planned aspect ratio, e.g. 16:9.")
    parser.add_argument("--report", type=Path, help="Where to write the JSON report.")
    args = parser.parse_args()

    image = args.image.expanduser().resolve()
    if not image.exists():
        print(json.dumps({"status": "failed", "message": f"Image not found: {image}"}), file=sys.stderr)
        return 2

    expected = _collect_expected_colors(
        args.style_spec.expanduser().resolve() if args.style_spec else None, args.color
    )
    report = analyse(image, expected, args.expect_aspect)
    if args.report:
        path = args.report.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())

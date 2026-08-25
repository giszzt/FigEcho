#!/usr/bin/env python3
"""Reference-conditioned figure generation adapter for third-party backends.

Route selection stays with the FigEcho workflow. Use this script only
after style-prompt.md, content-graph.json, visual-plan.json and prompt.md are
complete, and only when the current agent has no built-in reference-capable
image tool (Codex image_gen), or that tool failed.

Scriptable priority:
  1. labnana-gpt-image-2   (provider=openai,  model=gpt-image-2)
  2. labnana-nano-banana   (provider=google,  model=gemini-3-pro-image)
  3. openai-official       (images.edit with the reference image)
  4. gemini-official
  5. configured-command    (provider-neutral external command)

Unlike a clean-plate adapter, every reference here is a STYLE reference: the
model must not reproduce the reference's content, only its visual language.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import mimetypes
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import api_keys as _api_keys

    _api_keys.load()
except Exception:  # pragma: no cover - .env loading is best effort
    pass

LABNANA_DEFAULT_BASE_URL = "https://api.labnana.com"
LABNANA_IMAGE_ENDPOINT = "/openapi/v1/images/generation"
LABNANA_GPT_MODEL = "gpt-image-2"
LABNANA_GEMINI_MODEL = "gemini-3-pro-image"

LABNANA_VARIANTS = {
    "labnana-gpt-image-2": LABNANA_GPT_MODEL,
    "labnana-nano-banana": LABNANA_GEMINI_MODEL,
}

# Labnana rejects any aspectRatio outside the model's own table with a 400.
# Snapping to the nearest supported ratio keeps the planned canvas intent;
# dropping the field is only safe where the model infers the ratio itself.
LABNANA_ALL_RATIOS = (
    "1:1", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9", "21:9",
    "1:4", "4:1", "1:8", "8:1",
)
LABNANA_MODEL_CAPS: dict[str, dict[str, Any]] = {
    LABNANA_GPT_MODEL: {
        "provider": "openai",
        "aspect_ratios": ("1:1", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9", "21:9"),
        "image_sizes": ("1K", "2K", "4K"),
        "max_references": 4,
        # documented: omitting aspectRatio lets the model pick from the prompt
        "omit_aspect_ok": True,
    },
    LABNANA_GEMINI_MODEL: {
        "provider": "google",
        "aspect_ratios": LABNANA_ALL_RATIOS,
        "image_sizes": ("1K", "2K", "4K"),
        "max_references": 14,
        # omitting aspectRatio here falls back to the 1:1 default, not to
        # prompt-driven selection, so the field always has to be sent
        "omit_aspect_ok": False,
    },
}

# business codes ride on HTTP 400, so the status alone cannot classify a failure
LABNANA_RETRYABLE_CODES = frozenset({29998})
LABNANA_FATAL_CODES = frozenset({21007, 26004})
LABNANA_PARAMETER_CODES = frozenset({29003})
LABNANA_RETRY_BASE_SECONDS = 20  # provider guidance for 29998
LABNANA_MAX_BODY_BYTES = 20 * 1024 * 1024
LABNANA_REFERENCE_BUDGET = 17 * 1024 * 1024

VALID_ROLES = ("style_reference", "supporting_insert", "edit_target")


class ApiHTTPError(RuntimeError):
    """HTTP failure that also carries the provider's business error code."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = int(status)
        self.detail = detail
        self.code: int | None = None
        self.api_message = ""
        try:
            body = json.loads(detail)
        except Exception:
            body = None
        if isinstance(body, dict):
            raw = body.get("code")
            if isinstance(raw, int):
                self.code = raw
            elif isinstance(raw, str) and raw.strip().isdigit():
                self.code = int(raw.strip())
            self.api_message = str(body.get("message") or "")[:400]
        super().__init__(f"HTTP {self.status}: {detail}")


class FatalBackendError(RuntimeError):
    """Account-level failure; other models behind the same key will fail too."""

    def __init__(self, message: str, family: str) -> None:
        super().__init__(message)
        self.family = family


# --------------------------------------------------------------------------
# helpers


def _guess_mime(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed and guessed.startswith("image/"):
        return guessed
    head = path.read_bytes()[:16]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _inline_reference(path: Path, budget: int | None = None) -> tuple[dict[str, Any], str | None]:
    """Inline one reference, downscaling it if it would blow the 20 MB body cap."""
    raw = path.read_bytes()
    mime = _guess_mime(path)
    note: str | None = None
    if budget is not None and len(raw) * 4 // 3 > budget:
        try:
            import io

            from PIL import Image  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                f"{path.name} is {len(raw) // 1048576} MB; Labnana caps the whole request "
                "body at 20 MB and Pillow is not available to downscale it. Shrink the "
                "reference image manually before retrying."
            ) from exc
        with Image.open(path) as opened:
            image = opened.convert("RGB")
        width, height = image.width, image.height
        for _ in range(6):
            width = max(640, int(width * 0.75))
            height = max(640, int(height * 0.75))
            buffer = io.BytesIO()
            image.resize((width, height)).save(buffer, format="JPEG", quality=90)
            raw = buffer.getvalue()
            if len(raw) * 4 // 3 <= budget:
                mime = "image/jpeg"
                note = f"{path.name} downscaled to {width}x{height} JPEG to fit the 20 MB request body."
                break
        else:
            raise RuntimeError(
                f"{path.name} stays above the request body budget after six downscale "
                "passes; supply a smaller reference image."
            )
    return (
        {
            "inlineData": {
                "data": base64.b64encode(raw).decode("ascii"),
                "mimeType": mime,
            }
        },
        note,
    )


def _parse_ratio(value: str) -> float | None:
    text = str(value).strip().replace("：", ":").lower()
    if ":" in text:
        left, _, right = text.partition(":")
    elif "x" in text:
        left, _, right = text.partition("x")
    elif "/" in text:
        left, _, right = text.partition("/")
    else:
        try:
            parsed = float(text)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    try:
        width, height = float(left), float(right)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width / height


def _snap_aspect_ratio(requested: str, supported: tuple[str, ...]) -> tuple[str, bool]:
    """Map a requested ratio onto the nearest ratio the model actually accepts."""
    if requested in supported:
        return requested, False
    target = _parse_ratio(requested)
    if target is None:
        raise SystemExit(
            f"Unparsable --aspect-ratio {requested!r}; use auto or a W:H value such as 16:9."
        )
    best = min(
        supported,
        key=lambda candidate: abs(math.log((_parse_ratio(candidate) or 1.0) / target)),
    )
    return best, True


def _with_aspect_hint(prompt: str, aspect: str) -> str:
    return (
        f"{prompt}\n\n【画幅】输出图像的宽高比必须是 {aspect}"
        "（宽 : 高）。整幅构图按这个比例排布，"
        "不要输出方形画面，也不要用留白边凑出这个比例。"
    )


def _describe_empty_response(response: dict[str, Any]) -> str:
    parts: list[str] = ["Labnana response did not contain image bytes."]
    code = response.get("code")
    message = response.get("message")
    if code is not None or message:
        parts.append(f"code={code} message={str(message)[:300]}")
    candidates = response.get("candidates")
    if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
        reason = candidates[0].get("finishReason")
        if reason and reason != "STOP":
            parts.append(f"finishReason={reason}")
            ratings = candidates[0].get("safetyRatings")
            if ratings:
                parts.append(f"safetyRatings={json.dumps(ratings, ensure_ascii=False)[:300]}")
    feedback = response.get("promptFeedback")
    if feedback:
        parts.append(f"promptFeedback={json.dumps(feedback, ensure_ascii=False)[:300]}")
    return " ".join(parts)


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as img:
            return int(img.width), int(img.height)
    except Exception:
        return None


def _parse_reference(value: str) -> tuple[Path, str]:
    """Accept ``path`` or ``path::role``. Windows drive letters stay intact."""
    role = "style_reference"
    raw = value
    if "::" in value:
        raw, _, role = value.rpartition("::")
    if role not in VALID_ROLES:
        raise SystemExit(f"Invalid reference role {role!r}; use one of {VALID_ROLES}.")
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Reference image not found: {path}")
    return path, role


def _write_json(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_image_bytes(obj: Any) -> tuple[bytes, str] | None:
    if isinstance(obj, dict):
        inline = obj.get("inlineData") or obj.get("inline_data")
        if isinstance(inline, dict) and inline.get("data"):
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            return base64.b64decode(str(inline["data"])), str(mime)
        if obj.get("b64_json"):
            return base64.b64decode(str(obj["b64_json"])), "image/png"
        if obj.get("data") and str(
            obj.get("mimeType") or obj.get("mime_type") or ""
        ).startswith("image/"):
            mime = obj.get("mimeType") or obj.get("mime_type") or "image/png"
            return base64.b64decode(str(obj["data"])), str(mime)
        for value in obj.values():
            found = _extract_image_bytes(value)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _extract_image_bytes(value)
            if found:
                return found
    return None


def _save_image_bytes(out: Path, data: bytes, mime: str) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".png" and mime not in ("image/png", "image/x-png"):
        try:
            import io

            from PIL import Image  # type: ignore

            with Image.open(io.BytesIO(data)) as img:
                img.convert("RGB").save(out, format="PNG")
            return out
        except Exception:
            pass
    out.write_bytes(data)
    return out


def _post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:1500]
        raise ApiHTTPError(exc.code, detail) from exc


# --------------------------------------------------------------------------
# backends


def _labnana_available() -> bool:
    return bool(os.environ.get("LABNANA_API_KEY"))


def _run_labnana(
    args: argparse.Namespace,
    *,
    variant: str,
    references: list[tuple[Path, str]],
    prompt: str,
    out: Path,
) -> dict[str, Any]:
    api_key = os.environ.get("LABNANA_API_KEY")
    if not api_key:
        raise RuntimeError("LABNANA_API_KEY is not set.")

    model = LABNANA_VARIANTS.get(variant)
    if model is None:
        raise ValueError(f"Unsupported Labnana variant: {variant}")
    caps = LABNANA_MODEL_CAPS[model]
    provider = str(caps["provider"])
    notes: list[str] = []

    image_size = args.image_size.strip().upper()
    if image_size not in caps["image_sizes"]:
        raise RuntimeError(
            f"{model} accepts imageSize {list(caps['image_sizes'])}, not {args.image_size!r}."
        )
    if len(references) > int(caps["max_references"]):
        raise RuntimeError(
            f"{model} accepts at most {caps['max_references']} reference images but "
            f"{len(references)} were supplied. Drop the lowest-value supporting inserts."
        )

    requested = args.aspect_ratio.strip()
    if requested == "auto":
        first_aspect: str | None = None
        aspect_source = "model-selected"
    else:
        snapped_to, was_snapped = _snap_aspect_ratio(requested, caps["aspect_ratios"])
        first_aspect = snapped_to
        aspect_source = "snapped" if was_snapped else "exact"
        if was_snapped:
            notes.append(
                f"{model} does not support aspectRatio {requested}; snapped to the nearest "
                f"supported ratio {snapped_to}. Re-plan the layout for {snapped_to} or pick "
                "a backend that accepts the original ratio."
            )

    budget = LABNANA_REFERENCE_BUDGET // max(1, len(references))
    reference_payload: list[dict[str, Any]] = []
    for path, _ in references:
        item, note = _inline_reference(path, budget)
        reference_payload.append(item)
        if note:
            notes.append(note)

    base_url = os.environ.get("LABNANA_BASE_URL", LABNANA_DEFAULT_BASE_URL).rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    attempts: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = [{"aspect": first_aspect, "prompt": prompt}]
    response_json: dict[str, Any] | None = None
    used_aspect = first_aspect
    used_prompt = prompt
    plan_index = 0

    while plan_index < len(plans):
        plan = plans[plan_index]
        plan_index += 1
        image_config: dict[str, Any] = {"imageSize": image_size}
        if plan["aspect"]:
            image_config["aspectRatio"] = plan["aspect"]
        payload = {
            "provider": provider,
            "model": model,
            "prompt": plan["prompt"],
            "imageConfig": image_config,
            "referenceImages": reference_payload,
        }
        body_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if body_bytes > LABNANA_MAX_BODY_BYTES:
            raise RuntimeError(
                f"Request body is {body_bytes // 1048576} MB, above Labnana's 20 MB cap. "
                "Use fewer or smaller reference images."
            )

        for attempt in range(1, args.max_retries + 1):
            try:
                response_json = _post_json(
                    base_url + LABNANA_IMAGE_ENDPOINT, payload, headers, args.timeout
                )
                used_aspect = plan["aspect"]
                used_prompt = plan["prompt"]
                break
            except ApiHTTPError as exc:
                attempts.append(
                    {
                        "aspect_ratio": plan["aspect"] or "omitted",
                        "attempt": attempt,
                        "http_status": exc.status,
                        "code": exc.code,
                        "message": exc.api_message or exc.detail[:400],
                    }
                )
                if exc.code in LABNANA_FATAL_CODES or exc.status in (401, 403):
                    raise FatalBackendError(
                        f"Labnana account failure (code {exc.code}): "
                        f"{exc.api_message or exc.detail[:200]}",
                        "labnana-",
                    ) from exc
                retryable = (
                    exc.code in LABNANA_RETRYABLE_CODES
                    or exc.status == 429
                    or exc.status >= 500
                )
                if retryable:
                    if attempt < args.max_retries:
                        time.sleep(min(60, LABNANA_RETRY_BASE_SECONDS * attempt))
                        continue
                    break
                # Parameter or content rejection. Resending the same body is
                # pointless. The one useful variation is dropping aspectRatio on
                # a model that infers the ratio from the prompt, and only when the
                # rejection was about parameters -- a content refusal survives it.
                if (
                    plan["aspect"]
                    and caps["omit_aspect_ok"]
                    and (exc.code in LABNANA_PARAMETER_CODES or exc.code is None)
                    and not any(item["aspect"] is None for item in plans)
                ):
                    plans.append(
                        {
                            "aspect": None,
                            "prompt": _with_aspect_hint(prompt, plan["aspect"]),
                        }
                    )
                    notes.append(
                        f"{model} rejected aspectRatio {plan['aspect']} (code {exc.code}); "
                        "retrying with the ratio stated in the prompt instead. Verify the "
                        "delivered canvas with check_render.py."
                    )
                break
            except Exception as exc:  # transport-level failure
                # 2K/4K responses are multi-megabyte; truncated reads and SSL
                # EOFs are the most common failure in practice, and retrying
                # the identical body is the correct response to them.
                attempts.append(
                    {
                        "aspect_ratio": plan["aspect"] or "omitted",
                        "attempt": attempt,
                        "http_status": None,
                        "code": None,
                        "message": str(exc)[:400],
                    }
                )
                if attempt < args.max_retries:
                    time.sleep(2 * attempt)
                    continue
                break
        if response_json is not None:
            break

    if response_json is None:
        detail = {"model": model, "notes": notes, "attempts": attempts}
        if first_aspect and not caps["omit_aspect_ok"]:
            detail["hint"] = (
                f"{model} defaults to 1:1 when aspectRatio is omitted, so the field was not "
                "dropped. Fix the parameters or switch to gpt-image-2 rather than accepting "
                "a square canvas."
            )
        raise RuntimeError(json.dumps(detail, ensure_ascii=False)[:1800])

    extracted = _extract_image_bytes(response_json)
    if not extracted:
        raise RuntimeError(_describe_empty_response(response_json))
    image_bytes, mime = extracted
    written = _save_image_bytes(out, image_bytes, mime)
    return {
        "backend": f"labnana/{provider}",
        "model": model,
        "requested_aspect_ratio": requested,
        "submitted_aspect_ratio": used_aspect or "omitted",
        "aspect_source": "prompt-only" if used_aspect is None and requested != "auto" else aspect_source,
        "prompt_modified": used_prompt != prompt,
        "requested_image_size": image_size,
        "response_mime": mime,
        "notes": notes,
        "attempts": attempts,
        "output": str(written),
    }


def _run_official_openai(
    args: argparse.Namespace,
    *,
    references: list[tuple[Path, str]],
    prompt: str,
    out: Path,
) -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")
    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:
        raise RuntimeError("The openai Python package is not installed.") from exc

    model = os.environ.get("FIGECHO_OPENAI_IMAGE_MODEL", "gpt-image-2")
    client = OpenAI()
    handles = [path.open("rb") for path, _ in references]
    try:
        result = client.images.edit(
            model=model,
            image=handles if len(handles) > 1 else handles[0],
            prompt=prompt,
            size=os.environ.get("FIGECHO_OPENAI_IMAGE_SIZE", "auto"),
        )
    finally:
        for handle in handles:
            handle.close()
    data_items = getattr(result, "data", None) or []
    if not data_items:
        raise RuntimeError("OpenAI Images API returned no image data.")
    item = data_items[0]
    b64 = getattr(item, "b64_json", None) or (
        item.get("b64_json") if isinstance(item, dict) else None
    )
    if not b64:
        raise RuntimeError("OpenAI Images API returned no b64_json image.")
    written = _save_image_bytes(out, base64.b64decode(b64), "image/png")
    return {
        "backend": "openai-official",
        "model": model,
        "requested_aspect_ratio": args.aspect_ratio,
        "submitted_aspect_ratio": "auto",
        "output": str(written),
    }


def _run_official_gemini(
    args: argparse.Namespace,
    *,
    references: list[tuple[Path, str]],
    prompt: str,
    out: Path,
) -> dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not set.")
    model = os.environ.get("FIGECHO_GEMINI_IMAGE_MODEL", "gemini-3-pro-image")
    inputs: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for path, _ in references:
        inputs.append(
            {
                "type": "image",
                "mime_type": _guess_mime(path),
                "data": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
        )
    base_url = os.environ.get(
        "GEMINI_INTERACTIONS_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta",
    ).rstrip("/")
    response_json = _post_json(
        base_url + "/interactions",
        {"model": model, "input": inputs},
        {"Content-Type": "application/json", "x-goog-api-key": api_key},
        args.timeout,
    )
    extracted = _extract_image_bytes(response_json)
    if not extracted:
        raise RuntimeError("Gemini response did not contain image bytes.")
    image_bytes, mime = extracted
    written = _save_image_bytes(out, image_bytes, mime)
    return {
        "backend": "gemini-official",
        "model": model,
        "requested_aspect_ratio": args.aspect_ratio,
        "submitted_aspect_ratio": "auto",
        "response_mime": mime,
        "output": str(written),
    }


def _load_command_config(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        env_path = os.environ.get("FIGECHO_IMAGE_CONFIG")
        path = Path(env_path) if env_path else None
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"Image backend config not found: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Image backend config must be a JSON object.")
    command = config.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) for item in command)
    ):
        raise ValueError("Image backend config needs a non-empty string-list 'command'.")
    config.setdefault("name", "configured-image-backend")
    return config


def _run_command_backend(
    args: argparse.Namespace,
    *,
    references: list[tuple[Path, str]],
    prompt_file: Path,
    out: Path,
) -> dict[str, Any]:
    config = _load_command_config(args.config)
    if not config:
        raise RuntimeError(
            "No configured command backend. Set FIGECHO_IMAGE_CONFIG or pass --config."
        )
    values = {
        "prompt_file": str(prompt_file),
        "out": str(out),
        "aspect_ratio": args.aspect_ratio,
        "image_size": args.image_size,
        "references": os.pathsep.join(str(path) for path, _ in references),
        "reference": str(references[0][0]) if references else "",
    }
    command = [part.format(**values) for part in config["command"]]
    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=args.timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout[-2000:])
    if not out.exists():
        raise RuntimeError("Backend command succeeded but produced no output image.")
    return {
        "backend": str(config.get("name")),
        "model": str(config.get("model", "external-command")),
        "requested_aspect_ratio": args.aspect_ratio,
        "submitted_aspect_ratio": args.aspect_ratio,
        "stdout_tail": proc.stdout[-2000:],
        "output": str(out),
    }


# --------------------------------------------------------------------------
# orchestration


def _backend_order(args: argparse.Namespace) -> list[str]:
    if args.backend != "auto":
        return [args.backend]
    order = [
        "labnana-gpt-image-2",
        "labnana-nano-banana",
        "openai-official",
        "gemini-official",
        "configured-command",
    ]
    preferred = os.environ.get("FIGECHO_IMAGE_BACKEND", "").strip()
    if preferred in order:
        order.remove(preferred)
        order.insert(0, preferred)
    return order


def _routes(args: argparse.Namespace) -> list[dict[str, Any]]:
    try:
        configured = _load_command_config(args.config) is not None
    except Exception:
        configured = False
    return [
        {
            "priority": 0,
            "route": "built-in-imagegen",
            "available": "agent-check-required",
            "note": "If this agent has a built-in reference-capable image tool (Codex image_gen), use it first; this script cannot call it.",
        },
        {
            "priority": 1,
            "route": "labnana-gpt-image-2",
            "available": _labnana_available(),
            "required": ["LABNANA_API_KEY"],
            "aspect_ratios": list(LABNANA_MODEL_CAPS[LABNANA_GPT_MODEL]["aspect_ratios"]),
            "max_references": LABNANA_MODEL_CAPS[LABNANA_GPT_MODEL]["max_references"],
        },
        {
            "priority": 2,
            "route": "labnana-nano-banana",
            "available": _labnana_available(),
            "required": ["LABNANA_API_KEY"],
            "aspect_ratios": list(LABNANA_MODEL_CAPS[LABNANA_GEMINI_MODEL]["aspect_ratios"]),
            "max_references": LABNANA_MODEL_CAPS[LABNANA_GEMINI_MODEL]["max_references"],
        },
        {
            "priority": 3,
            "route": "openai-official",
            "available": bool(os.environ.get("OPENAI_API_KEY")),
            "required": ["OPENAI_API_KEY", "openai Python package"],
        },
        {
            "priority": 4,
            "route": "gemini-official",
            "available": bool(
                os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            ),
            "required": ["GEMINI_API_KEY or GOOGLE_API_KEY"],
        },
        {
            "priority": 5,
            "route": "configured-command",
            "available": configured,
            "required": ["FIGECHO_IMAGE_CONFIG or --config"],
        },
    ]


def precheck(args: argparse.Namespace) -> int:
    routes = _routes(args)
    ok = any(item["available"] is True for item in routes if item["priority"] > 0)
    print(
        json.dumps(
            {
                "status": "ok" if ok else "unavailable",
                "routes": routes,
                "message": (
                    "Scriptable backends are configured. They are the route for agents "
                    "without a built-in reference-capable image tool; inside Codex, use "
                    "image_gen first."
                    if ok
                    else "No scriptable backend configured. Copy env.example to .env (or write "
                    "~/.claude/image-backends.env) and set LABNANA_API_KEY."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if ok else 1


def _record_path_value(path: Path, tail: str) -> str:
    text = path.as_posix()
    return tail if text.endswith(tail) else str(path)


def generate(args: argparse.Namespace) -> int:
    if not args.prompt_file or not args.out or not args.reference:
        raise SystemExit("--prompt-file, --reference and --out are required.")
    prompt_file = args.prompt_file.expanduser().resolve()
    if not prompt_file.exists():
        raise SystemExit(f"Prompt file not found: {prompt_file}")
    out = args.out.expanduser().resolve()
    references = [_parse_reference(value) for value in args.reference]
    if not any(role == "style_reference" for _, role in references):
        raise SystemExit("At least one reference must have role style_reference.")

    prompt_text = prompt_file.read_text(encoding="utf-8")
    prompt = prompt_text.strip()
    if not prompt:
        raise SystemExit("Prompt file is empty.")

    errors: list[dict[str, Any]] = []
    skip_families: set[str] = set()
    for backend in _backend_order(args):
        if any(backend.startswith(family) for family in skip_families):
            errors.append(
                {
                    "backend": backend,
                    "message": "Skipped: an earlier model behind the same credentials failed "
                    "with an account-level error.",
                }
            )
            continue
        try:
            if backend.startswith("labnana-"):
                result = _run_labnana(
                    args, variant=backend, references=references, prompt=prompt, out=out
                )
            elif backend == "openai-official":
                result = _run_official_openai(
                    args, references=references, prompt=prompt, out=out
                )
            elif backend == "gemini-official":
                result = _run_official_gemini(
                    args, references=references, prompt=prompt, out=out
                )
            elif backend == "configured-command":
                result = _run_command_backend(
                    args, references=references, prompt_file=prompt_file, out=out
                )
            else:
                raise RuntimeError(f"Unknown backend: {backend}")
        except FatalBackendError as exc:
            errors.append(
                {"backend": backend, "message": str(exc)[:1200], "fatal_family": exc.family}
            )
            skip_families.add(exc.family)
            if args.backend != "auto":
                break
            continue
        except Exception as exc:
            errors.append({"backend": backend, "message": str(exc)[:1200]})
            if args.backend != "auto":
                break
            continue

        size = _image_size(out)
        record = {
            "schema_version": "1.0.0",
            "provider_mode": "external-image-api",
            "intent": "generate",
            "prompt_file": _record_path_value(prompt_file, "prompt.md"),
            "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            "binding_mechanism": "reference_images_payload",
            "input_images": [
                {"source": str(path), "role": role} for path, role in references
            ],
            "output_path": _record_path_value(out, "output/final.png"),
            "provider": result,
            "output_size": {"width": size[0], "height": size[1]} if size else None,
            "fallback_errors": errors,
        }
        if args.record:
            _write_json(args.record.expanduser().resolve(), record)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0

    failure = {
        "status": "failed",
        "message": "No image backend succeeded.",
        "errors": errors,
    }
    if args.record:
        _write_json(args.record.expanduser().resolve(), failure)
    print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a style-conditioned figure through a third-party image backend."
    )
    parser.add_argument("--precheck", action="store_true", help="Report configured routes.")
    parser.add_argument("--prompt-file", type=Path, help="prompt.md to submit verbatim.")
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        metavar="PATH[::ROLE]",
        help="Reference image; role is style_reference (default), supporting_insert or edit_target. Repeatable.",
    )
    parser.add_argument("--out", type=Path, help="Output PNG path, normally output/final.png.")
    parser.add_argument("--record", type=Path, help="Where to write generation-record.json.")
    parser.add_argument("--config", type=Path, help="Provider-neutral command backend config JSON.")
    parser.add_argument(
        "--backend",
        default="auto",
        choices=[
            "auto",
            "labnana-gpt-image-2",
            "labnana-nano-banana",
            "openai-official",
            "gemini-official",
            "configured-command",
        ],
    )
    parser.add_argument("--image-size", default="2K", choices=["1K", "2K", "4K"])
    parser.add_argument(
        "--aspect-ratio",
        default="auto",
        help="auto, or a ratio such as 16:9. Ratios outside a model's supported set are "
        "snapped to the nearest supported one and recorded in the generation record.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=4,
        help="Attempts per request variant; only retryable failures (rate limit, 5xx, "
        "transport) consume them.",
    )
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    if args.precheck:
        return precheck(args)
    return generate(args)


if __name__ == "__main__":
    raise SystemExit(main())

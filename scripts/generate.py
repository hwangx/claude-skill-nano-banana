#!/usr/bin/env python3
"""Generate images with Google's Nano Banana family via Vertex AI google-genai SDK.

Models (aliases → real IDs):
  nano-banana     → gemini-2.5-flash-image          (legacy, fixed 1024)
  nano-banana-2   → gemini-3.1-flash-image-preview  (default — fast, cheap, 14 aspects, 4K)
  nano-banana-pro → gemini-3-pro-image-preview      (text rendering, thinking, professional)

Auth: ADC via `gcloud auth application-default login`.
Project: GOOGLE_CLOUD_PROJECT env var or quota_project_id in ADC.
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import pathlib
import sys
import time

from google import genai
from google.genai import types


MODEL_ALIASES = {
    # Default
    "nano-banana-2": "gemini-3.1-flash-image-preview",
    "banana-2": "gemini-3.1-flash-image-preview",
    "2": "gemini-3.1-flash-image-preview",
    "flash": "gemini-3.1-flash-image-preview",
    # Pro
    "nano-banana-pro": "gemini-3-pro-image-preview",
    "banana-pro": "gemini-3-pro-image-preview",
    "pro": "gemini-3-pro-image-preview",
    # Legacy
    "nano-banana": "gemini-2.5-flash-image",
    "nano-banana-1": "gemini-2.5-flash-image",
    "banana-1": "gemini-2.5-flash-image",
    "1": "gemini-2.5-flash-image",
}

# Capability matrix per resolved model id.
MODEL_CAPS = {
    "gemini-3.1-flash-image-preview": {
        "sizes": {"512", "1K", "2K", "4K"},
        "aspects": {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
                    "9:16", "16:9", "21:9", "1:4", "4:1", "1:8", "8:1"},
        "thinking": True,
        "thinking_default": "minimal",
        "max_refs": 14,
    },
    "gemini-3-pro-image-preview": {
        "sizes": {"1K", "2K", "4K"},
        "aspects": {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
                    "9:16", "16:9", "21:9"},
        "thinking": True,
        "thinking_default": "high",
        "max_refs": 14,
    },
    "gemini-2.5-flash-image": {
        "sizes": set(),  # fixed 1024
        "aspects": {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
                    "9:16", "16:9", "21:9"},
        "thinking": False,
        "thinking_default": None,
        "max_refs": 3,  # legacy: up to 3 reference images
    },
}

# Vertex AI inline-request payload ceiling. Beyond this, the API rejects the
# request; the File API / GCS URIs would be needed (not wired up here).
MAX_INLINE_BYTES = 20 * 1024 * 1024  # ~20 MB


def resolve_model(arg: str) -> str:
    """Map a CLI alias to a real model ID; pass through unknown values."""
    return MODEL_ALIASES.get(arg, arg)


def ext_from_mime(mime: str, fallback: str = "png") -> str:
    if not mime:
        return fallback
    guess = mimetypes.guess_extension(mime)
    if not guess:
        return fallback
    return guess.lstrip(".").lower()


# Image MIME types Gemini accepts as static input (for editing / multi-reference).
# Animated formats (gif) are intentionally excluded — only the first frame would
# be used and behavior is unreliable; convert to a still image first.
INPUT_IMAGE_MIMES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".heic": "image/heic", ".heif": "image/heif",
}


def load_ref_parts(ref_paths: list[str], max_refs: int, model: str) -> list:
    """Load reference/source images as google-genai Parts for editing / multi-image input.

    De-dupes identical paths, enforces the model's reference-image cap, validates
    image type, and guards the total inline payload against the Vertex ceiling.
    """
    # Dedup identical paths (preserve order); a repeated image wastes payload and confuses the model.
    seen: set[str] = set()
    unique: list[str] = []
    for raw in ref_paths:
        key = str(pathlib.Path(raw).expanduser())
        if key in seen:
            print(f"  (skipping duplicate --ref: {raw})", file=sys.stderr)
            continue
        seen.add(key)
        unique.append(raw)

    if len(unique) > max_refs:
        sys.exit(
            f"ERROR: {len(unique)} --ref images, but model {model} supports at most {max_refs}. "
            f"Use fewer, or switch to nano-banana-2 / nano-banana-pro (14)."
        )

    parts = []
    total_bytes = 0
    for raw in unique:
        path = pathlib.Path(raw).expanduser()
        if not path.is_file():
            sys.exit(f"ERROR: --ref image not found: {path}")
        mime = INPUT_IMAGE_MIMES.get(path.suffix.lower())
        if not mime:
            guessed, _ = mimetypes.guess_type(str(path))
            # Only accept guessed types we actually support as still images.
            mime = guessed if guessed in INPUT_IMAGE_MIMES.values() else None
        if not mime:
            sys.exit(
                f"ERROR: --ref {path} is not a supported still image. "
                f"Supported extensions: {', '.join(sorted(INPUT_IMAGE_MIMES))} "
                f"(animated GIF not supported — convert to PNG/JPEG first)."
            )
        try:
            data = path.read_bytes()
        except Exception as e:
            sys.exit(f"ERROR reading --ref {path}: {e}")
        total_bytes += len(data)
        if total_bytes > MAX_INLINE_BYTES:
            sys.exit(
                f"ERROR: total --ref image size exceeds the ~{MAX_INLINE_BYTES // (1024*1024)}MB "
                f"inline request limit. Use fewer or smaller images (downscale large source files)."
            )
        parts.append(types.Part.from_bytes(data=data, mime_type=mime))
    return parts


# Image harm categories that Vertex AI lets you tune for image output.
IMAGE_HARM_CATEGORIES = [
    "HARM_CATEGORY_IMAGE_DANGEROUS_CONTENT",
    "HARM_CATEGORY_IMAGE_HARASSMENT",
    "HARM_CATEGORY_IMAGE_HATE",
    "HARM_CATEGORY_IMAGE_SEXUALLY_EXPLICIT",
]

# --safety mode → (block threshold for the 4 image categories, person_generation).
# These are the loosest values the API exposes; server-side HARD blocks
# (CSAM, real public-figure likeness, etc.) are NOT affected by any of these.
SAFETY_MODES = {
    "default": (None, None),                  # leave Google defaults untouched
    "relaxed": ("BLOCK_ONLY_HIGH", "allow_all"),
    "off":     ("BLOCK_NONE", "allow_all"),
}


def build_safety_settings(mode: str) -> list[types.SafetySetting]:
    threshold, _ = SAFETY_MODES[mode]
    if threshold is None:
        return []
    return [
        types.SafetySetting(
            category=getattr(types.HarmCategory, cat),
            threshold=getattr(types.HarmBlockThreshold, threshold),
        )
        for cat in IMAGE_HARM_CATEGORIES
    ]


def build_image_config(args, caps: dict) -> types.ImageConfig:
    aspect = args.aspect
    if aspect not in caps["aspects"]:
        sys.exit(
            f"ERROR: --aspect {aspect!r} not supported by model {args.model}.\n"
            f"  Supported: {sorted(caps['aspects'])}"
        )

    image_size = args.size
    if image_size:
        if not caps["sizes"]:
            sys.exit(
                f"ERROR: --size not supported by model {args.model} (fixed 1024). "
                f"Drop --size or switch to nano-banana-2 / nano-banana-pro."
            )
        if image_size not in caps["sizes"]:
            sys.exit(
                f"ERROR: --size {image_size!r} not supported by model {args.model}.\n"
                f"  Supported: {sorted(caps['sizes'])}"
            )

    mime = {"png": "image/png", "jpeg": "image/jpeg", "jpg": "image/jpeg"}.get(
        args.output_format, "image/png"
    )

    kwargs = dict(
        aspect_ratio=aspect,
        output_mime_type=mime,
    )
    if image_size:
        kwargs["image_size"] = image_size
    if args.output_format in {"jpeg", "jpg"} and args.compression is not None:
        kwargs["output_compression_quality"] = args.compression

    _, person_generation = SAFETY_MODES[args.safety]
    if person_generation:
        kwargs["person_generation"] = person_generation

    return types.ImageConfig(**kwargs)


def build_generate_config(args, caps: dict) -> types.GenerateContentConfig:
    modalities = ["IMAGE"]
    if args.include_thoughts:
        modalities = ["TEXT", "IMAGE"]

    cfg_kwargs = dict(
        response_modalities=modalities,
        image_config=build_image_config(args, caps),
    )

    safety_settings = build_safety_settings(args.safety)
    if safety_settings:
        cfg_kwargs["safety_settings"] = safety_settings

    if caps["thinking"] and (args.thinking or args.include_thoughts):
        cfg_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_level=args.thinking or caps["thinking_default"] or "minimal",
            include_thoughts=args.include_thoughts,
        )

    return types.GenerateContentConfig(**cfg_kwargs)


def extract_images(response) -> list[tuple[bytes, str]]:
    """Return list of (image_bytes, mime_type) tuples from a response."""
    out: list[tuple[bytes, str]] = []
    for cand in response.candidates or []:
        content = getattr(cand, "content", None)
        if not content:
            continue
        for part in content.parts or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                mime = getattr(inline, "mime_type", "image/png") or "image/png"
                out.append((inline.data, mime))
    return out


def save_image(data: bytes, out_dir: pathlib.Path, stem: str, ext: str, idx: int, total: int) -> pathlib.Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if total == 1 else f"_{idx + 1}"
    path = out_dir / f"{stem}{suffix}.{ext}"
    path.write_bytes(data)
    return path


def main() -> None:
    p = argparse.ArgumentParser(description="Generate or edit images via Google Nano Banana (Gemini image models).")
    p.add_argument("prompt", help="Subject→Action→Location→Composition→Style prose. For edits, use change-X / preserve-Y.")
    p.add_argument(
        "--ref",
        action="append",
        default=None,
        metavar="PATH",
        help="Reference/source image to edit or guide generation (repeatable, up to 14). "
             "With one --ref the prompt edits that image (use change-X/preserve-Y). "
             "With several, assign roles in the prompt ('use image 1 for pose, image 2 for style').",
    )
    p.add_argument(
        "--model",
        default="nano-banana-2",
        help="Model alias or raw ID. Default: nano-banana-2 (gemini-3.1-flash-image-preview).",
    )
    p.add_argument(
        "--aspect",
        default="1:1",
        help="Aspect ratio. 9 standard: 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9. "
             "Nano Banana 2 also: 1:4, 4:1, 1:8, 8:1.",
    )
    p.add_argument(
        "--size",
        default=None,
        help="Image size: 512 (nb2 only), 1K, 2K, 4K (nb2/pro). Omit for nano-banana legacy (fixed 1024).",
    )
    p.add_argument(
        "--thinking",
        default=None,
        choices=["minimal", "high"],
        help="Thinking level. Default minimal (nb2) / high (pro). Not supported on legacy.",
    )
    p.add_argument(
        "--include-thoughts",
        action="store_true",
        help="Include model thinking traces in stderr (forces TEXT modality).",
    )
    p.add_argument(
        "--format",
        dest="output_format",
        default="png",
        choices=["png", "jpeg", "jpg"],
        help="Output format (default: png).",
    )
    p.add_argument(
        "--compression",
        type=int,
        default=None,
        help="JPEG quality 0-100 (only used with --format jpeg).",
    )
    p.add_argument(
        "--safety",
        default="default",
        choices=["default", "relaxed", "off"],
        help="Safety threshold for the 4 tunable IMAGE harm categories. "
             "default=Google defaults; relaxed=BLOCK_ONLY_HIGH + person_generation=allow_all; "
             "off=BLOCK_NONE + allow_all (loosest the API exposes). "
             "Server-side HARD blocks (CSAM, real public-figure likeness, etc.) are NOT affected.",
    )
    p.add_argument("--n", type=int, default=1, help="Number of images (separate API calls, max 4).")
    p.add_argument("--out", default=".", help="Output directory (default: current dir).")
    p.add_argument("--name", default=None, help="Filename stem (default: nano-banana-<timestamp>).")
    p.add_argument(
        "--project",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        help="GCP project (auto-detected from env / ADC).",
    )
    p.add_argument("--location", default="global", help="Vertex AI location (default: global).")
    args = p.parse_args()

    args.model = resolve_model(args.model)
    if args.model not in MODEL_CAPS:
        sys.exit(
            f"ERROR: unknown model {args.model!r}. Aliases: nano-banana-2, nano-banana-pro, nano-banana. "
            "Or pass a full Gemini image model ID."
        )
    caps = MODEL_CAPS[args.model]

    if args.n < 1 or args.n > 4:
        sys.exit("ERROR: --n must be between 1 and 4.")

    ref_paths = args.ref or []
    ref_parts = load_ref_parts(ref_paths, caps.get("max_refs", 14), args.model)
    # contents = [ref images..., prompt]. Empty ref_parts → text-to-image as before.
    contents = ref_parts + [args.prompt]

    cfg = build_generate_config(args, caps)

    try:
        client = genai.Client(vertexai=True, project=args.project, location=args.location)
    except Exception as e:
        sys.exit(f"ERROR initializing Vertex client: {e}")

    stem = args.name or f"nano-banana-{int(time.time())}"
    out_dir = pathlib.Path(args.out).expanduser()
    mode = f"edit/ref×{len(ref_parts)}" if ref_parts else "text→image"
    print(
        f"→ {args.model}  {mode}  aspect={args.aspect}  size={args.size or 'default'}  "
        f"n={args.n}  thinking={args.thinking or caps['thinking_default'] or 'n/a'}",
        file=sys.stderr,
    )

    all_paths: list[pathlib.Path] = []
    for i in range(args.n):
        try:
            resp = client.models.generate_content(
                model=args.model,
                contents=contents,
                config=cfg,
            )
        except Exception as e:
            sys.exit(f"ERROR generating image (call {i + 1}/{args.n}): {e}")

        if args.include_thoughts:
            for cand in resp.candidates or []:
                for part in (cand.content.parts if cand.content else []):
                    if getattr(part, "text", None):
                        print(f"  [thinking] {part.text}", file=sys.stderr)

        imgs = extract_images(resp)
        if not imgs:
            sys.exit(
                f"ERROR: no image returned (call {i + 1}/{args.n}). "
                f"Possible safety filter or prompt issue. "
                f"Candidates: {len(resp.candidates or [])}"
            )

        for j, (data, mime) in enumerate(imgs):
            ext = ext_from_mime(mime, fallback=args.output_format)
            idx = i * len(imgs) + j
            total = args.n * len(imgs)
            path = save_image(data, out_dir, stem, ext, idx, total)
            all_paths.append(path)

        usage = getattr(resp, "usage_metadata", None)
        if usage:
            print(
                f"  tokens (call {i + 1}): prompt={getattr(usage, 'prompt_token_count', '?')} "
                f"candidates={getattr(usage, 'candidates_token_count', '?')} "
                f"total={getattr(usage, 'total_token_count', '?')}",
                file=sys.stderr,
            )

    for path in all_paths:
        print(path.resolve())


if __name__ == "__main__":
    main()

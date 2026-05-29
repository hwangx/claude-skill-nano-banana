# Vertex AI Nano Banana API reference

This skill calls Google's image-generation models on Vertex AI via the
`google-genai` Python SDK. Same client / same auth as `gemini-consult`.

## Endpoint

Implicit via SDK — no manual HTTP. Under the hood the SDK calls
`generativelanguage.googleapis.com` (Studio) or
`<location>-aiplatform.googleapis.com` (Vertex AI). This skill pins
**Vertex AI** (`vertexai=True`) so quota goes to the user's GCP project.

```python
from google import genai
client = genai.Client(vertexai=True, location="global")  # project auto-detected
```

## Models (verified on a Vertex AI project; set your own `GOOGLE_CLOUD_PROJECT`)

| Alias | Real model ID | Generation |
|---|---|---|
| `nano-banana-2` (default) | `gemini-3.1-flash-image-preview` | Gemini 3.1 Flash |
| `nano-banana-pro` | `gemini-3-pro-image-preview` | Gemini 3 Pro |
| `nano-banana` (legacy) | `gemini-2.5-flash-image` | Gemini 2.5 Flash |

Verify availability:
```python
for m in client.models.list():
    if "image" in m.name.lower():
        print(m.name)
```

## Capability matrix

| | Nano Banana | Nano Banana 2 | Nano Banana Pro |
|---|---|---|---|
| Resolution | 1024 fixed | 512 / 1K / 2K / **4K** | 1K / 2K / **4K** |
| Aspects | 9 standard | **14** (extras: 1:4, 4:1, 1:8, 8:1) | 9 standard |
| Text rendering | Good | Advanced | **Excellent** |
| Multi-image input | up to 3 | up to 14 (10 obj + 4 char) | up to 14 (6 obj + 5 char) |
| Character consistency | OK | Strong | **Best** |
| Thinking / reasoning | — | minimal (default) | **high (default)** |
| Google Search grounding | ❌ | Web + Image | Web + Image |
| Tokens / image (range) | 1,290 | 500–2,520 | 1,120–2,000 |
| Positioning | Legacy | Speed + scale | Professional |

## Request shape

```python
from google.genai import types

cfg = types.GenerateContentConfig(
    response_modalities=["IMAGE"],         # add "TEXT" for thinking output
    image_config=types.ImageConfig(
        aspect_ratio="16:9",                # required
        image_size="2K",                    # optional, nb2/pro only
        output_mime_type="image/png",       # or image/jpeg
        output_compression_quality=95,      # JPEG only
        person_generation="allow_adult",    # optional safety knob
    ),
    thinking_config=types.ThinkingConfig(   # optional, nb2/pro only
        thinking_level="high",              # or "minimal"
        include_thoughts=True,              # exposes reasoning as TEXT parts
    ),
)

resp = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=["<Subject → Action → Location → Composition → Style prose>"],
    config=cfg,
)
```

### Extracting the image bytes

```python
for cand in resp.candidates or []:
    for part in (cand.content.parts if cand.content else []):
        if part.inline_data and part.inline_data.data:
            with open("out.png", "wb") as f:
                f.write(part.inline_data.data)
        elif part.text:
            print(part.text)  # thinking trace, only if response_modalities includes "TEXT"
```

The SDK's `Part` may also expose `part.as_image()` returning a PIL image —
this skill prefers raw bytes to avoid a Pillow dependency.

## `ImageConfig` fields (verified via SDK introspection)

| Field | Type | Notes |
|---|---|---|
| `aspect_ratio` | `str` | Required for image output. See aspect lists. |
| `image_size` | `str` | `"512"` / `"1K"` / `"2K"` / `"4K"`. Model-dependent. |
| `output_mime_type` | `str` | `"image/png"` (default) or `"image/jpeg"`. |
| `output_compression_quality` | `int` | 0–100, JPEG only. |
| `person_generation` | `str` | `"allow_all"` / `"allow_adult"` / `"dont_allow"`. |
| `prominent_people` | `ProminentPeople` | Safety setting for famous-person likeness. |
| `image_output_options` | `ImageConfigImageOutputOptions` | Reserved for future options. |

## Aspect ratios

Standard 9 (all three models): `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`,
`5:4`, `9:16`, `16:9`, `21:9`

Nano Banana 2 only — extra 4 ultra-wide / ultra-tall: `1:4`, `4:1`, `1:8`,
`8:1`. Use these for sidebar strips, mobile fullscreen banners, header
ribbons.

## Pricing (gemini-3 series, Vertex AI)

- Billed in tokens. Per-image **token counts** vary by resolution:
  - Nano Banana (2.5 Flash): 1,290 tokens (all resolutions)
  - Nano Banana 2 (3.1 Flash): 500–2,520 depending on resolution
  - Nano Banana Pro (3 Pro): 1,120–2,000 depending on resolution
- Token rate: see [Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing) for the current per-token rate on each model.
- Rough per-image cost — single-digit cents to under $0.10 for most calls.
  Pro at 4K with thinking can push higher.

For the authoritative rate, run:
```bash
gcloud billing accounts list
# then check the billing-account-specific pricing in Console
```

## Rate limits

Vertex AI quota is per-project, per-model, per-region. Defaults are
generous for Tier-1 projects (dozens of QPM). On `RESOURCE_EXHAUSTED`,
back off exponentially (1s → 2s → 4s → 8s) and retry. The script does
not auto-retry — it surfaces the GCP error verbatim.

## Limits & known issues

| Issue | Workaround |
|---|---|
| Editing / multi-reference | Available via `--ref <image>` (nb2/pro ≤14, legacy 3). Still images only (png/jpg/webp/heic) — animated GIF rejected; identical paths de-duped; total inline payload ≤ ~20MB (else File API/GCS, not wired). Script builds `contents=[Part.from_bytes(img)…, prompt]`. Best on Nano Banana Pro. |
| Non-deterministic — same prompt yields different results | Expected. Vertex AI image models do not currently accept a seed for these previews |
| Safety filters block a benign prompt | First raise permissiveness with `--safety relaxed` / `off` (sets the 4 IMAGE harm categories looser + `person_generation=allow_all`). If still blocked it's a server-side hard block (real public-figure likeness, etc.) — avoid named living individuals; for likeness work use Pro with character-consistency reference images |
| Preview models can change behavior between SDK versions | This skill pins behavior to verified output paths; if `image_config` API changes, surface the SDK exception verbatim |
| Multi-line CJK text in image may decompose glyphs | Per `prompting-guide.md` §7 — use larger text + double quotes + font name; for critical copy use Nano Banana Pro |
| 4K + thinking=high latency | Can exceed 60s; bump Bash timeout to 240s+ |

## Error codes (Vertex AI gRPC → SDK exceptions)

| Status | Cause | Action |
|---|---|---|
| `UNAUTHENTICATED` | ADC missing/expired | `gcloud auth application-default login` |
| `PERMISSION_DENIED` | Vertex AI API not enabled, or project missing IAM role `roles/aiplatform.user` | Enable API + grant role |
| `FAILED_PRECONDITION` | Billing not enabled on project | Attach billing account |
| `INVALID_ARGUMENT` | aspect / size not supported, prompt too long, bad enum | Read message; script catches most before the call |
| `NOT_FOUND` | Preview model rolled out of your region | Try `location="us-central1"` or check current preview availability |
| `RESOURCE_EXHAUSTED` | Quota / rate limit | Wait, retry, request quota increase |
| Empty `candidates[0].content.parts` | Safety filter triggered | First retry with `--safety relaxed` / `off`. If still empty → hard block: rephrase (drop named real people, ambiguous anatomy, violence). Do NOT auto-retry the same text under the same safety setting |
| `INTERNAL` / `UNAVAILABLE` | GCP server issue | Retry with backoff (max 3) |

## Post-processing recipes (optional)

Vertex returns images at the requested `image_size` reasonably accurately,
unlike older generations. If you still need a precise output size after
download:

```bash
# macOS — sips arg order is HEIGHT WIDTH
sips -z 900 1600 ./hero.png      # → 1600 wide × 900 tall
sips -z 630 1200 ./og-card.png   # → 1200 wide × 630 tall

# Linux — ImageMagick uses WIDTHxHEIGHT
convert in.png -resize 1600x900! out.png
```

`!` in ImageMagick forces exact dimensions, ignoring aspect.

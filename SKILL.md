---
name: nano-banana
description: >
  Generate images with Google's Nano Banana family (Gemini 3.1 Flash Image
  preview = "Nano Banana 2", Gemini 3 Pro Image preview = "Nano Banana Pro",
  Gemini 2.5 Flash Image = "Nano Banana") via the Vertex AI google-genai SDK.
  Use when the user asks to "make/draw/generate an image", "그림 그려줘",
  "이미지 만들어줘", "그림 만들어줘", "일러스트 그려줘", "아이콘 만들어줘",
  "배너 만들어줘", "포스터 만들어줘", "로고 만들어줘", "OG image", "썸네일",
  "나노 바나나", "nano banana", "구글로 이미지", "제미나이로 그림",
  or any request that produces a visual file saved to disk. Also EDITS existing
  images and combines reference images — "이 이미지 배경만 바꿔줘", "이 사진을
  다른 스타일로", "이 캐릭터로 다른 장면" — via the `--ref` flag (up to 14 images).
  The image is saved as PNG (default) or JPEG to the user's working directory or
  a specified path. Do NOT use for Figma flows, OpenAI image flows, or pure image
  analysis (describing/critiquing an image without producing a new file).
---

# nano-banana (Google Gemini image models)

Direct Vertex AI calls via `google-genai` SDK. No third-party deps beyond what
`gemini-consult` already needs. Auth via Application Default Credentials.

## Prerequisites

- `google-genai` Python package (already installed for `gemini-consult`)
- ADC authenticated: `gcloud auth application-default login`
- `GOOGLE_CLOUD_PROJECT` env var set, or `quota_project_id` in ADC

If auth fails, the script exits with the GCP error verbatim. Direct the user
to run `gcloud auth application-default login` and retry.

## Models — pick one per call

| Alias (`--model`) | Real ID | When |
|---|---|---|
| **`nano-banana-2`** (default) | `gemini-3.1-flash-image-preview` | Default. Fast, cheap. 14 aspect ratios (incl. 1:4, 4:1, 1:8, 8:1). 512/1K/2K/4K. Thinking minimal. |
| **`nano-banana-pro`** | `gemini-3-pro-image-preview` | Professional asset creation. **Best text rendering**, advanced reasoning (thinking high by default), best character consistency. 1K/2K/4K. |
| `nano-banana` (legacy) | `gemini-2.5-flash-image` | Old gen. Fixed 1024. Use only if the user explicitly asks. |

### Routing heuristic — Claude decides per request

Default to **`nano-banana-2`**. Escalate to **`nano-banana-pro`** when any of these signals appears:

| Signal | Why → Pro |
|---|---|
| Image contains literal text (logo, OG card, poster, book cover, infographic with labels) | Pro's high-fidelity text rendering |
| Keywords: "로고", "브랜드", "전문", "최종 결과", "고품질", "정밀", "포트폴리오", "포스터 디자인", "타이포그래피" | Asset-grade output |
| Multi-image character consistency series (same person/character across N shots) | Pro is stronger at this |
| Complex composition with many constraints (8+ instructions in one prompt) | Pro's thinking handles complexity better |
| User explicitly says "프로", "Pro", "고품질로", "정밀하게" | Direct instruction |
| 4K requested AND output quality matters more than throughput | Pro returns better 4K detail |

Stay on **`nano-banana-2`** when:
- General illustrations, icons, banners with no in-image text
- User says "빠르게", "대충", "draft", "초안"
- Batch jobs where cost / throughput matters
- Non-standard aspect ratios (1:4, 4:1, 1:8, 8:1) — only Nano Banana 2 supports these

### Session-first-confirm pattern (mimics `gemini-consult`)

- **First call of a session**: announce the routing decision in one line before invoking the script. Example:
  > → Nano Banana 2 사용 (기본 라우팅). 로고·텍스트·고품질이 필요하면 "Pro로" 말씀해 주세요.

  Or:
  > → Nano Banana Pro 사용 (이미지 안에 텍스트가 들어가는 작업이라 자동 격상).

- **Subsequent calls in the same session**: skip the announcement, just say which model in one short line (e.g. `→ Nano Banana Pro (텍스트 렌더링)`).
- **User explicit override** ("프로로 바꿔", "이번 건 2로", "그냥 빠른 거로"): switch immediately and keep that choice for the rest of the session unless the user changes their mind.

## Workflow

### 1. Compose the prompt — Google-native 5-slot structure

**Do not pass the user's raw request to the API.** Rewrite as a flowing-prose
paragraph using Google's Nano Banana structure — this is the biggest
determinant of output quality.

| Slot | Content |
|---|---|
| **1. Subject** | the main figure or object, specific |
| **2. Action** | what is happening / the pose |
| **3. Location/context** | where the scene takes place, time, mood |
| **4. Composition** | framing, angle, depth of field |
| **5. Style** | aesthetic, medium, color grade, lighting, film stock |

**Start the prompt with a strong verb** (`Generate`, `Create`, `Photograph`,
`Illustrate`, `Render`). The most important elements (subject + style) follow
right after, which front-loads them naturally.

**Positive framing, NOT negative constraints.** Do NOT append "no watermark,
no extra text, no border" lists — on Gemini those tokens enter the attention
window and often *summon* the thing you forbade. To get a clean image,
describe the clean state ("a clean empty studio backdrop"), not the absence.

Skip empty adjectives ("stunning, 8K, masterpiece"). Name concrete materials
("navy tweed" > "suit"). For literal text in the image: wrap in double quotes
and name the font ("bold white sans-serif", "Century Gothic") — do NOT use
`EXACT TEXT verbatim` markers or letter-by-letter spelling (both are obsolete
and the latter actively breaks Gemini's tokenizer).

If multiple slots are missing from what the user said, ask **one** clarifying
question targeting the most important gap and proceed with reasonable
inferences for the rest.

Full prompting playbook (text rendering, camera/film-stock control, edit
patterns, anti-patterns, multilingual, before/after): see
[`references/prompting-guide.md`](references/prompting-guide.md).

### 2. Apply a `DESIGN.md` if present

If `DESIGN.md` exists at `cwd`, **or** the user references one
("DESIGN.md 보고", "이 사이트 톤", "editorial-photo.md 스타일"), read it first
and merge its palette / typography / illustration-style into **slot 3
(Details)** of every prompt in the current session. Same DESIGN.md = stylistic
consistency across multiple images.

The descriptive lines ("hand-folded paper feel", "soft natural light from
upper left", "single subject, plenty of whitespace") carry more weight than
hex codes — preserve them verbatim.

Don't invent a `DESIGN.md` or nag the user to create one.

### 3. Pick aspect and size

Aspect from user intent:

| Intent | `--aspect` |
|---|---|
| Square, icon, generic | `1:1` |
| Portrait, 세로, poster, mobile screen | `3:4`, `4:5`, or `9:16` |
| Landscape, banner, hero, 와이드 | `4:3`, `3:2`, or `16:9` |
| OG / social card | `16:9` (then optionally resize to 1200×630) |
| Ultra-wide banner | `21:9` |
| Vertical mobile banner / sidebar strip (Nano Banana 2 only) | `1:4`, `4:1`, `1:8`, `8:1` |

Size:
- Default omit `--size` on legacy (`nano-banana`) — fixed 1024
- `nano-banana-2`: default to `1K`; bump to `2K` for hero/print, `4K` for posters
- `nano-banana-pro`: default to `2K` (Pro is for asset quality — don't waste it on 1K); `4K` for print

### 4. Decide the output path

Default — save under cwd with a meaningful filename:

- `./assets/icons/dashboard.png`
- `./public/og-image.png`
- `./hero-banner.png`
- `./gardener-autumn.png`

Pass a kebab-case `--name` derived from the subject when the subject is
clear. Otherwise let it default to the timestamp.

### 5. Run the script

```bash
python3 ~/.claude/skills/nano-banana/scripts/generate.py \
  "<Subject → Action → Location → Composition → Style prose>" \
  --model nano-banana-2 \
  --aspect 1:1 \
  --size 1K \
  --out . \
  --name <kebab-case-name>
```

Bash tool timeout: **≥ 240,000 ms** (Pro with thinking=high can take 1–2 min).

**Editing an existing image** — pass it with `--ref` and write a change-X /
preserve-Y prompt (prefer Nano Banana Pro for fidelity):

```bash
python3 ~/.claude/skills/nano-banana/scripts/generate.py \
  "Change only the background to deep navy. Preserve everything else identically: \
the logo, all text, layout, lighting." \
  --ref ./current-banner.png \
  --model nano-banana-pro --aspect 16:9 --size 2K \
  --out . --name banner-navy
```

Combine several references (assign roles in the prompt):
`--ref pose.png --ref style.png` + *"use image 1 for the pose, image 2 for the art style."*

If a benign prompt gets refused by the safety filter (empty result), retry
with `--safety relaxed` (loosens the 4 tunable IMAGE harm categories +
`person_generation=allow_all`), or `--safety off` for the loosest the API
exposes. Server-side hard blocks (real public-figure likeness, CSAM, etc.)
are unaffected by these flags — rephrasing the prompt is the only path there.

The script prints absolute path(s) on stdout, one per saved file, and tokens
on stderr.

### 6. Report back

Tell the user:
1. The saved absolute path
2. Model + aspect + size used
3. Token usage (from stderr `tokens:` line)

If verification matters (text rendered correctly, layout right), open the PNG
with the Read tool before reporting. Do not embed inline — just the path.

## Script CLI parameters

| Flag | Default | Notes |
|------|---------|-------|
| `prompt` (positional) | — | Subject→Action→Location→Composition→Style prose. For edits: change-X / preserve-Y. |
| `--ref` | None | Source/reference image to edit or combine (repeatable; nb2/pro up to 14, legacy 3). 1 ref = edit it; many = assign roles in prompt. Best on Nano Banana Pro. Total input ≤ ~20MB; animated GIF not accepted. |
| `--model` | `nano-banana-2` | Alias or raw model ID. See routing table above. |
| `--aspect` | `1:1` | See aspect table. 14 ratios on nb2, 10 on pro/legacy. |
| `--size` | None | `512`/`1K`/`2K`/`4K` (model-dependent). Omit for legacy. |
| `--thinking` | model default | `minimal` / `high`. Not supported on legacy. |
| `--include-thoughts` | off | Print model's reasoning on stderr. Useful for debugging Pro outputs. |
| `--safety` | `default` | `default` / `relaxed` (BLOCK_ONLY_HIGH + allow_all) / `off` (BLOCK_NONE + allow_all). Tunes the 4 IMAGE harm categories only; hard blocks unaffected. |
| `--format` | `png` | `png` / `jpeg`. |
| `--compression` | — | JPEG quality 0–100. Only with `--format jpeg`. |
| `--n` | `1` | Number of separate API calls (1–4). Each is billed separately. |
| `--out` | `.` | Output directory. Created if missing. |
| `--name` | `nano-banana-<timestamp>` | Stem. With `--n > 1`, files get `_1`, `_2`, … |
| `--project` | env `GOOGLE_CLOUD_PROJECT` | GCP project; auto-detected from ADC. |
| `--location` | `global` | Vertex AI location. |

## Errors

The script exits non-zero on failure with the raw error text. Common cases:

- `PERMISSION_DENIED` / `UNAUTHENTICATED` → `gcloud auth application-default login`
- `Model not found` → check the model ID is still in preview in your region
- `aspect not supported` → script catches before the API; check capability table
- `No image returned` → safety filter or weak prompt. First try `--safety relaxed` / `off`; if still blocked it's a hard block — rephrase (drop named real people, ambiguous anatomy, violence). Do NOT auto-retry the same text.
- Timeout → bump Bash timeout; Pro thinking=high can be slow

## Limitations

- **Editing & multi-reference**: supported via `--ref <image>` (repeatable; nb2/pro up to 14, legacy `nano-banana` 3). One ref → edit that image (use change-X/preserve-Y, `prompting-guide.md` §4). Several refs → assign roles in the prompt ("image 1 for pose, image 2 for style"). Best on Nano Banana Pro. The script dedupes repeated paths, rejects animated GIF, and caps total inline input at ~20MB.
- **Non-deterministic**: same prompt yields different results each call. No seed support exposed.
- **Safety**: `--safety` tunes the 4 IMAGE harm categories + `person_generation`. Server-side hard blocks (real public-figure likeness, CSAM, sexual content) and the SynthID/C2PA watermark cannot be removed by any flag.

## References

- [`references/prompting-guide.md`](references/prompting-guide.md) — Google-native 5-slot (Subject/Action/Location/Composition/Style), strong-verb start, text rendering, camera/film-stock control, edit patterns, anti-patterns, multilingual, before/after
- [`references/api-reference.md`](references/api-reference.md) — Vertex AI endpoints, ImageConfig fields, model capabilities matrix, pricing, error codes

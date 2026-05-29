# Nano Banana Prompting Guide

Read this before composing prompts — especially for complex images, images containing text, or batches that need stylistic consistency. This guide is tuned to **Google's Nano Banana models** (Gemini image models), per Google's official prompt docs. It deliberately drops OpenAI/gpt-image-2 lore that is unnecessary — or actively harmful — on Gemini.

> Image editing & multi-reference input are available via the `--ref <image>` flag (repeatable, up to 14). The change-X / preserve-Y patterns in §4 are what you write in the prompt when editing.

## Table of contents

1. Five-part prompt structure (Google-native)
2. Start with a strong verb
3. Text rendering
4. Editing (change-X / preserve-Y pattern)
5. Size & aspect
6. Anti-patterns
7. Multilingual (non-Latin scripts)
8. Camera, lens & film-stock control
9. Before/After examples

---

## 1. Five-part prompt structure (Google-native)

Google's official Nano Banana structure. Write it as **flowing prose**, not a keyword list — the model reads it as a semantic structure and reasons about relationships before generating.

| Slot | What goes here | Example |
|---|---|---|
| **1. Subject** | The main figure or object, specific | "A stoic robot barista with glowing blue optics" |
| **2. Action** | What is happening / the pose | "carefully brewing a single cup of pour-over coffee" |
| **3. Location/context** | Where the scene takes place | "in a cozy, futuristic café on Mars at golden hour" |
| **4. Composition** | How the shot is framed | "medium close-up, slightly low angle, shallow depth of field" |
| **5. Style** | Overall aesthetic, medium, color, film stock | "cinematic 3D-animation look, warm teal-and-amber grade, soft volumetric light" |

> Google's verbatim example: *"[Subject] A striking fashion model wearing a tailored brown dress… [Action] Posing with a confident, statuesque stance… [Location] A seamless, deep cherry red studio backdrop… [Composition] Medium-full shot, center-framed… [Style] Fashion magazine editorial, shot on medium-format analog film, pronounced grain, high saturation, cinematic lighting."*

**Note what is NOT a slot:**
- **No "Use case" slot** — output size/aspect are set by the CLI flags (`--aspect`, `--size`), not by prose.
- **No "Constraints" slot** — Gemini does NOT want a "no watermark, no extra text, no border" list. Negative constraints put those very tokens into the attention window and often *summon* the thing you're forbidding. Use **positive framing** instead (see §6): to get a clean image, describe a *"clean, empty studio backdrop"* — don't write *"no clutter."*

## 2. Start with a strong verb

Google's first principle: **begin the prompt with a strong verb that names the primary operation.**

- `Generate…`, `Create…`, `Photograph…`, `Illustrate…`, `Render…`, `Compose…`, `Transform…` (edits)

This triggers the model's task-specific behavior up front. The most important elements (subject, style, mood) naturally follow right after — which keeps them early in the prompt where they carry the most weight. (There is no special "first-50-words" rule on Gemini; the Subject-first structure already front-loads what matters.)

## 3. Text rendering

Nano Banana models treat text as a **primary semantic layer** (Gemini 3 Pro ≈ 94% legible, strong on CJK). They do NOT need the tokenizer hacks older diffusion models required.

**Rules**:
- **Wrap literal strings in double quotes**: `the headline reads "URBAN EXPLORER"`
- **Name the font explicitly** — by class or actual name: `bold white sans-serif`, `Century Gothic`, `elegant brush-script font`, `heavy blocky Impact font`
- **State placement & size**: `centered`, `top-left at 8% padding`, `~80px equivalent`
- **For dense or tiny text → use Nano Banana Pro** (highest text fidelity)
- **Text-first hack** (Google-recommended): for tricky copy, first have the model draft the text in conversation, then ask it to render an image containing that exact text.

**Do NOT do (harmful/obsolete on Gemini):**
- ❌ **Letter-by-letter spelling** (`N-o-t-a-b-l-e`) — this *breaks* Gemini's whole-word tokenizer and degrades text. It was a CLIP-era workaround. Never use it here.
- ❌ `EXACT TEXT verbatim` markers and `no duplicate text` boilerplate — unnecessary on Gemini. Quotes + a font description are enough.

**Example — product label text**:
```
Render three lines of text on the label: the word "GLOW" in a flowing elegant
brush-script font (top), "10% OFF" in a heavy blocky Impact font (middle), and
"Your First Order" in a thin minimalist Century Gothic font (bottom).
```

## 4. Editing (change-X / preserve-Y pattern)

> Available via `--ref <image>`. Pass the source image with `--ref` and write the change-X / preserve-Y prompt below. Prefer Nano Banana Pro for edit fidelity; on NB2/legacy keep to 1–2 changes per pass.

**Rules**:
1. **Narrow the change to a single target**: "change only the background color to deep navy"
2. **List the preserve set explicitly**: "preserve: face, pose, lighting direction, framing, all text content, geometry"
3. **Repeat the preserve list every iteration** to fight drift.
4. **How many changes per pass depends on the model:**
   - **Nano Banana Pro** — its thinking phase can resolve several constraints at once; 3–4 simultaneous changes are fine.
   - **Nano Banana 2 / legacy** — keep to 1–2 changes per pass for coherence.

**Bad**: `Make this better and more professional looking`

**Good**:
```
Change only the sky from overcast to clear blue with soft cumulus clouds.
Preserve everything else identically: the woman's face, pose, beige sweater,
the painting on the wall, marble floor, lighting on her skin (still soft
afternoon side-light from camera-left), camera angle, framing. Match cloud
lighting to existing skin lighting direction.
```

## 5. Size & aspect

Set via CLI flags, not prose. Full detail in [`api-reference.md`](api-reference.md).

| Parameter | Values | Note |
|---|---|---|
| `--aspect` | 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 (+ 1:4, 4:1, 1:8, 8:1 on NB2) | Pick from the requested Composition/Location |
| `--size` | `512` (NB2), `1K`, `2K`, `4K`; legacy fixed 1024 | Resolution, not a "quality" enum |
| `--format` | png (default), jpeg | Line art/icons → png; photos → jpeg |
| Background | opaque | NB returns opaque PNG; post-process for transparency |

There is **no `quality: low/medium/high` parameter** on Nano Banana (that was a gpt-image-2 concept). Detail/effort is governed by `image_size` and, on NB2/Pro, by thinking level.

Recommended final sizes by use case (set aspect+size, resize locally only if you need an exact non-standard pixel target):
- **App icon**: request `1K` square → resize to 512×512 if needed
- **OG / social card**: `1K`–`2K` at `16:9` → resize to 1200×630
- **Blog header**: `2K` at `16:9`
- **Mobile portrait illustration**: `1K`–`2K` at `3:4` or `9:16`

## 6. Anti-patterns

| Anti-pattern | Why it fails | Use instead |
|---|---|---|
| **Negative constraints** (`no watermark`, `no extra text`, `no cars`) | Puts the forbidden token in the attention window — often *summons* it | **Positive framing**: `clean empty backdrop`, `an empty street`, describe the clean state you want |
| **Empty adjectives** (`stunning, masterpiece, cinematic, 8K, ultra-realistic`) | The model can't map them to pixels → generic "AI slop" | Concrete details: `overcast daylight, brushed aluminum, visible surface wear` |
| **Keyword soup** (`a cat, cute, soft, fluffy, big eyes, pink ribbon`) | Word relationships are lost | Natural sentence describing the scene |
| **Vague materials** (`a suit jacket`, `armor`) | Under-specified texture | Specific material: `navy blue tweed`, `ornate elven plate etched with silver leaf` |
| **Ten changes in one edit pass** (NB2/legacy) | Output destabilizes | 1–2 changes per pass on NB2; up to 3–4 on Pro |

## 7. Multilingual (non-Latin scripts)

Nano Banana renders CJK/Arabic/Devanagari far better than older models, but small or complex non-Latin text can still wobble.

**Tips**:
- **Write-and-translate pattern** (Google-recommended): write the prompt in any language and specify the target language for the in-image text — e.g. *"…then render the label text in Korean and Arabic."*
- Wrap the literal text in **double quotes** and name a typeface for that script: *"in a humanist sans-serif designed for Hangul."*
- Keep non-Latin text **≥ 5% of image height** — small glyphs break first.
- For mission-critical copy, use **Nano Banana Pro** and/or the text-first hack (§3).

## 8. Camera, lens & film-stock control

Nano Banana has strong latent associations with **real camera hardware and film stocks** — naming them is one of the highest-leverage Style controls (more effective than abstract adjectives).

| Want this vibe | Name this |
|---|---|
| Immersive, wide, slightly distorted action | `shot on a GoPro` |
| Authentic, warm, filmic color | `shot on a Fujifilm camera` |
| Raw, nostalgic, harsh-flash snapshot | `shot on a cheap disposable camera` |
| Shallow focus, subject isolation | `low-angle shot, shallow depth of field (f/1.8)` |
| Vast scale | `wide-angle lens` |
| Intricate close detail | `macro lens` |
| Nostalgic grain | `as if on 1980s color film, slightly grainy` |
| Modern moody | `cinematic color grading, muted teal tones` |

Also direct the **lighting** like a cinematographer: `three-point softbox setup`, `chiaroscuro high-contrast`, `golden-hour backlighting with long shadows`.

## 9. Before/After examples

All examples use the Google-native structure (Subject → Action → Location → Composition → Style) and **positive framing** (no negative constraint lists).

### Example 1 — Generic icon

**Bad**:
```
make an icon of a seedling, cute, simple
```

**Good**:
```
Illustrate a minimalist line-art icon of a single seedling with two leaves
growing from a flat horizon. Clean monochrome vector style, a single 2px
black stroke on a pure white background, centered with generous padding.
App-icon aesthetic for an indie note-taking app.
```
(Set `--aspect 1:1 --size 1K`. Note: no "no shadows/no watermark/no border" list — the positive style description already implies a clean flat icon.)

### Example 2 — OG image with text

**Bad**:
```
make me an OG image for my SaaS, modern and clean
```

**Good**:
```
Create an Open Graph card for a note-taking app called "Notable". On the
left half, the headline "Notable" in a bold sans-serif, dark navy (#0A1F3D)
on white, top-left at 8% padding, ~80px equivalent; beneath it the subhead
"fast notes for fast minds" at ~32px in medium gray. On the right half, a
soft radial gradient from pale blue (#E8F2FF) to white, with a faint
line-art seedling silhouette near the center-right.
```
(Set `--aspect 16:9`. Use Nano Banana Pro for crispest text. Quotes + font + placement carry the text — no EXACT TEXT marker needed.)

### Example 3 — Photo composition (future, when edits land)

**Bad**:
```
add a person to this photo
```

**Good**:
```
Add a man in his 40s wearing a charcoal coat to the scene, standing on the
sidewalk camera-left, 3m from the camera, gazing at the building entrance.
Preserve everything else identically: the building facade, all signage and
text, the parked cars, overcast lighting from camera-right, wet pavement
reflections, framing, and camera angle. Match his lighting (soft overcast,
slight rim from camera-right) and shadow direction (camera-left, short
mid-afternoon shadow) to the existing scene.
```

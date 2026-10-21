# Option 2 — Image-to-Video, Then Extract Sprite Frames

## Concept

Use a single approved character image as the video model's visual reference, request one brief attack and recovery, then extract and curate frames with Python/OpenCV. This is the fastest route to seeing whether the action prompt and design can produce a useful animation. The model's generated clip is an intermediate—not a finished spritesheet.

Proposed stack:

> Base image + compatible LoRA (if supported in the image-generation/reference stage) + [fal MiniMax H3 Max Turbo image-to-video](https://fal.ai/models/minimax/h3-max-turbo/image-to-video) + Python/OpenCV extraction, alignment, cleanup, and packing

The requested FAL endpoint is identified. Before implementation, verify its current API schema, supported image input, resolution/duration choices, pricing unit, and commercial-use terms. The endpoint's name alone does not guarantee the locked camera or weapon constraints in the generated clip.

## Workflow

1. **Prepare one clean input** — approve a right-facing side-view character reference on a plain white background, with the complete character and weapon inside generous margins. The input should already match the desired proportions and outfit.
2. **Send a short, controlled action prompt** — use the existing [action prompt](../prompt/action_prompt.txt) as the baseline. It specifies one fast polearm attack, return to idle, a locked orthographic camera, a singular physical weapon, and no added visual effects.
3. **Generate short clips** — keep the same input image and settings while comparing a small number of prompt/model settings. Record model ID/version, seed if available, duration, and generation parameters.
4. **Inspect the whole clip** — reject clips with camera motion, design changes, extra weapons/effects, implausible weapon deformation, clipping, or an unstable return pose. Do not use automated frame extraction to disguise these failures.
5. **Select usable frames** — use OpenCV to decode frames, select visually distinct poses by default, and order the selected images. Uniform sampling is also available. Retain original timestamps so timing can be adjusted in the game.
6. **Normalize** — crop/letterbox to a fixed canvas, align the ground point and character center, preserve the target right-facing orientation, and create alpha only if masking quality is acceptable. Save individual frames and a sheet plus metadata (frame order, duration/timing, pivot).
7. **Review at target scale** — inspect the strip in motion at the intended frame rate and at actual in-game size. Hand-correct or discard failures.

## Why use the existing action prompt

The prompt already defines constraints that commonly fail in generated clips: a fixed camera, unchanged character design, one continuous physical weapon, no slash trails or effects, and a stable idle recovery. Keep it as the comparison baseline. If the video API has separate negative-prompt, camera, motion-strength, or duration fields, map requirements into those fields only where the schema supports them; do not assume prompt text guarantees compliance.

## Strengths

- Fastest way to obtain a complete motion proposal from a single reference.
- Captures natural transitions between action poses without authoring every pose.
- Frame extraction is deterministic and can be scripted once the video is acceptable.
- Useful for discovering timing and key poses even if the final art requires repainting.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Temporal drift in face, costume, proportions, or palette | Review the entire clip; reject clips with drift. Prefer a model/API with strong image-reference conditioning if available. |
| Weapon bends, duplicates, disappears, or gains a trail | Preserve the strict prompt and inspect fast-motion frames; remove bad frames or hand-repair them. Do not assume optical flow or interpolation fixes geometry. |
| Camera, framing, or scale changes | Use a fixed-camera prompt and generous input margins; measure the character bounding box across frames and reject significant scale/position drift. |
| Clip does not return to the exact starting idle | Select or manually correct the recovery frames; for a seamless loop, match the first and last poses explicitly. |
| White background is not cleanly transparent | Keep white if the game pipeline supports it, or test threshold/segmentation methods on edges. Avoid global color-key removal where white costume details may be lost. |
| Frame cadence creates duplicates or uneven motion | Use timestamps and motion review to choose frames; remove redundant frames and set playback timing deliberately. |
| API model name, availability, or costs differ from expectations | Verify the current catalog and schema before coding. Record exact model/version and current unit costs in the pilot. |

## Minimal Python/OpenCV processing scope

Keep processing conservative and reproducible:

- Decode video and write selected source frames to a numbered folder; select diverse poses by default or choose uniform timestamps.
- Calculate per-frame foreground bounds or use an explicitly chosen segmentation method.
- Center or ground-align frames on one fixed-size canvas.
- Detect near-duplicate frames and produce a contact sheet for human selection.
- Export an atlas and a simple metadata file with source timestamps, frame order, dimensions, and pivot.

Do not automatically add motion blur, slash arcs, particles, or generated effects; the source prompt explicitly prohibits them. Make raw extracted frames available alongside cleaned outputs so processing decisions remain auditable.

## Pilot and acceptance criteria

Generate a short, single-attack clip from one approved character image. Select a compact set of action beats rather than blindly converting every video frame.

Measure:

- Percentage of extracted frames that pass design and weapon review.
- Variation in character bounding-box size and ground position.
- Number of duplicated/near-duplicate or unusable frames.
- Manual cleanup minutes and cost per accepted frame.
- Whether attack, recovery, and idle are readable in a real-time preview.

This option passes as a production candidate only if a useful proportion of frames remain consistent after curation and cleanup effort is lower than the alternatives. Otherwise, treat the output as motion reference for option 1 or option 3.

## First pilot result

One H3 Max Turbo clip was generated from the glaive-warrior reference with the project action prompt. The returned clip is 1152 × 768 at 24 fps with 124 frames (about 5.2 seconds). The motion-aware sampler produced eight distinct frames spanning the idle, attack, and recovery. Review the [contact sheet](../output/option2/contact_sheet.jpg) and [spritesheet preview](../output/option2/spritesheet.png); the source clip and timestamp metadata are saved alongside them in `output/option2/`.

The character remains recognizable and the attack/recovery are visible, so this is a promising motion-reference proof of concept. It is **not yet a production-ready sprite sheet**: at least one fast-action frame has a visible red motion-smear artifact despite the no-effects constraint, and the white video background is retained. Inspect the individual PNGs before using them, and do not pay for inpainting to repair video frames; inpainting is reserved for hidden pixels in the later cutout-part workflow. This single sample does not establish the success rate across multiple generations.

## Cost estimate

For the shared one-character pilot assumptions and cost formula, see [cost estimate](./cost-estimate.md). This option's variable is primarily the number and length of H3 Max Turbo clip generations; record the actual FAL quote/rate before running retries. Optional frame inpainting is not included in this extraction-only option.

## Local implementation

The project CLI is [generate_spritesheet.py](../scripts/generate_spritesheet.py). Install its dependencies with `python -m pip install -r requirements.txt`.

To process a clip that is already on disk without calling a paid API:

```powershell
python scripts\generate_spritesheet.py process path\to\clip.mp4 --output-dir output\option2 --selection diverse
```

To submit one generation using the default glaive reference and action prompt:

```powershell
python scripts\generate_spritesheet.py generate --yes
```

`generate` uploads the selected reference to fal.ai and can incur a charge; `--yes` is the explicit confirmation. The script reads `FAL_KEY`, `FAL_API`, or `FAL_API_KEY` from the process environment or project `.env` without printing it. Review the live endpoint pricing/schema before running. Output includes `source_video.mp4`, sampled PNGs under `frames\`, `spritesheet.png`, `contact_sheet.jpg`, and `metadata.json`. The processor preserves the video background and does not key out white or add effects. Diversity sampling may emit fewer than the requested frame count if the clip contains too few distinct-looking poses.

## Human work boundary

Humans approve the input design, inspect clip-level failures, select frames, and correct edges, pivots, or broken poses. OpenCV can extract and arrange pixels; it cannot reliably restore a changed character design or a physically broken weapon.

## Sources and verification

- [Action prompt](../prompt/action_prompt.txt) — supplied project prompt and visual constraints.
- [FAL Z-Image Turbo LoRA](https://fal.ai/models/fal-ai/z-image/turbo/lora) — possible reference-image creation/style stage; LoRA is not assumed to transfer into the video model.
- [fal MiniMax H3 Max Turbo image-to-video](https://fal.ai/models/minimax/h3-max-turbo/image-to-video) — requested animation-reference endpoint; confirm current API schema and billing in the model page/API response.

# Option 2 — Image-to-Video, Then Extract Sprite Frames

## Concept

Use a single approved character image as the video model's visual reference, request one brief attack and recovery, then extract and curate frames with Python/OpenCV. This is the fastest route to seeing whether the action prompt and design can produce a useful animation. The model's generated clip is an intermediate—not a finished spritesheet.

Proposed stack:

> Base image + compatible LoRA (if supported in the image-generation/reference stage) + [fal MiniMax H3 Max Turbo image-to-video](https://fal.ai/models/minimax/h3-max-turbo/image-to-video) + Python/OpenCV extraction, alignment, cleanup, and packing

The requested FAL endpoint is identified. Before implementation, verify its current API schema, supported image input, resolution/duration choices, pricing unit, and commercial-use terms. The endpoint's name alone does not guarantee the locked camera or weapon constraints in the generated clip.

## Workflow

1. **Prepare a padded input** — approve the right-facing reference and add blank canvas around it before video generation. The default CLI adds 25% of the source width to each horizontal side and 10% of the source height above and below, without scaling or cropping the character. This gives the weapon and limbs space to move; it cannot guarantee that the video model will never zoom, reframe, or crop them. Adjust padding if a test still clips.
2. **Send a short, controlled action prompt** — use the existing [action prompt](../prompt/action_prompt.txt) as the baseline. It specifies one fast polearm attack, return to idle, a locked orthographic camera, a singular physical weapon, and no added visual effects.
3. **Generate short clips** — keep the same input image and settings while comparing a small number of prompt/model settings. Record model ID/version, seed if available, duration, and generation parameters.
4. **Inspect the whole clip** — reject clips with camera motion, design changes, extra weapons/effects, implausible weapon deformation, clipping, or an unstable return pose. Do not use automated frame extraction to disguise these failures.
5. **Remove reference-like idle endpoints, then select usable frames** — compare the video's first and last frames with the reference after cropping/normalizing the visible subject. If either endpoint reaches the configurable similarity threshold (default `0.95`), omit that endpoint before selecting visually distinct or uniformly spaced poses. The measured similarities and trim decisions are saved to metadata; review them rather than treating the threshold as a universal perceptual metric. Retain original source-frame indices and timestamps so timing can be adjusted in the game.
6. **Optional background removal** — after reviewing the raw video and selected frames, run [BiRefNet v2](https://fal.ai/models/fal-ai/birefnet/v2) on the sampled images to create transparent PNGs. Keep original frames and atlas unchanged; write alpha results separately for edge review.
7. **Normalize** — crop/letterbox to a fixed canvas, align the ground point and character center, preserve the target right-facing orientation, and verify the alpha edges if background removal was run. Save individual frames and a sheet plus metadata (frame order, duration/timing, pivot).
8. **Review at target scale** — inspect the strip in motion at the intended frame rate and at actual in-game size. Hand-correct or discard failures.

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
| White background removal damages thin details or leaves halos | Use BiRefNet v2 on sampled frames and inspect the transparent results against the original; retain both versions. Avoid global color-key removal where white costume details may be lost. |
| Weapon or limbs are clipped by source/video framing | Add horizontal and vertical blank canvas around the input before generation; review the generated clip for model-induced zoom/reframing as well. |
| Frame cadence creates duplicates or uneven motion | Use timestamps and motion review to choose frames; remove redundant frames and set playback timing deliberately. |
| API model name, availability, or costs differ from expectations | Verify the current catalog and schema before coding. Record exact model/version and current unit costs in the pilot. |

## Minimal Python/OpenCV processing scope

Keep processing conservative and reproducible:

- Decode video and write selected source frames to a numbered folder; select diverse poses by default or choose uniform timestamps.
- Calculate per-frame foreground bounds or use an explicitly chosen segmentation method.
- Center or ground-align frames on one fixed-size canvas.
- Detect near-duplicate frames and produce a contact sheet for human selection.
- Export an atlas and a simple metadata file with source timestamps, frame order, dimensions, and pivot.
- Pad the source image on a clean background before upload and record source/canvas dimensions.
- Optionally call BiRefNet v2 once per selected frame; preserve raw frames and emit a separate alpha atlas.

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

### Padded-reference rerun

A second generation used the padded 2304 × 1228 reference and was saved separately under `output/option2_padded/`, preserving the first result. The returned clip is 1376 × 736 at 24 fps with 124 frames. The character and weapon fit comfortably within the frame, so padding improved the framing margin for this sample. However, the weapon changes orientation across poses and a bright streak is still visible during the attack; therefore padding addresses source-edge cropping risk but does not guarantee weapon continuity or obey the no-effects constraint. Review the [padded-run contact sheet](../output/option2_padded/contact_sheet.jpg), [spritesheet](../output/option2_padded/spritesheet.png), and [generation metadata](../output/option2_padded/metadata.json). This remains useful as motion reference, not a finished game sheet.

BiRefNet v2 background removal was then run on the eight sampled frames. Transparent outputs are in `output/option2_padded/frames_alpha/`; review the [alpha contact sheet](../output/option2_padded/contact_sheet_alpha.jpg) and [transparent spritesheet](../output/option2_padded/spritesheet_alpha.png). The original RGB frames, contact sheet, and spritesheet remain available. The output files contain non-opaque alpha, confirming transparency was produced; inspect fine hair, ribbon, and glaive edges at full size before game use.

### Increased vertical-padding rerun

A third paid generation used 25% padding on each edge horizontally and vertically, producing a 2304 × 1536 input canvas. The clip returned at 1152 × 768, 24 fps, 124 frames; BiRefNet v2 was applied to all eight selected frames. Outputs are isolated under `output/option2_tallpadding/`. Review its [raw contact sheet](../output/option2_tallpadding/contact_sheet.jpg), [transparent contact sheet](../output/option2_tallpadding/contact_sheet_alpha.jpg), and [transparent spritesheet](../output/option2_tallpadding/spritesheet_alpha.png).

This run contains distinct preparation/wind-up/attack/recovery poses, with the weapon and character fitting inside the frame in the selected images. The attack still includes a bright streak/smear, so more vertical padding did not prevent the model from inventing a visual effect. The original padded reference and source video are retained; this remains a promising motion reference rather than a compliant final animation sheet.

### Reference-matching idle endpoint rule

The local processor now compares the actual first and last video frames with the padded reference before frame selection. It crops and normalizes the visible subject, then uses normalized RGB similarity; endpoints at or above `0.95` are omitted. The threshold can be changed with `--reference-similarity-threshold`. Scores, the reference path, and removal decisions are recorded in `metadata.json`. This is a conservative heuristic, so inspect the reported scores and resulting sheet; it does not attempt to remove reference-like poses from the middle of a clip.

The existing tall-padded clip was reprocessed locally with no new generation or background-removal requests. The first and last frames scored `0.9847` and `0.9831`, respectively, and both were excluded before diverse pose selection. Review the regenerated [contact sheet](../output/option2_tallpadding_diverse_trimmed/contact_sheet.jpg), [spritesheet](../output/option2_tallpadding_diverse_trimmed/spritesheet.png), and [metadata](../output/option2_tallpadding_diverse_trimmed/metadata.json). The original video, eight earlier BiRefNet outputs, and their atlases were not modified; this regenerated output contains RGB frames only.

### Local rembg comparison

Tested [rembg](https://github.com/danielgatis/rembg) `2.0.85` with its `isnet-anime` model on the same eight raw frames used in the earlier BiRefNet run. It ran on CPU in an isolated temporary Python environment; the ONNX model (about 176 MB) was downloaded locally. No FAL request was made and `requirements.txt` was not changed. The [side-by-side comparison sheet](../output/option2_tallpadding_rembg_test/comparison_contact_sheet.jpg), [transparent rembg atlas](../output/option2_tallpadding_rembg_test/spritesheet_alpha.png), individual PNGs, and [per-frame metrics](../output/option2_tallpadding_rembg_test/test_metadata.json) are saved separately from prior results.

At alpha >127, rembg and BiRefNet masks had mean IoU `0.9592` across the eight frames. The lowest agreement was `0.8918` on frame 002, which contains the bright attack streak. Visual review shows rembg retains the character and weapon, but produces substantially more soft/partial-alpha pixels and some gray edge/ghosting around hair and motion-smear regions. The IoU is only a mask-agreement measure, not an image-quality score. This small test suggests rembg is a viable no-per-image-API-cost local alternative worth keeping for evaluation, but does not establish that it is better than BiRefNet; inspect fine edges and the smeared attack frame before choosing it for production. No project dependency or processing behavior was changed.

## Cost estimate

For the shared one-character pilot assumptions and cost formula, see [cost estimate](./cost-estimate.md). This option's variable is primarily the number and length of H3 Max Turbo clip generations; record the actual FAL quote/rate before running retries. Optional frame inpainting is not included in this extraction-only option.

## Local implementation

The project CLI is [generate_spritesheet.py](../scripts/generate_spritesheet.py). Install its dependencies with `python -m pip install -r requirements.txt`.

To process a clip that is already on disk without calling a paid API:

```powershell
python scripts\generate_spritesheet.py process path\to\clip.mp4 --output-dir output\option2 --selection diverse
```

To compare both clip endpoints against a reference explicitly:

```powershell
python scripts\generate_spritesheet.py process path\to\clip.mp4 --output-dir output\option2_trimmed --selection uniform --reference-image path\to\padded_reference.png --reference-similarity-threshold 0.95
```

If the input clip's folder contains `generation.json`, the CLI can locate its uploaded or original reference automatically; `--reference-image` overrides that lookup. Endpoint matching is local and does not call an API. This command does not create or modify transparent frames; background removal remains a separate optional step.

To preview the padded input canvas without uploading or calling an API:

```powershell
python scripts\generate_spritesheet.py prepare
```

To submit one generation using the default glaive reference and action prompt:

```powershell
python scripts\generate_spritesheet.py generate --yes
```

`prepare` previews the padded input locally without a network request. `generate` pads the source image, uploads the padded reference to fal.ai, and can incur a charge; `--yes` is the explicit confirmation. Defaults add 25% of the reference width to each side and 10% of its height to the top and bottom. Override them with `--horizontal-padding 0.35 --vertical-padding 0.15` (fractions per edge, from 0 to 1). Padding creates room but cannot force the video model to preserve framing. The script reads `FAL_KEY`, `FAL_API`, or `FAL_API_KEY` from the process environment or project `.env` without printing it. Review live endpoint pricing/schema before running. Default output includes `padded_reference.png`, `generation.json`, `source_video.mp4`, sampled PNGs under `frames\`, `spritesheet.png`, `contact_sheet.jpg`, and `metadata.json`. The video background is preserved by default. Add `--remove-background` to submit one BiRefNet v2 request per selected frame; this creates `frames_alpha\`, `spritesheet_alpha.png`, and `contact_sheet_alpha.jpg` without replacing originals. This flag can incur additional charges. For an existing clip, run `python scripts\generate_spritesheet.py process path\to\clip.mp4 --output-dir output\option2 --remove-background`; add `--yes` only after checking the current BiRefNet price. Diversity sampling may emit fewer than the requested frame count if the clip contains too few distinct-looking poses.

## Human work boundary

Humans approve the input design, inspect clip-level failures, select frames, and correct edges, pivots, or broken poses. OpenCV can extract and arrange pixels; it cannot reliably restore a changed character design or a physically broken weapon.

## Sources and verification

- [Action prompt](../prompt/action_prompt.txt) — supplied project prompt and visual constraints.
- [FAL Z-Image Turbo LoRA](https://fal.ai/models/fal-ai/z-image/turbo/lora) — possible reference-image creation/style stage; LoRA is not assumed to transfer into the video model.
- [fal MiniMax H3 Max Turbo image-to-video](https://fal.ai/models/minimax/h3-max-turbo/image-to-video) — requested animation-reference endpoint; confirm current API schema and billing in the model page/API response.
- [BiRefNet v2](https://fal.ai/models/fal-ai/birefnet/v2) — optional background-removal endpoint for sampled video frames.

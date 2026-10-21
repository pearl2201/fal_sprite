# Option 2 — Image-to-Video, Then Extract Sprite Frames

## Concept

Use a single approved character image as the video model's visual reference, request one brief attack and recovery, then extract and curate frames with Python/OpenCV. This is the fastest route to seeing whether the action prompt and design can produce a useful animation. The model's generated clip is an intermediate—not a finished spritesheet.

Proposed stack:

> Base image + compatible LoRA (if supported in the image-generation/reference stage) + [fal MiniMax H3 Max Turbo image-to-video](https://fal.ai/models/minimax/h3-max-turbo/image-to-video) + Python/OpenCV extraction, alignment, cleanup, and packing

The requested FAL endpoint is identified. Before implementation, verify its current API schema, supported image input, resolution/duration choices, pricing unit, and commercial-use terms. The endpoint's name alone does not guarantee the locked camera or weapon constraints in the generated clip.

## Workflow

1. **Prepare a padded input** — approve the right-facing reference and add blank canvas around it before video generation. This step is required, not optional: `generate` rejects zero padding. The default CLI adds 25% of the source width to each horizontal side and 10% of the source height above and below, without scaling or cropping the character. This gives the weapon and limbs space to move; it cannot guarantee that the video model will never zoom, reframe, or crop them. Adjust padding if a test still clips.
2. **Send a short, controlled action prompt** — use the existing [action prompt](../prompt/action_prompt.txt) as the baseline. It specifies one fast polearm attack, return to idle, a locked orthographic camera, a singular physical weapon, and no added visual effects.
3. **Generate short clips** — keep the same input image and settings while comparing a small number of prompt/model settings. Record model ID/version, seed if available, duration, and generation parameters.
4. **Inspect the whole clip** — reject clips with camera motion, design changes, extra weapons/effects, implausible weapon deformation, clipping, or an unstable return pose. Do not use automated frame extraction to disguise these failures.
5. **Remove reference-like idle endpoints, then select usable frames** — compare the video's first and last frames with the reference after cropping/normalizing the visible subject. If either endpoint reaches the configurable similarity threshold (default `0.95`), omit that endpoint before selecting visually distinct or uniformly spaced poses. The measured similarities and trim decisions are saved to metadata; review them rather than treating the threshold as a universal perceptual metric. Retain original source-frame indices and timestamps so timing can be adjusted in the game.
6. **Optional background removal** — after the spritesheet is built, run [BiRefNet v2](https://fal.ai/models/fal-ai/birefnet/v2) either on the packed sheet (default, one request per animation) or on each sampled frame (`--background-mode frames`, one request per frame). Keep original frames and atlas unchanged; write alpha results separately for edge review.
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
- Optionally call BiRefNet v2 on the packed atlas (one request) or once per selected frame (sharpest edges); preserve raw frames and emit a separate alpha atlas.

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

### Full animation set pilot

Seven H3 Max Turbo generations were run from the same padded glaive reference, one per required action, using per-action prompts under [prompt/animation_set](../prompt/animation_set). Each output is isolated in `output/option2_animation_set/<action>/` with its raw clip, eight sampled frames, RGB sheet, and metadata. Idle was sampled uniformly with reference endpoints kept so the loop could close; walk, run, attack, hurt, death, and skill used diverse sampling with reference-like endpoints trimmed.

BiRefNet v2 was then applied to all 56 selected frames (eight per action), producing `frames_alpha/`, `spritesheet_alpha.png`, `contact_sheet_alpha.jpg`, and a `background_removal` block in each `metadata.json`. Raw frames, RGB sheets, and source clips were preserved. Review the [combined overview](../output/option2_animation_set/animation_set_overview.jpg) and the [set index](../output/option2_animation_set/animation_set_index.json).

| Action | Frames | Notes |
|---|---:|---|
| Idle | 8 | Subtle breathing loop; endpoints kept. |
| Walk | 8 | Readable walk-in-place cycle; low motion produced few diverse frames, so uniform sampling was used. |
| Run | 8 | Energetic run cycle with clear stride phases. |
| Normal Attack | 8 | Wind-up through recovery; the model still inserted a bright streak in two mid-strike frames. |
| Hurt | 8 | Flinch and recovery; low motion, resampled uniformly. |
| Death | 8 | Controlled fall ending in a still ground pose. |
| Skill Attack | 8 | Broad polearm maneuver; also shows model-added streaks. |

These are consistent motion references, not final game-ready art. The streak artifacts violate the prompt constraints and need hand repair or discarding; the alpha edges and any weapon deformation must also be reviewed at full size.

### Combined review GIF

[build_animation_gif.py](../scripts/build_animation_gif.py) plays every animation in one GIF for motion review:

```powershell
python scripts\build_animation_gif.py
```

Default order is **idle → walk → run → normal attack → skill attack → hurt → death**, followed by any other animation folder found under the root, alphabetically. Override it with `--order idle,walk,run`. Frames come from `frames_alpha\` when present (`--prefer frames` uses the raw RGB frames instead), and each frame gets a `name n/total` label that `--no-label` hides.

The default run produced [animation_set.gif](../output/option2_animation_set/animation_set.gif): 56 frames, 480 × 336, 10 fps, 984 KiB, looping forever. `--hold-last` (default 2) doubles the final frame of each action so the end pose is readable; `--fps`, `--max-width`, `--background`, and `--loop` adjust playback and size. A `<output>.json` sidecar records the exact frame order for traceability. The script only reads PNGs, so it never calls an API.

### Second character run: horned skull-masked warrior

The full pipeline was repeated for [art_references/4.Horned Skull-Masked Armored Warrior.png](../art_references/4.Horned%20Skull-Masked%20Armored%20Warrior.png), a cleaver-and-shield design rather than a polearm. Per-action prompts were written for that specific loadout under [prompt/animation_set_skull_warrior](../prompt/animation_set_skull_warrior), because reusing the glaive prompts would have described the wrong weapon.

Run shape: seven H3 generations at `--horizontal-padding 0.30 --vertical-padding 0.20`, portrait source 1055 × 1491 padded to 1687 × 2087, clips returned at 768 × 960 / 24 fps / 124 frames. Idle used uniform sampling with endpoints kept; walk, run, and hurt used uniform; normal attack, death, and skill attack used diverse. BiRefNet ran once per packed sheet (`sheet` mode), so background removal cost 7 requests instead of 56. Outputs are under `output/option2_animation_set_skull_warrior/`.

Review the [set overview](../output/option2_animation_set_skull_warrior/animation_set_overview.jpg), [looping GIF](../output/option2_animation_set_skull_warrior/animation_set.gif), and [set index](../output/option2_animation_set_skull_warrior/animation_set_index.json).

| Action | Usable frames | Observed defects |
|---|---:|---|
| Idle | 8/8 | None; design, mask, cleaver, and shield stay consistent. |
| Hurt | 8/8 | None; readable flinch and recovery. |
| Walk | 5/8 | Frames 03, 06, 07 flatten the round shield into a capsule shape. |
| Normal Attack | 5/8 | Frames 03–05 contain large white motion-smear arcs, a prohibited effect. |
| Death | 5/8 | Frames 05–07 collapse the body into an unreadable mass. |
| Run | 2/8 | Frames 01–06 collapse the coat into a flat tan shape and deform the shield. |
| Skill Attack | 3/8 | Shield becomes a capsule in 02–04, frame 04 adds a smear arc, and 06–07 redraw the shield with different hardware. |

This is the clearest evidence so far that prompt constraints alone do not stop the model from inventing speed effects or deforming rigid props. Two practical levers, in order of cost: regenerate only the failing actions, or curate frames per action instead of accepting a fixed count. The cleaver-and-shield loadout is harder than the single polearm because two rigid objects must stay coherent through fast motion.

### Third character run: unarmed boxer with permitted VFX

The third run ([art_references/5.kien_nguyen.png](../art_references/5.kien_nguyen.png)) inverted the earlier constraint: the character has **no weapon at all** — two red boxing gloves — and the user explicitly asked for **strong VFX, particle effects, and splash trails**. Prompts live in [prompt/animation_set_kien_boxer](../prompt/animation_set_kien_boxer) and are driven by [manifests/kien_boxer.json](../manifests/kien_boxer.json).

The attack prompts were adapted to boxing rather than reusing a weapon template: normal attack is a jab–cross–hook combination and skill attack is a coiled uppercut into a spinning backfist. Weapon-continuity rules were replaced with glove-continuity rules ("exactly one glove per hand, always attached to an arm, never duplicated"), because the previous characters' failure mode was duplicated or deforming weapons.

Run shape: 7 H3 generations, `--horizontal-padding 0.35 --vertical-padding 0.25`, source 1312 × 1199 padded to 2230 × 1799, clips returned at 960 × 768 / 24 fps / 124 frames, 8 frames per action.

Background removal was run once for evaluation (7 sheet-mode requests), but a VFX set does not require it: the effects are the animation, so the set is reviewed and delivered from the raw frames. The manifest now uses `"background_remove_option": "none"`, so future reruns make **zero** background calls. The review GIF is built from raw frames with `--prefer frames`, and the earlier cutout variant is kept as `animation_set_alpha.gif` for comparison.

**Design lesson — VFX colour must contrast with the background.** The first draft of these prompts asked for white impact flashes, white speed streaks, and luminous white motion trails. That is the wrong choice twice over: white effects are nearly invisible on the pure-white generation background, and background removal then deletes them along with the background. The prompts were rewritten around a **saturated gold / crimson / black-ink** palette, and every effect survived BiRefNet segmentation. With that change, sheet-mode removal preserved the shockwave rings, ink splatter, dust, and motion trails in `spritesheet_alpha.png`.

| Action | Usable frames | Observed defects |
|---|---:|---|
| Idle | 8/8 | Clean loop; faint haze and dust motes only. |
| Walk | 8/8 | Dust puffs read well; scale stays consistent. |
| Run | 8/8 | Crimson speed streaks and dust; strongest locomotion clip so far. |
| Normal Attack | 8/8 | Jab, cross, and hook read clearly with gold flash, red rings, and black ink spatter. |
| Skill Attack | 4/8 | Frames 01–04 let the shockwave column swallow the torso, leaving the character unreadable; 05–07 show the backfist clearly. |
| Hurt | 5/8 | Frames 01–03 load so much black ink splatter that it covers the face and head. |
| Death | 8/8 | Clean knockdown and readable resting pose. |

Per-frame bounding-box cropping in the overview exaggerates apparent size changes, because VFX widen the box. The raw `contact_sheet.jpg` for each action is the accurate check for character scale.

This run shows the trade-off the earlier runs could not test: **permitting VFX fixes the model's unwanted smear problem on attacks — the effects are now intentional and styled — but heavy effects can occlude the character**. The fix is effect intensity, not suppression: keep the burst adjacent to the fist and let it clear before the next pose.

Because the effects are the animation, a VFX set should not require background removal. Keep `background_remove_option` at `none`, deliver `frames/` and `spritesheet.png`, and build the review GIF with `--prefer frames`.

### Fourth character run: grey-wasteland comedy character

[art_references/6_e_vuong.png](../art_references/6_e_vuong.png) is a comedic character whose attacks are a single booger throw and a single toxic-gas release. Prompts are in [prompt/animation_set_e_vuong](../prompt/animation_set_e_vuong), driven by [manifests/e_vuong.json](../manifests/e_vuong.json). The requested effects were "filthy wasteland" grey tones, so every VFX instruction names mid-grey, slate-grey, and sickly olive-grey explicitly — pale grey would have vanished on the white background.

Run shape: 7 H3 generations at `--horizontal-padding 0.5 --vertical-padding 0.5` (source 1312 × 1199 → 2624 × 2399 padded), clips returned at 832 × 768 / 24 fps / 124 frames, `background_remove_option: none` so background removal cost **0 requests**. Total: 7 video calls, 0 background calls.

Each prompt constrains the action to **one** execution: the normal attack throws exactly one projectile, and the skill releases exactly one gas burst, with no repeats inside the clip.

| Action | Frames | Notes |
|---|---:|---|
| Idle | 8 | Slow sway with grey haze at the ankles. |
| Walk | 8 | Waddling stride with grey dust puffs. |
| Run | 8 | Grey dust clouds, grit spray, slate speed streaks. |
| Normal Attack | 12 | Nose dig, glob loaded, one green projectile in flight with a splash trail, recovery. |
| Skill Attack | 8 | Turns away, bends over, single olive-green gas cloud with curling tendrils. |
| Hurt | 8 | Grey impact burst and dust, glasses knocked crooked. |
| Death | 8 | Backward flop into a dust cloud. |

**Framing trade-off with heavy padding.** At `0.5` on both axes the model frames the entire padded canvas, so the character occupies only about **15% of each 832 × 768 frame** (measured subject bounding box 265 × 367 px). The padding does prevent VFX clipping — the gas cloud and projectile both stay inside the frame — but it wastes a large amount of resolution. `diverse` sampling also returned only 5 frames for the normal attack and missed the airborne projectile, so it was re-sampled with `--selection uniform --frame-count 12`, which captures the whole beat. Re-sampling is free; no clip was regenerated.

### Fifth run: v2 reference with more VFX room

Re-ran the same seven actions from [art_references/7_e_vuong_v2.png](../art_references/7_e_vuong_v2.png), a redesigned version of the character: off-white cat-mascot t-shirt, black cargo shorts with a bear keychain, sneakers and socks, smartwatch. Fidelity lines were rewritten for the new outfit; prompts live in [prompt/animation_set_e_vuong_v2](../prompt/animation_set_e_vuong_v2) and the run is driven by [manifests/e_vuong_v2.json](../manifests/e_vuong_v2.json).

Padding was raised to `0.8` horizontal and `0.6` vertical (area ×5.6 versus ×4.0) specifically to give the projectile and gas cloud more empty space. Measured effect on the returned 992 × 768 frames: free margin grew to **36% left / 38% right**, with the subject still 43% of frame height.

| Action | Frames | Notes |
|---|---:|---|
| Idle | 8 | Grey haze at the ankles, wide framing. |
| Walk | 8 | Compact grey dust puffs at each foot plant. |
| Run | 8 | Dust clouds, grit spray, slate speed streaks. |
| Normal Attack | 12 | The green glob now travels across a wide empty lane with a long splash trail before leaving frame. |
| Skill Attack | 8 | Large olive-grey cloud billows out and stays fully inside frame. |
| Hurt | 8 | Grey impact burst and dust. |
| Death | 8 | Backward flop into a dust cloud. |

Extra padding achieved the goal: neither the projectile nor the gas cloud touches a frame edge. Outputs are under `output/option2_animation_set_e_vuong_v2/`.

**Bug fixed during this run:** `_normalized_subject` loaded full-resolution images into numpy before downscaling, which raised `MemoryError` on a machine with ~4 GB free while comparing the reference. It now thumbnails to `working_size` (512 px) before array work, so similarity scoring is bounded regardless of reference or frame size. The walk clip had already downloaded, so the resumed run reused it instead of paying for another generation.

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

If the input clip's folder contains `generation.json`, the CLI can locate its uploaded or original reference automatically; `--reference-image` overrides that lookup. Endpoint matching is local and does not call an API. Add `--keep-reference-endpoints` for looping clips such as idle, where the matching first and last frames are wanted rather than trimmed. This command does not create or modify transparent frames; background removal remains a separate optional step.

To generate one animation from a per-action prompt into its own folder:

```powershell
python scripts\generate_spritesheet.py generate --prompt prompt\animation_set\run.txt --output-dir output\option2_animation_set\run --horizontal-padding 0.25 --vertical-padding 0.25 --yes
```

Add `--keep-reference-endpoints` for idle. Each `generate` call submits one potentially paid H3 request; `--remove-background` adds one BiRefNet request per animation (sheet mode) or one per sampled frame (`--background-mode frames`).

To preview the padded input canvas without uploading or calling an API:

```powershell
python scripts\generate_spritesheet.py prepare
```

To submit one generation using the default glaive reference and action prompt:

```powershell
python scripts\generate_spritesheet.py generate --yes
```

`prepare` previews the padded input locally without a network request. `generate` pads the source image, uploads the padded reference to fal.ai, and can incur a charge; `--yes` is the explicit confirmation. Defaults add 25% of the reference width to each side and 10% of its height to the top and bottom. Override them with `--horizontal-padding 0.35 --vertical-padding 0.15` (fractions per edge, from 0 to 1). Padding creates room but cannot force the video model to preserve framing. The script reads `FAL_KEY`, `FAL_API`, or `FAL_API_KEY` from the process environment or project `.env` without printing it. Review live endpoint pricing/schema before running. Default output includes `padded_reference.png`, `generation.json`, `source_video.mp4`, sampled PNGs under `frames\`, `spritesheet.png`, `contact_sheet.jpg`, and `metadata.json`. The video background is preserved by default.

### Batch runs from a manifest

[run_batch.py](../scripts/run_batch.py) runs the whole flow for one or more characters described in JSON, so a set can be reproduced from one file instead of seven commands:

```powershell
python scripts\run_batch.py manifests\characters.example.json --dry-run
python scripts\run_batch.py manifests\characters.example.json --yes
```

Each entry supplies the reference image, padding, animation-to-prompt mapping, and `background_remove_option` (`spritesheet`, `frames`, or `none`). Relative paths resolve against the project root, and the key order of `animations_prompt` becomes the GIF and overview order. Re-running is cheap: a clip whose `source_video.mp4` already exists is reused unless `--force` is passed, so a failed action can be retried without re-paying for finished ones. `--dry-run` reports the exact number of video generations and background requests, `--only NAME` narrows the run, and `--skip-background` or `--skip-report` isolate stages. A `<manifest>.report.json` is written after each run.

The manifest schema, all field defaults, and the CLI options are documented in the [README](../README.md#batch-manifest), and [.github/skills/fal-spritesheet-pipeline/SKILL.md](../.github/skills/fal-spritesheet-pipeline/SKILL.md) captures the operating procedure for agents. [animation_set_report.py](../scripts/animation_set_report.py) builds the overview and index for an existing set without any API call.

### Background removal call count

`--remove-background` runs only after `spritesheet.png` exists, and `--background-mode` decides how many paid BiRefNet requests that costs:

| Mode | Requests per animation | Trade-off |
|---|---:|---|
| `sheet` (default) | 1 | Entire atlas is resized to BiRefNet's operating resolution, so each character gets fewer mask pixels. |
| `frames` | 1 per sampled frame (8 by default) | Full per-character resolution and sharper edges. |

Both modes write `frames_alpha\`, `spritesheet_alpha.png`, and `contact_sheet_alpha.jpg` without replacing originals, and both record `mode` and `api_calls` in `metadata.json`. Sheet mode crops the returned atlas back into per-frame PNGs using the saved layout.

Measured on the idle clip: sheet mode produced one mask per eight frames with mean IoU `0.9417` against the per-frame result and raised the partial-alpha share from `2.3%` to `5.5%`, which is the expected softness from downscaling a 4608 × 1536 atlas. Visual comparison at full size was close, so sheet mode is a reasonable default for review passes; use `frames` mode for final art where thin glaive and hair edges matter.

For an existing clip, run `python scripts\generate_spritesheet.py process path\to\clip.mp4 --output-dir output\option2 --remove-background`; add `--yes` only after checking the current BiRefNet price. Diversity sampling may emit fewer than the requested frame count if the clip contains too few distinct-looking poses.

## Human work boundary

Humans approve the input design, inspect clip-level failures, select frames, and correct edges, pivots, or broken poses. OpenCV can extract and arrange pixels; it cannot reliably restore a changed character design or a physically broken weapon.

## Sources and verification

- [Action prompt](../prompt/action_prompt.txt) — supplied project prompt and visual constraints.
- [FAL Z-Image Turbo LoRA](https://fal.ai/models/fal-ai/z-image/turbo/lora) — possible reference-image creation/style stage; LoRA is not assumed to transfer into the video model.
- [fal MiniMax H3 Max Turbo image-to-video](https://fal.ai/models/minimax/h3-max-turbo/image-to-video) — requested animation-reference endpoint; confirm current API schema and billing in the model page/API response.
- [BiRefNet v2](https://fal.ai/models/fal-ai/birefnet/v2) — optional background-removal endpoint for the packed spritesheet or individual sampled frames.

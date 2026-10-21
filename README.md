# FAL Sprite Sheet Pipeline

Generate game-character animation sets from a single character reference image using FAL image-to-video, local frame extraction, and AI background removal.

The pipeline turns one approved character illustration into per-action spritesheets (`idle`, `walk`, `run`, `normal_attack`, `skill_attack`, `hurt`, `death`) plus transparent atlases, contact sheets, a combined review GIF, and machine-readable metadata.

```
reference image
  -> padded canvas (required)
  -> H3 Max Turbo image-to-video (one clip per action)
  -> frame sampling + reference-matching endpoint trim
  -> BiRefNet v2 on the packed spritesheet (one request per action)
  -> atlas + contact sheet + metadata
  -> overview / index / GIF
```

This is a research and prototyping tool. Output is a motion reference, not finished game art: review every clip for model-invented effects and prop deformation before use.

## Requirements

- Python 3.11+
- A FAL API key
- The dependencies in [requirements.txt](requirements.txt)

```powershell
python -m pip install -r requirements.txt
```

Create `.env` in the project root with either variable name:

```
FAL_API=your-key-here
```

`FAL_KEY` and `FAL_API_KEY` are also accepted. The key is read from the environment or `.env` and is never printed.

## Quick start

Preview the padded reference without any network call:

```powershell
python scripts\generate_spritesheet.py prepare
```

Run one action end to end, including background removal:

```powershell
python scripts\generate_spritesheet.py generate `
  --reference "art_references\4.Horned Skull-Masked Armored Warrior.png" `
  --prompt "prompt\animation_set_skull_warrior\idle.txt" `
  --output-dir "output\option2_animations\skull_warrior\idle" `
  --selection uniform --keep-reference-endpoints --remove-background --yes
```

Run a whole animation set from a manifest (recommended):

```powershell
python scripts\run_batch.py manifests\characters.example.json --dry-run
python scripts\run_batch.py manifests\characters.example.json --yes
```

Build the review GIF and overview for an existing set:

```powershell
python scripts\build_animation_gif.py --root output\option2_animation_set_skull_warrior
python scripts\animation_set_report.py --root output\option2_animation_set_skull_warrior
```

## Commands

| Command | API calls | Purpose |
|---|---|---|
| `generate_spritesheet.py prepare` | none | Preview the padded reference canvas |
| `generate_spritesheet.py generate` | 1 video + optional background removal | Generate a clip and process its frames |
| `generate_spritesheet.py process` | optional background removal | Re-sample an existing clip without generating |
| `rerun_animation.py` | 1 video only if the clip is missing | Rerun one action and refresh the set's reports |
| `run_batch.py` | per manifest | Full pipeline for one or more characters |
| `build_animation_gif.py` | none | Combine all actions into one ordered GIF |
| `animation_set_report.py` | none | Build the overview image and JSON index |

Run any command with `--help` for its full option list.

### Rerun one action

`rerun_animation.py` redoes a single action inside an existing set, then rebuilds the overview, index, and GIF so the set stays consistent:

```powershell
# Re-sample from the saved clip: no API call at all
python scripts\rerun_animation.py --character skull_warrior --animation walk --background-mode none

# Generate a new clip for one action (1 paid video + background removal)
python scripts\rerun_animation.py --character skull_warrior --animation skill_attack `
  --prompt "prompt\animation_set_skull_warrior\skill_attack.txt" --yes

# Add a brand-new action name to an existing character
python scripts\rerun_animation.py --character skull_warrior --animation emote_wave `
  --prompt "prompt\animation_set_skull_warrior\emote_wave.txt" --yes
```

The reference and padding are recovered from the set's `generation.json`, so a rerun matches the original framing without retyping values. Any animation name is accepted, not just the seven defaults. Without `--force`, an existing `source_video.mp4` is reused and no video generation is charged.

## Batch manifest

A manifest is either a JSON array of character entries, or an object with a `characters` array. See [manifests/characters.example.json](manifests/characters.example.json).

```json
[
  {
    "name": "skull_warrior",
    "image_references": "art_references/4.Horned Skull-Masked Armored Warrior.png",
    "padding_width": 0.30,
    "padding_height": 0.20,
    "animations_prompt": {
      "idle": "prompt/animation_set_skull_warrior/idle.txt",
      "walk": "prompt/animation_set_skull_warrior/walk.txt",
      "normal_attack": "prompt/animation_set_skull_warrior/normal_attack.txt"
    },
    "background_remove_option": "spritesheet"
  }
]
```

Relative paths resolve against the project root. The order of keys in `animations_prompt` is the order used for the GIF and overview.

### Fields

| Field | Required | Default | Notes |
|---|---|---|---|
| `name` | no | slug of the reference filename | Used for the default output folder |
| `image_references` | yes | — | One image per entry; use a string or a one-item list |
| `padding_width` | no | `0.25` | Fraction of width added **per** horizontal edge; must be > 0 |
| `padding_height` | no | `0.10` | Fraction of height added **per** vertical edge; must be > 0 |
| `animations_prompt` | yes | — | Map of animation name to prompt path, or list of single-key objects |
| `background_remove_option` | no | `spritesheet` | `spritesheet`, `frames`, or `none` |
| `output_root` | no | `output/option2_animation_set/<name>` | Output folder for the character |
| `frame_count` | no | `8` | Frames sampled per action |
| `columns` | no | `4` | Atlas columns |
| `overview` | no | `true` | Build the overview image |
| `gif` | no | `true` | Build the combined GIF |

An animation may also be an object for finer control:

```json
"animations_prompt": {
  "idle": { "prompt": "prompt/idle.txt", "selection": "uniform", "keep_endpoints": true },
  "run": { "prompt": "prompt/run.txt", "selection": "diverse", "frame_count": 10 }
}
```

Defaults per animation: `idle`, `walk`, `run`, and `hurt` use `selection: uniform`; everything else uses `diverse`. `keep_endpoints` defaults to `true` only for `idle`, so a loop keeps its matching first and last frames.

### Batch options

| Option | Effect |
|---|---|
| `--dry-run` | Print the plan and estimated paid calls; generate nothing |
| `--only NAME` | Run one character; repeatable |
| `--force` | Regenerate clips even when `source_video.mp4` already exists |
| `--skip-background` | Skip paid background removal |
| `--skip-report` | Skip overview, index, and GIF |
| `--yes` | Required to perform paid work |

Without `--yes` the batch prints the plan and exits with code `2`. Existing clips are reused by default, so re-running a manifest after a failure does not re-pay for finished actions. A `<manifest>.report.json` is written after each run.

## Defaults and guardrails

1. **The reference is always padded before generation.** `generate` rejects zero padding. Without margins the model clips weapons and limbs; the unpadded first pilot cut off the glaive.
2. **Background removal runs on the packed spritesheet, not per frame.** One BiRefNet request per action instead of one per frame — 7 instead of 56 for a seven-action set. Pass `--background-mode frames` when final-art edge fidelity matters more than cost.
3. **Clipped endpoints are only trimmed when they match the reference.** The first and last video frames are compared with the reference (default threshold `0.95`); scores and decisions are recorded in `metadata.json`.

### Background removal modes

| Mode | Requests per action | Trade-off |
|---|---:|---|
| `sheet` (default) | 1 | Atlas is downscaled to BiRefNet's operating resolution, so edges are softer |
| `frames` | 1 per sampled frame | Full per-character resolution |

Measured on one clip: sheet mode scored `0.9417` mean IoU against per-frame mode and raised the partial-alpha share from `2.3%` to `5.5%`.

## Output layout

```
output/<set>/
  animation_set_overview.jpg
  animation_set_index.json
  animation_set.gif
  <action>/
    source_video.mp4          # raw generated clip
    padded_reference.png      # exact image sent to the video model
    generation.json           # endpoint + padding provenance
    frames/frame_000.png ...  # sampled RGB frames
    frames_alpha/             # transparent frames
    spritesheet.png           # RGB atlas
    spritesheet_alpha.png     # transparent atlas
    contact_sheet.jpg
    contact_sheet_alpha.jpg
    metadata.json             # timings, selection, endpoint rule, background removal
```

`metadata.json` maps each output frame to its `source_frame` index and `timestamp_seconds`, which is what you need to pull replacement frames from `source_video.mp4` during manual repair.

## Cost control

Every paid step is explicit:

- `generate` and `run_batch.py` require `--yes`.
- `run_batch.py --dry-run` reports the exact number of video generations and background-removal requests, accounting for already-generated clips.
- `--skip-background` isolates the video spend.
- `process` never calls the video model, so re-sampling a clip is free.

See [document/cost-estimate.md](document/cost-estimate.md) for per-option estimates and observed usage.

## Known limitations

- Fast motion can make the video model invent smear arcs even when the prompt forbids effects, and can deform rigid props such as shields and blades. Both were observed on real runs.
- Low-motion actions (`idle`, `walk`, `hurt`) yield few visually distinct frames; using `selection: uniform` keeps the requested frame count, at the cost of subtle differences between frames.
- Frame timing in the GIF is uniform playback, not true clip timing. Source timestamps are preserved in metadata if you need accurate timing.
- Background removal quality depends on the source brushwork; inspect thin shapes such as horns, tassels, and blade edges at full size.

## Project structure

| Path | Purpose |
|---|---|
| [scripts/generate_spritesheet.py](scripts/generate_spritesheet.py) | Padding, generation, sampling, background removal |
| [scripts/run_batch.py](scripts/run_batch.py) | Manifest-driven multi-character runner |
| [scripts/rerun_animation.py](scripts/rerun_animation.py) | Rerun a single action and refresh set reports |
| [scripts/build_animation_gif.py](scripts/build_animation_gif.py) | Ordered review GIF |
| [scripts/animation_set_report.py](scripts/animation_set_report.py) | Overview image and JSON index |
| [prompt/](prompt) | Per-action prompt sets, one folder per character |
| [art_references/](art_references) | Approved character reference images |
| [manifests/](manifests) | Example batch manifests |
| [AGENTS.md](AGENTS.md) | Conventions and guardrails for AI agents |
| [document/](document) | Research, workflow, and cost documentation |
| [tests/](tests) | Unit tests (no network access) |

## Tests

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Tests cover padding, frame sampling, endpoint trimming, background-removal request counting, manifest validation, and report generation. They use temporary directories and mock the FAL client, so they never make paid calls.

## Documentation

- [Research overview](document/overview.md)
- [Option 2 workflow](document/option-2-video-frames.md)
- [Cost estimate](document/cost-estimate.md)
- [Option 1: pose-guided 2D](document/option-1-pose-guided-2d.md)
- [Option 3: AI 3D + Blender](document/option-3-ai-3d-blender.md)
- [Option 4: LoRA + video + inpainting + Unity](document/option-4-lora-video-inpaint-unity.md)
- [Agent skill (.github/skills/fal-spritesheet-pipeline)](.github/skills/fal-spritesheet-pipeline/SKILL.md) — operating procedure and guardrails for automated runs
- [AGENTS.md](AGENTS.md) — repository conventions for AI coding agents

## External services

This project calls third-party endpoints and your use is subject to their terms and pricing:

- [MiniMax H3 Max Turbo image-to-video](https://fal.ai/models/minimax/h3-max-turbo/image-to-video)
- [BiRefNet v2](https://fal.ai/models/fal-ai/birefnet/v2) for background removal

Verify current schema, availability, and per-call pricing before running a paid workload. Character reference art remains the property of its creator; confirm you have the rights to use and publish any derived assets.

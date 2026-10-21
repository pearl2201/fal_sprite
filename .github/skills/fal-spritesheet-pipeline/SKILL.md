---
name: fal-spritesheet-pipeline
description: Generate a game-character animation set (idle, walk, run, normal attack, skill attack, hurt, death) from one character reference image using this repo's FAL pipeline. USE FOR: creating or regenerating spritesheets, running the H3 image-to-video plus BiRefNet flow, writing per-action prompts for a new character, authoring or debugging a batch manifest, rebuilding the review GIF/overview, or investigating why frames are clipped, deformed, or smeared. DO NOT USE FOR: generic FAL API questions unrelated to this pipeline, Unity/Spine rigging work, or Tripo 3D generation (see the Option 3 document).
---

# FAL Spritesheet Pipeline

Turns one approved character illustration into per-action spritesheets with transparent atlases, a review GIF, and metadata.

## Hard rules

1. **Never run a paid step without explicit user confirmation.** `generate` and `run_batch.py` need `--yes`. Always show `--dry-run` output first and state the exact call count.
2. **Always pad the reference.** `generate` rejects zero padding. Defaults are `0.25` width per horizontal edge and `0.10` height per vertical edge. Without margins the model clips weapons and limbs.
3. **Keep background removal on the packed sheet by default** (`--background-mode sheet`, or `"background_remove_option": "spritesheet"`). That is one BiRefNet request per action instead of one per frame. Use `frames` only when the user asks for sharper final-art edges.
4. **Never print or commit the FAL key.** It comes from `.env` (`FAL_API`, `FAL_KEY`, or `FAL_API_KEY`).
5. **Preserve prior outputs.** Write to a new folder rather than overwriting a reviewed set unless the user asks for a rebuild.

## Workflow

1. Read the reference image and describe the actual loadout. Do not reuse prompts written for a different weapon; a polearm prompt on a cleaver-and-shield character produces wrong props.
2. Create per-action prompts under `prompt/<set>/` for `idle`, `walk`, `run`, `normal_attack`, `skill_attack`, `hurt`, `death`. Each prompt must state: fixed orthographic side view, locked camera, constant scale, full body plus props inside frame, explicit "no trails/arcs/afterimages/particles", prop continuity (one blade, one shield), and preserving costume and palette.
3. Choose sampling per action. Cyclic or low-motion actions (`idle`, `walk`, `run`, `hurt`) use `uniform`; one-shot key-pose actions (`normal_attack`, `skill_attack`, `death`) use `diverse`. Set `keep_endpoints` for loops such as idle.
4. Preview the padded canvas and the plan before spending:
   ```powershell
   python scripts\generate_spritesheet.py prepare --reference "<reference>" --horizontal-padding 0.30 --vertical-padding 0.20
   python scripts\run_batch.py <manifest>.json --dry-run
   ```
5. Generate one clip first and inspect its contact sheet before committing the rest of the set. Confirm the returned aspect ratio and that nothing is cropped.
6. Run the remaining actions, then background removal, then reports.
7. Inspect the result before declaring success (see Verification).

## Commands

```powershell
# One action, end to end
python scripts\generate_spritesheet.py generate `
  --reference "<image>" --prompt "prompt\<set>\<action>.txt" `
  --output-dir "output\<set>\<action>" --selection uniform --keep-reference-endpoints `
  --horizontal-padding 0.30 --vertical-padding 0.20 --remove-background --yes

# Whole set from a manifest
python scripts\run_batch.py manifests\characters.json --dry-run
python scripts\run_batch.py manifests\characters.json --only skull_warrior --yes

# Re-sample an existing clip with no API call
python scripts\generate_spritesheet.py process "output\<set>\<action>\source_video.mp4" `
  --output-dir "output\<set>\<action>" --selection uniform --reference-image "<reference>"

# Reports (no API calls)
python scripts\build_animation_gif.py --root "output\<set>"
python scripts\animation_set_report.py --root "output\<set>"
```

Useful flags: `--force` regenerates cached clips, `--skip-background` isolates video spend, `--skip-report` skips overview/index/GIF, `--reference-similarity-threshold` tunes endpoint trimming.

## Manifest schema

Array of entries, or an object with a `characters` array. Relative paths resolve against the project root.

```json
[
  {
    "name": "skull_warrior",
    "image_references": "art_references/4.Horned Skull-Masked Armored Warrior.png",
    "padding_width": 0.30,
    "padding_height": 0.20,
    "animations_prompt": {
      "idle": { "prompt": "prompt/skull/idle.txt", "selection": "uniform", "keep_endpoints": true },
      "walk": "prompt/skull/walk.txt"
    },
    "background_remove_option": "spritesheet"
  }
]
```

`background_remove_option` accepts `spritesheet`, `frames`, or `none`. Key order in `animations_prompt` becomes GIF and overview order. Copy [manifests/characters.example.json](../../../manifests/characters.example.json) as a starting point.

## Verification

Do not claim success from exit codes alone:

1. Open each `contact_sheet.jpg` and check for model-added smear arcs, duplicated props, deformed rigid objects, and costume drift.
2. Open `spritesheet_alpha.png` and check that alpha covers the whole subject with no gray halos or missing horns, tassels, or blade tips.
3. Confirm `metadata.json` has a `background_removal` block with `mode` and `api_calls`, and that `sampled_frame_count` equals the frames you intended.
4. Open the GIF to confirm action order and that each action ends on a readable pose.
5. Confirm raw `frames/`, `spritesheet.png`, and `source_video.mp4` still exist untouched.
6. Run `python -m unittest discover -s tests -p "test_*.py"` after any code change.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Weapon or limbs cropped | Insufficient padding, or model reframing | Raise `--horizontal-padding` / `--vertical-padding`; regenerate |
| Only 2-4 frames produced | `diverse` sampling on a low-motion clip | Re-run `process` with `--selection uniform` (no API cost) |
| Bright arcs or streaks | Model-invented speed effects | Cannot be fixed by threshold tuning; regenerate the action or discard those frames |
| Shield or blade changes shape | Rigid prop deformation during fast motion | Regenerate; two-prop characters fail more often than single-weapon ones |
| Idle loop jumps | Endpoints were trimmed | Set `--keep-reference-endpoints` / `"keep_endpoints": true` |
| `FAL_KEY is missing` | `.env` not loaded | Add `FAL_API=<key>` to `.env` in the project root |
| Batch refuses to run | Missing `--yes` | Review `--dry-run`, then add `--yes` |

## Reporting

State the paid call count (video generations and background requests separately), list per-action usable frame counts with the specific defect frames, and link the overview, GIF, index, and each atlas. Record findings in `document/option-2-video-frames.md` and update `document/cost-estimate.md` when the number of calls changes.

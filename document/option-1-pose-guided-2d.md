# Option 1 — Pose-Guided 2D Frame Generation

## Concept

Generate individual animation frames from a fixed set of pose guides rather than asking a video model to invent the whole movement. Use a consistent image-generation base model and a compatible character/style LoRA, with OpenPose or another supported pose condition to control body posture. Assemble and align accepted frames into a spritesheet.

Proposed stack:

> Base image model + compatible character/style LoRA + pose-conditioned generation (OpenPose/ControlNet) + frame cleanup and packing

The FAL Z-Image Turbo LoRA endpoint is a candidate for the base-plus-LoRA part: its model page describes text-to-image generation, up to three inference-time LoRAs, and batch output. Do not assume it supports ControlNet/OpenPose: the cited page does not document pose-conditioning inputs. If it cannot accept the required control image, select a separate compatible pose-conditioned endpoint/model. A LoRA must be compatible with that model's architecture; LoRAs are not generally interchangeable across unrelated checkpoints.

## Workflow

1. **Lock the design** — approve one front/side character reference, weapon design, palette, and orthographic game-view target. Record model/checkpoint, LoRA version and license.
2. **Plan animation beats** — make a pose strip for the attack (anticipation, wind-up, attack, follow-through, recovery, idle). Create one skeleton/pose map with consistent scale and facing direction. A human should review this map before expensive generation.
3. **Generate candidates** — generate each key pose with the same reference, prompt core, seed strategy where supported, model, LoRA, resolution, and camera description. Keep per-frame variation limited to pose and action beat.
4. **Review and repair** — reject frames with changed costume, face, weapon, silhouette, orientation, or crop. Use inpainting/manual edits for small defects; do not rely on post-processing to repair a fundamentally different design.
5. **Normalize and pack** — crop to a shared character canvas, align a stable ground/contact point, preserve transparent background if the generation path supports reliable masking, and export individual PNGs plus a uniformly sized sheet and frame metadata.
6. **Validate in-game** — play the sequence at the target frame rate and inspect silhouette readability, timing, pivots, and clipping at actual game scale.

## Strengths

- Explicit poses give direct control over timing and silhouette and make missed or unwanted beats easy to identify.
- Frames can be regenerated individually, which localizes corrections.
- No 3D rig is required; the workflow can stay close to a hand-painted sprite art direction.
- The selected FAL page lists batched image generation and LoRA inference support, useful for fast candidate iteration.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| The selected endpoint does not accept pose conditioning | Prove the pose-control input with one test request before implementing a batch workflow. Change endpoint if unsupported. |
| A LoRA is incompatible with the pose model's base checkpoint | Verify the LoRA's exact supported model family and test it on the chosen endpoint. Do not infer compatibility from a model page title. |
| Face, costume, proportions, or weapon drift frame to frame | Use a stable reference and pose guides; generate small batches, compare contact sheets, and reject failures rather than accepting every output. |
| AI changes weapon geometry or creates duplicate/ghost weapons | Keep the prompt's strict weapon constraints; inspect every frame at full size. If needed, separate the weapon layer for controlled compositing or manual correction. |
| Background removal damages thin details | Generate on a consistent flat background, test masking on hair and weapon edges, and preserve a manual alpha-cleanup step. |
| Per-frame generation is slow or costly | Generate only reviewed key poses first, then decide whether in-between frames can be interpolated without artifacts. Measure cost per accepted frame, not per request. |

## Pilot and acceptance criteria

Use one character and one action. Produce a short side-view attack that starts and ends at the same idle pose. Include a small set of key poses first; expand to the full target frame count only after the character and pose controls pass review.

For the pilot, record:

- Accepted frames / generated candidates.
- Character-design, weapon, facing, and scale consistency.
- Manual cleanup minutes per accepted frame.
- Generation time and cost per accepted frame.
- Whether the final sheet loops/recoveries cleanly at the intended game frame rate.

Pass only if the key poses are readable at game scale, the character and singular weapon remain recognizable, the framing is stable, and all required action beats can be generated without extensive redrawing.

## Human work boundary

Human approval is needed for the pose strip, final frame selection, edge cleanup, and timing. This option avoids rigging but does not remove frame-by-frame art direction and quality control.

## Cost estimate

See [per-character cost estimate](./cost-estimate.md). The estimate uses 28 approximately 1MP candidate images (four reference candidates plus 24 pose candidates) and up to four 1024² FLUX Fill repairs, yielding a proxy of **about $0.25-$0.65** at the published Z-Image LoRA and FLUX Fill rates. Z-Image Turbo LoRA is not documented as pose-conditioned; the actual compatible pose endpoint and any control-model charges may change this estimate.

## Sources and verification

- [FAL Z-Image Turbo LoRA](https://fal.ai/models/fal-ai/z-image/turbo/lora) — model page reports a text-to-image API, LoRA support, and batching. Confirm current schema, dimensions, pricing, and account availability.
- [Civitai Character Design Sheet Helper](https://civitai.com/models/100435/character-design-sheet-helper-3-perspectivescolor-palette-z-image-turbo-or-illustrious-xl-or-flux-or-xl-pony-or-sd-15-by-yeiyeiart) — candidate reference only. The page could not be inspected in this research pass; verify file, checkpoint compatibility, and license directly before use.

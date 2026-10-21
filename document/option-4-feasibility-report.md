# Option 4 — Feasibility and Requirement Verification

Verification date: 2026-10-22. Scope: research, implementation, and Unity pilot; paid calls were explicitly authorized.

## Verdict

Option 4 is **not production-ready**. It is technically explorable and produces a convincing prototype, but two production requirements are unmet:

1. **Segmentation is not pixel-faithful or reliably separated.** EVF-SAM fails on overlapping limbs. Seedream `layerize` produces clean named parts, but it regeneratively redraws them, re-compositing is not identical to the source, and the model's z-order puts the weapon behind the torso. Manual cleanup and manual z-order are required.
2. **Automated rigging is not available at production quality.** Unity MCP can create sprites, objects, and scenes, but no reliable automated bone/weight authoring or video-to-pose retargeting was found. The current Unity results are hand-built: a 5-sprite rigid cutout with hand-authored keys and a static 14-layer assembly.

Everything else (Unity 2D Animation availability, inpaint endpoints, H3 parameterization, layer import) checks out. The option should be clearly labeled **prototype only** until manual layered art and manual rigging are accepted as part of the workflow.

## Verified facts

### Unity

- Unity **6000.0.59f2** and **2022.3.62f2** are installed. Chosen target: Unity 6.
- Unity 6 ships `com.unity.2d.animation` **10.2.1** in its package cache:
  `/Applications/Unity/Hub/Editor/6000.0.59f2/Unity.app/Contents/Resources/PackageManager/Editor/com.unity.2d.animation-10.2.1.tgz`
- The built-in `com.unity.feature.2d` feature set includes `com.unity.2d.animation` and `com.unity.2d.psdimporter`.
- A Unity 2D project template is present (`com.unity.template.2d-cross-platform-5.1.0.tgz`).
- **Unity MCP is unavailable**: the tool bridge returned `ECONNREFUSED 127.0.0.1:8080`. No Unity project files exist under the repository root.
- Spine is not installed. It remains an unlicensed fallback, as the document states.

Consequence: rigging, bone creation, weight painting, clip authoring, and export cannot be automated or validated today. For the pilot, either start the Unity MCP bridge and verify its write surface, or use Unity `-batchmode -executeMethod` with an editor script, or do the rig manually.

### FAL endpoints

Schemas were read from `https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=...` (no paid call made).

| Endpoint | Verified input requirement | Notes |
|---|---|---|
| `minimax/h3-max-turbo/image-to-video` | `prompt`, `prompt_expansion_mode` required; `image_url` optional | `duration` 0.92-15 s, default 5; `resolution` `480P`/`768P`/`1080P`; optional `end_image_url`, `seed` |
| `fal-ai/inpaint` | `model_name`, `prompt`, `image_url`, `mask_url` | White mask areas are inpainted, black preserved. Requires choosing a base model, so it is not a turnkey inpaint endpoint. |
| `fal-ai/flux-pro/v1/fill` | `prompt`, `image_url`, `mask_url` | Mask must match image dimensions; `num_images` supported |
| `fal-ai/evf-sam` | `prompt`, `image_url` | Text-prompted segmentation; `mask_only` defaults to true; `semantic_type` claims body-part-level segmentation; `use_grounding_dino` option |
| `fal-ai/birefnet/v2` | `image_url` | `mask_only` supported; can produce masks without cutouts |
| `fal-ai/z-image/turbo/lora` | `prompt` | **Text-to-image only — no image input.** Cannot refine the existing approved reference |
| `fal-ai/sam2/auto-segmentation` | — | **404, endpoint does not exist** under that ID |
| `fal-ai/sam2/video` | exists | Video segmentation, not useful for a single still |

Pricing could not be verified: `fal.ai` model pages are behind a consent wall and the model metadata API returns 404. The H3 rate, `fal-ai/inpaint` rate, EVF-SAM rate, and any per-part segmentation cost remain unverified. `FLUX.1 Pro Fill` remains documented at $0.05/MP (≈$0.10 per 1024² output).

### Repository / environment

- No cutout, mask, inpaint, rig, or Unity code exists. Option 4 is still a research document.
- Existing Option 2 pipeline can produce motion-reference clips and sample frames, but has no key-pose curation or part segmentation.
- Python is **3.10.15**, while `README.md` and `AGENTS.md` require **3.11+**. No virtual environment is present. Current code does not use 3.11-only features, so this is a documentation/environment mismatch, not a runtime blocker.
- `AGENTS.md` declares Windows primary with PowerShell/backslash commands; the active environment is macOS. Documented commands must be adapted.
- `.env` is present; no key was read or printed.

## Requirement matrix

| Requirement (Option 4 doc) | Status | Gap / action |
|---|---|---|
| Lock canonical design and metadata | Partially available | Approved references exist, but `fal-ai/z-image/turbo/lora` accepts text only. It cannot refine an existing image. Use the approved art as canonical; drop the LoRA-refinement step unless a different image-to-image LoRA endpoint is selected. |
| Generate one short motion reference | Available | H3 endpoint works in prior runs, but add `prompt_expansion_mode: "disabled"`, explicit `duration`/`resolution`/`seed`, and record them. Omitting the now-required field may return 422. |
| Extract key poses | Partial | Video sampling exists; selecting idle/anticipation/wind-up/attack/follow-through/recovery is manual. Clips still contain model-invented streaks, as documented in Option 2. |
| Automated cutout segmentation from one reference | **Unproven** | No test of `fal-ai/evf-sam` `semantic_type` on the references. One query per body part; masks need union/cleanup. Segmentation returns visible pixels only, so it cannot supply occluded artwork. |
| Complete hidden artwork via inpaint | **Unproven** | No mask tooling. Masks must match image dimensions. `fal-ai/inpaint` additionally requires `model_name`. Inpainting cannot infer the *target* extension without a hand-authored or rig-derived mask. |
| Build and validate Unity 2D cutout rig | **Blocked for automation** | 2D Animation 10.2.1 is available; MCP is down; no project exists. Sprite Skin bones/weights are UI-driven, so plan manual rigging or an editor script. |
| Author animation, preview, export | Blocked for automation | Depends on the rig step and an unspecified export target (Animation clips vs. sprite atlas, fps, pixels-per-unit). |
| Provenance metadata | Not implemented | No schema or writer for cutout layers, masks, inpaint results, model versions. |
| Acceptance criteria | Incomplete | The doc lists metrics but no pass thresholds (usable-pose %, drift tolerance, joint-pop count, max human minutes). |

## Cost implications of the verified requirements

- **H3 clip:** one new clip at the default 5 s is one billable generation; the rate is still unverified. Add retries only with explicit approval.
- **Segmentation:** automated parts imply one EVF-SAM request per part prompt. A minimal humanoid cutout set (head/hair, torso, upper/lower arms, hands, hips, upper/lower legs, feet, weapon) is roughly 10-14 requests per character, plus retries. They are not free, and the current cost estimate does not budget them.
- **Inpainting:** the document budgets 2-4 extensions ($0.20-0.40). A cutout rig typically needs more: torso behind each arm, hips behind each thigh, neck behind head, elbow/knee joints, and the hand under the weapon grip. Budget 6-10 FLUX Fill calls ($0.60-1.00 at $0.10 each) until a test proves otherwise.
- **Unity/Spine licenses and human labor remain excluded.**

## Recommended next step (still report/pilot only)

1. Start the Unity 6 editor with a disposable 2D project and confirm the MCP bridge is reachable; if not, document the manual rig procedure and skip MCP automation claims.
2. Test `fal-ai/evf-sam` on one reference for 3-4 part prompts (`head`, `torso`, `arm`, `leg`) with `semantic_type` on and off. Judge mask completeness, not just exit status.
3. Add `prompt_expansion_mode: "disabled"` and explicit generation parameters to the H3 payload before any new paid clip; record seed/duration/resolution in `generation.json`.
4. Test one FLUX Fill extension on a real joint gap with a hand-authored mask; compare style and seam at the intended overlap.
5. Only then run the Unity cutout prototype. Use the existing Option 2 clip's key poses for timing rather than paying for a new clip if motion reference is not the question under test.

## Resolved decisions and pilot outcome

The decisions above were resolved on 2026-10-22 and a first pilot was executed:

- Canonical art: existing reference in `art_references/`, not a generated image.
- Segmentation: automated EVF-SAM with manual masks accepted as fallback.
- Unity: `templates/FalSprite`, Unity 6000.0.59f2, MCP verified live.
- Export: Unity AnimationClip.
- Paid calls: approved. The pilot used 1 H3 generation ($0.30) and 18 EVF-SAM requests ($0.09); no FLUX Fill call was needed.

Outcome: EVF-SAM produced usable masks for the major masses (`weapon`, `head`, `torso`) and legs, but the `arm` mask was 87% torso, `hand` was empty, and `skirt` returned the whole character. Six crop-based retries were worse. **Seedream layerize is the validated replacement**: one auto request returned base/body/weapon, and one prompted request returned 15 layers (base + 14 named body parts and weapon). The model z-index puts the weapon behind the torso; the corrected order is saved in `full_canvas/parts.json`. Layers are regeneratively redrawn, so re-compositing is close but not pixel-identical — use the original reference as the canonical image and the layers as rig parts. Full-canvas sprites are under `output/option4/pilot/layerize_glaive_parts/full_canvas/`. See [Option 4 pilot result](./option-4-lora-video-inpaint-unity.md#pilot-result-2026-10-22).


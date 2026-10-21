# Option 4 — Feasibility and Requirement Verification

Verification date: 2026-10-22. Scope: research/report only; no pipeline code, Unity project, or paid FAL call was created.

## Verdict

Option 4 is **feasible in principle but not implementation-ready**. Three requirements are currently unmet:

1. **Automated part segmentation is unproven for this art style.** A text-prompted segmentation endpoint exists (`fal-ai/evf-sam`), but it has not been tested on the approved anime-style references and cannot recover pixels hidden behind overlapping parts.
2. **Unity automation is unverified.** The Unity MCP server is not running in this environment, and no Unity project exists in the repository. The rig/build steps would currently be manual.
3. **H3 request schema has drifted.** `prompt_expansion_mode` is now a required field, but `scripts/generate_spritesheet.py` sends only `image_url` and `prompt`.

Everything else (Unity 2D Animation availability, inpaint endpoints, existing pose-sampling pipeline) checks out.

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

## Decisions still required

1. **Canonical art:** use the existing approved reference as the cutout master (recommended), or require a generated canonical image first? The Z-Image LoRA endpoint cannot do image-to-image.
2. **Segmentation cleanup:** is manual mask editing acceptable? If not, automated segmentation will not meet production quality.
3. **Unity automation path:** start and validate the MCP bridge, or accept manual rigging / an editor batch script for the pilot?
4. **Export target:** Unity Animation clips, sprite atlas, or rendered frame sequence? Frame rate and pixels-per-unit are needed for acceptance.
5. **Paid budget:** approve the actual call counts (1 H3 clip + 10-14 segmentation requests + 6-10 inpaint requests) or restrict the pilot to free reuse of existing Option 2 assets.
6. **Pass thresholds:** define numeric limits for usable poses, bounding-box drift, joint gaps, weapon-grip failures, and human minutes per animation.

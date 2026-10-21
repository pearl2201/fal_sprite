# Option 4 — LoRA + Image-to-Video + Inpainting + Unity 2D Animation

> **Status: prototype only — not production quality (2026-10-22).**
>
> Option 4 has been prototyped end to end, but it is **not ready for production**. Two blockers remain:
>
> - **Segmentation is not production-grade.** EVF-SAM collapses overlapping limbs: the `arm` prompt returns the torso, `hand` is empty, and `skirt` returns the whole character. Seedream `layerize` produces clean named parts, but it regeneratively redraws them, is not pixel-faithful to the source, and its z-order must be corrected manually. Re-compositing the layers is close but not identical to the reference.
> - **Automated rigging is not available at production quality.** No reliable automated bone/weight authoring or pose retargeting was found. Unity MCP can create objects, sprites, and scenes, but the current rigs are hand-built: a 5-sprite rigid cutout and a static 14-layer assembly. Joint pivots, weights, and animation keys still require a human.
>
> Treat this option as a research prototype. Production use requires manually authored layered art, manual rigging in Unity or Spine, and human animation/QA. Do not sell the current pipeline as an automated production solution.

## Concept

Use a consistent image-generation model and compatible LoRA to establish the character's appearance, then generate a short image-to-video attack as a motion reference. Separate the character artwork into cutout parts for a reusable 2D rig; use inpainting only where cutting or articulating a part exposes missing/occluded artwork that must be extended. Build and animate the rig in Unity 2D Animation. Test Unity first to avoid Spine license cost; keep Spine as a fallback if Unity's workflow does not meet the animation needs.

The AI-generated video is a **motion and pose reference**, not the final animation asset. The production result is the editable Unity project, with authored body-part images, rig, bones/weights, animation keys, and validated in-game animation or rendered image sequence.

Proposed stack:

> Base image model + compatible character/style LoRA → [fal MiniMax H3 Max Turbo image-to-video](https://fal.ai/models/minimax/h3-max-turbo/image-to-video) for motion reference → cutout/segmentation of approved character artwork → selective inpainting to extend occluded part artwork → Unity 2D Animation rig and animation → preview/export
>
> DeepSeek plans/checks steps and calls an available Unity-capable MCP; a human approves design, edits, and final export.

This is a hybrid workflow: video provides motion ideation; cutout segmentation prepares the character for rigging; inpainting extends only occluded artwork that becomes necessary when parts are separated or moved; Unity converts the approved design and motion reference into controllable, reusable animation.

## Roles and integration boundary

| Component | Role | Important constraint |
|---|---|---|
| Base image model + LoRA | Create or refine a canonical character image and, if supported, consistent views/parts | Verify that the LoRA matches the base model. A LoRA used for image generation is not automatically usable by the video model. |
| Image-to-video | Propose timing and poses from the approved image | Confirm that the selected model supports image input and the required short action. Video is reference material; expect temporal drift. |
| Inpainting | Extend missing pixels in a cutout part (such as torso hidden behind an arm or clothing behind a leg) | Mask only the newly exposed gap. Compare fal-ai/inpaint and FLUX.1 Pro Fill on the same example; reject fills that alter the known silhouette, pattern, or palette. |
| Unity 2D Animation | Author a 2D cutout skeleton and keyframed attack animation in Unity | Requires the 2D Animation package and valid layered cutout artwork. It is not a one-click video-to-rig converter; validate package features and target runtime. |
| Spine (fallback) | Alternative 2D skeletal editor/runtime if the Unity prototype is inadequate | License cost is excluded from this comparison as requested; verify the license requirement before production selection. |
| DeepSeek | Turn the action into a pose/animation checklist, call available tools, summarize validation, and ask for approval at gates | It should not be treated as an image/video model or trusted to make unreviewed art edits. |
| MCP server | Provide explicit operations for the Unity project/editor (e.g., inspect project, import assets, set animation keys, preview, export) | No particular Unity MCP server is assumed. If no suitable server exists, the human performs those editor actions; do not imply MCP capabilities that are not installed and tested. |

## Workflow

1. **Lock the canonical design** — approve the character, side-facing orientation, outfit, polearm, colors, proportions, and target camera/framing. Store the reference image and any LoRA/model/version/license metadata.
2. **Generate a motion reference** — provide the canonical image to [fal MiniMax H3 Max Turbo image-to-video](https://fal.ai/models/minimax/h3-max-turbo/image-to-video) with the existing [action prompt](../prompt/action_prompt.txt) as the starting point. Request one attack and recovery, fixed side camera, full-character margins, and no weapon effects. Confirm the current schema, pricing, and accepted image/duration parameters before building automation.
3. **Extract key poses** — inspect the complete video and choose a sparse set of readable poses: idle, anticipation, wind-up, attack, follow-through, recovery. Keep timestamps, source frames, and notes. Reject clips whose character/weapon/camera changes cannot be corrected locally.
4. **Prepare cutout artwork for Unity** — segment the approved character image into clean, consistently named layers for torso, head/hair, upper/lower limbs, hands, and costume pieces that need independent deformation. Keep the weapon on a separate rigid attachment/layer aligned with the hand grip. Note areas hidden by overlaps or outside the source silhouette that may be exposed as parts move.
5. **Complete hidden artwork only where needed** — first check whether layer order can hide a gap. For remaining gaps, use a small mask to inpaint only the missing extension on the affected part (for example, fill the torso behind an arm so it remains complete when the arm rotates). Compare [fal-ai/inpaint](https://fal.ai/models/fal-ai/inpaint) with [FLUX.1 Pro Fill](https://fal.ai/models/fal-ai/flux-pro/v1/fill) on the same masked region. Keep the original cutout and mask, then review the fill in context before import. Do not inpaint every video frame or regenerate the whole character.
6. **Prototype and build the Unity rig** — first import a disposable layered character into the project's Unity version, install/verify the 2D Animation package, and prove bone creation, skinning/weights, animation clips, and target runtime playback. If this passes, define bones and pivots, maintain foot/contact points, and test weapon attachment through extreme poses.
7. **Author the animation** — use video poses as timing and silhouette references, then key the motion in Unity. The final animation should have one continuous physical weapon, one attack, and a stable return to idle. Use DeepSeek through MCP only for supported operations; pause for human approval before overwriting assets, changing art, or exporting.
8. **Preview, revise, export** — preview in the target Unity scene at game resolution and frame rate. Fix joint pops, body-part gaps, weapon grip, timing, foot sliding, and silhouette issues. Export/package through the chosen Unity runtime pipeline. If Unity cannot meet requirements, repeat the pilot using Spine and make a documented license-cost decision.
9. **Record provenance** — save the project file, source references, generated clip, selected timestamps, cutout layers, masks and inpainted extensions, model versions, and export settings.

## MCP + DeepSeek interaction design

Treat the assistant as a workflow operator, not an autonomous animator. A safe first version can expose a small, bounded tool set:

- Read Unity project/package/animation metadata and report the active project/version.
- Import or list approved image assets without destructive replacement.
- Create a new animation or duplicate a project before edits.
- Add or modify named keyframes only where the MCP schema supports it.
- Request preview/render and report validation results.
- Export to a user-approved output folder after confirmation.

Keep image/video generation outside that MCP unless explicit tools support it. Require approval before changing source art, replacing attachments, deleting animation keys, or overwriting the project. Log tool inputs and outputs. If the MCP cannot manipulate the Unity project, use DeepSeek to produce a human-readable pose sheet/keyframe plan and execute it manually in Unity. A Spine MCP is not assumed for the fallback either.

## Strengths

- Video helps discover attack timing and pose silhouettes without making its frame-to-frame defects the final output.
- Inpainting targets localized errors, potentially reducing manual repaint work.
- Unity's 2D skeletal-animation workflow is the first implementation target, avoiding an additional Spine license purchase if the existing Unity setup is sufficient.
- A separate rigid weapon attachment can preserve weapon continuity more reliably than a fully generated video sequence.
- The same rig and assets can support idle, attack, recovery, and later actions.
- If Unity's tooling is insufficient, Spine remains a fallback with its own license/runtime requirements.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| LoRA and video model use incompatible architectures or conditioning | Use the LoRA only in the endpoint that explicitly supports it. Treat the canonical image as the visual bridge and test reference retention with a short clip. |
| Video changes character or weapon between poses | Use video only to select motion beats; do not build the final sprite sheet directly from all video frames. Reject unusable clips early. |
| Inpainted cutout extensions do not match style or create seams | Use tight masks only on missing artwork, keep the original cutouts, compare the result at intended overlaps/deformations, and require human approval. Skip inpainting where layer order or manual paint solves the gap. |
| Cutout rig looks stiff or exposes missing pixels | Plan overlaps and hidden geometry, add mesh deformation where helpful, and manually paint unseen areas revealed during the action. |
| Weapon grip breaks or weapon duplicates | Keep the weapon as a separate attachment or rigid layer, key its orientation with the hand, and verify singular continuity in every pose. |
| Unity 2D Animation package or MCP cannot perform desired editing/export | Verify package and MCP behavior against a disposable project first. Fall back to manual editor work or evaluate Spine; do not promise unsupported automation. |
| DeepSeek produces incorrect operations or overwrites files | Use typed, narrow MCP commands, project copies/version control, explicit approval gates, and recoverable exports. Do not pass API secrets in prompts or logs. |
| Unity project/package version incompatibility | Pin Unity Editor and 2D Animation package versions in project settings; validate rigging and playback after upgrades. |
| Final output differs from Unity scene preview | Validate in the target build/runtime and at actual game scale. |

## Pilot and acceptance criteria

Run one character, one short side-view attack, and a disposable Unity project. Keep the first test small:

1. Generate one canonical image and one short video.
2. Select six to eight distinct motion/reference poses.
3. Segment the character into a minimal cutout set and list hidden areas exposed by likely joint movement.
4. Inpaint one or two representative missing part extensions; compare both endpoints on the same mask if practical.
5. Create a simple Unity 2D cutout rig, animate the attack and return, and validate playback in a test scene.
6. Compare the result to the original action constraints and estimate human time.

Record:

- Percentage of reference poses usable without extensive redesign.
- Seam quality and style consistency of inpainted hidden-part extensions.
- Human minutes to prepare layered cutouts, build the rig, and polish the first animation.
- MCP operations that succeeded, needed correction, or were unavailable.
- Number of joint gaps/pops, weapon-grip failures, and exposed missing-art regions.
- Runtime/spritesheet export quality and cost per accepted animation.

Proceed beyond the pilot only if the Unity animation is controllable and readable at game scale, weapon continuity and framing pass review, and the rig is reusable enough to offset cutout preparation. If Unity fails the package/runtime test, compare Spine before committing to the workflow and include its license cost in the production decision. If video adds little value, skip it and author poses directly in Unity. If cutout setup dominates the cost, compare option 2's curated frames or option 3's 3D rig.

## Pilot result (2026-10-22)

One character, one attack, Unity 6000.0.59f2, `templates/FalSprite`.

| Step | Result |
|---|---|
| Motion reference | One H3 clip at 5 s, 768P, seed `424242`, prompt expansion disabled. The clip returned 124 frames at 24 fps with the usual model-invented streak during the strike, so it was used for timing only. |
| Cutout segmentation | 18 EVF-SAM requests across three probes. `weapon`, `head`, `torso`, `upper_leg`, `lower_leg`, and `foot` were usable. The `arm` mask was 87% torso, `hand` was empty, and `skirt` returned the whole character. |
| Seedream layerize | 2 requests. Empty prompt returned 3 layers (base, body, weapon). A detailed prompt returned 15 layers: base + hair, head/face, neck, torso, pelvis, both upper arms, both forearms/hands, both thighs/shins, both boots, and the polearm. Each layer has a name, description, z-index, and bounding box. |
| Layer reconstruction | Resizing each layer to `bounding_box.absolute` and compositing in the model's z-order reconstructs the reference closely, but the model z-order places the polearm behind the torso. The correct occlusion order puts the weapon above the torso/upper arms and below the forearms/hands. A corrected preview is at `output/option4/pilot/layerize_glaive_parts/reconstructed_zorder_fixed.jpg`. |
| Unity layered import | 14 full-canvas sprites imported under `Assets/FalSprite/LayeredParts`, PPU 480, sorting order from the corrected `render_order`. Static assembly scene: `Assets/FalSprite/Scenes/FalSpriteLayered.unity`; preview: `output/option4/pilot/unity_layered_preview.png`. No rig or animation was added yet. |
| Production readiness | **No.** Segmentation is not pixel-faithful and needs manual cleanup/z-order; automated bone/weight authoring and pose retargeting are unavailable. Current Unity rigs are hand-built prototypes. |
| Crop re-segmentation | Six crop-based requests (arm, hand, skirt, torso, legs) produced slivers or empty masks; tighter crops made EVF-SAM worse, not better. |
| Local mask repair | Removed detached torso/head/leg fragments, kept the largest component, filled holes, and bridged the weapon's two shaft pieces with a 26 px line. The weapon is now one continuous sprite. Separate foot sprites were dropped because the leg masks already include the boots. |
| Unity rig | Five sprites, PPU 480, hierarchy `Hips > Torso > Head/Weapon`, `Hips > LegFront`, `Hips > LegBack`. The arm sprite was dropped because its mask was the torso. |
| Animation clip | `Assets/FalSprite/Animations/NormalAttack.anim`, 2 s, 24 fps, six key poses stored as **quaternion** curves (`localRotation.x/y/z/w`) plus hip translation. Legacy `Animation` component with `playAutomatically`. Scene: `Assets/FalSprite/Scenes/FalSpritePilot.unity`. |
| Preview check | 13 rendered frames and `output/option4/pilot/unity_v10_preview.gif` show the torso swinging, hips lunging, and weapon angle changing. Sampled torso Z is 0° at t=0, 18° at t=1.1 s, and 0° at t=2 s. |

Paid calls: **1 H3 generation ($0.30) + 18 EVF-SAM requests ($0.09) = $0.39**. No FLUX Fill call was made.

Key finding: Seedream layerize is the better segmentation path. With a detailed prompt it produced 14 clean named body-part layers plus the weapon. Two limitations matter: the model's z-index puts the weapon behind the torso, so occlusion must be corrected manually, and the layers are generatively redrawn, so re-compositing is close but not pixel-identical to the reference. Use the original reference as the canonical image and the layers as rig parts. EVF-SAM cannot separate overlapping body parts: prompting `arm` returns the torso, and tight crops degrade the result. The Unity animation on the old 5-sprite rig uses **quaternion** curves rather than Euler curves so the legacy `Animation` component plays the same poses that `SampleAnimation` previews.


## Cost estimate

See [per-character cost estimate](./cost-estimate.md). Inpainting is budgeted for a few cutout-part extensions, not video-frame repair. At 1024² output, FLUX.1 Pro Fill is about **$0.10 per extension** under the documented rounded-megapixel pricing. Total cost depends on how many gaps cannot be solved by layer overlap or manual paint. H3 Max Turbo cost must be calculated from its current billing unit and actual retries. Check fal-ai/inpaint's current price before the pilot. Unity/Spine license fees and human labor are excluded.

## Human work boundary

Human approval remains necessary for the canonical design, pose selection, inpainted results, hidden cutout artwork, rig quality, and final animation. DeepSeek/MCP may speed up repeatable project operations only when the actual integration supports them; they do not remove the need for art direction or Unity animation expertise.

## Sources and verification

- [FAL Z-Image Turbo LoRA](https://fal.ai/models/fal-ai/z-image/turbo/lora) — candidate image-generation LoRA endpoint; verify the actual LoRA's supported checkpoint and license.
- [Action prompt](../prompt/action_prompt.txt) — project constraints for camera, character consistency, weapon continuity, and forbidden effects.
- [fal MiniMax H3 Max Turbo image-to-video](https://fal.ai/models/minimax/h3-max-turbo/image-to-video) — motion-reference endpoint.
- [fal-ai/inpaint](https://fal.ai/models/fal-ai/inpaint) — alternative mask-based repair endpoint; verify its current price and schema.
- [FLUX.1 Pro Fill](https://fal.ai/models/fal-ai/flux-pro/v1/fill) — mask-based inpainting listed at $0.05/MP.
- [Unity 2D Animation package documentation](https://docs.unity3d.com/Packages/com.unity.2d.animation@latest) — verify package features and compatibility with the project's Unity version.
- [Spine export documentation](https://esotericsoftware.com/spine-export) — fallback reference; license cost is excluded from estimates, not waived.
- [DeepSeek API documentation](https://api-docs.deepseek.com/) — API/agent integration reference. It does not establish that a particular Unity MCP is installed or supports project editing.
- See [per-character cost estimate](./cost-estimate.md) for assumptions and unknown-rate handling.

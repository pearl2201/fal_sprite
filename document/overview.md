# Game Spritesheet Generation Research

This research compares four ways to create a consistent game-character spritesheet, starting from an approved character design and an action description. The goal is a usable, game-ready animation—not just a character concept image or an uncurated video.

## Options

1. **Pose-guided 2D generation** — generate each frame from explicit pose controls, using a consistent base model and compatible LoRA. Best when frame-level control and sprite-like output matter most. See [option 1](./option-1-pose-guided-2d.md).
2. **Image-to-video, then extract frames** — animate a reference image with a video model, then use Python/OpenCV to select, clean, align, and pack frames. Fastest prototype, but temporal and object consistency need testing. See [option 2](./option-2-video-frames.md).
3. **AI-assisted 3D, then render in Blender** — generate a character asset with Tripo's requested Image-to-3D P Series / P1-20260311 workflow, prepare it in Blender, and render a fixed-camera frame sequence. Highest setup cost, strongest camera and geometric repeatability after the asset is production-ready. See [option 3](./option-3-ai-3d-blender.md).
4. **LoRA + video + cutout-part inpainting + Unity 2D Animation** — use image-to-video for motion reference, then segment the character into rig parts and inpaint only the hidden artwork exposed by separating or moving those parts. Build the production cutout rig in Unity first; keep Spine as a fallback. See [option 4](./option-4-lora-video-inpaint-unity.md).

## Current direction

Run a small, same-character pilot for the relevant options before committing to a production pipeline. Score each on design fidelity, frame-to-frame consistency, cleanup time, usable-frame ratio, and total cost per accepted frame. Option 2 is the quickest motion-reference baseline; option 1 is the most direct frame-by-frame 2D route; option 3 is worth pursuing if predictable 3D animation and reuse justify asset cleanup and rigging. Option 4 uses video for motion reference but makes the Unity 2D rig—not AI-generated video—the editable, reusable production animation.

All four options should use the same approved reference, action, camera/framing target, and acceptance checklist. Do not expose FAL or Tripo API keys in client-side code or generated documents; keep credentials server-side in environment configuration.

## Recommended first pilot

Option 2 has now had three feasibility runs using [2. Low-Poly Warrior with Ornate Glaive](../art_references/2.Low-Poly%20Warrior%20with%20Ornate%20Glaive.png). Horizontal and vertical blank-canvas padding gave the character and weapon room in the selected frames; BiRefNet v2 produced transparent frame atlases while preserving the original RGB frames. The latest, with 25% padding on each edge, still has a bright motion streak during the attack, so padding and background removal do not resolve the model's effects/weapon-consistency issue. Compare the [first contact sheet](../output/option2/contact_sheet.jpg), [padded contact sheet](../output/option2_padded/contact_sheet.jpg), and [tall-padded transparent sheet](../output/option2_tallpadding/spritesheet_alpha.png). See the detailed [Option 2 pilot notes](./option-2-video-frames.md).

Next, use the selected poses as references for a small **Unity 2D Animation cutout-rig prototype** (Option 4), but keep the source concept art as the cutout master to avoid baking video smear into the rig artwork. In this workflow, inpainting is for extending missing/occluded pixels on cutout parts, not for retouching video frames. If the cutout approach proves too labor-intensive, test **one Tripo P1-20260311 task** from the same reference (Option 3), because its low-poly 3D art style is a natural match. Keep [3. Spiky-Haired Warrior with Techsword](../art_references/3.Spiky-Haired%20Warrior%20with%20Techsword.png) for a later weapon/style comparison.

The references are single rendered views, not layered 2D cutouts or rigged 3D assets. Option 4 will therefore need manual segmentation/hidden-art preparation, and Option 3 still needs mesh inspection and rigging. The first pilot should judge what the references actually enable, not assume those assets already exist.

## Known assumptions and verification needs

- The FAL Z-Image Turbo LoRA page describes a text-to-image endpoint with inference-time LoRA support. It does not, by itself, establish that this endpoint accepts OpenPose/ControlNet conditioning. Option 1 therefore requires a compatible pose-conditioned endpoint and a LoRA trained for, or verified against, its base model.
- The linked Civitai model page could not be independently inspected during this research pass. Verify the exact downloadable LoRA, supported checkpoint(s), license, and compatibility before using it.
- The requested Tripo identifier **P1-20260311** is documented as a P Series value for `POST https://openapi.tripo3d.ai/v3/generation/image-to-model`. Check the current API docs for request fields and account access before implementation.
- Use the specified [fal MiniMax H3 Max Turbo image-to-video endpoint](https://fal.ai/models/minimax/h3-max-turbo/image-to-video). Confirm current duration, resolution, pricing, and API constraints before budgeting.
- Use [BiRefNet v2](https://fal.ai/models/fal-ai/birefnet/v2) optionally after frame selection; retain the original RGB frames alongside its alpha outputs.
- Compare [fal-ai/inpaint](https://fal.ai/models/fal-ai/inpaint) and [FLUX.1 Pro Fill](https://fal.ai/models/fal-ai/flux-pro/v1/fill) on the same masked defects. The latter page lists $0.05/MP; verify the former's current pricing and behavior.
- Unity 2D Animation is the first skeletal-animation workflow to test because Spine license cost is being excluded from the comparison. Check installed Unity/package versions and prototype import/rig/export before treating the workflow as settled. Spine remains an alternative.
- MCP availability and write/export capabilities are environment-specific. DeepSeek can plan work and request MCP tools, but it cannot author a Unity or Spine project unless an appropriate MCP server or other automation interface is available and validated.
- See [cost estimate](./cost-estimate.md) for per-character assumptions and API spend; unknown or account-dependent rates are explicitly marked rather than presented as quotes.
- Pricing, rate limits, output dimensions, terms, and API request schemas change. Confirm them at implementation time and record the exact model/version used in each pilot.

## Source links

- [FAL Z-Image Turbo LoRA model page](https://fal.ai/models/fal-ai/z-image/turbo/lora)
- [fal MiniMax H3 Max Turbo image-to-video](https://fal.ai/models/minimax/h3-max-turbo/image-to-video)
- [fal-ai/inpaint](https://fal.ai/models/fal-ai/inpaint)
- [FLUX.1 Pro Fill](https://fal.ai/models/fal-ai/flux-pro/v1/fill)
- [Unity 2D Animation manual](https://docs.unity3d.com/Packages/com.unity.2d.animation@latest)
- [Civitai Character Design Sheet Helper model page](https://civitai.com/models/100435/character-design-sheet-helper-3-perspectivescolor-palette-z-image-turbo-or-illustrious-xl-or-flux-or-xl-pony-or-sd-15-by-yeiyeiart)
- [Tripo](https://www.tripo3d.ai/)
- [Tripo Image to 3D Model — P Series API](https://developers.tripo3d.ai/en/docs/generation-image-to-model/p)
- [Spine export documentation](https://esotericsoftware.com/spine-export)
- [DeepSeek API documentation](https://api-docs.deepseek.com/)
- [Per-character cost estimate](./cost-estimate.md)
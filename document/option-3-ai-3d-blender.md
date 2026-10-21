# Option 3 — AI-Assisted 3D Asset and Blender Rendering

## Concept

Create a 3D starting asset from the approved character design using Tripo's Image-to-3D Model — P Series endpoint with `model: "P1-20260311"`. Bring the result into Blender, repair the asset as needed, rig and animate it, then render a fixed orthographic sequence with a consistent camera and lighting. This creates frames from one persistent model, so camera, scale, and weapon geometry can remain stable after setup.

Proposed stack:

> Character concept image (optionally LoRA-generated) → Tripo Image-to-3D P Series / P1-20260311 → Blender cleanup, rigging, animation, orthographic render → sprite cleanup and packing

The [Tripo P Series API documentation](https://developers.tripo3d.ai/en/docs/generation-image-to-model/p) documents `POST https://openapi.tripo3d.ai/v3/generation/image-to-model` and the `P1-20260311` model value. It accepts one image source (`file_token`, public URL, or a prior image-generation `task_id`), with PNG/JPEG/WebP formats, a 20 MB maximum, and a recommended minimum resolution of 256 × 256. The docs describe P1 as optimized for low-poly generation; `face_limit` is documented from 50 to 20,000, and texture/PBR options are available. The API returns a task ID; poll the task result for the model URL. Verify the latest schema, account access, credit cost, and license before implementation.

## Workflow

1. **Approve the 2D design first** — settle the side-view silhouette, outfit, palette, weapon, and proportions. A clean image reference is more useful than asking the 3D generator to invent missing views.
2. **Create the initial model** — upload the image through Tripo's File Upload API and pass its returned `file_token`, or use a publicly accessible image URL or supported prior image-generation `task_id`. Set `model` to `P1-20260311`; use a clean, minimally occluded subject image. Save the original input, request parameters, task ID, response metadata, and downloaded source asset.
3. **Inspect and repair in Blender** — check mesh topology, silhouette, hidden surfaces, face/hands, accessories, weapon separation, UVs, materials, and scale. Expect human edits; image-to-3D output should be treated as a draft asset until verified.
4. **Rig the character** — create or repair a game-appropriate skeleton; weight-paint and test deformations at the attack's extreme poses. Keep the weapon a separate rigid object or attach it to the correct hand bone.
5. **Animate the action** — key a wind-up, attack, follow-through, and recovery into idle. Keep the camera fixed, orthographic, side-on, and framed with margins. Use root/foot contact controls to prevent sliding.
6. **Render the sequence** — render at a fixed resolution, color management, lighting, camera, and transparent or clean background. Use consistent frame numbering and the selected game frame rate.
7. **Pack and validate** — trim transparent margins consistently, establish the sprite pivot/ground point, pack frames with metadata, and preview the result in the target game or a simple playback tool.

## Strengths

- Every rendered frame comes from the same model and camera, which improves geometric, palette, and framing continuity.
- The asset can support many attacks, idle cycles, directions, and revisions after rigging.
- Fixed orthographic rendering provides predictable canvas size, pivots, and framing.
- Animation timing can be edited in Blender without asking an image model to regenerate every frame.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Single-image 3D reconstruction invents unseen geometry | Supply multiple consistent views if supported; inspect all sides and correct the silhouette manually. |
| Generated mesh is not rig-ready | Budget for retopology, weight cleanup, and human rigging. Test extreme poses before producing a full animation. |
| The style changes from painted 2D to generic 3D | Use matching materials, outlines/shaders, orthographic camera, palette control, and a style test render before rigging the full asset. |
| Weapon becomes fused to the body or deforms | Separate it as a rigid object and attach it to a hand control; validate grip and weapon shape in each key pose. |
| Animation feels mechanical or feet slide | Use deliberate key poses, foot/contact constraints, and preview at actual playback speed. |
| Setup cost is high for a one-off animation | Compare total human setup/cleanup time against accepted frames from options 1 and 2. This option is more compelling when the character will be reused. |
| API product/model details are assumed incorrectly | Verify P Series, P1-20260311, export formats, limits, terms, and pricing in Tripo's current developer documentation/account. |

## Human work boundary

Plan for human work at model inspection/repair, material and style matching, rigging, weight painting, animation polish, and final render approval. Stop at the first stage where the generated asset cannot meet the silhouette or deformation criteria without disproportionate manual rebuilding; record that failure rather than treating the AI mesh as production-ready.

## Pilot and acceptance criteria

Use one character, one side-view action, and a single render style. Before building a full asset pipeline, test:

- Whether the model matches the approved front/side silhouette from the game camera.
- Whether the weapon and hands can be separated and posed correctly.
- Whether the mesh deforms cleanly through wind-up, attack, and recovery.
- Human hours from image submission to the first acceptable rendered frame.
- Cost per accepted frame after the one-time asset and rigging work.
- Whether the asset can be reused for at least one additional action without rebuilding it.

The option is viable when the character survives rigging and key poses, the rendered sequence meets the art direction at game scale, and reuse potential offsets the initial modeling/rigging effort.

## Cost estimate

See [per-character cost estimate](./cost-estimate.md). The image-concept portion is about **$0.04** for four 1024² Z-Image Turbo LoRA candidates at the listed rate. Add Tripo's actual credit cost for one or two P1-20260311 tasks; the cited API documentation does not establish a USD task price. Blender labor is excluded.

## Sources and verification

- [Tripo Image to 3D Model — P Series API](https://developers.tripo3d.ai/en/docs/generation-image-to-model/p) — endpoint, supported model IDs, input forms, constraints, generation parameters, and task-result example.
- [FAL Z-Image Turbo LoRA](https://fal.ai/models/fal-ai/z-image/turbo/lora) — optional character concept/style exploration stage; not required if an approved design image already exists.

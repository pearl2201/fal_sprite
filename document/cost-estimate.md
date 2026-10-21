# Per-Character Generation Cost Estimate

## Scope and assumptions

These are **provider/API spend estimates**, not labor estimates. They exclude software and runtime licenses as requested, including Spine fees, plus human art/rigging/cleanup time, tax, storage, and game-engine licensing.

Comparable pilot unit:

- One character design and one short side-view attack with recovery.
- Four 1024 × 1024 base-image candidates, then one selected reference.
- Up to eight final key poses/frames where the workflow outputs frames.
- Cost includes a small number of retries, but not unlimited iteration.
- USD rates are the rates visible on the linked model pages checked for this estimate; unknown current prices are left as variables instead of guessed.

The linked FAL Z-Image Turbo LoRA page lists **$0.0085 per megapixel**. A 1024 × 1024 image is about 1.05 megapixels, so use approximately **$0.009 per image** for planning (about **$0.04 for four candidates**). Actual billing can depend on the endpoint's resolution/billing implementation.

FLUX.1 [pro] Fill lists **$0.05 per megapixel**, billed by rounding up to a whole megapixel. Thus a 1024 × 1024 output is budgeted as two megapixels, or **$0.10 per output**. The fal-ai/inpaint page did not expose a price in this research pass; obtain its current rate in the model/API page before comparing it.

The H3 Max Turbo model page was reachable, but its current price and unit could not be verified from the retrieved page content. Let **Rᵥ** be the current FAL charge per generated video second (or use the model's actual per-video billing unit if it differs). Confirm it immediately before running the pilot. This avoids assuming a price basis that the endpoint may not use.

Optional BiRefNet v2 background removal also has an account/model-specific cost that was not verifiable from its page during this check. Let **Rᵦ** be its cost per submitted sampled image; enabling it for eight frames adds **8 × Rᵦ**. The implementation preserves the original frame outputs and writes the transparent results separately.

## Estimated API spend by option

| Option | Estimated usage for one character | Verifiable or formula-based API spend | Main unknown |
|---|---|---:|---|
| **1. Pose-guided 2D** | Four reference candidates + 8 poses × 3 candidates (24 frame candidates); up to four 1024² FLUX Fill repairs | About **$0.25-$0.65**, assuming the pose-capable generator bills at the Z-Image LoRA page's $0.0085/MP rate and 0-4 Fill repairs. Calculation: 28 images ≈ $0.25; 0-4 Fill repairs ≈ $0-$0.40. | Z-Image Turbo LoRA is not documented on its linked page as accepting OpenPose/ControlNet. A compatible pose-conditioned endpoint must be selected; its price may differ. The range excludes any pose-control surcharge or a separately priced ControlNet model. |
| **2. Image-to-video + extracted frames** | Four reference candidates + 3 video attempts × 6 seconds; extraction and packing local; optional background removal on up to 8 selected frames | About **$0.04 + 18 × Rᵥ**, or **$0.04 + 18 × Rᵥ + 8 × Rᵦ** with BiRefNet v2. No image-to-video total is claimed until the current H3 billing unit/rate is confirmed. | H3 Max Turbo price/billing basis and optional BiRefNet price; possible minimum duration or resolution multiplier. |
| **3. Tripo image-to-3D + Blender** | Four reference candidates + up to 2 Tripo P1-20260311 image-to-model tasks (first attempt plus one retry); local Blender work | About **$0.04 + 2 × Rₜ**, where **Rₜ** is the current Tripo credit/currency cost per image-to-model task at the chosen settings. If one task suffices: $0.04 + Rₜ. | Tripo's documentation confirms the endpoint and task flow, but a stable USD task price was not available in the cited API page. Check account credits and settings-dependent cost before generation. |
| **4. LoRA + H3 video + cutout inpainting + Unity 2D Animation** | Four reference candidates + 2 video attempts × 6 seconds + an assumed 2-4 inpainted cutout-part extensions at 1024²; Unity animation local | About **$0.24-$0.44 + 12 × Rᵥ** using FLUX Fill. The $0.24-$0.44 is about $0.04 for reference candidates + $0.20-$0.40 for 2-4 Fill outputs. | H3 video price and any output-size billing. The number of required hidden-part extensions depends on cutout design and may be zero if overlaps/manual paint suffice. fal-ai/inpaint pricing is unverified. |

### Reading these estimates

- Option 1's numeric amount is a **proxy** based on the published Z-Image LoRA rate, not a quote for a verified pose-conditioned endpoint.
- Option 2's and 4's actual spend is dominated by the current H3 video price and retry count. Calculate video spend as `number of clips × clip duration × rate` only if FAL bills per second; otherwise use the model's listed billing unit. Optional BiRefNet calls add one request per selected frame.
- Option 3's API spend depends on Tripo credits and task configuration. Use the credit consumption returned by the API and the account's effective credit price to fill in `Rₜ`.
- In option 4, inpainting estimates apply to missing artwork revealed by cutting or articulating sprite parts, not repairs to generated video frames. FLUX Fill charges for the output image area, not just the masked pixel area. Smaller accepted output sizes may lower the bill if quality remains sufficient.
- Unity 2D Animation and Spine license costs are omitted from the table. Unity should be tested first per the requested preference; include the appropriate Spine license cost only if the fallback is selected.
- Each estimate excludes human labor. Option 3 and option 4 can have low API charges while requiring substantial manual modeling/rigging and art preparation, so compare labor separately before choosing.

## Observed usage for the Option 4 Unity pilot

The first Option 4 pilot (2026-10-22) used the glaive reference and Unity 6000.0.59f2:

| Item | Endpoint | Units |
|---|---|---:|
| Motion-reference clip | `minimax/h3-max-turbo/image-to-video` | 1 clip (5 s, 768P, prompt expansion disabled) |
| Cutout segmentation probe 1 | `fal-ai/evf-sam` | 4 requests (weapon, head, torso, arm) |
| Cutout segmentation probe 2 | `fal-ai/evf-sam` | 4 requests (hand, leg, boot, skirt; hand/leg/skirt unusable) |
| Cutout segmentation probe 3 | `fal-ai/evf-sam` | 4 requests (pants, upper leg, lower leg, foot) |
| Crop re-segmentation | `fal-ai/evf-sam` | 6 requests (arm, hand, skirt, torso, leg front, leg back); all unusable |
| Seedream layerize, auto | `bytedance/seedream/v5/flash/layerize` | 1 request (3 layers: base, body, weapon) |
| Seedream layerize, prompted | `bytedance/seedream/v5/flash/layerize` | 1 request (15 layers: base + 14 named body parts and weapon) |
| Hidden-part inpainting | `fal-ai/flux-pro/v1/fill` | 0 requests (local mask repair was enough) |

At the quoted rates that is about **$0.30 (H3) + $0.09 (18 EVF-SAM requests)** = **$0.39**, plus **2 Seedream layerize requests** whose rate was not verifiable from the public page. The first H3 clip again contained model-invented streaks, so it was used only for motion timing; no video pixels were used as final art.

Fourteen of eighteen EVF-SAM masks were usable after local cleanup. The `hand`, `leg`, and `skirt` prompts failed on the full image, and the six crop-based requests were worse: `hand` was empty and the arm/skirt masks were slivers. Prompt wording and crops do not fix overlapping parts.

## Observed usage for the full animation set pilot

The seven-action pilot recorded billable units rather than USD, because H3 and BiRefNet rates were not verifiable at run time. Reconstruct the spend from the FAL account dashboard using these counts:

| Item | Endpoint | Units |
|---|---|---:|
| Video generations | `minimax/h3-max-turbo/image-to-video` | 7 clips (glaive) + 7 (skull warrior) + 7 (boxer) + 7 (e_vuong) + 7 (e_vuong_v2) |
| Background removal, glaive set | `fal-ai/birefnet/v2` | 56 images (8 per action, per-frame mode) |
| Background removal, skull warrior set | `fal-ai/birefnet/v2` | 7 images (1 per action, sheet mode) |
| Background removal, boxer set | `fal-ai/birefnet/v2` | 7 images (1 per action, sheet mode, experimental) |
| Background removal, e_vuong and e_vuong_v2 sets | `fal-ai/birefnet/v2` | 0 (VFX sets, `background_remove_option: none`) |
| Local extraction, trimming, atlas packing | Python/OpenCV | 0 billable |
| Local rembg comparison test | `isnet-anime` via rembg | 0 billable |

The glaive set used per-frame background removal (`--background-mode frames`). The skull warrior and boxer sets used the new `sheet` default, covering the same 56 frames in **7 requests instead of 56**, at the resolution trade-off described in [option 2](./option-2-video-frames.md#background-removal-call-count).

No retries were run, so one clip per action is the only video spend. A production set typically needs additional attempts per action, so multiply by the accepted-attempt rate you observe in practice.

## Pilot accounting template

For each attempt, record:

| Field | Value to record |
|---|---|
| Character / option | |
| Model endpoint and version | |
| Resolution, duration, settings | |
| Number of attempted generations | |
| Provider-reported units/credits consumed | |
| USD-equivalent API cost | |
| Accepted frames / usable asset | |
| Human minutes for cleanup/rigging | |
| API cost per accepted frame | |

Use provider-reported usage and actual billing for the final comparison. Recheck prices immediately before the pilot; these rates and model endpoints can change.

## Sources

- [FAL Z-Image Turbo LoRA](https://fal.ai/models/fal-ai/z-image/turbo/lora) — listed at $0.0085/MP.
- [fal MiniMax H3 Max Turbo image-to-video](https://fal.ai/models/minimax/h3-max-turbo/image-to-video) — confirm current billing in the live model/API page.
- [fal-ai/inpaint](https://fal.ai/models/fal-ai/inpaint) — pricing not verifiable from the retrieved page.
- [BiRefNet v2](https://fal.ai/models/fal-ai/birefnet/v2) — optional background removal; verify current per-image pricing.
- [FLUX.1 Pro Fill](https://fal.ai/models/fal-ai/flux-pro/v1/fill) — listed at $0.05/MP, billed by rounding up to the nearest megapixel.
- [Tripo Image to 3D Model — P Series API](https://developers.tripo3d.ai/en/docs/generation-image-to-model/p) — P1-20260311 task API; check account credit pricing.

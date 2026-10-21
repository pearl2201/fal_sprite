"""Segment a character reference into cutout parts and inpaint hidden artwork."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image
import cv2
import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.generate_spritesheet import _download_asset, load_project_env
else:
    from .generate_spritesheet import _download_asset, load_project_env


ROOT = Path(__file__).resolve().parents[1]
SEGMENT_ENDPOINT = "fal-ai/evf-sam"
INPAINT_ENDPOINT = "fal-ai/flux-pro/v1/fill"
LAYERIZE_ENDPOINT = "bytedance/seedream/v5/flash/layerize"
DEFAULT_REFERENCE = ROOT / "art_references" / "2.Low-Poly Warrior with Ornate Glaive.png"
DEFAULT_OUTPUT = ROOT / "output" / "option4" / "parts"
DEFAULT_MASK_THRESHOLD = 127


@dataclass(frozen=True)
class PartPrompt:
    """One named text prompt used to segment a cutout part."""

    name: str
    prompt: str
    crop: tuple[int, int, int, int] | None = None


DEFAULT_PARTS: tuple[PartPrompt, ...] = (
    PartPrompt("weapon", "the polearm weapon"),
    PartPrompt("head", "the character's head and hair"),
    PartPrompt("torso", "the character's torso and armor"),
    PartPrompt("arm", "the character's arms"),
    PartPrompt("hand", "the character's hands"),
    PartPrompt("thigh", "the character's thighs"),
    PartPrompt("shin_foot", "the character's lower legs and feet"),
)


def parse_parts(values: Iterable[str]) -> tuple[PartPrompt, ...]:
    """Parse repeatable ``name=prompt[@x1,y1,x2,y2]`` CLI values."""
    parts: list[PartPrompt] = []
    seen: set[str] = set()
    for index, raw in enumerate(values, start=1):
        if "=" not in raw:
            raise ValueError(f"Part {index}: expected 'name=prompt', got '{raw}'.")
        name, prompt = (piece.strip() for piece in raw.split("=", 1))
        if not name or not prompt:
            raise ValueError(f"Part {index}: name and prompt must both be non-empty.")
        if name in seen:
            raise ValueError(f"Part {index}: duplicate part name '{name}'.")
        crop: tuple[int, int, int, int] | None = None
        if "@" in prompt:
            prompt, raw_crop = (piece.strip() for piece in prompt.rsplit("@", 1))
            coordinates = raw_crop.split(",")
            if len(coordinates) != 4:
                raise ValueError(
                    f"Part {index}: crop must be '@x1,y1,x2,y2', got '{raw_crop}'."
                )
            try:
                x1, y1, x2, y2 = (int(value) for value in coordinates)
            except ValueError as error:
                raise ValueError(
                    f"Part {index}: crop coordinates must be integers, got '{raw_crop}'."
                ) from error
            if x1 >= x2 or y1 >= y2:
                raise ValueError(
                    f"Part {index}: crop requires x1 < x2 and y1 < y2, got '{raw_crop}'."
                )
            crop = (x1, y1, x2, y2)
        if not prompt:
            raise ValueError(f"Part {index}: prompt must be non-empty before '@'.")
        seen.add(name)
        parts.append(PartPrompt(name=name, prompt=prompt, crop=crop))
    return tuple(parts)


def mask_to_rgba(
    image_path: Path | Image.Image,
    mask_path: Path,
    destination: Path,
    threshold: int = DEFAULT_MASK_THRESHOLD,
) -> dict[str, Any]:
    """Apply a white-on-black mask as alpha and keep the full reference canvas."""
    if not 0 <= threshold <= 255:
        raise ValueError("Mask threshold must be between 0 and 255.")

    if isinstance(image_path, Image.Image):
        image = image_path.convert("RGBA")
    else:
        with Image.open(image_path) as source:
            image = source.convert("RGBA")
    with Image.open(mask_path) as source:
        mask = source.convert("L")
    if image.size != mask.size:
        raise ValueError(
            f"Mask size {mask.size} does not match image size {image.size}: {mask_path}"
        )

    alpha = mask.point(lambda value: 255 if value > threshold else 0)
    image.putalpha(alpha)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG")
    opaque_pixels = alpha.histogram()[255]
    return {
        "part": str(destination),
        "mask": str(mask_path),
        "size": {"width": image.width, "height": image.height},
        "opaque_pixels": opaque_pixels,
        "coverage": opaque_pixels / (image.width * image.height),
    }


def _clean_mask(mask_path: Path, destination: Path, min_component_pixels: int) -> None:
    """Drop detached specks so a part mask follows one connected region."""
    with Image.open(mask_path) as source:
        mask = np.array(source.convert("L"))
    binary = (mask > 127).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    cleaned = np.zeros_like(binary)
    for index in range(1, count):
        if int(stats[index, cv2.CC_STAT_AREA]) >= min_component_pixels:
            cleaned[labels == index] = 255
    Image.fromarray(cleaned).save(destination, format="PNG")


def _require_api_key() -> None:
    load_project_env(ROOT / ".env")
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError(
            "FAL_KEY is missing. Add FAL_API=<key> to the project .env file."
        )


def segment_parts(
    reference: Path,
    output_dir: Path,
    parts: Iterable[PartPrompt],
    *,
    semantic_type: bool = True,
    expand_mask: int = 1,
    fill_holes: bool = True,
    use_grounding_dino: bool = False,
    negative_prompt: str | None = "background, shadow, text, additional characters",
    mask_threshold: int = DEFAULT_MASK_THRESHOLD,
    min_component_pixels: int = 200,
) -> dict[str, Any]:
    """Submit one EVF-SAM request per part and write masks plus RGBA parts."""
    part_list = tuple(parts)
    if not part_list:
        raise ValueError("At least one part prompt is required.")
    if not 0 <= expand_mask <= 20:
        raise ValueError("expand_mask must be between 0 and 20.")
    if min_component_pixels < 0:
        raise ValueError("min_component_pixels must be non-negative.")
    if not reference.is_file():
        raise FileNotFoundError(f"Reference image not found: {reference}")

    _require_api_key()
    import fal_client

    masks_dir = output_dir / "masks"
    parts_dir = output_dir / "parts"
    crops_dir = output_dir / "crops"
    masks_dir.mkdir(parents=True, exist_ok=True)
    parts_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(reference) as source:
        reference_image = source.convert("RGBA")
    full_image_url = fal_client.upload_file(str(reference))
    if not isinstance(full_image_url, str) or not full_image_url.startswith("https://"):
        raise RuntimeError("fal.ai did not return a valid HTTPS image URL.")

    records: list[dict[str, Any]] = []
    for part in part_list:
        image_url = full_image_url
        if part.crop is not None:
            x1, y1, x2, y2 = part.crop
            if x1 < 0 or y1 < 0 or x2 > reference_image.width or y2 > reference_image.height:
                raise ValueError(
                    f"Crop for '{part.name}' is outside the {reference_image.width}x"
                    f"{reference_image.height} reference: {part.crop}"
                )
            crop_path = crops_dir / f"{part.name}_crop.png"
            reference_image.crop(part.crop).save(crop_path, format="PNG")
            image_url = fal_client.upload_file(str(crop_path))
            if not isinstance(image_url, str) or not image_url.startswith("https://"):
                raise RuntimeError("fal.ai did not return a valid HTTPS crop URL.")

        arguments: dict[str, Any] = {
            "image_url": image_url,
            "prompt": part.prompt,
            "mask_only": True,
            "semantic_type": semantic_type,
            "expand_mask": expand_mask,
            "fill_holes": fill_holes,
            "blur_mask": 0,
            "revert_mask": False,
            "use_grounding_dino": use_grounding_dino,
        }
        if negative_prompt:
            arguments["negative_prompt"] = negative_prompt

        print(f"Submitting EVF-SAM part '{part.name}': {part.prompt}")
        result: Any = fal_client.subscribe(
            SEGMENT_ENDPOINT, arguments=arguments, with_logs=True
        )
        image_data = result.get("image") if isinstance(result, dict) else None
        mask_url = image_data.get("url") if isinstance(image_data, dict) else None
        if not isinstance(mask_url, str):
            raise RuntimeError(
                f"EVF-SAM response for '{part.name}' did not include image.url."
            )

        raw_mask_path = masks_dir / f"{part.name}_raw.png"
        _download_asset(mask_url, raw_mask_path)
        mask_path = masks_dir / f"{part.name}_mask.png"
        if part.crop is None:
            raw_mask_path.replace(mask_path)
        else:
            x1, y1, _, _ = part.crop
            with Image.open(raw_mask_path) as source:
                crop_mask = source.convert("L")
            expected = (part.crop[2] - x1, part.crop[3] - y1)
            if crop_mask.size != expected:
                raise RuntimeError(
                    f"Crop mask for '{part.name}' is {crop_mask.size}, expected {expected}."
                )
            full_mask = Image.new("L", reference_image.size, 0)
            full_mask.paste(crop_mask, (x1, y1))
            full_mask.save(mask_path, format="PNG")
            raw_mask_path.unlink(missing_ok=True)
        if min_component_pixels:
            _clean_mask(mask_path, mask_path, min_component_pixels)

        part_path = parts_dir / f"{part.name}.png"
        record = mask_to_rgba(reference_image, mask_path, part_path, mask_threshold)
        record.update(
            {
                "name": part.name,
                "prompt": part.prompt,
                "crop": list(part.crop) if part.crop else None,
                "mask_api_url": mask_url,
                "empty": record["opaque_pixels"] == 0,
            }
        )
        records.append(record)

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": SEGMENT_ENDPOINT,
        "reference": str(reference),
        "api_calls": len(records),
        "parameters": {
            "semantic_type": semantic_type,
            "expand_mask": expand_mask,
            "fill_holes": fill_holes,
            "use_grounding_dino": use_grounding_dino,
            "negative_prompt": negative_prompt,
            "mask_threshold": mask_threshold,
            "min_component_pixels": min_component_pixels,
        },
        "parts": records,
    }
    (output_dir / "segmentation.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def inpaint_part(
    image_path: Path,
    mask_path: Path,
    destination: Path,
    prompt: str,
    *,
    seed: int = 424242,
    safety_tolerance: str = "5",
    num_images: int = 1,
) -> dict[str, Any]:
    """Submit one FLUX Fill request for a masked part extension."""
    if not prompt.strip():
        raise ValueError("An inpainting prompt is required.")
    if num_images < 1:
        raise ValueError("num_images must be at least 1.")
    if safety_tolerance not in ("1", "2", "3", "4", "5", "6"):
        raise ValueError("safety_tolerance must be between 1 and 6.")
    if not image_path.is_file():
        raise FileNotFoundError(f"Part image not found: {image_path}")
    if not mask_path.is_file():
        raise FileNotFoundError(f"Mask not found: {mask_path}")

    with Image.open(image_path) as source:
        image_size = source.size
    with Image.open(mask_path) as source:
        mask_size = source.size
    if image_size != mask_size:
        raise ValueError(
            f"Mask size {mask_size} does not match image size {image_size}. "
            "FLUX Fill requires identical dimensions."
        )

    _require_api_key()
    import fal_client

    image_url = fal_client.upload_file(str(image_path))
    mask_url = fal_client.upload_file(str(mask_path))
    for label, url in (("image", image_url), ("mask", mask_url)):
        if not isinstance(url, str) or not url.startswith("https://"):
            raise RuntimeError(f"fal.ai did not return a valid HTTPS {label} URL.")

    parameters: dict[str, Any] = {
        "prompt": prompt,
        "image_url": image_url,
        "mask_url": mask_url,
        "num_images": num_images,
        "output_format": "png",
        "seed": seed,
        "safety_tolerance": safety_tolerance,
    }
    print(f"Submitting one FLUX Fill request for {image_path.name}...")
    result: Any = fal_client.subscribe(
        INPAINT_ENDPOINT, arguments=parameters, with_logs=True
    )
    images = result.get("images") if isinstance(result, dict) else None
    first = images[0] if isinstance(images, list) and images else None
    output_url = first.get("url") if isinstance(first, dict) else None
    if not isinstance(output_url, str):
        raise RuntimeError("FLUX Fill response did not include images[0].url.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    _download_asset(output_url, destination)
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": INPAINT_ENDPOINT,
        "image": str(image_path),
        "mask": str(mask_path),
        "output": str(destination),
        "api_calls": 1,
        "parameters": {
            "prompt": prompt,
            "seed": seed,
            "safety_tolerance": safety_tolerance,
            "num_images": num_images,
            "output_format": "png",
        },
        "seed_returned": result.get("seed") if isinstance(result, dict) else None,
    }
    destination.with_suffix(".inpaint.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def layerize_reference(
    reference: Path,
    output_dir: Path,
    *,
    prompt: str = "",
    image_size: str = "auto",
) -> dict[str, Any]:
    """Decompose a reference into named Seedream layers with one paid request."""
    if image_size not in ("auto", "auto_1K", "auto_1.5K", "auto_2K"):
        raise ValueError("image_size must be one of: auto, auto_1K, auto_1.5K, auto_2K.")
    if not reference.is_file():
        raise FileNotFoundError(f"Reference image not found: {reference}")

    _require_api_key()
    import fal_client

    image_url = fal_client.upload_file(str(reference))
    if not isinstance(image_url, str) or not image_url.startswith("https://"):
        raise RuntimeError("fal.ai did not return a valid HTTPS image URL.")

    arguments: dict[str, Any] = {
        "image_url": image_url,
        "image_size": image_size,
        "enable_safety_checker": True,
    }
    if prompt.strip():
        arguments["prompt"] = prompt.strip()

    print(f"Submitting one layerize request to {LAYERIZE_ENDPOINT}...")
    result: Any = fal_client.subscribe(
        LAYERIZE_ENDPOINT, arguments=arguments, with_logs=True
    )
    layers = result.get("layers") if isinstance(result, dict) else None
    if not isinstance(layers, list) or not layers:
        raise RuntimeError("Layerize response did not include a non-empty layers array.")

    layers_dir = output_dir / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for index, layer in enumerate(layers):
        image = layer.get("image") if isinstance(layer, dict) else None
        url = image.get("url") if isinstance(image, dict) else None
        if not isinstance(url, str):
            raise RuntimeError(f"Layer {index} did not include image.url.")
        raw_name = layer.get("name") or ("base" if index == 0 else f"layer_{index}")
        slug = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in str(raw_name).lower()
        ).strip("_")
        z_index = int(layer.get("z_index", index))
        destination = layers_dir / f"{z_index:02d}_{slug}.png"
        _download_asset(url, destination)
        records.append(
            {
                "index": index,
                "z_index": z_index,
                "name": layer.get("name"),
                "description": layer.get("description"),
                "bounding_box": layer.get("bounding_box"),
                "file": str(destination),
                "width": image.get("width"),
                "height": image.get("height"),
            }
        )

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": LAYERIZE_ENDPOINT,
        "reference": str(reference),
        "api_calls": 1,
        "parameters": {
            "prompt": prompt,
            "image_size": image_size,
            "enable_safety_checker": True,
        },
        "layers": records,
    }
    (output_dir / "layerize.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def _confirm_paid(action: str, count: int) -> bool:
    if not sys.stdin.isatty():
        print(
            f"{action} submits {count} potentially paid FAL request(s). "
            "Re-run with --yes only after reviewing the current price.",
            file=sys.stderr,
        )
        return False
    try:
        response = input(
            f"This uploads imagery and submits {count} potentially paid FAL "
            f"request(s) ({action}). Type YES to continue: "
        )
    except EOFError:
        return False
    return response == "YES"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Segment a reference into cutout parts, decompose it into named "
            "layers, or inpaint a hidden extension."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    segment_parser = subparsers.add_parser(
        "segment", help="Run EVF-SAM once per part prompt."
    )
    segment_parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    segment_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    segment_parser.add_argument(
        "--part",
        action="append",
        default=[],
        metavar="NAME=PROMPT[@X1,Y1,X2,Y2]",
        help="Repeatable part prompt, optionally restricted to a crop. Defaults to the built-in humanoid set.",
    )
    segment_parser.add_argument(
        "--min-component-pixels",
        type=int,
        default=200,
        help="Drop connected mask fragments smaller than this many pixels.",
    )
    segment_parser.add_argument(
        "--no-semantic-type",
        action="store_true",
        help="Disable semantic body-part segmentation in EVF-SAM.",
    )
    segment_parser.add_argument("--expand-mask", type=int, default=1)
    segment_parser.add_argument(
        "--no-fill-holes", action="store_true", help="Disable EVF-SAM hole filling."
    )
    segment_parser.add_argument("--use-grounding-dino", action="store_true")
    segment_parser.add_argument("--negative-prompt", type=str, default=None)
    segment_parser.add_argument(
        "--mask-threshold", type=int, default=DEFAULT_MASK_THRESHOLD
    )
    segment_parser.add_argument(
        "--yes", action="store_true", help="Confirm the paid EVF-SAM requests."
    )

    inpaint_parser = subparsers.add_parser(
        "inpaint", help="Run one FLUX Fill request for a masked extension."
    )
    inpaint_parser.add_argument("--image", type=Path, required=True)
    inpaint_parser.add_argument("--mask", type=Path, required=True)
    inpaint_parser.add_argument("--output", type=Path, required=True)
    inpaint_parser.add_argument("--prompt", required=True)
    inpaint_parser.add_argument("--seed", type=int, default=424242)
    inpaint_parser.add_argument(
        "--safety-tolerance", choices=("1", "2", "3", "4", "5", "6"), default="5"
    )
    inpaint_parser.add_argument("--num-images", type=int, default=1)
    inpaint_parser.add_argument(
        "--yes", action="store_true", help="Confirm the paid FLUX Fill request."
    )

    layerize_parser = subparsers.add_parser(
        "layerize", help="Decompose a reference into named layers with Seedream."
    )
    layerize_parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    layerize_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT.parent / "layerize")
    layerize_parser.add_argument(
        "--prompt",
        default="",
        help="Optional separation instructions; empty lets the model choose major elements.",
    )
    layerize_parser.add_argument(
        "--image-size",
        choices=("auto", "auto_1K", "auto_1.5K", "auto_2K"),
        default="auto",
    )
    layerize_parser.add_argument(
        "--yes", action="store_true", help="Confirm the paid layerize request."
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "segment":
            parts = parse_parts(args.part) if args.part else DEFAULT_PARTS
            if not args.yes and not _confirm_paid("EVF-SAM segmentation", len(parts)):
                print("Cancelled; nothing was uploaded and no segmentation was submitted.")
                return 2
            metadata = segment_parts(
                args.reference,
                args.output_dir,
                parts,
                semantic_type=not args.no_semantic_type,
                expand_mask=args.expand_mask,
                fill_holes=not args.no_fill_holes,
                use_grounding_dino=args.use_grounding_dino,
                negative_prompt=args.negative_prompt,
                mask_threshold=args.mask_threshold,
                min_component_pixels=args.min_component_pixels,
            )
            empty = [part["name"] for part in metadata["parts"] if part["empty"]]
            print(
                f"Wrote {metadata['api_calls']} masks to {args.output_dir / 'masks'} "
                f"and parts to {args.output_dir / 'parts'}."
            )
            if empty:
                print(
                    "Empty masks (review or rerun): " + ", ".join(empty),
                    file=sys.stderr,
                )
            return 0

        if args.command == "layerize":
            if not args.yes and not _confirm_paid("Seedream layerize", 1):
                print("Cancelled; nothing was uploaded and no layerize request was submitted.")
                return 2
            metadata = layerize_reference(
                args.reference,
                args.output_dir,
                prompt=args.prompt,
                image_size=args.image_size,
            )
            print(
                f"Wrote {len(metadata['layers'])} layers to "
                f"{args.output_dir / 'layers'}."
            )
            for layer in metadata["layers"]:
                label = layer["name"] or ("base" if layer["z_index"] == 0 else "unnamed")
                print(f"  z={layer['z_index']}: {label} -> {layer['file']}")
            return 0

        if not args.yes and not _confirm_paid("FLUX Fill inpainting", 1):
            print("Cancelled; nothing was uploaded and no inpainting was submitted.")
            return 2
        metadata = inpaint_part(
            args.image,
            args.mask,
            args.output,
            args.prompt,
            seed=args.seed,
            safety_tolerance=args.safety_tolerance,
            num_images=args.num_images,
        )
        print(f"Wrote inpainted part: {metadata['output']}")
        return 0
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

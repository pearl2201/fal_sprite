"""Generate an H3 Max Turbo clip and curate evenly sampled sprite frames."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import cv2
import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFERENCE = ROOT / "art_references" / "2.Low-Poly Warrior with Ornate Glaive.png"
DEFAULT_PROMPT = ROOT / "prompt" / "action_prompt.txt"
DEFAULT_OUTPUT = ROOT / "output" / "option2"
FAL_ENDPOINT = "minimax/h3-max-turbo/image-to-video"
BACKGROUND_ENDPOINT = "fal-ai/birefnet/v2"
MAX_VIDEO_BYTES = 300 * 1024 * 1024


def prepare_padded_reference(
    reference: Path,
    destination: Path,
    horizontal_padding: float = 0.25,
    vertical_padding: float = 0.10,
) -> dict[str, Any]:
    """Add clean border canvas without scaling or cropping the reference."""
    if not 0 <= horizontal_padding <= 1 or not 0 <= vertical_padding <= 1:
        raise ValueError("Padding fractions must be between 0 and 1.")

    with Image.open(reference) as source:
        image = source.convert("RGB")
    width, height = image.size
    horizontal_pixels = round(width * horizontal_padding)
    vertical_pixels = round(height * vertical_padding)
    corners = [
        image.getpixel((0, 0)),
        image.getpixel((width - 1, 0)),
        image.getpixel((0, height - 1)),
        image.getpixel((width - 1, height - 1)),
    ]
    background = tuple(
        sorted(color[channel] for color in corners)[len(corners) // 2]
        for channel in range(3)
    )
    canvas = Image.new(
        "RGB",
        (width + 2 * horizontal_pixels, height + 2 * vertical_pixels),
        background,
    )
    canvas.paste(image, (horizontal_pixels, vertical_pixels))
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, format="PNG")
    return {
        "original_size": {"width": width, "height": height},
        "padded_size": {
            "width": canvas.width,
            "height": canvas.height,
        },
        "padding_per_side_pixels": {
            "horizontal": horizontal_pixels,
            "vertical": vertical_pixels,
        },
        "background_rgb": list(background),
    }


def load_project_env(env_path: Path) -> None:
    """Load project env vars without overriding the caller's environment."""
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith(("'", '"')) and value.endswith(value[0]):
            value = value[1:-1]
        if key and value:
            os.environ.setdefault(key, value)

    if not os.environ.get("FAL_KEY"):
        for alias in ("FAL_API", "FAL_API_KEY"):
            if os.environ.get(alias):
                os.environ["FAL_KEY"] = os.environ[alias]
                break


def _download_asset(asset_url: str, destination: Path) -> None:
    parsed = urlparse(asset_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("The model returned an asset URL that is not HTTPS.")

    request = urllib.request.Request(
        asset_url,
        headers={"User-Agent": "fal-sprite-option2/1.0"},
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    completed = False
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_VIDEO_BYTES:
                raise ValueError("The generated asset exceeds the 300 MiB download limit.")
            with destination.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    written += len(chunk)
                    if written > MAX_VIDEO_BYTES:
                        raise ValueError("The generated asset exceeds the 300 MiB download limit.")
                    output.write(chunk)
        completed = True
    finally:
        if not completed:
            destination.unlink(missing_ok=True)

    if written == 0:
        destination.unlink(missing_ok=True)
        raise RuntimeError("The generated asset download was empty.")


def generate_video(
    reference: Path,
    prompt_path: Path,
    output_dir: Path,
    horizontal_padding: float = 0.25,
    vertical_padding: float = 0.10,
    duration: float = 5.0,
    resolution: str = "768P",
    seed: int | None = 424242,
    prompt_expansion_mode: str = "disabled",
) -> Path:
    """Upload a padded reference and submit one paid H3 Max Turbo generation."""
    if not 0.92 <= duration <= 15:
        raise ValueError("duration must be between 0.92 and 15 seconds.")
    if resolution not in ("480P", "768P", "1080P"):
        raise ValueError("resolution must be one of: 480P, 768P, 1080P.")
    if prompt_expansion_mode not in ("disabled", "balanced", "quality"):
        raise ValueError(
            "prompt_expansion_mode must be one of: disabled, balanced, quality."
        )
    if seed is not None and seed < 0:
        raise ValueError("seed must be a non-negative integer or None.")
    if horizontal_padding <= 0 or vertical_padding <= 0:
        raise ValueError(
            "The reference must be padded before generation so the weapon, hair, and "
            "limbs stay inside the frame. Pass a positive --horizontal-padding and "
            "--vertical-padding (defaults: 0.25 and 0.10)."
        )
    load_project_env(ROOT / ".env")
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("FAL_KEY is missing. Add it to the environment or project .env file.")
    if not reference.is_file():
        raise FileNotFoundError(f"Reference image not found: {reference}")
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Action prompt not found: {prompt_path}")

    import fal_client

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"Action prompt is empty: {prompt_path}")

    padded_reference = output_dir / "padded_reference.png"
    padding_metadata = prepare_padded_reference(
        reference,
        padded_reference,
        horizontal_padding,
        vertical_padding,
    )
    print(
        "Uploading padded reference image to fal.ai "
        f"({padding_metadata['padded_size']['width']}x"
        f"{padding_metadata['padded_size']['height']})..."
    )
    image_url = fal_client.upload_file(str(padded_reference))
    if not isinstance(image_url, str) or not image_url.startswith("https://"):
        raise RuntimeError("fal.ai did not return a valid HTTPS image URL.")

    parameters: dict[str, Any] = {
        "duration": duration,
        "resolution": resolution,
        "prompt_expansion_mode": prompt_expansion_mode,
        "seed": seed,
    }
    print(f"Submitting one generation to {FAL_ENDPOINT} ({parameters})...")
    result: Any = fal_client.subscribe(
        FAL_ENDPOINT,
        arguments={"image_url": image_url, "prompt": prompt, **parameters},
        with_logs=True,
    )
    video_data = result.get("video") if isinstance(result, dict) else None
    video_url = video_data.get("url") if isinstance(video_data, dict) else None
    if not isinstance(video_url, str):
        raise RuntimeError(
            "The model response did not include video.url. "
            "Check the FAL endpoint response/schema before retrying."
        )

    destination = output_dir / "source_video.mp4"
    print(f"Downloading generated clip to {destination}...")
    _download_asset(video_url, destination)
    generation_metadata = {
        "endpoint": FAL_ENDPOINT,
        "original_reference": str(reference),
        "uploaded_reference": padded_reference.name,
        "padding": padding_metadata,
        "parameters": parameters,
    }
    (output_dir / "generation.json").write_text(
        json.dumps(generation_metadata, indent=2),
        encoding="utf-8",
    )
    return destination


def _sample_indices(frame_total: int, requested: int) -> list[int]:
    if frame_total < 1:
        raise ValueError("The video contains no readable frames.")
    count = min(frame_total, requested)
    if count == 1:
        return [0]
    return [
        round(index * (frame_total - 1) / (count - 1))
        for index in range(count)
    ]


def _select_diverse_indices(
    thumbnails: list[Any],
    requested: int,
    min_distance: float = 7.0,
) -> list[int]:
    """Select distinct-looking frames while keeping the sequence's temporal order."""
    if not thumbnails:
        raise ValueError("The video contains no readable frames.")
    if requested < 1:
        raise ValueError("requested must be at least 1.")

    selected = [0]
    while len(selected) < min(requested, len(thumbnails)):
        best_index = -1
        best_distance = min_distance
        for index, thumbnail in enumerate(thumbnails):
            if index in selected:
                continue
            nearest_distance = min(
                cv2.mean(cv2.absdiff(thumbnail, thumbnails[chosen]))[0]
                for chosen in selected
            )
            if nearest_distance > best_distance:
                best_index = index
                best_distance = nearest_distance
        if best_index < 0:
            break
        selected.append(best_index)
    return sorted(selected)


def _normalized_subject(
    image_source: Path | Image.Image,
    size: int = 128,
    working_size: int = 512,
) -> Image.Image:
    """Return a fixed white canvas holding the cropped subject, for similarity scoring.

    The image is downscaled to ``working_size`` before array work so a large
    reference or high-resolution frame cannot exhaust memory.
    """
    if isinstance(image_source, Image.Image):
        image = image_source.convert("RGBA")
    else:
        with Image.open(image_source) as source:
            image = source.convert("RGBA")
    if max(image.size) > working_size:
        image.thumbnail((working_size, working_size), Image.Resampling.LANCZOS)
    rgba = np.asarray(image)
    if "A" in image.getbands() and np.min(rgba[:, :, 3]) < 255:
        mask = rgba[:, :, 3] > 8
    else:
        rgb = rgba[:, :, :3].astype(np.int16)
        corners = np.stack((rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]))
        background = np.median(corners, axis=0)
        mask = np.max(np.abs(rgb - background), axis=2) > 18

    ys, xs = np.where(mask)
    if len(xs):
        image = image.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    else:
        image = image.convert("RGB").convert("RGBA")

    image.thumbnail((size - 16, size - 16), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    canvas.alpha_composite(
        image,
        ((size - image.width) // 2, (size - image.height) // 2),
    )
    return canvas.convert("RGB")


def _reference_endpoint_bounds(
    first_frame: Image.Image,
    last_frame: Image.Image,
    frame_total: int,
    reference_path: Path | None,
    threshold: float,
) -> tuple[int, int, dict[str, Any]]:
    if not 0 <= threshold <= 1:
        raise ValueError("reference similarity threshold must be between 0 and 1.")
    comparison: dict[str, Any] = {
        "reference_image": str(reference_path.resolve()) if reference_path else None,
        "similarity_threshold": threshold,
        "first_similarity": None,
        "last_similarity": None,
        "first_removed": False,
        "last_removed": False,
    }
    if reference_path is None or frame_total < 1:
        return 0, frame_total, comparison

    first_similarity = _image_reference_similarity(first_frame, reference_path)
    last_similarity = (
        _image_reference_similarity(last_frame, reference_path)
        if frame_total > 1
        else first_similarity
    )
    comparison["first_similarity"] = round(first_similarity, 4)
    comparison["last_similarity"] = round(last_similarity, 4)

    start = 1 if frame_total > 1 and first_similarity >= threshold else 0
    end = (
        frame_total - 1
        if frame_total - start > 1 and last_similarity >= threshold
        else frame_total
    )
    comparison["first_removed"] = start > 0
    comparison["last_removed"] = end < frame_total
    return start, end, comparison


def _image_reference_similarity(image: Image.Image, reference_path: Path) -> float:
    reference = np.asarray(_normalized_subject(reference_path), dtype=np.int16)
    candidate = np.asarray(_normalized_subject(image), dtype=np.int16)
    difference = np.abs(reference - candidate).mean()
    return float(1.0 - difference / 255.0)


def _resolve_reference_image(
    reference_image: Path | None,
    source_dir: Path,
) -> Path | None:
    if reference_image is not None:
        if not reference_image.is_file():
            raise FileNotFoundError(f"Reference image not found: {reference_image}")
        return reference_image

    generation_path = source_dir / "generation.json"
    if not generation_path.is_file():
        return None
    try:
        generation = json.loads(generation_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid generation metadata: {generation_path}") from error

    uploaded_reference = generation.get("uploaded_reference")
    original_reference = generation.get("original_reference")
    for candidate in (
        source_dir / uploaded_reference if uploaded_reference else None,
        Path(original_reference) if original_reference else None,
    ):
        if candidate is not None and candidate.is_file():
            return candidate
    return None


def _remove_background_single(image_path: Path, destination: Path) -> Image.Image:
    """Submit one paid BiRefNet request and save its transparent result."""
    import fal_client

    image_url = fal_client.upload_file(str(image_path))
    if not isinstance(image_url, str) or not image_url.startswith("https://"):
        raise RuntimeError(f"fal.ai did not return a valid URL for {image_path.name}.")

    result: Any = fal_client.subscribe(
        BACKGROUND_ENDPOINT,
        arguments={
            "image_url": image_url,
            "model": "General Use (Light)",
            "operating_resolution": "2048x2048",
            "output_format": "png",
            "refine_foreground": True,
            "output_mask": False,
        },
        with_logs=True,
    )
    image_data = result.get("image") if isinstance(result, dict) else None
    result_url = image_data.get("url") if isinstance(image_data, dict) else None
    if not isinstance(result_url, str):
        raise RuntimeError(
            f"BiRefNet response for {image_path.name} did not include image.url."
        )

    _download_asset(result_url, destination)
    with Image.open(destination) as removed_background:
        rgba = removed_background.convert("RGBA")
    if rgba.getchannel("A").getextrema() == (255, 255):
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            f"BiRefNet output for {image_path.name} has no transparency; "
            "the source image was preserved."
        )
    rgba.save(destination, format="PNG")
    return rgba


def _write_alpha_contact_sheet(
    tiles: list[Image.Image],
    destination: Path,
    columns: int = 4,
) -> None:
    columns = max(1, min(columns, len(tiles)))
    rows = (len(tiles) + columns - 1) // columns
    tile_width, tile_height = tiles[0].size
    contact_width = min(tile_width, 320)
    contact_height = max(1, round(tile_height * contact_width / tile_width))
    contact = Image.new("RGB", (contact_width * columns, (contact_height + 28) * rows), "white")
    draw = ImageDraw.Draw(contact)

    for index, image in enumerate(tiles):
        thumb = image.resize((contact_width, contact_height), Image.Resampling.LANCZOS)
        x = (index % columns) * contact_width
        y = (index // columns) * (contact_height + 28)
        contact.paste(thumb, (x, y), thumb)
        draw.text((x + 6, y + contact_height + 6), f"Frame {index:03d}", fill="black")

    contact.save(destination, quality=90)


def _stack_alpha_tiles(tiles: list[Image.Image], columns: int = 4) -> Image.Image:
    columns = max(1, min(columns, len(tiles)))
    rows = (len(tiles) + columns - 1) // columns
    tile_width, tile_height = tiles[0].size
    atlas = Image.new("RGBA", (tile_width * columns, tile_height * rows), (0, 0, 0, 0))
    for index, image in enumerate(tiles):
        atlas.alpha_composite(image, ((index % columns) * tile_width, (index // columns) * tile_height))
    return atlas


def remove_background_from_frames(
    frames_dir: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    """Remove backgrounds per frame: highest mask resolution, one call per frame."""
    load_project_env(ROOT / ".env")
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("FAL_KEY is missing. Add it to the environment or project .env file.")
    if not frames_dir.is_dir():
        raise FileNotFoundError(f"Frame directory not found: {frames_dir}")

    frame_paths = sorted(frames_dir.glob("frame_*.png"))
    if not frame_paths:
        raise FileNotFoundError(f"No sampled PNG frames found in {frames_dir}")

    output_alpha_dir = output_dir / "frames_alpha"
    output_alpha_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    transparent_tiles: list[Image.Image] = []

    for frame_path in frame_paths:
        print(f"Removing background from {frame_path.name}...")
        destination = output_alpha_dir / frame_path.name
        rgba = _remove_background_single(frame_path, destination)
        transparent_tiles.append(rgba)
        records.append(
            {
                "source": f"frames/{frame_path.name}",
                "output": f"frames_alpha/{frame_path.name}",
                "width": rgba.width,
                "height": rgba.height,
            }
        )

    if not transparent_tiles:
        return records

    _stack_alpha_tiles(transparent_tiles).save(output_dir / "spritesheet_alpha.png")
    _write_alpha_contact_sheet(transparent_tiles, output_dir / "contact_sheet_alpha.jpg")
    metadata_path = output_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    metadata["background_removal"] = {
        "endpoint": BACKGROUND_ENDPOINT,
        "model": "General Use (Light)",
        "operating_resolution": "2048x2048",
        "mode": "frames",
        "api_calls": len(records),
        "frame_count": len(records),
        "frames": records,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return records


def remove_background_from_sheet(output_dir: Path) -> list[dict[str, Any]]:
    """Remove background from the packed spritesheet with one BiRefNet request.

    One call per animation instead of one per frame. BiRefNet resizes its input to
    ``operating_resolution``, so a wide atlas gives each character fewer pixels than
    a per-frame call; use ``frames`` mode when edge fidelity matters more than cost.
    """
    load_project_env(ROOT / ".env")
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("FAL_KEY is missing. Add it to the environment or project .env file.")

    sheet_path = output_dir / "spritesheet.png"
    metadata_path = output_dir / "metadata.json"
    if not sheet_path.is_file():
        raise FileNotFoundError(f"Spritesheet not found: {sheet_path}. Build it first.")
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Metadata not found: {metadata_path}. Build the sheet first.")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    layout = metadata.get("layout") or {}
    frame_size = metadata.get("frame_size") or {}
    columns = int(layout.get("columns") or 0)
    rows = int(layout.get("rows") or 0)
    frame_count = int(metadata.get("sampled_frame_count") or 0)
    tile_width = int(frame_size.get("width") or 0)
    tile_height = int(frame_size.get("height") or 0)
    if min(columns, rows, frame_count, tile_width, tile_height) < 1:
        raise ValueError("Spritesheet metadata is missing layout or frame dimensions.")
    if columns * rows < frame_count:
        raise ValueError(
            f"Layout {columns}x{rows} cannot hold {frame_count} frames."
        )

    with Image.open(sheet_path) as source:
        sheet_size = source.size
    expected_size = (tile_width * columns, tile_height * rows)
    if sheet_size != expected_size:
        raise ValueError(
            f"Spritesheet is {sheet_size[0]}x{sheet_size[1]} but layout "
            f"{columns}x{rows} of {tile_width}x{tile_height} implies "
            f"{expected_size[0]}x{expected_size[1]}."
        )

    print(
        f"Removing background from packed spritesheet {sheet_path.name} "
        f"({sheet_size[0]}x{sheet_size[1]}) in one request..."
    )
    alpha_sheet_path = output_dir / "spritesheet_alpha.png"
    alpha_sheet = _remove_background_single(sheet_path, alpha_sheet_path)
    if alpha_sheet.size != expected_size:
        alpha_sheet = alpha_sheet.resize(expected_size, Image.Resampling.LANCZOS)
        alpha_sheet.save(alpha_sheet_path, format="PNG")

    output_alpha_dir = output_dir / "frames_alpha"
    output_alpha_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    transparent_tiles: list[Image.Image] = []
    for index in range(frame_count):
        column = index % columns
        row = index // columns
        tile = alpha_sheet.crop(
            (
                column * tile_width,
                row * tile_height,
                (column + 1) * tile_width,
                (row + 1) * tile_height,
            )
        )
        frame_name = f"frame_{index:03d}.png"
        tile.save(output_alpha_dir / frame_name, format="PNG")
        transparent_tiles.append(tile)
        records.append(
            {
                "source": f"spritesheet.png#{frame_name}",
                "output": f"frames_alpha/{frame_name}",
                "width": tile.width,
                "height": tile.height,
            }
        )

    _write_alpha_contact_sheet(transparent_tiles, output_dir / "contact_sheet_alpha.jpg", columns)

    metadata["background_removal"] = {
        "endpoint": BACKGROUND_ENDPOINT,
        "model": "General Use (Light)",
        "operating_resolution": "2048x2048",
        "mode": "sheet",
        "api_calls": 1,
        "frame_count": len(records),
        "frames": records,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return records


def apply_background_removal(output_dir: Path, mode: str = "sheet") -> list[dict[str, Any]]:
    """Run BiRefNet on one packed sheet (cheapest) or on every sampled frame."""
    if mode == "sheet":
        return remove_background_from_sheet(output_dir)
    if mode == "frames":
        return remove_background_from_frames(output_dir / "frames", output_dir)
    raise ValueError("background mode must be 'sheet' or 'frames'.")


def process_video(
    video_path: Path,
    output_dir: Path,
    frame_count: int = 8,
    columns: int = 4,
    selection: str = "diverse",
    reference_image: Path | None = None,
    reference_similarity_threshold: float = 0.95,
    keep_reference_endpoints: bool = False,
) -> list[dict[str, Any]]:
    """Sample a clip uniformly and produce frames, contact sheet, atlas, and metadata."""
    if not video_path.is_file():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if frame_count < 1:
        raise ValueError("frame_count must be at least 1.")
    if columns < 1:
        raise ValueError("columns must be at least 1.")
    if selection not in {"diverse", "uniform"}:
        raise ValueError("selection must be 'diverse' or 'uniform'.")
    if not 0 <= reference_similarity_threshold <= 1:
        raise ValueError("reference similarity threshold must be between 0 and 1.")

    resolved_reference = _resolve_reference_image(reference_image, video_path.parent)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width < 1 or height < 1:
            raise RuntimeError(f"Video has invalid dimensions: {video_path}")

        if frame_total < 1:
            raise RuntimeError(f"Video has no readable frames: {video_path}")
        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        success, first_bgr = capture.read()
        if not success:
            raise RuntimeError("Could not decode the video's first frame.")
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_total - 1)
        success, last_bgr = capture.read()
        if not success:
            raise RuntimeError("Could not decode the video's last frame.")
        first_rgb = cv2.cvtColor(first_bgr, cv2.COLOR_BGR2RGB)
        last_rgb = cv2.cvtColor(last_bgr, cv2.COLOR_BGR2RGB)
        if keep_reference_endpoints:
            source_start, source_end = 0, frame_total
            endpoint_comparison = {
                "enabled": False,
                "reference_image": str(resolved_reference.resolve()) if resolved_reference else None,
                "similarity_threshold": reference_similarity_threshold,
                "first_similarity": None,
                "last_similarity": None,
                "first_removed": False,
                "last_removed": False,
            }
        else:
            source_start, source_end, endpoint_comparison = _reference_endpoint_bounds(
                Image.fromarray(first_rgb),
                Image.fromarray(last_rgb),
                frame_total,
                resolved_reference,
                reference_similarity_threshold,
            )
            endpoint_comparison["enabled"] = True
        candidate_count = source_end - source_start

        if selection == "diverse":
            thumbnails = []
            for source_index in range(source_start, source_end):
                capture.set(cv2.CAP_PROP_POS_FRAMES, source_index)
                success, frame = capture.read()
                if not success:
                    raise RuntimeError(f"Could not decode source frame {source_index}.")
                resized = cv2.resize(frame, (64, 64), interpolation=cv2.INTER_AREA)
                thumbnails.append(cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY))
            indices = [
                source_start + index
                for index in _select_diverse_indices(thumbnails, frame_count)
            ]
        else:
            indices = [
                source_start + index
                for index in _sample_indices(candidate_count, frame_count)
            ]
        output_dir.mkdir(parents=True, exist_ok=True)
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        tile_images: list[Image.Image] = []
        records: list[dict[str, Any]] = []

        for output_index, source_index in enumerate(indices):
            capture.set(cv2.CAP_PROP_POS_FRAMES, source_index)
            success, bgr_frame = capture.read()
            if not success:
                raise RuntimeError(f"Could not decode source frame {source_index}.")
            rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb_frame)
            frame_name = f"frame_{output_index:03d}.png"
            image.save(frames_dir / frame_name)
            tile_images.append(image)
            records.append(
                {
                    "index": output_index,
                    "file": f"frames/{frame_name}",
                    "source_frame": source_index,
                    "timestamp_seconds": round(source_index / fps, 4) if fps > 0 else None,
                }
            )
    finally:
        capture.release()

    columns = min(columns, len(tile_images))
    rows = (len(tile_images) + columns - 1) // columns
    sheet = Image.new("RGB", (width * columns, height * rows), "white")
    contact_tile_width = min(width, 320)
    contact_tile_height = max(1, round(height * contact_tile_width / width))
    contact_columns = min(columns, len(tile_images))
    contact_rows = (len(tile_images) + contact_columns - 1) // contact_columns
    contact_sheet = Image.new(
        "RGB",
        (contact_tile_width * contact_columns, (contact_tile_height + 28) * contact_rows),
        "#e8e8e8",
    )
    draw = ImageDraw.Draw(contact_sheet)

    for index, image in enumerate(tile_images):
        column = index % columns
        row = index // columns
        sheet.paste(image, (column * width, row * height))

        thumb = image.resize((contact_tile_width, contact_tile_height), Image.Resampling.LANCZOS)
        contact_x = (index % contact_columns) * contact_tile_width
        contact_y = (index // contact_columns) * (contact_tile_height + 28)
        contact_sheet.paste(thumb, (contact_x, contact_y))
        draw.text((contact_x + 6, contact_y + contact_tile_height + 6), f"Frame {index:03d}", fill="black")

    sheet.save(output_dir / "spritesheet.png")
    contact_sheet.save(output_dir / "contact_sheet.jpg", quality=90)
    metadata = {
        "source_video": str(video_path.resolve()),
        "video_fps": fps if fps > 0 else None,
        "source_frame_count": frame_total,
        "frame_size": {"width": width, "height": height},
        "sampled_frame_count": len(records),
        "selection": selection,
        "reference_endpoint_comparison": endpoint_comparison,
        "layout": {"columns": columns, "rows": rows},
        "background": "Preserved from source video; no transparency/keying applied.",
        "frames": records,
    }
    generation_metadata_path = output_dir / "generation.json"
    if generation_metadata_path.is_file():
        metadata["generation"] = json.loads(
            generation_metadata_path.read_text(encoding="utf-8")
        )
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    return records


def _confirm_generation(remove_background: bool = False, background_mode: str = "sheet") -> bool:
    if not sys.stdin.isatty():
        print(
            "FAL generation can incur charges. Re-run with --yes only after reviewing "
            "the endpoint's current prices and terms.",
            file=sys.stderr,
        )
        return False
    charge_description = "submit one potentially paid video generation"
    if remove_background:
        if background_mode == "sheet":
            charge_description += " and one potentially paid background-removal request for the packed spritesheet"
        else:
            charge_description += " and one potentially paid background-removal request per sampled frame"
    try:
        response = input(
            f"This uploads the reference and will {charge_description}. "
            "Type GENERATE to continue: "
        )
    except EOFError:
        return False
    return response == "GENERATE"


def _confirm_background_removal(background_mode: str = "sheet") -> bool:
    if background_mode == "sheet":
        scope = "one BiRefNet request for the packed spritesheet"
    else:
        scope = "one BiRefNet request per sampled frame"
    if not sys.stdin.isatty():
        print(
            f"Background removal submits {scope}. "
            "Re-run with --yes only after checking the current endpoint price.",
            file=sys.stderr,
        )
        return False
    try:
        response = input(
            f"This uploads imagery and submits potentially paid BiRefNet requests "
            f"({scope}). Type REMOVE BACKGROUNDS to continue: "
        )
    except EOFError:
        return False
    return response == "REMOVE BACKGROUNDS"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an H3 Max Turbo clip, then extract a uniformly sampled spritesheet."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="Generate a clip and process its frames.")
    generate_parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    generate_parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    generate_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    generate_parser.add_argument("--frame-count", type=int, default=8)
    generate_parser.add_argument("--columns", type=int, default=4)
    generate_parser.add_argument("--selection", choices=("diverse", "uniform"), default="diverse")
    generate_parser.add_argument("--reference-similarity-threshold", type=float, default=0.95)
    generate_parser.add_argument(
        "--keep-reference-endpoints",
        action="store_true",
        help="Keep clip endpoints even when they match the reference (useful for idle loops).",
    )
    generate_parser.add_argument("--horizontal-padding", type=float, default=0.25)
    generate_parser.add_argument("--vertical-padding", type=float, default=0.10)
    generate_parser.add_argument("--duration", type=float, default=5.0)
    generate_parser.add_argument(
        "--resolution", choices=("480P", "768P", "1080P"), default="768P"
    )
    generate_parser.add_argument("--seed", type=int, default=424242)
    generate_parser.add_argument(
        "--prompt-expansion-mode",
        choices=("disabled", "balanced", "quality"),
        default="disabled",
        help="Disable prompt rewriting so the no-effects and locked-camera constraints survive.",
    )
    generate_parser.add_argument(
        "--remove-background",
        action="store_true",
        help="Run potentially paid BiRefNet background removal after the sheet is built.",
    )
    generate_parser.add_argument(
        "--background-mode",
        choices=("sheet", "frames"),
        default="sheet",
        help=(
            "sheet: one BiRefNet call per spritesheet (cheapest, lower per-character "
            "resolution). frames: one call per sampled frame (sharpest edges)."
        ),
    )
    generate_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm all potentially paid FAL requests in this command.",
    )

    process_parser = subparsers.add_parser("process", help="Process an existing local video without API calls.")
    process_parser.add_argument("video", type=Path)
    process_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    process_parser.add_argument("--frame-count", type=int, default=8)
    process_parser.add_argument("--columns", type=int, default=4)
    process_parser.add_argument("--selection", choices=("diverse", "uniform"), default="diverse")
    process_parser.add_argument("--reference-image", type=Path)
    process_parser.add_argument("--reference-similarity-threshold", type=float, default=0.95)
    process_parser.add_argument(
        "--keep-reference-endpoints",
        action="store_true",
        help="Keep clip endpoints even when they match the reference (useful for idle loops).",
    )
    process_parser.add_argument(
        "--remove-background",
        action="store_true",
        help="Run potentially paid BiRefNet background removal after the sheet is built.",
    )
    process_parser.add_argument(
        "--background-mode",
        choices=("sheet", "frames"),
        default="sheet",
        help=(
            "sheet: one BiRefNet call per spritesheet (cheapest, lower per-character "
            "resolution). frames: one call per sampled frame (sharpest edges)."
        ),
    )
    process_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm paid background-removal requests.",
    )

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Create a padded reference preview without calling any API.",
    )
    prepare_parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    prepare_parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT / "padded_reference.png",
    )
    prepare_parser.add_argument("--horizontal-padding", type=float, default=0.25)
    prepare_parser.add_argument("--vertical-padding", type=float, default=0.10)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "generate":
            if not args.yes and not _confirm_generation(
                args.remove_background, args.background_mode
            ):
                print("Cancelled; no reference was uploaded and no generation was submitted.")
                return 2
            video_path = generate_video(
                args.reference,
                args.prompt,
                args.output_dir,
                args.horizontal_padding,
                args.vertical_padding,
                duration=args.duration,
                resolution=args.resolution,
                seed=args.seed,
                prompt_expansion_mode=args.prompt_expansion_mode,
            )
            records = process_video(
                video_path,
                args.output_dir,
                args.frame_count,
                args.columns,
                args.selection,
                reference_image=args.reference,
                reference_similarity_threshold=args.reference_similarity_threshold,
                keep_reference_endpoints=args.keep_reference_endpoints,
            )
            if args.remove_background:
                apply_background_removal(args.output_dir, args.background_mode)
        elif args.command == "process":
            if (
                args.remove_background
                and not args.yes
                and not _confirm_background_removal(args.background_mode)
            ):
                print("Cancelled; no images were uploaded and no background removal was submitted.")
                return 2
            records = process_video(
                args.video,
                args.output_dir,
                args.frame_count,
                args.columns,
                args.selection,
                reference_image=args.reference_image,
                reference_similarity_threshold=args.reference_similarity_threshold,
                keep_reference_endpoints=args.keep_reference_endpoints,
            )
            if args.remove_background:
                apply_background_removal(args.output_dir, args.background_mode)
        else:
            metadata = prepare_padded_reference(
                args.reference,
                args.output,
                args.horizontal_padding,
                args.vertical_padding,
            )
            print(
                f"Created {args.output.resolve()} "
                f"({metadata['padded_size']['width']}x{metadata['padded_size']['height']})"
            )
            print("No API was called.")
            return 0
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Processed {len(records)} frames.")
    print(f"Output: {args.output_dir.resolve()}")
    metadata_path = args.output_dir / "metadata.json"
    if metadata_path.is_file():
        endpoint_comparison = json.loads(
            metadata_path.read_text(encoding="utf-8")
        ).get("reference_endpoint_comparison", {})
        if endpoint_comparison.get("reference_image"):
            print(
                "Reference endpoint comparison: "
                f"first={endpoint_comparison['first_similarity']}, "
                f"last={endpoint_comparison['last_similarity']}, "
                f"removed first={endpoint_comparison['first_removed']}, "
                f"last={endpoint_comparison['last_removed']}."
            )
    print("Files: frames\\, spritesheet.png, contact_sheet.jpg, metadata.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build a combined overview image and index for one character's animation set."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

if __package__ in (None, ""):  # allow `python scripts\animation_set_report.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_animation_gif import DEFAULT_ORDER, discover_animations


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_LABELS = {
    "idle": "Idle (loop)",
    "walk": "Walk",
    "run": "Run",
    "normal_attack": "Normal Attack",
    "skill_attack": "Skill Attack",
    "hurt": "Hurt",
    "death": "Death",
}


def resolve_order(root: Path, order: list[str] | None) -> list[str]:
    """Return animation names in requested order, then any remaining folders."""
    names = [name for name, _ in discover_animations(root, list(order or DEFAULT_ORDER))]
    return names


def build_overview(
    root: Path,
    order: list[str] | None = None,
    destination: Path | None = None,
    *,
    title: str | None = None,
    tile_width: int = 150,
    tile_height: int = 190,
) -> Path:
    """Render every animation as one row of cropped, alpha-composited thumbnails."""
    if not root.is_dir():
        raise FileNotFoundError(f"Animation root not found: {root}")
    if tile_width < 40 or tile_height < 40:
        raise ValueError("tile_width and tile_height must be at least 40.")

    names = resolve_order(root, order)
    if not names:
        raise FileNotFoundError(f"No animation frames found under {root}")

    widest = max(len(list((root / name / "frames_alpha").glob("frame_*.png")) or
                     list((root / name / "frames").glob("frame_*.png")))
                 for name in names)
    label_width = 150
    header = 48
    gap = 24
    canvas = Image.new(
        "RGB",
        (label_width + widest * tile_width, header + len(names) * (tile_height + gap)),
        "#f2f2f2",
    )
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 8), title or f"Animation set - {root.name}", fill="black")
    draw.text((10, 26), "8 frames per action unless noted; alpha composited", fill="#555555")

    for row, name in enumerate(names):
        directory = root / name
        frames = sorted((directory / "frames_alpha").glob("frame_*.png"))
        if not frames:
            frames = sorted((directory / "frames").glob("frame_*.png"))
        y = header + row * (tile_height + gap)
        draw.text((10, y + tile_height // 2 - 6), DEFAULT_LABELS.get(name, name), fill="black")
        for column, path in enumerate(frames):
            with Image.open(path) as image:
                rgba = image.convert("RGBA")
            bbox = rgba.getchannel("A").getbbox()
            cropped = rgba.crop(bbox) if bbox else rgba
            cropped.thumbnail((tile_width - 10, tile_height - 10), Image.Resampling.LANCZOS)
            preview = Image.new("RGB", (tile_width, tile_height), "white")
            preview.paste(
                cropped,
                ((tile_width - cropped.width) // 2, (tile_height - cropped.height) // 2),
                cropped,
            )
            x = label_width + column * tile_width
            canvas.paste(preview, (x, y))
            draw.rectangle([x, y, x + tile_width - 1, y + tile_height - 1], outline="#dddddd")
            draw.text((x + 4, y + tile_height + 4), f"{column:02d}", fill="#666666")

    destination = destination or root / "animation_set_overview.jpg"
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, quality=92)
    return destination


def write_index(
    root: Path,
    order: list[str] | None = None,
    destination: Path | None = None,
    *,
    character: str | None = None,
) -> Path:
    """Write a JSON index of the set: frame timings, provenance, and endpoint decisions."""
    names = resolve_order(root, order)
    if not names:
        raise FileNotFoundError(f"No animation frames found under {root}")

    animations: list[dict[str, Any]] = []
    for name in names:
        directory = root / name
        frames = sorted((directory / "frames_alpha").glob("frame_*.png"))
        if not frames:
            frames = sorted((directory / "frames").glob("frame_*.png"))
        metadata_path = directory / "metadata.json"
        metadata = (
            json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata_path.is_file()
            else {}
        )
        background = metadata.get("background_removal") or {}
        generation = metadata.get("generation") or {}
        animations.append(
            {
                "name": name,
                "label": DEFAULT_LABELS.get(name, name),
                "frame_count": len(frames),
                "directory": str(directory),
                "spritesheet": str(directory / "spritesheet_alpha.png")
                if (directory / "spritesheet_alpha.png").is_file()
                else str(directory / "spritesheet.png"),
                "contact_sheet": str(directory / "contact_sheet_alpha.jpg")
                if (directory / "contact_sheet_alpha.jpg").is_file()
                else str(directory / "contact_sheet.jpg"),
                "metadata": str(metadata_path) if metadata_path.is_file() else None,
                "source_video": metadata.get("source_video"),
                "frame_times": [frame.get("timestamp_seconds") for frame in metadata.get("frames", [])],
                "reference_endpoint_comparison": metadata.get("reference_endpoint_comparison"),
                "background_removal": {
                    "endpoint": background.get("endpoint"),
                    "mode": background.get("mode"),
                    "api_calls": background.get("api_calls"),
                },
                "generation": {
                    "endpoint": generation.get("endpoint"),
                    "original_reference": generation.get("original_reference"),
                    "padding": generation.get("padding"),
                },
            }
        )

    payload = {
        "character": character or root.name,
        "animation_root": str(root),
        "animation_order": names,
        "animations": animations,
    }
    destination = destination or root / "animation_set_index.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an overview image and JSON index for an animation set (no API calls)."
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--order", default=",".join(DEFAULT_ORDER))
    parser.add_argument("--overview", type=Path)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--title")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    order = [part.strip() for part in args.order.split(",") if part.strip()]
    try:
        overview = build_overview(args.root, order, args.overview, title=args.title)
        index = write_index(args.root, order, args.index)
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Overview: {overview}")
    print(f"Index: {index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

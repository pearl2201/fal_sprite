"""Combine per-animation sprite frames into one ordered review GIF."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "output" / "option2_animation_set"
DEFAULT_OUTPUT = DEFAULT_ROOT / "animation_set.gif"
DEFAULT_ORDER = ("idle", "walk", "run", "normal_attack", "skill_attack", "hurt", "death")


def discover_animations(root: Path, order: list[str]) -> list[tuple[str, Path]]:
    """Return animations in the requested order, then any remaining folders alphabetically."""
    if not root.is_dir():
        raise FileNotFoundError(f"Animation root not found: {root}")

    available = {
        directory.name: directory
        for directory in sorted(root.iterdir())
        if directory.is_dir()
        and (
            any((directory / "frames_alpha").glob("frame_*.png"))
            or any((directory / "frames").glob("frame_*.png"))
        )
    }

    discovered: list[tuple[str, Path]] = []
    for name in order:
        normalized = name.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized in available:
            discovered.append((normalized, available.pop(normalized)))
    for name in sorted(available):
        discovered.append((name, available[name]))
    return discovered


def load_frames(directory: Path, prefer: str) -> tuple[str, list[Image.Image]]:
    """Load alpha frames when available, otherwise raw frames."""
    alpha_dir = directory / "frames_alpha"
    raw_dir = directory / "frames"
    order = (alpha_dir, raw_dir) if prefer == "alpha" else (raw_dir, alpha_dir)
    for candidate in order:
        paths = sorted(candidate.glob("frame_*.png"))
        if paths:
            frames = []
            for path in paths:
                with Image.open(path) as source:
                    frames.append(source.convert("RGBA"))
            return candidate.name, frames
    raise FileNotFoundError(f"No frame PNGs found under {directory}")


def _load_label_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for candidate in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    fitted = image.copy()
    fitted.thumbnail(size, Image.Resampling.LANCZOS)
    return fitted


def build_gif(
    root: Path,
    output: Path,
    order: list[str] | None = None,
    fps: float = 10.0,
    prefer: str = "alpha",
    background: str = "white",
    label: bool = True,
    hold_last: int = 2,
    max_width: int = 480,
    loop: int = 0,
) -> dict[str, Any]:
    """Write one GIF that plays every animation in order."""
    if fps <= 0:
        raise ValueError("fps must be greater than 0.")
    if hold_last < 1:
        raise ValueError("hold_last must be at least 1.")
    if max_width < 1:
        raise ValueError("max_width must be at least 1.")

    animations = discover_animations(root, list(order) if order else list(DEFAULT_ORDER))
    if not animations:
        raise FileNotFoundError(f"No animation frames found under {root}")

    sequences: list[tuple[str, str, list[Image.Image]]] = []
    for name, directory in animations:
        source_kind, frames = load_frames(directory, prefer)
        sequences.append((name, source_kind, frames))

    widest = max(frame.width for _, _, frames in sequences for frame in frames)
    tallest = max(frame.height for _, _, frames in sequences for frame in frames)
    scale = min(1.0, max_width / widest)
    canvas_width = max(1, round(widest * scale))
    canvas_height = max(1, round(tallest * scale))

    label_height = 0
    font = None
    if label:
        label_height = max(14, round(canvas_height * 0.05))
        font = _load_label_font(label_height)

    tint = tuple(Image.new("RGB", (1, 1), background).getpixel((0, 0)))
    base_duration = max(20, round(1000 / fps))

    gif_frames: list[Image.Image] = []
    durations: list[int] = []
    timeline: list[dict[str, Any]] = []

    for name, source_kind, frames in sequences:
        for index, frame in enumerate(frames):
            canvas = Image.new("RGB", (canvas_width, canvas_height + label_height), tint)
            fitted = _fit(frame, (canvas_width, canvas_height))
            canvas.paste(
                fitted,
                ((canvas_width - fitted.width) // 2, label_height + (canvas_height - fitted.height) // 2),
                fitted,
            )
            if font is not None:
                ImageDraw.Draw(canvas).text(
                    (6, 1),
                    f"{name} {index + 1}/{len(frames)}",
                    font=font,
                    fill=(40, 40, 40),
                )
            gif_frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE))
            is_last = index == len(frames) - 1
            durations.append(base_duration * hold_last if is_last else base_duration)
            timeline.append({"animation": name, "frame": index, "hold": is_last})

    output.parent.mkdir(parents=True, exist_ok=True)
    gif_frames[0].save(
        output,
        save_all=True,
        append_images=gif_frames[1:],
        duration=durations,
        loop=loop,
        disposal=2,
        optimize=False,
    )

    summary = {
        "output": str(output.resolve()),
        "canvas": {"width": canvas_width, "height": canvas_height + label_height},
        "frame_count": len(gif_frames),
        "fps": fps,
        "hold_last": hold_last,
        "prefer": prefer,
        "label": label,
        "animations": [
            {
                "name": name,
                "source": source_kind,
                "frame_count": len(frames),
                "directory": str(root / name),
            }
            for name, source_kind, frames in sequences
        ],
        "timeline": timeline,
    }
    output.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Combine every animation's frames into one ordered GIF."
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--order",
        default=",".join(DEFAULT_ORDER),
        help="Comma-separated animation names played first, in this order.",
    )
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--prefer", choices=("alpha", "frames"), default="alpha")
    parser.add_argument(
        "--background",
        default="white",
        help="Canvas color behind transparent frames (name or #rrggbb).",
    )
    parser.add_argument("--no-label", action="store_true", help="Hide the per-frame label.")
    parser.add_argument(
        "--hold-last",
        type=int,
        default=2,
        help="Duration multiplier for each animation's final frame.",
    )
    parser.add_argument("--max-width", type=int, default=480)
    parser.add_argument("--loop", type=int, default=0, help="0 loops forever.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    order = [part.strip() for part in args.order.split(",") if part.strip()]
    try:
        summary = build_gif(
            args.root,
            args.output,
            order=order,
            fps=args.fps,
            prefer=args.prefer,
            background=args.background,
            label=not args.no_label,
            hold_last=args.hold_last,
            max_width=args.max_width,
            loop=args.loop,
        )
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {summary['output']}")
    print(
        f"{summary['frame_count']} frames, "
        f"{summary['canvas']['width']}x{summary['canvas']['height']}, {args.fps:g} fps"
    )
    print("Order: " + " -> ".join(entry["name"] for entry in summary["animations"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

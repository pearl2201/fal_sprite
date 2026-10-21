"""Rerun a single animation for a character, then refresh the set's review artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # allow `python scripts\rerun_animation.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.animation_set_report import build_overview, write_index
from scripts.build_animation_gif import DEFAULT_ORDER, build_gif
from scripts.generate_spritesheet import (
    apply_background_removal,
    generate_video,
    process_video,
)
from scripts.run_batch import (
    DEFAULT_PADDING_HEIGHT,
    DEFAULT_PADDING_WIDTH,
    default_keep_endpoints,
    default_selection,
    slugify,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SET_PARENT = ROOT / "output" / "option2_animation_set"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path}: {error}") from error


def _fraction(pixels: Any, size: Any) -> float | None:
    try:
        return round(float(pixels) / float(size), 4)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def load_set_defaults(set_root: Path) -> dict[str, Any]:
    """Recover reference, padding, background mode, and order from an existing set."""
    defaults: dict[str, Any] = {
        "reference": None,
        "padding_width": None,
        "padding_height": None,
        "background_mode": None,
        "order": [],
    }
    if not set_root.is_dir():
        return defaults

    for directory in sorted(path for path in set_root.iterdir() if path.is_dir()):
        generation_path = directory / "generation.json"
        if defaults["reference"] is None and generation_path.is_file():
            generation = _read_json(generation_path)
            original = generation.get("original_reference")
            if original:
                defaults["reference"] = Path(original)
            padding = generation.get("padding") or {}
            original_size = padding.get("original_size") or {}
            pixels = padding.get("padding_per_side_pixels") or {}
            if defaults["padding_width"] is None:
                defaults["padding_width"] = _fraction(
                    pixels.get("horizontal"), original_size.get("width")
                )
            if defaults["padding_height"] is None:
                defaults["padding_height"] = _fraction(
                    pixels.get("vertical"), original_size.get("height")
                )

        metadata_path = directory / "metadata.json"
        if defaults["background_mode"] is None and metadata_path.is_file():
            metadata = _read_json(metadata_path)
            mode = (metadata.get("background_removal") or {}).get("mode")
            if mode:
                defaults["background_mode"] = mode

    index_path = set_root / "animation_set_index.json"
    if index_path.is_file():
        defaults["order"] = list(_read_json(index_path).get("animation_order") or [])

    return defaults


def resolve_order(existing_order: list[str], animation: str) -> list[str]:
    """Keep the set's order, insert the new action, and never drop existing actions."""
    order = [name for name in existing_order if name] or list(DEFAULT_ORDER)
    if animation not in order:
        order.append(animation)
    return order


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Rerun one animation for a character and refresh the set's overview, index, and GIF. "
            "An existing clip is re-sampled without any API call unless --force is passed."
        )
    )
    parser.add_argument(
        "--character",
        required=True,
        help="Character slug or set folder name (for example: skull_warrior).",
    )
    parser.add_argument(
        "--animation",
        required=True,
        help="Animation name to rerun (any name, for example: skill_attack or emote_wave).",
    )
    parser.add_argument(
        "--set-root",
        type=Path,
        help="Animation set folder. Defaults to output/option2_animation_set/<character>.",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        help="Reference image. Defaults to the reference recorded in the set's generation.json.",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        help="Prompt file. Required only when a new clip must be generated.",
    )
    parser.add_argument("--padding-width", type=float)
    parser.add_argument("--padding-height", type=float)
    parser.add_argument("--selection", choices=("diverse", "uniform"))
    parser.add_argument("--frame-count", type=int, default=8)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument(
        "--keep-endpoints",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Keep reference-matching clip endpoints (default: on for idle).",
    )
    parser.add_argument(
        "--background-mode",
        choices=("sheet", "frames", "none"),
        help="Background removal mode. Defaults to the mode used elsewhere in the set.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate the clip even when source_video.mp4 already exists.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip rebuilding the overview, index, and GIF.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm the potentially paid FAL calls.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    character = slugify(args.character)
    animation = slugify(args.animation)
    set_root = args.set_root or DEFAULT_SET_PARENT / character
    output_dir = set_root / animation

    try:
        defaults = load_set_defaults(set_root)

        reference = args.reference or defaults["reference"]
        if reference is None:
            if not args.reference:
                raise ValueError(
                    "No reference image found. Pass --reference, or point --set-root at a set "
                    "that already has generation.json."
                )
        if not reference.is_file():
            raise FileNotFoundError(f"Reference image not found: {reference}")

        padding_width = args.padding_width or defaults["padding_width"] or DEFAULT_PADDING_WIDTH
        padding_height = args.padding_height or defaults["padding_height"] or DEFAULT_PADDING_HEIGHT
        if padding_width <= 0 or padding_height <= 0:
            raise ValueError("Padding must be greater than 0; the reference must be padded.")

        background_mode = args.background_mode or defaults["background_mode"] or "sheet"
        selection = args.selection or default_selection(animation)
        keep_endpoints = (
            default_keep_endpoints(animation)
            if args.keep_endpoints is None
            else args.keep_endpoints
        )
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    video_path = output_dir / "source_video.mp4"
    cached = video_path.is_file() and not args.force
    needs_generation = not cached

    print(f"Character : {character}")
    print(f"Animation : {animation}")
    print(f"Set root  : {set_root}")
    print(f"Reference : {reference}")
    print(
        f"Padding   : {padding_width:g} / {padding_height:g} | "
        f"selection={selection} | keep_endpoints={keep_endpoints}"
    )
    print(f"Background: {background_mode}")
    print(
        "Plan      : "
        + (
            "reuse existing clip, then re-sample"
            if cached
            else "generate 1 clip, then sample"
        )
        + ("" if args.no_report else " and rebuild overview/index/GIF")
        + ("" if cached else " (1 paid video generation)")
    )

    if needs_generation:
        if not args.prompt:
            print(
                "Error: --prompt is required when the clip must be generated.",
                file=sys.stderr,
            )
            return 1
        if not args.prompt.is_file():
            print(f"Error: prompt not found: {args.prompt}", file=sys.stderr)
            return 1
        if not args.yes:
            print(
                "Refusing to generate without --yes. Re-run with --yes after reviewing the plan "
                "and current FAL prices.",
                file=sys.stderr,
            )
            return 2

    try:
        if needs_generation:
            print(f"Generating clip for {character}/{animation}...", flush=True)
            video_path = generate_video(
                reference,
                args.prompt,
                output_dir,
                padding_width,
                padding_height,
            )
        else:
            print(f"Reusing {video_path}")

        records = process_video(
            video_path,
            output_dir,
            args.frame_count,
            args.columns,
            selection,
            reference_image=reference,
            keep_reference_endpoints=keep_endpoints,
        )

        if background_mode != "none":
            print(f"Background removal ({background_mode})...", flush=True)
            apply_background_removal(output_dir, background_mode)

        if not args.no_report:
            order = resolve_order(defaults["order"], animation)
            overview = build_overview(set_root, order, title=f"{character} - {len(order)} actions")
            index = write_index(set_root, order, character=character)
            gif = build_gif(set_root, set_root / "animation_set.gif", order=order)
            print(f"Overview: {overview}")
            print(f"Index: {index}")
            print(f"GIF: {gif['output']} ({gif['frame_count']} frames)")
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Done: {len(records)} frames in {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

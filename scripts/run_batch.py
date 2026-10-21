"""Run the full Option 2 pipeline for one or more characters from a JSON manifest."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # allow `python scripts\run_batch.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.animation_set_report import build_overview, write_index
from scripts.build_animation_gif import build_gif
from scripts.generate_spritesheet import (
    apply_background_removal,
    generate_video,
    process_video,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PADDING_WIDTH = 0.25
DEFAULT_PADDING_HEIGHT = 0.10
DEFAULT_FRAME_COUNT = 8
DEFAULT_COLUMNS = 4
UNIFORM_ANIMATIONS = {"idle", "walk", "run", "hurt"}
LOOPING_ANIMATIONS = {"idle"}


@dataclass(frozen=True)
class AnimationSpec:
    name: str
    prompt: Path
    selection: str
    keep_endpoints: bool
    frame_count: int
    columns: int


@dataclass(frozen=True)
class CharacterJob:
    name: str
    reference: Path
    output_root: Path
    padding_width: float
    padding_height: float
    background_mode: str
    animations: tuple[AnimationSpec, ...]
    build_overview: bool
    build_gif: bool


def slugify(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "_" for character in value)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "character"


def default_selection(name: str) -> str:
    """Cyclic or low-motion actions sample uniformly; one-shot actions sample diversely."""
    return "uniform" if name in UNIFORM_ANIMATIONS else "diverse"


def default_keep_endpoints(name: str) -> bool:
    """Only looping actions need their matching first and last frames."""
    return name in LOOPING_ANIMATIONS


def _resolve_path(value: str, field: str, entry_index: int) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Entry {entry_index}: '{field}' must be a non-empty string path.")
    path = Path(value)
    return path if path.is_absolute() else (ROOT / path)


def _as_fraction(value: Any, field: str, entry_index: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Entry {entry_index}: '{field}' must be a number.") from error
    if not 0 < number <= 1:
        raise ValueError(
            f"Entry {entry_index}: '{field}' must be greater than 0 and at most 1 "
            "(the reference must be padded before generation)."
        )
    return number


def _padding_from(entry: dict[str, Any], entry_index: int) -> tuple[float, float]:
    nested = entry.get("padding") or {}
    width = (
        entry.get("padding_width")
        if entry.get("padding_width") is not None
        else entry.get("padding_horizontal", nested.get("width", nested.get("horizontal")))
    )
    height = (
        entry.get("padding_height")
        if entry.get("padding_height") is not None
        else entry.get("padding_vertical", nested.get("height", nested.get("vertical")))
    )
    return (
        _as_fraction(DEFAULT_PADDING_WIDTH if width is None else width, "padding_width", entry_index),
        _as_fraction(DEFAULT_PADDING_HEIGHT if height is None else height, "padding_height", entry_index),
    )


def _background_mode_from(entry: dict[str, Any], entry_index: int) -> str:
    raw = entry.get("background_remove_option", "spritesheet")
    if not isinstance(raw, str):
        raise ValueError(
            f"Entry {entry_index}: 'background_remove_option' must be one of "
            "'spritesheet', 'frames', or 'none'."
        )
    normalized = raw.strip().lower()
    if normalized in {"spritesheet", "sheet", "atlas"}:
        return "sheet"
    if normalized in {"frames", "frame", "per-frame", "per_frame"}:
        return "frames"
    if normalized in {"none", "off", "skip"}:
        return "none"
    raise ValueError(
        f"Entry {entry_index}: unsupported background_remove_option '{raw}'. "
        "Use 'spritesheet', 'frames', or 'none'."
    )


def _parse_animation_items(value: Any, entry_index: int) -> list[tuple[str, Any]]:
    """Accept {name: spec} or [{name: spec}, ...] and flatten to ordered pairs."""
    if isinstance(value, dict):
        pairs = list(value.items())
    elif isinstance(value, list):
        pairs = []
        for item in value:
            if not isinstance(item, dict) or len(item) != 1:
                raise ValueError(
                    f"Entry {entry_index}: 'animations_prompt' list items must be single-key "
                    "objects such as {\"idle\": \"prompt/idle.txt\"}."
                )
            pairs.extend(item.items())
    else:
        raise ValueError(
            f"Entry {entry_index}: 'animations_prompt' must be an object or a list of objects."
        )
    if not pairs:
        raise ValueError(f"Entry {entry_index}: 'animations_prompt' is empty.")
    return pairs


def _parse_animations(
    entry: dict[str, Any],
    entry_index: int,
    default_frame_count: int,
    default_columns: int,
) -> tuple[AnimationSpec, ...]:
    if "animations_prompt" not in entry:
        raise ValueError(f"Entry {entry_index}: 'animations_prompt' is required.")

    specs: list[AnimationSpec] = []
    seen: set[str] = set()
    for raw_name, raw_spec in _parse_animation_items(entry["animations_prompt"], entry_index):
        name = slugify(str(raw_name))
        if name in seen:
            raise ValueError(f"Entry {entry_index}: duplicate animation '{name}'.")
        seen.add(name)

        if isinstance(raw_spec, str):
            prompt_value, overrides = raw_spec, {}
        elif isinstance(raw_spec, dict):
            prompt_value = raw_spec.get("prompt") or raw_spec.get("path")
            overrides = raw_spec
        else:
            raise ValueError(
                f"Entry {entry_index}: animation '{name}' must map to a prompt path "
                "or an object with a 'prompt' key."
            )
        if not prompt_value:
            raise ValueError(f"Entry {entry_index}: animation '{name}' has no prompt path.")

        selection = str(overrides.get("selection", default_selection(name))).lower()
        if selection not in {"diverse", "uniform"}:
            raise ValueError(
                f"Entry {entry_index}: animation '{name}' selection must be "
                "'diverse' or 'uniform'."
            )

        keep_endpoints = overrides.get("keep_endpoints", default_keep_endpoints(name))
        if not isinstance(keep_endpoints, bool):
            raise ValueError(
                f"Entry {entry_index}: animation '{name}' keep_endpoints must be true or false."
            )

        frame_count = int(overrides.get("frame_count", default_frame_count))
        columns = int(overrides.get("columns", default_columns))
        if frame_count < 1 or columns < 1:
            raise ValueError(
                f"Entry {entry_index}: animation '{name}' frame_count and columns must be at least 1."
            )

        specs.append(
            AnimationSpec(
                name=name,
                prompt=_resolve_path(prompt_value, f"animations_prompt.{name}", entry_index),
                selection=selection,
                keep_endpoints=keep_endpoints,
                frame_count=frame_count,
                columns=columns,
            )
        )
    return tuple(specs)


def _parse_entry(entry: Any, entry_index: int) -> CharacterJob:
    if not isinstance(entry, dict):
        raise ValueError(f"Entry {entry_index}: must be an object.")

    reference_value = entry.get("image_references", entry.get("image_reference"))
    if isinstance(reference_value, list):
        if len(reference_value) != 1:
            raise ValueError(
                f"Entry {entry_index}: 'image_references' supports exactly one image per entry; "
                f"got {len(reference_value)}. Add a separate entry per character."
            )
        reference_value = reference_value[0]
    if reference_value is None:
        raise ValueError(f"Entry {entry_index}: 'image_references' is required.")

    reference = _resolve_path(reference_value, "image_references", entry_index)
    name = slugify(entry.get("name") or reference.stem)
    padding_width, padding_height = _padding_from(entry, entry_index)

    frame_count = int(entry.get("frame_count", DEFAULT_FRAME_COUNT))
    columns = int(entry.get("columns", DEFAULT_COLUMNS))
    if frame_count < 1 or columns < 1:
        raise ValueError(
            f"Entry {entry_index}: frame_count and columns must be at least 1."
        )

    output_root = entry.get("output_root")
    output_path = (
        _resolve_path(output_root, "output_root", entry_index)
        if output_root
        else ROOT / "output" / "option2_animation_set" / name
    )

    return CharacterJob(
        name=name,
        reference=reference,
        output_root=output_path,
        padding_width=padding_width,
        padding_height=padding_height,
        background_mode=_background_mode_from(entry, entry_index),
        animations=_parse_animations(entry, entry_index, frame_count, columns),
        build_overview=bool(entry.get("overview", True)),
        build_gif=bool(entry.get("gif", True)),
    )


def load_manifest(path: Path) -> list[CharacterJob]:
    """Parse and validate a manifest without touching prompts, images, or the network."""
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path}: {error}") from error

    entries = raw.get("characters") if isinstance(raw, dict) else raw
    if not isinstance(entries, list) or not entries:
        raise ValueError(
            "Manifest must be a non-empty list of character entries "
            "or an object with a non-empty 'characters' list."
        )

    jobs = [_parse_entry(entry, index) for index, entry in enumerate(entries, start=1)]
    names = [job.name for job in jobs]
    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        raise ValueError(
            "Duplicate character name(s) in manifest: " + ", ".join(sorted(duplicates))
        )
    return jobs


def validate_jobs(jobs: list[CharacterJob]) -> list[str]:
    """Return human-readable problems for missing references or prompts."""
    problems: list[str] = []
    for job in jobs:
        if not job.reference.is_file():
            problems.append(f"{job.name}: reference image not found: {job.reference}")
        for animation in job.animations:
            if not animation.prompt.is_file():
                problems.append(
                    f"{job.name}/{animation.name}: prompt not found: {animation.prompt}"
                )
    return problems


def job_plan(job: CharacterJob) -> dict[str, Any]:
    animations = []
    for animation in job.animations:
        output = job.output_root / animation.name
        animations.append(
            {
                "name": animation.name,
                "output": str(output),
                "video_cached": (output / "source_video.mp4").is_file(),
                "selection": animation.selection,
                "keep_endpoints": animation.keep_endpoints,
                "frame_count": animation.frame_count,
            }
        )
    return {
        "name": job.name,
        "reference": str(job.reference),
        "output_root": str(job.output_root),
        "padding": {"width": job.padding_width, "height": job.padding_height},
        "background_mode": job.background_mode,
        "animations": animations,
    }


def estimate_calls(
    plans: list[dict[str, Any]],
    *,
    skip_background: bool = False,
    force: bool = False,
) -> dict[str, int]:
    videos = sum(
        1
        for plan in plans
        for animation in plan["animations"]
        if force or not animation["video_cached"]
    )
    images = 0
    if not skip_background:
        for plan in plans:
            if plan["background_mode"] == "sheet":
                images += len(plan["animations"])
            elif plan["background_mode"] == "frames":
                images += sum(
                    animation["frame_count"] for animation in plan["animations"]
                )
    return {"video_generations": videos, "background_requests": images}


def run_job(
    job: CharacterJob,
    *,
    force: bool = False,
    skip_background: bool = False,
    skip_report: bool = False,
) -> dict[str, Any]:
    """Generate, sample, background-remove, and report one character."""
    results: list[dict[str, Any]] = []
    for animation in job.animations:
        output = job.output_root / animation.name
        video = output / "source_video.mp4"
        generated = False
        if force or not video.is_file():
            print(f"[{job.name}/{animation.name}] generating clip...", flush=True)
            video = generate_video(
                job.reference,
                animation.prompt,
                output,
                job.padding_width,
                job.padding_height,
            )
            generated = True
        else:
            print(f"[{job.name}/{animation.name}] reusing {video.name}", flush=True)

        records = process_video(
            video,
            output,
            animation.frame_count,
            animation.columns,
            animation.selection,
            reference_image=job.reference,
            keep_reference_endpoints=animation.keep_endpoints,
        )

        alpha_records = 0
        if not skip_background and job.background_mode != "none":
            print(
                f"[{job.name}/{animation.name}] background removal ({job.background_mode})...",
                flush=True,
            )
            alpha_records = len(apply_background_removal(output, job.background_mode))
        elif job.background_mode == "none":
            print(f"[{job.name}/{animation.name}] background removal skipped by manifest", flush=True)

        results.append(
            {
                "name": animation.name,
                "generated": generated,
                "frames": len(records),
                "alpha_frames": alpha_records,
                "output": str(output),
            }
        )

    report: dict[str, Any] = {}
    if not skip_report:
        order = [animation.name for animation in job.animations]
        if job.build_overview:
            report["overview"] = str(
                build_overview(
                    job.output_root,
                    order,
                    title=f"{job.name} - {len(order)} actions",
                )
            )
        report["index"] = str(write_index(job.output_root, order, character=job.name))
        if job.build_gif:
            summary = build_gif(job.output_root, job.output_root / "animation_set.gif", order=order)
            report["gif"] = summary["output"]

    return {"name": job.name, "animations": results, "report": report}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full Option 2 pipeline (H3 clip -> frames -> BiRefNet -> overview/GIF) "
            "for every character in a JSON manifest."
        )
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="NAME",
        help="Run only the named character(s); repeatable.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan and estimated paid calls without generating.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate clips even when source_video.mp4 already exists.",
    )
    parser.add_argument(
        "--skip-background",
        action="store_true",
        help="Sample frames and build reports but skip paid background removal.",
    )
    parser.add_argument(
        "--skip-report",
        action="store_true",
        help="Skip the overview image, index, and GIF.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm the potentially paid FAL requests described in the plan.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        jobs = load_manifest(args.manifest)
        if args.only:
            wanted = {slugify(name) for name in args.only}
            jobs = [job for job in jobs if job.name in wanted]
            if not jobs:
                raise ValueError(
                    "No manifest entry matched --only " + ", ".join(sorted(wanted))
                )
        problems = validate_jobs(jobs)
        if problems:
            for problem in problems:
                print(f"Error: {problem}", file=sys.stderr)
            return 1
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    plans = [job_plan(job) for job in jobs]
    calls = estimate_calls(plans, skip_background=args.skip_background, force=args.force)

    print("=== Plan ===")
    for plan in plans:
        cached = sum(1 for animation in plan["animations"] if animation["video_cached"])
        print(
            f"{plan['name']}: {len(plan['animations'])} actions, "
            f"padding {plan['padding']['width']:g}/{plan['padding']['height']:g}, "
            f"background={plan['background_mode']}, "
            f"clips cached={cached}/{len(plan['animations'])}"
        )
    print(
        f"Estimated paid calls: {calls['video_generations']} video generation(s), "
        f"{calls['background_requests']} background-removal request(s)"
    )

    if args.dry_run:
        print("Dry run only; nothing was generated.")
        return 0

    if not args.yes:
        print(
            "Refusing to run without --yes. Re-run with --yes after reviewing the plan "
            "and current FAL prices.",
            file=sys.stderr,
        )
        return 2

    report: dict[str, Any] = {"manifest": str(args.manifest.resolve()), "characters": []}
    exit_code = 0
    for job in jobs:
        try:
            report["characters"].append(
                run_job(
                    job,
                    force=args.force,
                    skip_background=args.skip_background,
                    skip_report=args.skip_report,
                )
            )
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as error:
            print(f"Error: {job.name}: {error}", file=sys.stderr)
            report["characters"].append({"name": job.name, "error": str(error)})
            exit_code = 1
            break

    report_path = args.manifest.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report: {report_path.resolve()}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

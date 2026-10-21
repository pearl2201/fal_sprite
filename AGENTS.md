# AGENTS.md

Guidance for AI coding agents working in this repository. Read this before changing code.

## What this project is

A research and prototyping tool that turns one character reference illustration into a game animation set using FAL image-to-video, local frame extraction, and AI background removal.

```
reference image -> padded canvas -> H3 image-to-video (one clip per action)
  -> frame sampling + endpoint trim -> BiRefNet on the packed atlas
  -> per-action atlas/contact sheet/metadata -> overview + index + GIF
```

Output is a motion reference, not finished game art.

## Setup and commands

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py"
```

| Task | Command |
|---|---|
| Preview padded input (free) | `python scripts\generate_spritesheet.py prepare` |
| One action, full flow | `python scripts\generate_spritesheet.py generate --yes` |
| Re-sample an existing clip (free) | `python scripts\generate_spritesheet.py process <video> --output-dir <dir>` |
| Whole set from manifest | `python scripts\run_batch.py <manifest>.json --dry-run` then `--yes` |
| Rerun one action | `python scripts\rerun_animation.py --character <name> --animation <name> --yes` |
| Review GIF (free) | `python scripts\build_animation_gif.py --root <set>` |
| Overview + index (free) | `python scripts\animation_set_report.py --root <set>` |

Windows is the primary platform. Use PowerShell syntax with backslash paths.

## Repository map

| Path | Ownership |
|---|---|
| `scripts/generate_spritesheet.py` | Padding, generation, sampling, endpoint trimming, background removal |
| `scripts/run_batch.py` | Manifest parsing, planning, cost estimates, multi-character runs |
| `scripts/rerun_animation.py` | Surgical single-action rerun inside an existing set |
| `scripts/build_animation_gif.py` | Ordered review GIF |
| `scripts/animation_set_report.py` | Overview image and JSON index |
| `prompt/<set>/` | One prompt per action, per character |
| `art_references/` | Approved character references (do not modify) |
| `manifests/` | Batch manifests |
| `document/` | Research, workflow, and cost documentation |
| `tests/` | Unit tests; never touch the network |
| `.github/skills/fal-spritesheet-pipeline/` | Agent operating procedure for this pipeline |

## Non-negotiable rules

1. **Never make a paid FAL call without explicit user authorization.** Every paid path requires `--yes`. Show a plan or `--dry-run` first and state the exact call counts (video generations and background requests separately).
2. **Never commit `.env` or `output/`.** They are gitignored; keep them untracked. Never print, echo, or log the FAL key.
3. **Always pad the reference before generation.** `generate` rejects zero padding. Defaults are `0.25` width and `0.10` height per edge. Unpadded uploads clip weapons and limbs.
4. **Background removal defaults to the packed spritesheet** (`--background-mode sheet`), one BiRefNet request per action. Use `frames` only when the user asks for maximum edge fidelity and accepts the cost.
5. **Do not overwrite reviewed output.** Write to a new folder unless the user explicitly asks to rebuild in place.
6. **Preserve raw artifacts.** Never delete `source_video.mp4`, `frames/`, or `spritesheet.png` when adding derived outputs.

## Code conventions

- Python 3.11+, `from __future__ import annotations`, type hints on public functions.
- Use `dataclass(frozen=True)` for parsed configuration and keep parsing pure: `load_manifest` must not touch the filesystem beyond reading the manifest.
- Raise `ValueError`, `FileNotFoundError`, or `RuntimeError` with actionable messages. CLIs catch these, print `Error: ...` to stderr, and return `1` (or `2` when confirmation is required).
- Keep validation errors scoped, e.g. `Entry 3: 'padding_width' must be a number.`
- Scripts that import sibling modules need the `if __package__ in (None, ""):` sys.path bootstrap so `python scripts\x.py` works.
- Prefer extending an existing module over adding a new one.

## Definition of done

1. `python -m unittest discover -s tests -p "test_*.py"` passes.
2. New behavior has tests; tests use temporary directories and mock `fal_client`, `_download_asset`, or `generate_video` so no test can spend money.
3. Documentation updated: `README.md` for user-facing behavior, `document/option-2-video-frames.md` for workflow findings, `document/cost-estimate.md` when the number of paid calls changes.
4. For output changes, verify by opening the produced contact sheet, atlas, and GIF — not just by checking exit codes.

## Gotchas

- Frame counts differ by sampling mode: `diverse` can return fewer frames than requested on low-motion clips; `uniform` always fills the count. Report this instead of silently padding.
- `metadata.json` is the source of truth for layout, timings, endpoint decisions, and background provenance. Keep it in sync when adding outputs.
- H3 may add smear arcs and deform rigid props despite explicit prompt constraints. Treat this as a model limitation; never mask it with image processing.
- BiRefNet sheet mode downscales the whole atlas, so edges are softer than per-frame mode (measured ~0.94 mean IoU on one clip).
- Git history was rewritten once to drop `output/` and `.env`; if a clone still contains them, it needs the same cleanup.

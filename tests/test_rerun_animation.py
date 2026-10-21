import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.build_animation_gif import DEFAULT_ORDER
from scripts.rerun_animation import load_set_defaults, main, resolve_order


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_set(root: Path) -> Path:
    set_root = root / "warrior"
    _write_json(
        set_root / "idle" / "generation.json",
        {
            "endpoint": "minimax/h3-max-turbo/image-to-video",
            "original_reference": str(root / "reference.png"),
            "padding": {
                "original_size": {"width": 1000, "height": 800},
                "padding_per_side_pixels": {"horizontal": 300, "vertical": 160},
            },
        },
    )
    _write_json(
        set_root / "idle" / "metadata.json",
        {"background_removal": {"mode": "sheet", "api_calls": 1}},
    )
    _write_json(
        set_root / "animation_set_index.json",
        {"animation_order": ["idle", "walk"]},
    )
    return set_root


class RerunAnimationTests(unittest.TestCase):
    def test_set_defaults_come_from_existing_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            set_root = _make_set(root)

            defaults = load_set_defaults(set_root)

        self.assertEqual(defaults["reference"], root / "reference.png")
        self.assertAlmostEqual(defaults["padding_width"], 0.3)
        self.assertAlmostEqual(defaults["padding_height"], 0.2)
        self.assertEqual(defaults["background_mode"], "sheet")
        self.assertEqual(defaults["order"], ["idle", "walk"])

    def test_missing_set_returns_empty_defaults(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            defaults = load_set_defaults(Path(temporary_directory) / "nope")

        self.assertIsNone(defaults["reference"])
        self.assertIsNone(defaults["padding_width"])
        self.assertIsNone(defaults["background_mode"])
        self.assertEqual(defaults["order"], [])

    def test_resolve_order_appends_new_animation(self):
        self.assertEqual(
            resolve_order(["idle", "walk"], "emote_wave"),
            ["idle", "walk", "emote_wave"],
        )
        self.assertEqual(resolve_order(["idle"], "idle"), ["idle"])

    def test_resolve_order_falls_back_to_default_order(self):
        resolved = resolve_order([], "run")
        self.assertEqual(resolved, list(DEFAULT_ORDER))
        self.assertEqual(resolve_order([], "emote_bow")[-1], "emote_bow")

    def test_generation_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reference = root / "reference.png"
            Image.new("RGB", (40, 40), "white").save(reference)
            prompt = root / "idle.txt"
            prompt.write_text("idle prompt", encoding="utf-8")

            argv = [
                "rerun_animation.py",
                "--character",
                "warrior",
                "--animation",
                "idle",
                "--set-root",
                str(root / "set"),
                "--reference",
                str(reference),
                "--prompt",
                str(prompt),
            ]
            output, errors = io.StringIO(), io.StringIO()
            with patch("sys.argv", argv):
                with redirect_stdout(output), redirect_stderr(errors):
                    code = main()

            self.assertEqual(code, 2)
            self.assertIn("Refusing to generate without --yes", errors.getvalue())
            self.assertIn("generate 1 clip", output.getvalue())

    def test_generation_requires_prompt(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reference = root / "reference.png"
            Image.new("RGB", (40, 40), "white").save(reference)

            argv = [
                "rerun_animation.py",
                "--character",
                "warrior",
                "--animation",
                "idle",
                "--set-root",
                str(root / "set"),
                "--reference",
                str(reference),
                "--yes",
            ]
            output, errors = io.StringIO(), io.StringIO()
            with patch("sys.argv", argv):
                with redirect_stdout(output), redirect_stderr(errors):
                    code = main()

            self.assertEqual(code, 1)
            self.assertIn("--prompt is required", errors.getvalue())

    def test_missing_reference_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            argv = [
                "rerun_animation.py",
                "--character",
                "unknown",
                "--animation",
                "idle",
                "--set-root",
                str(Path(temporary_directory) / "empty"),
            ]
            output, errors = io.StringIO(), io.StringIO()
            with patch("sys.argv", argv):
                with redirect_stdout(output), redirect_stderr(errors):
                    code = main()

            self.assertEqual(code, 1)
            self.assertIn("No reference image found", errors.getvalue())


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.build_animation_gif import DEFAULT_ORDER, build_gif, discover_animations


def _write_frames(root: Path, name: str, colors, folder: str = "frames_alpha") -> None:
    directory = root / name / folder
    directory.mkdir(parents=True)
    for index, color in enumerate(colors):
        Image.new("RGBA", (20, 20), color).save(directory / f"frame_{index:03d}.png")


class AnimationGifTests(unittest.TestCase):
    def test_animations_follow_requested_order_then_extras(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for name in ("death", "idle", "run", "extra_dash", "walk"):
                _write_frames(root, name, [(255, 0, 0, 255)])

            discovered = discover_animations(root, list(DEFAULT_ORDER))
            self.assertEqual(
                [name for name, _ in discovered],
                ["idle", "walk", "run", "death", "extra_dash"],
            )

    def test_gif_plays_each_animation_in_order(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _write_frames(root, "idle", [(255, 0, 0, 255), (0, 255, 0, 255)])
            _write_frames(root, "walk", [(0, 0, 255, 255), (255, 255, 0, 255)])
            _write_frames(root, "custom", [(255, 0, 255, 255)])

            output = root / "set.gif"
            summary = build_gif(
                root,
                output,
                order=["idle", "walk"],
                fps=10,
                label=False,
                hold_last=1,
                max_width=20,
            )

            self.assertTrue(output.is_file())
            self.assertEqual(summary["frame_count"], 5)
            self.assertEqual(
                [entry["name"] for entry in summary["animations"]],
                ["idle", "walk", "custom"],
            )

            with Image.open(output) as gif:
                self.assertEqual(gif.n_frames, 5)
                colors = []
                for index in range(gif.n_frames):
                    gif.seek(index)
                    colors.append(gif.convert("RGB").getpixel((10, 10)))
            self.assertEqual(
                colors,
                [
                    (255, 0, 0),
                    (0, 255, 0),
                    (0, 0, 255),
                    (255, 255, 0),
                    (255, 0, 255),
                ],
            )

            sidecar = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(sidecar["frame_count"], 5)

    def test_prefers_raw_frames_when_requested(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _write_frames(root, "idle", [(10, 10, 10, 255)], folder="frames")

            summary = build_gif(root, root / "out.gif", prefer="frames", label=False, max_width=20)
            self.assertEqual(summary["animations"][0]["source"], "frames")

    def test_invalid_fps_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _write_frames(root, "idle", [(255, 255, 255, 255)])
            with self.assertRaises(ValueError):
                build_gif(root, root / "out.gif", fps=0)


if __name__ == "__main__":
    unittest.main()

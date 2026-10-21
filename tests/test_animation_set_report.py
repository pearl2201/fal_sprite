import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.animation_set_report import (
    build_overview,
    resolve_order,
    subtitle_from_frames,
    write_index,
)


def _make_set(root: Path, names, frames: int = 2, with_alpha: bool = True) -> None:
    for name in names:
        directory = root / name
        if with_alpha:
            alpha = directory / "frames_alpha"
            alpha.mkdir(parents=True)
            for index in range(frames):
                Image.new("RGBA", (20, 20), (200, 40, 40, 255)).save(
                    alpha / f"frame_{index:03d}.png"
                )
        raw = directory / "frames"
        raw.mkdir(parents=True, exist_ok=True)
        for index in range(frames):
            Image.new("RGB", (20, 20), "white").save(raw / f"frame_{index:03d}.png")
        metadata = {
            "source_video": str(directory / "source_video.mp4"),
            "frames": [{"index": i, "timestamp_seconds": round(i * 0.25, 4)} for i in range(frames)],
            "layout": {"columns": 2, "rows": 1},
            "reference_endpoint_comparison": {"first_removed": True},
            "background_removal": {"endpoint": "fal-ai/birefnet/v2", "mode": "sheet", "api_calls": 1},
            "generation": {"endpoint": "minimax/h3-max-turbo/image-to-video"},
        }
        (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


class AnimationSetReportTests(unittest.TestCase):
    def test_resolve_order_puts_requested_first_then_extras(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _make_set(root, ["death", "idle", "extra_dash"])
            self.assertEqual(
                resolve_order(root, ["idle", "death"]),
                ["idle", "death", "extra_dash"],
            )

    def test_subtitle_reports_real_frame_count_and_layer(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _make_set(root, ["idle", "death"], frames=4)
            self.assertEqual(
                subtitle_from_frames(root, ["idle", "death"]),
                "4 frames per action; alpha cutouts",
            )

            raw_only = Path(temporary_directory) / "raw"
            _make_set(raw_only, ["idle"], frames=6, with_alpha=False)
            self.assertEqual(
                subtitle_from_frames(raw_only, ["idle"]),
                "6 frames per action; raw RGB frames",
            )

    def test_subtitle_handles_mixed_counts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _make_set(root, ["idle"], frames=2)
            _make_set(root, ["death"], frames=5)
            self.assertEqual(
                subtitle_from_frames(root, ["idle", "death"]),
                "2-5 frames per action; alpha cutouts",
            )

    def test_overview_is_written_with_one_row_per_action(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _make_set(root, ["idle", "death"], frames=2)

            destination = build_overview(
                root, ["idle", "death"], tile_width=60, tile_height=60
            )

            self.assertTrue(destination.is_file())
            with Image.open(destination) as image:
                self.assertEqual(image.size, (150 + 2 * 60, 48 + 2 * (60 + 24)))

    def test_overview_requires_frames(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(FileNotFoundError):
                build_overview(Path(temporary_directory), ["idle"])

    def test_index_records_frames_and_provenance(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _make_set(root, ["idle"], frames=3)

            destination = write_index(root, ["idle"], character="warrior")
            payload = json.loads(destination.read_text(encoding="utf-8"))

            self.assertEqual(payload["character"], "warrior")
            self.assertEqual(payload["animation_order"], ["idle"])
            entry = payload["animations"][0]
            self.assertEqual(entry["frame_count"], 3)
            self.assertEqual(entry["frame_times"], [0.0, 0.25, 0.5])
            self.assertEqual(entry["background_removal"]["mode"], "sheet")
            self.assertTrue(entry["spritesheet"].endswith("spritesheet.png"))


if __name__ == "__main__":
    unittest.main()

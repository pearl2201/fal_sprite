import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from scripts.generate_spritesheet import (
    _confirm_generation,
    _confirm_background_removal,
    _select_diverse_indices,
    _sample_indices,
    load_project_env,
    prepare_padded_reference,
    process_video,
    remove_background_from_frames,
)


class SpritesheetPipelineTests(unittest.TestCase):
    def test_sample_indices_are_even_and_unique(self):
        self.assertEqual(_sample_indices(25, 5), [0, 6, 12, 18, 24])
        self.assertEqual(_sample_indices(3, 8), [0, 1, 2])

    def test_diverse_selection_skips_near_duplicate_frames(self):
        thumbnails = [
            np.full((8, 8), value, dtype=np.uint8)
            for value in (0, 0, 60, 110, 110, 0)
        ]
        selected = _select_diverse_indices(thumbnails, requested=6)
        self.assertEqual(selected, [0, 2, 3])

    def test_prepare_padded_reference_extends_canvas_without_scaling_subject(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.png"
            destination = root / "padded.png"
            Image.new("RGB", (100, 80), (255, 255, 255)).save(source)

            metadata = prepare_padded_reference(
                source,
                destination,
                horizontal_padding=0.25,
                vertical_padding=0.10,
            )

            with Image.open(destination) as padded:
                self.assertEqual(padded.size, (150, 96))
                self.assertEqual(padded.getpixel((25, 8)), (255, 255, 255))
                self.assertEqual(padded.getpixel((75, 48)), (255, 255, 255))
            self.assertEqual(metadata["padding_per_side_pixels"], {"horizontal": 25, "vertical": 8})

    def test_prepare_padded_reference_rejects_invalid_padding(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.png"
            Image.new("RGB", (10, 10), "white").save(source)
            with self.assertRaises(ValueError):
                prepare_padded_reference(source, root / "out.png", horizontal_padding=1.5)

    def test_process_video_writes_frames_sheet_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            video_path = root / "sample.avi"
            writer = cv2.VideoWriter(
                str(video_path),
                cv2.VideoWriter_fourcc(*"MJPG"),
                10.0,
                (64, 48),
            )
            self.assertTrue(writer.isOpened())
            for index in range(10):
                frame = np.full((48, 64, 3), index * 20, dtype=np.uint8)
                writer.write(frame)
            writer.release()

            output = root / "result"
            records = process_video(
                video_path,
                output,
                frame_count=4,
                columns=2,
                selection="uniform",
            )

            self.assertEqual(len(records), 4)
            self.assertEqual(
                [record["source_frame"] for record in records],
                [0, 3, 6, 9],
            )
            self.assertTrue((output / "spritesheet.png").is_file())
            self.assertTrue((output / "contact_sheet.jpg").is_file())
            self.assertEqual(len(list((output / "frames").glob("*.png"))), 4)
            metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["frame_size"], {"width": 64, "height": 48})
            self.assertEqual(metadata["layout"], {"columns": 2, "rows": 2})
            self.assertEqual(metadata["selection"], "uniform")

    def test_process_video_trims_reference_matching_clip_endpoints(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reference_path = root / "reference.png"
            reference = Image.new("RGB", (64, 48), "white")
            for x in range(20, 36):
                for y in range(10, 40):
                    reference.putpixel((x, y), (30, 30, 30))
            reference.save(reference_path)

            video_path = root / "endpoints.avi"
            writer = cv2.VideoWriter(
                str(video_path),
                cv2.VideoWriter_fourcc(*"MJPG"),
                10.0,
                (64, 48),
            )
            self.assertTrue(writer.isOpened())
            for index in range(10):
                image = reference.copy()
                if index not in (0, 9):
                    for x in range(5 + index, 20 + index):
                        for y in range(5, 20):
                            image.putpixel((x, y), (220, 40, 30))
                writer.write(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR))
            writer.release()

            output = root / "trimmed"
            records = process_video(
                video_path,
                output,
                frame_count=4,
                columns=2,
                selection="uniform",
                reference_image=reference_path,
            )

            self.assertEqual([record["source_frame"] for record in records], [1, 3, 6, 8])
            metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            comparison = metadata["reference_endpoint_comparison"]
            self.assertTrue(comparison["first_removed"])
            self.assertTrue(comparison["last_removed"])
            self.assertGreaterEqual(comparison["first_similarity"], 0.95)
            self.assertGreaterEqual(comparison["last_similarity"], 0.95)

    def test_invalid_video_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_video = Path(temporary_directory) / "missing.mp4"
            with self.assertRaises(FileNotFoundError):
                process_video(missing_video, Path(temporary_directory) / "out")

    def test_generation_confirmation_cancels_on_eof(self):
        with patch("scripts.generate_spritesheet.sys.stdin.isatty", return_value=True):
            with patch("builtins.input", side_effect=EOFError):
                self.assertFalse(_confirm_generation())

    def test_background_confirmation_cancels_on_eof(self):
        with patch("scripts.generate_spritesheet.sys.stdin.isatty", return_value=True):
            with patch("builtins.input", side_effect=EOFError):
                self.assertFalse(_confirm_background_removal())

    def test_project_env_maps_fal_api_to_sdk_variable(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / ".env"
            env_path.write_text("FAL_API=example-test-key\n", encoding="utf-8")
            with patch.dict(os.environ, {"FAL_API": "example-test-key"}, clear=True):
                load_project_env(env_path)
                self.assertEqual(os.environ["FAL_KEY"], "example-test-key")

    def test_background_removal_keeps_original_and_writes_alpha_atlas(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            frames_dir = root / "frames"
            frames_dir.mkdir()
            source_frame = frames_dir / "frame_000.png"
            Image.new("RGB", (20, 12), "white").save(source_frame)
            result = {
                "image": {
                    "url": "https://example.test/removed.png",
                    "width": 20,
                    "height": 12,
                }
            }
            fake_client = SimpleNamespace(
                upload_file=lambda path: "https://example.test/input.png",
                subscribe=lambda endpoint, **kwargs: result,
            )

            def write_transparent_png(_url, destination):
                Image.new("RGBA", (20, 12), (20, 30, 40, 128)).save(destination)

            with patch.dict(sys.modules, {"fal_client": fake_client}):
                with patch.dict(os.environ, {"FAL_KEY": "test-key"}):
                    with patch("scripts.generate_spritesheet.load_project_env"):
                        with patch("scripts.generate_spritesheet._download_asset", side_effect=write_transparent_png):
                            records = remove_background_from_frames(frames_dir, root)

            self.assertEqual(len(records), 1)
            self.assertTrue(source_frame.is_file())
            self.assertTrue((root / "frames_alpha" / "frame_000.png").is_file())
            self.assertTrue((root / "spritesheet_alpha.png").is_file())
            metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["background_removal"]["endpoint"], "fal-ai/birefnet/v2")


if __name__ == "__main__":
    unittest.main()

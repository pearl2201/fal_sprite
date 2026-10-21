import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from scripts.generate_spritesheet import (
    _confirm_generation,
    _select_diverse_indices,
    _sample_indices,
    load_project_env,
    process_video,
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

    def test_invalid_video_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_video = Path(temporary_directory) / "missing.mp4"
            with self.assertRaises(FileNotFoundError):
                process_video(missing_video, Path(temporary_directory) / "out")

    def test_generation_confirmation_cancels_on_eof(self):
        with patch("scripts.generate_spritesheet.sys.stdin.isatty", return_value=True):
            with patch("builtins.input", side_effect=EOFError):
                self.assertFalse(_confirm_generation())

    def test_project_env_maps_fal_api_to_sdk_variable(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / ".env"
            env_path.write_text("FAL_API=example-test-key\n", encoding="utf-8")
            with patch.dict(os.environ, {"FAL_API": "example-test-key"}, clear=True):
                load_project_env(env_path)
                self.assertEqual(os.environ["FAL_KEY"], "example-test-key")


if __name__ == "__main__":
    unittest.main()

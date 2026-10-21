import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_batch import (
    AnimationSpec,
    CharacterJob,
    estimate_calls,
    job_plan,
    load_manifest,
    slugify,
    validate_jobs,
)


def _write_manifest(directory: Path, data) -> Path:
    path = directory / "characters.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _animation(name: str, frame_count: int = 4) -> AnimationSpec:
    return AnimationSpec(
        name=name,
        prompt=Path(f"{name}.txt"),
        selection="uniform" if name == "idle" else "diverse",
        keep_endpoints=name == "idle",
        frame_count=frame_count,
        columns=2,
    )


def _job(output_root: Path, background_mode: str, names, frame_count: int = 4) -> CharacterJob:
    return CharacterJob(
        name="character",
        reference=Path("ref.png"),
        output_root=output_root,
        padding_width=0.25,
        padding_height=0.1,
        background_mode=background_mode,
        animations=tuple(_animation(name, frame_count) for name in names),
        build_overview=False,
        build_gif=False,
    )


class RunBatchTests(unittest.TestCase):
    def test_slugify_normalizes_names(self):
        self.assertEqual(slugify("Horned Skull-Masked Warrior"), "horned_skull_masked_warrior")
        self.assertEqual(slugify("normal attack"), "normal_attack")
        self.assertEqual(slugify("---"), "character")

    def test_manifest_parses_defaults_and_animation_heuristics(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = _write_manifest(
                Path(temporary_directory),
                [
                    {
                        "image_references": "art_references/warrior.png",
                        "animations_prompt": {
                            "idle": "prompt/idle.txt",
                            "normal_attack": "prompt/attack.txt",
                        },
                        "background_remove_option": "spritesheet",
                    }
                ],
            )
            jobs = load_manifest(path)

        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job.name, "warrior")
        self.assertEqual((job.padding_width, job.padding_height), (0.25, 0.10))
        self.assertEqual(job.background_mode, "sheet")
        self.assertTrue(job.build_gif)
        self.assertTrue(job.build_overview)

        idle, attack = job.animations
        self.assertEqual((idle.name, idle.selection, idle.keep_endpoints), ("idle", "uniform", True))
        self.assertEqual(
            (attack.name, attack.selection, attack.keep_endpoints),
            ("normal_attack", "diverse", False),
        )
        self.assertEqual((idle.frame_count, idle.columns), (8, 4))

    def test_manifest_accepts_list_of_single_key_objects(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = _write_manifest(
                Path(temporary_directory),
                {
                    "characters": [
                        {
                            "name": "skull",
                            "image_references": ["art_references/warrior.png"],
                            "padding": {"horizontal": 0.4, "vertical": 0.2},
                            "animations_prompt": [
                                {"walk": "prompt/walk.txt"},
                                {"death": {"prompt": "prompt/death.txt", "selection": "uniform"}},
                            ],
                            "background_remove_option": "none",
                        }
                    ]
                },
            )
            job = load_manifest(path)[0]

        self.assertEqual(job.name, "skull")
        self.assertEqual((job.padding_width, job.padding_height), (0.4, 0.2))
        self.assertEqual(job.background_mode, "none")
        self.assertEqual([a.name for a in job.animations], ["walk", "death"])
        self.assertEqual(job.animations[1].selection, "uniform")

    def test_zero_padding_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = _write_manifest(
                Path(temporary_directory),
                [
                    {
                        "image_references": "art_references/warrior.png",
                        "padding_width": 0,
                        "animations_prompt": {"idle": "prompt/idle.txt"},
                    }
                ],
            )
            with self.assertRaises(ValueError) as context:
                load_manifest(path)
        self.assertIn("padded", str(context.exception))

    def test_unknown_background_option_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = _write_manifest(
                Path(temporary_directory),
                [
                    {
                        "image_references": "art_references/warrior.png",
                        "animations_prompt": {"idle": "prompt/idle.txt"},
                        "background_remove_option": "magic",
                    }
                ],
            )
            with self.assertRaises(ValueError):
                load_manifest(path)

    def test_multiple_references_in_one_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = _write_manifest(
                Path(temporary_directory),
                [
                    {
                        "image_references": ["a.png", "b.png"],
                        "animations_prompt": {"idle": "prompt/idle.txt"},
                    }
                ],
            )
            with self.assertRaises(ValueError) as context:
                load_manifest(path)
        self.assertIn("exactly one image", str(context.exception))

    def test_duplicate_animation_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = _write_manifest(
                Path(temporary_directory),
                [
                    {
                        "image_references": "art_references/warrior.png",
                        "animations_prompt": [{"idle": "a.txt"}, {"idle": "b.txt"}],
                    }
                ],
            )
            with self.assertRaises(ValueError):
                load_manifest(path)

    def test_empty_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = _write_manifest(Path(temporary_directory), [])
            with self.assertRaises(ValueError):
                load_manifest(path)

    def test_estimate_calls_sheet_mode_is_one_per_animation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            plan = job_plan(
                _job(Path(temporary_directory), "sheet", ("idle", "walk", "run"))
            )
        self.assertEqual(
            estimate_calls([plan]),
            {"video_generations": 3, "background_requests": 3},
        )
        self.assertEqual(
            estimate_calls([plan], skip_background=True),
            {"video_generations": 3, "background_requests": 0},
        )

    def test_estimate_calls_frames_mode_counts_each_frame(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            plan = job_plan(_job(Path(temporary_directory), "frames", ("idle", "walk")))
        self.assertEqual(estimate_calls([plan])["background_requests"], 8)

    def test_estimate_calls_accounts_for_cached_clips(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            path = _write_manifest(
                root,
                [
                    {
                        "name": "cached",
                        "image_references": "art_references/warrior.png",
                        "output_root": str(root / "out"),
                        "animations_prompt": {"idle": "i.txt", "walk": "w.txt"},
                    }
                ],
            )
            job = load_manifest(path)[0]
            (root / "out" / "idle").mkdir(parents=True)
            (root / "out" / "idle" / "source_video.mp4").write_bytes(b"stub")

            plan = job_plan(job)
            self.assertEqual(
                estimate_calls([plan]),
                {"video_generations": 1, "background_requests": 2},
            )
            self.assertEqual(estimate_calls([plan], force=True)["video_generations"], 2)

    def test_validate_jobs_reports_missing_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = _write_manifest(
                Path(temporary_directory),
                [
                    {
                        "image_references": "art_references/missing.png",
                        "animations_prompt": {"idle": "prompt/missing.txt"},
                    }
                ],
            )
            problems = validate_jobs(load_manifest(path))
        self.assertEqual(len(problems), 2)
        self.assertTrue(any("reference image not found" in problem for problem in problems))
        self.assertTrue(any("prompt not found" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()

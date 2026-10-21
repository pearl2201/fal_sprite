import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from scripts.cutout_parts import (
    PartPrompt,
    inpaint_part,
    layerize_reference,
    mask_to_rgba,
    parse_parts,
    segment_parts,
)


class CutoutPartsTests(unittest.TestCase):
    def test_parse_parts_reads_name_and_prompt(self):
        parts = parse_parts(
            ["weapon=the polearm weapon", "head=the character's head and hair"]
        )
        self.assertEqual(
            parts,
            (
                PartPrompt("weapon", "the polearm weapon"),
                PartPrompt("head", "the character's head and hair"),
            ),
        )

    def test_parse_parts_reads_optional_crop(self):
        parts = parse_parts(["hand=the hand@600,500,900,760"])
        self.assertEqual(
            parts[0],
            PartPrompt("hand", "the hand", (600, 500, 900, 760)),
        )

    def test_parse_parts_rejects_bad_crop(self):
        with self.assertRaisesRegex(ValueError, "requires x1 < x2"):
            parse_parts(["hand=the hand@900,500,600,760"])
        with self.assertRaisesRegex(ValueError, "must be integers"):
            parse_parts(["hand=the hand@a,b,c,d"])

    def test_parse_parts_rejects_malformed_and_duplicate_values(self):
        with self.assertRaisesRegex(ValueError, "Part 1: expected 'name=prompt'"):
            parse_parts(["weapon"])
        with self.assertRaisesRegex(ValueError, "must both be non-empty"):
            parse_parts(["=prompt"])
        with self.assertRaisesRegex(ValueError, "duplicate part name 'arm'"):
            parse_parts(["arm=left arm", "arm=right arm"])

    def test_mask_to_rgba_keeps_canvas_and_applies_alpha(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            image_path = root / "image.png"
            mask_path = root / "mask.png"
            output_path = root / "part.png"
            Image.new("RGB", (20, 10), (255, 255, 255)).save(image_path)
            mask = Image.new("L", (20, 10), 0)
            mask.paste(255, (5, 2, 10, 6))
            mask.save(mask_path)

            metadata = mask_to_rgba(image_path, mask_path, output_path)

            with Image.open(output_path) as result:
                self.assertEqual(result.size, (20, 10))
                self.assertEqual(result.getpixel((0, 0))[3], 0)
                self.assertEqual(result.getpixel((6, 3))[3], 255)
            self.assertEqual(metadata["opaque_pixels"], 20)

    def test_mask_to_rgba_rejects_mismatched_dimensions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            image_path = root / "image.png"
            mask_path = root / "mask.png"
            Image.new("RGB", (20, 10), "white").save(image_path)
            Image.new("L", (10, 10), 255).save(mask_path)
            with self.assertRaisesRegex(ValueError, "does not match image size"):
                mask_to_rgba(image_path, mask_path, root / "part.png")

    def test_segment_parts_submits_one_request_per_part(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reference = root / "reference.png"
            Image.new("RGB", (20, 10), "white").save(reference)
            calls = []

            def subscribe(endpoint, **kwargs):
                calls.append((endpoint, kwargs["arguments"]))
                return {"image": {"url": f"https://example.com/mask-{len(calls)}.png"}}

            def write_mask(url, destination):
                mask = Image.new("L", (20, 10), 0)
                mask.paste(255, (5, 2, 10, 6))
                mask.save(destination)

            fake_client = SimpleNamespace(
                upload_file=lambda path: "https://example.com/uploaded.png",
                subscribe=subscribe,
            )
            with patch.dict(sys.modules, {"fal_client": fake_client}):
                with patch.dict(os.environ, {"FAL_KEY": "test-key"}):
                    with patch("scripts.cutout_parts.load_project_env"):
                        with patch(
                            "scripts.cutout_parts._download_asset",
                            side_effect=write_mask,
                        ):
                            metadata = segment_parts(
                                reference,
                                root / "out",
                                (PartPrompt("weapon", "the polearm weapon"),),
                            )

            self.assertEqual(metadata["api_calls"], 1)
            self.assertEqual(len(calls), 1)
            endpoint, arguments = calls[0]
            self.assertEqual(endpoint, "fal-ai/evf-sam")
            self.assertTrue(arguments["mask_only"])
            self.assertTrue(arguments["semantic_type"])
            self.assertEqual(arguments["prompt"], "the polearm weapon")
            self.assertTrue((root / "out" / "masks" / "weapon_mask.png").is_file())
            self.assertTrue((root / "out" / "parts" / "weapon.png").is_file())
            saved = json.loads(
                (root / "out" / "segmentation.json").read_text(encoding="utf-8")
            )
            self.assertEqual(saved["parts"][0]["name"], "weapon")

    def test_segment_parts_with_crop_pastes_mask_back_to_full_canvas(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reference = root / "reference.png"
            Image.new("RGB", (40, 20), "white").save(reference)
            calls = []

            def subscribe(endpoint, **kwargs):
                calls.append(kwargs["arguments"])
                return {"image": {"url": "https://example.com/crop-mask.png"}}

            def write_crop_mask(url, destination):
                mask = Image.new("L", (20, 10), 0)
                mask.paste(255, (2, 2, 8, 8))
                mask.save(destination)

            fake_client = SimpleNamespace(
                upload_file=lambda path: f"https://example.com/{Path(path).name}",
                subscribe=subscribe,
            )
            with patch.dict(sys.modules, {"fal_client": fake_client}):
                with patch.dict(os.environ, {"FAL_KEY": "test-key"}):
                    with patch("scripts.cutout_parts.load_project_env"):
                        with patch(
                            "scripts.cutout_parts._download_asset",
                            side_effect=write_crop_mask,
                        ):
                            metadata = segment_parts(
                                reference,
                                root / "out",
                                (
                                    PartPrompt(
                                        "hand", "the hand", (10, 5, 30, 15)
                                    ),
                                ),
                                min_component_pixels=0,
                            )

            self.assertEqual(len(calls), 1)
            with Image.open(root / "out" / "masks" / "hand_mask.png") as mask:
                self.assertEqual(mask.size, (40, 20))
                self.assertEqual(mask.getpixel((0, 0)), 0)
                self.assertEqual(mask.getpixel((12, 7)), 255)
            self.assertEqual(metadata["parts"][0]["crop"], [10, 5, 30, 15])

    def test_layerize_reference_downloads_named_layers(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reference = root / "reference.png"
            Image.new("RGB", (20, 10), "white").save(reference)
            calls = []

            def subscribe(endpoint, **kwargs):
                calls.append((endpoint, kwargs["arguments"]))
                return {
                    "layers": [
                        {"image": {"url": "https://example.com/base.png"}, "z_index": 0},
                        {
                            "image": {"url": "https://example.com/hair.png"},
                            "z_index": 1,
                            "name": "Hair",
                            "description": "ponytail",
                            "bounding_box": {"left": 1, "top": 2, "right": 3, "bottom": 4},
                        },
                    ]
                }

            def write_layer(url, destination):
                Image.new("RGBA", (20, 10), (255, 255, 255, 0)).save(destination)

            fake_client = SimpleNamespace(
                upload_file=lambda path: "https://example.com/uploaded.png",
                subscribe=subscribe,
            )
            with patch.dict(sys.modules, {"fal_client": fake_client}):
                with patch.dict(os.environ, {"FAL_KEY": "test-key"}):
                    with patch("scripts.cutout_parts.load_project_env"):
                        with patch(
                            "scripts.cutout_parts._download_asset",
                            side_effect=write_layer,
                        ):
                            metadata = layerize_reference(
                                reference, root / "out", prompt="separate hair"
                            )

            self.assertEqual(metadata["api_calls"], 1)
            endpoint, arguments = calls[0]
            self.assertEqual(endpoint, "bytedance/seedream/v5/flash/layerize")
            self.assertEqual(arguments["prompt"], "separate hair")
            self.assertTrue((root / "out" / "layers" / "00_base.png").is_file())
            self.assertTrue((root / "out" / "layers" / "01_hair.png").is_file())
            self.assertEqual(metadata["layers"][1]["z_index"], 1)
            self.assertEqual(metadata["layers"][1]["name"], "Hair")

    def test_inpaint_part_writes_output_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            image_path = root / "arm.png"
            mask_path = root / "arm_mask.png"
            output_path = root / "arm_extended.png"
            Image.new("RGB", (20, 10), "white").save(image_path)
            Image.new("L", (20, 10), 255).save(mask_path)
            calls = []

            def subscribe(endpoint, **kwargs):
                calls.append((endpoint, kwargs["arguments"]))
                return {"images": [{"url": "https://example.com/fill.png"}], "seed": 7}

            def write_output(url, destination):
                Image.new("RGB", (20, 10), "white").save(destination)

            fake_client = SimpleNamespace(
                upload_file=lambda path: f"https://example.com/{Path(path).name}",
                subscribe=subscribe,
            )
            with patch.dict(sys.modules, {"fal_client": fake_client}):
                with patch.dict(os.environ, {"FAL_KEY": "test-key"}):
                    with patch("scripts.cutout_parts.load_project_env"):
                        with patch(
                            "scripts.cutout_parts._download_asset",
                            side_effect=write_output,
                        ):
                            metadata = inpaint_part(
                                image_path,
                                mask_path,
                                output_path,
                                "extend the armor",
                            )

            self.assertTrue(output_path.is_file())
            self.assertEqual(metadata["seed_returned"], 7)
            endpoint, arguments = calls[0]
            self.assertEqual(endpoint, "fal-ai/flux-pro/v1/fill")
            self.assertEqual(arguments["prompt"], "extend the armor")
            self.assertEqual(arguments["output_format"], "png")
            sidecar = json.loads(
                output_path.with_suffix(".inpaint.json").read_text(encoding="utf-8")
            )
            self.assertEqual(sidecar["api_calls"], 1)

    def test_inpaint_part_rejects_mismatched_mask_before_uploading(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            image_path = root / "arm.png"
            mask_path = root / "arm_mask.png"
            Image.new("RGB", (20, 10), "white").save(image_path)
            Image.new("L", (10, 10), 255).save(mask_path)
            with self.assertRaisesRegex(ValueError, "identical dimensions"):
                inpaint_part(
                    image_path,
                    mask_path,
                    root / "out.png",
                    "extend",
                )


if __name__ == "__main__":
    unittest.main()

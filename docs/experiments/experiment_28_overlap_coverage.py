"""Experiment 28: compare full-image and estimated-overlap coverage."""

import argparse
import csv
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
from PIL import Image, ImageOps

from benchmarks.orb_detector import compare_orb
from docs.experiments.experiment_27_spatial_coverage import (
    RESULTS,
    SEED,
    benchmark_controls,
    synthetic_controls,
)


def edge_controls(negative_controls, directory):
    """Make genuine crops and shared-patch pairs from the same source regions."""
    for index, (_, _, _, reference, candidate) in enumerate(negative_controls, 1):
        images = []
        for path in (reference, candidate):
            with Image.open(path) as source:
                oriented = ImageOps.exif_transpose(source).convert("RGB")
                images.append(ImageOps.fit(oriented, (768, 768)))
        reference_image, composite = images
        size = 256 if index % 2 else 384
        patch = reference_image.crop((0, 0, size, size))
        composite.paste(patch, (768 - size, 768 - size))

        reference_path = directory / f"edge_reference_{index}.png"
        crop_path = directory / f"edge_crop_{index}.png"
        composite_path = directory / f"edge_composite_{index}.png"
        reference_image.save(reference_path)
        patch.save(crop_path)
        composite.save(composite_path)

        yield f"edge_crop_{index}", "photo_edge_crop", "positive", reference_path, crop_path
        yield (
            f"edge_composite_{index}", "photo_edge_composite", "negative",
            reference_path, composite_path,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, default=RESULTS / "benchmark_pairs.csv")
    parser.add_argument("--output", type=Path, default=RESULTS / "experiment_28_overlap_coverage.csv")
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")

    cv2.setRNGSeed(SEED)
    controls = list(benchmark_controls(args.pairs))
    negative_controls = [control for control in controls if control[1] == "generated_negative"]
    with TemporaryDirectory(prefix="mediadedup-orb28-") as temporary:
        directory = Path(temporary)
        controls.extend(synthetic_controls(directory))
        controls.extend(edge_controls(negative_controls[:6], directory))
        rows = [
            {
                "pair_id": pair_id,
                "group": group,
                "label": label,
                **compare_orb(reference, candidate, measure_overlap=True),
            }
            for pair_id, group, label, reference, candidate in controls
        ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Measured {len(rows)} pairs. Results: {args.output}")


if __name__ == "__main__":
    main()

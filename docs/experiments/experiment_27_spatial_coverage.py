"""Experiment 27: measure spatial coverage before and after RANSAC.

Run from the repository root with:
python -m docs.experiments.experiment_27_spatial_coverage
"""

import argparse
import csv
from pathlib import Path
import random
from tempfile import TemporaryDirectory

import cv2
import numpy as np
from PIL import Image, ImageDraw

from benchmarks.orb_detector import compare_orb


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmarks" / "results"
CURATED_LABELS = ROOT / "benchmarks" / "data" / "curated_pair_labels.csv"
GRID_SIZE = 20
SEED = 27


def read_pairs(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def benchmark_controls(pair_list):
    rows = read_pairs(pair_list)
    negative_candidates = [
        row for row in rows
        if row["pair_group"] == "original_to_original" and row["label"] == "negative"
    ]
    # Sample across the generated negatives instead of using a single anchor.
    for row in random.Random(SEED).sample(negative_candidates, 36):
        yield row["pair_id"], "generated_negative", "negative", ROOT / row["image_a"], ROOT / row["image_b"]

    for row in rows:
        if (
            row["pair_group"] == "original_to_variant"
            and row["label"] == "positive"
            and row["transformation_b"] in {"exact_copy", "crop_centre_080"}
        ):
            yield (
                row["pair_id"], row["transformation_b"], "positive",
                ROOT / row["image_a"], ROOT / row["image_b"],
            )

    for row in read_pairs(CURATED_LABELS):
        yield (
            row["pair_id"], row["relationship"], row["near_duplicate_label"],
            ROOT / row["image_a"], ROOT / row["image_b"],
        )


def synthetic_controls(directory):
    """Compare each insert with its source and with a different composite."""
    rng = np.random.default_rng(SEED)
    for size in (256, 320, 384):
        patch = Image.fromarray(rng.integers(0, 256, (size, size), dtype=np.uint8))
        reference = Image.new("L", (1024, 768), 70)
        ImageDraw.Draw(reference).rectangle((40, 80, 240, 670), fill=200)
        reference.paste(patch, (304, 160))

        composite = Image.new("L", reference.size, 180)
        ImageDraw.Draw(composite).ellipse((70, 150, 510, 700), fill=50)
        composite.paste(patch, (548, 276))

        source_path = directory / f"reference_{size}.png"
        crop_path = directory / f"crop_{size}.png"
        composite_path = directory / f"composite_{size}.png"
        reference.save(source_path)
        patch.save(crop_path)
        composite.save(composite_path)

        yield f"crop_{size}", "synthetic_crop", "positive", source_path, crop_path
        yield (
            f"composite_{size}", "synthetic_shared_patch", "negative",
            source_path, composite_path,
        )


def measure(control):
    pair_id, group, label, reference, candidate = control
    return {
        "pair_id": pair_id,
        "group": group,
        "label": label,
        **compare_orb(reference, candidate, diagnostic_grid_size=GRID_SIZE),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, default=RESULTS / "benchmark_pairs.csv")
    parser.add_argument("--output", type=Path, default=RESULTS / "experiment_27_spatial_coverage.csv")
    args = parser.parse_args()

    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")

    cv2.setRNGSeed(SEED)
    rows = [measure(control) for control in benchmark_controls(args.pairs)]
    with TemporaryDirectory(prefix="mediadedup-orb27-") as directory:
        rows.extend(measure(control) for control in synthetic_controls(Path(directory)))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Measured {len(rows)} pairs on a {GRID_SIZE} x {GRID_SIZE} grid.")
    print(f"Results: {args.output}")


if __name__ == "__main__":
    main()

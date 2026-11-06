"""Compare every hard negative against every original using four detectors."""

import csv
from pathlib import Path

from benchmarks.run_hard_negative_orb import (
    IMAGE_EXTENSIONS,
    RESULT_FIELDS,
    run_detector,
)
from benchmarks.detectors import (
    compare_dhash,
    compare_phash,
    compare_ssim,
)
from benchmarks.orb_detector import compare_orb


ROOT = Path(__file__).resolve().parent.parent

ORIGINALS = ROOT / "TestMedia" / "Originals"
HARD_NEGATIVES = ROOT / "TestMedia" / "HardNegatives"

OUTPUT = (
    ROOT
    / "benchmarks"
    / "results"
    / "hard_negative_cross_reference_results.csv"
)


def get_images(directory):
    """Return supported image files in deterministic filename order."""

    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )


def main():
    if not ORIGINALS.is_dir():
        raise FileNotFoundError(
            f"Originals directory not found: {ORIGINALS}"
        )

    if not HARD_NEGATIVES.is_dir():
        raise FileNotFoundError(
            f"Hard-negative directory not found: {HARD_NEGATIVES}"
        )

    if OUTPUT.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing results: {OUTPUT}"
        )

    originals = get_images(ORIGINALS)
    hard_negatives = get_images(HARD_NEGATIVES)

    if not originals:
        raise RuntimeError("No original images found.")

    if not hard_negatives:
        raise RuntimeError("No hard-negative images found.")

    total_pairs = len(originals) * len(hard_negatives)

    print(f"Original images: {len(originals)}")
    print(f"Hard-negative images: {len(hard_negatives)}")
    print(f"Total comparisons: {total_pairs}")
    print("Detectors: ORB, pHash, dHash, SSIM")
    print()

    rows = []

    for negative_index, negative in enumerate(
        hard_negatives,
        start=1,
    ):
        relative_negative = negative.relative_to(ROOT).as_posix()

        print(
            f"[{negative_index}/{len(hard_negatives)}] "
            f"{negative.name}"
        )

        for original_index, original in enumerate(
            originals,
            start=1,
        ):
            relative_original = original.relative_to(ROOT).as_posix()

            row = {
                "pair_id": (
                    f"hn_{negative_index:04d}_"
                    f"orig_{original_index:04d}"
                ),
                "pair_group": "original_to_hard_negative",
                "label": "negative",
                "image_a": relative_original,
                "image_b": relative_negative,
            }

            run_detector(
                row, "orb", compare_orb, original, negative
            )

            run_detector(
                row, "phash", compare_phash, original, negative
            )

            run_detector(
                row, "dhash", compare_dhash, original, negative
            )

            run_detector(
                row, "ssim", compare_ssim, original, negative
            )

            rows.append(row)

        print(f"    Completed comparisons: {len(originals)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=RESULT_FIELDS,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"Completed pairs: {len(rows)}")

    for detector in ("orb", "phash", "dhash", "ssim"):
        successful = sum(
            row.get(f"{detector}_status") == "ok"
            for row in rows
        )
        not_comparable = sum(
            row.get(f"{detector}_status") == "not_comparable"
            for row in rows
        )
        errors = sum(
            row.get(f"{detector}_status") == "error"
            for row in rows
        )

        print(
            f"{detector}: successful={successful}, "
            f"not_comparable={not_comparable}, errors={errors}"
        )

    print(f"\nResults saved to: {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
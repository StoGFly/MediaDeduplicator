
"""Run all production image similarity detectors against hard negatives."""

import csv
from pathlib import Path

from benchmarks.detectors import (
    compare_dhash,
    compare_phash,
    compare_ssim,
)
from benchmarks.orb_detector import compare_orb


ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "TestMedia" / "Originals" / "2024-12-03 15.24.16.jpg"
HARD_NEGATIVES = ROOT / "TestMedia" / "HardNegatives"

OUTPUT = (
    ROOT
    / "benchmarks"
    / "results"
    / "hard_negative_detector_results.csv"
)

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp",
    ".tif", ".tiff", ".webp",
}


RESULT_FIELDS = [
    "pair_id",
    "pair_group",
    "label",
    "image_a",
    "image_b",

    "orb_status",
    "orb_reference_keypoints",
    "orb_candidate_keypoints",
    "orb_forward_matches",
    "orb_mutual_matches",
    "orb_inliers",
    "orb_inlier_percent",
    "orb_reference_coverage_percent",
    "orb_candidate_coverage_percent",
    "orb_scale",
    "orb_rotation_degrees",
    "orb_transformation_valid",
    "orb_geometry_supported",
    "orb_geometry_status",
    "orb_error",

    "phash_status",
    "phash_distance",
    "phash_hash_bits",
    "phash_similarity_percent",
    "phash_hash_a",
    "phash_hash_b",
    "phash_error",

    "dhash_status",
    "dhash_distance",
    "dhash_hash_bits",
    "dhash_similarity_percent",
    "dhash_hash_a",
    "dhash_hash_b",
    "dhash_error",

    "ssim_status",
    "ssim_similarity_score",
    "ssim_similarity_percent",
    "ssim_rotation_degrees",
    "ssim_error",
]


def run_detector(row, prefix, detector, image_a, image_b):
    """Run one detector without preventing the others from running."""

    try:
        result = detector(image_a, image_b)

        for key, value in result.items():
            row[f"{prefix}_{key}"] = value

    except Exception as exc:
        row[f"{prefix}_status"] = "error"
        row[f"{prefix}_error"] = f"{type(exc).__name__}: {exc}"


def main():
    if not REFERENCE.is_file():
        raise FileNotFoundError(
            f"Reference image not found: {REFERENCE}"
        )

    if not HARD_NEGATIVES.is_dir():
        raise FileNotFoundError(
            f"Hard-negative directory not found: {HARD_NEGATIVES}"
        )

    if OUTPUT.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing results: {OUTPUT}"
        )

    candidates = sorted(
        (
            path
            for path in HARD_NEGATIVES.iterdir()
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )

    if not candidates:
        raise RuntimeError("No hard-negative images found.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    rows = []

    relative_reference = REFERENCE.relative_to(ROOT).as_posix()

    print(f"Reference: {relative_reference}")
    print(f"Hard-negative images: {len(candidates)}")
    print("Detectors: ORB, pHash, dHash, SSIM")
    print()

    for index, candidate in enumerate(candidates, start=1):
        relative_candidate = candidate.relative_to(ROOT).as_posix()

        print(f"[{index}/{len(candidates)}] {candidate.name}")

        row = {
            "pair_id": f"hard_negative_{index:04d}",
            "pair_group": "reference_to_hard_negative",
            "label": "negative",
            "image_a": relative_reference,
            "image_b": relative_candidate,
        }

        run_detector(
            row, "orb", compare_orb, REFERENCE, candidate
        )

        run_detector(
            row, "phash", compare_phash, REFERENCE, candidate
        )

        run_detector(
            row, "dhash", compare_dhash, REFERENCE, candidate
        )

        run_detector(
            row, "ssim", compare_ssim, REFERENCE, candidate
        )

        rows.append(row)

        print(
            f'    ORB: mutual={row.get("orb_mutual_matches", "")}, '
            f'inliers={row.get("orb_inliers", "")}, '
            f'status={row.get("orb_geometry_status", "")}'
        )
        print(
            f'    pHash: {row.get("phash_similarity_percent", "")}% '
            f'[{row.get("phash_status", "")}]'
        )
        print(
            f'    dHash: {row.get("dhash_similarity_percent", "")}% '
            f'[{row.get("dhash_status", "")}]'
        )
        print(
            f'    SSIM: {row.get("ssim_similarity_percent", "")}% '
            f'[{row.get("ssim_status", "")}]'
        )

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


from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "TestMedia" / "Reference"

IMAGES = [
    "photo_original.jpg",
    "photo_original.png",
    "2022-12-27 21.34.20.jpg",
    "2022-12-27 21.34.20-1.jpg",
]

FEATURE_COUNT = 2000

GRID_SIZES = [10, 20, 40]
COVERAGE_LEVELS = [0.10, 0.20, 0.30]


def load_image(filename):
    path = MEDIA / filename
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)

    if image is None:
        raise FileNotFoundError(f"Could not load image: {path}")

    return image


def analyse_keypoints(keypoints, width, height, rows, cols):
    counts = np.zeros((rows, cols), dtype=np.int32)
    response_sums = np.zeros((rows, cols), dtype=np.float64)

    for keypoint in keypoints:
        col = min(cols - 1, int(keypoint.pt[0] * cols / width))
        row = min(rows - 1, int(keypoint.pt[1] * rows / height))

        counts[row, col] += 1
        response_sums[row, col] += keypoint.response

    averages = np.divide(
        response_sums,
        counts,
        out=np.zeros_like(response_sums),
        where=counts > 0,
    )

    return counts.flatten(), response_sums.flatten(), averages.flatten()


def ranking(scores, occupied_indices):
    return sorted(
        occupied_indices,
        key=lambda index: (-scores[index], index),
    )


def concentration_by_area(scores, counts, total_keypoints, total_response):
    ranked = sorted(
        range(len(counts)),
        key=lambda index: (-scores[index], index),
    )

    print("  Concentration by image area:")

    for percentage in COVERAGE_LEVELS:
        number_of_cells = max(1, round(len(counts) * percentage))
        selected = ranked[:number_of_cells]

        keypoints = int(counts[selected].sum())
        response = float(total_response[selected].sum())

        kp_percentage = (
            keypoints / total_keypoints * 100
            if total_keypoints else 0
        )

        response_percentage = (
            response / total_response.sum() * 100
            if total_response.sum() else 0
        )

        print(
            f"    Top {percentage * 100:2.0f}% area "
            f"({number_of_cells:4d} cells): "
            f"{keypoints:4d} keypoints "
            f"({kp_percentage:6.2f}%) | "
            f"response {response_percentage:6.2f}%"
        )


def concentration_by_occupied_cells(scores, counts, occupied_indices):
    ranked = ranking(scores, occupied_indices)

    print("  Concentration by occupied cells:")

    for percentage in COVERAGE_LEVELS:
        number_of_cells = max(
            1,
            round(len(occupied_indices) * percentage),
        )

        selected = ranked[:number_of_cells]
        keypoints = int(counts[selected].sum())
        total_keypoints = int(counts.sum())

        kp_percentage = (
            keypoints / total_keypoints * 100
            if total_keypoints else 0
        )

        print(
            f"    Top {percentage * 100:2.0f}% occupied "
            f"({number_of_cells:4d} cells): "
            f"{keypoints:4d} keypoints "
            f"({kp_percentage:6.2f}%)"
        )


def ranking_overlap(counts, response_sums, averages, occupied_indices):
    density_rank = ranking(counts, occupied_indices)
    total_rank = ranking(response_sums, occupied_indices)
    average_rank = ranking(averages, occupied_indices)

    print("  Ranking overlap (occupied cells only):")

    for percentage in COVERAGE_LEVELS:
        number_of_cells = max(
            1,
            round(len(occupied_indices) * percentage),
        )

        density_set = set(density_rank[:number_of_cells])
        total_set = set(total_rank[:number_of_cells])
        average_set = set(average_rank[:number_of_cells])

        pairs = [
            ("Density vs total response", density_set, total_set),
            ("Density vs average response", density_set, average_set),
            ("Total vs average response", total_set, average_set),
        ]

        results = []

        for label, first, second in pairs:
            overlap = len(first & second)
            results.append(
                f"{label}: {overlap}/{number_of_cells} "
                f"({overlap / number_of_cells * 100:.1f}%)"
            )

        print(f"    Top {percentage * 100:.0f}%: " + " | ".join(results))


def analyse_image(filename, orb):
    image = load_image(filename)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    keypoints, _ = orb.detectAndCompute(gray, None)

    print("\n" + "=" * 110)
    print(f"IMAGE: {filename}")
    print("=" * 110)
    print(f"Dimensions: {image.shape[1]} x {image.shape[0]}")
    print(f"Detected keypoints: {len(keypoints)}")

    if not keypoints:
        print("No keypoints detected. Skipping.")
        return

    for grid_size in GRID_SIZES:
        counts, response_sums, averages = analyse_keypoints(
            keypoints,
            image.shape[1],
            image.shape[0],
            grid_size,
            grid_size,
        )

        occupied_indices = np.flatnonzero(counts > 0)
        empty_count = len(counts) - len(occupied_indices)

        print(f"\n--- Grid: {grid_size} x {grid_size} ---")
        print(f"Occupied cells: {len(occupied_indices)}/{len(counts)}")
        print(f"Empty cells: {empty_count}")
        print(f"Maximum keypoints in one cell: {int(counts.max())}")
        print(f"Mean keypoints per cell: {counts.mean():.2f}")
        print(f"Median keypoints per cell: {np.median(counts):.2f}")

        concentration_by_area(
            counts,
            counts,
            len(keypoints),
            response_sums,
        )

        concentration_by_occupied_cells(
            counts,
            counts,
            occupied_indices,
        )

        ranking_overlap(
            counts,
            response_sums,
            averages,
            occupied_indices,
        )


def main():
    print("=" * 110)
    print("EXPERIMENT 26 - GRID RESOLUTION SENSITIVITY")
    print("=" * 110)
    print(f"OpenCV version: {cv2.__version__}")
    print(f"ORB features: {FEATURE_COUNT}")
    print(f"Grid sizes: {GRID_SIZES}")

    orb = cv2.ORB_create(nfeatures=FEATURE_COUNT)

    for filename in IMAGES:
        analyse_image(filename, orb)

    print("\n" + "=" * 110)
    print("EXPERIMENT 26 COMPLETE")
    print("=" * 110)


if __name__ == "__main__":
    main()

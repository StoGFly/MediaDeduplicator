
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "TestMedia" / "Reference"

REFERENCE = "photo_original.jpg"
CANDIDATE = "photo_exact_copy.jpg"

FEATURE_COUNT = 2000
GRID_ROWS = 20
GRID_COLS = 20

COVERAGE_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50]


def load_image(filename):
    path = MEDIA / filename
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)

    if image is None:
        raise FileNotFoundError(f"Could not load image: {path}")

    return image


def analyse_keypoints(keypoints, width, height):
    """Calculate keypoint count and response statistics per grid cell."""

    counts = np.zeros(
        (GRID_ROWS, GRID_COLS),
        dtype=np.int32,
    )

    response_sums = np.zeros(
        (GRID_ROWS, GRID_COLS),
        dtype=np.float64,
    )

    for keypoint in keypoints:
        col = min(
            GRID_COLS - 1,
            int(keypoint.pt[0] * GRID_COLS / width),
        )

        row = min(
            GRID_ROWS - 1,
            int(keypoint.pt[1] * GRID_ROWS / height),
        )

        counts[row, col] += 1
        response_sums[row, col] += keypoint.response

    averages = np.divide(
        response_sums,
        counts,
        out=np.zeros_like(response_sums),
        where=counts > 0,
    )

    return counts, response_sums, averages


def ranked_cells(scores, descending=True):
    flat = scores.flatten()

    if descending:
        return sorted(
            range(len(flat)),
            key=lambda index: (-flat[index], index),
        )

    return sorted(
        range(len(flat)),
        key=lambda index: (flat[index], index),
    )


def print_concentration(label, ranking, counts, responses):
    flat_counts = counts.flatten()
    flat_responses = responses.flatten()

    print(f"\n{label}")

    cumulative_keypoints = 0
    cumulative_response = 0.0

    for percentage in COVERAGE_LEVELS:
        number_of_cells = round(
            len(ranking) * percentage
        )

        selected = ranking[:number_of_cells]

        cumulative_keypoints = int(
            flat_counts[selected].sum()
        )

        cumulative_response = float(
            flat_responses[selected].sum()
        )

        total_keypoints = int(flat_counts.sum())
        total_response = float(flat_responses.sum())

        keypoint_percentage = (
            cumulative_keypoints / total_keypoints * 100
            if total_keypoints else 0
        )

        response_percentage = (
            cumulative_response / total_response * 100
            if total_response else 0
        )

        print(
            f"  Top {percentage * 100:4.0f}% of cells: "
            f"{cumulative_keypoints:4d} keypoints "
            f"({keypoint_percentage:6.2f}%) | "
            f"response strength: {response_percentage:6.2f}%"
        )


def main():
    print("=" * 100)
    print("EXPERIMENT 25 - SPATIAL CONCENTRATION AUDIT")
    print("=" * 100)

    print(f"OpenCV version: {cv2.__version__}")
    print(f"ORB features: {FEATURE_COUNT}")
    print(f"Grid: {GRID_COLS} x {GRID_ROWS}")

    reference = load_image(REFERENCE)
    candidate = load_image(CANDIDATE)

    reference_gray = cv2.cvtColor(
        reference,
        cv2.COLOR_BGR2GRAY,
    )

    candidate_gray = cv2.cvtColor(
        candidate,
        cv2.COLOR_BGR2GRAY,
    )

    orb = cv2.ORB_create(nfeatures=FEATURE_COUNT)

    reference_keypoints, _ = orb.detectAndCompute(
        reference_gray,
        None,
    )

    candidate_keypoints, _ = orb.detectAndCompute(
        candidate_gray,
        None,
    )

    print(f"\nReference: {REFERENCE}")
    print(f"Dimensions: {reference.shape[1]} x {reference.shape[0]}")
    print(f"Reference keypoints: {len(reference_keypoints)}")

    print(f"\nCandidate: {CANDIDATE}")
    print(f"Dimensions: {candidate.shape[1]} x {candidate.shape[0]}")
    print(f"Candidate keypoints: {len(candidate_keypoints)}")

    counts, response_sums, averages = analyse_keypoints(
        candidate_keypoints,
        candidate.shape[1],
        candidate.shape[0],
    )

    density_ranking = ranked_cells(counts)
    total_response_ranking = ranked_cells(response_sums)
    average_response_ranking = ranked_cells(averages)

    print("\n" + "=" * 100)
    print("KEYPOINT CONCENTRATION")
    print("=" * 100)

    print_concentration(
        "RANKED BY KEYPOINT DENSITY",
        density_ranking,
        counts,
        response_sums,
    )

    print_concentration(
        "RANKED BY TOTAL RESPONSE STRENGTH",
        total_response_ranking,
        counts,
        response_sums,
    )

    print_concentration(
        "RANKED BY AVERAGE RESPONSE STRENGTH",
        average_response_ranking,
        counts,
        response_sums,
    )

    print("\n" + "=" * 100)
    print("RANKING OVERLAP")
    print("=" * 100)

    for percentage in COVERAGE_LEVELS:
        number_of_cells = round(
            GRID_ROWS * GRID_COLS * percentage
        )

        density_set = set(
            density_ranking[:number_of_cells]
        )

        response_set = set(
            total_response_ranking[:number_of_cells]
        )

        average_set = set(
            average_response_ranking[:number_of_cells]
        )

        density_response_overlap = len(
            density_set & response_set
        )

        density_average_overlap = len(
            density_set & average_set
        )

        response_average_overlap = len(
            response_set & average_set
        )

        print(
            f"\nTop {percentage * 100:.0f}% "
            f"({number_of_cells} cells):"
        )

        print(
            f"  Density vs total response: "
            f"{density_response_overlap}/{number_of_cells} "
            f"({density_response_overlap / number_of_cells * 100:.1f}%)"
        )

        print(
            f"  Density vs average response: "
            f"{density_average_overlap}/{number_of_cells} "
            f"({density_average_overlap / number_of_cells * 100:.1f}%)"
        )

        print(
            f"  Total vs average response: "
            f"{response_average_overlap}/{number_of_cells} "
            f"({response_average_overlap / number_of_cells * 100:.1f}%)"
        )

    print("\n" + "=" * 100)
    print("DISTRIBUTION SUMMARY")
    print("=" * 100)

    occupied = int(np.count_nonzero(counts))
    empty = counts.size - occupied

    print(f"Occupied cells: {occupied}/{counts.size}")
    print(f"Empty cells: {empty}/{counts.size}")
    print(f"Maximum keypoints in one cell: {int(counts.max())}")
    print(f"Mean keypoints per cell: {counts.mean():.2f}")
    print(f"Median keypoints per cell: {np.median(counts):.2f}")
    print(f"Maximum cell response sum: {response_sums.max():.5f}")
    print(f"Maximum cell average response: {averages.max():.5f}")

    print("\nExperiment 25 diagnostic complete.")


if __name__ == "__main__":
    main()

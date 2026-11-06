
from pathlib import Path
import math

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "TestMedia" / "Reference"

REFERENCE = "photo_original.jpg"

CANDIDATES = {
    "Exact-copy positive": "photo_exact_copy.jpg",
    "Resized PNG positive": "photo_original.png",
    "Taxi negative 1": "2022-12-27 21.34.20.jpg",
    "Taxi negative 2": "2022-12-27 21.34.20-1.jpg",
}

OCCLUSION_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50]

FEATURE_COUNT = 2000
LOWE_RATIO = 0.75
RANSAC_THRESHOLD = 5.0
MINIMUM_MATCHES = 8
MINIMUM_INLIERS = 6

GRID_ROWS = 20
GRID_COLS = 20
RANDOM_SEED = 2401

OCCLUSION_COLOUR = (0, 0, 0)


def load_image(filename):
    path = MEDIA / filename
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)

    if image is None:
        raise FileNotFoundError(f"Could not load image: {path}")

    return image


def get_cells(width, height):
    """Return deterministic, approximately equal-sized grid cells."""

    x_edges = np.linspace(0, width, GRID_COLS + 1, dtype=int)
    y_edges = np.linspace(0, height, GRID_ROWS + 1, dtype=int)

    cells = []

    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            cells.append((
                x_edges[col],
                y_edges[row],
                x_edges[col + 1],
                y_edges[row + 1],
            ))

    return cells


def score_feature_cells(keypoints, width, height, cells):
    """Count keypoints and sum ORB responses in each grid cell."""

    counts = np.zeros(len(cells), dtype=np.int32)
    responses = np.zeros(len(cells), dtype=np.float64)

    for keypoint in keypoints:
        col = min(
            GRID_COLS - 1,
            int(keypoint.pt[0] * GRID_COLS / width),
        )

        row = min(
            GRID_ROWS - 1,
            int(keypoint.pt[1] * GRID_ROWS / height),
        )

        index = row * GRID_COLS + col

        counts[index] += 1
        responses[index] += keypoint.response

    return counts, responses


def select_cells(counts, responses, strategy, percentage):
    """Select the grid cells to obscure."""

    total_cells = len(counts)
    number_to_select = round(total_cells * percentage)

    if strategy == "random":
        rng = np.random.default_rng(RANDOM_SEED)

        # One reproducible ordering, nested across coverage levels.
        order = rng.permutation(total_cells)

    elif strategy == "feature density":
        order = sorted(
            range(total_cells),
            key=lambda i: (-counts[i], -responses[i], i),
        )

    elif strategy == "feature strength":
        order = sorted(
            range(total_cells),
            key=lambda i: (-responses[i], -counts[i], i),
        )

    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    return order[:number_to_select]


def create_occlusion(
    image,
    keypoints,
    percentage,
    strategy,
):
    """Apply selected grid cells and measure actual feature removal."""

    height, width = image.shape[:2]
    cells = get_cells(width, height)

    counts, responses = score_feature_cells(
        keypoints,
        width,
        height,
        cells,
    )

    selected = select_cells(
        counts,
        responses,
        strategy,
        percentage,
    )

    mask = np.zeros((height, width), dtype=np.uint8)

    for index in selected:
        x1, y1, x2, y2 = cells[index]
        mask[y1:y2, x1:x2] = 255

    result = image.copy()
    result[mask > 0] = OCCLUSION_COLOUR

    actual_percentage = np.count_nonzero(mask) / mask.size * 100

    removed_keypoints = sum(
        mask[
            min(height - 1, max(0, round(kp.pt[1]))),
            min(width - 1, max(0, round(kp.pt[0]))),
        ] > 0
        for kp in keypoints
    )

    removed_percentage = (
        removed_keypoints / len(keypoints) * 100
        if keypoints else 0.0
    )

    return (
        result,
        actual_percentage,
        removed_keypoints,
        removed_percentage,
    )


def mutual_ratio_matches(descriptors_a, descriptors_b, matcher):
    forward_raw = matcher.knnMatch(descriptors_a, descriptors_b, k=2)
    reverse_raw = matcher.knnMatch(descriptors_b, descriptors_a, k=2)

    forward = [
        pair[0]
        for pair in forward_raw
        if len(pair) == 2
        and pair[0].distance < LOWE_RATIO * pair[1].distance
    ]

    reverse_pairs = {
        (pair[0].queryIdx, pair[0].trainIdx)
        for pair in reverse_raw
        if len(pair) == 2
        and pair[0].distance < LOWE_RATIO * pair[1].distance
    }

    return [
        match
        for match in forward
        if (match.trainIdx, match.queryIdx) in reverse_pairs
    ]


def compare_images(reference_gray, candidate_gray, orb, matcher):
    reference_keypoints, reference_descriptors = orb.detectAndCompute(
        reference_gray, None
    )

    candidate_keypoints, candidate_descriptors = orb.detectAndCompute(
        candidate_gray, None
    )

    result = {
        "reference_keypoints": len(reference_keypoints),
        "candidate_keypoints": len(candidate_keypoints),
        "mutual": 0,
        "inliers": 0,
        "ratio": 0.0,
        "scale": None,
        "rotation": None,
    }

    if reference_descriptors is None or candidate_descriptors is None:
        return result

    matches = mutual_ratio_matches(
        reference_descriptors,
        candidate_descriptors,
        matcher,
    )

    result["mutual"] = len(matches)

    if len(matches) < MINIMUM_MATCHES:
        return result

    source_points = np.float32([
        candidate_keypoints[match.trainIdx].pt
        for match in matches
    ]).reshape(-1, 1, 2)

    destination_points = np.float32([
        reference_keypoints[match.queryIdx].pt
        for match in matches
    ]).reshape(-1, 1, 2)

    matrix, inlier_mask = cv2.estimateAffinePartial2D(
        source_points,
        destination_points,
        method=cv2.RANSAC,
        ransacReprojThreshold=RANSAC_THRESHOLD,
        maxIters=2000,
        confidence=0.99,
        refineIters=10,
    )

    if matrix is None or inlier_mask is None:
        return result

    result["inliers"] = int(inlier_mask.sum())
    result["ratio"] = result["inliers"] / len(matches) * 100
    if result["inliers"] < MINIMUM_INLIERS:
        return result

    result["scale"] = math.hypot(
        matrix[0, 0],
        matrix[1, 0],
    )

    result["rotation"] = math.degrees(
        math.atan2(matrix[1, 0], matrix[0, 0])
    )

    return result


def print_result(result):
    print(
        f"  Keypoints: reference={result['reference_keypoints']}, "
        f"candidate={result['candidate_keypoints']}"
    )

    print(f"  Mutual matches: {result['mutual']}")

    print(
        f"  RANSAC inliers: {result['inliers']} "
        f"({result['ratio']:.2f}%)"
    )

    if result["scale"] is not None:
        print(f"  Estimated scale: {result['scale']:.5f}")
        print(f"  Estimated rotation: {result['rotation']:.2f} degrees")
    else:
        print("  Estimated transformation: unavailable")


def main():
    print("=" * 100)
    print("EXPERIMENT 24 - FEATURE-TARGETED OCCLUSION")
    print("=" * 100)

    print(f"OpenCV version: {cv2.__version__}")
    print(f"ORB features: {FEATURE_COUNT}")
    print(f"Lowe ratio: {LOWE_RATIO}")
    print("Mutual matching: enabled")
    print(f"RANSAC threshold: {RANSAC_THRESHOLD} pixels")
    print(f"Grid: {GRID_COLS} x {GRID_ROWS}")
    print(f"Random seed: {RANDOM_SEED}")

    reference = load_image(REFERENCE)
    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)

    print(f"\nReference: {REFERENCE}")
    print(f"Dimensions: {reference.shape[1]} x {reference.shape[0]}")

    orb = cv2.ORB_create(nfeatures=FEATURE_COUNT)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

    strategies = (
        "random",
        "feature density",
        "feature strength",
    )

    for label, filename in CANDIDATES.items():
        candidate = load_image(filename)
        candidate_gray = cv2.cvtColor(
            candidate,
            cv2.COLOR_BGR2GRAY,
        )

        original_keypoints, _ = orb.detectAndCompute(
            candidate_gray,
            None,
        )

        print("\n" + "=" * 100)
        print(f"{label}: {filename}")
        print("=" * 100)

        print(
            f"Dimensions: {candidate.shape[1]} x {candidate.shape[0]}"
        )
        print(f"Original candidate keypoints: {len(original_keypoints)}")

        print("\nBASELINE - NO OCCLUSION")

        print_result(
            compare_images(
                reference_gray,
                candidate_gray,
                orb,
                matcher,
            )
        )

        for strategy in strategies:
            print("\n" + "-" * 90)
            print(f"STRATEGY: {strategy.upper()}")
            print("-" * 90)

            for percentage in OCCLUSION_LEVELS:
                (
                    occluded,
                    actual_percentage,
                    removed_keypoints,
                    removed_percentage,
                ) = create_occlusion(
                    candidate,
                    original_keypoints,
                    percentage,
                    strategy,
                )

                occluded_gray = cv2.cvtColor(
                    occluded,
                    cv2.COLOR_BGR2GRAY,
                )

                result = compare_images(
                    reference_gray,
                    occluded_gray,
                    orb,
                    matcher,
                )

                print(
                    f"\nRequested coverage: {percentage * 100:5.1f}% | "
                    f"Actual: {actual_percentage:5.2f}%"
                )

                print(
                    f"  Original keypoints obscured: "
                    f"{removed_keypoints}/{len(original_keypoints)} "
                    f"({removed_percentage:.2f}%)"
                )

                print_result(result)


if __name__ == "__main__":
    main()

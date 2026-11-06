
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

OCCLUSION_COLOUR = (0, 0, 0)

FEATURE_COUNT = 2000
LOWE_RATIO = 0.75
RANSAC_THRESHOLD = 5.0

MINIMUM_MATCHES = 8
MINIMUM_INLIERS = 6

MASK_TESTS = [
    ("Circle", "centre"),
    ("Circle", "off-centre"),
    ("Multiple rectangles", "distributed"),
    ("Irregular polygon", "centre"),
    ("Irregular polygon", "off-centre"),
]


def load_image(filename):
    path = MEDIA / filename
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)

    if image is None:
        raise FileNotFoundError(f"Could not load image: {path}")

    return image


def build_mask(width, height, shape, position, scale, target_area):
    """Create a deterministic binary occlusion mask."""

    mask = np.zeros((height, width), dtype=np.uint8)

    if shape == "Circle":
        radius = max(1, round(math.sqrt(target_area / math.pi) * scale))

        centre_x = width // 2

        if position == "centre":
            centre_y = height // 2
        else:
            centre_y = round(height * 0.55)

        cv2.circle(
            mask,
            (centre_x, centre_y),
            radius,
            255,
            thickness=-1,
        )

    elif shape == "Multiple rectangles":
        # Four rectangles distributed across four image regions.
        # Each rectangle receives one quarter of the target area.

        area_each = target_area / 4

        rectangle_width = max(
            1,
            round(math.sqrt(area_each * width / height) * scale),
        )

        rectangle_height = max(
            1,
            round(math.sqrt(area_each * height / width) * scale),
        )

        centres = [
            (width * 0.25, height * 0.25),
            (width * 0.75, height * 0.25),
            (width * 0.25, height * 0.75),
            (width * 0.75, height * 0.75),
        ]

        for centre_x, centre_y in centres:
            x1 = round(centre_x - rectangle_width / 2)
            y1 = round(centre_y - rectangle_height / 2)
            x2 = x1 + rectangle_width - 1
            y2 = y1 + rectangle_height - 1

            cv2.rectangle(
                mask,
                (x1, y1),
                (x2, y2),
                255,
                thickness=-1,
            )

    elif shape == "Irregular polygon":
        # Fixed irregular polygon, scaled around its centre.
        # Coordinates are normalized to image dimensions.

        polygon = np.array(
            [
                [-0.45, -0.25],
                [-0.30, -0.45],
                [-0.05, -0.35],
                [ 0.15, -0.46],
                [ 0.42, -0.30],
                [ 0.35, -0.08],
                [ 0.46,  0.12],
                [ 0.22,  0.42],
                [-0.02,  0.32],
                [-0.25,  0.44],
                [-0.43,  0.20],
                [-0.34, -0.03],
            ],
            dtype=np.float64,
        )

        centre_x = width * 0.5

        if position == "centre":
            centre_y = height * 0.5
        else:
            centre_y = height * 0.52

        points = polygon.copy()
        points[:, 0] = centre_x + points[:, 0] * width * scale
        points[:, 1] = centre_y + points[:, 1] * height * scale

        points = np.round(points).astype(np.int32)

        cv2.fillPoly(mask, [points], 255)

    else:
        raise ValueError(f"Unknown mask shape: {shape}")

    return mask


def create_occlusion(image, percentage, shape, position):
    """Find a mask close to the requested pixel coverage."""

    height, width = image.shape[:2]
    target_area = round(width * height * percentage)

    best_mask = None
    best_difference = float("inf")

    low = 0.0
    high = 1.15

    # Binary search for a scale producing the requested coverage.
    for _ in range(45):
        scale = (low + high) / 2

        mask = build_mask(
            width,
            height,
            shape,
            position,
            scale,
            target_area,
        )

        actual_area = int(np.count_nonzero(mask))
        difference = abs(actual_area - target_area)

        if difference < best_difference:
            best_difference = difference
            best_mask = mask.copy()

        if actual_area < target_area:
            low = scale
        else:
            high = scale

    if best_mask is None:
        raise RuntimeError("Could not generate occlusion mask")

    result = image.copy()
    result[best_mask > 0] = OCCLUSION_COLOUR

    actual_percentage = (
        np.count_nonzero(best_mask) / (width * height) * 100
    )

    return result, actual_percentage


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

    inliers = int(inlier_mask.sum())

    result["inliers"] = inliers
    result["ratio"] = inliers / len(matches) * 100
    if inliers < MINIMUM_INLIERS:
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
    print("EXPERIMENT 23 - IRREGULAR OCCLUSION RESISTANCE")
    print("=" * 100)

    print(f"OpenCV version: {cv2.__version__}")
    print(f"ORB features: {FEATURE_COUNT}")
    print(f"Lowe ratio: {LOWE_RATIO}")
    print("Mutual matching: enabled")
    print(f"RANSAC threshold: {RANSAC_THRESHOLD} pixels")

    reference = load_image(REFERENCE)
    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)

    print(f"\nReference: {REFERENCE}")
    print(f"Dimensions: {reference.shape[1]} x {reference.shape[0]}")

    orb = cv2.ORB_create(nfeatures=FEATURE_COUNT)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

    for label, filename in CANDIDATES.items():
        candidate = load_image(filename)

        print("\n" + "=" * 100)
        print(f"{label}: {filename}")
        print("=" * 100)

        print(
            f"Candidate dimensions: "
            f"{candidate.shape[1]} x {candidate.shape[0]}"
        )

        # Unobstructed baseline.
        baseline_gray = cv2.cvtColor(
            candidate,
            cv2.COLOR_BGR2GRAY,
        )

        print("\nBASELINE - NO OCCLUSION")
        print_result(
            compare_images(
                reference_gray,
                baseline_gray,
                orb,
                matcher,
            )
        )

        # Test all mask shapes and coverage levels.
        for shape, position in MASK_TESTS:
            print("\n" + "-" * 90)
            print(f"MASK: {shape} | POSITION: {position}")
            print("-" * 90)

            for percentage in OCCLUSION_LEVELS:
                occluded, actual_percentage = create_occlusion(
                    candidate,
                    percentage,
                    shape,
                    position,
                )

                candidate_gray = cv2.cvtColor(
                    occluded,
                    cv2.COLOR_BGR2GRAY,
                )

                result = compare_images(
                    reference_gray,
                    candidate_gray,
                    orb,
                    matcher,
                )

                print(
                    f"\nRequested: {percentage * 100:5.1f}% | "
                    f"Actual: {actual_percentage:5.2f}%"
                )

                print_result(result)


if __name__ == "__main__":
    main()

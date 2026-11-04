from pathlib import Path

import cv2
import numpy as np
import math


ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "TestMedia"

REFERENCE = "photo_original.jpg"

CANDIDATES = {
    "Positive control": "photo_exact_copy.jpg",
    "Taxi control 1": "2022-12-27 21.34.20.jpg",
    "Taxi control 2": "2022-12-27 21.34.20-1.jpg",
}

OCCLUSION_LEVELS = [0.00, 0.10, 0.20, 0.30, 0.40, 0.50]

OCCLUSION_COLOUR = (0, 0, 0)

FEATURE_COUNT = 2000
LOWE_RATIO = 0.75
RANSAC_THRESHOLD = 5.0


def load_image(filename):
    path = MEDIA / filename
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)

    if image is None:
        raise FileNotFoundError(f"Could not load image: {path}")

    return image


def apply_occlusion(image, percentage, position):
    """Hide a specified image-area percentage with a solid rectangle."""
    if percentage == 0:
        return image.copy(), 0.0

    height, width = image.shape[:2]
    target_area = round(width * height * percentage)

    rectangle_width = round(width * np.sqrt(percentage))
    rectangle_width = max(1, min(width, rectangle_width))

    rectangle_height = round(target_area / rectangle_width)
    rectangle_height = max(1, min(height, rectangle_height))

    if position == "centre":
        x1 = (width - rectangle_width) // 2
        y1 = (height - rectangle_height) // 2

    elif position == "edge":
        x1 = width - rectangle_width
        y1 = (height - rectangle_height) // 2

    else:
        raise ValueError(f"Unknown occlusion position: {position}")

    x2 = x1 + rectangle_width
    y2 = y1 + rectangle_height

    result = image.copy()
    result[y1:y2, x1:x2] = OCCLUSION_COLOUR

    actual_percentage = (
        rectangle_width * rectangle_height / (width * height) * 100
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

    if len(matches) < 3:
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

    result["scale"] = math.hypot(
        matrix[0, 0],
        matrix[1, 0],
    )

    result["rotation"] = math.degrees(
        math.atan2(matrix[1, 0], matrix[0, 0])
    )

    return result


def main():
    print("=" * 100)
    print("EXPERIMENT 22 - OCCLUSION RESISTANCE")
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

        for percentage in OCCLUSION_LEVELS:
            positions = ("none",) if percentage == 0 else ("centre", "edge")

            for position in positions:
                if position == "none":
                    occluded = candidate.copy()
                    actual_percentage = 0.0
                else:
                    occluded, actual_percentage = apply_occlusion(
                        candidate,
                        percentage,
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
                    f"\nOcclusion: {percentage * 100:5.1f}% | "
                    f"Actual: {actual_percentage:5.2f}% | "
                    f"Position: {position}"
                )

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
                    print(
                        f"  Estimated rotation: "
                        f"{result['rotation']:.2f} degrees"
                    )
                else:
                    print("  Estimated transformation: unavailable")


if __name__ == "__main__":
    main()
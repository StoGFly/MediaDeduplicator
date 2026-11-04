
from pathlib import Path
import math

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "TestMedia"

REFERENCE = "photo_original.jpg"

CANDIDATES = {
    "Positive control": "photo_exact_copy.jpg",
    "Taxi control 1": "2022-12-27 21.34.20.jpg",
    "Taxi control 2": "2022-12-27 21.34.20-1.jpg",
}

TRANSFORMS = [
    (30, 0.50),
    (45, 1.50),
    (90, 0.75),
    (180, 2.00),
]

FEATURE_COUNT = 2000
LOWE_RATIO = 0.75
RANSAC_THRESHOLD = 5.0


def load_image(filename):
    path = MEDIA / filename
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)

    if image is None:
        raise FileNotFoundError(f"Could not load image: {path}")

    return image


def rotate_expand(image, angle):
    """Rotate an image while expanding the canvas to retain the full image."""
    height, width = image.shape[:2]
    centre = (width / 2, height / 2)

    matrix = cv2.getRotationMatrix2D(centre, angle, 1.0)

    cos_angle = abs(matrix[0, 0])
    sin_angle = abs(matrix[0, 1])

    new_width = int(math.ceil(height * sin_angle + width * cos_angle))
    new_height = int(math.ceil(height * cos_angle + width * sin_angle))

    matrix[0, 2] += new_width / 2 - centre[0]
    matrix[1, 2] += new_height / 2 - centre[1]

    return cv2.warpAffine(
        image,
        matrix,
        (new_width, new_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )


def transform_image(image, angle, scale):
    rotated = rotate_expand(image, angle)

    height, width = rotated.shape[:2]
    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))

    interpolation = (
        cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    )

    return cv2.resize(
        rotated,
        (new_width, new_height),
        interpolation=interpolation,
    )


def mutual_ratio_matches(descriptors_a, descriptors_b, matcher):
    """Lowe-ratio filter in both directions, retaining mutual pairs."""
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

    mutual = [
        match
        for match in forward
        if (match.trainIdx, match.queryIdx) in reverse_pairs
    ]

    return mutual


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

    # Transform candidate coordinates into reference coordinates.
    source_points = np.float32([
        candidate_keypoints[m.trainIdx].pt for m in matches
    ]).reshape(-1, 1, 2)

    destination_points = np.float32([
        reference_keypoints[m.queryIdx].pt for m in matches
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
    print("=" * 105)
    print("EXPERIMENT 21 - COMBINED ROTATION AND SCALING")
    print("=" * 105)
    print(f"OpenCV version: {cv2.__version__}")
    print(f"ORB features: {FEATURE_COUNT}")
    print(f"Lowe ratio: {LOWE_RATIO}")
    print(f"Mutual matching: enabled")
    print(f"RANSAC threshold: {RANSAC_THRESHOLD} pixels")

    reference = load_image(REFERENCE)
    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)

    print(f"\nReference: {REFERENCE}")
    print(f"Reference dimensions: {reference.shape[1]} x {reference.shape[0]}")

    orb = cv2.ORB_create(nfeatures=FEATURE_COUNT)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

    for label, filename in CANDIDATES.items():
        original_candidate = load_image(filename)

        print("\n" + "=" * 105)
        print(f"{label}: {filename}")
        print("=" * 105)

        for angle, scale in TRANSFORMS:
            transformed = transform_image(
                original_candidate,
                angle,
                scale,
            )

            candidate_gray = cv2.cvtColor(
                transformed,
                cv2.COLOR_BGR2GRAY,
            )

            result = compare_images(
                reference_gray,
                candidate_gray,
                orb,
                matcher,
            )

            print(
                f"\nRotation {angle:3d} degrees | "
                f"Scale {scale:.2f}x | "
                f"Dimensions {transformed.shape[1]}x{transformed.shape[0]}"
            )

            print(
                f"  Keypoints: reference={result['reference_keypoints']}, "
                f"candidate={result['candidate_keypoints']}"
            )

            print(
                f"  Mutual matches: {result['mutual']}"
            )

            print(
                f"  RANSAC inliers: {result['inliers']} "
                f"({result['ratio']:.2f}%)"
            )

            if result["scale"] is not None:
                print(
                    f"  Estimated scale: {result['scale']:.5f}"
                )
                print(
                    f"  Estimated rotation: {result['rotation']:.2f} degrees"
                )
            else:
                print("  Estimated transformation: unavailable")


if __name__ == "__main__":
    main()

"""ORB feature matching and geometric diagnostics for benchmarks."""

import math
from pathlib import Path

import cv2
import numpy as np

from benchmarks.image_loader import load_image


FEATURE_COUNT = 2000
LOWE_RATIO = 0.75
RANSAC_THRESHOLD = 5.0
RANSAC_MAX_ITERATIONS = 2000
RANSAC_CONFIDENCE = 0.99
RANSAC_REFINE_ITERATIONS = 10


def _ratio_matches(descriptors_a, descriptors_b, matcher):
    """Return forward Lowe-ratio matches."""

    raw_matches = matcher.knnMatch(
        descriptors_a,
        descriptors_b,
        k=2,
    )

    return [
        pair[0]
        for pair in raw_matches
        if len(pair) == 2
        and pair[0].distance < LOWE_RATIO * pair[1].distance
    ]


def _mutual_matches(forward, descriptors_a, descriptors_b, matcher):
    """Retain forward matches also passing the reverse ratio test."""

    reverse = _ratio_matches(
        descriptors_b,
        descriptors_a,
        matcher,
    )

    reverse_pairs = {
        (match.trainIdx, match.queryIdx)
        for match in reverse
    }

    return [
        match
        for match in forward
        if (match.queryIdx, match.trainIdx) in reverse_pairs
    ]


def _convex_hull_coverage(points, width, height):
    """Calculate convex hull area as a percentage of image area."""

    if len(points) < 3:
        return 0.0

    hull = cv2.convexHull(
        np.asarray(points, dtype=np.float32).reshape(-1, 1, 2)
    )

    hull_area = cv2.contourArea(hull)
    image_area = width * height

    if image_area <= 0:
        return 0.0

    return float(hull_area / image_area * 100.0)


def compare_orb(path_a: str | Path, path_b: str | Path) -> dict:
    """Compare two images using the Experiment 21 ORB pipeline."""

    image_a = load_image(path_a)
    image_b = load_image(path_b)

    orb = cv2.ORB_create(nfeatures=FEATURE_COUNT)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

    keypoints_a, descriptors_a = orb.detectAndCompute(
        image_a.gray,
        None,
    )

    keypoints_b, descriptors_b = orb.detectAndCompute(
        image_b.gray,
        None,
    )

    result = {
        "status": "ok",
        "reference_keypoints": len(keypoints_a),
        "candidate_keypoints": len(keypoints_b),
        "forward_matches": 0,
        "mutual_matches": 0,
        "inliers": 0,
        "inlier_percent": 0.0,
        "reference_coverage_percent": 0.0,
        "candidate_coverage_percent": 0.0,
        "scale": None,
        "rotation_degrees": None,
        "transformation_valid": False,
        "geometry_supported": False,
        "geometry_status": "not_estimated",
    }

    if descriptors_a is None or descriptors_b is None:
        return result

    forward = _ratio_matches(
        descriptors_a,
        descriptors_b,
        matcher,
    )

    result["forward_matches"] = len(forward)

    mutual = _mutual_matches(
        forward,
        descriptors_a,
        descriptors_b,
        matcher,
    )

    result["mutual_matches"] = len(mutual)

    if len(mutual) < 3:
        result["geometry_status"] = "insufficient_matches"
        return result

    # Transform candidate coordinates into reference coordinates.
    source_points = np.float32([
        keypoints_b[match.trainIdx].pt
        for match in mutual
    ]).reshape(-1, 1, 2)

    destination_points = np.float32([
        keypoints_a[match.queryIdx].pt
        for match in mutual
    ]).reshape(-1, 1, 2)

    matrix, inlier_mask = cv2.estimateAffinePartial2D(
        source_points,
        destination_points,
        method=cv2.RANSAC,
        ransacReprojThreshold=RANSAC_THRESHOLD,
        maxIters=RANSAC_MAX_ITERATIONS,
        confidence=RANSAC_CONFIDENCE,
        refineIters=RANSAC_REFINE_ITERATIONS,
    )

    if matrix is None or inlier_mask is None:
        result["geometry_status"] = "estimation_failed"
        return result

    inlier_mask = inlier_mask.ravel().astype(bool)
    inlier_count = int(inlier_mask.sum())

    result["inliers"] = inlier_count
    result["geometry_supported"] = inlier_count >= 3
    result["geometry_status"] = (
        "estimated"
        if result["geometry_supported"]
        else "insufficient_inliers"
    )
    result["inlier_percent"] = (
        inlier_count / len(mutual) * 100.0
    )

    inlier_source = source_points.reshape(-1, 2)[inlier_mask]
    inlier_destination = destination_points.reshape(-1, 2)[inlier_mask]

    result["candidate_coverage_percent"] = _convex_hull_coverage(
        inlier_source,
        image_b.width,
        image_b.height,
    )

    result["reference_coverage_percent"] = _convex_hull_coverage(
        inlier_destination,
        image_a.width,
        image_a.height,
    )

    result["scale"] = float(math.hypot(
        matrix[0, 0],
        matrix[1, 0],
    ))

    result["rotation_degrees"] = float(math.degrees(
        math.atan2(matrix[1, 0], matrix[0, 0])
    ))

    result["transformation_valid"] = bool(
        np.isfinite(matrix).all()
        and result["scale"] > 0
    )

    return result
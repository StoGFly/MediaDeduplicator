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


def _occupied_grid_cells(points, image, grid_size):
    """Count cells containing a match in a grid over the full image."""
    cell_size = np.array([image.width, image.height]) / grid_size
    cells = (points.reshape(-1, 2) / cell_size).astype(int)
    return len(np.unique(cells, axis=0))


def _overlap_diagnostics(matrix, reference, candidate, inliers):
    """Measure footprint overlap and inlier hull coverage in reference coordinates."""
    reference_bounds = np.float32([
        [0, 0], [reference.width, 0],
        [reference.width, reference.height], [0, reference.height],
    ])
    candidate_bounds = np.float32([
        [0, 0], [candidate.width, 0],
        [candidate.width, candidate.height], [0, candidate.height],
    ])
    footprint = cv2.transform(candidate_bounds.reshape(-1, 1, 2), matrix)
    overlap_area, overlap = cv2.intersectConvexConvex(reference_bounds, footprint)
    footprint_area = cv2.contourArea(footprint)
    if overlap_area <= 0 or footprint_area <= 0:
        return {}

    covered_area = 0.0
    if len(inliers) >= 3:
        hull = cv2.convexHull(inliers)
        if cv2.contourArea(hull) > 0:
            covered_area, _ = cv2.intersectConvexConvex(overlap, hull)

    return {
        "reference_overlap_percent": min(100.0, 100 * overlap_area / (reference.width * reference.height)),
        "candidate_overlap_percent": min(100.0, 100 * overlap_area / footprint_area),
        "overlap_inlier_hull_percent": max(0.0, min(100.0, 100 * covered_area / overlap_area)),
    }


def compare_orb(
    path_a: str | Path,
    path_b: str | Path,
    *,
    diagnostic_grid_size: int | None = None,
    measure_overlap: bool = False,
) -> dict:
    """Compare images and optionally include spatial diagnostics for research."""
    if diagnostic_grid_size is not None and diagnostic_grid_size < 1:
        raise ValueError("Diagnostic grid size must be positive.")

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

    if diagnostic_grid_size is not None:
        result.update(
            reference_mutual_coverage_percent=0.0,
            candidate_mutual_coverage_percent=0.0,
            reference_mutual_cells=0,
            candidate_mutual_cells=0,
            reference_inlier_cells=0,
            candidate_inlier_cells=0,
        )

    if measure_overlap:
        result.update(
            reference_overlap_percent=0.0,
            candidate_overlap_percent=0.0,
            overlap_inlier_hull_percent=None,
        )

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

    # Transform candidate coordinates into reference coordinates.
    source_points = np.float32([
        keypoints_b[match.trainIdx].pt
        for match in mutual
    ]).reshape(-1, 1, 2)

    destination_points = np.float32([
        keypoints_a[match.queryIdx].pt
        for match in mutual
    ]).reshape(-1, 1, 2)

    if diagnostic_grid_size is not None:
        for side, points, image in (
            ("reference", destination_points, image_a),
            ("candidate", source_points, image_b),
        ):
            result[f"{side}_mutual_coverage_percent"] = _convex_hull_coverage(
                points, image.width, image.height
            )
            result[f"{side}_mutual_cells"] = _occupied_grid_cells(
                points, image, diagnostic_grid_size
            )

    if len(mutual) < 3:
        result["geometry_status"] = "insufficient_matches"
        return result

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

    if diagnostic_grid_size is not None:
        result["reference_inlier_cells"] = _occupied_grid_cells(
            inlier_destination, image_a, diagnostic_grid_size
        )
        result["candidate_inlier_cells"] = _occupied_grid_cells(
            inlier_source, image_b, diagnostic_grid_size
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
    if measure_overlap and result["transformation_valid"]:
        result.update(_overlap_diagnostics(
            matrix, image_a, image_b, inlier_destination
        ))

    return result
# ORB Research Archive — MediaDeduplicator

Last updated: 2026-11-04

Status: Experimental research only — not integrated into production code.

## 1. Research objective

Investigate whether OpenCV ORB (Oriented FAST and Rotated BRIEF) feature detection and matching can identify visually related photographs despite:

- Cropping.
- Resizing and scaling.
- Rotation.
- Brightness and image-quality differences.
- Noise and blur.
- Different image formats and resolutions.

The objective is to establish whether ORB can complement perceptual hashing (pHash/dHash) and SSIM in MediaDeduplicator.

ORB is particularly interesting because it can identify corresponding local image features and estimate geometric transformations between photographs.

This research is exploratory. The current sample set is small and does not establish production-grade accuracy.

## 2. Test environment

- Operating system: Windows 11.
- Python: 3.12.
- OpenCV: 5.0.0.
- Project: `F:\MediaDeduplicator`.
- Test directory: `F:\MediaDeduplicator\TestMedia`.

### Test images

| Filename | Description |
|---|---|
| `photo_original.jpg` | Original photograph |
| `photo_exact_copy.jpg` | Close copy/variant of original |
| `photo_original.png` | Visually related PNG with a different orientation and resolution |
| `2022-12-27 21.34.20-1.jpg` | Unrelated taxi photograph |
| `2022-12-27 21.34.20.jpg` | Second unrelated taxi photograph |
| `contact_sheet.jpg` | Visual reference montage; exclude from comparisons |

All actual photographs have different SHA-256 hashes.

The original JPEG has EXIF orientation 6:
- Stored dimensions: 3264 × 2448.
- Display dimensions: 2448 × 3264.

The PNG has orientation 1 and dimensions 1024 × 768. It depicts the same visual content rotated 90° clockwise relative to the original's stored pixel orientation.

The two taxi photographs are negative controls: they depict a similar general subject but are different photographs.

## 3. Baseline ORB configuration

The provisional baseline used in the experiments:

| Parameter | Setting |
|---|---:|
| ORB feature count | 2,000 |
| Lowe ratio threshold | 0.75 |
| Descriptor matching | Hamming distance |
| Matching | Mutual matching where specified |
| Geometric model | Partial affine transformation |
| RANSAC reprojection threshold | 5 pixels |

Relevant OpenCV functions:

- `cv2.ORB_create`
- `cv2.BFMatcher`
- `cv2.findHomography`
- `cv2.estimateAffinePartial2D`

Not every experiment used mutual matching. Where it was not enabled, results are identified as forward ratio matches.

### Terminology

- **Keypoints:** Features detected in an image.
- **Forward ratio matches:** Descriptor matches surviving Lowe's ratio test.
- **Mutual matches:** Correspondences that agree in both matching directions.
- **Inliers:** Correspondences accepted by the geometric transformation model and RANSAC.
- **Inlier ratio:** Inliers divided by the relevant match count.
- **Scale:** Estimated relative image scale.
- **Rotation:** Estimated relative image rotation.

Important: A high inlier ratio by itself does not prove a genuine match. Very small numbers of correspondences can produce misleadingly high ratios.

## 4. Experiment results

### Experiment 01 — Centered cropping and negative control

Configuration:
- ORB: 2,000 features.
- Lowe ratio: 0.75.
- Homography with RANSAC, 5-pixel threshold.

Centered cropping removes the same percentage from each edge.

| Crop removed per edge | Matches | Inliers |
|---|---:|---:|
| 10% | 504 | 490 |
| 20% | 164 | 152 |
| 30% | 65 | 53 |
| Unrelated taxi | 26 | 7 |

Findings:
- Genuine image matching survived significant cropping.
- Match counts declined as more image content was removed.
- The unrelated taxi photograph produced substantially weaker geometric evidence.

### Experiment 02 — Original compared against all test images

| Comparison | Matches | Inliers |
|---|---:|---:|
| Taxi photograph 1 | 19 | 6 |
| Taxi photograph 2 | 26 | 7 |
| Exact-copy variant | 437 | 356 |
| Related PNG | 246 | 214 |

Findings:
- Both genuine comparisons produced substantially more inliers than the unrelated photographs.
- ORB successfully matched the related PNG despite differences in format, dimensions and orientation.

### Experiment 03 — Asymmetrical cropping

Different portions of the original image were removed.

| Crop | Matches | Inliers |
|---|---:|---:|
| Left 30% | 1,045 | 1,030 |
| Right 30% | 1,128 | 1,120 |
| Top 30% | 479 | 474 |
| Bottom 30% | 1,594 | 1,588 |
| Uneven crop | 393 | 379 |
| Left 40% | 924 | 915 |
| Top 40% | 425 | 413 |

Findings:
- ORB handled asymmetrical cropping very well.
- The number of available features depends heavily on which image region remains.
- Cropping percentage alone cannot predict matching difficulty.

### Experiment 04 — Aggressive cropping

| Crop | Matches | Inliers |
|---|---:|---:|
| Left 50% | 896 | 886 |
| Left 60% | 850 | 840 |
| Left 70% | 780 | 768 |
| Centre 30% retained | 43 | 34 |
| Centre 20% retained | 26 | 12 |
| Unrelated taxi | 26 | 7 |

Findings:
- Even a relatively small retained portion can contain many distinctive features.
- Central crops behaved differently because of the distribution of visual detail.
- Very small retained regions require additional validation.

### Experiment 05 — Spatial distribution

Investigated where matching features were located.

| Crop | Inliers | Original convex hull coverage | Grid cells occupied |
|---|---:|---:|---:|
| Left 30% | 1,030 | 54.75% | 10/16 |
| Left 50% | 886 | 33.90% | 7/16 |
| Left 70% | 768 | 16.72% | 6/16 |
| Centre 30% | 34 | 0.30% | 2/16 |
| Centre 20% | 12 | 8.37% | 3/16 |

Findings:
- Spatial distribution adds useful information beyond raw match count.
- Matching features can be concentrated in a small part of an image.
- Convex hull coverage can be misleading when only a few points are present.

### Experiment 06 — Geometric diagnostics

Examined spatial spans and degeneracy.

Centre 30%:
- 34 inliers.
- X span: 20.7%.
- Y span: 2.1%.
- Features clustered in a narrow horizontal strip.

Centre 20%:
- 12 inliers.
- Source X span: 72.7%.
- Source Y span: 66.3%.
- Target points clustered into a very small region.

Findings:
- A seemingly broad source distribution does not guarantee a valid transformation.
- Source and target distributions must both be examined.
- Reprojection error alone is insufficient.

### Experiment 07 — Homography corner validation

Mapped image corners through the estimated homography.

Centre 30%:
- Crop corners mapped sensibly.
- Transformation remained physically plausible.

Centre 20%:
- All four original image corners collapsed close to (320, 63).
- Transformation was degenerate despite 12 RANSAC inliers.

Finding:

A transformation can have accepted inliers and still be physically meaningless. Validate its mapped geometry.

### Experiment 08 — Physical transformation validity

Examined whether matched points and expected crop boundaries were consistent.

Centre 30%:
- All 34 inliers were inside the expected crop.
- Crop corners mapped close to expected boundaries.
- Affine scale was close to 1.

Centre 20%:
- Only 8 of 12 source points were inside the expected crop.
- Target points were clustered.
- Affine transformation was degenerate.

Finding:

A credible image match needs plausible geometric behaviour, not just a RANSAC result.

### Experiment 09 — Partial affine transformation

Used `cv2.estimateAffinePartial2D`.

| Comparison | Inliers / Matches | Inlier ratio | Estimated scale |
|---|---:|---:|---:|
| Left 30% | 1,030 / 1,045 | 98.56% | ~1.0 |
| Left 50% | 886 / 896 | 98.88% | ~1.0 |
| Left 70% | 768 / 780 | 98.46% | ~1.0 |
| Centre 30% | 35 / 43 | 81.40% | ~1.0 |
| Centre 20% | 11 / 26 | 42.31% | 0.00022 |
| Exact-copy variant | 317 / 437 | 72.54% | 0.99833 |
| Related PNG | 214 / 246 | 86.99% | 0.31372 |

Unrelated taxi controls:
- Taxi 1: 4/19 inliers.
- Taxi 2: 5/26 inliers.

Related PNG rotation estimate: approximately -90°.

Findings:
- Partial affine estimation handles translation, rotation and uniform scaling.
- It is more constrained than a general homography.
- Degenerate solutions still need to be rejected.
- The very small estimated scale for centre 20% is a clear warning.

### Experiment 10 — Lowe ratio threshold

Compared thresholds:
- 0.65
- 0.70
- 0.75
- 0.80

Findings:
- Stricter thresholds remove ambiguous matches but can discard useful correspondences.
- Looser thresholds increase matches but may introduce false correspondences.
- 0.75 was selected as a provisional compromise.

This is not a universal optimum. It should remain configurable in an eventual Advanced GUI.

### Experiment 11 — Mutual matching

Enabled mutual matching with Lowe ratio 0.75.

| Comparison | Forward matches | Mutual matches | Inliers | Inlier ratio |
|---|---:|---:|---:|---:|
| Left 70% crop | 780 | 763 | 762 | 99.87% |
| Centre 30% crop | 43 | 30 | 30 | 100% |
| Centre 20% crop | 26 | 9 | 8 | 88.89% |
| Exact-copy variant | 437 | 320 | 258 | 80.62% |
| Related PNG | 246 | 134 | 132 | 98.51% |
| Taxi 1 | 19 | 4 | 2 | 50% |
| Taxi 2 | 26 | 5 | 2 | 40% |

Findings:
- Mutual matching removes many ambiguous correspondences.
- Genuine comparisons retain substantial geometric evidence.
- A negative control can still show a high inlier ratio when the absolute count is tiny.

### Experiment 12 — Mutual-match spatial coverage

| Comparison | Mutual matches | Inliers | Source hull coverage | Target hull coverage |
|---|---:|---:|---:|---:|
| Left 70% | 763 | 762 | 16.72% | 55.75% |
| Centre 30% | 30 | 30 | 0.30% | 3.29% |
| Centre 20% | 9 | 8 | ~0% | ~0% |
| Exact-copy variant | 320 | 258 | 27.64% | 27.57% |
| Related PNG | 134 | 132 | 71.93% | 71.90% |

Taxi controls:
- Only 2 inliers each.

Findings:
- Genuine comparisons can have very different spatial coverage.
- Small crops may legitimately have low coverage.
- Coverage must be interpreted alongside absolute inlier count, expected overlap and geometric plausibility.

### Experiment 13 — Affine corner overlap

Examined how the estimated affine transformation maps image corners.

| Comparison | Source overlap | Target coverage |
|---|---:|---:|
| Left 70% crop | 29.95% | 100% |
| Centre 30% crop | 8.98% | 100% |
| Centre 20% crop | 4.43% | 100% |
| Exact-copy variant | 99.23% | 98.91% |
| Related PNG | 99.83% | 99.99% |
| Taxi 1 | 23.83% | 92.71% |
| Taxi 2 | 3.03% | 84.54% |

Finding:

Overlap alone is not reliable. Unrelated images can sometimes produce plausible-looking overlap values.

### Experiment 14 — RANSAC reprojection threshold

Tested:
- 2 pixels.
- 3 pixels.
- 5 pixels.
- 8 pixels.
- 10 pixels.

Findings:
- Genuine crops remained reasonably stable.
- Exact-copy inlier counts increased with more permissive thresholds.
- Related PNG results remained stable.
- Taxi controls never exceeded two inliers.
- Median reprojection error can be zero for a negative control with only two points because two correspondences can fit an affine transformation exactly.

Provisional setting: 5 pixels.

Important: Require a meaningful minimum number of correspondences. Do not trust a tiny set simply because its reprojection error is low.

### Experiment 15 — Resolution scaling

Resized images to different percentages before matching.

Exact-copy variant:

| Resolution | Mutual matches | Inliers |
|---|---:|---:|
| 100% | 320 | 258 |
| 75% | 378 | 279 |
| 50% | 452 | 385 |
| 25% | 655 | 625 |
| 10% | 234 | 227 |

Related PNG:

| Resolution | Mutual matches | Inliers |
|---|---:|---:|
| 100% | 134 | 132 |
| 75% | 124 | 121 |
| 50% | 103 | 99 |
| 25% | 117 | 114 |
| 10% | 3 | Insufficient |

Findings:
- Downscaling can improve matching by suppressing fine details and small differences.
- The best resolution depends on the image pair.
- Excessive downscaling can remove too many useful features.
- A two-stage strategy (initial downscale followed by a higher-resolution retry) may be worth investigating.

### Experiment 16 — ORB feature count

Tested feature counts:
- 500.
- 1,000.
- 2,000.
- 4,000.
- 8,000.

Exact-copy variant:

| Features | Mutual matches | Inliers | Inlier ratio |
|---|---:|---:|---:|
| 500 | 98 | 88 | 89.80% |
| 1,000 | 166 | 146 | 87.95% |
| 2,000 | 320 | 258 | 80.62% |
| 4,000 | 543 | 335 | 61.69% |
| 8,000 | 1,097 | 734 | 66.91% |

Related PNG:

| Features | Mutual matches | Inliers |
|---|---:|---:|
| 500 | 39 | 38 |
| 1,000 | 73 | 71 |
| 2,000 | 134 | 132 |
| 4,000 | 250 | 248 |
| 8,000 | 471 | 464 |

Findings:
- Increasing feature count increases the number of correspondences.
- More features do not necessarily increase the inlier ratio.
- More features also mean greater computational cost.
- Feature count should be user-adjustable in Advanced mode.

### Experiment 17 — Feature-count negative controls

Repeated feature-count tests with both unrelated taxi photographs.

Findings:
- Taxi controls remained weak.
- Maximum observed geometric inliers: 2.
- Genuine exact-copy and PNG matches increased substantially with feature count.

Interpretation:

Absolute geometric inlier count is more informative than inlier ratio alone for the current sample set.

### Experiment 18 — Noise and blur resistance: positive control

Compared the original against the exact-copy variant.

Baseline:
- 320 mutual matches.
- 258 inliers.
- 80.62% inlier ratio.

#### Gaussian noise

| Noise sigma | Mutual matches | Inliers | Inlier ratio |
|---|---:|---:|---:|
| 5 | 300 | 226 | 75.33% |
| 10 | 283 | 217 | 76.68% |
| 20 | 209 | 168 | 80.38% |
| 30 | 166 | 128 | 77.11% |
| 50 | 107 | 88 | 82.24% |

#### Gaussian blur

| Blur kernel | Mutual matches | Inliers | Inlier ratio |
|---|---:|---:|---:|
| 3×3 | 306 | 222 | 72.55% |
| 5×5 | 292 | 223 | 76.37% |
| 9×9 | 247 | 186 | 75.30% |
| 15×15 | 140 | 97 | 69.29% |

Findings:
- Genuine matching survived considerable noise and blur.
- Match counts declined as degradation increased.
- Inlier ratios remained relatively strong.
- The blur 15×15 target had 1,557 detected keypoints.

### Experiment 19 — Noise and blur resistance: negative controls

Compared the original against both unrelated taxi photographs.

#### Taxi 1

| Transformation | Mutual matches | Inliers |
|---|---:|---:|
| Baseline | 4 | 2 |
| Noise sigma 5 | 3 | 0 |
| Noise sigma 10 | 4 | 2 |
| Noise sigma 20 | 5 | 2 |
| Noise sigma 30 | 4 | 2 |
| Noise sigma 50 | 2 | 0 |
| Blur 3×3 | 2 | 0 |
| Blur 5×5 | 2 | 0 |
| Blur 9×9 | 7 | 2 |
| Blur 15×15 | 2 | 0 |

#### Taxi 2

| Transformation | Mutual matches | Inliers |
|---|---:|---:|
| Baseline | 5 | 2 |
| Noise sigma 5 | 3 | 0 |
| Noise sigma 10 | 2 | 0 |
| Noise sigma 20 | 0 | 0 |
| Noise sigma 30 | 1 | 0 |
| Noise sigma 50 | 0 | 0 |
| Blur 3×3 | 2 | 0 |
| Blur 5×5 | 1 | 0 |
| Blur 9×9 | 1 | 0 |
| Blur 15×15 | 3 | 0 |

Findings:
- No convincing false positives were observed.
- Maximum mutual matches: 7.
- Maximum geometric inliers: 2.
- These results reinforce the importance of absolute inlier counts and geometric validation.

Caveat: Two negative-control images are not enough to establish a reliable false-positive rate.

### Experiment 20 — Rotation and scaling resistance

Compared the original against the exact-copy variant.

#### Rotation

| Applied rotation | Mutual matches | Inliers | Inlier ratio | Estimated scale | Estimated rotation |
|---|---:|---:|---:|---:|---:|
| 15° | 237 | 187 | 78.90% | 0.9954 | -14.74° |
| 30° | 245 | 204 | 83.27% | 0.9954 | -29.73° |
| 45° | 237 | 188 | 79.32% | 0.9953 | -44.72° |
| 90° | 325 | 247 | 76.00% | 0.9984 | -89.77° |
| 180° | 320 | 235 | 73.44% | 0.9953 | -179.74° |

#### Scaling

| Applied scale | Mutual matches | Inliers | Inlier ratio | Estimated scale | Estimated rotation |
|---|---:|---:|---:|---:|---:|
| 0.50× | 130 | 115 | 88.46% | 0.5025 | 0.17° |
| 0.75× | 140 | 107 | 76.43% | 0.7490 | 0.18° |
| 1.25× | 241 | 177 | 73.44% | 1.2441 | 0.27° |
| 1.50× | 194 | 150 | 77.32% | 1.4939 | 0.26° |
| 2.00× | 114 | 75 | 65.79% | 1.9917 | 0.29° |

The negative rotation sign reflects the OpenCV coordinate and transformation convention.

#### Negative controls

Taxi 1:
- Baseline: 4 mutual / 2 inliers.
- Rotation 30°: 1 / 0.
- Rotation 90°: 2 / 0.
- Rotation 180°: 1 / 0.
- Scale 0.5×: 1 / 0.
- Scale 1.5×: 7 / 2; estimated scale 0.1538, rotation -39.29°.
- Scale 2×: 4 / 2; estimated scale 3.8246, rotation -5.36°.

Taxi 2:
- Baseline: 5 / 2.
- Rotation 30°: 1 / 0.
- Rotation 90°: 2 / 0.
- Rotation 180°: 5 / 2.
- Scale 0.5×: 2 / 0.
- Scale 1.5×: 3 / 0.
- Scale 2×: 3 / 0.

Findings:
- All ten genuine rotation and scaling tests retained strong geometric evidence.
- Estimated rotation and scale were close to the applied transformations.
- Negative controls remained weak, with at most two inliers.
- ORB shows promising rotation and scale invariance.

Caveat: This is encouraging evidence from a limited test set, not proof of general performance.

## 5. Overall conclusions

The experiments suggest ORB may be a valuable complementary image comparison technique.

Promising capabilities:
- Significant cropping resistance.
- Rotation resistance.
- Scaling resistance.
- Robustness to noise and blur.
- Matching across differing image resolutions and formats.
- Geometric verification of corresponding image regions.

Important limitations and safeguards:
- Match count alone is insufficient.
- Inlier ratio alone is insufficient.
- Two or three inliers are not convincing evidence.
- Homography and affine transformations can be degenerate.
- Spatial distribution must be considered.
- Source and target geometry both matter.
- Estimated scale and rotation should be physically plausible.
- Thresholds need validation against a much larger and more diverse image collection.

A future detector should combine multiple signals rather than rely on a single score.

Potential evidence:
1. Mutual match count.
2. Geometric inlier count.
3. Inlier ratio.
4. Spatial distribution in both images.
5. Transformation plausibility.
6. Estimated scale and rotation.
7. Reprojection error.
8. Expected image overlap.
9. Consistency across resolutions or retries.

No final matching score or acceptance threshold has been established.

## 6. Provisional parameter decisions

These are experimental starting points, not final production defaults.

| Parameter | Provisional value |
|---|---:|
| ORB feature count | 2,000 |
| Lowe ratio | 0.75 |
| Mutual matching | Enabled |
| RANSAC threshold | 5 pixels |

The Advanced GUI should eventually expose:
- Feature count.
- Lowe ratio threshold.
- Mutual matching.
- RANSAC reprojection threshold.
- Resolution/downscaling.
- Potential retry strategies.

Users should be told that changing these affects speed, sensitivity and false-positive risk.

Basic mode should hide technical complexity and use sensible defaults.

## 7. Next experiment

### Experiment 21 — Combined rotation and scaling resistance

Test these combined transformations:

| Test | Rotation | Scale |
|---|---:|---:|
| A | 30° | 0.50× |
| B | 45° | 1.50× |
| C | 90° | 0.75× |
| D | 180° | 2.00× |

Compare each transformed genuine image against the original.

Repeat the same transformations against both unrelated taxi photographs.

Record:
- Detected keypoints.
- Mutual matches.
- Geometric inliers.
- Inlier ratio.
- Estimated scale.
- Estimated rotation.

Where possible, expand the rotation canvas so rotation itself does not unnecessarily crop the image before scaling.

The next research step is to implement this as a temporary PowerShell experiment, inspect the results, and then decide what to test next.

Do not modify production source code as part of this experiment.

## 8. Research status

Experiments completed: 1–20.

Next: Experiment 21.

Production integration: Not started.

Production tests: Not written for ORB.

Final ORB thresholds: Not established.

The current findings should be treated as research evidence and not as guaranteed application behaviour.
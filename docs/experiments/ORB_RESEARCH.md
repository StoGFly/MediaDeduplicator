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

### Experiment 01 - Centered cropping and negative control

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

### Experiment 02 - Original compared against all test images

| Comparison | Matches | Inliers |
|---|---:|---:|
| Taxi photograph 1 | 19 | 6 |
| Taxi photograph 2 | 26 | 7 |
| Exact-copy variant | 437 | 356 |
| Related PNG | 246 | 214 |

Findings:
- Both genuine comparisons produced substantially more inliers than the unrelated photographs.
- ORB successfully matched the related PNG despite differences in format, dimensions and orientation.

### Experiment 03 - Asymmetrical cropping

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

### Experiment 04 - Aggressive cropping

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

### Experiment 05 - Spatial distribution

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

### Experiment 06 - Geometric diagnostics

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


## 7. Recent experiments and next steps

### Experiment 21 - Combined rotation and scaling resistance

Test these combined transformations:

| Test | Rotation | Scale |
|---|---:|---:|
| A | 30 degrees | 0.50x |
| B | 45 degrees | 1.50x |
| C | 90 degrees | 0.75x |
| D | 180 degrees | 2.00x |

The rotation canvas was expanded to retain the full image before scaling.

**Positive control results**

| Rotation | Applied scale | Mutual matches | RANSAC inliers | Inlier ratio | Estimated scale | Estimated rotation |
|---:|---:|---:|---:|---:|---:|---:|
| 30 degrees | 0.50x | 135 | 98 | 72.59% | 2.00350 | 29.82 degrees |
| 45 degrees | 1.50x | 140 | 110 | 78.57% | 0.66965 | 44.74 degrees |
| 90 degrees | 0.75x | 168 | 104 | 61.90% | 1.33846 | 89.83 degrees |
| 180 degrees | 2.00x | 121 | 101 | 83.47% | 0.50076 | 179.82 degrees |

The estimated scales closely matched the reciprocal of the applied scales. Estimated rotations were within approximately 0.3 degrees of the applied rotations.

**Negative controls**

Two unrelated taxi photographs were subjected to the same transformations.

- Taxi control 1 produced at most 4 mutual matches and 3 inliers.
- Taxi control 2 produced at most 4 mutual matches and 2 inliers.

One result had a 75% inlier ratio from only four matches, demonstrating why an inlier percentage cannot be considered independently of absolute match counts.

**Conclusion**

The positive control retained strong geometric matching across all four combined transformations. The two negative controls remained weak.

The results are encouraging but do not establish a general false-positive rate because the negative-control dataset is small.

### Experiment 22 - Occlusion resistance

**Objective:** Measure ORB's ability to recognise an image when part of the candidate image is hidden by a solid obstruction.

The reference was `photo_original.jpg`. The positive control was `photo_exact_copy.jpg`. Two unrelated taxi photographs were used as negative controls.

**Test conditions**

- Occlusion levels: 0%, 10%, 20%, 30%, 40% and 50%.
- Central obstruction: rectangle centred in the image.
- Edge obstruction: rectangle aligned with the right-hand edge.
- Obstruction colour: solid black.
- Rectangle dimensions were calculated to cover the requested percentage of image area.
- ORB configuration: 2,000 features, Lowe ratio 0.75, mutual matching enabled, RANSAC threshold 5 pixels.
- OpenCV version: 5.0.0.

The actual occlusion area was within 0.01 percentage points of the requested percentage.

**Positive control results**

| Occlusion | Position | Mutual matches | RANSAC inliers | Inlier ratio |
|---:|---|---:|---:|---:|
| 0% | None | 320 | 258 | 80.62% |
| 10% | Centre | 312 | 245 | 78.53% |
| 10% | Edge | 314 | 251 | 79.94% |
| 20% | Centre | 312 | 236 | 75.64% |
| 20% | Edge | 314 | 251 | 79.94% |
| 30% | Centre | 302 | 239 | 79.14% |
| 30% | Edge | 308 | 250 | 81.17% |
| 40% | Centre | 281 | 240 | 85.41% |
| 40% | Edge | 294 | 245 | 83.33% |
| 50% | Centre | 229 | 187 | 81.66% |
| 50% | Edge | 285 | 240 | 84.21% |

At 50% occlusion, the genuine image still produced:

- 187 RANSAC inliers with central occlusion.
- 240 RANSAC inliers with edge occlusion.

The estimated scale remained close to 1.0 and the estimated rotation remained close to zero.

The edge obstruction retained more matches than the central obstruction at every tested level. This suggests that, in this particular photograph, the unobstructed right-hand region contains more useful ORB features than the central region.

This is an observation about the test image, not a general rule about edge occlusion.

**Negative control results**

| Control | Mutual matches observed | Maximum RANSAC inliers |
|---|---:|---:|
| Taxi control 1 | 3-6 | 2 |
| Taxi control 2 | 1-4 | 2 |

Some negative-control results had apparently high inlier percentages, but they were based on only one or two inliers. These are not credible geometric matches.

**Conclusion**

ORB demonstrated strong resistance to the tested solid rectangular occlusions, retaining substantial geometric agreement even when half of the candidate image was hidden.

The negative controls remained weak throughout the experiment.

The results support the importance of absolute inlier counts alongside inlier ratios and geometric consistency.

**Limitations**

- Only one genuine photograph was tested.
- Only two unrelated negative photographs were used.
- The obstruction was a solid black rectangle, which introduces artificial boundaries that may themselves generate ORB keypoints.
- Only central and right-edge placements were tested.
- The experiment does not establish a general occlusion tolerance or production threshold.

### Experiment 23 - Irregular occlusion resistance

**Objective:** Investigate whether ORB's occlusion resistance extends beyond large rectangular obstructions.

The experiment tested circular obstructions, multiple smaller rectangles and irregular polygon masks. It used the same reference and positive/negative controls as the earlier occlusion research.

**Test conditions**

- Multiple obstruction shapes and placements.
- Comparable covered-area percentages.
- Solid black synthetic masks.
- ORB configuration: 2,000 features, Lowe ratio 0.75, mutual matching enabled, RANSAC threshold 5 pixels.
- Minimum accepted matching evidence: 8 mutual matches and 6 RANSAC inliers.

The minimum-match and minimum-inlier safeguards prevent transformations based on very small numbers of correspondences from being treated as meaningful results.

**Positive control results**

The exact-copy positive control began with 320 mutual matches and 258 RANSAC inliers (80.62%).

Across the tested irregular masks covering up to 50% of the image:

- Circular masks produced approximately 104-313 mutual matches.
- Multiple-rectangle masks produced approximately 32-313 mutual matches.
- Polygon masks produced approximately 95-313 mutual matches.
- Inlier ratios for accepted transformations generally remained between approximately 74.5% and 87.9%.

The resized PNG positive control began with 134 mutual matches and 111 inliers (82.84%). It also retained accepted geometric matches under the tested irregular masks, although results varied with mask shape and placement.

**Negative controls**

The two unrelated taxi photographs remained weak. Their mutual-match counts generally stayed in the single digits, and the minimum-match and minimum-inlier safeguards prevented unsupported transformations from being accepted.

**Conclusion**

ORB retained substantial geometric evidence under the tested circular, multiple-rectangle and polygon occlusions.

The results extend the earlier rectangular-occlusion findings, but they still represent synthetic obstruction tests on a limited image set.

**Limitations**

- Only a small number of genuine and unrelated images were tested.
- Masks were synthetic and solid black.
- Mask placement and shape affect which features remain available.
- Synthetic masks do not represent all real-world obstructions, such as people, objects, reflections or complex foreground content.
- These results do not establish a general occlusion tolerance or production threshold.

### Experiment 24 - Feature-targeted occlusion

**Objective:** Determine whether occlusion becomes more damaging when it is deliberately placed over feature-rich image regions rather than distributed randomly.

This experiment compared random-area occlusion with masks targeting regions containing high concentrations of ORB features.

**Test conditions**

- Random occlusion at increasing coverage levels.
- Feature-density-targeted occlusion.
- Feature-strength-targeted occlusion.
- ORB configuration: 2,000 features, Lowe ratio 0.75, mutual matching enabled, RANSAC threshold 5 pixels.
- Minimum accepted matching evidence: 8 mutual matches and 6 RANSAC inliers.

**Exact-copy positive control**

The baseline was 320 mutual matches and 258 RANSAC inliers (80.62%).

| Occlusion method | Level | Mutual matches | RANSAC inliers | Inlier ratio |
|---|---:|---:|---:|---:|
| Random area | 10% | 258 | 214 | 82.95% |
| Random area | 20% | 159 | 125 | 78.62% |
| Random area | 50% | 99 | 79 | 79.80% |
| Feature density | 10% | 39 | 20 | 51.28% |
| Feature density | 20% | 3 | Not accepted | - |
| Feature strength | 10% | 46 | 18 | 39.13% |
| Feature strength | 20% | 3 | Not accepted | - |

At 10% feature-density-targeted occlusion, approximately 79.65% of the original keypoints were obscured. At 10% feature-strength-targeted occlusion, approximately 78.45% were obscured.

At 20% targeted occlusion, approximately 97% of the original keypoints were obscured, leaving too few matches to pass the minimum evidence safeguards.

**Resized PNG positive control**

The baseline was 134 mutual matches and 111 RANSAC inliers (82.84%).

| Occlusion method | Level | Mutual matches | RANSAC inliers | Inlier ratio |
|---|---:|---:|---:|---:|
| Random area | 50% | 28 | 26 | 92.86% |
| Feature density | 10% | 23 | 21 | 91.30% |
| Feature density | 20% | 8 | 6 | 75.00% |
| Feature density | 30% | 2 | Not accepted | - |
| Feature strength | 10% | 20 | 19 | 95.00% |
| Feature strength | 20% | 7 | Not accepted | - |

At 20% feature-density-targeted occlusion, approximately 92.10% of the original keypoints were obscured. At 20% feature-strength-targeted occlusion, approximately 91.25% were obscured.

**Negative controls**

The unrelated taxi photographs continued to produce very few mutual matches. No convincing geometric transformations were accepted.

**Conclusion**

Feature-targeted occlusion was substantially more damaging than random occlusion in these tests.

The important variable is not simply the percentage of image area hidden. It is how much useful matching information the obstruction removes.

A relatively small obstruction can remove a large proportion of an image's detectable features if it covers feature-rich regions.

This is deliberately adversarial occlusion. It must not be interpreted as evidence that ordinary 10% real-world occlusion will generally defeat ORB.

**Limitations**

- The feature-targeting method deliberately selects regions to remove useful keypoints.
- The experiments use a limited set of positive and negative images.
- Different images have different feature distributions.
- The results do not establish a universal relationship between occluded area and matching performance.

### Experiment 25 - Spatial concentration audit

**Objective:** Measure how ORB keypoints are distributed across an image and determine whether a relatively small number of image regions contain most detected features.

The exact-copy candidate `photo_exact_copy.jpg` was analysed against the reference `photo_original.jpg`.

**Test conditions**

- Image dimensions: 2448 x 3264.
- ORB feature count: 2,000.
- Spatial grid: 20 x 20.
- Rankings compared: keypoint density, total keypoint response and average keypoint response.

**Results**

| Measurement | Result |
|---|---:|
| Total grid cells | 400 |
| Occupied cells | 103 |
| Empty cells | 297 |
| Empty-cell percentage | 74.25% |
| Maximum keypoints in one cell | 174 |
| Mean keypoints per cell | 5 |
| Median keypoints per cell | 0 |

**Concentration by image area**

| Ranked area | Keypoints captured | Percentage |
|---|---:|---:|
| Top 10% | 1,599 | 79.95% |
| Top 20% | 1,947 | 97.35% |
| Top 30% | 2,000 | 100.00% |

**Ranking overlap**

The overlap between the highest-ranked cells differed depending on the ranking metric.

| Ranked cells | Density vs total response | Density vs average response | Total vs average response |
|---|---:|---:|---:|
| Top 10% | 85.0% | 65.0% | 80.0% |
| Top 20% | 97.5% | 88.8% | 91.2% |
| Top 30% | 100.0% | 100.0% | 100.0% |

**Conclusion**

The detected keypoints were strongly concentrated in a relatively small portion of the image.

The top 10% of grid cells by density contained approximately 80% of all detected keypoints. The top 20% contained approximately 97%.

Density and average response did not always identify the same important regions. They measure different properties and should not be treated as interchangeable.

This finding supports the feature-targeted occlusion results from Experiment 24.

For image matching, the important question is not only how many keypoints are detected, but also where they are located.

### Experiment 26 - Grid resolution sensitivity

**Objective:** Determine how the choice of spatial grid resolution affects measured keypoint concentration.

Four images were examined:

- `photo_original.jpg`
- `photo_original.png`
- `2022-12-27 21.34.20.jpg`
- `2022-12-27 21.34.20-1.jpg`

Each image was analysed using 2,000 ORB features and grid sizes of 10 x 10, 20 x 20 and 40 x 40.

**Results: occupied and empty cells**

| Grid | Occupied cells across images | Empty cells across images |
|---|---:|---:|
| 10 x 10 | 47-69 of 100 | 31-53 |
| 20 x 20 | 91-130 of 400 | 270-309 |
| 40 x 40 | 159-260 of 1,600 | 1,340-1,441 |

**Concentration by image area**

| Grid | Top 10% of area captures | Top 20% of area captures |
|---|---:|---:|
| 10 x 10 | 52.65-72.55% | 74.25-87.95% |
| 20 x 20 | 67.15-87.45% | 92.60-99.25% |
| 40 x 40 | 90.35-100.00% | 100.00% |

The 40 x 40 results require particular care. There are only 159-260 occupied cells out of 1,600. Selecting the top 160 cells can therefore include almost every occupied cell in some images. This makes the area-based concentration figure less informative at that resolution.

**Concentration by occupied cells**

At 20 x 20 resolution, the top 10% of occupied cells contained 34.00-49.55% of keypoints across the four images. The top 20% contained 49.30-69.05%.

At 40 x 40 resolution, the top 10% of occupied cells contained 31.20-42.35% of keypoints. The top 20% contained 49.30-62.15%.

These measurements provide a different view from concentration by total image area. Empty cells are excluded when ranking occupied cells.

**Ranking metric comparison**

Density and total response generally showed moderate to strong overlap, particularly when larger groups of occupied cells were considered.

Density and average response often showed much lower overlap among the top 10% of occupied cells. For example, at 20 x 20 resolution, density-versus-average-response overlap ranged from approximately 9.1% to 22.2% for three of the four images.

This reinforces the conclusion that average response is not a substitute for keypoint density or total response.

**Conclusion**

Grid resolution has a substantial effect on spatial concentration measurements.

- A 10 x 10 grid provides a coarser view of feature distribution.
- A 20 x 20 grid provides a useful middle-ground research baseline.
- A 40 x 40 grid produces many empty cells and can make area-based concentration figures misleading.

Keep 20 x 20 as the current research baseline, not as a proven universal optimum.

Area-based concentration and occupied-cell concentration should remain separate measurements because they answer different questions.

Most importantly, a future matcher should investigate the spatial distribution of geometrically verified matches in both images, rather than relying only on the distribution of detected keypoints.

## 8. Research status

Experiments completed: 1-26.

Current research focus: Spatial distribution and geometric reliability of ORB matches.

Current experimental safeguards:
- Minimum 8 mutual matches for accepted geometric evaluation.
- Minimum 6 RANSAC inliers.
- Match count and inlier ratio must be considered together.
- Spatial distribution and transformation plausibility require further investigation.

Current research baseline:
- ORB feature count: 2,000.
- Lowe ratio: 0.75.
- Mutual matching: Enabled.
- RANSAC threshold: 5 pixels.
- Spatial diagnostic grid: 20 x 20.

Production integration: Not started.

Production tests: Not written for ORB.

Final ORB thresholds: Not established.

**Next research priorities**

1. Investigate the spatial distribution of matched keypoints and RANSAC inliers in both reference and candidate images.
2. Determine whether matches concentrated in a small image region can produce misleading geometric agreement.
3. Investigate minimum spatial coverage and distribution requirements without rejecting legitimate partial-image matches.
4. Expand positive and negative controls to include more diverse photographs and difficult near-duplicate cases.
5. Validate candidate matching and acceptance rules against a larger labelled dataset.
6. Only after sufficient validation, consider integrating ORB into the application as a complementary matching method.

The current findings are experimental evidence, not guaranteed application behaviour. The test collection is limited, and further validation is required before production thresholds or false-positive claims can be justified.

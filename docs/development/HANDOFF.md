# MediaDeduplicator - Development Handoff

Last updated: 2026-11-06

## 1. Purpose

This document allows development to continue in a fresh ChatGPT conversation without depending on previous conversation history.

The local repository and project documentation are authoritative.

Read `AGENTS.md` and `PROJECT_STATUS.md` first.

## 2. Project location

`F:\MediaDeduplicator`

Windows PowerShell.

Python virtual environment:

`F:\MediaDeduplicator\.venv`

Activate with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 3. Last verified Git checkpoint

The research checkpoint on `main` is [`111a6db`](https://github.com/StoGFly/MediaDeduplicator/commit/111a6db40f2ff115418bfe310d3a8f2c62282a44) (Add benchmark framework and ORB experiments 23-26).

This commit tracks the [benchmark framework](../../benchmarks/), the [curated pair labels](../../benchmarks/data/curated_pair_labels.csv), the [local media manifest builder](../../build_testmedia_manifest.py), and the scripts and notes for ORB experiments 23–26. The framework generates labelled pairs, runs detector comparisons and supports review of difficult negative pairs.

Git ignores `TestMedia/`, root-level `TestMedia_manifest_*.csv` inventories and `benchmarks/results/`. Keep personal media and generated outputs local.

All 58 pytest tests passed on the local checkout of `111a6db` on 2026-11-06. Run standalone research scripts and benchmarks separately when verifying those workflows.

Inspect the current repository state before proceeding. Explicit user approval is required to stage, commit or push.

## 4. Current development phase

The project is investigating ORB feature matching using OpenCV.

This remains research only.

The [ORB benchmark detector](../../benchmarks/orb_detector.py) is experimental. The production scan and pytest suite have no ORB integration.

Research scripts for experiments 21–26 are stored in:

`docs/experiments/`

The research media is stored under:

`F:\MediaDeduplicator\TestMedia`

The contact sheet is for visual reference only and must not be used as an image comparison input.

The detailed research record is:

`docs/experiments/ORB_RESEARCH.md`

## 5. ORB experimental configuration

Current research baseline:

- ORB features: 2,000.
- Lowe ratio: 0.75.
- Mutual matching: enabled.
- RANSAC reprojection threshold: 5 pixels.
- Geometric model: `cv2.estimateAffinePartial2D`.
- Descriptor matching: Hamming distance.
- OpenCV version observed: 5.0.0.
- Spatial diagnostic grid: 20 x 20.

Experiments 23 and 24 use minimum evidence safeguards:

- At least 8 mutual matches.
- At least 6 RANSAC inliers.

These are experimental safeguards, not production acceptance thresholds.

All parameters remain provisional.

## 6. Research findings to date

Experiments completed: 1–26.

The research has investigated:

- Cropping and partial-image matching.
- Negative controls.
- Spatial distribution.
- Homography and affine degeneracy.
- Lowe ratio sensitivity.
- Mutual matching.
- Geometric overlap.
- RANSAC threshold sensitivity.
- Resolution and downscaling.
- Feature-count sensitivity.
- Noise and blur.
- Rotation and scaling.
- Rectangular and irregular occlusion.
- Feature-targeted occlusion.
- Spatial concentration.
- Grid resolution sensitivity.

### Important findings

1. Genuine cropped copies can retain strong geometric matching even when much of the original image is missing.
2. Tiny retained regions can produce uncertain results.
3. Homography and affine models can produce degenerate solutions.
4. A small number of geometric inliers is not sufficient evidence of a genuine match.
5. High inlier ratio alone is not sufficient.
6. Spatial coverage and geometric validity matter.
7. Mutual matching removes many ambiguous feature correspondences.
8. Downscaling can sometimes improve matching by suppressing fine image differences.
9. Increasing feature count increases genuine matches but can also introduce ambiguous correspondences.
10. Noise and blur reduce genuine matches in the tested examples.
11. Rotation and scaling are handled well in the current positive tests.
12. Irregular synthetic occlusion can be tolerated when sufficient useful features remain.
13. Deliberately targeting feature-rich regions can be much more damaging than randomly hiding the same image area.
14. ORB keypoints can be strongly concentrated in a small portion of an image.
15. Measured spatial concentration depends on grid resolution and ranking method.

### Current research direction

The next important question is how well the geometrically verified matches are distributed across both images.

A high number of matches concentrated in a small region may not provide sufficient evidence that two entire images represent the same underlying photograph.

However, overly strict spatial coverage requirements could reject legitimate cropped or partially overlapping images.

This trade-off requires further research.

The positive and negative image collection is still limited. Do not claim a general false-positive rate or universal matching threshold.

## 7. Latest completed experiments

### Experiment 21 - Combined rotation and scaling

Tested four combinations of rotation and scaling.

The genuine positive control retained strong geometric matching across all four transformations. Estimated rotation and scale were close to the applied transformations.

Two unrelated taxi controls remained weak, producing at most three and two inliers respectively.

### Experiment 22 - Rectangular occlusion resistance

Tested central and right-edge black rectangular masks covering up to 50% of the image.

The exact-copy positive control retained 187 inliers with 50% central occlusion and 240 inliers with 50% edge occlusion.

Only one genuine photograph and two unrelated negative photographs were used.

### Experiment 23 - Irregular occlusion resistance

Tested circular masks, multiple rectangles and irregular polygons.

The experiment used minimum evidence safeguards of 8 mutual matches and 6 RANSAC inliers.

The genuine positive controls retained substantial geometric evidence under the tested masks. Negative controls remained weak.

### Experiment 24 - Feature-targeted occlusion

Compared random-area occlusion with occlusion targeting feature-dense and high-response regions.

Targeted occlusion removed useful ORB keypoints much faster than random occlusion in the tested images.

This was deliberately adversarial synthetic occlusion, not a general test of ordinary real-world obstruction.

### Experiment 25 - Spatial concentration audit

Analysed the distribution of 2,000 ORB keypoints over a 20 x 20 grid.

For the exact-copy candidate:
- 103 of 400 cells were occupied.
- 297 cells were empty.
- The top 10% of cells by density contained approximately 80% of keypoints.
- The top 20% contained approximately 97%.

Density, total response and average response do not always rank the same cells.

### Experiment 26 - Grid resolution sensitivity

Compared 10 x 10, 20 x 20 and 40 x 40 grids across four images.

A 20 x 20 grid is retained as a useful middle-ground research baseline, not a universal optimum.

Area-based concentration and occupied-cell concentration must be kept separate. Fine grids can make area-based measurements misleading when most cells are empty.

## 8. Immediate next task

Continue research into the spatial distribution of geometrically verified matches.

The next experiment should investigate:

1. The spatial distribution of mutual matches in both reference and candidate images.
2. The spatial distribution of RANSAC inliers in both images.
3. Whether concentrated matches can produce misleading geometric agreement.
4. Whether spatial coverage can help distinguish genuine image matches from accidental local agreement.
5. How to establish useful minimum spatial coverage requirements without rejecting legitimate partial-image matches.

Use the existing research scripts and labelled benchmark material where appropriate.

The existing 20 x 20 grid is a provisional diagnostic baseline. Do not assume it is the correct production grid resolution.

Record the results in the research documentation and update the project handoff when appropriate.

Do not change production source code yet.

After research and documentation changes, run the full test suite:

```powershell
python -m pytest -v
```

Standalone research scripts must also be checked independently because the existing pytest suite may not cover them.

## 9. GUI requirement

The user wants two experience levels:

### Basic

Simple everyday operation with sensible defaults and minimal technical complexity.

### Advanced

Allow users to adjust ORB parameters and experiment, with safeguards and explanations.

Parameters under consideration:
- Feature count.
- Lowe ratio threshold.
- Mutual matching.
- RANSAC threshold.
- Resolution/downscaling.
- Retry strategies.

Changing these settings affects speed, sensitivity and false-positive risk.

This is a confirmed design requirement, not an implemented feature.

## 10. User working preferences

- Friendly, conversational style.
- Explain why each step matters.
- Small, incremental tasks.
- PowerShell instructions.
- Notepad++ for editing.
- Wait for command output before proceeding.
- Do not overwhelm with giant implementation plans.
- Do not stage, commit or push without explicit user approval.
- Run the full pytest suite periodically, particularly after code changes.
- Check standalone research scripts separately where appropriate.
- Do not assume the assistant can directly access or modify the user's Windows machine.

## 11. Recovery instructions for a new conversation

Start by reading:

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/development/HANDOFF.md`
4. `docs/experiments/ORB_RESEARCH.md`

Then inspect the actual repository state:

```powershell
cd F:\MediaDeduplicator

git status --short --branch

git log -10 --oneline

python -m pytest -v
```

The test suite should only be run after checking the repository and confirming the virtual environment is available.

Do not assume the historical test count or Git state is still current.

Do not assume the previous experiment or research state is still current without checking the documentation and working tree.

The latest documented research milestone is Experiment 26 - Grid resolution sensitivity.

Resume with the spatial-distribution research task described in Section 8, unless the user requests a different task.

Do not repeat completed experiments unnecessarily.

Do not change production source code, stage files, commit changes or push to GitHub without explicit user approval.

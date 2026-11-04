# MediaDeduplicator — Development Handoff

Last updated: 2026-11-04

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

Branch: `main`

HEAD:

`e1d87aa` — Add project continuity and ORB research documentation

Recent history:

```text
e1d87aa Add project continuity and ORB research documentation
4507e1c Add structural similarity image comparison
ec81824 Add difference hash image comparison
f255d66 Add image metadata extraction
1b6c366 Add image similarity threshold and pair scanning
3a67838 Add perceptual hash foundation
7ef18f9 Add exact duplicate scanning foundation
```

Last observed working tree:

- No modified tracked files.
- `TestMedia/` untracked.
- Do not stage or commit `TestMedia/`.

Always inspect the current repository state before proceeding.

## 4. Current development phase

We are investigating ORB feature matching using OpenCV.

This is research only.

No production source files or tests have been changed during the ORB experiments.

Experiments have been run as temporary PowerShell here-strings piped directly to Python.

Actual sample files are in:

`F:\MediaDeduplicator\TestMedia`

The contact sheet is for visual reference only and must not be used as an image comparison input.

## 5. ORB experimental configuration

Current baseline:

- ORB features: 2,000.
- Lowe ratio: 0.75.
- Mutual matching: enabled.
- RANSAC reprojection threshold: 5 pixels.
- Geometric model: `cv2.estimateAffinePartial2D`.
- Descriptor matching: Hamming distance.
- OpenCV version observed: 5.0.0.

These are provisional experimental settings.

## 6. Research findings to date

ORB experiments have investigated:

- Cropping.
- Negative controls.
- Spatial distribution.
- Homography degeneracy.
- Partial affine transformation.
- Lowe ratio threshold.
- Mutual matching.
- Spatial coverage.
- Affine overlap.
- RANSAC threshold.
- Resolution and downscaling.
- Feature count.
- Noise and blur.
- Rotation and scaling.

### Important findings

1. Genuine cropped copies can retain strong geometric matching even when much of the original image is missing.
2. Tiny retained regions can produce uncertain results.
3. Homography and affine models can produce degenerate solutions.
4. Two geometric inliers are not sufficient evidence of a genuine match.
5. High inlier ratio alone is not sufficient.
6. Spatial coverage and geometric validity matter.
7. Mutual matching removes many ambiguous feature correspondences.
8. Downscaling can sometimes improve matching by suppressing fine image differences.
9. Increasing feature count increases genuine matches but can also introduce ambiguous correspondences.
10. Noise and blur reduce genuine matches, but our current unrelated taxi controls remain weak.
11. Rotation and scaling are handled impressively well in the current positive tests.

Detailed experiment results belong in `docs/experiments/ORB_RESEARCH.md`.

## 7. Latest completed experiment

### Experiment 20 — Rotation and scaling resistance

Genuine exact-copy variant:

Rotation:
- 15°: 187 inliers.
- 30°: 204 inliers.
- 45°: 188 inliers.
- 90°: 247 inliers.
- 180°: 235 inliers.

Scaling:
- 0.50×: 115 inliers.
- 0.75×: 107 inliers.
- 1.25×: 177 inliers.
- 1.50×: 150 inliers.
- 2.00×: 75 inliers.

Estimated rotations and scales were close to the applied transformations.

The two unrelated taxi photographs remained weak negative controls, producing at most two geometric inliers in the reported tests.

## 8. Immediate next task

### Experiment 21 — Combined transformations

Test rotation and scaling together.

Planned combinations:

- Rotate 30° and scale 0.50×.
- Rotate 45° and scale 1.50×.
- Rotate 90° and scale 0.75×.
- Rotate 180° and scale 2.00×.

Compare:
- Genuine exact-copy variant.
- Unrelated taxi photograph 1.
- Unrelated taxi photograph 2.

Record:
- Keypoints in each image.
- Mutual matches.
- Geometric inliers.
- Inlier ratio.
- Estimated scale.
- Estimated rotation.

The next assistant should provide a single manageable PowerShell experiment script and wait for the user's results before continuing.

Do not change production source code yet.

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
- Do not push to GitHub prematurely.

## 11. Recovery instructions for a new conversation

Start by reading:

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/development/HANDOFF.md`

Then inspect:

```powershell
cd F:\MediaDeduplicator

git status --short --branch

git log -10 --oneline

python -m pytest -v
```

The test suite should only be run after checking the repository and confirming the virtual environment is available.

Do not assume the historical test count or Git state is still current.

Report the actual state and resume with Experiment 23 — Irregular occlusion resistance — unless the user requests a different task.
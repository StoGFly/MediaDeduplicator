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

The benchmark framework, curated labels and ORB experiments 23-26 were committed in `111a6db`. Experiments 27 and 28 extend that research locally. Use `git log -1 --oneline` and `git status --short --branch` to check the current checkout.

The [curated benchmark labels](../../benchmarks/data/curated_pair_labels.csv) are tracked. Git ignores `TestMedia/`, root-level `TestMedia_manifest_*.csv` inventories and `benchmarks/results/`. Keep personal media and generated results local.

## 4. Current development phase

The project is investigating ORB feature matching using OpenCV.

The project supports exact duplicates for photos and videos and focuses similarity research on photos. The first real-world milestone is a read-only image pilot with manual review of similarity results. ORB remains experimental.

ORB has not been integrated into production source code, and no production ORB tests have been written.

Research scripts for Experiments 23–28 are stored in:

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

Experiments completed: 1–28.

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

Experiment 28 found that overlap-normalized coverage can be almost identical for a genuine crop and a shared-patch composite. Record how much of each image overlaps and assess the combined evidence on more labelled images.

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

### Experiment 27 - Spatial coverage of verified matches

Measured 124 pairs. Shared-patch composites produced 435-476 inliers at a 100% inlier ratio, with evidence concentrated in a small part of each canvas. Genuine synthetic crops showed substantially higher coverage in the crop than in the reference. Some curated near-duplicate bursts had coverage as low as sampled negatives.

See [the research record](../experiments/ORB_RESEARCH.md#experiment-27---spatial-coverage-of-verified-matches) for the command, control groups and results. The full pytest suite passed all 58 tests. The experiment ran separately.

### Experiment 28 - Coverage within estimated overlap

Measured 136 pairs. Two shared-patch composites had overlap hull coverage close to their corresponding genuine crops. Their estimated overlap covered about 25% of both images, while nearly all of the crop candidate was inside the overlap. Three of six genuine edge crops produced zero inliers.

The run reproduced the common Experiment 27 metrics across 124 pairs. Seven geometry checks and all 58 pytest tests passed.

## 8. Immediate next task

Evaluate a review-only image pilot on a representative labelled folder. Record overlap on each side separately and compare genuine crops, near-duplicate bursts and images that share a small region. Treat ambiguous local matches as candidates for manual review. Keep the existing exact scan read-only.

Run the full suite with `python -m pytest -v` and verify standalone research scripts separately.

## 9. GUI requirement

Launch from the project environment with `python -m mediadedup.gui`.

Choose a recent folder in the editable path dropdown, or enter a new path. **Scan options → File extensions** lets you choose individual formats and stores the filter with the scan. Hide Scan Status to see compact progress along the bottom of the main window.

The Media preview panel supports video playback and opening the file in the default player. Tick copies to queue them for moving. **Move Status** shows the current file, bytes moved and issues. Successful moves clear their checkboxes, and failed copies stay queued for review.

- **Basic** finds exact SHA-256 duplicates in photos, videos, or both. Select the file types under **Include**. Advanced similarity searches photos.
- **Advanced** exposes the pHash agreement threshold and hash width for manual similarity review. The search compares every pair and may miss crops.

Both modes scan read-only. ORB controls remain part of the research roadmap.

**Review → Folder overlap** compares two separate folder trees using SHA-256. It shows how many files on each side match the other folder, the matched size, and the files that exist only on that side. Completed comparisons are saved locally.

Open **Scan Status** to see progress, elapsed time and totals. **Stop scan** saves a checkpoint. **Resume** checks for changed files and continues the saved scan. **Start fresh** starts a new history entry. Only one scan or move can run against the local database at a time.

The toolbar provides folder selection, scanning, scan history, filtering and file review controls. Desktop scans are recorded in the local `sql.db` under the MediaDeduplicator application data folder. History can reopen completed results with the original scan settings.

In Basic mode, select an exact group or extra copies and use **Move exact copies** to choose a destination. The app keeps the first file in each group, rechecks both hashes and preserves relative paths at the destination.

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
- Reuse available test and dependency caches while executing current checks. Use GPU acceleration when the test or benchmark supports it, and record the backend for measurements that need to be comparable.
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

The latest documented research milestone is Experiment 28 - Coverage within estimated overlap.

Resume with the image pilot evaluation in Section 8, unless the user requests a different task.

Do not repeat completed experiments unnecessarily.

Do not change production source code, stage files, commit changes or push to GitHub without explicit user approval.
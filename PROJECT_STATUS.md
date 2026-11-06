# MediaDeduplicator - Project Status

Last updated: 2026-11-06

## 1. Project overview

MediaDeduplicator is a Windows-based media deduplication application.

Project directory: `F:\MediaDeduplicator`

Git repository: `StoGFly/MediaDeduplicator` (public GitHub repository).

The application focuses on exact duplicate detection and visual similarity for images.

Planned interfaces:
- Graphical interface using PySide6.
- Command-line interface using Typer.

Optional AI-assisted functionality is also planned.

## 2. Development environment

- Operating system: Windows 11.
- Python: 3.12.
- Virtual environment: `.venv`.
- Test framework: pytest.
- Build configuration: `pyproject.toml`.

Installed project dependencies include:
- PySide6
- Typer
- SQLAlchemy
- Pillow
- ImageHash
- OpenCV
- NumPy
- Jinja2
- platformdirs

Optional image-quality dependency:
- scikit-image

## 3. Git status and milestones

The benchmark framework, curated labels and ORB experiments 23-26 were committed in `111a6db`. Experiments 27 and 28 extend that research locally. Use `git log -1 --oneline` and `git status --short --branch` to check the current checkout.

The [curated benchmark labels](benchmarks/data/curated_pair_labels.csv) are tracked. Git ignores `TestMedia/`, root-level `TestMedia_manifest_*.csv` inventories and `benchmarks/results/`. Keep personal media and generated results local.

## 4. Implemented functionality

### Exact duplicate scanning

- File discovery.
- Cryptographic SHA-256 hashing.
- Exact duplicate identification.

### Image perceptual hashing

- Perceptual hash (pHash).
- Difference hash (dHash).
- Similarity percentage calculations.
- Similar-image pair scanning.
- Similarity threshold validation.

### Image metadata

- Image metadata extraction.
- EXIF orientation handling.

### Structural similarity

- SSIM image comparison.
- Orientation-aware comparison for 90° and 270° rotations.
- Rotation information included in SSIM comparison results.

### CLI

The project can be invoked using:

```powershell
python -m mediadedup
```

Example exact scan:

```powershell
python -m mediadedup scan "F:\MediaDeduplicator\TestMedia"
```

Do not assume a globally installed `mediadedup` executable is available.

## 5. Testing status

All 58 pytest tests and seven standalone overlap geometry checks passed. Experiment 28 measured 136 pairs separately.

## 6. Current experimental research: ORB

OpenCV ORB feature matching is being investigated as an additional image similarity technique.

It is experimental and has not yet been integrated into production code.

Experiments completed: 1-28.

The detailed research record is maintained in:

`docs/experiments/ORB_RESEARCH.md`

### Recent experiments

| Experiment | Subject |
|---|---|
| 21 | Combined rotation and scaling resistance |
| 22 | Rectangular occlusion resistance |
| 23 | Irregular occlusion resistance |
| 24 | Feature-targeted occlusion |
| 25 | Spatial concentration audit |
| 26 | Grid resolution sensitivity |
| 27 | Spatial coverage of verified matches |
| 28 | Coverage within estimated overlap |

### Current experimental baseline

| Parameter | Experimental value |
|---|---:|
| ORB features | 2,000 |
| Lowe ratio | 0.75 |
| Mutual matching | Enabled |
| RANSAC reprojection threshold | 5 pixels |
| Geometric model | Partial affine |
| Spatial diagnostic grid | 20 x 20 |

These are experimental starting points, not final production defaults.

Experiments 23 and 24 use minimum evidence safeguards:
- At least 8 mutual matches.
- At least 6 RANSAC inliers.

These safeguards are research-script acceptance conditions, not established production thresholds.

### Experimental findings

The experiments have investigated:
- Cropping and partial-image matching.
- Rotation and scaling.
- Noise and blur.
- Different image resolutions and formats.
- Rectangular and irregular occlusion.
- Deliberately feature-targeted occlusion.
- Spatial concentration of detected keypoints.
- Sensitivity to spatial grid resolution.

Important findings:

- Match count alone is insufficient.
- Inlier ratio alone is insufficient.
- A small number of inliers is not convincing evidence.
- Synthetic feature-targeted occlusion can be substantially more damaging than random-area occlusion.
- Keypoints can be heavily concentrated in a relatively small portion of an image.
- Spatial concentration measurements depend on grid resolution and ranking method.
- Experiment 27 found concentrated inlier coverage in shared-patch composites despite high inlier counts. Genuine crops can have much higher coverage in the cropped image than in the original.

The test collection remains limited. These results do not establish a general false-positive rate, universal occlusion tolerance or production acceptance threshold.

### Next research focus

Evaluate a review-only image pilot on a representative labelled folder. Record overlap on each side separately and compare genuine crops, near-duplicate bursts and images that share a small region. Treat ambiguous local matches as candidates for manual review. Keep the existing exact scan read-only.

Do not integrate ORB into production code until the matching and acceptance rules have been validated against a larger, more diverse labelled dataset.

### Current experimental baseline

| Parameter | Experimental value |
|---|---:|
| ORB features | 2,000 |
| Lowe ratio | 0.75 |
| Mutual matching | Enabled |
| RANSAC reprojection threshold | 5 pixels |
| Geometric model | Partial affine |

These values are experimental starting points, not final production defaults.

### Experimental findings

ORB has demonstrated promising matching behaviour with:
- Cropped images.
- Brightness and contrast changes.
- JPEG compression.
- Noise.
- Blur.
- Rotation.
- Scaling.
- Different image dimensions and formats.

Unrelated taxi photographs have been used as negative controls.

The experiments show why absolute inlier count, inlier ratio, spatial distribution and geometric validity must be considered together.

A high inlier percentage alone is insufficient evidence of a genuine match.

## 7. GUI design direction

The intended GUI will provide two experience levels.

### Basic mode

- Straightforward controls.
- Sensible automatic defaults.
- Clear similarity results.
- Minimal technical complexity.
- Safe workflows.

### Advanced mode

Expose adjustable detection parameters, including:
- ORB feature count.
- Lowe ratio threshold.
- Mutual matching.
- RANSAC reprojection threshold.
- Resolution and downscaling.
- Potential retry strategies.

Advanced settings must explain their effects on speed, sensitivity and false-positive risk.

Provide sensible defaults and safeguards.

This GUI design is planned, not implemented.

## 8. Planned development areas

The following areas remain future work unless subsequent documentation or source inspection establishes otherwise:

- ORB production detector and matching pipeline.
- Spatial distribution analysis of geometrically verified matches.
- Larger and more diverse positive and negative image datasets.
- Validation of matching and acceptance thresholds.
- Optional AI-assisted similarity using OpenCLIP.
- SQLite-backed application storage.
- PySide6 graphical interface.
- Quarantine and restoration workflows.
- CLI expansion.
- TOML configuration.
- Packaging with PyInstaller.
- Continuous integration.

## 9. Safety principles

- Scanning must be read-only.
- SHA-256 remains authoritative for exact duplicates.
- Perceptual similarity is not proof of identity.
- Never permanently delete files automatically.
- Quarantine and restore operations require safeguards.
- Preserve user data and original files.

## 10. Immediate next task

Experiments completed: **1-28**.

Continue with the review-only image pilot evaluation in [the development handoff](docs/development/HANDOFF.md#8-immediate-next-task). Expand the labelled controls and validate any matching rule before considering production integration.

## 11. GitHub publication

`StoGFly/MediaDeduplicator` is public and uses the MIT licence.

# MediaDeduplicator — Project Status

Last updated: 2026-11-04

## 1. Project overview

MediaDeduplicator is a Windows-based media deduplication application.

Project directory: `F:\MediaDeduplicator`

Git repository: `StoGFly/MediaDeduplicator` (planned private GitHub repository).

The application is intended to identify exact duplicates and visually or acoustically similar media.

Supported media categories planned:
- Images.
- Videos.
- Audio.

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

Main branch: `main`

Latest recorded commit:

`cf20551` — Add orientation-aware SSIM image comparison

Recorded development milestones:

| Commit | Description |
|---|---|
| `7ef18f9` | Add exact duplicate scanning foundation |
| `3a67838` | Add perceptual image hashing foundation |
| `1b6c366` | Add image similarity threshold and pair scanning |
| `f255d66` | Add image metadata extraction |
| `ec81824` | Add difference hash image comparison |
| `4507e1c` | Add structural similarity image comparison |
| `cf20551` | Add orientation-aware SSIM image comparison |

At the last verified Git inspection:
- No modified tracked files.
- `TestMedia/` is untracked.
- Personal sample media must remain outside Git.

Do not assume this Git state remains current. Inspect the repository before further work.

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

Previously verified:
- Full project test suite: 58 tests passed.
- Image test suite: 43 tests passed at the last recorded image milestone.

These are historical results, not confirmation of the current test state.

Run the tests again before making claims about current test status:

```powershell
python -m pytest -v
```

## 6. Current experimental research: ORB

OpenCV ORB feature matching is being investigated as an additional image similarity technique.

It is experimental and has not yet been integrated into production code.

Investigations completed through 2026-11-04:

1. Centred cropping.
2. Unrelated-image negative controls.
3. Asymmetric cropping.
4. Aggressive cropping.
5. Spatial distribution of matches.
6. Geometric diagnostics.
7. Homography corner mapping.
8. Physical validity checks.
9. Partial affine transformation.
10. Lowe ratio sensitivity.
11. Mutual matching.
12. Mutual-match spatial coverage.
13. Affine overlap analysis.
14. RANSAC threshold sensitivity.
15. Resolution sensitivity.
16. ORB feature-count sensitivity.
17. Feature-count positive and negative controls.
18. Noise and blur resistance.
19. Noise and blur negative controls.
20. Rotation and scaling resistance.

Detailed results should be maintained in:

`docs/experiments/ORB_RESEARCH.md`

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

- ORB production detector.
- Combined rotation and scaling experiments.
- More extensive positive and negative image datasets.
- Improved image similarity detection pipeline.
- Video similarity using FFmpeg and sampled frames.
- Audio similarity using Chromaprint.
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

Continue experimental ORB research.

Next experiment:

**Experiment 21 — Combined rotation and scaling resistance.**

Test combinations of rotation and resizing against:
- The genuine exact-copy variant.
- Both unrelated taxi photographs.

Evaluate mutual matches, geometric inliers, inlier ratio, estimated scale and rotation.

Do not integrate ORB into production code yet.

## 11. GitHub publication

The intended repository is private:

`StoGFly/MediaDeduplicator`

MIT licence.

The first GitHub push is intentionally deferred until the agreed development and testing milestones are ready.
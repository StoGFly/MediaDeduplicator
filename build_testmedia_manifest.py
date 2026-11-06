
from pathlib import Path
from datetime import datetime
import csv
import hashlib
from collections import defaultdict

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "TestMedia"
OUTPUT = ROOT / f"TestMedia_manifest_{datetime.now():%Y%m%d_%H%M%S}.csv"

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp",
    ".tif", ".tiff", ".webp", ".gif"
}

COLUMNS = [
    "relative_path",
    "category",
    "role",
    "comparison_input",
    "legacy_test_candidate",
    "filename",
    "extension",
    "format",
    "file_size_bytes",
    "sha256",
    "stored_width",
    "stored_height",
    "display_width",
    "display_height",
    "exif_orientation",
    "source_filename",
    "source_relative_path",
    "source_original_relative_path",
    "transformation",
    "source_hash_match",
    "status",
    "error",
]


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path):
    return path.relative_to(DATASET).as_posix()


def image_metadata(path):
    with Image.open(path) as image:
        image.load()

        stored_width, stored_height = image.size
        orientation = image.getexif().get(274)
        display = ImageOps.exif_transpose(image)

        return {
            "format": image.format,
            "stored_width": stored_width,
            "stored_height": stored_height,
            "display_width": display.width,
            "display_height": display.height,
            "exif_orientation": orientation,
        }


def classify(path):
    parts = path.relative_to(DATASET).parts
    category = parts[0]

    if category == "Originals":
        return category, "original", True

    if category == "PositiveVariants":
        if len(parts) > 1 and parts[1] == "Generated":
            return category, "positive_generated_variant", True
        return category, "positive_source_copy", False

    if category == "HardNegatives":
        return category, "hard_negative", True

    if category == "NegativeControls":
        return category, "negative_control", True

    if category == "Reference":
        return category, "reference_only", False

    return category, "unclassified", False


def main():
    if not DATASET.is_dir():
        raise SystemExit(f"Dataset directory not found: {DATASET}")

    files = sorted(
        path for path in DATASET.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )

    records = []

    # First pass: inventory, hashes and image metadata.
    for path in files:
        category, role, comparison_input = classify(path)

        record = {
            "relative_path": relative(path),
            "category": category,
            "role": role,
            "comparison_input": comparison_input,
            "legacy_test_candidate": (
                category == "Reference"
                and path.name in {
                    "2022-12-27 21.34.20.jpg",
                    "2022-12-27 21.34.20-1.jpg",
                }
            ),
            "filename": path.name,
            "extension": path.suffix.lower(),
            "format": "",
            "file_size_bytes": path.stat().st_size,
            "sha256": "",
            "stored_width": "",
            "stored_height": "",
            "display_width": "",
            "display_height": "",
            "exif_orientation": "",
            "source_filename": "",
            "source_relative_path": "",
            "source_original_relative_path": "",
            "transformation": "",
            "source_hash_match": "",
            "status": "",
            "error": "",
            "_path": path,
        }

        try:
            record["sha256"] = sha256_file(path)
            record.update(image_metadata(path))
            record["status"] = "OK"
        except Exception as exc:
            record["status"] = "ERROR"
            record["error"] = str(exc)

        records.append(record)

    # Build filename/stem indexes for source association.
    originals = defaultdict(list)
    positive_sources = defaultdict(list)

    for record in records:
        path = record["_path"]

        if record["category"] == "Originals":
            originals[path.stem].append(record)

        elif record["role"] == "positive_source_copy":
            positive_sources[path.stem].append(record)

    # Second pass: associate source copies and generated variants.
    for record in records:
        path = record["_path"]
        role = record["role"]

        if role == "positive_source_copy":
            matches = originals[path.stem]

            if len(matches) == 1:
                source = matches[0]
                record["source_filename"] = source["filename"]
                record["source_relative_path"] = source["relative_path"]
                record["source_original_relative_path"] = source["relative_path"]

                if record["sha256"] and source["sha256"]:
                    record["source_hash_match"] = (
                        record["sha256"] == source["sha256"]
                    )

            else:
                record["error"] = (
                    f"Original source matches found: {len(matches)}"
                )

        elif role == "positive_generated_variant":
            if "__" not in path.stem:
                record["error"] = "Generated filename has no transformation separator"
                continue

            source_stem, transformation = path.stem.rsplit("__", 1)
            record["transformation"] = transformation

            matches = positive_sources[source_stem]

            if len(matches) == 1:
                source = matches[0]
                record["source_filename"] = source["filename"]
                record["source_relative_path"] = source["relative_path"]
                record["source_original_relative_path"] = (
                    source["source_original_relative_path"]
                )
            else:
                record["error"] = (
                    f"Positive source matches found for "
                    f"{source_stem}: {len(matches)}"
                )

    # Detect duplicate source stems.
    duplicate_original_stems = {
        stem: len(matches)
        for stem, matches in originals.items()
        if len(matches) > 1
    }

    # Write CSV.
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()

        for record in records:
            writer.writerow({
                column: record.get(column, "")
                for column in COLUMNS
            })

    # Report summary.
    print("=" * 65)
    print("TEST MEDIA MANIFEST")
    print("=" * 65)
    print(f"Dataset:             {DATASET}")
    print(f"CSV output:          {OUTPUT}")
    print(f"Total image files:   {len(records)}")
    print()

    categories = defaultdict(int)
    statuses = defaultdict(int)
    transformations = defaultdict(int)

    for record in records:
        categories[record["category"]] += 1
        statuses[record["status"]] += 1

        if record["transformation"]:
            transformations[record["transformation"]] += 1

    print("CATEGORY COUNTS")
    for category, count in sorted(categories.items()):
        print(f"{category:22} {count:5}")

    print()
    print("IMAGE STATUS")
    for status, count in sorted(statuses.items()):
        print(f"{status:22} {count:5}")

    print()
    print("GENERATED TRANSFORMATIONS")
    for name, count in sorted(transformations.items()):
        print(f"{name:22} {count:5}")

    print()
    print("SOURCE ASSOCIATIONS")

    source_copies = [
        r for r in records if r["role"] == "positive_source_copy"
    ]
    generated = [
        r for r in records if r["role"] == "positive_generated_variant"
    ]

    print(f"Positive source copies: {len(source_copies)}")
    print(f"Generated variants:     {len(generated)}")
    print(
        "Exact source-copy hash matches:",
        sum(r["source_hash_match"] is True for r in source_copies),
    )
    print(
        "Generated variants with source:",
        sum(bool(r["source_relative_path"]) for r in generated),
    )

    print()
    print("DUPLICATE ORIGINAL STEMS")
    if duplicate_original_stems:
        for stem, count in sorted(duplicate_original_stems.items()):
            print(f"{stem}: {count}")
    else:
        print("None")

    errors = [
        r for r in records
        if r["status"] != "OK" or r["error"]
    ]

    print()
    print(f"Records needing attention: {len(errors)}")
    for record in errors:
        print(f"  {record['relative_path']}: {record['error']}")

    print()
    print("Manifest generation complete.")


if __name__ == "__main__":
    main()

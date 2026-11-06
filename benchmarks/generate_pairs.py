
"""Generate deterministic, labelled image pairs for benchmarking."""

import argparse
import csv
from collections import defaultdict
from itertools import combinations
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "benchmarks" / "results" / "benchmark_pairs.csv"

EXPECTED_FAMILIES = 36
EXPECTED_GENERATED_PER_FAMILY = 15


def load_manifest(manifest_path):
    with manifest_path.open(
        "r", newline="", encoding="utf-8-sig"
    ) as file:
        records = list(csv.DictReader(file))

    if not records:
        raise ValueError("Manifest is empty.")

    errors = [
        record for record in records
        if record["status"] != "OK" or record["error"].strip()
    ]

    if errors:
        raise ValueError(
            f"Manifest contains {len(errors)} records needing attention."
        )

    return records


def validate_dataset(records):
    originals = {
        record["relative_path"]: record
        for record in records
        if record["role"] == "original"
    }

    source_copies = {
        record["relative_path"]: record
        for record in records
        if record["role"] == "positive_source_copy"
    }

    generated_by_family = defaultdict(list)

    for record in records:
        if record["role"] == "positive_generated_variant":
            family = record["source_original_relative_path"]

            if family not in originals:
                raise ValueError(
                    f"Unknown original family: {family}"
                )

            generated_by_family[family].append(record)

    if len(originals) != EXPECTED_FAMILIES:
        raise ValueError(
            f"Expected {EXPECTED_FAMILIES} originals, "
            f"found {len(originals)}."
        )

    if len(source_copies) != EXPECTED_FAMILIES:
        raise ValueError(
            f"Expected {EXPECTED_FAMILIES} source copies, "
            f"found {len(source_copies)}."
        )

    if len(generated_by_family) != EXPECTED_FAMILIES:
        raise ValueError(
            "Not all original families have generated variants."
        )

    for original_path in sorted(originals):
        original = originals[original_path]
        matches = [
            record for record in source_copies.values()
            if record["source_original_relative_path"] == original_path
        ]

        if len(matches) != 1:
            raise ValueError(
                f"Expected one source copy for {original_path}; "
                f"found {len(matches)}."
            )

        if matches[0]["source_hash_match"].lower() != "true":
            raise ValueError(
                f"Source copy is not an exact hash match: "
                f"{matches[0]['relative_path']}"
            )

        variants = generated_by_family[original_path]

        if len(variants) != EXPECTED_GENERATED_PER_FAMILY:
            raise ValueError(
                f"{original_path}: expected "
                f"{EXPECTED_GENERATED_PER_FAMILY} generated variants, "
                f"found {len(variants)}."
            )

        for variant in variants:
            if variant["source_relative_path"] not in source_copies:
                raise ValueError(
                    f"Invalid source-copy association: "
                    f"{variant['relative_path']}"
                )

    return originals, source_copies, generated_by_family


def make_pair(
    pair_id,
    pair_group,
    label,
    image_a,
    image_b,
    family_id="",
    transformation_a="",
    transformation_b="",
):
    return {
        "pair_id": pair_id,
        "pair_group": pair_group,
        "label": label,
        "image_a": f"TestMedia/{image_a}",
        "image_b": f"TestMedia/{image_b}",
        "family_id": family_id,
        "transformation_a": transformation_a,
        "transformation_b": transformation_b,
    }


def generate_pairs(originals, source_copies, generated_by_family):
    pairs = []
    counters = defaultdict(int)

    def add_pair(group, *args, **kwargs):
        counters[group] += 1
        pair_id = f"{group.upper()}-{counters[group]:06d}"

        pairs.append(
            make_pair(pair_id, group, *args, **kwargs)
        )

    # Group 1: original against its exact source copy and
    # all 15 generated transformations.
    for family in sorted(originals):
        original = originals[family]

        source_copy = next(
            record for record in source_copies.values()
            if record["source_original_relative_path"] == family
        )

        add_pair(
            "original_to_variant",
            "positive",
            original["relative_path"],
            source_copy["relative_path"],
            family_id=family,
            transformation_b="exact_copy",
        )

        for variant in sorted(
            generated_by_family[family],
            key=lambda record: record["relative_path"],
        ):
            add_pair(
                "original_to_variant",
                "positive",
                original["relative_path"],
                variant["relative_path"],
                family_id=family,
                transformation_b=variant["transformation"],
            )

    # Group 2: all combinations of generated variants
    # belonging to the same original family.
    for family in sorted(generated_by_family):
        variants = sorted(
            generated_by_family[family],
            key=lambda record: record["relative_path"],
        )

        for first, second in combinations(variants, 2):
            add_pair(
                "variant_to_variant",
                "positive",
                first["relative_path"],
                second["relative_path"],
                family_id=family,
                transformation_a=first["transformation"],
                transformation_b=second["transformation"],
            )

    # Group 3: different original photographs.
    original_records = [
        originals[path] for path in sorted(originals)
    ]

    for first, second in combinations(original_records, 2):
        add_pair(
            "original_to_original",
            "negative",
            first["relative_path"],
            second["relative_path"],
        )

    return pairs, counters


def main():
    parser = argparse.ArgumentParser(
        description="Generate deterministic benchmark image pairs."
    )

    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to the TestMedia manifest CSV.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output CSV path.",
    )

    args = parser.parse_args()

    manifest_path = Path(args.manifest)

    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path

    if not manifest_path.is_file():
        raise SystemExit(
            f"Manifest not found: {manifest_path}"
        )

    try:
        records = load_manifest(manifest_path)

        originals, source_copies, generated = (
            validate_dataset(records)
        )

        pairs, counters = generate_pairs(
            originals,
            source_copies,
            generated,
        )

    except (ValueError, KeyError, OSError) as exc:
        raise SystemExit(f"Benchmark generation failed: {exc}")

    columns = [
        "pair_id",
        "pair_group",
        "label",
        "image_a",
        "image_b",
        "family_id",
        "transformation_a",
        "transformation_b",
    ]

    output_path = args.output

    if not output_path.is_absolute():
        output_path = ROOT / output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(pairs)

    print("=" * 65)
    print("BENCHMARK PAIR GENERATION")
    print("=" * 65)
    print(f"Manifest: {manifest_path}")
    print(f"Output:   {output_path}")
    print()
    print("PAIR COUNTS")

    for group, count in sorted(counters.items()):
        print(f"{group:25} {count:6}")

    print("-" * 65)
    print(f"{'TOTAL':25} {len(pairs):6}")
    print()
    print("Dataset validation passed.")
    print("Pair generation complete.")


if __name__ == "__main__":
    main()

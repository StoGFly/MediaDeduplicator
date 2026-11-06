"""Rank hard negatives against all originals and identify detector consensus."""

import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

INPUT = (
    ROOT
    / "benchmarks"
    / "results"
    / "hard_negative_cross_reference_results.csv"
)

OUTPUT = (
    ROOT
    / "benchmarks"
    / "results"
    / "hard_negative_cross_reference_ranked.csv"
)

DETECTORS = ("phash", "dhash", "ssim")

EXPECTED_ORIGINALS = 36
EXPECTED_NEGATIVES = 41


def number(row, field):
    value = row.get(field, "")
    return float(value) if value not in ("", None) else 0.0


def rank_rows(rows, sort_key, rank_field):
    """Assign deterministic ordinal ranks within a hard-negative group."""

    ordered = sorted(rows, key=sort_key)

    for rank, row in enumerate(ordered, start=1):
        row[rank_field] = rank

    return ordered


def main():
    if not INPUT.is_file():
        raise FileNotFoundError(INPUT)

    if OUTPUT.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing results: {OUTPUT}"
        )

    with INPUT.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        original_fields = reader.fieldnames
        rows = list(reader)

    if len(rows) != EXPECTED_ORIGINALS * EXPECTED_NEGATIVES:
        raise ValueError(
            f"Expected {EXPECTED_ORIGINALS * EXPECTED_NEGATIVES} rows, "
            f"found {len(rows)}"
        )

    groups = defaultdict(list)

    for row in rows:
        if row["label"] != "negative":
            raise ValueError(f"Unexpected label: {row['label']}")

        groups[row["image_b"]].append(row)

    if len(groups) != EXPECTED_NEGATIVES:
        raise ValueError(
            f"Expected {EXPECTED_NEGATIVES} hard negatives, "
            f"found {len(groups)}"
        )

    extra_fields = [
        "phash_rank",
        "dhash_rank",
        "ssim_rank",
        "orb_rank",
        "orb_supported_rank",
        "phash_top3",
        "dhash_top3",
        "ssim_top3",
        "orb_supported_top3",
        "consensus_top3_votes",
    ]

    supported_pair_count = 0
    negatives_with_supported_orb = 0

    for negative, group in sorted(groups.items()):
        if len(group) != EXPECTED_ORIGINALS:
            raise ValueError(
                f"{negative}: expected {EXPECTED_ORIGINALS} pairs, "
                f"found {len(group)}"
            )

        if any(row[f"{detector}_status"] != "ok"
               for row in group
               for detector in DETECTORS + ("orb",)):
            raise ValueError(f"Detector failure found for {negative}")

        if len({row["image_a"] for row in group}) != EXPECTED_ORIGINALS:
            raise ValueError(f"Duplicate original comparison in {negative}")

        for row in group:
            for field in extra_fields:
                row[field] = ""

        for detector in DETECTORS:
            rank_rows(
                group,
                lambda row, d=detector: (
                    -number(row, f"{d}_similarity_percent"),
                    row["image_a"],
                ),
                f"{detector}_rank",
            )

        # Raw ORB ranking. This is diagnostic, not a similarity score.
        rank_rows(
            group,
            lambda row: (
                -number(row, "orb_mutual_matches"),
                -number(row, "orb_inliers"),
                -number(row, "orb_inlier_percent"),
                row["image_a"],
            ),
            "orb_rank",
        )

        # Only geometry-supported ORB comparisons can contribute a vote.
        supported = [
            row for row in group
            if row["orb_geometry_supported"].strip().lower() == "true"
        ]

        supported_pair_count += len(supported)

        if supported:
            negatives_with_supported_orb += 1

            rank_rows(
                supported,
                lambda row: (
                    -number(row, "orb_mutual_matches"),
                    -number(row, "orb_inliers"),
                    -number(row, "orb_inlier_percent"),
                    row["image_a"],
                ),
                "orb_supported_rank",
            )

        for row in group:
            for detector in DETECTORS:
                row[f"{detector}_top3"] = (
                    "true" if int(row[f"{detector}_rank"]) <= 3
                    else "false"
                )

            if row["orb_supported_rank"] != "":
                row["orb_supported_top3"] = (
                    "true" if int(row["orb_supported_rank"]) <= 3
                    else "false"
                )
            else:
                row["orb_supported_top3"] = "false"

            row["consensus_top3_votes"] = sum(
                row[field] == "true"
                for field in (
                    "phash_top3",
                    "dhash_top3",
                    "ssim_top3",
                    "orb_supported_top3",
                )
            )

    output_fields = original_fields + extra_fields

    with OUTPUT.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=output_fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Hard negatives analysed: {len(groups)}")
    print(f"Originals per hard negative: {EXPECTED_ORIGINALS}")
    print(f"Ranked comparisons: {len(rows)}")
    print(f"ORB geometry-supported pairs: {supported_pair_count}")
    print(
        "Hard negatives with at least one geometry-supported ORB pair: "
        f"{negatives_with_supported_orb}"
    )

    print("\nCross-detector top-three consensus (2 or more votes):")

    consensus_rows = sorted(
        (
            row for row in rows
            if int(row["consensus_top3_votes"]) >= 2
        ),
        key=lambda row: (
            -int(row["consensus_top3_votes"]),
            row["image_b"],
            row["image_a"],
        ),
    )

    for row in consensus_rows[:25]:
        print(
            f'{row["image_b"].split("/")[-1]} -> '
            f'{row["image_a"].split("/")[-1]} | '
            f'votes={row["consensus_top3_votes"]}/4 | '
            f'pHash={row["phash_rank"]} '
            f'dHash={row["dhash_rank"]} '
            f'SSIM={row["ssim_rank"]} '
            f'ORB-supported={row["orb_supported_rank"] or "-"}'
        )

    print(f"\nConsensus pairs with 2+ votes: {len(consensus_rows)}")
    print(f"Results saved to: {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

"""Create the complete human-reviewed benchmark label dataset."""

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "benchmarks" / "data" / "curated_pair_labels.csv"

FIELDS = [
    "pair_id",
    "image_a",
    "image_b",
    "exact_duplicate_label",
    "near_duplicate_label",
    "relationship",
    "review_status",
    "review_note",
]

REVIEWED_PAIRS = [
    {
        "pair_id": "CURATED-0001",
        "image_a": "TestMedia/Originals/2024-12-03 22.35.32.jpg",
        "image_b": "TestMedia/HardNegatives/2024-12-03 22.35.33.jpg",
        "exact_duplicate_label": "negative",
        "near_duplicate_label": "positive",
        "relationship": "near_duplicate_burst",
        "review_status": "human_reviewed",
        "review_note": "Same person and location, almost identical camera position; minor pose differences.",
    },
    {
        "pair_id": "CURATED-0002",
        "image_a": "TestMedia/Originals/2024-12-03 22.50.38.jpg",
        "image_b": "TestMedia/HardNegatives/2024-12-03 22.50.40.jpg",
        "exact_duplicate_label": "negative",
        "near_duplicate_label": "positive",
        "relationship": "near_duplicate_burst",
        "review_status": "human_reviewed",
        "review_note": "Same people and selfie setting; slight expression and framing differences.",
    },
    {
        "pair_id": "CURATED-0003",
        "image_a": "TestMedia/Originals/2024-12-03 22.57.32.jpg",
        "image_b": "TestMedia/HardNegatives/2024-12-03 22.57.33.jpg",
        "exact_duplicate_label": "negative",
        "near_duplicate_label": "positive",
        "relationship": "near_duplicate_burst",
        "review_status": "human_reviewed",
        "review_note": "Same cathedral and almost identical viewpoint; minor framing differences.",
    },
    {
        "pair_id": "CURATED-0004",
        "image_a": "TestMedia/Originals/2024-12-03 23.21.02.jpg",
        "image_b": "TestMedia/HardNegatives/2024-12-03 23.21.05.jpg",
        "exact_duplicate_label": "negative",
        "near_duplicate_label": "positive",
        "relationship": "near_duplicate_burst",
        "review_status": "human_reviewed",
        "review_note": "Same street and viewpoint; a hand enters the foreground in one image.",
    },
    {
        "pair_id": "CURATED-0005",
        "image_a": "TestMedia/Originals/2024-12-03 23.21.18.jpg",
        "image_b": "TestMedia/HardNegatives/2024-12-03 23.21.19.jpg",
        "exact_duplicate_label": "negative",
        "near_duplicate_label": "positive",
        "relationship": "near_duplicate_burst",
        "review_status": "human_reviewed",
        "review_note": "Same street and viewpoint; framing and pedestrian positions differ.",
    },
    {
        "pair_id": "CURATED-0006",
        "image_a": "TestMedia/Originals/2024-12-03 17.46.03-1.jpg",
        "image_b": "TestMedia/HardNegatives/2024-12-03 17.46.04-1.jpg",
        "exact_duplicate_label": "negative",
        "near_duplicate_label": "positive",
        "relationship": "near_duplicate_burst",
        "review_status": "human_reviewed",
        "review_note": "Same people, clothing and Leaning Tower background; almost identical framing, one-second burst.",
    },
    {
        "pair_id": "CURATED-0007",
        "image_a": "TestMedia/Originals/2024-12-03 22.54.52.jpg",
        "image_b": "TestMedia/HardNegatives/2024-12-03 22.54.53.jpg",
        "exact_duplicate_label": "negative",
        "near_duplicate_label": "positive",
        "relationship": "near_duplicate_burst",
        "review_status": "human_reviewed",
        "review_note": "Same people and cathedral viewpoint; minor expression and framing differences, one-second burst.",
    },
    {
        "pair_id": "CURATED-0008",
        "image_a": "TestMedia/Originals/2024-12-03 17.46.05-1.jpg",
        "image_b": "TestMedia/HardNegatives/2024-12-03 17.46.08.jpg",
        "exact_duplicate_label": "negative",
        "near_duplicate_label": "negative",
        "relationship": "same_scene",
        "review_status": "human_reviewed",
        "review_note": "Same people and Leaning Tower setting, three seconds apart; substantially different poses and composition. Burst sequence, but not a near-duplicate.",
    },
    {
        "pair_id": "CURATED-0009",
        "image_a": "TestMedia/Originals/2024-12-03 17.46.17.jpg",
        "image_b": "TestMedia/HardNegatives/2024-12-03 17.46.18.jpg",
        "exact_duplicate_label": "negative",
        "near_duplicate_label": "positive",
        "relationship": "near_duplicate_burst",
        "review_status": "human_reviewed",
        "review_note": "Same family members, positions and Leaning Tower background; nearly identical composition with minor expression and framing differences.",
    },
    {
        "pair_id": "CURATED-0010",
        "image_a": "TestMedia/Originals/2024-12-03 22.51.10.jpg",
        "image_b": "TestMedia/HardNegatives/2024-12-03 22.51.13.jpg",
        "exact_duplicate_label": "negative",
        "near_duplicate_label": "positive",
        "relationship": "near_duplicate_burst",
        "review_status": "human_reviewed",
        "review_note": "Same people and low-angle cathedral viewpoint; nearly identical composition with minor expression and framing differences, three seconds apart.",
    },
]


def main():
    if OUTPUT.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing file: {OUTPUT}"
        )

    records = []

    for pair in REVIEWED_PAIRS:
        for field in ("image_a", "image_b"):
            image_path = ROOT / pair[field]

            if not image_path.is_file():
                raise FileNotFoundError(image_path)

        records.append({field: pair[field] for field in FIELDS})

    if len({record["pair_id"] for record in records}) != len(records):
        raise ValueError("Duplicate pair IDs detected.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)

    near_positive = sum(
        record["near_duplicate_label"] == "positive"
        for record in records
    )
    same_scene = sum(
        record["relationship"] == "same_scene"
        for record in records
    )

    print(f"Created: {OUTPUT.relative_to(ROOT)}")
    print(f"Reviewed pairs: {len(records)}")
    print(f"Near-duplicate positives: {near_positive}")
    print(f"Same-scene relationships: {same_scene}")


if __name__ == "__main__":
    main()

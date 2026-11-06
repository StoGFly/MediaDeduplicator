
"""Create contact sheets for unreviewed cross-detector consensus pairs."""

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]

INPUT = (
    ROOT / "benchmarks" / "results"
    / "hard_negative_cross_reference_ranked.csv"
)

OUTPUT_DIR = ROOT / "benchmarks" / "results"

BATCH_SIZE = 10
COLUMNS = 2

IMAGE_WIDTH = 420
IMAGE_HEIGHT = 260
PAIR_WIDTH = IMAGE_WIDTH * 2 + 40
PAIR_HEIGHT = 350
MARGIN = 20
HEADER_HEIGHT = 65

REVIEWED_PAIRS = {
    (
        "TestMedia/Originals/2024-12-03 22.35.32.jpg",
        "TestMedia/HardNegatives/2024-12-03 22.35.33.jpg",
    ),
    (
        "TestMedia/Originals/2024-12-03 22.50.38.jpg",
        "TestMedia/HardNegatives/2024-12-03 22.50.40.jpg",
    ),
    (
        "TestMedia/Originals/2024-12-03 22.57.32.jpg",
        "TestMedia/HardNegatives/2024-12-03 22.57.33.jpg",
    ),
    (
        "TestMedia/Originals/2024-12-03 23.21.02.jpg",
        "TestMedia/HardNegatives/2024-12-03 23.21.05.jpg",
    ),
    (
        "TestMedia/Originals/2024-12-03 23.21.18.jpg",
        "TestMedia/HardNegatives/2024-12-03 23.21.19.jpg",
    ),
}


def load_candidates():
    with INPUT.open(
        "r", newline="", encoding="utf-8-sig"
    ) as file:
        rows = list(csv.DictReader(file))

    candidates = []

    for row in rows:
        votes = int(row["consensus_top3_votes"])
        pair = (row["image_a"], row["image_b"])

        if votes < 2 or pair in REVIEWED_PAIRS:
            continue

        candidates.append(row)

    candidates.sort(
        key=lambda row: (
            -int(row["consensus_top3_votes"]),
            row["image_b"],
            row["image_a"],
        )
    )

    return candidates


def load_thumbnail(path):
    full_path = ROOT / path

    if not full_path.is_file():
        raise FileNotFoundError(full_path)

    with Image.open(full_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((IMAGE_WIDTH - 10, IMAGE_HEIGHT - 10))

    return image


def draw_pair(sheet, draw, row, index, x, y, font):
    image_a = row["image_a"]
    image_b = row["image_b"]

    votes = row["consensus_top3_votes"]

    title = (
        f"PAIR {index:02d} | CONSENSUS {votes}/4"
    )

    metrics = (
        f"pHash rank {row['phash_rank']} ({row['phash_similarity_percent']}%)  "
        f"dHash rank {row['dhash_rank']} ({row['dhash_similarity_percent']}%)"
    )

    metrics2 = (
        f"SSIM rank {row['ssim_rank']} ({row['ssim_similarity_percent']}%)  "
        f"ORB supported rank {row['orb_supported_rank'] or '-'}"
    )

    draw.text((x, y), title, fill="black", font=font)
    draw.text((x, y + 23), metrics, fill="black", font=font)
    draw.text((x, y + 44), metrics2, fill="black", font=font)

    image_y = y + 72

    for column, (path, label) in enumerate([
        (image_b, "HARD NEGATIVE"),
        (image_a, "ORIGINAL"),
    ]):
        image_x = x + column * (IMAGE_WIDTH + 20)

        draw.text(
            (image_x, image_y),
            f"{label}: {Path(path).name}",
            fill="black",
            font=font,
        )

        image = load_thumbnail(path)

        paste_x = image_x + (IMAGE_WIDTH - image.width) // 2
        paste_y = image_y + 20 + (
            IMAGE_HEIGHT - image.height
        ) // 2

        sheet.paste(image, (paste_x, paste_y))


def create_batch(batch_number, batch):
    rows = 5
    width = MARGIN * 3 + PAIR_WIDTH * COLUMNS
    height = (
        HEADER_HEIGHT
        + MARGIN
        + rows * (PAIR_HEIGHT + MARGIN)
    )

    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=16)

    draw.text(
        (MARGIN, 20),
        f"HARD-NEGATIVE CONSENSUS REVIEW - BATCH {batch_number:02d}",
        fill="black",
        font=font,
    )

    for index, row in enumerate(batch):
        column = index % COLUMNS
        row_number = index // COLUMNS

        x = MARGIN + column * (PAIR_WIDTH + MARGIN)
        y = HEADER_HEIGHT + row_number * (
            PAIR_HEIGHT + MARGIN
        )

        draw_pair(
            sheet,
            draw,
            row,
            (batch_number - 1) * BATCH_SIZE + index + 1,
            x,
            y,
            font,
        )

    output = (
        OUTPUT_DIR
        / f"hard_negative_consensus_review_batch_{batch_number:02d}.jpg"
    )

    if output.exists():
        raise FileExistsError(
            f"Refusing to overwrite: {output}"
        )

    sheet.save(output, quality=94)

    print(
        f"Created {output.relative_to(ROOT)} "
        f"({len(batch)} pairs, {sheet.width} x {sheet.height})"
    )


def main():
    candidates = load_candidates()

    if len(candidates) != 50:
        raise ValueError(
            f"Expected 50 unreviewed consensus pairs, "
            f"found {len(candidates)}. Check source results."
        )

    total_batches = (
        len(candidates) + BATCH_SIZE - 1
    ) // BATCH_SIZE

    outputs = [
        OUTPUT_DIR
        / f"hard_negative_consensus_review_batch_{number:02d}.jpg"
        for number in range(1, total_batches + 1)
    ]

    existing = [path for path in outputs if path.exists()]

    if existing:
        raise FileExistsError(
            f"Review sheets already exist: {existing}"
        )

    for batch_number in range(1, total_batches + 1):
        start = (batch_number - 1) * BATCH_SIZE
        batch = candidates[start:start + BATCH_SIZE]
        create_batch(batch_number, batch)

    print()
    print(f"Unreviewed consensus pairs: {len(candidates)}")
    print(f"Previously reviewed pairs excluded: {len(REVIEWED_PAIRS)}")
    print(f"Contact sheets created: {total_batches}")


if __name__ == "__main__":
    main()

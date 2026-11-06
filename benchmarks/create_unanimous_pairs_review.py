"""Create a side-by-side review sheet for unanimous detector matches."""

from pathlib import Path

from PIL import Image, ImageOps, ImageDraw


ROOT = Path(__file__).resolve().parent.parent

OUTPUT = (
    ROOT
    / "benchmarks"
    / "results"
    / "hard_negative_unanimous_pairs_review.jpg"
)

PAIRS = [
    ("22.35.33", "22.35.32"),
    ("22.50.40", "22.50.38"),
    ("22.57.33", "22.57.32"),
    ("23.21.05", "23.21.02"),
    ("23.21.19", "23.21.18"),
]

NEGATIVE_DIR = ROOT / "TestMedia" / "HardNegatives"
ORIGINAL_DIR = ROOT / "TestMedia" / "Originals"

CELL_WIDTH = 700
CELL_HEIGHT = 440
LABEL_HEIGHT = 35
ROW_HEIGHT = CELL_HEIGHT + LABEL_HEIGHT + 35
MARGIN = 20
HEADER_HEIGHT = 55

sheet = Image.new(
    "RGB",
    (
        MARGIN * 3 + CELL_WIDTH * 2,
        HEADER_HEIGHT + ROW_HEIGHT * len(PAIRS) + MARGIN,
    ),
    "white",
)

draw = ImageDraw.Draw(sheet)
draw.text(
    (MARGIN, 15),
    "UNANIMOUS DETECTOR MATCHES - HARD NEGATIVE REVIEW",
    fill="black",
)

for index, (negative_stem, original_stem) in enumerate(PAIRS):
    negative_path = NEGATIVE_DIR / f"2024-12-03 {negative_stem}.jpg"
    original_path = ORIGINAL_DIR / f"2024-12-03 {original_stem}.jpg"

    if not negative_path.is_file():
        raise FileNotFoundError(negative_path)

    if not original_path.is_file():
        raise FileNotFoundError(original_path)

    y = HEADER_HEIGHT + index * ROW_HEIGHT

    draw.text(
        (MARGIN, y),
        f"PAIR {index + 1}: {negative_stem} vs {original_stem}",
        fill="black",
    )

    for column, (path, label) in enumerate([
        (negative_path, f"HARD NEGATIVE - {negative_stem}"),
        (original_path, f"ORIGINAL - {original_stem}"),
    ]):
        x = MARGIN + column * (CELL_WIDTH + MARGIN)

        draw.text(
            (x, y + LABEL_HEIGHT),
            label,
            fill="black",
        )

        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((CELL_WIDTH - 20, CELL_HEIGHT - 20))

        paste_x = x + (CELL_WIDTH - image.width) // 2
        paste_y = y + LABEL_HEIGHT + (
            CELL_HEIGHT - image.height
        ) // 2

        sheet.paste(image, (paste_x, paste_y))

if OUTPUT.exists():
    raise FileExistsError(
        f"Refusing to overwrite existing file: {OUTPUT}"
    )

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
sheet.save(OUTPUT, quality=94)

print(f"Created: {OUTPUT.relative_to(ROOT)}")
print(f"Dimensions: {sheet.width} x {sheet.height}")
print(f"Pairs: {len(PAIRS)}")
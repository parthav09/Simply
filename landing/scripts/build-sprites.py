"""Build the shopper sprite sheet from Kenney's RPG Urban Pack (CC0).

    python3 scripts/build-sprites.py

Writes public/sprites/shoppers.png and ui/shopperSprites.json. Requires Pillow.

Sheet layout: one row per (sprite, direction), directions ordered down/left/right/up;
four columns per row: idle, step A, idle, step B, so a 4-step CSS animation
walks and column 0 is the standing pose.
"""

import colorsys
import io
import json
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

PACK_URL = (
    "https://kenney.nl/media/pages/assets/rpg-urban-pack/"
    "0a097d1dc7-1677578575/kenney_rpg-urban-pack.zip"
)
SOURCE_TILE = 16
# Drawn at 2x with a black contour so the figures stay crisp and readable on the floor.
TILE = 32
# Characters live in the right-most 4 columns of tilemap_packed.png; each takes
# 3 rows (idle, step A, step B) and its columns face left, down, up, right.
CHAR_COL = 23
SOURCE_DIR_COL = {"down": 1, "left": 0, "right": 3, "up": 2}
DIRS = ["down", "left", "right", "up"]
FRAME_ROWS = [0, 1, 0, 2]

ROOT = Path(__file__).resolve().parent.parent

GREEN = ("#42a379", "#369069")
RED = ("#c2504d", "#a54240")
BAND_ORANGE = ("#c77b47", "#a9673b")
BALD_GREY = ("#aaa8bd", "#898ca6")
BLACK_HAIR = ("#373733", "#50504a", "#60605a")

# Destinations are pushed toward solid, saturated cloth so a figure reads at a glance.
SHIRTS = {
    "green": ("#1f9d4a", "#147536"),
    "red": ("#e23b3b", "#b42323"),
    "blue": ("#2f6bff", "#1d45c4"),
    "teal": ("#0d9aa8", "#0a7380"),
    "purple": ("#8b3fd4", "#6a24ad"),
    "gold": ("#f0b400", "#c48a00"),
    "pink": ("#ee4d8b", "#c42868"),
    "navy": ("#2c3e66", "#1e2c4d"),
}
HAIR = {
    "brown": ("#3f2a22", "#5e3b2c", "#714a36"),
    "blonde": ("#8a6630", "#c99a44", "#ddb35a"),
    "grey": ("#5f5e70", "#9a99ac", "#b7b6c6"),
    "silver": ("#6d6c7c", "#b9b8c8", "#d6d5e0"),
}


def swap(src, dst):
    return dict(zip(src, dst))


# (id, group, source character index, colour swaps)
SPRITES = [
    ("young-man-green", "young_man", 0, {}),
    ("young-man-blue", "young_man", 0, swap(GREEN, SHIRTS["blue"])),
    ("young-man-gold", "young_man", 0, swap(GREEN, SHIRTS["gold"])),
    ("woman-red", "woman", 1, {}),
    ("woman-blue", "woman", 1, swap(RED, SHIRTS["blue"])),
    ("woman-teal", "woman", 1, swap(RED, SHIRTS["teal"])),
    ("woman-purple", "woman", 1, swap(RED, SHIRTS["purple"])),
    ("woman-headband", "woman", 5, {}),
    ("woman-headband-brown", "woman", 5, {**swap(BLACK_HAIR, HAIR["brown"]), **swap(BAND_ORANGE, SHIRTS["green"])}),
    ("woman-headband-blonde", "woman", 5, {**swap(BLACK_HAIR, HAIR["blonde"]), **swap(BAND_ORANGE, SHIRTS["blue"])}),
    ("woman-headband-pink", "woman", 5, swap(BAND_ORANGE, SHIRTS["pink"])),
    ("senior-woman-grey", "senior_woman", 5, {**swap(BLACK_HAIR, HAIR["grey"]), **swap(BAND_ORANGE, SHIRTS["purple"])}),
    ("senior-woman-silver", "senior_woman", 5, {**swap(BLACK_HAIR, HAIR["silver"]), **swap(BAND_ORANGE, SHIRTS["teal"])}),
    ("senior-woman-rose", "senior_woman", 5, {**swap(BLACK_HAIR, HAIR["grey"]), **swap(BAND_ORANGE, SHIRTS["red"])}),
    ("senior-man", "senior_man", 2, {}),
    ("senior-man-blue", "senior_man", 2, swap(GREEN, SHIRTS["blue"])),
    ("worker", "worker", 3, {}),
    ("man-navy", "man", 4, swap(BALD_GREY, SHIRTS["navy"])),
    ("man-blue", "man", 4, swap(BALD_GREY, SHIRTS["blue"])),
    ("man-green", "man", 4, swap(BALD_GREY, SHIRTS["green"])),
]

# The pack draws every contour in this muddy brown, which vanishes on the floor.
CONTOUR = (0x8D, 0x52, 0x43)
INK = (12, 10, 8)


def rgb(hex_color):
    return tuple(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))


def punch(r, g, b):
    """Blacken the contour and push the remaining colours away from the floor."""
    if (r, g, b) == CONTOUR:
        return INK
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if s < 0.16:
        v = min(0.72, v * 0.85)
        return tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h, s, v))
    s = min(1.0, s * 1.45 + 0.1)
    v = min(1.0, v * 1.06)
    return tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h, s, v))


def recolor(tile, swaps):
    table = {rgb(k): rgb(v) for k, v in swaps.items()}
    px = tile.load()
    for y in range(tile.height):
        for x in range(tile.width):
            r, g, b, a = px[x, y]
            if not a:
                continue
            if (r, g, b) in table:
                r, g, b = table[(r, g, b)]
            px[x, y] = (*punch(r, g, b), 255)
    return tile.resize((TILE, TILE), Image.NEAREST)


def main():
    with urllib.request.urlopen(PACK_URL) as resp:
        pack = zipfile.ZipFile(io.BytesIO(resp.read()))
    with pack.open("Tilemap/tilemap_packed.png") as f:
        source = Image.open(f).convert("RGBA")

    sheet = Image.new("RGBA", (TILE * len(FRAME_ROWS), TILE * len(DIRS) * len(SPRITES)))
    for s, (_, _, char, swaps) in enumerate(SPRITES):
        for d, direction in enumerate(DIRS):
            sx = (CHAR_COL + SOURCE_DIR_COL[direction]) * SOURCE_TILE
            for f, frame_row in enumerate(FRAME_ROWS):
                sy = (char * 3 + frame_row) * SOURCE_TILE
                tile = recolor(source.crop((sx, sy, sx + SOURCE_TILE, sy + SOURCE_TILE)), swaps)
                sheet.paste(tile, (f * TILE, (s * len(DIRS) + d) * TILE))

    out = ROOT / "public" / "sprites"
    out.mkdir(parents=True, exist_ok=True)
    sheet.save(out / "shoppers.png", optimize=True)
    manifest = {
        "src": "/sprites/shoppers.png",
        "tile": TILE,
        "frames": len(FRAME_ROWS),
        "directions": DIRS,
        "sprites": [{"id": sid, "group": group} for sid, group, _, _ in SPRITES],
    }
    (ROOT / "ui" / "shopperSprites.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {len(SPRITES)} sprites to {out / 'shoppers.png'}")


if __name__ == "__main__":
    main()

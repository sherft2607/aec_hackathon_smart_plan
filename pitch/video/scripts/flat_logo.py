"""Build the flat top-bar logo: an upright mosaic "4" beside the existing "Site" box.

The source logo leans its 4, which smears at 30 px. This keeps the "Site" box as drawn
and sets an upright 4 on the same 4 px mosaic grid, then makes the paper transparent so
the dark theme can invert it cleanly.

    /usr/bin/python3 pitch/video/scripts/flat_logo.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "web/src/design/brand/4site-logo.png"
OUT = ROOT / "web/src/design/brand/4site-logo-flat.png"
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"

PITCH, CELL = 4, 3
INK = (26, 26, 26)
SHADE = (150, 150, 150)
BOX = (296, 98, 720, 309)  # the dashed "Site" box in the source logo
GAP = 24
PAD = 6


def glyph_mask(height: int) -> Image.Image:
    for index in range(12):
        try:
            font = ImageFont.truetype(FONT, 400, index=index)
        except OSError:
            break
        if "Bold" in " ".join(font.getname()) and "Condensed" not in " ".join(font.getname()):
            break
    left, top, right, bottom = font.getbbox("4")
    canvas = Image.new("L", (right - left + 20, bottom - top + 20), 0)
    ImageDraw.Draw(canvas).text((10 - left, 10 - top), "4", font=font, fill=255)
    canvas = canvas.crop(canvas.getbbox())
    width = round(canvas.width * height / canvas.height)
    return canvas.resize((width, height), Image.LANCZOS)


def mosaic(mask: Image.Image, colour, into: Image.Image, origin) -> None:
    draw = ImageDraw.Draw(into)
    ox, oy = origin
    for cy in range(0, mask.height, PITCH):
        for cx in range(0, mask.width, PITCH):
            sample = mask.getpixel((min(cx + PITCH // 2, mask.width - 1), min(cy + PITCH // 2, mask.height - 1)))
            if sample > 110:
                x, y = ox + cx, oy + cy
                draw.rectangle((x, y, x + PITCH - 1, y + PITCH - 1), fill=grout(colour))
                draw.rectangle((x, y, x + CELL - 1, y + CELL - 1), fill=colour)


def grout(colour):
    return tuple(round(c + (255 - c) * 0.38) for c in colour)


def main() -> None:
    source = Image.open(SRC).convert("RGB")
    site = source.crop(BOX)
    height = site.height
    four = glyph_mask(height - 2 * PITCH)
    shadow = 2 * PITCH
    width = PAD + four.width + shadow + GAP + site.width + PAD
    out = Image.new("RGB", (width, height + 2 * PAD), (255, 255, 255))
    top = PAD + PITCH
    mosaic(four, SHADE, out, (PAD + shadow, top + shadow - PITCH))
    mosaic(four, INK, out, (PAD, top - PITCH))
    out.paste(site, (PAD + four.width + shadow + GAP, PAD))

    rgba = out.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, _ = pixels[x, y]
            if max(r, g, b) - min(r, g, b) > 60:
                continue
            lightness = (r + g + b) / 3
            alpha = max(0, min(255, round((255 - lightness) * 255 / 200)))
            if alpha:
                scale = 255 / alpha
                pixels[x, y] = (
                    max(0, min(255, round(255 - (255 - r) * scale))),
                    max(0, min(255, round(255 - (255 - g) * scale))),
                    max(0, min(255, round(255 - (255 - b) * scale))),
                    alpha,
                )
            else:
                pixels[x, y] = (255, 255, 255, 0)
    rgba.save(OUT, optimize=True)
    print(OUT, rgba.size)


if __name__ == "__main__":
    main()

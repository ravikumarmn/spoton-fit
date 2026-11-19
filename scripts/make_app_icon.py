"""Draw the SpotOn app icon (an original mark): a progress ring with a centre dot.

    .venv/bin/python scripts/make_app_icon.py

Writes mobile/assets/icon/{icon,foreground,monochrome}.png (1024 px) and the launch-screen
images splash_logo.png and splash_android12.png. The ring echoes the
calorie ring on the Today screen; the dot is the "spot" in SpotOn. Then run
`dart run flutter_launcher_icons` and `dart run flutter_native_splash:create` in mobile/
to generate the Android and iOS sizes. The in-app logo (AppMark) draws the same shape.
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "mobile" / "assets" / "icon"
SAGE = (43, 122, 104, 255)  # AppColors.primary #2B7A68
WHITE = (255, 255, 255, 255)
TRACK = (255, 255, 255, 80)
S = 4  # supersampling for smooth edges
N = 1024 * S


def mark(scale: float, track: bool = True) -> Image.Image:
    """The ring + dot on a transparent canvas; `scale` = ring diameter / canvas."""
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = N / 2
    r = N * scale / 2
    w = round(N * scale * 0.17)  # stroke
    box = (c - r, c - r, c + r, c + r)
    if track:
        d.ellipse(box, outline=TRACK, width=w)
    start, end = -90, 200  # about 80% of the circle, from 12 o'clock clockwise
    d.arc(box, start, end, fill=WHITE, width=w)
    # round caps
    import math

    rm = r - w / 2
    for a in (start, end):
        x, y = c + rm * math.cos(math.radians(a)), c + rm * math.sin(math.radians(a))
        d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=WHITE)
    dot = N * scale * 0.24 / 2
    d.ellipse((c - dot, c - dot, c + dot, c + dot), fill=WHITE)
    return img


def save(img: Image.Image, name: str) -> None:
    img.resize((1024, 1024), Image.LANCZOS).save(OUT / name)


def save_size(img: Image.Image, name: str, px: int) -> None:
    img.resize((px, px), Image.LANCZOS).save(OUT / name)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    full = Image.new("RGBA", (N, N), SAGE)
    full.alpha_composite(mark(0.62))
    save(full.convert("RGB"), "icon.png")  # iOS and legacy Android (no transparency)
    # Android adaptive icons: flutter_launcher_icons insets the foreground by 16% per side, and
    # launchers show a shape inside the 66% safe zone. 0.68 * (1 - 2 * 0.16) = a ring of 46%.
    save(mark(0.68), "foreground.png")
    save(mark(0.68, track=False), "monochrome.png")  # Android 13 themed icons tint this
    # Launch screen (Android < 12 and iOS): the icon as a rounded square, 72 dp at 4x.
    tile = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, N - 1, N - 1), radius=round(N * 0.28), fill=SAGE)
    tile.alpha_composite(mark(0.62))
    tile.resize((288, 288), Image.LANCZOS).save(OUT / "splash_logo.png")
    # Android 12+ launch screen: the system draws the sage circle (icon_background_color);
    # the image is 1152 px and must fit a 768 px circle.
    save_size(mark(0.42), "splash_android12.png", 1152)
    print(f"wrote icons to {OUT}")


if __name__ == "__main__":
    main()

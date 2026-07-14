"""Composite pathman foreground artwork onto a rounded gradient plate (run from repo root or pathman/)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def rounded_plate_rgba(
    size: int,
    *,
    inset: int,
    radius: int,
    rgb_top: tuple[int, int, int],
    rgb_bottom: tuple[int, int, int],
) -> Image.Image:
    """RGBA image: vertical gradient inside a rounded rectangle; transparent outside."""
    h = w = size
    top = np.array(rgb_top, dtype=np.float32)
    bot = np.array(rgb_bottom, dtype=np.float32)
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, np.newaxis]
    row_rgb = top * (1.0 - t) + bot * t
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[:, :, :3] = np.round(row_rgb[:, np.newaxis, :]).astype(np.uint8)

    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (inset, inset, w - 1 - inset, h - 1 - inset),
        radius=radius,
        fill=255,
    )
    ma = np.array(mask)
    arr[:, :, 3] = ma
    im = Image.fromarray(arr, "RGBA")
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle(
        (inset, inset, w - 1 - inset, h - 1 - inset),
        radius=radius,
        outline=(140, 230, 232, 220),
        width=max(1, size // 128),
    )
    return im


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--fg",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "assets" / "icon_foreground.png",
        help="Transparent foreground PNG (artwork only)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "assets" / "icon.png",
    )
    p.add_argument(
        "--ico-out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "assets" / "pathman.ico",
        help="Optional multi-size Windows .ico (from --out PNG or --fg composite)",
    )
    p.add_argument("--size", type=int, default=256)
    args = p.parse_args()

    fg_path = args.fg
    if not fg_path.is_file():
        raise SystemExit(f"Missing foreground PNG: {fg_path}")

    fg = Image.open(fg_path).convert("RGBA")
    if fg.size != (args.size, args.size):
        fg = fg.resize((args.size, args.size), Image.Resampling.LANCZOS)

    inset = max(8, args.size // 32)
    radius = max(28, args.size // 6)
    bg = rounded_plate_rgba(
        args.size,
        inset=inset,
        radius=radius,
        rgb_top=(9, 74, 77),  # darker teal
        rgb_bottom=(18, 130, 133),  # #127e85-ish
    )

    out = Image.alpha_composite(bg, fg)
    out.save(args.out, format="PNG", optimize=True)
    print(f"Wrote {args.out} ({args.size}x{args.size})")
    write_ico(out, args.ico_out)


def write_ico(source: Image.Image, ico_path: Path) -> None:
    """Write a Windows .ico with common shell/taskbar sizes."""
    sizes = (16, 32, 48, 64, 128, 256)
    base = source.convert("RGBA")
    images = [base.resize((s, s), Image.Resampling.LANCZOS) for s in sizes]
    images[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"Wrote {ico_path} ({', '.join(str(s) for s in sizes)} px)")


if __name__ == "__main__":
    main()

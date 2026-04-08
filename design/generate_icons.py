#!/usr/bin/env python3
"""
Generate all logo assets from logo-source.svg.

Reads design/logo-source.svg and produces every icon file required by
docs/designer-brief-logo.md.  Uses sharp-cli (npx) for SVG→PNG conversion,
Pillow for compositing, and macOS iconutil for the .icns bundle.

Usage:
    python3 design/generate_icons.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image

# ── paths ──────────────────────────────────────────────────────────────
PROJECT = Path(__file__).resolve().parent.parent
DESIGN  = PROJECT / "design"
BUILD   = PROJECT / "build"
PUBLIC  = PROJECT / "public"
ASSETS  = PROJECT / "src" / "renderer" / "assets"

SVG_SRC = DESIGN / "logo-source.svg"

# ── brand colours ──────────────────────────────────────────────────────
PARCHMENT = (0xFB, 0xF9, 0xF3)
DARK_BG   = (0x1A, 0x1C, 0x1E)


# ── helpers ────────────────────────────────────────────────────────────
def sharp_svg_to_png(svg_path: Path, png_path: Path, size: int):
    """Render SVG to PNG at *size*×*size* using sharp-cli."""
    png_path.parent.mkdir(parents=True, exist_ok=True)
    # sharp-cli uses subcommand syntax: sharp -i IN -o OUT resize W H -- -f png
    out_dir = png_path.parent
    cmd = [
        "npx", "sharp-cli",
        "-i", str(svg_path),
        "-o", str(out_dir),
        "resize", str(size), str(size),
        "--", "-f", "png",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    # sharp writes output using the input filename stem in the output dir
    candidate = out_dir / (svg_path.stem + ".png")
    if candidate.exists() and candidate != png_path:
        candidate.rename(png_path)


def render(svg_path: Path, size: int, bg_color=None) -> Image.Image:
    """Return a PIL Image rendered from the SVG at *size* px."""
    tmp = DESIGN / f"_tmp_{size}.png"
    sharp_svg_to_png(svg_path, tmp, size)
    img = Image.open(tmp).convert("RGBA")
    tmp.unlink(missing_ok=True)

    if bg_color:
        bg = Image.new("RGBA", (size, size), bg_color + (255,))
        return Image.alpha_composite(bg, img).convert("RGB")
    return img


def save(img: Image.Image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), "PNG")
    print(f"  {path.relative_to(PROJECT)}  ({img.size[0]}×{img.size[1]})")


def build_iconset(svg_path: Path) -> Path:
    """Create a macOS .iconset directory and return its path."""
    iconset = BUILD / "icon.iconset"
    iconset.mkdir(parents=True, exist_ok=True)

    entries = [
        (16,   "icon_16x16.png"),
        (32,   "icon_16x16@2x.png"),
        (32,   "icon_32x32.png"),
        (64,   "icon_32x32@2x.png"),
        (128,  "icon_128x128.png"),
        (256,  "icon_128x128@2x.png"),
        (256,  "icon_256x256.png"),
        (512,  "icon_256x256@2x.png"),
        (512,  "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]
    for size, name in entries:
        img = render(svg_path, size)
        img.save(str(iconset / name), "PNG")
    print(f"  build/icon.iconset/  (10 sizes)")
    return iconset


def build_ico(svg_path: Path, sizes: list[int], out: Path):
    """Create a Windows .ico with the given sizes."""
    images = [render(svg_path, s).convert("RGBA") for s in sizes]
    out.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        str(out),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"  {out.relative_to(PROJECT)}")


def run_iconutil():
    """Convert .iconset → .icns via macOS iconutil."""
    icns = BUILD / "icon.icns"
    subprocess.run(
        ["iconutil", "-c", "icns", str(BUILD / "icon.iconset"), "-o", str(icns)],
        check=True,
    )
    print(f"  {icns.relative_to(PROJECT)}")


# ── main ───────────────────────────────────────────────────────────────
def main():
    if not SVG_SRC.exists():
        sys.exit(f"ERROR: {SVG_SRC} not found. Place your SVG there first.")

    print("Generating logo assets from", SVG_SRC.name, "\n")

    # 1. macOS 1024 px PNG
    print("1. macOS icon_1024.png")
    save(render(SVG_SRC, 1024), BUILD / "icon_1024.png")

    # 2. macOS .icns
    print("\n2. macOS icon.icns")
    build_iconset(SVG_SRC)
    run_iconutil()

    # 3. Windows .ico
    print("\n3. Windows icon.ico")
    build_ico(SVG_SRC, [16, 32, 48, 64, 128, 256], BUILD / "icon.ico")

    # 4. Web / favicons
    print("\n4. Favicon assets")
    for sz in (16, 32):
        save(render(SVG_SRC, sz), PUBLIC / f"favicon-{sz}.png")

    shutil.copy2(str(SVG_SRC), str(PUBLIC / "favicon.svg"))
    print(f"  public/favicon.svg  (copy of source)")

    save(render(SVG_SRC, 180), PUBLIC / "apple-touch-icon.png")

    # 5. Splash / about panel
    print("\n5. Splash logos")
    save(render(SVG_SRC, 512, bg_color=PARCHMENT), ASSETS / "logo-light.png")
    save(render(SVG_SRC, 512, bg_color=DARK_BG),   ASSETS / "logo-dark.png")

    # Cleanup iconset (intermediate artefact)
    shutil.rmtree(str(BUILD / "icon.iconset"), ignore_errors=True)

    print("\nDone.")


if __name__ == "__main__":
    main()

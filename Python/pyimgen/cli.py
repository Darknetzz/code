#!/usr/bin/env python3
"""CLI for generating space images (procedural for now)."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).resolve().parent))

from imagegen.core.procedural import ProceduralSpaceGenerator

app = typer.Typer(
    help="Generate procedural space images (nebula, stars, galaxy, deep_space).",
)
console = Console()


def _open_with_default_app(path: Path) -> None:
    """Open path with the system default application. No-op if unsupported or headless."""
    path = path.resolve()
    if not path.exists():
        return
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except OSError:
        pass


@app.command()
def main(
    prompt: str = typer.Argument(
        "deep_space",
        help="Preset or hint: nebula, stars, galaxy, deep_space (default)",
    ),
    output: Path = typer.Option(
        Path("output.png"),
        "--output",
        "-o",
        path_type=Path,
        help="Output file path",
    ),
    width: int = typer.Option(1024, "--width", "-W", help="Image width in pixels"),
    height: int = typer.Option(1024, "--height", "-H", help="Image height in pixels"),
    seed: Optional[int] = typer.Option(None, "--seed", "-s", help="Random seed for reproducible output"),
    open_after: bool = typer.Option(False, "--open", help="Open the generated image with the default viewer"),
    star_density: float = typer.Option(
        1.0,
        "--star-density",
        help="Star count multiplier (e.g. 0.5 = fewer, 2.0 = more)",
    ),
    star_min_brightness: float = typer.Option(
        0.5,
        "--star-min-brightness",
        min=0.0,
        max=1.0,
        help="Only draw stars at or above this brightness (reduces faint speckle; 0 = all stars)",
    ),
    nebula_strength: float = typer.Option(
        1.0,
        "--nebula-strength",
        help="Nebula intensity (0 = dark only, 1 = default)",
    ),
    nebula_smooth: int = typer.Option(
        1,
        "--nebula-smooth",
        min=0,
        help="Blur radius for nebula to reduce grain (0 = off)",
    ),
    color_style: str = typer.Option(
        "cosmic",
        "--color-style",
        help="Color palette: cosmic (all), cool (blues/purples/cyans), warm (oranges/reds/golds)",
    ),
    color_jitter: float = typer.Option(
        0.1,
        "--color-jitter",
        min=0.0,
        max=0.4,
        help="Random variation in chosen colors (0 = none)",
    ),
) -> None:
    """Generate a procedural space image and save it to a file."""
    if width < 1 or height < 1:
        console.print("[red]Error:[/] Width and height must be positive.", err=True)
        raise typer.Exit(1)

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with console.status("Generating image…"):
        gen = ProceduralSpaceGenerator(default_seed=seed)
        img = gen.generate(
            prompt=prompt,
            width=width,
            height=height,
            seed=seed,
            star_density=star_density,
            star_brightness_min=star_min_brightness,
            nebula_strength=nebula_strength,
            nebula_smooth=nebula_smooth,
            color_style=color_style,
            color_jitter=color_jitter,
        )
        img.save(output)

    console.print(f"Saved: [bold green]{output}[/]")
    if open_after:
        _open_with_default_app(output)


if __name__ == "__main__":
    app()

# pyimgen (Imagegen)

> **Future Rust candidate (tier 2):** No Rust port yet. The procedural pixel core would benefit from native speed; the FastAPI UI would likely stay Python or become a thin wrapper.

Procedural space image generator (nebula, stars, galaxy). Python core; API-backed generation can be added later. Lives in the `code` repo under `Python/pyimgen`.

## Setup

```bash
pip install -r requirements.txt
```

## CLI

Generate an image (default: `deep_space` — nebula + stars):

```bash
python cli.py -o out.png
```

Presets (use as prompt): `nebula`, `stars`, `galaxy`, `deep_space`.

```bash
python cli.py nebula -o nebula.png
python cli.py galaxy -o galaxy.png -W 800 -H 600
python cli.py stars -o stars.png --seed 42
```

Options: `-o` output path, `-W`/`-H` size, `-s`/`--seed` for reproducibility.

**Star and nebula tuning** (reduce noise / faint speckle in front of stars):

| Option | Default | Effect |
|--------|--------|--------|
| `--star-density` | 1.0 | Star count multiplier (e.g. `0.5` = fewer, `2` = more). |
| `--star-min-brightness` | 0.5 | Only draw stars at or above this (0–1). Use `0` for all stars including faint. |
| `--nebula-strength` | 1.0 | Nebula intensity (`0` = dark only, `1` = current). |
| `--nebula-smooth` | 1 | Blur radius for nebula (`0` = off, `1` or `2` = smoother, less grain). |
| `--color-style` | cosmic | Palette: `cosmic` (all), `cool` (blues/purples/cyans), `warm` (oranges/reds/golds). |
| `--color-jitter` | 0.1 | Random variation in colors (0–0.4; 0 = none). |

Examples:

```bash
# Default (cleaner stars, light nebula smooth)
python cli.py deep_space -o out.png

# Even cleaner: only brighter stars, smoother nebula
python cli.py deep_space -o out.png --star-min-brightness 0.6 --nebula-smooth 2

# More stars, no brightness cutoff
python cli.py deep_space -o out.png --star-min-brightness 0 --star-density 1.5

# Softer nebula so stars stand out more
python cli.py deep_space -o out.png --nebula-strength 0.7

# Cool palette only (blues, purples, cyans)
python cli.py nebula -o out.png --color-style cool

# Warm colors with more variation
python cli.py deep_space -o out.png --color-style warm --color-jitter 0.2
```

## Web GUI

Run the web interface (same options as the CLI, in a browser):

```bash
uvicorn server:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). Use the form to pick preset, size, seed, and star/nebula tuning; click **Generate** to create an image and **Download PNG** to save it.

## As a library

```python
from imagegen.core.procedural import ProceduralSpaceGenerator

gen = ProceduralSpaceGenerator()
img = gen.generate(
    prompt="nebula",
    width=1024,
    height=1024,
    seed=123,
    star_brightness_min=0.5,
    nebula_smooth=1,
)
img.save("nebula.png")
```

Run from the `pyimgen` directory so the `imagegen` package is on the path (or install in development mode).

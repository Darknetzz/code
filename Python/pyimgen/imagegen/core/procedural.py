"""Procedural space image generation (nebulas, starfields, galaxies)."""

import random
from typing import Any, List, Optional, Tuple

import numpy as np
from PIL import Image

from imagegen.core.base import Generator

# Wide cosmic palette: blues, purples, magentas, cyans, teals, oranges, reds, yellows
_COSMIC_COLORS: List[Tuple[float, float, float]] = [
    (0.08, 0.04, 0.35),   # dark blue
    (0.25, 0.08, 0.45),   # purple
    (0.45, 0.08, 0.4),    # magenta
    (0.08, 0.35, 0.45),   # cyan
    (0.12, 0.4, 0.35),    # teal
    (0.4, 0.2, 0.08),     # orange/brown
    (0.5, 0.12, 0.1),     # red
    (0.45, 0.4, 0.12),   # gold/yellow
    (0.15, 0.25, 0.5),   # blue
    (0.35, 0.15, 0.5),   # violet
]

# Sub-palettes for color_style
_COSMIC_COOL: List[Tuple[float, float, float]] = [
    _COSMIC_COLORS[i] for i in (0, 1, 3, 4, 8, 9)  # blues, purples, cyans, teals, violet
]
_COSMIC_WARM: List[Tuple[float, float, float]] = [
    _COSMIC_COLORS[i] for i in (2, 5, 6, 7, 1)  # magenta, orange, red, gold, purple
]

COLOR_STYLES = ("cosmic", "cool", "warm")


def _get_palette_for_style(style: str) -> List[Tuple[float, float, float]]:
    if style == "cool":
        return _COSMIC_COOL
    if style == "warm":
        return _COSMIC_WARM
    return _COSMIC_COLORS


def _palette_from_seed(
    seed: Optional[int],
    n: int = 4,
    shuffle: bool = True,
    jitter: float = 0.12,
    style: str = "cosmic",
) -> List[Tuple[float, float, float]]:
    """Pick n colors from the palette for the given style, shuffled and jittered by seed."""
    source = _get_palette_for_style(style)
    rng = random.Random(seed)
    indices = list(range(len(source)))
    if shuffle:
        rng.shuffle(indices)
    out: List[Tuple[float, float, float]] = []
    for i in range(n):
        r, g, b = source[indices[i % len(indices)]]
        if jitter > 0:
            r = np.clip(r + rng.uniform(-jitter, jitter), 0.02, 0.95)
            g = np.clip(g + rng.uniform(-jitter, jitter), 0.02, 0.95)
            b = np.clip(b + rng.uniform(-jitter, jitter), 0.02, 0.95)
        out.append((r, g, b))
    return out


def _noise_layer(
    width: int,
    height: int,
    scale: float = 0.005,
    octaves: int = 4,
    seed: Optional[int] = None,
) -> np.ndarray:
    """Coherent 2D noise in [0, 1] using multiple octaves of sine-based noise."""
    if seed is not None:
        np.random.seed(seed)
    out = np.zeros((height, width), dtype=np.float64)
    for octave in range(octaves):
        freq = scale * (2 ** octave)
        phase = np.random.uniform(0, 2 * np.pi, (1, 1))
        y = np.linspace(0, height * freq, height, endpoint=False)
        x = np.linspace(0, width * freq, width, endpoint=False)
        xx, yy = np.meshgrid(x, y)
        # Simple coherent-ish noise: layered sine waves with random phase shifts
        layer = (
            np.sin(xx + phase) * np.sin(yy * 1.3 + phase * 0.7)
            + np.sin((xx + yy) * 0.7 + phase * 1.1)
        ) / 3.0
        out += (layer + 1) / 2 * (0.5 ** octave)
    out = out / out.max() if out.max() > 0 else out
    return np.clip(out, 0, 1).astype(np.float32)


def _box_blur_2d(arr: np.ndarray, radius: int) -> np.ndarray:
    """2D uniform box blur; output same shape as input. radius 1 = 3x3, 2 = 5x5."""
    if radius <= 0:
        return arr
    H, W = arr.shape
    pad = np.pad(arr, radius, mode="edge")
    k = 2 * radius + 1
    out = np.zeros((H, W), dtype=np.float64)
    for di in range(k):
        for dj in range(k):
            out += pad[di : di + H, dj : dj + W]
    out /= k * k
    return out.astype(arr.dtype)


def _box_blur(arr: np.ndarray, radius: int) -> np.ndarray:
    """Box blur; (H,W) or (H,W,C). radius 0 = no blur. Output same shape as input."""
    if radius <= 0 or arr.size == 0:
        return arr
    if arr.ndim == 3:
        return np.stack([_box_blur_2d(arr[:, :, c], radius) for c in range(arr.shape[2])], axis=-1)
    return _box_blur_2d(arr, radius)


def _starfield(
    width: int,
    height: int,
    density: float = 0.00015,
    seed: Optional[int] = None,
    min_brightness: float = 0.0,
) -> np.ndarray:
    """Single-channel starfield. min_brightness: only draw stars at or above this (0–1) to avoid faint speckle."""
    rng = random.Random(seed)
    out = np.zeros((height, width), dtype=np.float32)
    n = int(width * height * density)
    brightness_choices = [0.25, 0.45, 0.65, 0.85, 1.0]
    weights = [0.35, 0.35, 0.18, 0.09, 0.03]
    for _ in range(n):
        x = rng.randint(0, width - 1)
        y = rng.randint(0, height - 1)
        b = rng.choices(brightness_choices, weights=weights, k=1)[0]
        if b < min_brightness:
            continue
        out[y, x] = max(out[y, x], b)
        if b >= 0.85 and width > 2 and height > 2:
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width and (dx != 0 or dy != 0):
                        out[ny, nx] = max(out[ny, nx], b * 0.4)
    return out


class ProceduralSpaceGenerator(Generator):
    """
    Generates space-like images procedurally: nebulas, starfields, galaxies.
    Uses 'prompt' as a preset hint: nebula, stars, galaxy, deep_space (default).
    """

    PRESETS = ("nebula", "stars", "galaxy", "deep_space")

    def __init__(self, default_seed: Optional[int] = None):
        self.default_seed = default_seed

    def _parse_preset(self, prompt: str) -> str:
        p = prompt.strip().lower() or "deep_space"
        for preset in self.PRESETS:
            if preset in p or preset.replace("_", " ") in p:
                return preset
        return "deep_space"

    def generate(
        self,
        prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        *,
        star_density: float = 1.0,
        star_brightness_min: float = 0.5,
        nebula_strength: float = 1.0,
        nebula_smooth: int = 1,
        color_style: str = "cosmic",
        color_jitter: float = 0.1,
        **kwargs: Any,
    ) -> Image.Image:
        preset = self._parse_preset(prompt)
        s = seed if seed is not None else self.default_seed
        style = color_style if color_style in COLOR_STYLES else "cosmic"
        opts = {
            "star_density": star_density,
            "star_brightness_min": max(0.0, min(1.0, star_brightness_min)),
            "nebula_strength": max(0.0, nebula_strength),
            "nebula_smooth": max(0, nebula_smooth),
            "color_style": style,
            "color_jitter": max(0.0, min(0.4, color_jitter)),
        }
        if preset == "nebula":
            arr = self._generate_nebula(width, height, s, opts)
        elif preset == "stars":
            arr = self._generate_starfield(width, height, s, opts)
        elif preset == "galaxy":
            arr = self._generate_galaxy(width, height, s, opts)
        else:
            arr = self._generate_deep_space(width, height, s, opts)
        return Image.fromarray(np.clip(np.round(arr), 0, 255).astype(np.uint8), "RGB")

    def _generate_nebula(
        self,
        width: int,
        height: int,
        seed: Optional[int],
        opts: dict,
    ) -> np.ndarray:
        """Nebula: dark space with bright clouds; colors from seed-based palette (wide range)."""
        n1 = _noise_layer(width, height, scale=0.003, octaves=5, seed=seed)
        n2 = _noise_layer(width, height, scale=0.006, octaves=4, seed=(seed or 0) + 1)
        n3 = _noise_layer(width, height, scale=0.0015, octaves=6, seed=(seed or 0) + 2)
        n4 = _noise_layer(width, height, scale=0.008, octaves=3, seed=(seed or 0) + 3)
        mask = np.clip((n1 * 0.4 + n2 * 0.3 + n3 * 0.2 + n4 * 0.1 - 0.2) * 2.8, 0, 1) ** 0.8
        palette = _palette_from_seed(
            seed, n=4, shuffle=True,
            jitter=opts.get("color_jitter", 0.1),
            style=opts.get("color_style", "cosmic"),
        )
        r = np.zeros((height, width), dtype=np.float32)
        g = np.zeros((height, width), dtype=np.float32)
        b = np.zeros((height, width), dtype=np.float32)
        noises = [n1, n2, n3, n4]
        for i, (nr, ng, nb) in enumerate(palette):
            n = noises[i] * mask
            r += n * nr
            g += n * ng
            b += n * nb
        # Dark base (seed-based tint so each image has a different void color)
        base_palette = _palette_from_seed(
            (seed or 0) + 99, n=1, shuffle=True,
            jitter=min(0.05, opts.get("color_jitter", 0.1) * 0.5),
            style=opts.get("color_style", "cosmic"),
        )
        br, bg, bb = base_palette[0]
        base_r, base_g, base_b = br * 0.25, bg * 0.2, bb * 0.3
        rgb = np.stack(
            [np.clip(base_r + r, 0, 1), np.clip(base_g + g, 0, 1), np.clip(base_b + b, 0, 1)],
            axis=-1,
        )
        strength = opts.get("nebula_strength", 1.0)
        if strength != 1.0:
            base = np.array([base_r, base_g, base_b], dtype=np.float32)
            rgb = base + (rgb - base) * strength
            rgb = np.clip(rgb, 0, 1)
        rgb = rgb * 255
        smooth = opts.get("nebula_smooth", 0)
        if smooth > 0:
            rgb = _box_blur(rgb.astype(np.float32), smooth).astype(np.float32)
        return np.clip(rgb, 0, 255).astype(np.float32)

    def _generate_starfield(
        self,
        width: int,
        height: int,
        seed: Optional[int],
        opts: dict,
    ) -> np.ndarray:
        """Starfield on near-black background; star tints vary (warm, cool, colored) by seed."""
        density = 0.00025 * opts.get("star_density", 1.0)
        min_b = opts.get("star_brightness_min", 0.0)
        stars = _starfield(width, height, density=density, seed=seed, min_brightness=min_b)
        rng = np.random.default_rng(seed)
        # Wider color range: some stars blue, some yellow/orange, some white
        tint_r = rng.uniform(0.75, 1.1, (height, width))
        tint_g = rng.uniform(0.8, 1.08, (height, width))
        tint_b = rng.uniform(0.8, 1.15, (height, width))
        tint = np.stack([tint_r, tint_g, tint_b], axis=-1)
        base = np.zeros((height, width, 3), dtype=np.float32)
        base[:, :] = (0.015, 0.018, 0.03)
        star_rgb = np.stack([stars, stars, stars], axis=-1) * tint
        return np.clip((base + star_rgb) * 255, 0, 255).astype(np.float32)

    def _generate_galaxy(
        self,
        width: int,
        height: int,
        seed: Optional[int],
        opts: dict,
    ) -> np.ndarray:
        """Simple spiral galaxy: dark void, bright core and arms; colors from seed palette."""
        cy, cx = height / 2, width / 2
        y = np.linspace(0, height - 1, height)
        x = np.linspace(0, width - 1, width)
        xx, yy = np.meshgrid(x, y)
        dx = xx - cx
        dy = yy - cy
        r = np.sqrt(dx * dx + dy * dy) / (min(width, height) / 2)
        angle = np.arctan2(dy, dx)
        core = np.exp(-r * 2.5)
        spiral = _noise_layer(width, height, scale=0.003, octaves=3, seed=seed)
        arm = np.sin(angle * 4 + r * 8) * 0.5 + 0.5
        arm = arm * (1 - r) * spiral
        brightness = np.clip(core * 0.7 + arm * 0.5, 0, 1) ** 0.9
        # Core and arms use different palette colors for variety
        palette = _palette_from_seed(
            seed, n=3, shuffle=True,
            jitter=opts.get("color_jitter", 0.08),
            style=opts.get("color_style", "cosmic"),
        )
        cr, cg, cb = palette[0]
        ar, ag, ab = palette[1]
        r_ch = (cr * core + ar * arm) * brightness
        g_ch = (cg * core + ag * arm) * brightness
        b_ch = (cb * core + ab * arm) * brightness
        rgb = np.stack([r_ch, g_ch, b_ch], axis=-1)
        void = _palette_from_seed(
            (seed or 0) + 50, n=1, shuffle=True,
            jitter=min(0.03, opts.get("color_jitter", 0.1)),
            style=opts.get("color_style", "cosmic"),
        )[0]
        base = np.array([void[0] * 0.15, void[1] * 0.15, void[2] * 0.2], dtype=np.float32)
        rgb = base + rgb * (1 - base)
        density = 0.0001 * opts.get("star_density", 1.0)
        min_b = opts.get("star_brightness_min", 0.0)
        stars = _starfield(width, height, density=density, seed=seed, min_brightness=min_b)
        rgb = rgb + np.stack([stars, stars, stars], axis=-1) * 0.6
        return np.clip(rgb * 255, 0, 255).astype(np.float32)

    def _generate_deep_space(
        self,
        width: int,
        height: int,
        seed: Optional[int],
        opts: dict,
    ) -> np.ndarray:
        """Dark space with subtle nebula clouds and a clear starfield."""
        nebula = self._generate_nebula(width, height, seed, opts) / 255.0
        density = 0.0002 * opts.get("star_density", 1.0)
        min_b = opts.get("star_brightness_min", 0.5)
        stars = _starfield(
            width, height, density=density, seed=(seed or 0) + 100, min_brightness=min_b
        )
        star_rgb = np.stack([stars, stars, stars], axis=-1)
        out = nebula + star_rgb * 0.95
        return np.clip(out * 255, 0, 255).astype(np.float32)

"""Web server for the image generator — serves the GUI and /api/generate."""

import base64
import io
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from imagegen.core.procedural import ProceduralSpaceGenerator

app = FastAPI(title="Imagegen", description="Procedural space image generator")

# Mount static files (index.html and assets) after routes so /api/* takes precedence
static = StaticFiles(directory="static", html=True)


class GenerateRequest(BaseModel):
    """Options for procedural space image generation."""

    prompt: str = Field(default="deep_space", description="Preset: nebula, stars, galaxy, deep_space")
    width: int = Field(default=1024, ge=1, le=8192, description="Image width")
    height: int = Field(default=1024, ge=1, le=8192, description="Image height")
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")
    star_density: float = Field(default=1.0, ge=0.1, le=5.0)
    star_brightness_min: float = Field(default=0.5, ge=0.0, le=1.0)
    nebula_strength: float = Field(default=1.0, ge=0.0, le=2.0)
    nebula_smooth: int = Field(default=1, ge=0, le=5)
    color_style: str = Field(default="cosmic", description="cosmic, cool, or warm")
    color_jitter: float = Field(default=0.1, ge=0.0, le=0.4)


@app.post("/api/generate")
def generate_image(req: GenerateRequest) -> dict:
    """Generate a procedural space image; returns PNG as base64."""
    try:
        gen = ProceduralSpaceGenerator(default_seed=req.seed)
        img = gen.generate(
            prompt=req.prompt,
            width=req.width,
            height=req.height,
            seed=req.seed,
            star_density=req.star_density,
            star_brightness_min=req.star_brightness_min,
            nebula_strength=req.nebula_strength,
            nebula_smooth=req.nebula_smooth,
            color_style=req.color_style,
            color_jitter=req.color_jitter,
        )
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        data = base64.b64encode(buf.getvalue()).decode("ascii")
        return {"image": data, "content_type": "image/png"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/presets")
def list_presets() -> list[str]:
    """Return available preset names."""
    return list(ProceduralSpaceGenerator.PRESETS)


# Serve frontend; catch-all must be last
app.mount("/", static)

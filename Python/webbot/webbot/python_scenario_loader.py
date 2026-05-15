"""Load user-editable Python scenarios from disk."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def load_user_python_module(path: Path, module_suffix: str) -> Any:
    """Execute ``path`` as a module (trusted local content only)."""
    safe = "".join(c if c.isalnum() or c == "_" else "_" for c in module_suffix)
    mod_name = f"webbot_user_scenario_{safe}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Python scenario from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_python_run_fn(mod: Any):
    run_fn = getattr(mod, "run", None)
    if run_fn is None or not callable(run_fn):
        raise ValueError("Python scenario must define: async def run(page): ...")
    return run_fn


def read_python_meta(mod: Any) -> tuple[str, tuple[str, ...]]:
    """Optional DESCRIPTION and STEP_LABELS for previews."""
    desc = getattr(mod, "DESCRIPTION", "") or ""
    labels = getattr(mod, "STEP_LABELS", ()) or ()
    if isinstance(labels, str):
        labels = (labels,)
    return str(desc), tuple(str(x) for x in labels)

"""Regenerate the Day 1-10 forecast grid served to the dashboard.

The states are drawn from the same distribution as the training archive, so the
engine never scores a smoother, cleaner lattice than the model was fitted on.
Run with::

    python -m app.data.generate_data
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.core.archive import build_live_grid
from app.core.config import settings

OUTPUT_PATH = Path(__file__).resolve().parent / "mock_weather_grid.json"


def generate_grid_dataset() -> List[Dict[str, Any]]:
    grid = build_live_grid()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(grid, fh, indent=2)
    print(
        f"Generated {len(grid)} regions x "
        f"{settings.LEAD_DAY_MAX - settings.LEAD_DAY_MIN + 1} lead days "
        f"-> {OUTPUT_PATH}"
    )
    return grid


if __name__ == "__main__":
    generate_grid_dataset()

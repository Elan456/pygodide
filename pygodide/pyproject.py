from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def load_pyproject_data(pyproject_path: str | Path) -> dict[str, Any]:
    path = Path(pyproject_path)
    with path.open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)

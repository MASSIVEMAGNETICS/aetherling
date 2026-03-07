"""Schemas sub-package – provides runtime access to JSON schema files."""

from __future__ import annotations

import json
from pathlib import Path

_SCHEMA_DIR = Path(__file__).parent


def load_schema(name: str = "aetherling_schema") -> dict:
    """Load and return a JSON schema by base name.

    Parameters
    ----------
    name:
        Base filename without extension (default: ``"aetherling_schema"``).

    Returns
    -------
    dict
        Parsed JSON schema object.
    """
    path = _SCHEMA_DIR / f"{name}.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)

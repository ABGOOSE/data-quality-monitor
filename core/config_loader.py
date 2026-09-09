"""Load quality rules from YAML config files."""

from pathlib import Path

import yaml


def load_rules(path: str | Path) -> dict:
    """Load quality rules from a YAML file.

    Args:
        path: Path to the YAML rules file.

    Returns:
        A dict with rule definitions, e.g.
        {"tables": {"sample_orders": {"columns": {...}, "checks": [...]}}}
    """
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

from pathlib import Path

import yaml


def load_yaml(path: str) -> dict:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")

    with open(file_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)

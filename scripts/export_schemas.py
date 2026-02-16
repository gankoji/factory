"""Export pydantic model schemas to static JSON files."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from software_factory.core.models import SCHEMA_MODEL_REGISTRY

SCHEMA_DIR = ROOT / "schemas"


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in SCHEMA_MODEL_REGISTRY.items():
        path = SCHEMA_DIR / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n")
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()

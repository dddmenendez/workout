"""Local config for persisting active athlete selection."""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".crossfit_coach"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _read_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def _write_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def get_active_athlete_id() -> int | None:
    return _read_config().get("active_athlete_id")


def set_active_athlete_id(athlete_id: int) -> None:
    config = _read_config()
    config["active_athlete_id"] = athlete_id
    _write_config(config)

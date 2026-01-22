import json
import os
from typing import Any, Dict


DEFAULT_SETTINGS: Dict[str, Any] = {
    "exposure_us": 5000,
    "gain": 50,
}


class SettingsManager:
    def __init__(self, path: str):
        self.path = path
        self.data = DEFAULT_SETTINGS.copy()

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            self.save()
            return self.data

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f) or {}
            merged = DEFAULT_SETTINGS.copy()
            merged.update(loaded)
            self.data = merged
            return self.data
        except Exception:
            # If file is corrupted, fall back to defaults and rewrite
            self.data = DEFAULT_SETTINGS.copy()
            self.save()
            return self.data

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True) if os.path.dirname(self.path) else None
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, sort_keys=True)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

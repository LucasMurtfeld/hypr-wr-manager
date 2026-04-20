"""Application configuration: paths + UI mode, persisted as JSON."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path


HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "hypr-wr-manager"
CONFIG_FILE = CONFIG_DIR / "config.json"

HYPR_CONFIG_DIR = HOME / ".config" / "hypr"

# Candidates probed for the file that gets the one-line `source = ...` entry.
# First match wins. hyprland.conf is the always-present fallback.
SOURCE_FILE_CANDIDATES = (
    HYPR_CONFIG_DIR / "UserConfigs" / "WindowRules.conf",
    HYPR_CONFIG_DIR / "conf" / "windowrules.conf",
    HYPR_CONFIG_DIR / "hyprland.conf",
)

# Legacy file created by hypr-wb-manager 0.1.x; migrated on first run.
LEGACY_RULES_FILES = (
    HYPR_CONFIG_DIR / "UserConfigs" / "hypr-wb-manager.conf",
    HYPR_CONFIG_DIR / "hypr-wb-manager.conf",
)
LEGACY_SOURCE_LINE_PREFIX = "source = $UserConfigs/hypr-wb-manager.conf"


UIMode = str  # "simple" | "expert"


@dataclass
class AppConfig:
    rules_file: str = ""
    source_file: str = ""
    add_source_line: bool = True
    ui_mode: UIMode = "simple"
    first_run_done: bool = False
    # Free-form extras so we can survive forward/backward config changes:
    extras: dict = field(default_factory=dict)

    @property
    def rules_path(self) -> Path:
        return Path(os.path.expanduser(self.rules_file)) if self.rules_file else detect_default_rules_path()

    @property
    def source_path(self) -> Path:
        return Path(os.path.expanduser(self.source_file)) if self.source_file else detect_default_source_path()


def detect_default_source_path() -> Path:
    for candidate in SOURCE_FILE_CANDIDATES:
        if candidate.exists():
            return candidate
    return HYPR_CONFIG_DIR / "hyprland.conf"


def detect_default_rules_path() -> Path:
    """Prefer a UserConfigs/ subdir if it looks like a JaKooLit-style layout."""
    user_configs = HYPR_CONFIG_DIR / "UserConfigs"
    if user_configs.is_dir():
        return user_configs / "hypr-wr-manager.conf"
    return HYPR_CONFIG_DIR / "hypr-wr-manager.conf"


def detect_legacy_rules_file() -> Path | None:
    for candidate in LEGACY_RULES_FILES:
        if candidate.exists():
            return candidate
    return None


def load() -> AppConfig:
    if not CONFIG_FILE.exists():
        return AppConfig()
    try:
        data = json.loads(CONFIG_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return AppConfig()
    known = {"rules_file", "source_file", "add_source_line", "ui_mode", "first_run_done"}
    extras = {k: v for k, v in data.items() if k not in known}
    return AppConfig(
        rules_file=str(data.get("rules_file") or ""),
        source_file=str(data.get("source_file") or ""),
        add_source_line=bool(data.get("add_source_line", True)),
        ui_mode=str(data.get("ui_mode") or "simple"),
        first_run_done=bool(data.get("first_run_done", False)),
        extras=extras,
    )


def save(cfg: AppConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = asdict(cfg)
    extras = payload.pop("extras", {}) or {}
    payload.update(extras)
    CONFIG_FILE.write_text(json.dumps(payload, indent=2) + "\n")


def populate_defaults(cfg: AppConfig) -> AppConfig:
    """Fill in empty paths with detected defaults, including legacy migration hint."""
    if not cfg.rules_file:
        legacy = detect_legacy_rules_file()
        if legacy is not None:
            # Put the new file next to the legacy one; migration happens in persistence layer.
            cfg.rules_file = str(legacy.with_name("hypr-wr-manager.conf"))
        else:
            cfg.rules_file = str(detect_default_rules_path())
    if not cfg.source_file:
        cfg.source_file = str(detect_default_source_path())
    return cfg

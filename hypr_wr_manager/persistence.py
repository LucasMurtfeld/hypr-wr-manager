"""Read/write the managed rules file; manage the one-line source bootstrap."""
from __future__ import annotations

import datetime as _dt
import os
import tempfile
from pathlib import Path

from hypr_wr_manager import config as app_config
from hypr_wr_manager.rules import Rule, parse_rules, serialize_rules

FILE_HEADER = (
    "# Managed by hypr-wr-manager. Do not hand-edit this file.\n"
    "# Use the GUI; it fully rewrites this file on every save.\n"
    "# See https://wiki.hypr.land/Configuring/Window-Rules/\n"
)
BACKUP_KEEP = 5


def source_line_for(rules_file: Path) -> str:
    """Build the `source = ...` line for a given rules file path."""
    return f"source = {rules_file}"


def ensure_sourced(cfg: app_config.AppConfig) -> tuple[bool, str]:
    """Ensure the source-line is present in cfg.source_path. Also rewrites any
    legacy hypr-wb-manager source lines to point at the new file.

    Returns (changed, message) so the UI can surface what happened.
    """
    if not cfg.add_source_line:
        return False, ""

    src = cfg.source_path
    rules = cfg.rules_path
    target_line = source_line_for(rules)

    src.parent.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        src.write_text(
            f"# Added by hypr-wr-manager on {_dt.date.today().isoformat()}\n"
            f"{target_line}\n"
        )
        return True, f"Created {src} and added source line."

    text = src.read_text()
    lines = text.splitlines()
    out: list[str] = []
    found = False
    changed = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("source") and "hypr-wb-manager.conf" in stripped:
            out.append(target_line)
            found = True
            changed = True
            continue
        if stripped == target_line:
            found = True
        out.append(line)

    if not found:
        if out and out[-1].strip() != "":
            out.append("")
        out.append(f"# Added by hypr-wr-manager on {_dt.date.today().isoformat()}")
        out.append(target_line)
        changed = True

    if changed:
        src.write_text("\n".join(out) + "\n")
        return True, f"Updated source line in {src}."
    return False, ""


def migrate_legacy_rules_file(cfg: app_config.AppConfig) -> str | None:
    """If a hypr-wb-manager.conf exists, move it to the configured wr-manager path.

    Returns a human-readable message if migration happened, else None.
    """
    legacy = app_config.detect_legacy_rules_file()
    if legacy is None:
        return None
    target = cfg.rules_path
    if target.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    legacy.rename(target)
    return f"Migrated rules file: {legacy} \u2192 {target}"


def load_rules(cfg: app_config.AppConfig) -> list[Rule]:
    path = cfg.rules_path
    if not path.exists():
        return []
    return parse_rules(path.read_text())


def save_rules(cfg: app_config.AppConfig, rules: list[Rule]) -> Path:
    path = cfg.rules_path
    path.parent.mkdir(parents=True, exist_ok=True)
    body = FILE_HEADER + "\n" + serialize_rules(rules)
    _atomic_write(path, body)
    _rotate_backups(path)
    return path


def _atomic_write(path: Path, content: str) -> None:
    if path.exists():
        ts = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        backup = path.with_name(f"{path.name}.bak-{ts}")
        backup.write_bytes(path.read_bytes())
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.chmod(tmp_name, 0o644)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _rotate_backups(path: Path) -> None:
    backups = sorted(
        path.parent.glob(path.name + ".bak-*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for stale in backups[BACKUP_KEEP:]:
        try:
            stale.unlink()
        except OSError:
            pass

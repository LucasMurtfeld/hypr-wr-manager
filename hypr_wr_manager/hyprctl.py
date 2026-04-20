from __future__ import annotations

import json
import subprocess
from typing import Any


class HyprctlError(RuntimeError):
    pass


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["hyprctl", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _run_json(args: list[str]) -> Any:
    proc = _run([*args, "-j"])
    if proc.returncode != 0:
        raise HyprctlError(f"hyprctl {' '.join(args)} failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise HyprctlError(f"hyprctl {' '.join(args)} returned invalid JSON: {e}") from e


def list_clients() -> list[dict[str, Any]]:
    data = _run_json(["clients"])
    if not isinstance(data, list):
        raise HyprctlError("expected JSON array from hyprctl clients")
    return data


def list_workspaces() -> list[dict[str, Any]]:
    data = _run_json(["workspaces"])
    if not isinstance(data, list):
        raise HyprctlError("expected JSON array from hyprctl workspaces")
    return data


def reload() -> tuple[int, str]:
    proc = _run(["reload"])
    return proc.returncode, proc.stderr.strip()


def config_errors() -> str:
    proc = _run(["configerrors"])
    return proc.stdout.strip()

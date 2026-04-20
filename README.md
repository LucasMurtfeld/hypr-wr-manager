# hypr-wr-manager

A small PyQt6 GUI for managing **Hyprland** window rules.

It lists every open window via `hyprctl clients`, lets you pick one, and builds the right `windowrule { ... }` block through a form: float, center, workspace placement, opacity, size, and more. Rules are written to a file you own, and `hyprctl reload` can be triggered with one click.

## Features

- Live list of every Hyprland window, filterable by class/title
- Form-based rule editor — no manual regex required for the common case
- **Simple** mode for common tweaks (float, center, workspace, opacity, size)
- **Expert** mode exposing `initial_class` / `initial_title`, `match:tag`, `match:fullscreen`, regex mode, pin, `no_blur`, fullscreen state, inactive opacity, reordering, and a live preview of the block that will be written
- Configurable paths — works with JaKooLit dotfiles, plain Hyprland, and anything in between
- Atomic writes with 5 rolling backups (`*.bak-<timestamp>`)
- Round-trips unknown rule properties so upgrading the app never drops your fields
- One-line `source = ...` bootstrap into your existing config; your hand-edits are never touched
- Legacy migration: automatically renames `hypr-wb-manager.conf` (older versions) to `hypr-wr-manager.conf` and fixes the source line

## Requirements

- Hyprland 0.53+ (uses the `windowrule { ... }` block syntax)
- Python 3.11+
- PyQt6 6.5+
- `hyprctl` on `$PATH`

## Install

### From source

```sh
git clone https://github.com/niva/hypr-wr-manager.git
cd hypr-wr-manager
pip install --user .
hypr-wr-manager
```

### Without installing

```sh
cd hypr-wr-manager
python -m hypr_wr_manager
```

### Arch Linux

```sh
sudo pacman -S python-pyqt6
python -m hypr_wr_manager
```

## First run

On first launch you'll see a **Preferences** dialog with two paths:

- **Managed rules file** — the file this app owns and rewrites on every save. Default: `~/.config/hypr/hypr-wr-manager.conf` (or under `~/.config/hypr/UserConfigs/` if that directory exists).
- **Add source line to** — the Hyprland config file that should include a `source = ...` line pointing at the managed rules file. Auto-detected: `UserConfigs/WindowRules.conf` if present, else `hyprland.conf`.

You can change both later under **File → Preferences…** (`Ctrl+,`).

## Usage

1. **Refresh** (F5) — load the current window list.
2. Select a window and click **New Rule…** — the match fields are prefilled.
3. Check the property you want (Float, Center, Workspace, Opacity, …) and click **OK**.
4. **Save & Reload** (`Ctrl+S`) — writes the file and runs `hyprctl reload`. Any syntax errors from Hyprland are surfaced in a dialog.

Switch between Simple and Expert under **View → Simple / Expert mode**. In Expert mode you get:

- Separate rows for `class`, `title`, `initial_class`, `initial_title` with a mode selector (Exact / Substring / Regex)
- `match:tag` and `match:fullscreen`
- Pin, No blur, Fullscreen state, separate inactive opacity
- Duplicate / Move Up / Move Down for rule ordering
- Save-only and Reload-only menu items
- A live preview of the `windowrule { ... }` block that will be written

## How the file layout works

The app writes only one file — your **managed rules file** — and it rewrites that file entirely on every save. It never touches anything else, with one exception: on first launch (and any time the rules path changes) it appends a single `source = ...` line to your **source file** so Hyprland picks up the managed rules. That line is idempotent — re-launches don't duplicate it.

Everything you hand-write in your other Hyprland config files is left alone.

## Storage locations

- Rules: configurable, default `~/.config/hypr/hypr-wr-manager.conf`
- App preferences: `~/.config/hypr-wr-manager/config.json`
- Backups: `<rules-file>.bak-<timestamp>`, last 5 kept

## Credits

- Hyprland — [hyprland.org](https://hyprland.org)
- PyQt6 — Riverbank Computing
- Default paths designed to match JaKooLit's Hyprland-Dots layout but work anywhere

## License

MIT — see [LICENSE](LICENSE).

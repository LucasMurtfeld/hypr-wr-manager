"""Preferences dialog: paths + UI mode."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hypr_wr_manager import config as app_config


class _PathRow(QWidget):
    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.browse_btn = QPushButton("Browse\u2026")
        self.browse_btn.clicked.connect(self._browse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.browse_btn)

    def _browse(self) -> None:
        start = self.edit.text() or str(Path.home() / ".config" / "hypr")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Select file",
            start,
            "Hyprland config (*.conf);;All files (*)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if path:
            self.edit.setText(path)

    def value(self) -> str:
        return self.edit.text().strip()

    def set_value(self, v: str) -> None:
        self.edit.setText(v)


class PreferencesDialog(QDialog):
    def __init__(self, parent: QWidget | None, cfg: app_config.AppConfig) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(700, 280)
        self._cfg = cfg

        root = QVBoxLayout(self)

        intro = QLabel(
            "Choose where hypr-wr-manager stores its rules and where to add the "
            "<code>source = &hellip;</code> line that pulls them in. "
            "These default to your existing Hyprland layout \u2014 override if you use a non-standard setup."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        form.setLabelAlignment(
            form.labelAlignment()
            if hasattr(form, "labelAlignment")
            else form.formAlignment()
        )
        self.rules_row = _PathRow("e.g. ~/.config/hypr/hypr-wr-manager.conf")
        self.source_row = _PathRow("e.g. ~/.config/hypr/hyprland.conf")
        form.addRow("Managed rules file:", self.rules_row)
        form.addRow("Add source line to:", self.source_row)
        self.add_source_chk = QCheckBox("Automatically add/update the source line in the file above")
        form.addRow("", self.add_source_chk)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Simple", userData="simple")
        self.mode_combo.addItem("Expert", userData="expert")
        form.addRow("Interface mode:", self.mode_combo)

        root.addLayout(form)
        root.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        restore_btn = buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults)
        if restore_btn is not None:
            restore_btn.clicked.connect(self._restore_defaults)
        root.addWidget(buttons)

        self._load_cfg()

    def _load_cfg(self) -> None:
        cfg = app_config.populate_defaults(
            app_config.AppConfig(
                rules_file=self._cfg.rules_file,
                source_file=self._cfg.source_file,
                add_source_line=self._cfg.add_source_line,
                ui_mode=self._cfg.ui_mode,
                first_run_done=self._cfg.first_run_done,
                extras=dict(self._cfg.extras),
            )
        )
        self.rules_row.set_value(cfg.rules_file)
        self.source_row.set_value(cfg.source_file)
        self.add_source_chk.setChecked(cfg.add_source_line)
        idx = self.mode_combo.findData(cfg.ui_mode)
        self.mode_combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _restore_defaults(self) -> None:
        defaults = app_config.populate_defaults(app_config.AppConfig())
        self.rules_row.set_value(defaults.rules_file)
        self.source_row.set_value(defaults.source_file)
        self.add_source_chk.setChecked(True)
        self.mode_combo.setCurrentIndex(self.mode_combo.findData("simple"))

    def apply_to(self, cfg: app_config.AppConfig) -> app_config.AppConfig:
        cfg.rules_file = self.rules_row.value()
        cfg.source_file = self.source_row.value()
        cfg.add_source_line = self.add_source_chk.isChecked()
        cfg.ui_mode = self.mode_combo.currentData() or "simple"
        return cfg

"""Main window: live window table + managed-rules list + toolbar + menus."""
from __future__ import annotations

import copy
from typing import Any

from PyQt6.QtCore import Qt, QSortFilterProxyModel, QTimer, QUrl
from PyQt6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from hypr_wr_manager import APP_DISPLAY_NAME, __version__
from hypr_wr_manager import config as app_config
from hypr_wr_manager import hyprctl, persistence
from hypr_wr_manager.rules import Rule
from hypr_wr_manager.ui.client_model import ClientTableModel
from hypr_wr_manager.ui.preferences import PreferencesDialog
from hypr_wr_manager.ui.rule_dialog import RuleEditorDialog


WIKI_URL = "https://wiki.hypr.land/Configuring/Window-Rules/"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(1200, 720)

        self._rules: list[Rule] = []
        self._workspaces: list[dict[str, Any]] = []
        self._dirty = False

        self._cfg = app_config.populate_defaults(app_config.load())

        self._build_ui()
        self._build_menus()

        if not self._cfg.first_run_done:
            QTimer.singleShot(0, self._show_first_run_preferences)
        else:
            self._bootstrap_sources_and_load()

    # -- bootstrap -------------------------------------------------------

    def _show_first_run_preferences(self) -> None:
        dlg = PreferencesDialog(self, self._cfg)
        if dlg.exec() == PreferencesDialog.DialogCode.Accepted:
            self._cfg = dlg.apply_to(self._cfg)
        self._cfg.first_run_done = True
        app_config.save(self._cfg)
        self._bootstrap_sources_and_load()

    def _bootstrap_sources_and_load(self) -> None:
        try:
            msg = persistence.migrate_legacy_rules_file(self._cfg)
            if msg:
                self.statusBar().showMessage(msg, 6000)
            changed, smsg = persistence.ensure_sourced(self._cfg)
            if changed and smsg:
                self.statusBar().showMessage(smsg, 6000)
        except OSError as e:
            QMessageBox.warning(self, "Bootstrap warning", str(e))
        try:
            self._rules = persistence.load_rules(self._cfg)
        except OSError as e:
            QMessageBox.warning(self, "Load failed", str(e))
            self._rules = []
        self._refresh_rules_list()
        self.refresh_clients()
        self._apply_mode_visibility()

    # -- UI --------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)

        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setObjectName("MainToolbar")
        self.addToolBar(toolbar)

        self.act_refresh = QAction("Refresh", self)
        self.act_refresh.setShortcut(QKeySequence("F5"))
        self.act_refresh.setToolTip("Re-fetch the current window list from Hyprland (F5)")
        self.act_refresh.triggered.connect(self.refresh_clients)
        toolbar.addAction(self.act_refresh)

        self.act_new_from_selection = QAction("New Rule\u2026", self)
        self.act_new_from_selection.setToolTip("Create a rule prefilled from the selected window")
        self.act_new_from_selection.triggered.connect(self.new_rule_from_selection)
        toolbar.addAction(self.act_new_from_selection)

        toolbar.addSeparator()

        self.act_edit = QAction("Edit", self)
        self.act_edit.triggered.connect(self.edit_selected_rule)
        toolbar.addAction(self.act_edit)

        self.act_delete = QAction("Delete", self)
        self.act_delete.triggered.connect(self.delete_selected_rule)
        toolbar.addAction(self.act_delete)

        self.act_duplicate = QAction("Duplicate", self)
        self.act_duplicate.triggered.connect(self.duplicate_selected_rule)
        toolbar.addAction(self.act_duplicate)
        self.act_up = QAction("Move Up", self)
        self.act_up.triggered.connect(lambda: self.move_selected_rule(-1))
        toolbar.addAction(self.act_up)
        self.act_down = QAction("Move Down", self)
        self.act_down.triggered.connect(lambda: self.move_selected_rule(1))
        toolbar.addAction(self.act_down)

        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy(), spacer.sizePolicy().verticalPolicy())
        toolbar.addWidget(spacer)

        self.act_save_reload = QAction("Save & Reload", self)
        self.act_save_reload.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save_reload.setToolTip("Write rules to disk and run hyprctl reload (Ctrl+S)")
        self.act_save_reload.triggered.connect(self.save_and_reload)
        toolbar.addAction(self.act_save_reload)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_clients_pane())
        splitter.addWidget(self._build_rules_pane())
        splitter.setSizes([720, 480])
        root.addWidget(splitter, 1)

        self.statusBar().showMessage("Ready.")

    def _build_clients_pane(self) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("<b>Live windows</b>"))
        header_row.addStretch(1)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter\u2026")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setMaximumWidth(320)
        header_row.addWidget(self.filter_edit)
        v.addLayout(header_row)

        self.client_model = ClientTableModel([])
        self.client_proxy = QSortFilterProxyModel()
        self.client_proxy.setSourceModel(self.client_model)
        self.client_proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.client_proxy.setFilterKeyColumn(-1)
        self.filter_edit.textChanged.connect(self.client_proxy.setFilterFixedString)

        self.clients_view = QTableView()
        self.clients_view.setModel(self.client_proxy)
        self.clients_view.setSortingEnabled(True)
        self.clients_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.clients_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.clients_view.setAlternatingRowColors(True)
        self.clients_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.clients_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.clients_view.doubleClicked.connect(lambda _i: self.new_rule_from_selection())
        v.addWidget(self.clients_view, 1)
        return container

    def _build_rules_pane(self) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(QLabel("<b>Managed rules</b>"))
        self.rules_list = QListWidget()
        self.rules_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.rules_list.customContextMenuRequested.connect(self._rules_context_menu)
        self.rules_list.itemDoubleClicked.connect(lambda _it: self.edit_selected_rule())
        v.addWidget(self.rules_list, 1)
        return container

    def _build_menus(self) -> None:
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")
        act_refresh = QAction("Refresh windows", self)
        act_refresh.setShortcut(QKeySequence("F5"))
        act_refresh.triggered.connect(self.refresh_clients)
        file_menu.addAction(act_refresh)
        file_menu.addSeparator()
        self.act_save_only = QAction("Save only", self)
        self.act_save_only.triggered.connect(self.save_only)
        file_menu.addAction(self.act_save_only)
        act_save_reload_m = QAction("Save && reload Hyprland", self)
        act_save_reload_m.setShortcut(QKeySequence("Ctrl+S"))
        act_save_reload_m.triggered.connect(self.save_and_reload)
        file_menu.addAction(act_save_reload_m)
        self.act_reload_only = QAction("Reload Hyprland only", self)
        self.act_reload_only.triggered.connect(self.reload_only)
        file_menu.addAction(self.act_reload_only)
        file_menu.addSeparator()
        act_prefs = QAction("Preferences\u2026", self)
        act_prefs.setShortcut(QKeySequence("Ctrl+,"))
        act_prefs.triggered.connect(self.open_preferences)
        file_menu.addAction(act_prefs)
        file_menu.addSeparator()
        act_quit = QAction("Quit", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        view_menu = bar.addMenu("&View")
        self.act_simple = QAction("Simple mode", self, checkable=True)
        self.act_expert = QAction("Expert mode", self, checkable=True)
        group = QActionGroup(self)
        group.setExclusive(True)
        group.addAction(self.act_simple)
        group.addAction(self.act_expert)
        self.act_simple.triggered.connect(lambda: self.set_mode("simple"))
        self.act_expert.triggered.connect(lambda: self.set_mode("expert"))
        view_menu.addAction(self.act_simple)
        view_menu.addAction(self.act_expert)

        help_menu = bar.addMenu("&Help")
        act_wiki = QAction("Hyprland window-rules wiki", self)
        act_wiki.triggered.connect(self._open_wiki)
        help_menu.addAction(act_wiki)
        act_config_errors = QAction("Show hyprctl config errors", self)
        act_config_errors.triggered.connect(self._show_config_errors)
        help_menu.addAction(act_config_errors)
        help_menu.addSeparator()
        act_about = QAction("About", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    # -- mode ------------------------------------------------------------

    def _apply_mode_visibility(self) -> None:
        expert = self._cfg.ui_mode == "expert"
        for a in (self.act_duplicate, self.act_up, self.act_down,
                  self.act_save_only, self.act_reload_only):
            a.setVisible(expert)
        self.act_simple.setChecked(not expert)
        self.act_expert.setChecked(expert)

    def set_mode(self, mode: str) -> None:
        self._cfg.ui_mode = mode
        app_config.save(self._cfg)
        self._apply_mode_visibility()
        self.statusBar().showMessage(f"Switched to {mode} mode.", 2500)

    # -- rules list ------------------------------------------------------

    def _refresh_rules_list(self) -> None:
        self.rules_list.clear()
        for rule in self._rules:
            item = QListWidgetItem(f"{rule.name}  —  {rule.summary()}")
            self.rules_list.addItem(item)

    def _selected_rule_index(self) -> int | None:
        row = self.rules_list.currentRow()
        return row if row >= 0 else None

    def _rules_context_menu(self, pos) -> None:
        if self.rules_list.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction("Edit\u2026", self.edit_selected_rule)
        menu.addAction("Delete", self.delete_selected_rule)
        if self._cfg.ui_mode == "expert":
            menu.addSeparator()
            menu.addAction("Duplicate", self.duplicate_selected_rule)
            menu.addAction("Move up", lambda: self.move_selected_rule(-1))
            menu.addAction("Move down", lambda: self.move_selected_rule(1))
        menu.exec(self.rules_list.viewport().mapToGlobal(pos))

    # -- actions ---------------------------------------------------------

    def refresh_clients(self) -> None:
        try:
            clients = hyprctl.list_clients()
            self._workspaces = hyprctl.list_workspaces()
        except hyprctl.HyprctlError as e:
            QMessageBox.critical(self, "hyprctl failed", str(e))
            return
        self.client_model.set_clients(clients)
        self.clients_view.resizeColumnsToContents()
        self.clients_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.statusBar().showMessage(f"Loaded {len(clients)} window(s).", 3000)

    def _selected_client(self) -> dict[str, Any] | None:
        sel = self.clients_view.selectionModel().selectedRows()
        if not sel:
            return None
        src_idx = self.client_proxy.mapToSource(sel[0])
        return self.client_model.client_at(src_idx.row())

    def new_rule_from_selection(self) -> None:
        client = self._selected_client()
        if client is None:
            QMessageBox.information(self, "No selection", "Select a window in the list first.")
            return
        dlg = RuleEditorDialog(
            self,
            workspaces=self._workspaces,
            client=client,
            expert=self._cfg.ui_mode == "expert",
        )
        if dlg.exec() == RuleEditorDialog.DialogCode.Accepted:
            rule = dlg.build_rule()
            if self._name_clashes(rule.name, ignore_index=None):
                rule.name = self._unique_name(rule.name)
            self._rules.append(rule)
            self._refresh_rules_list()
            self.rules_list.setCurrentRow(len(self._rules) - 1)
            self._set_dirty(True)

    def edit_selected_rule(self) -> None:
        idx = self._selected_rule_index()
        if idx is None:
            return
        existing = self._rules[idx]
        dlg = RuleEditorDialog(
            self,
            workspaces=self._workspaces,
            existing=existing,
            expert=self._cfg.ui_mode == "expert",
        )
        if dlg.exec() == RuleEditorDialog.DialogCode.Accepted:
            new_rule = dlg.build_rule()
            if self._name_clashes(new_rule.name, ignore_index=idx):
                new_rule.name = self._unique_name(new_rule.name)
            self._rules[idx] = new_rule
            self._refresh_rules_list()
            self.rules_list.setCurrentRow(idx)
            self._set_dirty(True)

    def delete_selected_rule(self) -> None:
        idx = self._selected_rule_index()
        if idx is None:
            return
        name = self._rules[idx].name
        r = QMessageBox.question(
            self,
            "Delete rule",
            f"Delete rule '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r == QMessageBox.StandardButton.Yes:
            del self._rules[idx]
            self._refresh_rules_list()
            self._set_dirty(True)

    def duplicate_selected_rule(self) -> None:
        idx = self._selected_rule_index()
        if idx is None:
            return
        dup = copy.deepcopy(self._rules[idx])
        dup.name = self._unique_name(dup.name + "_copy")
        self._rules.insert(idx + 1, dup)
        self._refresh_rules_list()
        self.rules_list.setCurrentRow(idx + 1)
        self._set_dirty(True)

    def move_selected_rule(self, delta: int) -> None:
        idx = self._selected_rule_index()
        if idx is None:
            return
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(self._rules):
            return
        self._rules[idx], self._rules[new_idx] = self._rules[new_idx], self._rules[idx]
        self._refresh_rules_list()
        self.rules_list.setCurrentRow(new_idx)
        self._set_dirty(True)

    def save_only(self) -> None:
        try:
            path = persistence.save_rules(self._cfg, self._rules)
            persistence.ensure_sourced(self._cfg)
        except OSError as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self._set_dirty(False)
        self.statusBar().showMessage(f"Saved {len(self._rules)} rule(s) to {path}.", 4000)

    def save_and_reload(self) -> None:
        try:
            persistence.save_rules(self._cfg, self._rules)
            persistence.ensure_sourced(self._cfg)
        except OSError as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self._set_dirty(False)
        self._do_reload(after_save=True)

    def reload_only(self) -> None:
        self._do_reload(after_save=False)

    def _do_reload(self, *, after_save: bool) -> None:
        try:
            rc, err = hyprctl.reload()
        except hyprctl.HyprctlError as e:
            QMessageBox.critical(self, "hyprctl reload failed", str(e))
            return
        if rc != 0:
            QMessageBox.critical(
                self,
                "hyprctl reload failed",
                f"Exit code {rc}\n\n{err or '(no stderr)'}",
            )
            return
        try:
            residual = hyprctl.config_errors()
        except hyprctl.HyprctlError:
            residual = ""
        if residual:
            QMessageBox.warning(self, "Hyprland config errors", residual)
        prefix = "Saved and reloaded." if after_save else "Reloaded Hyprland."
        self.statusBar().showMessage(prefix, 4000)
        QTimer.singleShot(300, self.refresh_clients)

    def open_preferences(self) -> None:
        dlg = PreferencesDialog(self, self._cfg)
        if dlg.exec() != PreferencesDialog.DialogCode.Accepted:
            return
        old_rules_path = self._cfg.rules_path
        self._cfg = dlg.apply_to(self._cfg)
        app_config.save(self._cfg)
        new_rules_path = self._cfg.rules_path
        if new_rules_path != old_rules_path and new_rules_path.exists():
            try:
                self._rules = persistence.load_rules(self._cfg)
                self._refresh_rules_list()
                self._set_dirty(False)
            except OSError as e:
                QMessageBox.warning(self, "Reload failed", str(e))
        self._apply_mode_visibility()
        try:
            persistence.ensure_sourced(self._cfg)
        except OSError as e:
            QMessageBox.warning(self, "Source line update failed", str(e))

    # -- help ------------------------------------------------------------

    def _open_wiki(self) -> None:
        QDesktopServices.openUrl(QUrl(WIKI_URL))

    def _show_config_errors(self) -> None:
        try:
            errs = hyprctl.config_errors()
        except hyprctl.HyprctlError as e:
            QMessageBox.critical(self, "hyprctl failed", str(e))
            return
        if not errs:
            QMessageBox.information(self, "Hyprland config", "No configuration errors.")
            return
        QMessageBox.warning(self, "Hyprland config errors", errs)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_DISPLAY_NAME}",
            f"<h3>{APP_DISPLAY_NAME} {__version__}</h3>"
            f"<p>A PyQt6 GUI for managing Hyprland window rules.</p>"
            f"<p>Rules file: <code>{self._cfg.rules_path}</code><br>"
            f"Source line in: <code>{self._cfg.source_path}</code></p>"
            f"<p><a href='{WIKI_URL}'>Hyprland window-rules wiki</a></p>",
        )

    # -- helpers ---------------------------------------------------------

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        suffix = "  [unsaved changes]" if dirty else ""
        self.setWindowTitle(f"{APP_DISPLAY_NAME}{suffix}")

    def _name_clashes(self, name: str, *, ignore_index: int | None) -> bool:
        for i, r in enumerate(self._rules):
            if i == ignore_index:
                continue
            if r.name == name:
                return True
        return False

    def _unique_name(self, base: str) -> str:
        if not self._name_clashes(base, ignore_index=None):
            return base
        i = 2
        while True:
            cand = f"{base}_{i}"
            if not self._name_clashes(cand, ignore_index=None):
                return cand
            i += 1

    # -- lifecycle -------------------------------------------------------

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if not self._dirty:
            event.accept()
            return
        r = QMessageBox.question(
            self,
            "Unsaved changes",
            "You have unsaved rule changes. Save & reload before quitting?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if r == QMessageBox.StandardButton.Save:
            self.save_and_reload()
            event.accept()
        elif r == QMessageBox.StandardButton.Discard:
            event.accept()
        else:
            event.ignore()

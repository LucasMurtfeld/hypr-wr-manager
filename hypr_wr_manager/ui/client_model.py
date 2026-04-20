from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


COLUMNS: list[tuple[str, str]] = [
    ("Class", "class"),
    ("Title", "title"),
    ("Workspace", "_workspace"),
    ("Floating", "_floating"),
    ("PID", "pid"),
    ("Address", "address"),
]


class ClientTableModel(QAbstractTableModel):
    def __init__(self, clients: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._clients: list[dict[str, Any]] = clients or []

    def set_clients(self, clients: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._clients = clients
        self.endResetModel()

    def client_at(self, row: int) -> dict[str, Any] | None:
        if 0 <= row < len(self._clients):
            return self._clients[row]
        return None

    # -- Qt overrides ------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._clients)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section][0]
        return section + 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        client = self._clients[index.row()]
        key = COLUMNS[index.column()][1]
        if key == "_workspace":
            ws = client.get("workspace") or {}
            return f"{ws.get('name', '?')} ({ws.get('id', '?')})"
        if key == "_floating":
            return "yes" if client.get("floating") else "no"
        val = client.get(key)
        return "" if val is None else str(val)

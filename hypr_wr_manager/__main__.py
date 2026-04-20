from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from hypr_wr_manager import APP_NAME
from hypr_wr_manager.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

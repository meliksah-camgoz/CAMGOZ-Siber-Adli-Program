
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from ui.main_window import CamgozWindow
from ui.theme import APP_STYLESHEET

from database.database import init_database


BASE_DIR = Path(__file__).resolve().parent
ICON_PATH = BASE_DIR / "assets" / "CAMGOZ.ico"


def main():
    app = QApplication(sys.argv)

    app.setApplicationName("CAMGOZ")
    app.setOrganizationName("CAMGOZ")

    # Uygulama simgesi
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    # Pencere gizlendiğinde uygulama kapanmasın
    app.setQuitOnLastWindowClosed(False)

    # Global tasarım sistemi
    app.setStyleSheet(APP_STYLESHEET)

    # Veritabanını başlat
    init_database()

    # Uygulamayı başlat
    window = CamgozWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

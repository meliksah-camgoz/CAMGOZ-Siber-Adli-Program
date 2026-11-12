
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QButtonGroup,
    QSystemTrayIcon, QMenu
)
from PySide6.QtGui import QAction, QIcon

from ui.dashboard import DashboardPage
from ui.evidence_explorer import EvidenceExplorer
from ui.audit_trail import AuditTrailPage
from ui.archived_evidence import ArchivedEvidencePage
from ui.deep_file_inspector import DeepFileInspectorPage
from ui.windows_artifacts import WindowsArtifactsPage
from ui.browser_forensics import BrowserForensicsPage
from ui.timeline_analysis import TimelineAnalysisPage
from ui.threat_detection import ThreatDetectionPage
from modules.windows_artifacts.usb_monitor import USBMonitor


BASE_DIR = Path(__file__).resolve().parent.parent
ICON_PATH = BASE_DIR / "assets" / "CAMGOZ.ico"


class CamgozWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CAMGOZ | Dijital Adli Bilişim Programı")
        self.setMinimumSize(1280, 800)

        self._allow_close = False
        self._tray_icon = None

        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self.init_ui()
        self.init_tray_icon()

        self.usb_monitor = USBMonitor(self)
        self.usb_monitor.start()

    def init_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # SOL MENÜ
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)

        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 27, 18, 20)
        side.setSpacing(7)

        # LOGO
        logo_row = QHBoxLayout()
        logo_row.setSpacing(9)

        logo_icon = QLabel()
        logo_icon.setFixedSize(42, 42)
        logo_icon.setScaledContents(True)

        if ICON_PATH.exists():
            logo_icon.setPixmap(
                QIcon(str(ICON_PATH)).pixmap(42, 42)
            )

        brand_column = QVBoxLayout()
        brand_column.setSpacing(1)

        logo = QLabel("CAMGOZ")
        logo.setObjectName("Brand")

        sub = QLabel("DİJİTAL ADLİ BİLİŞİM PROGRAMI")
        sub.setObjectName("BrandSubtitle")

        brand_column.addWidget(logo)
        brand_column.addWidget(sub)

        logo_row.addWidget(logo_icon)
        logo_row.addLayout(brand_column, 1)

        side.addLayout(logo_row)
        side.addSpacing(35)

        # ÇALIŞMA ALANI
        section = QLabel("ÇALIŞMA ALANI")
        section.setStyleSheet(
            "color:#64748B;font-size:9px;font-weight:bold;"
            "letter-spacing:2px;padding-left:12px;"
        )

        side.addWidget(section)
        side.addSpacing(8)

        # SAYFALAR
        self.pages = QStackedWidget()

        self.dashboard = DashboardPage()
        self.evidence_explorer = EvidenceExplorer()
        self.audit_trail = AuditTrailPage()
        self.archived_evidence = ArchivedEvidencePage()
        self.deep_file_inspector = DeepFileInspectorPage()
        self.windows_artifacts = WindowsArtifactsPage()
        self.browser_forensics = BrowserForensicsPage()
        self.timeline_analysis = TimelineAnalysisPage()
        self.threat_detection = ThreatDetectionPage()

        for page in (
            self.dashboard,
            self.evidence_explorer,
            self.audit_trail,
            self.archived_evidence,
            self.deep_file_inspector,
            self.windows_artifacts,
            self.browser_forensics,
            self.timeline_analysis,
            self.threat_detection,
        ):
            self.pages.addWidget(page)

        # NAVİGASYON
        self.navigation_group = QButtonGroup(self)
        self.navigation_group.setExclusive(True)

        def add_nav(label, index):
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)

            self.navigation_group.addButton(button)

            button.clicked.connect(
                lambda checked=False, i=index: self.open_page(i)
            )

            side.addWidget(button)
            return button

        self.overview_button = add_nav("◈   Genel Bakış", 0)
        add_nav("▣   Kanıt İnceleme", 1)
        add_nav("≋   Denetim Kayıtları", 2)
        add_nav("▤   Arşivlenmiş Kanıtlar", 3)
        add_nav("⌕   Gelişmiş Dosya Analizi", 4)
        add_nav("▤   Windows İzleri", 5)

        side.addSpacing(25)

        # ANALİZ ARAÇLARI
        analysis = QLabel("ANALİZ ARAÇLARI")
        analysis.setStyleSheet(
            "color:#64748B;font-size:9px;font-weight:bold;"
            "letter-spacing:2px;padding-left:12px;"
        )

        side.addWidget(analysis)
        side.addSpacing(8)

        self.browser_button = add_nav("◎   Tarayıcı İncelemesi", 6)
        self.timeline_button = add_nav("◷   Zaman Çizelgesi", 7)
        self.threat_button = add_nav("⚠   Tehdit Tespiti", 8)

        side.addStretch()

        # ALT BİLGİ ALANI
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color:#263449;")

        side.addWidget(line)
        side.addSpacing(12)

        version = QLabel("CAMGOZ v0.13.0")
        version.setStyleSheet("color:#64748B;font-size:11px;")

        status = QLabel("●  SİSTEM HAZIR")
        status.setStyleSheet(
            "color:#34D399;font-size:10px;font-weight:bold;"
        )

        side.addWidget(version)
        side.addWidget(status)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.pages, 1)

        self.overview_button.setChecked(True)

    # SİSTEM TEPSİSİ
    def init_tray_icon(self):

        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon = None
            return

        tray_icon = (
            QIcon(str(ICON_PATH))
            if ICON_PATH.exists()
            else self.windowIcon()
        )

        self._tray_icon = QSystemTrayIcon(tray_icon, self)
        self._tray_icon.setToolTip(
            "CAMGOZ - Arka planda çalışıyor"
        )

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #101827;
                color: #E2E8F0;
                border: 1px solid #263449;
                border-radius: 8px;
                padding: 6px;
                font-size: 12px;
            }

            QMenu::item {
                padding: 9px 28px 9px 12px;
                border-radius: 5px;
                background-color: transparent;
            }

            QMenu::item:selected {
                background-color: #123C36;
                color: #34D399;
            }

            QMenu::separator {
                height: 1px;
                background-color: #263449;
                margin: 5px 8px;
            }

            QMenu::item:disabled {
                color: #64748B;
            }
        """)

        show_action = QAction("Pencereyi Göster", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        quick_action = QAction("Tehdit Tespitini Aç", self)
        quick_action.triggered.connect(
            lambda: self.open_page_and_show(8)
        )
        tray_menu.addAction(quick_action)

        tray_menu.addSeparator()

        exit_action = QAction("Çıkış", self)
        exit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(exit_action)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(
            self.on_tray_activated
        )
        self._tray_icon.show()

    def on_tray_activated(self, reason):

        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def show_window(self):

        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def open_page_and_show(self, index):

        self.open_page(index)
        self.show_window()

    # SAYFA GEÇİŞLERİ
    def open_page(self, index):

        self.pages.setCurrentIndex(index)

        if index == 0:
            self.dashboard.refresh_data()

        elif index == 1:
            self.evidence_explorer.load_evidence()

        elif index == 2:
            self.audit_trail.refresh_data()

        elif index == 3:
            self.archived_evidence.refresh_data()

        elif index == 5:
            self.windows_artifacts.refresh_data()

        elif index == 6:
            self.browser_forensics.refresh_profiles()

        elif index == 7:
            self.timeline_analysis.refresh_data()

    # PENCERE KAPATMA
    def closeEvent(self, event):

        if self._allow_close:
            if hasattr(self, "usb_monitor"):
                self.usb_monitor.stop()

            if self._tray_icon is not None:
                self._tray_icon.hide()

            event.accept()
            return

        # X tuşu: uygulamayı sistem tepsisine küçült.
        if self._tray_icon is not None and self._tray_icon.isVisible():

            event.ignore()
            self.hide()

            self._tray_icon.showMessage(
                "CAMGOZ",
                "Uygulama arka planda çalışmaya devam ediyor.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )

        else:
            # Sistem tepsisi kullanılamıyorsa normal kapat.
            self._allow_close = True

            if hasattr(self, "usb_monitor"):
                self.usb_monitor.stop()

            event.accept()
            QApplication.quit()

    # GERÇEK ÇIKIŞ
    def quit_application(self):

        self._allow_close = True

        if hasattr(self, "usb_monitor"):
            self.usb_monitor.stop()

        if self._tray_icon is not None:
            self._tray_icon.hide()

        self.close()
        QApplication.quit()

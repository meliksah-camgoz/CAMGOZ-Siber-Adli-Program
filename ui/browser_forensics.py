from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFrame, QDialog, QTextBrowser
)

from modules.browser_forensics import detect_profiles, collect_profile_artifacts


class BrowserForensicsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.profiles = []
        self.records = []
        self.init_ui()
        self.refresh_profiles()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(16)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("Tarayıcı İncelemesi")
        title.setStyleSheet("color:#E2E8F0;font-size:25px;font-weight:bold;")
        subtitle = QLabel("Tarayıcı geçmişi ve indirme kayıtlarını salt okunur inceleyin.")
        subtitle.setStyleSheet("color:#94A3B8;font-size:12px;")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch()
        self.refresh_button = QPushButton("⟳  Profilleri Tara")
        self.refresh_button.setFixedHeight(38)
        self.refresh_button.setStyleSheet("""
            QPushButton { background:#10B981;color:#06251D;border:0;
                border-radius:7px;padding:0 18px;font-weight:bold; }
            QPushButton:hover { background:#34D399; }
        """)
        self.refresh_button.clicked.connect(self.refresh_profiles)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        info = QFrame()
        info.setStyleSheet("QFrame{background:#111E30;border:1px solid #263449;border-radius:9px;}")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(16,12,16,12)
        info_title = QLabel("SALT OKUNUR TARAYICI ANALİZİ")
        info_title.setStyleSheet("color:#34D399;font-size:10px;font-weight:bold;letter-spacing:2px;")
        info_text = QLabel("Chrome, Edge ve Firefox profilleri yerel kullanıcı klasörlerinde aranır. "
                           "Kaynak tarayıcı veritabanlarına yazılmaz.")
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color:#94A3B8;font-size:12px;")
        info_layout.addWidget(info_title)
        info_layout.addWidget(info_text)
        layout.addWidget(info)

        controls = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(300)
        self.profile_combo.setMinimumHeight(38)
        self.profile_combo.setMaxVisibleItems(12)
        self.profile_combo.setStyleSheet(self.combo_style())
        self.profile_combo.currentIndexChanged.connect(self.load_selected_profile)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Tüm Kayıtlar", "All Artifacts")
        self.type_combo.addItem("Geçmiş", "History")
        self.type_combo.addItem("Arama", "Search")
        self.type_combo.addItem("İndirme", "Download")
        self.type_combo.setMinimumHeight(38)
        self.type_combo.setStyleSheet(self.combo_style())
        self.type_combo.currentIndexChanged.connect(self.apply_filters)

        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(38)
        self.search_input.setPlaceholderText("URL, başlık veya ayrıntılarda ara...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background:#111E30; color:#E2E8F0;
                border:1px solid #334155; border-radius:7px;
                padding:0 12px; selection-background-color:#145B48;
            }
            QLineEdit:hover { border:1px solid #475569; }
            QLineEdit:focus { background:#111E30; color:#E2E8F0;
                border:1px solid #10B981; }
        """)
        self.search_input.textChanged.connect(self.apply_filters)
        controls.addWidget(QLabel("Profil:"))
        controls.addWidget(self.profile_combo, 2)
        controls.addWidget(QLabel("Tür:"))
        controls.addWidget(self.type_combo)
        controls.addWidget(self.search_input, 2)
        layout.addLayout(controls)

        self.summary = QLabel("Henüz profil taranmadı.")
        self.summary.setStyleSheet("color:#94A3B8;font-size:11px;")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Tür", "Tarih", "Başlık", "URL", "Ayrıntılar"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 155)
        self.table.setColumnWidth(2, 220)
        self.table.setStyleSheet("""
            QTableWidget { background:#0F1B2B;alternate-background-color:#142238;
                color:#CBD5E1;border:1px solid #263449;border-radius:8px;
                gridline-color:#263449;selection-background-color:#145B48; }
            QHeaderView::section { background:#17263B;color:#94A3B8;border:0;
                padding:10px 7px;font-size:10px;font-weight:bold; }
            QTableWidget::item { padding:6px; }
        """)
        self.table.cellDoubleClicked.connect(self.show_details)
        layout.addWidget(self.table, 1)

        self.status = QLabel("Hazır")
        self.status.setStyleSheet("color:#64748B;font-size:11px;")
        layout.addWidget(self.status)

    @staticmethod
    def combo_style():
        # Explicit popup styling prevents the native Windows white popup/focus flash.
        return """
            QComboBox {
                background:#111E30; color:#E2E8F0;
                border:1px solid #334155; border-radius:7px;
                padding:0 10px; min-height:36px;
                selection-background-color:#145B48;
            }
            QComboBox:hover { border:1px solid #475569; }
            QComboBox:focus { background:#111E30; color:#E2E8F0;
                border:1px solid #10B981; }
            QComboBox::drop-down {
                background:#17263B; border:0; width:28px;
                border-top-right-radius:7px; border-bottom-right-radius:7px;
            }
            QComboBox::down-arrow { width:9px; height:9px; }
            QComboBox QAbstractItemView {
                background:#111E30; color:#E2E8F0;
                border:1px solid #334155; outline:0;
                selection-background-color:#145B48;
                selection-color:#FFFFFF;
                padding:5px;
            }
            QComboBox QAbstractItemView::item {
                min-height:30px; padding:6px 9px;
                background:#111E30; color:#E2E8F0;
            }
            QComboBox QAbstractItemView::item:hover {
                background:#172F42; color:#FFFFFF;
            }
            QComboBox QAbstractItemView::item:selected {
                background:#145B48; color:#FFFFFF;
            }
        """

    def refresh_profiles(self):
        self.refresh_button.setEnabled(False)
        try:
            self.profiles = detect_profiles()
            self.profile_combo.blockSignals(True)
            self.profile_combo.clear()
            for profile in self.profiles:
                display_name = profile.get("display_name") or profile["profile"]
                label = f'{profile["browser"]} — {display_name} [{profile["profile"]}]'
                self.profile_combo.addItem(label)
                self.profile_combo.setItemData(
                    self.profile_combo.count() - 1,
                    profile.get("profile_path", ""),
                    Qt.ItemDataRole.ToolTipRole,
                )
            self.profile_combo.blockSignals(False)

            if self.profiles:
                self.profile_combo.setCurrentIndex(0)
                self.load_selected_profile()
            else:
                self.records = []
                self.table.setRowCount(0)
                self.summary.setText("Desteklenen tarayıcı profili bulunamadı.")
                self.status.setText("Chrome, Edge veya Firefox profili bulunamadı.")
        except Exception as exc:
            QMessageBox.critical(self, "Tarayıcı İncelemesi", f"Profil taraması başarısız:\n\n{exc}")
        finally:
            self.refresh_button.setEnabled(True)

    def load_selected_profile(self, *_):
        index = self.profile_combo.currentIndex()
        if index < 0 or index >= len(self.profiles):
            return
        profile = self.profiles[index]
        self.status.setText(f'Reading {profile["browser"]} / {profile["profile"]}...')
        self.table.setEnabled(False)
        try:
            self.records = collect_profile_artifacts(profile)
            self.summary.setText(
                f'{profile["browser"]} | {profile["profile"]} | '
                f'{len(self.records):,} kayıt bulundu'
            )
            self.apply_filters()
            self.status.setText("Analiz tamamlandı. Kaynak veritabanı salt okunur açıldı.")
        except Exception as exc:
            self.records = []
            self.apply_filters()
            self.status.setText(f"Okuma başarısız: {exc}")
            QMessageBox.warning(
                self, "Tarayıcı Veritabanı",
                "Tarayıcı veritabanı okunamadı.\n\n"
                "Tarayıcıyı kapatıp yeniden deneyin.\n\n"
                f"Detay: {exc}"
            )
        finally:
            self.table.setEnabled(True)

    def apply_filters(self, *_):
        selected_type = self.type_combo.currentData()
        needle = self.search_input.text().strip().casefold()
        filtered = []
        for item in self.records:
            if selected_type != "All Artifacts" and item["type"] != selected_type:
                continue
            searchable = " ".join(str(item.get(key, "")) for key in ("title", "url", "details")).casefold()
            if needle and needle not in searchable:
                continue
            filtered.append(item)

        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(len(filtered))
            for row, record in enumerate(filtered):
                type_labels = {"History": "Geçmiş", "Search": "Arama", "Download": "İndirme"}
                values = [type_labels.get(record["type"], record["type"]), record["date"], record["title"], record["url"], record["details"]]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value or "-"))
                    item.setToolTip(str(value or "-"))
                    if col == 0:
                        color = {"History": "#93C5FD", "Search": "#C4B5FD", "Download": "#34D399"}.get(record["type"])
                        if color:
                            item.setForeground(Qt.GlobalColor.cyan if color == "#93C5FD" else Qt.GlobalColor.green)
                    self.table.setItem(row, col, item)
                self.table.setRowHeight(row, 32)
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.viewport().update()
        self.status.setText(f"Gösterilen {len(filtered):,} / {len(self.records):,} kayıt")

    def show_details(self, row, column):
        if row < 0:
            return
        # Table is filtered; rebuild the same filtered sequence to map row to record.
        selected_type = self.type_combo.currentData()
        needle = self.search_input.text().strip().casefold()
        filtered = [
            item for item in self.records
            if (selected_type == "All Artifacts" or item["type"] == selected_type)
            and (not needle or needle in " ".join(
                str(item.get(key, "")) for key in ("title", "url", "details")
            ).casefold())
        ]
        if row >= len(filtered):
            return
        record = filtered[row]
        dialog = QDialog(self)
        dialog.setWindowTitle("CAMGOZ | Tarayıcı Kaydı")
        dialog.resize(850, 600)
        dialog.setStyleSheet("QDialog{background:#0B1424;color:#E2E8F0;}")
        layout = QVBoxLayout(dialog)
        heading = QLabel(f'{record["type"]} — {record["browser"]}')
        heading.setStyleSheet("color:#34D399;font-weight:bold;font-size:13px;")
        layout.addWidget(heading)
        view = QTextBrowser()
        view.setStyleSheet("background:#111E30;color:#CBD5E1;border:1px solid #263449;padding:12px;")
        view.setPlainText(
            f'Tarayıcı: {record["browser"]}\nProfil: {record["profile"]}\n'
            f'Tür: {record["type"]}\nTarih: {record["date"]}\n'
            f'Başlık: {record["title"]}\nURL: {record["url"]}\n'
            f'Ayrıntılar: {record["details"]}'
        )
        layout.addWidget(view)
        close = QPushButton("Kapat")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

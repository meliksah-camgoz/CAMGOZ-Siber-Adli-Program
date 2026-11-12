from html import escape
import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDialog,
    QTextBrowser, QApplication, QTabWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from sqlalchemy import select, desc, func

from database.database import SessionLocal
from database.models import USBDevice, USBActivity
from modules.windows_artifacts.recent_files import collect_recent_files


class WindowsArtifactsPage(QWidget):

    def __init__(self):
        super().__init__()
        self.records = []
        self.usb_devices = []
        self.connection_records = []
        self.file_activity_records = []
        self._last_refresh_at = {}
        self._refresh_cache_seconds = 12.0
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 28, 30, 28)
        main_layout.setSpacing(18)

        header_layout = QHBoxLayout()
        title_layout = QVBoxLayout()

        title = QLabel("Windows İzleri")
        title.setStyleSheet("""
            color: #E2E8F0;
            font-size: 25px;
            font-weight: bold;
        """)

        subtitle = QLabel("Windows sistemindeki dijital izleri inceleyin.")
        subtitle.setStyleSheet("color: #94A3B8; font-size: 12px;")

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        self.refresh_button = QPushButton("⟳  Yenile")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setFixedHeight(38)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #06251D;
                border: none;
                border-radius: 7px;
                padding: 0 18px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #34D399; }
            QPushButton:disabled {
                background-color: #475569;
                color: #CBD5E1;
            }
        """)
        self.refresh_button.clicked.connect(lambda checked=False: self.refresh_data(force=True))
        header_layout.addWidget(self.refresh_button)
        main_layout.addLayout(header_layout)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                background-color: transparent;
                border: none;
                border-top: 1px solid #263449;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #111E30;
                color: #94A3B8;
                border: 1px solid #263449;
                border-bottom: none;
                padding: 12px 20px;
                margin-right: 5px;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                font-size: 11px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #17263B;
                color: #34D399;
                border-bottom: 2px solid #10B981;
            }
            QTabBar::tab:hover { color: #E2E8F0; }
        """)

        self.recent_tab = QWidget()
        self.devices_tab = QWidget()
        self.connections_tab = QWidget()
        self.file_activity_tab = QWidget()

        self.tabs.addTab(self.recent_tab, "Son Kullanılan Dosyalar")
        self.tabs.addTab(self.devices_tab, "USB Cihazları")
        self.tabs.addTab(self.connections_tab, "Bağlantı Geçmişi")
        self.tabs.addTab(self.file_activity_tab, "USB Dosya Etkinliği")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.build_recent_tab()
        self.build_devices_tab()
        self.build_connections_tab()
        self.build_file_activity_tab()

        main_layout.addWidget(self.tabs, 1)

        self.status_label = QLabel("Hazır")
        self.status_label.setStyleSheet("color: #64748B; font-size: 11px;")
        main_layout.addWidget(self.status_label)

    # -------------------------------------------------
    # TAB BUILDERS
    # -------------------------------------------------

    def build_recent_tab(self):
        layout = QVBoxLayout(self.recent_tab)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(15)

        layout.addWidget(self.create_module_card(
            "SON KULLANILAN DOSYALAR ANALİZİ",
            "Windows Son Kullanılanlar klasöründeki LNK kısayolları salt okunur şekilde analiz edilir."
        ))

        summary = QHBoxLayout()
        summary.setSpacing(12)
        self.total_card, self.total_label = self.create_summary_card("TOPLAM KISAYOL", "0")
        self.success_card, self.success_label = self.create_summary_card("BAŞARILI", "0")
        self.failed_card, self.failed_label = self.create_summary_card("BAŞARISIZ", "0")
        summary.addWidget(self.total_card)
        summary.addWidget(self.success_card)
        summary.addWidget(self.failed_card)
        layout.addLayout(summary)

        self.table = self.create_table([
            "Kısayol Adı", "Hedef Yol", "Oluşturulma", "Değiştirilme", "Durum", "Detaylar"
        ])
        self.table.cellDoubleClicked.connect(self.show_record_details)
        layout.addWidget(self.table, 1)

    def build_devices_tab(self):
        layout = QVBoxLayout(self.devices_tab)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(15)

        layout.addWidget(self.create_module_card(
            "USB CİHAZ ENVANTERİ",
            "CAMGOZ tarafından tespit edilmiş USB bellekleri, harici SSD ve HDD cihazlarını görüntüleyin."
        ))

        summary = QHBoxLayout()
        summary.setSpacing(12)
        self.device_total_card, self.device_total_label = self.create_summary_card(
            "KAYITLI CİHAZLAR", "0"
        )
        self.device_seen_card, self.device_seen_label = self.create_summary_card(
            "SON TESPİT", "-"
        )
        summary.addWidget(self.device_total_card)
        summary.addWidget(self.device_seen_card)
        summary.addStretch()
        layout.addLayout(summary)

        self.devices_table = self.create_table([
            "Cihaz Adı", "Seri Numarası", "Üretici Kimliği", "Ürün Kimliği",
            "İlk Görülme", "Son Görülme"
        ])
        self.devices_table.cellDoubleClicked.connect(self.show_device_details)
        layout.addWidget(self.devices_table, 1)

    def build_connections_tab(self):
        layout = QVBoxLayout(self.connections_tab)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(15)

        layout.addWidget(self.create_module_card(
            "USB BAĞLANTI GEÇMİŞİ",
            "CAMGOZ çalışırken kaydedilen cihaz bağlantı ve çıkarılma olayları. "
            "Başlangıçta bulunan cihazlar ayrıca işaretlenir."
        ))

        self.connections_table = self.create_table([
            "Event", "Device", "Drive", "Volume", "Olay Zamanı", "Kaynak"
        ])
        self.connections_table.cellDoubleClicked.connect(
            self.show_connection_details
        )
        layout.addWidget(self.connections_table, 1)

    def build_file_activity_tab(self):
        layout = QVBoxLayout(self.file_activity_tab)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(15)

        layout.addWidget(self.create_module_card(
            "USB DOSYA ETKİNLİĞİ",
            "USB sürücülerinde CAMGOZ açıkken gözlemlenen dosya oluşturma, "
            "değiştirme, silme ve yeniden adlandırma olayları."
        ))

        self.file_activity_table = self.create_table([
            "Event", "Dosya Adı", "Device", "Drive", "Olay Zamanı", "Dosya Yolu"
        ])
        self.file_activity_table.cellDoubleClicked.connect(
            self.show_file_activity_details
        )
        layout.addWidget(self.file_activity_table, 1)

    # -------------------------------------------------
    # SHARED UI HELPERS
    # -------------------------------------------------

    def create_module_card(self, title, description):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #111E30;
                border: 1px solid #263449;
                border-radius: 10px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 17, 20, 17)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #34D399;
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 2px;
        """)

        description_label = QLabel(description)
        description_label.setStyleSheet("color: #94A3B8; font-size: 12px;")
        description_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(description_label)
        return card

    def create_summary_card(self, title, value):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #111E30;
                border: 1px solid #263449;
                border-radius: 9px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #64748B;
            font-size: 9px;
            font-weight: bold;
            letter-spacing: 1px;
        """)

        value_label = QLabel(value)
        value_label.setStyleSheet("""
            color: #E2E8F0;
            font-size: 23px;
            font-weight: bold;
        """)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card, value_label

    def create_table(self, headers):
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)

        header = table.horizontalHeader()
        # ResizeToContents scans every cell and becomes expensive on forensic
        # event tables. Interactive sizing avoids a full-content scan.
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        if len(headers) > 1:
            header.setSectionResizeMode(
                len(headers) - 1, QHeaderView.ResizeMode.Stretch
            )

        table.setStyleSheet("""
            QTableWidget {
                background-color: #0F1B2B;
                alternate-background-color: #142238;
                color: #CBD5E1;
                border: 1px solid #263449;
                border-radius: 8px;
                gridline-color: #263449;
                selection-background-color: #145B48;
                selection-color: #FFFFFF;
            }
            QHeaderView::section {
                background-color: #17263B;
                color: #94A3B8;
                border: none;
                border-bottom: 1px solid #263449;
                padding: 11px 8px;
                font-size: 10px;
                font-weight: bold;
            }
            QTableWidget::item { padding: 7px; }
        """)
        return table

    def fill_table(self, table, rows):
        # Populate in one UI update instead of repainting after every cell.
        table.setUpdatesEnabled(False)
        table.setSortingEnabled(False)
        try:
            table.clearContents()
            table.setRowCount(len(rows))

            for row, values in enumerate(rows):
                for column, value in enumerate(values):
                    display = "-" if value is None or value == "" else str(value)
                    item = QTableWidgetItem(display)
                    item.setToolTip(display)

                    if column == 0:
                        event = display.upper()
                        if event in (
                            "CONNECTED", "DETECTED_AT_STARTUP", "FILE_CREATED", "SUCCESS"
                        ):
                            item.setForeground(Qt.GlobalColor.green)
                        elif event in ("DISCONNECTED", "FILE_DELETED", "BAŞARISIZ"):
                            item.setForeground(Qt.GlobalColor.red)
                        elif event in ("FILE_MODIFIED", "FILE_RENAMED"):
                            item.setForeground(Qt.GlobalColor.cyan)

                    if column == 0:
                        event_labels = {
                            "CONNECTED": "BAĞLANDI",
                            "DISCONNECTED": "BAĞLANTI KESİLDİ",
                            "DETECTED_AT_STARTUP": "BAŞLANGIÇTA TESPİT EDİLDİ",
                            "FILE_CREATED": "DOSYA OLUŞTURULDU",
                            "FILE_MODIFIED": "DOSYA DEĞİŞTİRİLDİ",
                            "FILE_DELETED": "DOSYA SİLİNDİ",
                            "FILE_RENAMED": "DOSYA YENİDEN ADLANDIRILDI",
                            "SUCCESS": "BAŞARILI",
                            "FAILED": "BAŞARISIZ",
                        }
                        item.setText(event_labels.get(display.upper(), display))

                    table.setItem(row, column, item)

                table.setRowHeight(row, 34)
        finally:
            table.setUpdatesEnabled(True)
            table.viewport().update()

    # -------------------------------------------------
    # DATA REFRESH
    # -------------------------------------------------

    def _on_tab_changed(self, index):
        # Sekme değişince yalnızca seçilen sekmenin verisini yükle.
        # Diğer dört modül arka arkaya sorgulanmaz.
        self.refresh_data(force=False)

    def refresh_data(self, force=True):
        index = self.tabs.currentIndex()
        now = time.monotonic()
        last = self._last_refresh_at.get(index, 0.0)

        if not force and now - last < self._refresh_cache_seconds:
            return

        self.refresh_button.setEnabled(False)
        tab_names = {
            0: "Son Kullanılan Dosyalar",
            1: "USB Cihazları",
            2: "Bağlantı Geçmişi",
            3: "USB Dosya Etkinliği",
        }
        self.status_label.setText(f"Yükleniyor: {tab_names.get(index, 'Windows İzleri')}...")

        try:
            started = time.monotonic()
            if index == 0:
                self.refresh_recent_files()
            elif index in (1, 2, 3):
                self.refresh_usb_data()
            elapsed = time.monotonic() - started
            self._last_refresh_at[index] = time.monotonic()
            self.status_label.setText(
                f"{tab_names.get(index, 'Windows Artifacts')} yenilendi "
                f"{elapsed:.2f} sn içinde | Son kullanılan: {len(self.records)} | "
                f"USB: {len(self.usb_devices)}"
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Windows İzleri Hatası",
                f"Veri yenileme başarısız:\n\n{exc}"
            )
            self.status_label.setText("Yenileme başarısız")

        finally:
            self.refresh_button.setEnabled(True)

    def refresh_recent_files(self):
        self.records = collect_recent_files()

        successful = sum(
            1 for record in self.records
            if record.get("parse_status") == "success"
        )
        failed = len(self.records) - successful

        self.total_label.setText(str(len(self.records)))
        self.success_label.setText(str(successful))
        self.failed_label.setText(str(failed))

        rows = []
        for record in self.records:
            rows.append([
                record.get("shortcut_name") or "-",
                record.get("target_path") or "Hedef kullanılamıyor",
                record.get("shortcut_created_at") or "-",
                record.get("shortcut_modified_at") or "-",
                "SUCCESS" if record.get("parse_status") == "success" else "BAŞARISIZ",
                "İncelemek için çift tıklayın",
            ])

        self.fill_table(self.table, rows)

    def refresh_usb_data(self):
        with SessionLocal() as session:
            self.usb_devices = session.scalars(
                select(USBDevice).order_by(desc(USBDevice.last_seen_at))
            ).all()

            activity_rows = session.execute(
                select(USBActivity, USBDevice)
                .join(USBDevice, USBActivity.device_id == USBDevice.id)
                .order_by(desc(USBActivity.event_time), desc(USBActivity.id))
                .limit(1000)
            ).all()

        self.connection_records = [
            (activity, device)
            for activity, device in activity_rows
            if activity.event_type in (
                "CONNECTED", "DISCONNECTED", "DETECTED_AT_STARTUP"
            )
        ]

        self.file_activity_records = [
            (activity, device)
            for activity, device in activity_rows
            if activity.event_type.startswith("FILE_")
        ]

        self.populate_devices_table()
        self.populate_connections_table()
        self.populate_file_activity_table()

        self.device_total_label.setText(str(len(self.usb_devices)))
        latest = self.usb_devices[0].last_seen_at if self.usb_devices else "-"
        self.device_seen_label.setText(latest or "-")

    def populate_devices_table(self):
        rows = [
            [
                device.device_name,
                device.serial_number,
                device.vendor_id,
                device.product_id,
                device.first_seen_at,
                device.last_seen_at,
            ]
            for device in self.usb_devices
        ]
        self.fill_table(self.devices_table, rows)

    def populate_connections_table(self):
        rows = [
            [
                activity.event_type,
                device.device_name,
                activity.drive_letter,
                activity.volume_label,
                activity.event_time,
                activity.source,
            ]
            for activity, device in self.connection_records
        ]
        self.fill_table(self.connections_table, rows)

    def populate_file_activity_table(self):
        rows = [
            [
                activity.event_type,
                activity.file_name,
                device.device_name,
                activity.drive_letter,
                activity.event_time,
                activity.file_path,
            ]
            for activity, device in self.file_activity_records
        ]
        self.fill_table(self.file_activity_table, rows)

    # -------------------------------------------------
    # GENERIC DETAILS DIALOG
    # -------------------------------------------------

    def show_details_dialog(self, window_title, heading, sections, copy_text=None):
        dialog = QDialog(self)
        dialog.setWindowTitle(window_title)
        dialog.setMinimumSize(700, 560)
        dialog.resize(850, 680)

        dialog.setStyleSheet("""
            QDialog {
                background-color: #0B1424;
                color: #E2E8F0;
            }
            QLabel#SectionTitle {
                color: #34D399;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 2px;
            }
            QTextBrowser {
                background-color: #111E30;
                color: #CBD5E1;
                border: 1px solid #263449;
                border-radius: 8px;
                padding: 15px;
                font-size: 12px;
            }
            QPushButton {
                background-color: #17263B;
                color: #CBD5E1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 9px 18px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #263449; }
            QPushButton#CopyButton {
                background-color: #10B981;
                color: #06251D;
                border: none;
            }
            QPushButton#CopyButton:hover { background-color: #34D399; }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(25, 22, 25, 22)
        layout.setSpacing(15)

        title = QLabel(heading)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        details = QTextBrowser()
        details.setOpenExternalLinks(False)
        details.setFont(QFont("Consolas", 10))

        html = ""
        for section_name, fields in sections:
            html += f"""
                <h3 style="
                    color: #34D399;
                    font-size: 11px;
                    letter-spacing: 2px;
                    margin-top: 15px;
                    border-bottom: 1px solid #263449;
                    padding-bottom: 8px;
                ">{escape(str(section_name))}</h3>
            """

            for label, value in fields:
                display_value = "-" if value is None or value == "" else str(value)
                html += f"""
                    <p style="margin-bottom: 13px;">
                        <span style="color: #64748B; font-size: 10px;">
                            {escape(str(label).upper())}
                        </span><br>
                        <span style="color: #E2E8F0; font-size: 12px;">
                            {escape(display_value)}
                        </span>
                    </p>
                """

        details.setHtml(html)
        layout.addWidget(details, 1)

        footer = QHBoxLayout()

        if copy_text:
            copy_button = QPushButton("Yolu Kopyala")
            copy_button.setObjectName("CopyButton")
            copy_button.clicked.connect(
                lambda: QApplication.clipboard().setText(copy_text)
            )
            footer.addWidget(copy_button)

        footer.addStretch()
        close_button = QPushButton("Kapat")
        close_button.clicked.connect(dialog.accept)
        footer.addWidget(close_button)

        layout.addLayout(footer)
        dialog.exec()

    # -------------------------------------------------
    # RECENT FILE DETAILS
    # -------------------------------------------------

    def show_record_details(self, row, column):
        if row < 0 or row >= len(self.records):
            return

        record = self.records[row]
        sections = [
            ("DOSYA BİLGİLERİ", [
                ("Kısayol Adı", record.get("shortcut_name")),
                ("Kısayol Yolu", record.get("shortcut_path")),
                ("Hedef Yol", record.get("target_path")),
            ]),
            ("KISAYOL ÜST VERİLERİ", [
                ("Açıklama", record.get("description")),
                ("Bağımsız Değişkenler", record.get("arguments")),
                ("Çalışma Dizini", record.get("working_directory")),
            ]),
            ("ZAMAN DAMGALARI", [
                ("Kısayol Oluşturulma", record.get("shortcut_created_at")),
                ("Kısayol Değiştirilme", record.get("shortcut_modified_at")),
                ("Kısayol Erişim", record.get("shortcut_accessed_at")),
            ]),
            ("ANALİZ BİLGİLERİ", [
                ("Ayrıştırma Durumu", record.get("parse_status")),
                ("Hata", record.get("error")),
            ]),
        ]

        self.show_details_dialog(
            "CAMGOZ | Artifact Details",
            record.get("shortcut_name") or "ARTIFACT DETAILS",
            sections,
            record.get("target_path") or None
        )

    # -------------------------------------------------
    # USB DEVICE DETAILS
    # -------------------------------------------------

    def show_device_details(self, row, column):
        if row < 0 or row >= len(self.usb_devices):
            return

        device = self.usb_devices[row]
        sections = [
            ("CİHAZ KİMLİĞİ", [
                ("Cihaz Adı", device.device_name),
                ("Cihaz Anahtarı", device.device_key),
                ("Seri Numarası", device.serial_number),
                ("Üretici", device.manufacturer),
                ("Üretici Kimliği", device.vendor_id),
                ("Ürün Kimliği", device.product_id),
            ]),
            ("WINDOWS TANIMLAYICILARI", [
                ("Örnek Kimliği", device.instance_id),
                ("Donanım Kimliği", device.hardware_id),
            ]),
            ("ZAMAN DAMGALARI", [
                ("İlk Görülme", device.first_seen_at),
                ("Son Görülme", device.last_seen_at),
                ("Veritabanı Oluşturulma", device.created_at),
            ]),
        ]

        self.show_details_dialog(
            "CAMGOZ | USB Device Details",
            device.device_name or "USB CİHAZI",
            sections
        )

    # -------------------------------------------------
    # CONNECTION DETAILS
    # -------------------------------------------------

    def show_connection_details(self, row, column):
        if row < 0 or row >= len(self.connection_records):
            return

        activity, device = self.connection_records[row]
        sections = [
            ("OLAY BİLGİLERİ", [
                ("Olay Türü", activity.event_type),
                ("Olay Zamanı", activity.event_time),
                ("Kaynak", activity.source),
                ("Oturum Kimliği", activity.session_id),
            ]),
            ("CİHAZ BİLGİLERİ", [
                ("Cihaz Adı", device.device_name),
                ("Seri Numarası", device.serial_number),
                ("Cihaz Anahtarı", device.device_key),
            ]),
            ("BİRİM BİLGİLERİ", [
                ("Sürücü Harfi", activity.drive_letter),
                ("Birim Etiketi", activity.volume_label),
                ("Yol", activity.file_path),
            ]),
            ("DETAILS", [
                ("Açıklama", activity.details),
            ]),
        ]

        self.show_details_dialog(
            "CAMGOZ | USB Connection Details",
            activity.event_type,
            sections,
            activity.file_path or None
        )

    # -------------------------------------------------
    # FILE ACTIVITY DETAILS
    # -------------------------------------------------

    def show_file_activity_details(self, row, column):
        if row < 0 or row >= len(self.file_activity_records):
            return

        activity, device = self.file_activity_records[row]
        sections = [
            ("DOSYA OLAYI", [
                ("Olay Türü", activity.event_type),
                ("Olay Zamanı", activity.event_time),
                ("Dosya Adı", activity.file_name),
                ("Dosya Yolu", activity.file_path),
                ("Kaynak", activity.source),
            ]),
            ("USB CİHAZI", [
                ("Cihaz Adı", device.device_name),
                ("Seri Numarası", device.serial_number),
                ("Cihaz Anahtarı", device.device_key),
                ("Sürücü Harfi", activity.drive_letter),
            ]),
            ("OTURUM", [
                ("Oturum Kimliği", activity.session_id),
                ("Detaylar", activity.details),
            ]),
        ]

        self.show_details_dialog(
            "CAMGOZ | File Activity Details",
            activity.file_name or activity.event_type,
            sections,
            activity.file_path or None
        )

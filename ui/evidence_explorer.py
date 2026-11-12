import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from core.evidence_manager import EvidenceManager
from database.database import SessionLocal
from database.models import AuditEvent
from modules.file_forensics.analyzer import analyze_file
from modules.reports.report_generator import generate_evidence_report
from ui.components.stat_card import StatCard


class EvidenceExplorer(QWidget):
    def __init__(self):
        super().__init__()

        self.selected_file = None
        self.current_analysis = None

        self.records = []
        self.filtered_records = []
        self.latest_status = {}

        self.init_ui()
        self.load_evidence()

    # ------------------------------------------------------------------
    # USER INTERFACE
    # ------------------------------------------------------------------

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 25, 30, 25)
        main_layout.setSpacing(16)

        # HEADER
        header = QHBoxLayout()
        title_area = QVBoxLayout()

        title = QLabel("Kanıt İnceleme")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Dijital kanıtları toplayın, inceleyin ve bütünlüklerini doğrulayın."
        )
        subtitle.setObjectName("PageSubtitle")

        title_area.addWidget(title)
        title_area.addWidget(subtitle)

        header.addLayout(title_area)
        header.addStretch()
        main_layout.addLayout(header)

        # STATISTICS
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self.total_card = StatCard(
            "Toplam Kanıt",
            "0",
            "Kaydedilen kanıt kayıtları",
            "#34D399",
            "▣",
        )

        self.verified_card = StatCard(
            "Doğrulandı",
            "0",
            "Son kontrol başarılı",
            "#34D399",
            "✓",
        )

        self.warning_card = StatCard(
            "Uyarılar",
            "0",
            "Başarısız veya bulunamayan dosyalar",
            "#FBBF24",
            "!",
        )

        self.pending_card = StatCard(
            "Doğrulanmadı",
            "0",
            "Başarılı bir son kontrol yok",
            "#60A5FA",
            "◷",
        )

        for card in (
            self.total_card,
            self.verified_card,
            self.warning_card,
            self.pending_card,
        ):
            stats_layout.addWidget(card)

        main_layout.addLayout(stats_layout)

        # ACTION BAR
        action_card = QFrame()
        action_card.setObjectName("SurfaceCard")

        action_layout = QHBoxLayout(action_card)
        action_layout.setContentsMargins(12, 10, 12, 10)
        action_layout.setSpacing(9)

        self.select_button = QPushButton("+  Dosya Seç")
        self.select_button.setObjectName("PrimaryButton")

        self.analyze_button = QPushButton("Dosyayı Analiz Et")
        self.analyze_button.setObjectName("SecondaryButton")
        self.analyze_button.setEnabled(False)

        self.save_button = QPushButton("Kanıt Olarak Kaydet")
        self.save_button.setObjectName("SecondaryButton")
        self.save_button.setEnabled(False)

        self.refresh_button = QPushButton("↻  Yenile")
        self.refresh_button.setObjectName("SecondaryButton")

        self.verify_all_button = QPushButton(
            "🛡  Tüm Kanıtları Doğrula"
        )
        self.verify_all_button.setObjectName("PrimaryButton")

        self.select_button.clicked.connect(self.select_file)
        self.analyze_button.clicked.connect(
            self.analyze_selected_file
        )
        self.save_button.clicked.connect(self.save_evidence)
        self.refresh_button.clicked.connect(self.load_evidence)
        self.verify_all_button.clicked.connect(
            self.verify_all_evidence
        )

        action_layout.addWidget(self.select_button)
        action_layout.addWidget(self.analyze_button)
        action_layout.addWidget(self.save_button)
        action_layout.addStretch()
        action_layout.addWidget(self.refresh_button)
        action_layout.addWidget(self.verify_all_button)

        main_layout.addWidget(action_card)

        # SEARCH AND FILTER
        filter_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Dosya adı, konum veya SHA256 ile ara..."
        )
        self.search_input.textChanged.connect(self.apply_filters)

        self.type_filter = QComboBox()
        self.type_filter.addItems(
            [
                "Tüm Dosya Türleri",
                "PDF",
                "Görseller",
                "Çalıştırılabilir Dosyalar",
                "Arşiv Dosyaları",
                "Diğer",
            ]
        )
        self.type_filter.currentTextChanged.connect(
            self.apply_filters
        )

        filter_layout.addWidget(self.search_input, 3)
        filter_layout.addWidget(self.type_filter, 1)
        main_layout.addLayout(filter_layout)

        # MAIN SPLITTER
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(7)

        # EVIDENCE TABLE
        table_container = QFrame()
        table_container.setObjectName("SurfaceCard")

        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(14, 14, 14, 14)

        table_header = QHBoxLayout()

        table_title = QLabel("Kayıtlı Kanıtlar")
        table_title.setStyleSheet(
            "font-size: 15px; font-weight: 700;"
        )

        self.result_count = QLabel("0 kayıt")
        self.result_count.setObjectName("MutedText")

        table_header.addWidget(table_title)
        table_header.addStretch()
        table_header.addWidget(self.result_count)
        table_layout.addLayout(table_header)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "DOSYA ADI",
                "TÜR",
                "BOYUT",
                "BÜTÜNLÜK",
                "EKLENME TARİHİ",
            ]
        )

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)

        table_header_view = self.table.horizontalHeader()
        table_header_view.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        table_header_view.setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        table_header_view.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        table_header_view.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        table_header_view.setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        table_header_view.setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )

        self.table.itemSelectionChanged.connect(
            self.show_selected_evidence
        )

        table_layout.addWidget(self.table)
        splitter.addWidget(table_container)

        # DETAILS PANEL
        details_container = QFrame()
        details_container.setObjectName("SurfaceCard")
        details_container.setMinimumWidth(300)
        details_container.setMaximumWidth(390)

        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(17, 17, 17, 17)
        details_layout.setSpacing(12)

        details_title = QLabel("Kanıt Detayları")
        details_title.setStyleSheet(
            "font-size: 16px; font-weight: 700;"
        )

        self.detail_status = QLabel(
            "●  Bir kanıt kaydı seçin"
        )
        self.detail_status.setStyleSheet(
            """
            color: #94A3B8;
            background-color: #1E293B;
            border-radius: 6px;
            padding: 9px;
            font-size: 11px;
            font-weight: bold;
            """
        )

        self.detail_name = QLabel("Henüz kanıt seçilmedi")
        self.detail_name.setWordWrap(True)
        self.detail_name.setStyleSheet(
            """
            font-size: 15px;
            font-weight: bold;
            color: #F8FAFC;
            """
        )

        self.detail_path = QLabel("")
        self.detail_path.setWordWrap(True)
        self.detail_path.setStyleSheet(
            "color: #64748B; font-size: 10px;"
        )

        details_layout.addWidget(details_title)
        details_layout.addWidget(self.detail_status)
        details_layout.addWidget(self.detail_name)
        details_layout.addWidget(self.detail_path)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #263449;")
        details_layout.addWidget(separator)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText(
            "Detaylarını incelemek için bir kayıt seçin."
        )
        self.details.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )
        self.details.setStyleSheet(
            """
            QPlainTextEdit {
                background-color: #0B1120;
                color: #A7F3D0;
                border: 1px solid #263449;
                border-radius: 7px;
                padding: 9px;
                font-family: Consolas;
                font-size: 10px;
            }
            """
        )
        details_layout.addWidget(self.details, 1)

        # VERIFY BUTTON
        self.verify_button = QPushButton("✓  Bütünlüğü Doğrula")
        self.verify_button.setObjectName("PrimaryButton")
        self.verify_button.setMinimumHeight(42)
        self.verify_button.setEnabled(False)
        self.verify_button.clicked.connect(
            self.verify_selected_evidence
        )
        details_layout.addWidget(self.verify_button)

        # PDF FORENSIC REPORT BUTTON
        self.report_button = QPushButton("▤  PDF Raporu Oluştur")
        self.report_button.setObjectName("SecondaryButton")
        self.report_button.setMinimumHeight(42)
        self.report_button.setEnabled(False)
        self.report_button.clicked.connect(self.generate_selected_report)
        details_layout.addWidget(self.report_button)

        # REMOVE / ARCHIVE BUTTON
        self.archive_button = QPushButton("✕  Kanıtı Arşivle")
        self.archive_button.setMinimumHeight(42)
        self.archive_button.setEnabled(False)
        self.archive_button.setStyleSheet(
            """
            QPushButton {
                background-color: #451A1A;
                color: #F87171;
                border: 1px solid #7F1D1D;
                border-radius: 7px;
                font-weight: bold;
                padding: 10px;
            }

            QPushButton:hover {
                background-color: #7F1D1D;
                color: white;
            }

            QPushButton:disabled {
                color: #64748B;
                background-color: #1E293B;
                border: none;
            }
            """
        )
        self.archive_button.clicked.connect(
            self.archive_selected_evidence
        )
        details_layout.addWidget(self.archive_button)

        splitter.addWidget(details_container)
        splitter.setSizes([720, 360])

        main_layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    # LOAD EVIDENCE AND AUDIT INFORMATION
    # ------------------------------------------------------------------

    def load_evidence(self):
        try:
            self.records = EvidenceManager.get_all_evidence()
            self.latest_status = {}

            with SessionLocal() as session:
                events = session.scalars(
                    select(AuditEvent).order_by(
                        AuditEvent.id.desc()
                    )
                ).all()

                for event in events:
                    if event.evidence_id is None:
                        continue

                    if event.evidence_id in self.latest_status:
                        continue

                    if event.event_type == "EVIDENCE_INTEGRITY_CHECK":
                        try:
                            details = json.loads(event.details or "{}")
                            self.latest_status[event.evidence_id] = (
                                details.get("status", "UNKNOWN")
                            )
                        except (ValueError, TypeError):
                            self.latest_status[event.evidence_id] = (
                                "UNKNOWN"
                            )

            self.update_statistics()
            self.apply_filters()

        except Exception as error:
            QMessageBox.critical(
                self,
                "Database Error",
                str(error),
            )

    def update_statistics(self):
        total = len(self.records)
        verified = 0
        warnings = 0

        for record in self.records:
            status = self.latest_status.get(
                record.id,
                "NOT_CHECKED",
            )

            if status == "INTEGRITY_VERIFIED":
                verified += 1
            elif status in ("INTEGRITY_FAILED", "FILE_MISSING"):
                warnings += 1

        pending = total - verified - warnings

        self.total_card.set_value(str(total))
        self.verified_card.set_value(str(verified))
        self.warning_card.set_value(str(warnings))
        self.pending_card.set_value(str(pending))

    # ------------------------------------------------------------------
    # SEARCH AND FILTER
    # ------------------------------------------------------------------

    def apply_filters(self):
        query = self.search_input.text().strip().lower()
        selected_type = self.type_filter.currentText()

        self.filtered_records = []

        for record in self.records:
            searchable = (
                f"{record.file_name} "
                f"{record.file_path} "
                f"{record.sha256}"
            ).lower()

            if query and query not in searchable:
                continue

            file_type = (record.file_type or "").lower()
            extension = (record.extension or "").lower()

            if selected_type == "PDF":
                if extension != ".pdf":
                    continue

            elif selected_type == "Görseller":
                image_extensions = (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".bmp",
                    ".webp",
                )
                if extension not in image_extensions:
                    continue

            elif selected_type == "Çalıştırılabilir Dosyalar":
                if not any(
                    term in file_type
                    for term in ("executable", "pe", "elf")
                ):
                    continue

            elif selected_type == "Arşiv Dosyaları":
                if not any(
                    term in file_type
                    for term in ("archive", "zip", "rar", "gzip")
                ):
                    continue

            elif selected_type == "Diğer":
                known_extensions = (
                    ".pdf",
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".bmp",
                    ".webp",
                    ".exe",
                    ".zip",
                    ".rar",
                )
                if extension in known_extensions:
                    continue

            self.filtered_records.append(record)

        self.populate_table()

    # ------------------------------------------------------------------
    # TABLE
    # ------------------------------------------------------------------

    def populate_table(self):
        self.table.setRowCount(0)
        self.result_count.setText(
            f"{len(self.filtered_records)} kayıt"
        )

        for record in self.filtered_records:
            row = self.table.rowCount()
            self.table.insertRow(row)

            status = self.latest_status.get(
                record.id,
                "NOT_CHECKED",
            )

            if status == "INTEGRITY_VERIFIED":
                status_text = "✓ Doğrulandı"
                status_color = "#34D399"
            elif status == "INTEGRITY_FAILED":
                status_text = "✕ Başarısız"
                status_color = "#F87171"
            elif status == "FILE_MISSING":
                status_text = "⚠ Eksik"
                status_color = "#FBBF24"
            else:
                status_text = "○ Kontrol edilmedi"
                status_color = "#94A3B8"

            try:
                file_date = str(record.analyzed_at)[:10]
            except (TypeError, AttributeError):
                file_date = "-"

            values = [
                str(record.id),
                record.file_name or "",
                record.file_type or "",
                self.format_size(record.file_size or 0),
                status_text,
                file_date,
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(
                    item.flags()
                    & ~Qt.ItemFlag.ItemIsEditable
                )

                if column == 4:
                    item.setForeground(QColor(status_color))

                self.table.setItem(row, column, item)

            self.table.setRowHeight(row, 39)

        self.clear_details()

    @staticmethod
    def format_size(size):
        size = int(size or 0)

        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"

        return f"{size / (1024 * 1024 * 1024):.2f} GB"

    # ------------------------------------------------------------------
    # FILE ANALYSIS
    # ------------------------------------------------------------------

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Kanıt Dosyasını Seçin",
            "",
            "Tüm Dosyalar (*.*)",
        )

        if not file_path:
            return

        self.selected_file = file_path
        self.current_analysis = None

        self.analyze_button.setEnabled(True)
        self.save_button.setEnabled(False)

    def analyze_selected_file(self):
        if not self.selected_file:
            return

        try:
            self.current_analysis = analyze_file(
                self.selected_file
            )
            result = self.current_analysis

            self.details.setPlainText(
                json.dumps(
                    result,
                    indent=4,
                    ensure_ascii=False,
                )
            )

            self.detail_name.setText(result["file_name"])
            self.detail_path.setText(result["file_path"])

            self.detail_status.setText(
                "●  ANALİZ TAMAMLANDI"
            )
            self.detail_status.setStyleSheet(
                """
                color: #34D399;
                background-color: #12372F;
                border-radius: 6px;
                padding: 9px;
                font-size: 11px;
                font-weight: bold;
                """
            )

            self.save_button.setEnabled(True)

        except Exception as error:
            QMessageBox.critical(
                self,
                "Analiz Başarısız",
                str(error),
            )

    def save_evidence(self):
        if not self.current_analysis:
            return

        try:
            evidence_id = EvidenceManager.add_evidence(
                self.current_analysis,
                notes="CAMGOZ Kanıt İnceleme üzerinden eklendi",
            )

            self.current_analysis = None
            self.save_button.setEnabled(False)
            self.load_evidence()

            QMessageBox.information(
                self,
                "Kanıt Kaydedildi",
                f"Evidence successfully saved.\nID: {evidence_id}",
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Database Error",
                str(error),
            )

    # ------------------------------------------------------------------
    # EVIDENCE DETAILS
    # ------------------------------------------------------------------

    def show_selected_evidence(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self.filtered_records):
            self.clear_details()
            return

        record = self.filtered_records[row]

        self.detail_name.setText(record.file_name)
        self.detail_path.setText(record.file_path)

        status = self.latest_status.get(
            record.id,
            "NOT_CHECKED",
        )

        status_labels = {
            "INTEGRITY_VERIFIED": (
                "✓  BÜTÜNLÜK DOĞRULANDI",
                "#34D399",
                "#12372F",
            ),
            "INTEGRITY_FAILED": (
                "✕  BÜTÜNLÜK DOĞRULANAMADI",
                "#F87171",
                "#451A1A",
            ),
            "FILE_MISSING": (
                "⚠  DOSYA BULUNAMADI",
                "#FBBF24",
                "#422006",
            ),
            "NOT_CHECKED": (
                "○  DOĞRULANMADI",
                "#94A3B8",
                "#1E293B",
            ),
        }

        label, color, background = status_labels.get(
            status,
            ("?  BİLİNMİYOR", "#94A3B8", "#1E293B"),
        )

        self.detail_status.setText(label)
        self.detail_status.setStyleSheet(
            f"""
            color: {color};
            background-color: {background};
            border-radius: 6px;
            padding: 9px;
            font-size: 11px;
            font-weight: bold;
            """
        )

        information = {
            "Kanıt No": record.id,
            "Dosya Adı": record.file_name,
            "Dosya Konumu": record.file_path,
            "Dosya Boyutu": self.format_size(record.file_size),
            "Dosya Türü": record.file_type,
            "Extension": record.extension,
            "MD5": record.md5,
            "SHA256": record.sha256,
            "Oluşturulma Tarihi": record.created_at,
            "Değiştirilme Tarihi": record.modified_at,
            "Erişim Tarihi": record.accessed_at,
            "Analiz Tarihi": record.analyzed_at,
            "Bütünlük Durumu": status,
            "Notlar": record.notes,
        }

        self.details.setPlainText(
            json.dumps(
                information,
                indent=4,
                ensure_ascii=False,
                default=str,
            )
        )

        self.verify_button.setEnabled(True)
        self.report_button.setEnabled(True)
        self.archive_button.setEnabled(True)

    def clear_details(self):
        self.detail_name.setText("Henüz kanıt seçilmedi")
        self.detail_path.setText("")

        self.detail_status.setText(
            "●  Bir kanıt kaydı seçin"
        )
        self.detail_status.setStyleSheet(
            """
            color: #94A3B8;
            background-color: #1E293B;
            border-radius: 6px;
            padding: 9px;
            font-size: 11px;
            """
        )

        self.details.clear()
        self.verify_button.setEnabled(False)
        self.report_button.setEnabled(False)
        self.archive_button.setEnabled(False)

    def generate_selected_report(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self.filtered_records):
            return

        evidence = self.filtered_records[row]
        suggested_name = f"CAMGOZ_Evidence_{evidence.id}_Report.pdf"

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Adli Bilişim PDF Raporunu Kaydet",
            suggested_name,
            "PDF Dosyaları (*.pdf)"
        )

        if not output_path:
            return

        if not output_path.lower().endswith(".pdf"):
            output_path += ".pdf"

        try:
            report_path = generate_evidence_report(
                evidence.id,
                output_path
            )
            QMessageBox.information(
                self,
                "PDF Raporu Oluşturuldu",
                f"Forensic report successfully created:\n\n{report_path}"
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "Rapor Oluşturulamadı",
                str(error)
            )

    # ------------------------------------------------------------------
    # INTEGRITY VERIFICATION
    # ------------------------------------------------------------------

    def verify_selected_evidence(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self.filtered_records):
            return

        evidence = self.filtered_records[row]

        try:
            result = EvidenceManager.verify_evidence_integrity(
                evidence.id
            )

            self.load_evidence()

            new_row = next(
                (
                    index
                    for index, record in enumerate(
                        self.filtered_records
                    )
                    if record.id == evidence.id
                ),
                -1,
            )

            if new_row >= 0:
                self.table.selectRow(new_row)

            status = result["status"]

            if status == "INTEGRITY_VERIFIED":
                QMessageBox.information(
                    self,
                    "Bütünlük Doğrulandı",
                    (
                        "The evidence file matches its original "
                        "recorded SHA256."
                    ),
                )

            elif status == "INTEGRITY_FAILED":
                QMessageBox.warning(
                    self,
                    "Bütünlük Doğrulanamadı",
                    (
                        "The current file does not match the "
                        "original evidence."
                    ),
                )

            elif status == "FILE_MISSING":
                QMessageBox.warning(
                    self,
                    "Dosya Bulunamadı",
                    "Orijinal kanıt dosyası bulunamadı.",
                )

            else:
                QMessageBox.warning(
                    self,
                    "Doğrulama Hatası",
                    result.get("message", "Unknown error"),
                )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Doğrulama Hatası",
                str(error),
            )

    def verify_all_evidence(self):
        records = list(self.records)
        total = len(records)

        if total == 0:
            QMessageBox.information(
                self,
                "Kanıt Bulunamadı",
                "Doğrulanacak kanıt kaydı bulunmuyor.",
            )
            return

        confirmation = QMessageBox.question(
            self,
            "Toplu Bütünlük Doğrulaması",
            (
                f"{total} evidence records will be checked.\n\n"
                "This operation will calculate the current "
                "SHA256 hash of every available file.\n\n"
                "Devam etmek istiyor musunuz?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if confirmation != QMessageBox.StandardButton.Yes:
            return

        progress = QProgressDialog(
            "Bütünlük doğrulaması hazırlanıyor...",
            None,
            0,
            total,
            self,
        )
        progress.setWindowTitle("CAMGOZ Bütünlük Tarayıcısı")
        progress.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.setCancelButton(None)

        verified = 0
        failed = 0
        missing = 0
        errors = 0

        failed_files = []
        missing_files = []
        error_files = []

        self.verify_all_button.setEnabled(False)
        self.verify_button.setEnabled(False)
        self.archive_button.setEnabled(False)

        try:
            for index, evidence in enumerate(records):
                progress.setLabelText(
                    f"Kontrol ediliyor: {evidence.file_name} "
                    f"({index + 1}/{total})"
                )
                QApplication.processEvents()

                try:
                    result = EvidenceManager.verify_evidence_integrity(
                        evidence.id
                    )
                    status = result.get("status")

                    if status == "INTEGRITY_VERIFIED":
                        verified += 1
                    elif status == "INTEGRITY_FAILED":
                        failed += 1
                        failed_files.append(evidence.file_name)
                    elif status == "FILE_MISSING":
                        missing += 1
                        missing_files.append(evidence.file_name)
                    else:
                        errors += 1
                        error_files.append(
                            f"{evidence.file_name}: "
                            f"{result.get('message', 'Unknown error')}"
                        )

                except Exception as error:
                    errors += 1
                    error_files.append(
                        f"{evidence.file_name}: {str(error)}"
                    )

                progress.setValue(index + 1)
                QApplication.processEvents()

        finally:
            self.verify_all_button.setEnabled(True)
            progress.close()
            self.load_evidence()

        summary = (
            "TOPLU BÜTÜNLÜK DOĞRULAMASI TAMAMLANDI\n\n"
            f"Toplam dosya: {total}\n"
            f"Doğrulandı: {verified}\n"
            f"Başarısız: {failed}\n"
            f"Bulunamadı: {missing}\n"
            f"Hata: {errors}\n"
        )

        if failed_files:
            summary += "\nDOĞRULANAMAYAN DOSYALAR:\n"
            for file_name in failed_files:
                summary += f"  - {file_name}\n"

        if missing_files:
            summary += "\nBULUNAMAYAN DOSYALAR:\n"
            for file_name in missing_files:
                summary += f"  - {file_name}\n"

        if error_files:
            summary += "\nHATALAR:\n"
            for error_message in error_files:
                summary += f"  - {error_message}\n"

        if failed or missing or errors:
            QMessageBox.warning(
                self,
                "Bütünlük Tarama Sonuçları",
                summary,
            )
        else:
            QMessageBox.information(
                self,
                "Bütünlük Taraması Başarılı",
                summary,
            )

    # ------------------------------------------------------------------
    # ARCHIVE / REMOVE EVIDENCE
    # ------------------------------------------------------------------

    def archive_selected_evidence(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self.filtered_records):
            return

        evidence = self.filtered_records[row]

        confirmation = QMessageBox.question(
            self,
            "Kanıtı Arşivle",
            (
                f"Are you sure you want to remove "
                f"'{evidence.file_name}'?\n\n"
                "This evidence will disappear from "
                "the active evidence list.\n\n"
                "Its database record and forensic "
                "history will be preserved.\n\n"
                "Diskteki orijinal dosya SİLİNMEYECEKTİR."
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirmation != QMessageBox.StandardButton.Yes:
            return

        try:
            success = EvidenceManager.archive_evidence(
                evidence.id
            )

            if success:
                self.load_evidence()
                QMessageBox.information(
                    self,
                    "Kanıt Arşivlendi",
                    (
                        "Evidence successfully removed "
                        "from the active list.\n\n"
                        "Adli bilişim geçmişi korunmuştur."
                    ),
                )
            else:
                QMessageBox.warning(
                    self,
                    "Zaten Arşivlenmiş",
                    "Bu kanıt zaten arşivlenmiş.",
                )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Arşivleme Hatası",
                str(error),
            )

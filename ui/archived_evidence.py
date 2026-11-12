import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.evidence_manager import EvidenceManager


class ArchivedEvidencePage(QWidget):
    def __init__(self):
        super().__init__()

        self.records = []
        self.filtered_records = []

        self.init_ui()
        self.refresh_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 25, 30, 25)
        main_layout.setSpacing(16)

        # HEADER
        header = QHBoxLayout()
        title_area = QVBoxLayout()

        title = QLabel("Arşivlenmiş Kanıtlar")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Arşivlenmiş kanıtları inceleyin ve kayıtları etkin kanıt listesine geri yükleyin."
        )
        subtitle.setObjectName("PageSubtitle")

        title_area.addWidget(title)
        title_area.addWidget(subtitle)
        header.addLayout(title_area)
        header.addStretch()

        self.refresh_button = QPushButton("↻  Yenile")
        self.refresh_button.setObjectName("SecondaryButton")
        self.refresh_button.clicked.connect(self.refresh_data)
        header.addWidget(self.refresh_button)

        main_layout.addLayout(header)

        # SUMMARY
        summary_card = QFrame()
        summary_card.setObjectName("SurfaceCard")
        summary_layout = QHBoxLayout(summary_card)
        summary_layout.setContentsMargins(16, 13, 16, 13)

        self.count_label = QLabel("0 arşivlenmiş kayıt")
        self.count_label.setStyleSheet(
            "color: #FBBF24; font-size: 13px; font-weight: bold;"
        )

        summary_note = QLabel(
            "Arşivlenmiş kayıtlar veritabanında tutulur; orijinal dosyalar silinmez."
        )
        summary_note.setObjectName("MutedText")

        summary_layout.addWidget(self.count_label)
        summary_layout.addStretch()
        summary_layout.addWidget(summary_note)
        main_layout.addWidget(summary_card)

        # SEARCH
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Dosya adı, yolu, SHA256 veya kanıt ID değerine göre ara..."
        )
        self.search_input.textChanged.connect(self.apply_filter)
        main_layout.addWidget(self.search_input)

        # SPLITTER
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(7)

        # TABLE
        table_container = QFrame()
        table_container.setObjectName("SurfaceCard")
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(14, 14, 14, 14)

        table_header = QHBoxLayout()
        table_title = QLabel("Arşivlenmiş Kayıtlar")
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
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["ID", "DOSYA ADI", "TÜR", "BOYUT", "SHA256"]
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

        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        header_view.setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        header_view.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        header_view.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        header_view.setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )

        self.table.itemSelectionChanged.connect(
            self.show_selected_record
        )
        table_layout.addWidget(self.table)
        splitter.addWidget(table_container)

        # DETAILS
        details_container = QFrame()
        details_container.setObjectName("SurfaceCard")
        details_container.setMinimumWidth(320)
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(16, 16, 16, 16)
        details_layout.setSpacing(10)

        details_title = QLabel("Arşivlenmiş Kanıt Detayları")
        details_title.setStyleSheet(
            "font-size: 15px; font-weight: 700;"
        )

        self.status_label = QLabel("●  Arşivlenmiş bir kayıt seçin")
        self.status_label.setStyleSheet(
            """
            color: #FBBF24;
            background-color: #422006;
            border-radius: 6px;
            padding: 9px;
            font-size: 11px;
            font-weight: bold;
            """
        )

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText(
            "Detaylarını incelemek için arşivlenmiş bir kayıt seçin."
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

        self.restore_button = QPushButton("↶  Kanıtı Geri Yükle")
        self.restore_button.setObjectName("PrimaryButton")
        self.restore_button.setMinimumHeight(42)
        self.restore_button.setEnabled(False)
        self.restore_button.clicked.connect(self.restore_selected)

        details_layout.addWidget(details_title)
        details_layout.addWidget(self.status_label)
        details_layout.addWidget(self.details, 1)
        details_layout.addWidget(self.restore_button)

        splitter.addWidget(details_container)
        splitter.setSizes([720, 360])
        main_layout.addWidget(splitter, 1)

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

    def refresh_data(self):
        try:
            self.records = EvidenceManager.get_archived_evidence()
            self.apply_filter()
        except Exception as error:
            QMessageBox.critical(
                self,
                "Arşiv Hatası",
                str(error),
            )

    def apply_filter(self):
        query = self.search_input.text().strip().lower()
        self.filtered_records = []

        for record in self.records:
            searchable = " ".join(
                [
                    str(record.id),
                    str(record.file_name or ""),
                    str(record.file_path or ""),
                    str(record.file_type or ""),
                    str(record.sha256 or ""),
                ]
            ).lower()

            if query and query not in searchable:
                continue

            self.filtered_records.append(record)

        self.populate_table()

    def populate_table(self):
        self.table.setRowCount(0)
        self.result_count.setText(
            f"{len(self.filtered_records)} kayıt"
        )
        self.count_label.setText(
            f"{len(self.records)} arşivlenmiş kayıt"
        )

        for record in self.filtered_records:
            row = self.table.rowCount()
            self.table.insertRow(row)

            values = [
                str(record.id),
                record.file_name or "",
                record.file_type or "",
                self.format_size(record.file_size),
                record.sha256 or "",
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(
                    item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )

                if column == 4:
                    item.setForeground(QColor("#94A3B8"))

                self.table.setItem(row, column, item)

            self.table.setRowHeight(row, 39)

        self.clear_details()

    def show_selected_record(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self.filtered_records):
            self.clear_details()
            return

        record = self.filtered_records[row]

        information = {
            "Kanıt ID": record.id,
            "Dosya Adı": record.file_name,
            "Dosya Yolu": record.file_path,
            "Dosya Boyutu": self.format_size(record.file_size),
            "Dosya Türü": record.file_type,
            "Uzantı": record.extension,
            "MD5": record.md5,
            "SHA256": record.sha256,
            "Oluşturulma Tarihi": record.created_at,
            "Değiştirilme Tarihi": record.modified_at,
            "Son Erişim Tarihi": record.accessed_at,
            "Analiz Tarihi": record.analyzed_at,
            "Notlar": record.notes,
            "Arşiv Durumu": "ARCHIVED",
        }

        self.details.setPlainText(
            json.dumps(
                information,
                indent=4,
                ensure_ascii=False,
                default=str,
            )
        )

        self.status_label.setText("●  ARŞİVLENDİ")
        self.restore_button.setEnabled(True)

    def clear_details(self):
        self.details.clear()
        self.status_label.setText("●  Arşivlenmiş bir kayıt seçin")
        self.restore_button.setEnabled(False)

    def restore_selected(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self.filtered_records):
            return

        record = self.filtered_records[row]

        answer = QMessageBox.question(
            self,
            "Kanıtı Geri Yükle",
            (
                f"'{record.file_name}' etkin kanıt listesine geri yüklensin mi?\n\n"
                "Orijinal dosya taşınmayacak veya değiştirilmeyecektir. "
                "Geri yükleme işlemi denetim geçmişine kaydedilecektir."
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            restored = EvidenceManager.restore_evidence(record.id)

            if restored:
                self.refresh_data()
                QMessageBox.information(
                    self,
                    "Kanıt Geri Yüklendi",
                    (
                        "Kanıt etkin listeye geri yüklendi.\n\n"
                        "İşlem Denetim Kayıtlarına eklendi."
                    ),
                )
            else:
                QMessageBox.warning(
                    self,
                    "Geri Yükleme Kullanılamıyor",
                    "Bu kanıt şu anda arşivlenmiş durumda değil.",
                )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Geri Yükleme Hatası",
                str(error),
            )

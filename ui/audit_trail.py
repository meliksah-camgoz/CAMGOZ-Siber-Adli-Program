import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
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
    QHeaderView,
)

from sqlalchemy import select

from database.database import SessionLocal
from database.models import AuditEvent
from core.audit_logger import verify_audit_chain


class AuditTrailPage(QWidget):
    def __init__(self):
        super().__init__()

        self.events = []
        self.filtered_events = []

        self.init_ui()
        self.refresh_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 25, 30, 25)
        main_layout.setSpacing(16)

        # HEADER
        header = QHBoxLayout()
        title_area = QVBoxLayout()

        title = QLabel("Denetim Kayıtları")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Adli bilişim işlemlerini inceleyin ve denetim zincirinin bütünlüğünü doğrulayın."
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

        self.verify_chain_button = QPushButton("🛡  Denetim Zincirini Doğrula")
        self.verify_chain_button.setObjectName("PrimaryButton")
        self.verify_chain_button.clicked.connect(self.verify_chain)
        header.addWidget(self.verify_chain_button)

        main_layout.addLayout(header)

        # CHAIN STATUS
        status_card = QFrame()
        status_card.setObjectName("SurfaceCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(16, 13, 16, 13)

        self.chain_status = QLabel("●  DENETİM ZİNCİRİ DOĞRULANMADI")
        self.chain_status.setStyleSheet(
            "color: #FBBF24; font-size: 12px; font-weight: bold;"
        )

        self.chain_summary = QLabel(
            "Kaydedilmiş denetim olaylarının bütünlüğünü kontrol etmek için doğrulama başlatın."
        )
        self.chain_summary.setObjectName("MutedText")

        status_layout.addWidget(self.chain_status)
        status_layout.addWidget(self.chain_summary)
        main_layout.addWidget(status_card)

        # SEARCH
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Olay türü, kullanıcı, kanıt numarası veya detaylarda ara..."
        )
        self.search_input.textChanged.connect(self.apply_filter)
        main_layout.addWidget(self.search_input)

        # TABLE AND DETAILS
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(7)

        table_container = QFrame()
        table_container.setObjectName("SurfaceCard")
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(14, 14, 14, 14)

        table_header = QHBoxLayout()
        table_title = QLabel("Adli Bilişim Etkinlikleri")
        table_title.setStyleSheet(
            "font-size: 15px; font-weight: 700;"
        )
        self.result_count = QLabel("0 olay")
        self.result_count.setObjectName("MutedText")

        table_header.addWidget(table_title)
        table_header.addStretch()
        table_header.addWidget(self.result_count)
        table_layout.addLayout(table_header)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["KAYIT NO", "OLAY", "KANIT NO", "KULLANICI", "ZAMAN DAMGASI"]
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
            4, QHeaderView.ResizeMode.ResizeToContents
        )

        self.table.itemSelectionChanged.connect(self.show_event_details)
        table_layout.addWidget(self.table)
        splitter.addWidget(table_container)

        details_container = QFrame()
        details_container.setObjectName("SurfaceCard")
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(14, 14, 14, 14)
        details_layout.setSpacing(8)

        details_title = QLabel("Olay Detayları")
        details_title.setStyleSheet(
            "font-size: 15px; font-weight: 700;"
        )

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText(
            "Detaylarını ve hash değerlerini incelemek için bir denetim olayı seçin."
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

        details_layout.addWidget(details_title)
        details_layout.addWidget(self.details, 1)
        splitter.addWidget(details_container)
        splitter.setSizes([430, 220])

        main_layout.addWidget(splitter, 1)

    def refresh_data(self):
        try:
            with SessionLocal() as session:
                self.events = session.scalars(
                    select(AuditEvent).order_by(AuditEvent.id.desc())
                ).all()

            self.apply_filter()

        except Exception as error:
            QMessageBox.critical(
                self,
                "Denetim Kayıtları Hatası",
                str(error),
            )

    def apply_filter(self):
        query = self.search_input.text().strip().lower()
        self.filtered_events = []

        for event in self.events:
            searchable = " ".join(
                [
                    str(event.id or ""),
                    str(event.event_type or ""),
                    str(event.evidence_id or ""),
                    str(event.actor or ""),
                    str(event.event_time or ""),
                    str(event.details or ""),
                ]
            ).lower()

            if query and query not in searchable:
                continue

            self.filtered_events.append(event)

        self.populate_table()

    def populate_table(self):
        self.table.setRowCount(0)
        self.result_count.setText(
            f"{len(self.filtered_events)} olay"
        )

        for event in self.filtered_events:
            row = self.table.rowCount()
            self.table.insertRow(row)

            values = [
                str(event.id),
                str(event.event_type or ""),
                str(event.evidence_id if event.evidence_id is not None else "—"),
                str(event.actor or ""),
                str(event.event_time or ""),
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(
                    item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )

                if column == 1:
                    item.setForeground(QColor("#34D399"))

                self.table.setItem(row, column, item)

            self.table.setRowHeight(row, 38)

        self.details.clear()

    def show_event_details(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self.filtered_events):
            self.details.clear()
            return

        event = self.filtered_events[row]

        try:
            parsed_details = json.loads(event.details or "{}")
        except (ValueError, TypeError):
            parsed_details = event.details

        information = {
            "Olay No": event.id,
            "Olay Türü": event.event_type,
            "Kanıt No": event.evidence_id,
            "İşlemi Yapan": event.actor,
            "Olay Zamanı": event.event_time,
            "Detaylar": parsed_details,
            "Önceki Hash": event.previous_hash,
            "Olay Hash Değeri": event.event_hash,
        }

        self.details.setPlainText(
            json.dumps(
                information,
                indent=4,
                ensure_ascii=False,
                default=str,
            )
        )

    def verify_chain(self):
        self.verify_chain_button.setEnabled(False)
        self.chain_status.setText("◷  DENETİM ZİNCİRİ DOĞRULANIYOR...")
        self.chain_status.setStyleSheet(
            "color: #FBBF24; font-size: 12px; font-weight: bold;"
        )

        try:
            result = verify_audit_chain()

            if result.get("valid"):
                total = result.get("total_events", 0)
                last_hash = result.get("last_hash", "")

                self.chain_status.setText(
                    "✓  DENETİM ZİNCİRİ BÜTÜNLÜĞÜ DOĞRULANDI"
                )
                self.chain_status.setStyleSheet(
                    "color: #34D399; font-size: 12px; font-weight: bold;"
                )
                self.chain_summary.setText(
                    f"{total} olay başarıyla doğrulandı. "
                    f"Son zincir hash değeri: {last_hash[:24]}..."
                )

                QMessageBox.information(
                    self,
                    "Denetim Zinciri Doğrulandı",
                    (
                        f"{total} denetim olayının tamamı doğrulamadan geçti.\n\n"
                        "Hash zincirinde herhangi bir uyuşmazlık tespit edilmedi."
                    ),
                )

            else:
                event_id = result.get("event_id", "Bilinmiyor")
                reason = result.get("reason", "Bilinmeyen bütünlük hatası")

                self.chain_status.setText(
                    "✕  DENETİM ZİNCİRİ BÜTÜNLÜK HATASI"
                )
                self.chain_status.setStyleSheet(
                    "color: #F87171; font-size: 12px; font-weight: bold;"
                )
                self.chain_summary.setText(
                    f"Doğrulama, {event_id} numaralı olayda başarısız oldu: {reason}"
                )

                QMessageBox.warning(
                    self,
                    "Denetim Zinciri Hatası",
                    (
                        f"Denetim zinciri doğrulaması başarısız oldu.\n\n"
                        f"Olay No: {event_id}\n"
                        f"Neden: {reason}"
                    ),
                )

        except Exception as error:
            self.chain_status.setText(
                "⚠  DENETİM ZİNCİRİ DOĞRULAMA HATASI"
            )
            self.chain_status.setStyleSheet(
                "color: #FBBF24; font-size: 12px; font-weight: bold;"
            )
            self.chain_summary.setText(str(error))

            QMessageBox.critical(
                self,
                "Doğrulama Hatası",
                str(error),
            )

        finally:
            self.verify_chain_button.setEnabled(True)


from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QFrame,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QTabWidget,
    QAbstractItemView,
)

from modules.file_forensics.deep_inspector import (
    analyze_signature_mismatch,
    scan_embedded_signatures,
    create_hex_dump,
    search_hex_pattern,
)


class DeepFileInspectorPage(QWidget):

    def __init__(self):
        super().__init__()

        self.selected_file = None
        self.hex_matches = []
        self.current_match_index = -1

        self.init_ui()

    # ---------------------------------------------------------
    # THEME
    # ---------------------------------------------------------

    def apply_theme(self):

        self.setStyleSheet("""
            QWidget#DeepFileInspectorPage {
                background-color: #0B1120;
            }

            QLabel {
                color: #E2E8F0;
                background-color: transparent;
            }

            QFrame#SurfaceCard {
                background-color: #111D30;
                border: 1px solid #263449;
                border-radius: 10px;
            }

            QPushButton {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #334155;
                border-radius: 7px;
                padding: 10px 16px;
                font-size: 11px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #26364D;
                border: 1px solid #34D399;
                color: #FFFFFF;
            }

            QPushButton:pressed {
                background-color: #12372F;
            }

            QPushButton:disabled {
                background-color: #172033;
                color: #64748B;
                border: 1px solid #263449;
            }

            QPushButton#PrimaryButton {
                background-color: #059669;
                color: #FFFFFF;
                border: 1px solid #059669;
                font-weight: bold;
            }

            QPushButton#PrimaryButton:hover {
                background-color: #047857;
                border: 1px solid #34D399;
            }

            QLineEdit {
                background-color: #0B1120;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 7px;
                padding: 10px;
                selection-background-color: #047857;
                selection-color: #FFFFFF;
            }

            QLineEdit:focus {
                border: 1px solid #34D399;
            }

            QPlainTextEdit {
                background-color: #0B1120;
                color: #A7F3D0;
                border: 1px solid #263449;
                border-radius: 8px;
                padding: 12px;
                font-family: Consolas;
                font-size: 11px;
                selection-background-color: #065F46;
                selection-color: #FFFFFF;
            }

            QTableWidget {
                background-color: #111D30;
                alternate-background-color: #17243A;
                color: #E2E8F0;
                gridline-color: #263449;
                border: 1px solid #263449;
                border-radius: 8px;
                selection-background-color: #065F46;
                selection-color: #FFFFFF;
                outline: none;
            }

            QTableWidget::item {
                padding: 9px;
                border-bottom: 1px solid #263449;
            }

            QTableWidget::item:selected {
                background-color: #065F46;
                color: #FFFFFF;
            }

            QHeaderView::section {
                background-color: #17243A;
                color: #34D399;
                border: none;
                border-bottom: 1px solid #263449;
                padding: 11px;
                font-size: 10px;
                font-weight: bold;
            }

            QTableWidget QTableCornerButton::section {
                background-color: #17243A;
                border: none;
            }

            QScrollBar:vertical {
                background-color: #0B1120;
                width: 10px;
                margin: 0;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical {
                background-color: #334155;
                min-height: 25px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #059669;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }

            QScrollBar:horizontal {
                background-color: #0B1120;
                height: 10px;
                border-radius: 5px;
            }

            QScrollBar::handle:horizontal {
                background-color: #334155;
                min-width: 25px;
                border-radius: 5px;
            }

            QScrollBar::handle:horizontal:hover {
                background-color: #059669;
            }

            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """)

        # Tab widget is styled separately to avoid
        # Windows native tab rendering issues.
        self.tabs.setStyleSheet("""
            QTabWidget {
                background-color: #0B1120;
                border: none;
            }

            QTabWidget::pane {
                background-color: #0F172A;
                border: 1px solid #263449;
                border-radius: 8px;
                top: -1px;
            }

            QTabWidget::tab-bar {
                alignment: left;
            }

            QTabBar {
                background-color: #0B1120;
                border: none;
            }

            QTabBar::tab {
                background-color: #17243A;
                color: #CBD5E1;
                border: 1px solid #263449;
                border-bottom: 1px solid #263449;
                padding: 12px 22px;
                margin-right: 4px;
                min-width: 115px;
                font-size: 11px;
                font-weight: bold;
            }

            QTabBar::tab:selected {
                background-color: #12372F;
                color: #34D399;
                border: 1px solid #047857;
                border-bottom: 3px solid #34D399;
            }

            QTabBar::tab:!selected {
                background-color: #17243A;
                color: #CBD5E1;
            }

            QTabBar::tab:hover:!selected {
                background-color: #26364D;
                color: #FFFFFF;
            }
        """)

        # Explicit palette prevents native Windows
        # style from using white tab backgrounds.
        palette = self.tabs.palette()
        palette.setColor(
            palette.ColorRole.Window,
            Qt.GlobalColor.darkGray
        )
        palette.setColor(
            palette.ColorRole.Base,
            Qt.GlobalColor.darkGray
        )
        palette.setColor(
            palette.ColorRole.Button,
            Qt.GlobalColor.darkGray
        )
        palette.setColor(
            palette.ColorRole.WindowText,
            Qt.GlobalColor.white
        )
        palette.setColor(
            palette.ColorRole.ButtonText,
            Qt.GlobalColor.white
        )

        self.tabs.setPalette(palette)

    # ---------------------------------------------------------
    # USER INTERFACE
    # ---------------------------------------------------------

    def init_ui(self):

        self.setObjectName("DeepFileInspectorPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        # HEADER
        title = QLabel("Gelişmiş Dosya Analizi")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Dosya imzalarını, gömülü içerikleri ve ham bayt verilerini inceleyin."
        )
        subtitle.setObjectName("PageSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # FILE SELECTION
        file_card = QFrame()
        file_card.setObjectName("SurfaceCard")

        file_layout = QHBoxLayout(file_card)
        file_layout.setContentsMargins(14, 12, 14, 12)
        file_layout.setSpacing(12)

        self.file_label = QLabel("Dosya seçilmedi")
        self.file_label.setWordWrap(True)
        self.file_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.select_button = QPushButton("Dosya Seç")
        self.select_button.setObjectName("PrimaryButton")
        self.select_button.clicked.connect(self.select_file)

        file_layout.addWidget(self.file_label, 1)
        file_layout.addWidget(self.select_button)

        layout.addWidget(file_card)

        # TAB WIDGET
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)
        self.tabs.setUsesScrollButtons(False)

        # -----------------------------------------------------
        # SIGNATURE ANALYSIS TAB
        # -----------------------------------------------------

        signature_page = QWidget()
        signature_layout = QVBoxLayout(signature_page)
        signature_layout.setContentsMargins(12, 14, 12, 12)
        signature_layout.setSpacing(12)

        signature_button = QPushButton(
            "Dosya İmzasını Analiz Et"
        )
        signature_button.setObjectName("PrimaryButton")
        signature_button.setMinimumHeight(40)
        signature_button.clicked.connect(
            self.run_signature_analysis
        )

        self.signature_output = QPlainTextEdit()
        self.signature_output.setReadOnly(True)
        self.signature_output.setPlaceholderText(
            "Bir dosya seçin ve imza analizini başlatın."
        )
        self.signature_output.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )

        signature_layout.addWidget(signature_button)
        signature_layout.addWidget(self.signature_output, 1)

        self.tabs.addTab(
            signature_page,
            "İmza Analizi"
        )

        # -----------------------------------------------------
        # EMBEDDED DETECTION TAB
        # -----------------------------------------------------

        embedded_page = QWidget()
        embedded_layout = QVBoxLayout(embedded_page)
        embedded_layout.setContentsMargins(12, 14, 12, 12)
        embedded_layout.setSpacing(12)

        embedded_button = QPushButton(
            "Gömülü İmzaları Tara"
        )
        embedded_button.setObjectName("PrimaryButton")
        embedded_button.setMinimumHeight(40)
        embedded_button.clicked.connect(
            self.run_embedded_scan
        )

        self.embedded_table = QTableWidget()
        self.embedded_table.setColumnCount(4)

        self.embedded_table.setHorizontalHeaderLabels([
            "DOSYA TÜRÜ",
            "KONUM",
            "İMZA",
            "BEKLENEN UZANTILAR",
        ])

        self.embedded_table.setAlternatingRowColors(True)
        self.embedded_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.embedded_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.embedded_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.embedded_table.verticalHeader().setVisible(False)

        header = self.embedded_table.horizontalHeader()

        header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )

        embedded_layout.addWidget(embedded_button)
        embedded_layout.addWidget(self.embedded_table, 1)

        self.tabs.addTab(
            embedded_page,
            "Gömülü İçerik Tespiti"
        )

        # -----------------------------------------------------
        # HEX VIEWER TAB
        # -----------------------------------------------------

        hex_page = QWidget()
        hex_layout = QVBoxLayout(hex_page)
        hex_layout.setContentsMargins(12, 14, 12, 12)
        hex_layout.setSpacing(12)

        controls_card = QFrame()
        controls_card.setObjectName("SurfaceCard")

        controls = QHBoxLayout(controls_card)
        controls.setContentsMargins(12, 10, 12, 10)
        controls.setSpacing(10)

        offset_label = QLabel("Konum:")
        offset_label.setStyleSheet(
            "color: #94A3B8; font-weight: bold;"
        )

        self.offset_input = QLineEdit("0")
        self.offset_input.setPlaceholderText("Konum")
        self.offset_input.setMaximumWidth(180)

        length_label = QLabel("Uzunluk:")
        length_label.setStyleSheet(
            "color: #94A3B8; font-weight: bold;"
        )

        self.length_input = QLineEdit("256")
        self.length_input.setPlaceholderText("Uzunluk")
        self.length_input.setMaximumWidth(180)

        self.hex_button = QPushButton("Baytları Oku")
        self.hex_button.setObjectName("PrimaryButton")
        self.hex_button.setMinimumHeight(40)
        self.hex_button.clicked.connect(
            self.run_hex_viewer
        )

        controls.addWidget(offset_label)
        controls.addWidget(self.offset_input, 1)
        controls.addWidget(length_label)
        controls.addWidget(self.length_input, 1)
        controls.addWidget(self.hex_button)

        self.hex_output = QPlainTextEdit()
        self.hex_output.setReadOnly(True)
        self.hex_output.setPlaceholderText(
            "Bir dosya seçin, konum ve uzunluk girerek baytları okuyun."
        )
        self.hex_output.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap
        )

        self.hex_output.setStyleSheet("""
            QPlainTextEdit {
                background-color: #080E1B;
                color: #A7F3D0;
                border: 1px solid #263449;
                border-radius: 8px;
                padding: 14px;
                font-family: Consolas;
                font-size: 12px;
                selection-background-color: #065F46;
                selection-color: #FFFFFF;
            }
        """)

        hex_layout.addWidget(controls_card)
        
        # HEX SEARCH CONTROLS
        search_card = QFrame()
        search_card.setObjectName("SurfaceCard")

        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(12, 10, 12, 10)
        search_layout.setSpacing(10)

        search_label = QLabel("HEX Arama:")
        search_label.setStyleSheet(
            "color: #94A3B8; font-weight: bold;"
        )

        self.hex_search_input = QLineEdit()
        self.hex_search_input.setPlaceholderText(
            "Örnek: 50 4B 03 04"
        )

        self.search_button = QPushButton("Ara")
        self.search_button.setObjectName("PrimaryButton")
        self.search_button.clicked.connect(
            self.run_hex_search
        )

        self.previous_match_button = QPushButton("Önceki")
        self.previous_match_button.clicked.connect(
            self.previous_hex_match
        )

        self.next_match_button = QPushButton("Sonraki")
        self.next_match_button.clicked.connect(
            self.next_hex_match
        )

        self.match_label = QLabel("Henüz arama yapılmadı")
        self.match_label.setStyleSheet(
            "color: #34D399; font-weight: bold;"
        )

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.hex_search_input, 1)
        search_layout.addWidget(self.search_button)
        search_layout.addWidget(self.previous_match_button)
        search_layout.addWidget(self.next_match_button)
        search_layout.addWidget(self.match_label)

        hex_layout.addWidget(search_card)

        hex_layout.addWidget(self.hex_output, 1)

        self.tabs.addTab(hex_page, "Hex Görüntüleyici")

        layout.addWidget(self.tabs, 1)

        # APPLY THEME AFTER ALL WIDGETS ARE CREATED
        self.apply_theme()

    # ---------------------------------------------------------
    # FILE SELECTION
    # ---------------------------------------------------------

    def select_file(self):

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "İncelenecek Dosyayı Seçin",
            "",
            "Tüm Dosyalar (*.*)"
        )

        if not file_path:
            return

        self.selected_file = file_path

        self.file_label.setText(
            f"Seçilen: {Path(file_path).name}\n{file_path}"
        )

        self.signature_output.clear()
        self.embedded_table.setRowCount(0)
        self.hex_output.clear()

    def require_file(self):

        if not self.selected_file:
            QMessageBox.warning(
                self,
                "Dosya Seçilmedi",
                "Lütfen önce bir dosya seçin."
            )
            return False

        if not Path(self.selected_file).is_file():
            QMessageBox.warning(
                self,
                "Dosya Bulunamadı",
                "Seçilen dosya artık mevcut değil."
            )
            return False

        return True

    # ---------------------------------------------------------
    # SIGNATURE ANALYSIS
    # ---------------------------------------------------------

    def run_signature_analysis(self):

        if not self.require_file():
            return

        try:
            result = analyze_signature_mismatch(
                self.selected_file
            )

            lines = [
                "CAMGOZ DOSYA İMZASI ANALİZİ",
                "=" * 55,
                "",
                f"Dosya: {Path(self.selected_file).name}",
                f"Yol: {self.selected_file}",
                "",
                "-" * 55,
                "TESPİT SONUÇLARI",
                "-" * 55,
                "",
                f"Tespit Edildi: {result['detected']}",
                f"Gerçek Tür: {result['file_type']}",
                f"Uzantı: {result['extension']}",
                f"İmza: {result['signature_hex']}",
                (
                    "Beklenen Uzantılar: "
                    + (
                        ", ".join(result["expected_extensions"])
                        or "-"
                    )
                ),
                f"Uyumsuzluk: {result['mismatch']}",
                f"Risk: {result['risk']}",
                "",
                "-" * 55,
                "DEĞERLENDİRME",
                "-" * 55,
                "",
                result["message"],
                "",
                (
                    "Not: Yalnızca imza tespiti, dosyanın "
                    "özgünlüğünü kanıtlamaz."
                ),
            ]

            self.signature_output.setPlainText(
                "\n".join(lines)
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "İmza Analizi Error",
                str(error)
            )

    # ---------------------------------------------------------
    # EMBEDDED SIGNATURE DETECTION
    # ---------------------------------------------------------

    def run_embedded_scan(self):

        if not self.require_file():
            return

        try:
            results = scan_embedded_signatures(
                self.selected_file
            )

            self.embedded_table.setRowCount(0)

            for result in results:

                row = self.embedded_table.rowCount()
                self.embedded_table.insertRow(row)

                values = [
                    result["file_type"],
                    str(result["offset"]),
                    result["signature_hex"],
                    ", ".join(
                        result["expected_extensions"]
                    ),
                ]

                for column, value in enumerate(values):

                    item = QTableWidgetItem(value)

                    item.setFlags(
                        item.flags()
                        & ~Qt.ItemFlag.ItemIsEditable
                    )

                    self.embedded_table.setItem(
                        row,
                        column,
                        item
                    )

                self.embedded_table.setRowHeight(row, 38)

            if not results:

                QMessageBox.information(
                    self,
                    "Tarama Tamamlandı",
                    "Bilinen bir gömülü imza tespit edilmedi."
                )

            elif len(results) >= 500:

                QMessageBox.warning(
                    self,
                    "Sonuç Sınırı",
                    "500 eşleşmelik sonuç sınırına ulaşıldı."
                )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Gömülü İçerik Tarama Hatası",
                str(error)
            )

    # ---------------------------------------------------------
    # HEX VIEWER
    # ---------------------------------------------------------

    def run_hex_viewer(self):

        if not self.require_file():
            return

        try:
            offset = int(self.offset_input.text())
            length = int(self.length_input.text())

            rows = create_hex_dump(
                self.selected_file,
                offset=offset,
                length=length,
                bytes_per_row=16,
            )

            output = [
                "KONUM        HEX BAYTLARI                                   ASCII",
                "-" * 85,
            ]

            for row in rows:

                output.append(
                    f"{row['offset']:08X}   "
                    f"{row['hex']:<48} "
                    f"{row['ascii']}"
                )

            if not rows:
                output.append(
                    "Bu konumda okunabilir bayt bulunamadı."
                )

            self.hex_output.setPlainText(
                "\n".join(output)
            )

        except ValueError as error:
            QMessageBox.warning(
                self,
                "Geçersiz Girdi",
                str(error)
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Hex Görüntüleyici Hatası",
                str(error)
            )
    
    def run_hex_search(self):
        if not self.require_file():
            return

        pattern = self.hex_search_input.text().strip()

        try:
            self.hex_matches = search_hex_pattern(
                self.selected_file,
                pattern,
            )

            self.current_match_index = -1

            if not self.hex_matches:
                self.match_label.setText("Eşleşme bulunamadı")
                self.hex_output.clear()

                QMessageBox.information(
                    self,
                    "Arama Tamamlandı",
                    "Eşleşen bir bayt dizisi bulunamadı."
                )
                return

            self.current_match_index = 0
            self.show_current_hex_match()

        except ValueError as error:
            QMessageBox.warning(
                self,
                "Geçersiz Hex Deseni",
                str(error)
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Hex Arama Hatası",
                str(error)
            )

    def show_current_hex_match(self):
        if not self.hex_matches:
            return

        offset = self.hex_matches[self.current_match_index]

        self.offset_input.setText(str(offset))

        self.match_label.setText(
            f"Eşleşme {self.current_match_index + 1} "
            f"/ {len(self.hex_matches)}"
        )

        self.run_hex_viewer()

    def next_hex_match(self):
        if not getattr(self, "hex_matches", []):
            return

        self.current_match_index = (
            self.current_match_index + 1
        ) % len(self.hex_matches)

        self.show_current_hex_match()

    def previous_hex_match(self):
        if not getattr(self, "hex_matches", []):
            return

        self.current_match_index = (
            self.current_match_index - 1
        ) % len(self.hex_matches)

        self.show_current_hex_match()
    

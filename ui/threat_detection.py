
import csv
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QLineEdit, QComboBox, QDialog, QTextBrowser
)

from modules.threat_detection import scan_path


class ThreatDetectionPage(QWidget):

    RISK_LABELS = {
        "CRITICAL": "KRİTİK",
        "HIGH": "YÜKSEK",
        "MEDIUM": "ORTA",
        "LOW": "DÜŞÜK",
        "ERROR": "HATA"
    }

    RISK_COLORS = {
        "CRITICAL": "#F87171",
        "HIGH": "#FB923C",
        "MEDIUM": "#FBBF24",
        "LOW": "#34D399",
        "ERROR": "#94A3B8"
    }

    def __init__(self):
        super().__init__()

        self.results = []
        self.filtered_results = []

        self.init_ui()

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 28, 30, 26)
        root.setSpacing(14)

        # BAŞLIK
        header = QHBoxLayout()
        titles = QVBoxLayout()

        title = QLabel("Tehdit Tespiti")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Dosya ve klasörleri sezgisel risk göstergeleriyle inceleyin."
        )
        subtitle.setObjectName("PageSubtitle")

        titles.addWidget(title)
        titles.addWidget(subtitle)

        header.addLayout(titles)
        header.addStretch()

        self.file_btn = QPushButton("Dosya Tara")
        self.file_btn.setObjectName("PrimaryButton")

        self.folder_btn = QPushButton("Klasör Tara")
        self.folder_btn.setObjectName("SecondaryButton")

        self.file_btn.clicked.connect(self.scan_file)
        self.folder_btn.clicked.connect(self.scan_folder)

        header.addWidget(self.file_btn)
        header.addWidget(self.folder_btn)

        root.addLayout(header)

        # BİLGİLENDİRME KARTI
        notice = QFrame()
        notice.setObjectName("SurfaceCard")

        nl = QVBoxLayout(notice)
        nl.setContentsMargins(16, 12, 16, 12)

        nt = QLabel("SEZGİSEL RİSK ANALİZİ")
        nt.setStyleSheet(
            "color:#34D399;font-size:10px;"
            "font-weight:800;letter-spacing:2px;"
        )

        nd = QLabel(
            "Dosyalar salt okunur olarak incelenir. "
            "Uzantı, dosya imzası, SHA256 ve dosya adı göstergeleri analiz edilir. "
            "Bu modül bir antivirüs değildir ve kesin kötü amaçlı yazılım tespiti yapmaz."
        )
        nd.setWordWrap(True)
        nd.setObjectName("MutedText")

        nl.addWidget(nt)
        nl.addWidget(nd)

        root.addWidget(notice)

        # İSTATİSTİK KARTLARI
        cards = QHBoxLayout()
        self.metrics = {}

        metric_items = (
            ("total", "TARANAN DOSYALAR"),
            ("high", "YÜKSEK / KRİTİK"),
            ("medium", "ORTA RİSK"),
            ("low", "DÜŞÜK RİSK")
        )

        for key, label in metric_items:
            card = QFrame()
            card.setObjectName("SurfaceCard")

            cl = QVBoxLayout(card)
            cl.setContentsMargins(15, 10, 15, 10)

            cap = QLabel(label)
            cap.setObjectName("CardTitle")

            val = QLabel("0")
            val.setObjectName("CardValue")

            cl.addWidget(cap)
            cl.addWidget(val)

            cards.addWidget(card)
            self.metrics[key] = val

        root.addLayout(cards)

        # FİLTRELER
        filters = QHBoxLayout()

        risk_label = QLabel("Risk Seviyesi:")

        self.risk = QComboBox()

        risk_options = [
            ("Tüm Riskler", "All Risks"),
            ("Kritik", "CRITICAL"),
            ("Yüksek", "HIGH"),
            ("Orta", "MEDIUM"),
            ("Düşük", "LOW"),
            ("Hata", "ERROR")
        ]

        for visible_text, internal_value in risk_options:
            self.risk.addItem(visible_text, internal_value)

        self.risk.currentIndexChanged.connect(self.apply_filters)

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Dosya adı, konum, hash veya bulgu ara..."
        )
        self.search.textChanged.connect(self.apply_filters)

        filters.addWidget(risk_label)
        filters.addWidget(self.risk, 1)
        filters.addWidget(self.search, 3)

        root.addLayout(filters)

        # SONUÇ TABLOSU
        self.table = QTableWidget(0, 6)

        self.table.setHorizontalHeaderLabels([
            "Risk Seviyesi",
            "Puan",
            "Dosya Adı",
            "Uzantı",
            "Boyut",
            "SHA256"
        ])

        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        h = self.table.horizontalHeader()

        h.setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )

        h.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch
        )

        h.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.Stretch
        )

        self.table.setStyleSheet("""
            QTableWidget {
                background:#111C2E;
                alternate-background-color:#142238;
                color:#E2E8F0;
                border:1px solid #263449;
                border-radius:8px;
                gridline-color:#263449;
                selection-background-color:#164E3C;
            }

            QHeaderView::section {
                background:#17253A;
                color:#34D399;
                padding:10px;
                border:0;
                font-weight:700;
            }
        """)

        self.table.cellDoubleClicked.connect(self.show_details)

        root.addWidget(self.table, 1)

        # ALT BİLGİ VE DIŞA AKTARMA
        footer = QHBoxLayout()

        self.status = QLabel(
            "Hazır — başlamak için bir dosya veya klasör seçin."
        )
        self.status.setObjectName("MutedText")

        footer.addWidget(self.status)
        footer.addStretch()

        export = QPushButton("CSV Dışa Aktar")
        export.setObjectName("SecondaryButton")
        export.clicked.connect(self.export_csv)

        footer.addWidget(export)

        root.addLayout(footer)

    # DOSYA TARAMA
    def scan_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "İncelenecek Dosyayı Seçin"
        )

        if path:
            self.run_scan(path)

    # KLASÖR TARAMA
    def scan_folder(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "İncelenecek Klasörü Seçin"
        )

        if path:
            self.run_scan(path)

    # TARAMA İŞLEMİ
    def run_scan(self, path):
        self.file_btn.setEnabled(False)
        self.folder_btn.setEnabled(False)

        self.status.setText(f"Taranıyor: {path}")

        try:
            self.results, skipped = scan_path(
                path,
                recursive=True,
                max_files=5000
            )

            counts = {
                risk: sum(
                    item["risk"] == risk
                    for item in self.results
                )
                for risk in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
            }

            self.metrics["total"].setText(
                f"{len(self.results):,}"
            )

            self.metrics["high"].setText(
                f"{counts['CRITICAL'] + counts['HIGH']:,}"
            )

            self.metrics["medium"].setText(
                f"{counts['MEDIUM']:,}"
            )

            self.metrics["low"].setText(
                f"{counts['LOW']:,}"
            )

            self.apply_filters()

            self.status.setText(
                f"Tarama tamamlandı: {len(self.results):,} dosya | "
                f"Atlanan dosya / sınır hatası: {skipped}"
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Tarama Hatası",
                f"Tarama sırasında hata oluştu:\n{exc}"
            )

            self.status.setText("Tarama başarısız oldu.")

        finally:
            self.file_btn.setEnabled(True)
            self.folder_btn.setEnabled(True)

    # FİLTRELEME
    def apply_filters(self, *_):
        risk = self.risk.currentData()
        query = self.search.text().casefold().strip()

        rows = []

        for item in self.results:

            if risk != "All Risks" and item["risk"] != risk:
                continue

            haystack = " ".join([
                item["name"],
                item["path"],
                item["sha256"],
                " ".join(item["reasons"])
            ]).casefold()

            if query and query not in haystack:
                continue

            rows.append(item)

        self.filtered_results = rows
        self.table.setRowCount(len(rows))

        for r, item in enumerate(rows):

            risk_value = item["risk"]
            risk_label = self.RISK_LABELS.get(
                risk_value,
                risk_value
            )

            vals = [
                risk_label,
                str(item["score"]),
                item["name"],
                item["extension"],
                self.format_size(item["size"]),
                item["sha256"] or "-"
            ]

            for c, val in enumerate(vals):

                cell = QTableWidgetItem(val)

                cell.setToolTip(
                    item["path"] if c == 2 else val
                )

                if c == 0:
                    cell.setForeground(
                        Qt.GlobalColor.white
                    )

                    cell.setForeground(
                        self.RISK_COLORS.get(
                            risk_value,
                            "#E2E8F0"
                        )
                    )

                self.table.setItem(r, c, cell)

            self.table.setRowHeight(r, 33)

        self.status.setText(
            f"Gösterilen: {len(rows):,} / "
            f"Analiz edilen: {len(self.results):,} dosya"
        )

    # DOSYA BOYUTU
    @staticmethod
    def format_size(size):
        n = float(size)

        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return f"{n:.1f} {unit}"

            n /= 1024

        return f"{n:.1f} GB"

    # DETAY PENCERESİ
    def show_details(self, row, column):

        if not 0 <= row < len(self.filtered_results):
            return

        item = self.filtered_results[row]

        risk_value = item["risk"]
        risk_label = self.RISK_LABELS.get(
            risk_value,
            risk_value
        )

        dialog = QDialog(self)

        dialog.setWindowTitle(
            "CAMGOZ | Tehdit Bulgusu"
        )

        dialog.resize(820, 560)

        dialog.setStyleSheet(
            "QDialog{background:#0B1120;color:#E2E8F0;}"
        )

        layout = QVBoxLayout(dialog)

        title = QLabel(
            f'{risk_label} RİSK — {item["name"]}'
        )

        title.setStyleSheet(
            "color:#34D399;font-size:14px;font-weight:800;"
        )

        layout.addWidget(title)

        detail = QTextBrowser()

        detail.setStyleSheet("""
            QTextBrowser {
                background:#111C2E;
                color:#E2E8F0;
                border:1px solid #263449;
                padding:12px;
            }
        """)

        reasons = "\n- ".join(item["reasons"])

        detail.setPlainText(
            f'Dosya Konumu: {item["path"]}\n'
            f'Risk Seviyesi: {risk_label} ({item["score"]}/100)\n'
            f'Dosya Uzantısı: {item["extension"]}\n'
            f'Dosya Boyutu: {self.format_size(item["size"])}\n'
            f'Dosya İmzası: {item["signature"]}\n'
            f'SHA256: {item["sha256"] or "-"}\n\n'
            f'Tespit Edilen Bulgular:\n- {reasons}\n\n'
            'Değerlendirme: Bu sonuç sezgisel risk göstergelerine '
            'dayanmaktadır. Kesin bir kötü amaçlı yazılım tespiti değildir.'
        )

        layout.addWidget(detail, 1)

        close = QPushButton("Kapat")
        close.setObjectName("SecondaryButton")
        close.clicked.connect(dialog.accept)

        layout.addWidget(
            close,
            alignment=Qt.AlignmentFlag.AlignRight
        )

        dialog.exec()

    # CSV DIŞA AKTARMA
    def export_csv(self):

        if not self.filtered_results:
            QMessageBox.information(
                self,
                "CSV Dışa Aktar",
                "Dışa aktarılacak sonuç bulunamadı."
            )
            return

        name = (
            f"CAMGOZ_Tehdit_Analizi_"
            f"{datetime.now():%Y%m%d_%H%M%S}.csv"
        )

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Bulguları Dışa Aktar",
            name,
            "CSV Dosyaları (*.csv)"
        )

        if not path:
            return

        try:
            fieldnames = [
                "Dosya Konumu",
                "Dosya Adı",
                "Uzantı",
                "Boyut",
                "SHA256",
                "Dosya İmzası",
                "Risk Seviyesi",
                "Risk Puanı",
                "Bulgular",
                "Durum"
            ]

            with open(
                path,
                "w",
                newline="",
                encoding="utf-8-sig"
            ) as f:

                writer = csv.writer(f)
                writer.writerow(fieldnames)

                for item in self.filtered_results:

                    writer.writerow([
                        item["path"],
                        item["name"],
                        item["extension"],
                        item["size"],
                        item["sha256"],
                        item["signature"],
                        self.RISK_LABELS.get(
                            item["risk"],
                            item["risk"]
                        ),
                        item["score"],
                        " | ".join(item["reasons"]),
                        item.get("status", "")
                    ])

            QMessageBox.information(
                self,
                "Dışa Aktarma Başarılı",
                f"CSV dosyası oluşturuldu:\n{path}"
            )

        except OSError as exc:
            QMessageBox.critical(
                self,
                "Dışa Aktarma Hatası",
                str(exc)
            )

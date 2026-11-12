import csv
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QFrame, QDialog, QTextBrowser, QDateEdit, QCheckBox
)

from modules.timeline import collect_timeline_events


class TimelineActivityChart(QWidget):
    """Compact stacked daily activity chart, grouped by artifact source."""

    SOURCE_COLORS = {
        "Evidence": "#34D399",
        "Audit Trail": "#60A5FA",
        "USB Connection": "#FBBF24",
        "USB File Activity": "#A78BFA",
        "Browser": "#22D3EE",
        "Recent Files": "#FB7185",
    }

    date_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.events = []
        self.visible_dates = []
        self._chart_left = 52
        self._chart_right = 0
        self.setMinimumHeight(164)
        self.setMaximumHeight(190)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Bir güne tıklayarak o günün olaylarını filtreleyin")

    def set_events(self, events):
        self.events = list(events or [])
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111E30"))

        outer = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor("#263449"), 1))
        painter.setBrush(QColor("#111E30"))
        painter.drawRoundedRect(outer, 9, 9)

        left, right = 52, self.width() - 18
        top, bottom = 31, self.height() - 30
        chart_height = max(35, bottom - top)

        painter.setPen(QColor("#94A3B8"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        painter.drawText(16, 19, "GÜNLÜK ETKİNLİK")

        # Legend: only show sources present in the selected data.
        present_sources = []
        for source in self.SOURCE_COLORS:
            if any(item.get("source") == source for item in self.events):
                present_sources.append(source)

        legend_x = 150
        painter.setFont(QFont("Segoe UI", 7))
        for source in present_sources:
            color = QColor(self.SOURCE_COLORS[source])
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(legend_x, 11, 7, 7), 2, 2)
            painter.setPen(QColor("#CBD5E1"))
            legend_labels = {
                "Evidence": "Kanıt",
                "Audit Trail": "Denetim",
                "USB Connection": "USB Bağlantısı",
                "USB File Activity": "USB Dosya",
                "Browser": "Tarayıcı",
                "Recent Files": "Son Dosyalar",
            }
            painter.drawText(legend_x + 11, 19, legend_labels.get(source, source))
            legend_x += painter.fontMetrics().horizontalAdvance(source) + 27
            if legend_x > self.width() - 80:
                break

        daily = {}
        for item in self.events:
            date_text = str(item.get("date") or "")[:10]
            try:
                datetime.strptime(date_text, "%Y-%m-%d")
            except ValueError:
                continue
            source = item.get("source", "Other")
            daily.setdefault(date_text, {})
            daily[date_text][source] = daily[date_text].get(source, 0) + 1

        dates = sorted(daily.keys())[-14:]
        self.visible_dates = dates
        self._chart_left = left
        self._chart_right = right
        if not dates:
            painter.setPen(QColor("#64748B"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(18, top + 28, "Grafik için tarih bilgisi içeren olay bulunamadı.")
            painter.end()
            return

        totals = [sum(daily[date].values()) for date in dates]
        max_total = max(totals) or 1
        slot_width = (right - left) / max(1, len(dates))
        bar_width = min(28.0, slot_width * 0.58)

        # Grid lines and scale labels.
        painter.setPen(QPen(QColor("#263449"), 1, Qt.PenStyle.DashLine))
        painter.setFont(QFont("Segoe UI", 7))
        for fraction in (0.0, 0.5, 1.0):
            y = bottom - chart_height * fraction
            painter.drawLine(int(left), int(y), int(right), int(y))
            label_value = int(max_total * fraction)
            painter.setPen(QColor("#64748B"))
            painter.drawText(8, int(y + 3), str(label_value))
            painter.setPen(QPen(QColor("#263449"), 1, Qt.PenStyle.DashLine))

        for index, date in enumerate(dates):
            x_center = left + slot_width * (index + 0.5)
            y_cursor = bottom
            for source, color_hex in self.SOURCE_COLORS.items():
                count = daily[date].get(source, 0)
                if not count:
                    continue
                segment_height = chart_height * count / max_total
                y_cursor -= segment_height
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(color_hex))
                painter.drawRoundedRect(
                    QRectF(x_center - bar_width / 2, y_cursor, bar_width,
                           max(2.0, segment_height - 1)),
                    2, 2
                )

            painter.setPen(QColor("#94A3B8"))
            painter.setFont(QFont("Segoe UI", 7))
            painter.drawText(
                QRectF(x_center - slot_width / 2, bottom + 7, slot_width, 16),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                date[5:]
            )

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.visible_dates:
            left, right = self._chart_left, self._chart_right
            if left <= event.position().x() <= right:
                slot_width = (right - left) / len(self.visible_dates)
                index = int((event.position().x() - left) / slot_width)
                index = max(0, min(index, len(self.visible_dates) - 1))
                self.date_clicked.emit(self.visible_dates[index])
        super().mousePressEvent(event)


class HourlyActivityChart(QWidget):
    """Hourly event distribution for the selected date."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.events = []
        self.selected_date = ""
        self.setMinimumHeight(125)
        self.setMaximumHeight(145)

    def set_data(self, events, selected_date):
        self.events = list(events or [])
        self.selected_date = selected_date or ""
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111E30"))
        painter.setPen(QPen(QColor("#263449"), 1))
        painter.setBrush(QColor("#111E30"))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 9, 9)

        painter.setPen(QColor("#94A3B8"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        label = f"SAATLİK ETKİNLİK — {self.selected_date}" if self.selected_date else "SAATLİK ETKİNLİK — ÖNCE YUKARIDAN BİR GÜN SEÇİN"
        painter.drawText(16, 19, label)

        if not self.selected_date:
            painter.setPen(QColor("#64748B"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(18, 75, "Günlük grafikte bir güne tıklayın.")
            painter.end()
            return

        counts = [0] * 24
        for item in self.events:
            stamp = str(item.get("date") or "")
            if stamp[:10] != self.selected_date:
                continue
            try:
                hour = int(stamp[11:13])
                if 0 <= hour <= 23:
                    counts[hour] += 1
            except (ValueError, IndexError):
                continue

        max_count = max(counts) or 1
        left, right = 34, self.width() - 18
        top, bottom = 34, self.height() - 25
        chart_height = bottom - top
        slot = (right - left) / 24
        bar_width = max(3.0, slot * 0.58)

        painter.setPen(QPen(QColor("#263449"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(left, bottom, right, bottom)
        for hour, count in enumerate(counts):
            height = chart_height * count / max_count
            x = left + slot * hour + (slot - bar_width) / 2
            y = bottom - height
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#22D3EE" if count else "#263449"))
            painter.drawRoundedRect(QRectF(x, y, bar_width, max(2, height)), 2, 2)
            if hour % 2 == 0:
                painter.setPen(QColor("#94A3B8"))
                painter.setFont(QFont("Segoe UI", 7))
                painter.drawText(QRectF(left + slot * hour - 4, bottom + 5, slot + 8, 14),
                                 Qt.AlignmentFlag.AlignHCenter, f"{hour:02d}")
        painter.end()



class TimelineAnalysisPage(QWidget):
    def __init__(self):
        super().__init__()
        self.events = []
        self.filtered_events = []
        self.init_ui()
        self.refresh_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title_layout = QVBoxLayout()
        title = QLabel("Zaman Çizelgesi Analizi")
        title.setStyleSheet("color:#E2E8F0;font-size:25px;font-weight:bold;")
        subtitle = QLabel("Farklı dijital izleri tek bir kronolojik olay akışında inceleyin.")
        subtitle.setStyleSheet("color:#94A3B8;font-size:12px;")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header.addLayout(title_layout)
        header.addStretch()

        self.refresh_button = QPushButton("⟳  Zaman Çizelgesini Yenile")
        self.refresh_button.setFixedHeight(38)
        self.refresh_button.setStyleSheet("""
            QPushButton { background:#10B981;color:#06251D;border:0;
                border-radius:7px;padding:0 18px;font-weight:bold; }
            QPushButton:hover { background:#34D399; }
            QPushButton:disabled { background:#475569;color:#CBD5E1; }
        """)
        self.refresh_button.clicked.connect(self.refresh_data)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        info = QFrame()
        info.setStyleSheet("QFrame{background:#111E30;border:1px solid #263449;border-radius:9px;}")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(16, 11, 16, 11)
        info_title = QLabel("BİRLEŞİK ADLİ BİLİŞİM ZAMAN ÇİZELGESİ")
        info_title.setStyleSheet("color:#34D399;font-size:10px;font-weight:bold;letter-spacing:2px;")
        info_text = QLabel(
            "Evidence, Audit Trail, USB, Browser ve Recent Files kayıtları birleştirilir. "
            "Kaynak veriler salt okunur şekilde alınır."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color:#94A3B8;font-size:12px;")
        info_layout.addWidget(info_title)
        info_layout.addWidget(info_text)
        layout.addWidget(info)

        self.activity_chart = TimelineActivityChart()
        self.activity_chart.date_clicked.connect(self.select_chart_date)
        layout.addWidget(self.activity_chart)

        self.hourly_chart = HourlyActivityChart()
        layout.addWidget(self.hourly_chart)

        filters = QHBoxLayout()
        self.source_combo = QComboBox()
        for label, value in [
            ("Tüm Kaynaklar", "All Sources"),
            ("Kanıt", "Evidence"),
            ("Denetim Kaydı", "Audit Trail"),
            ("USB Bağlantısı", "USB Connection"),
            ("USB Dosya Etkinliği", "USB File Activity"),
            ("Tarayıcı", "Browser"),
            ("Son Kullanılan Dosyalar", "Recent Files"),
        ]:
            self.source_combo.addItem(label, value)
        self.source_combo.setMinimumHeight(36)
        self.source_combo.setStyleSheet(self.combo_style())
        self.source_combo.currentIndexChanged.connect(self.apply_filters)

        self.type_input = QLineEdit()
        self.type_input.setPlaceholderText("Olay türü...")
        self.type_input.setMinimumHeight(36)
        self.type_input.setStyleSheet(self.input_style())
        self.type_input.textChanged.connect(self.apply_filters)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Başlık, ayrıntı veya referans ara...")
        self.search_input.setMinimumHeight(36)
        self.search_input.setStyleSheet(self.input_style())
        self.search_input.textChanged.connect(self.apply_filters)

        filters.addWidget(QLabel("Source:"))
        filters.addWidget(self.source_combo, 1)
        filters.addWidget(self.type_input, 1)
        filters.addWidget(self.search_input, 2)
        layout.addLayout(filters)

        date_filters = QHBoxLayout()
        self.use_date_filter = QCheckBox("Tarih aralığı")
        self.use_date_filter.setStyleSheet("color:#CBD5E1; spacing:7px;")
        self.use_date_filter.toggled.connect(self.apply_filters)
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("yyyy-MM-dd")
        self.from_date.setDate(datetime.now().date().replace(day=1))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("yyyy-MM-dd")
        self.to_date.setDate(datetime.now().date())
        for widget in (self.from_date, self.to_date):
            widget.setEnabled(False)
            widget.setMinimumHeight(34)
            widget.setStyleSheet(self.input_style())
            widget.dateChanged.connect(self.apply_filters)
        self.use_date_filter.toggled.connect(self.from_date.setEnabled)
        self.use_date_filter.toggled.connect(self.to_date.setEnabled)

        self.export_button = QPushButton("CSV Dışa Aktar")
        self.export_button.setMinimumHeight(34)
        self.export_button.setStyleSheet("""
            QPushButton { background:#17263B;color:#CBD5E1;border:1px solid #334155;
                border-radius:6px;padding:0 14px;font-weight:bold; }
            QPushButton:hover { background:#263449;color:#FFFFFF; }
        """)
        self.export_button.clicked.connect(self.export_csv)
        self.correlation_button = QPushButton("Korelasyonları Bul")
        self.correlation_button.setMinimumHeight(34)
        self.correlation_button.setStyleSheet("""
            QPushButton { background:#145B48;color:#E2E8F0;border:1px solid #1F8064;
                border-radius:6px;padding:0 14px;font-weight:bold; }
            QPushButton:hover { background:#176B54; }
        """)
        self.correlation_button.clicked.connect(self.show_correlations)
        date_filters.addWidget(self.use_date_filter)
        date_filters.addWidget(QLabel("Başlangıç:"))
        date_filters.addWidget(self.from_date)
        date_filters.addWidget(QLabel("Bitiş:"))
        date_filters.addWidget(self.to_date)
        date_filters.addStretch()
        date_filters.addWidget(self.correlation_button)
        date_filters.addWidget(self.export_button)
        layout.addLayout(date_filters)

        self.summary = QLabel("0 olay")
        self.summary.setStyleSheet("color:#94A3B8;font-size:11px;")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Tarih / Saat", "Kaynak", "Olay Türü", "Başlık", "Ayrıntılar"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 155)
        self.table.setColumnWidth(1, 135)
        self.table.setColumnWidth(2, 190)
        self.table.setColumnWidth(3, 220)
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
        return """
            QComboBox { background:#111E30;color:#E2E8F0;border:1px solid #334155;
                border-radius:7px;padding:0 9px;min-height:34px; }
            QComboBox:hover { border:1px solid #475569; }
            QComboBox:focus { background:#111E30;color:#E2E8F0;border:1px solid #10B981; }
            QComboBox::drop-down { background:#17263B;border:0;width:26px; }
            QComboBox QAbstractItemView { background:#111E30;color:#E2E8F0;
                border:1px solid #334155;outline:0;selection-background-color:#145B48;
                selection-color:#FFFFFF; }
            QComboBox QAbstractItemView::item { background:#111E30;color:#E2E8F0;padding:7px; }
            QComboBox QAbstractItemView::item:hover { background:#172F42;color:#FFFFFF; }
            QComboBox QAbstractItemView::item:selected { background:#145B48;color:#FFFFFF; }
        """

    @staticmethod
    def input_style():
        return """
            QLineEdit,QDateEdit { background:#111E30;color:#E2E8F0;
                border:1px solid #334155;border-radius:7px;padding:0 9px; }
            QLineEdit:focus,QDateEdit:focus { background:#111E30;color:#E2E8F0;
                border:1px solid #10B981; }
            QDateEdit::drop-down { background:#17263B;border:0;width:25px; }
        """

    def refresh_data(self):
        self.refresh_button.setEnabled(False)
        self.status.setText("Zaman çizelgesi olayları toplanıyor...")
        try:
            self.events = collect_timeline_events()
            self.events.sort(key=lambda item: item.get("date", ""), reverse=True)
            self.activity_chart.set_events(self.events)
            self.hourly_chart.set_data(self.events, "")
            self.apply_filters()
            self.status.setText("Zaman çizelgesi oluşturuldu. Kaynak veriler değiştirilmedi.")
        except Exception as exc:
            QMessageBox.critical(self, "Zaman Çizelgesi Analizi", f"Zaman çizelgesi yüklenemedi:\n\n{exc}")
            self.status.setText("Zaman çizelgesi oluşturulamadı.")
        finally:
            self.refresh_button.setEnabled(True)

    def apply_filters(self, *_):
        source = self.source_combo.currentData()
        event_type = self.type_input.text().strip().casefold()
        needle = self.search_input.text().strip().casefold()
        date_enabled = self.use_date_filter.isChecked()
        start_date = self.from_date.date().toString("yyyy-MM-dd")
        end_date = self.to_date.date().toString("yyyy-MM-dd")

        filtered = []
        for event in self.events:
            event_date = str(event.get("date") or "")
            if source != "All Sources" and event.get("source") != source:
                continue
            if event_type and event_type not in str(event.get("event_type", "")).casefold():
                continue
            searchable = " ".join(
                str(event.get(key, "")) for key in ("title", "details", "reference", "event_type")
            ).casefold()
            if needle and needle not in searchable:
                continue
            if date_enabled:
                date_part = event_date[:10]
                if not date_part or date_part < start_date or date_part > end_date:
                    continue
            filtered.append(event)

        self.filtered_events = filtered
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(len(filtered))
            for row, event in enumerate(filtered):
                values = [
                    event.get("date", ""), {
                        "Evidence": "Kanıt",
                        "Audit Trail": "Denetim Kaydı",
                        "USB Connection": "USB Bağlantısı",
                        "USB File Activity": "USB Dosya Etkinliği",
                        "Browser": "Tarayıcı",
                        "Recent Files": "Son Kullanılan Dosyalar",
                    }.get(event.get("source", ""), event.get("source", "")),
                    event.get("event_type", ""), event.get("title", ""),
                    event.get("details", ""),
                ]
                for col, value in enumerate(values):
                    display = str(value or "-")
                    cell = QTableWidgetItem(display)
                    cell.setToolTip(display)
                    if col == 1:
                        # Kaynak kimlikleri dahili olarak İngilizce kalır.
                        cell.setForeground(Qt.GlobalColor.cyan if event.get("source") == "Browser"
                                           else Qt.GlobalColor.green if event.get("source") == "Evidence"
                                           else Qt.GlobalColor.yellow if event.get("source") == "USB Connection"
                                           else Qt.GlobalColor.white)
                    self.table.setItem(row, col, cell)
                self.table.setRowHeight(row, 32)
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.viewport().update()

        self.summary.setText(f"{len(filtered):,} / {len(self.events):,} olay gösteriliyor")
        self.status.setText(f"Filtreleme sonrası {len(filtered):,} olay")


    def select_chart_date(self, selected_date):
        """Filter the event table to the day selected on the daily chart."""
        self.use_date_filter.setChecked(True)
        from_date = self.from_date.date()
        to_date = self.to_date.date()
        qdate = self.from_date.date().fromString(selected_date, "yyyy-MM-dd")
        if not qdate.isValid():
            return
        self.from_date.setDate(qdate)
        self.to_date.setDate(qdate)
        self.hourly_chart.set_data(self.events, selected_date)
        self.apply_filters()

    @staticmethod
    def _parse_event_datetime(value):
        text = str(value or "").strip()
        if not text:
            return None
        # Normalize common ISO strings and timestamps emitted by current collectors.
        candidates = [text, text.replace("T", " ", 1)]
        for candidate in candidates:
            try:
                parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
                if parsed.tzinfo is not None:
                    parsed = parsed.astimezone().replace(tzinfo=None)
                return parsed
            except ValueError:
                pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text[:19], fmt)
            except ValueError:
                continue
        return None

    def find_correlations(self, window_seconds=120):
        """Return heuristic cross-source event pairs within a time window.

        These are investigative leads, not proof of causation.
        """
        parsed = []
        for event in self.events:
            moment = self._parse_event_datetime(event.get("date"))
            if moment is not None:
                parsed.append((moment, event))
        parsed.sort(key=lambda pair: pair[0])

        usb_types = {"USB_CONNECTION", "USB_FILE_ACTIVITY"}
        candidates = []
        seen = set()
        for index, (moment, event) in enumerate(parsed):
            source = event.get("source", "")
            event_type = str(event.get("event_type", "")).upper()
            is_usb = source in ("USB Connection", "USB File Activity")
            if not is_usb:
                continue

            end = moment + timedelta(seconds=window_seconds)
            for other_moment, other in parsed[index + 1:]:
                if other_moment > end:
                    break
                if other.get("source") == source:
                    continue
                if other.get("source") not in ("Browser", "Recent Files", "Evidence", "Audit Trail"):
                    continue
                delta = int((other_moment - moment).total_seconds())
                key = (id(event), id(other))
                if key in seen:
                    continue
                seen.add(key)
                candidates.append({
                    "date": moment.strftime("%Y-%m-%d %H:%M:%S"),
                    "gap": delta,
                    "first": event,
                    "second": other,
                    "reason": (
                        f'{source} olayı ile {other.get("source")} olayı arasında '
                        f'{delta} saniye var.'
                    ),
                })
        candidates.sort(key=lambda item: item["gap"])
        return candidates[:500]

    def show_correlations(self):
        correlations = self.find_correlations()
        dialog = QDialog(self)
        dialog.setWindowTitle("CAMGOZ | Olay Korelasyonları")
        dialog.resize(1050, 650)
        dialog.setStyleSheet("QDialog{background:#0B1424;color:#E2E8F0;}")
        layout = QVBoxLayout(dialog)

        heading = QLabel(
            f"{len(correlations)} candidate correlations | 120-second window"
        )
        heading.setStyleSheet("color:#34D399;font-size:13px;font-weight:bold;")
        layout.addWidget(heading)

        note = QLabel(
            "These are time-proximity leads for manual investigation, not proof that "
            "one event caused another. Confirm paths, device identifiers and source records."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#94A3B8;font-size:11px;")
        layout.addWidget(note)

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels([
            "USB Olay Zamanı", "Zaman Farkı", "USB Olayı", "İlişkili Olay", "İlişkili Kaynak"
        ])
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        table.setStyleSheet("""
            QTableWidget{background:#0F1B2B;color:#CBD5E1;gridline-color:#263449;
                border:1px solid #263449;selection-background-color:#145B48;}
            QHeaderView::section{background:#17263B;color:#94A3B8;border:0;padding:9px;}
        """)
        table.setRowCount(len(correlations))
        for row, item in enumerate(correlations):
            first, second = item["first"], item["second"]
            values = [
                item["date"],
                f'{item["gap"]} sec',
                f'{first.get("event_type", "-")} — {first.get("title", "-")}',
                f'{second.get("event_type", "-")} — {second.get("title", "-")}',
                second.get("source", "-"),
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setToolTip(str(value))
                table.setItem(row, col, cell)
            table.setRowHeight(row, 32)
        layout.addWidget(table, 1)

        close = QPushButton("Kapat")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def show_details(self, row, column):
        if row < 0 or row >= len(self.filtered_events):
            return
        event = self.filtered_events[row]
        dialog = QDialog(self)
        dialog.setWindowTitle("CAMGOZ | Zaman Çizelgesi Olayı")
        dialog.resize(850, 600)
        dialog.setStyleSheet("QDialog{background:#0B1424;color:#E2E8F0;}")
        layout = QVBoxLayout(dialog)
        heading = QLabel(f'{event.get("event_type", "EVENT")} — {event.get("source", "")}')
        heading.setStyleSheet("color:#34D399;font-weight:bold;font-size:13px;")
        layout.addWidget(heading)
        details = QTextBrowser()
        details.setStyleSheet("background:#111E30;color:#CBD5E1;border:1px solid #263449;padding:12px;")
        details.setPlainText(
            f'Date: {event.get("date", "-")}\n'
            f'Source: {event.get("source", "-")}\n'
            f'Event Type: {event.get("event_type", "-")}\n'
            f'Title: {event.get("title", "-")}\n\n'
            f'Details:\n{event.get("details", "-")}\n\n'
            f'Reference:\n{event.get("reference", "-")}'
        )
        layout.addWidget(details)
        close = QPushButton("Kapat")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def export_csv(self):
        if not self.filtered_events:
            QMessageBox.information(self, "CSV Dışa Aktar", "Dışa aktarılacak olay bulunamadı.")
            return
        default_name = f"CAMGOZ_Timeline_{datetime.now():%Y%m%d_%H%M%S}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Zaman Çizelgesini Dışa Aktar", default_name, "CSV Dosyaları (*.csv)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["date", "source", "event_type", "title", "details", "reference"],
                )
                writer.writeheader()
                writer.writerows(self.filtered_events)
            QMessageBox.information(self, "CSV Dışa Aktar", f"CSV raporu oluşturuldu:\n{file_path}")
        except OSError as exc:
            QMessageBox.critical(self, "CSV Dışa Aktar", f"Dosya yazılamadı:\n{exc}")

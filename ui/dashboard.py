
import json

from datetime import datetime, timedelta, timezone

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
    QGridLayout, QSizePolicy
)

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QFont
)

from sqlalchemy import select, func

from database.database import SessionLocal
from database.models import Evidence, AuditEvent

from ui.components.stat_card import StatCard


class ActivityChart(QWidget):

    def __init__(self):
        super().__init__()

        self.setMinimumHeight(235)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.values = [0] * 7
        self.labels = []

    def set_data(self, values, labels):
        self.values = values
        self.labels = labels
        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        width = self.width()
        height = self.height()

        left = 42
        right = 15
        top = 20
        bottom = 35

        chart_width = width - left - right
        chart_height = height - top - bottom

        max_value = max(max(self.values, default=0), 1)

        # YATAY KILAVUZ ÇİZGİLERİ
        for i in range(4):

            y = top + (chart_height / 3) * i

            painter.setPen(
                QPen(QColor("#263449"), 1)
            )

            painter.drawLine(
                left,
                int(y),
                width - right,
                int(y)
            )

        # GRAFİK SÜTUNLARI
        slot_width = chart_width / 7
        bar_width = min(28, slot_width * 0.45)

        for index, value in enumerate(self.values):

            bar_height = (
                value / max_value
            ) * (chart_height - 10)

            x = (
                left
                + index * slot_width
                + (slot_width - bar_width) / 2
            )

            y = top + chart_height - bar_height

            rect = QRectF(
                x,
                y,
                bar_width,
                max(bar_height, 3)
            )

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#10B981"))

            painter.drawRoundedRect(
                rect,
                5,
                5
            )

            # SÜTUN ÜSTÜNDEKİ DEĞER
            painter.setPen(QColor("#94A3B8"))
            painter.setFont(QFont("Segoe UI", 8))

            painter.drawText(
                QRectF(
                    x - 10,
                    y - 19,
                    bar_width + 20,
                    16
                ),
                Qt.AlignmentFlag.AlignCenter,
                str(value)
            )

            # GÜN İSMİ
            painter.drawText(
                QRectF(
                    left + index * slot_width,
                    height - 25,
                    slot_width,
                    20
                ),
                Qt.AlignmentFlag.AlignCenter,
                self.labels[index]
            )

        painter.end()


class DashboardPage(QWidget):

    def __init__(self):
        super().__init__()

        self.init_ui()
        self.refresh_data()

    def init_ui(self):

        main_layout = QVBoxLayout(self)

        main_layout.setContentsMargins(
            30, 25, 30, 25
        )

        main_layout.setSpacing(20)

        # BAŞLIK ALANI
        header = QHBoxLayout()

        title_area = QVBoxLayout()

        title = QLabel("Genel Bakış")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Dijital adli bilişim incelemelerinizi buradan takip edin."
        )
        subtitle.setObjectName("PageSubtitle")

        title_area.addWidget(title)
        title_area.addWidget(subtitle)

        refresh_button = QPushButton("↻  Yenile")
        refresh_button.setObjectName("SecondaryButton")
        refresh_button.clicked.connect(self.refresh_data)

        header.addLayout(title_area)
        header.addStretch()
        header.addWidget(refresh_button)

        main_layout.addLayout(header)

        # İSTATİSTİK KARTLARI
        cards_layout = QGridLayout()
        cards_layout.setSpacing(15)

        self.evidence_card = StatCard(
            "Toplam Kanıt",
            "0",
            "Kaydedilen kanıt kayıtları",
            "#34D399",
            "▣"
        )

        self.verified_card = StatCard(
            "Doğrulanan Dosyalar",
            "0",
            "Başarılı bütünlük kontrolleri",
            "#34D399",
            "✓"
        )

        self.warning_card = StatCard(
            "Bütünlük Uyarıları",
            "0",
            "Başarısız veya eksik dosya kontrolleri",
            "#FBBF24",
            "!"
        )

        self.audit_card = StatCard(
            "Denetim Olayları",
            "0",
            "Kaydedilen sistem etkinlikleri",
            "#60A5FA",
            "◷"
        )

        cards_layout.addWidget(
            self.evidence_card, 0, 0
        )

        cards_layout.addWidget(
            self.verified_card, 0, 1
        )

        cards_layout.addWidget(
            self.warning_card, 0, 2
        )

        cards_layout.addWidget(
            self.audit_card, 0, 3
        )

        main_layout.addLayout(cards_layout)

        # ALT İÇERİK
        lower_layout = QHBoxLayout()
        lower_layout.setSpacing(15)

        # İNCELEME AKTİVİTESİ GRAFİĞİ
        chart_card = QFrame()
        chart_card.setObjectName("SurfaceCard")

        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(
            20, 18, 20, 18
        )

        chart_title = QLabel("İnceleme Aktivitesi")
        chart_title.setStyleSheet(
            "font-size: 15px; font-weight: 700;"
        )

        chart_subtitle = QLabel(
            "Son 7 gündeki denetim olayları"
        )
        chart_subtitle.setObjectName("MutedText")

        self.chart = ActivityChart()

        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(chart_subtitle)
        chart_layout.addWidget(self.chart)

        # SON AKTİVİTELER
        activity_card = QFrame()
        activity_card.setObjectName("SurfaceCard")
        activity_card.setMinimumWidth(290)
        activity_card.setMaximumWidth(350)

        activity_layout = QVBoxLayout(activity_card)

        activity_layout.setContentsMargins(
            18, 18, 18, 18
        )

        activity_title = QLabel("Son Aktiviteler")
        activity_title.setStyleSheet(
            "font-size: 15px; font-weight: 700;"
        )

        self.activity_list = QVBoxLayout()
        self.activity_list.setSpacing(13)

        activity_layout.addWidget(activity_title)
        activity_layout.addSpacing(10)
        activity_layout.addLayout(self.activity_list)
        activity_layout.addStretch()

        lower_layout.addWidget(chart_card, 3)
        lower_layout.addWidget(activity_card, 2)

        main_layout.addLayout(lower_layout, 1)

    # VERİLERİ YENİLE
    def refresh_data(self):

        try:

            with SessionLocal() as session:

                evidence_count = session.scalar(
                    select(func.count()).select_from(Evidence)
                ) or 0

                audit_count = session.scalar(
                    select(func.count()).select_from(AuditEvent)
                ) or 0

                events = session.scalars(
                    select(AuditEvent)
                    .order_by(AuditEvent.id.desc())
                    .limit(1000)
                ).all()

                now = datetime.now(timezone.utc)
                today = now.date()

                daily_counts = {
                    today - timedelta(days=i): 0
                    for i in range(6, -1, -1)
                }

                verified_count = 0
                warning_count = 0

                recent_events = []

                for event in events:

                    try:
                        details = json.loads(
                            event.details or "{}"
                        )
                    except (ValueError, TypeError):
                        details = {}

                    if event.event_type == "EVIDENCE_INTEGRITY_CHECK":

                        status = details.get("status")

                        if status == "INTEGRITY_VERIFIED":
                            verified_count += 1

                        elif status in (
                            "INTEGRITY_FAILED",
                            "FILE_MISSING"
                        ):
                            warning_count += 1

                    try:
                        event_date = datetime.fromisoformat(
                            event.event_time
                        ).date()

                        if event_date in daily_counts:
                            daily_counts[event_date] += 1

                    except (ValueError, TypeError):
                        pass

                    if len(recent_events) < 5:
                        recent_events.append({
                            "type": event.event_type,
                            "actor": event.actor,
                            "time": event.event_time
                        })

            # İSTATİSTİK KARTLARINI GÜNCELLE
            self.evidence_card.set_value(
                str(evidence_count)
            )

            self.verified_card.set_value(
                str(verified_count)
            )

            self.warning_card.set_value(
                str(warning_count)
            )

            self.audit_card.set_value(
                str(audit_count)
            )

            # GRAFİĞİ GÜNCELLE
            dates = list(daily_counts.keys())

            values = [
                daily_counts[date]
                for date in dates
            ]

            turkish_days = [
                "Pzt", "Sal", "Çar", "Per",
                "Cum", "Cmt", "Paz"
            ]

            labels = [
                turkish_days[date.weekday()]
                for date in dates
            ]

            self.chart.set_data(values, labels)

            # SON AKTİVİTELERİ GÜNCELLE
            self.clear_activity_list()

            if not recent_events:

                empty_label = QLabel(
                    "Henüz kaydedilmiş bir aktivite yok."
                )

                empty_label.setObjectName("MutedText")

                self.activity_list.addWidget(
                    empty_label
                )

            else:

                for event in recent_events:
                    self.add_activity_item(event)

            self.activity_list.addStretch()

        except Exception as error:

            print(f"Genel bakış hatası: {error}")

    # AKTİVİTE LİSTESİNİ TEMİZLE
    def clear_activity_list(self):

        while self.activity_list.count():

            item = self.activity_list.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

    # AKTİVİTE KARTI OLUŞTUR
    def add_activity_item(self, event):

        container = QWidget()

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        event_translations = {
            "EVIDENCE_CREATED": "Kanıt oluşturuldu",
            "EVIDENCE_UPDATED": "Kanıt güncellendi",
            "EVIDENCE_RESTORED": "Kanıt geri yüklendi",
            "EVIDENCE_ARCHIVED": "Kanıt arşivlendi",
            "EVIDENCE_DELETED": "Kanıt silindi",
            "EVIDENCE_INTEGRITY_CHECK": "Kanıt bütünlük kontrolü",
            "INTEGRITY_VERIFIED": "Bütünlük doğrulandı",
            "INTEGRITY_FAILED": "Bütünlük doğrulanamadı",
            "FILE_MISSING": "Dosya bulunamadı",
            "USB_CONNECTED": "USB aygıtı bağlandı",
            "USB_DISCONNECTED": "USB aygıtı çıkarıldı",
            "USB_FILE_CREATED": "USB üzerinde dosya oluşturuldu",
            "USB_FILE_MODIFIED": "USB üzerindeki dosya değiştirildi",
            "USB_FILE_DELETED": "USB üzerindeki dosya silindi",
            "USB_FILE_RENAMED": "USB üzerindeki dosya yeniden adlandırıldı"
        }

        event_type = event["type"]

        event_name = event_translations.get(
            event_type,
            event_type.replace("_", " ").title()
        )

        title = QLabel(event_name)

        title.setStyleSheet(
            "color: #E2E8F0; font-size: 11px; font-weight: 700;"
        )

        actor = QLabel(
            f"Kullanıcı: {event['actor']}"
        )

        actor.setObjectName("MutedText")

        time_label = QLabel(
            event["time"].replace("T", " ")[:19]
        )

        time_label.setStyleSheet(
            "color: #64748B; font-size: 10px;"
        )

        layout.addWidget(title)
        layout.addWidget(actor)
        layout.addWidget(time_label)

        self.activity_list.addWidget(container)

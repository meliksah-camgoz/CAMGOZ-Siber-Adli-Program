
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel
)
from PySide6.QtCore import Qt


class StatCard(QFrame):

    def __init__(
        self,
        title: str,
        value: str,
        description: str,
        accent: str = "#34D399",
        icon: str = "●"
    ):
        super().__init__()

        self.setObjectName("SurfaceCard")
        self.setMinimumHeight(145)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 17, 18, 17)
        layout.setSpacing(8)

        header = QHBoxLayout()

        title_label = QLabel(title.upper())
        title_label.setObjectName("CardTitle")

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(
            f"color: {accent}; font-size: 20px;"
        )

        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(icon_label)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        self.value_label.setStyleSheet(
            f"color: {accent};"
        )

        description_label = QLabel(description)
        description_label.setObjectName("MutedText")

        layout.addLayout(header)
        layout.addWidget(self.value_label)
        layout.addWidget(description_label)
        layout.addStretch()

    def set_value(self, value: str):
        self.value_label.setText(value)

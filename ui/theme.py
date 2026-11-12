
APP_STYLESHEET = """
* {
    font-family: "Segoe UI";
}

QMainWindow, QWidget#CentralWidget {
    background-color: #0B1120;
    color: #F1F5F9;
}

QWidget {
    color: #E2E8F0;
}

QFrame#Sidebar {
    background-color: #0F172A;
    border-right: 1px solid #1E293B;
}

QLabel#Brand {
    color: #34D399;
    font-size: 27px;
    font-weight: 800;
    letter-spacing: 1px;
}

QLabel#BrandSubtitle {
    color: #64748B;
    font-size: 9px;
    letter-spacing: 2px;
}

QLabel#PageTitle {
    color: #F8FAFC;
    font-size: 26px;
    font-weight: 700;
}

QLabel#PageSubtitle {
    color: #94A3B8;
    font-size: 12px;
}

QPushButton {
    background-color: transparent;
    color: #94A3B8;
    border: none;
    border-radius: 7px;
    padding: 11px 13px;
    text-align: left;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #1E293B;
    color: #F8FAFC;
}

QPushButton#NavButton {
    padding: 13px;
    font-size: 13px;
    text-align: left;
}

QPushButton#NavButton:checked {
    background-color: #12372F;
    color: #34D399;
    border-left: 3px solid #34D399;
    font-weight: 700;
}

QPushButton#PrimaryButton {
    background-color: #059669;
    color: #FFFFFF;
    font-weight: 700;
    padding: 11px 18px;
}

QPushButton#PrimaryButton:hover {
    background-color: #047857;
}

QPushButton#SecondaryButton {
    background-color: #1E293B;
    color: #E2E8F0;
    border: 1px solid #334155;
    padding: 10px 15px;
}

QPushButton#SecondaryButton:hover {
    background-color: #26364D;
}

QFrame#SurfaceCard {
    background-color: #111C2E;
    border: 1px solid #263449;
    border-radius: 11px;
}

QLabel#CardTitle {
    color: #94A3B8;
    font-size: 11px;
    font-weight: 600;
}

QLabel#CardValue {
    color: #F8FAFC;
    font-size: 29px;
    font-weight: 700;
}

QLabel#MutedText {
    color: #64748B;
    font-size: 11px;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QTableWidget, QTableView {
    background-color: #111C2E;
    alternate-background-color: #142238;
    color: #E2E8F0;
    gridline-color: #263449;
    border: 1px solid #263449;
    border-radius: 8px;
    selection-background-color: #164E3C;
    selection-color: #FFFFFF;
}

QHeaderView::section {
    background-color: #17253A;
    color: #34D399;
    padding: 11px;
    border: none;
    font-weight: 700;
}

QLineEdit, QComboBox {
    background-color: #111C2E;
    color: #E2E8F0;
    border: 1px solid #334155;
    border-radius: 7px;
    padding: 9px;
}

QPlainTextEdit {
    background-color: #111C2E;
    color: #34D399;
    border: 1px solid #263449;
    border-radius: 8px;
    padding: 10px;
}

QScrollBar:vertical {
    background: #0F172A;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 4px;
    min-height: 25px;
}

QScrollBar::handle:vertical:hover {
    background: #34D399;
}

QToolTip {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #34D399;
    padding: 5px;
}
"""

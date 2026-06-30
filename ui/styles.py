# Estilos QSS para los modos Claro y Oscuro de la aplicación

DARK_STYLE = """
QMainWindow {
    background-color: #09090b;
}

QWidget {
    color: #f4f4f5;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
    font-size: 13px;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #27272a;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #121214;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: #a1a1aa;
}

QLabel {
    color: #e4e4e7;
}

QLineEdit {
    background-color: #1c1c1f;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #fafafa;
}

QLineEdit:focus {
    border: 1px solid #6366f1;
}

QPushButton {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 8px 16px;
    color: #f4f4f5;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #3f3f46;
    border-color: #52525b;
}

QPushButton:pressed {
    background-color: #18181b;
}

QPushButton#primaryButton {
    background-color: #4f46e5;
    border: 1px solid #6366f1;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#primaryButton:hover {
    background-color: #4338ca;
}

QPushButton#primaryButton:pressed {
    background-color: #3730a3;
}

QPushButton#dangerButton {
    background-color: #991b1b;
    border: 1px solid #b91c1c;
    color: #ffffff;
}

QPushButton#dangerButton:hover {
    background-color: #7f1d1d;
}

QListWidget {
    background-color: #121214;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 5px;
    color: #e4e4e7;
}

QListWidget::item {
    border-bottom: 1px solid #1c1c1f;
    padding: 8px;
    border-radius: 4px;
}

QListWidget::item:hover {
    background-color: #1c1c1f;
}

QListWidget::item:selected {
    background-color: #2e2e33;
    color: #ffffff;
}

QScrollBar:vertical {
    border: none;
    background: #09090b;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #27272a;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #3f3f46;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #09090b;
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #27272a;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #3f3f46;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QScrollArea {
    border: 1px solid #27272a;
    background-color: #121214;
    border-radius: 8px;
}

#dropArea {
    border: 2px dashed #3f3f46;
    border-radius: 8px;
    background-color: #121214;
}

#dropArea[dragged="true"] {
    border-color: #6366f1;
    background-color: #1a1a24;
}
"""

LIGHT_STYLE = """
QMainWindow {
    background-color: #f4f4f5;
}

QWidget {
    color: #18181b;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
    font-size: 13px;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #e4e4e7;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: #71717a;
}

QLabel {
    color: #27272a;
}

QLineEdit {
    background-color: #f4f4f5;
    border: 1px solid #e4e4e7;
    border-radius: 6px;
    padding: 6px 10px;
    color: #09090b;
}

QLineEdit:focus {
    border: 1px solid #4f46e5;
}

QPushButton {
    background-color: #e4e4e7;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    padding: 8px 16px;
    color: #18181b;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #d4d4d8;
    border-color: #a1a1aa;
}

QPushButton:pressed {
    background-color: #e4e4e7;
}

QPushButton#primaryButton {
    background-color: #4f46e5;
    border: 1px solid #4338ca;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#primaryButton:hover {
    background-color: #4338ca;
}

QPushButton#primaryButton:pressed {
    background-color: #3730a3;
}

QPushButton#dangerButton {
    background-color: #ef4444;
    border: 1px solid #dc2626;
    color: #ffffff;
}

QPushButton#dangerButton:hover {
    background-color: #dc2626;
}

QListWidget {
    background-color: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 8px;
    padding: 5px;
    color: #18181b;
}

QListWidget::item {
    border-bottom: 1px solid #f4f4f5;
    padding: 8px;
    border-radius: 4px;
}

QListWidget::item:hover {
    background-color: #f4f4f5;
}

QListWidget::item:selected {
    background-color: #e0e7ff;
    color: #4f46e5;
}

QScrollBar:vertical {
    border: none;
    background: #f4f4f5;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #d4d4d8;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #a1a1aa;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #f4f4f5;
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #d4d4d8;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #a1a1aa;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QScrollArea {
    border: 1px solid #e4e4e7;
    background-color: #ffffff;
    border-radius: 8px;
}

#dropArea {
    border: 2px dashed #a1a1aa;
    border-radius: 8px;
    background-color: #e4e4e7;
}

#dropArea[dragged="true"] {
    border-color: #4f46e5;
    background-color: #d1d5db;
}
"""

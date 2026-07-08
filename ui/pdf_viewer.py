import os
from PySide6.QtWidgets import QScrollArea, QWidget, QLabel, QVBoxLayout, QMessageBox
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPixmap
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QRectF, QTimer

class PdfPageCanvas(QWidget):
    # Señal emitida al dibujar una nueva zona de firma: (x_pt, y_pt, w_pt, h_pt)
    zone_drawn = Signal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = None
        self.zoom = 1.0
        self.pdf_w = 0.0
        self.pdf_h = 0.0
        self.zones = []  # Lista de dicts: {"id": int, "rect_pt": QRectF}
        self.drawing = False
        self.start_pos = QPoint()
        self.current_rect = QRect()
        self._zone_emit_pending = False
        self.empty_text = "Arrastra o selecciona un PDF para comenzar"
        self.setMouseTracking(True)
        self.setMinimumSize(400, 300)

    def set_page_image(self, qimg, pdf_w, pdf_h, zoom):
        """Actualiza la imagen de la página y las dimensiones del PDF."""
        self.pixmap = QPixmap.fromImage(qimg)
        self.zoom = zoom
        self.pdf_w = pdf_w
        self.pdf_h = pdf_h
        
        # Ajustar el tamaño del widget al del PDF con zoom de pantalla
        self.setFixedSize(int(pdf_w * zoom), int(pdf_h * zoom))
        self.update()

    def set_zones(self, zones):
        """Actualiza la lista de zonas de firma para dibujar."""
        self.zones = zones
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.pixmap:
            self.start_pos = event.position().toPoint()
            self.current_rect = QRect()
            self.drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.drawing:
            self.current_rect = QRect(self.start_pos, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drawing:
            self.drawing = False
            self.current_rect = QRect(self.start_pos, event.position().toPoint()).normalized()
            
            # Solo añadir si la zona tiene un tamaño mínimo razonable (ej. 15x15 píxeles)
            if self.current_rect.width() > 15 and self.current_rect.height() > 15:
                if not self._zone_emit_pending:
                    self._zone_emit_pending = True
                    # Convertir coordenadas de píxeles (con zoom) a puntos de PDF (sin zoom)
                    x_pt = self.current_rect.x() / self.zoom
                    y_pt = self.current_rect.y() / self.zoom
                    w_pt = self.current_rect.width() / self.zoom
                    h_pt = self.current_rect.height() / self.zoom
                    
                    # Emitir señal con debounce
                    QTimer.singleShot(150, lambda: self._emit_zone(x_pt, y_pt, w_pt, h_pt))
                
            self.current_rect = QRect()
            self.update()

    def _emit_zone(self, x_pt, y_pt, w_pt, h_pt):
        self._zone_emit_pending = False
        self.zone_drawn.emit(x_pt, y_pt, w_pt, h_pt)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Dibujar la página del PDF
        if self.pixmap:
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawPixmap(self.rect(), self.pixmap)
        else:
            # Estado vacío
            painter.fillRect(self.rect(), QColor("#121214") if self.property("theme") == "dark" else QColor("#e4e4e7"))
            painter.setPen(QColor("#a1a1aa") if self.property("theme") == "dark" else QColor("#71717a"))
            font = QFont("Segoe UI", 14)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, self.empty_text)
            return

        # 2. Dibujar las zonas de firma ya guardadas
        for i, zone in enumerate(self.zones):
            rect_pt = zone["rect_pt"]
            # Escalar coordenadas de puntos a píxeles según el zoom actual
            rect_px = QRectF(
                rect_pt.x() * self.zoom,
                rect_pt.y() * self.zoom,
                rect_pt.width() * self.zoom,
                rect_pt.height() * self.zoom
            )
            
            # Estilo premium para las zonas de firma (índigo semitransparente)
            painter.setPen(QPen(QColor("#4f46e5"), 2, Qt.SolidLine))
            painter.setBrush(QBrush(QColor(79, 70, 229, 45)))  # Opacidad ligera
            painter.drawRoundedRect(rect_px, 4, 4)
            
            # Dibujar etiqueta de texto de la firma
            painter.setPen(QColor("#ffffff"))
            painter.setBrush(QBrush(QColor("#4f46e5")))
            label_rect = QRectF(rect_px.x(), rect_px.y(), max(rect_px.width(), 80), 20)
            painter.drawRoundedRect(label_rect, 2, 2)
            
            painter.setPen(QColor("#ffffff"))
            font = QFont("Segoe UI", 9, QFont.Bold)
            painter.setFont(font)
            painter.drawText(label_rect, Qt.AlignCenter, f"Firma #{zone['id']}")

        # 3. Dibujar el rectángulo que se está arrastrando actualmente
        if self.drawing and not self.current_rect.isEmpty():
            painter.setPen(QPen(QColor("#6366f1"), 2, Qt.DashLine))
            painter.setBrush(QBrush(QColor(99, 102, 241, 30)))
            painter.drawRoundedRect(self.current_rect, 4, 4)


class PdfViewer(QScrollArea):
    # Señales para comunicación con la ventana principal
    file_dropped = Signal(str)
    zone_added = Signal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        
        # Canvas de renderizado
        self.canvas = PdfPageCanvas(self)
        self.setWidget(self.canvas)
        self.setWidgetResizable(True)
        
        # Escuchar la señal de zona dibujada
        self.canvas.zone_drawn.connect(self.zone_added.emit)

    def set_theme(self, theme):
        self.canvas.setProperty("theme", theme)
        self.canvas.update()

    def set_empty_text(self, text):
        self.canvas.empty_text = text
        self.canvas.update()

    def set_page(self, qimg, pdf_w, pdf_h, zoom):
        """Asigna la página a mostrar."""
        self.canvas.setMinimumSize(0, 0)
        self.canvas.set_page_image(qimg, pdf_w, pdf_h, zoom)

    def update_zones(self, zones):
        """Actualiza las zonas dibujadas."""
        self.canvas.set_zones(zones)

    # Eventos para Drag & Drop
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) > 0 and urls[0].toLocalFile().lower().endswith(".pdf"):
                event.acceptProposedAction()
                self.setProperty("dragged", "true")
                self.style().unpolish(self)
                self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("dragged", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event):
        self.setProperty("dragged", "false")
        self.style().unpolish(self)
        self.style().polish(self)
        
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) > 0:
                filepath = urls[0].toLocalFile()
                if filepath.lower().endswith(".pdf"):
                    self.file_dropped.emit(filepath)

import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QFileDialog, QMessageBox, QProgressDialog, QAbstractItemView,
    QDialog, QDialogButtonBox, QSplitter, QSpinBox, QComboBox, QFrame,
    QSizePolicy, QScrollArea, QStyle, QInputDialog, QTabWidget
)
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt, QThread, Signal, Slot, QDate, QRectF, QTimer

from core.pdf_handler import PdfHandler, qt_to_pdf_coords, SUPPORTED_FONTS
from core.autofirma import sign_pdf_multiple_zones, detect_autofirma_path
from core.settings import (
    load_settings, save_settings,
    load_profiles, save_profiles,
    get_active_profile, DEFAULT_PROFILE
)
from ui.styles import DARK_STYLE, LIGHT_STYLE
from ui.pdf_viewer import PdfViewer

from ui.sign_thread import SignThread
from ui.config_dialog import ConfigDialog

TAB_ORIGINAL = 0
TAB_SIGNED = 1


# ---------------------------------------------------------------------------
# Ventana Principal
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FirmaPDF - Visualizador y Firma de Documentos PDF")
        self.resize(1100, 750)

        # Variables de estado
        self.pdf_handler = None
        self.pdf_handler_signed = None
        self.current_page = 0
        self.current_page_signed = 0
        self.zoom_factor = 1.0
        self.zoom_factor_signed = 1.0
        self.signature_zones = []  # Lista de dicts: {"id": int, "page": int, "rect_pt": QRectF, "coords": dict}
        self.next_zone_id = 1
        
        # Atributos adicionales
        self.tabs = None
        self.progress_dialog = None
        self.sign_thread = None
        self.last_output_pdf = None
        self.needs_initial_fit = False
        
        # Cargar configuración persistida
        self.settings = load_settings()
        self.profiles = load_profiles()
        if not self.settings["autofirma_path"]:
            self.settings["autofirma_path"] = detect_autofirma_path()
            save_settings(self.settings)

        # Inicializar interfaz
        self.init_ui()
        self.apply_theme(self.settings.get("theme", "light"))

    def init_ui(self):
        # Widget y Layout principal
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # ---------------- BARRA LATERAL IZQUIERDA ----------------
        sidebar = QWidget(self)
        sidebar.setFixedWidth(360)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(10)

        # --- Panel de Archivo ---
        file_group = QGroupBox("Documento PDF", sidebar)
        file_layout = QVBoxLayout(file_group)
        self.btn_select_pdf = QPushButton("Seleccionar PDF", file_group)
        self.btn_select_pdf.setObjectName("primaryButton")
        self.btn_select_pdf.clicked.connect(self.select_pdf_dialog)
        self.lbl_pdf_name = QLabel("Sin archivo seleccionado", file_group)
        self.lbl_pdf_name.setWordWrap(True)
        self.lbl_pdf_name.setAlignment(Qt.AlignCenter)
        self.lbl_pdf_name.setStyleSheet("color: #a1a1aa; font-style: italic;")
        file_layout.addWidget(self.btn_select_pdf)
        file_layout.addWidget(self.lbl_pdf_name)
        sidebar_layout.addWidget(file_group)

        # --- Panel de Navegación y Zoom ---
        nav_group = QGroupBox("Navegación y Vista", sidebar)
        nav_layout = QVBoxLayout(nav_group)
        
        # Navegación
        page_nav_layout = QHBoxLayout()
        self.btn_prev_page = QPushButton("Anterior", nav_group)
        self.btn_prev_page.clicked.connect(self.prev_page)
        self.btn_prev_page.setEnabled(False)
        self.lbl_page_info = QLabel("Página: - / -", nav_group)
        self.lbl_page_info.setAlignment(Qt.AlignCenter)
        self.btn_next_page = QPushButton("Siguiente", nav_group)
        self.btn_next_page.clicked.connect(self.next_page)
        self.btn_next_page.setEnabled(False)
        page_nav_layout.addWidget(self.btn_prev_page)
        page_nav_layout.addWidget(self.lbl_page_info)
        page_nav_layout.addWidget(self.btn_next_page)
        nav_layout.addLayout(page_nav_layout)

        # Zoom
        zoom_layout = QHBoxLayout()
        self.btn_zoom_out = QPushButton("- Zoom", nav_group)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_zoom_out.setEnabled(False)
        self.lbl_zoom_info = QLabel("100%", nav_group)
        self.lbl_zoom_info.setAlignment(Qt.AlignCenter)
        self.btn_zoom_in = QPushButton("+ Zoom", nav_group)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_in.setEnabled(False)
        zoom_layout.addWidget(self.btn_zoom_out)
        zoom_layout.addWidget(self.lbl_zoom_info)
        zoom_layout.addWidget(self.btn_zoom_in)
        nav_layout.addLayout(zoom_layout)

        # Fila de Ajuste
        fit_layout = QHBoxLayout()
        self.btn_fit_page = QPushButton("Ajustar a Ventana", nav_group)
        self.btn_fit_page.clicked.connect(self.fit_to_page_zoom_and_render)
        self.btn_fit_page.setEnabled(False)
        fit_layout.addWidget(self.btn_fit_page)
        nav_layout.addLayout(fit_layout)

        sidebar_layout.addWidget(nav_group)

        # --- Panel de Zonas de Firma ---
        zones_group = QGroupBox("Zonas de Firma Visible", sidebar)
        zones_layout = QVBoxLayout(zones_group)
        
        self.list_zones = QListWidget(zones_group)
        self.list_zones.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_zones.itemDoubleClicked.connect(self.go_to_zone_page)
        
        self.btn_delete_zone = QPushButton("Eliminar Zona Seleccionada", zones_group)
        self.btn_delete_zone.setObjectName("dangerButton")
        self.btn_delete_zone.clicked.connect(self.delete_selected_zone)
        self.btn_delete_zone.setEnabled(False)
        
        zones_layout.addWidget(self.list_zones)
        zones_layout.addWidget(self.btn_delete_zone)
        sidebar_layout.addWidget(zones_group)

        # --- Perfil activo en uso ---
        self.lbl_active_profile = QLabel("", sidebar)
        self.lbl_active_profile.setAlignment(Qt.AlignCenter)
        self.lbl_active_profile.setStyleSheet("color: #6b7280; font-size: 11px; font-style: italic;")
        sidebar_layout.addWidget(self.lbl_active_profile)
        self._update_active_profile_label()

        # --- Botón de Configuración de Firma (Modal) ---
        self.btn_config = QPushButton("⚙ Configuración de Firma", sidebar)
        self.btn_config.clicked.connect(self.open_config_dialog)
        sidebar_layout.addWidget(self.btn_config)

        # --- Controles Generales (Tema y Acción) ---
        bottom_actions = QHBoxLayout()
        self.btn_toggle_theme = QPushButton("Modo Oscuro", sidebar)
        self.btn_toggle_theme.clicked.connect(self.toggle_theme)
        
        self.btn_sign = QPushButton("Firmar PDF", sidebar)
        self.btn_sign.setObjectName("primaryButton")
        self.btn_sign.setStyleSheet("font-size: 14px; padding: 10px 20px;")
        self.btn_sign.clicked.connect(self.start_signing)
        self.btn_sign.setEnabled(False)
        
        bottom_actions.addWidget(self.btn_toggle_theme)
        bottom_actions.addWidget(self.btn_sign)
        sidebar_layout.addLayout(bottom_actions)

        # Agregar barra lateral al layout principal
        main_layout.addWidget(sidebar)

        # ---------------- VISOR DE PDF CENTRAL ----------------
        self.viewer = PdfViewer(self)
        self.viewer.file_dropped.connect(self.load_pdf)
        self.viewer.zone_added.connect(self.on_zone_drawn)
        
        self.viewer_signed = PdfViewer(self)
        self.viewer_signed.set_empty_text("Esperando documento firmado...")
        
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.viewer, "Documento Original")
        self.tabs.addTab(self.viewer_signed, "Documento Firmado")
        self.tabs.setTabEnabled(TAB_SIGNED, False)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        main_layout.addWidget(self.tabs, 1)  # Estirar para tomar todo el espacio restante

    # ---------------- MÉTODOS AUXILIARES DE ESTADO ACTIVO ----------------

    def get_active_viewer(self):
        if self.tabs and self.tabs.currentIndex() == TAB_SIGNED:
            return self.viewer_signed
        return self.viewer

    def get_active_handler(self):
        if self.tabs and self.tabs.currentIndex() == TAB_SIGNED:
            return self.pdf_handler_signed
        return self.pdf_handler

    def get_active_page(self):
        if self.tabs and self.tabs.currentIndex() == TAB_SIGNED:
            return self.current_page_signed
        return self.current_page

    def set_active_page(self, page):
        if self.tabs and self.tabs.currentIndex() == TAB_SIGNED:
            self.current_page_signed = page
        else:
            self.current_page = page

    def get_active_zoom(self):
        if self.tabs and self.tabs.currentIndex() == TAB_SIGNED:
            return self.zoom_factor_signed
        return self.zoom_factor

    def set_active_zoom(self, zoom):
        if self.tabs and self.tabs.currentIndex() == TAB_SIGNED:
            self.zoom_factor_signed = zoom
        else:
            self.zoom_factor = zoom

    def on_tab_changed(self, index):
        self.update_page_info()
        self.render_current_page()
        
        if index == TAB_SIGNED:
            self.list_zones.setEnabled(False)
            self.btn_delete_zone.setEnabled(False)
            self.btn_sign.setEnabled(False)
        else:
            self.list_zones.setEnabled(True)
            self.btn_delete_zone.setEnabled(len(self.signature_zones) > 0)
            self.btn_sign.setEnabled(len(self.signature_zones) > 0)

    # ---------------- HELPERS ----------------

    def _update_active_profile_label(self):
        active = get_active_profile(self.settings, self.profiles)
        self.lbl_active_profile.setText(f"Perfil activo: {active.get('name', '—')}")

    # ---------------- LÓGICA DE PDF Y RENDERIZADO ----------------

    def select_pdf_dialog(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo PDF", "", "Archivos PDF (*.pdf)"
        )
        if filepath:
            self.load_pdf(filepath)

    def load_pdf(self, filepath):
        if not os.path.exists(filepath):
            QMessageBox.critical(self, "Error", f"El archivo no existe: {filepath}")
            return
            
        try:
            if self.pdf_handler:
                self.pdf_handler.close()
                
            self.signature_zones.clear()
            self.next_zone_id = 1
            self.list_zones.clear()
            
            if self.pdf_handler_signed:
                self.pdf_handler_signed.close()
            self.pdf_handler_signed = None
            self.current_page_signed = 0
            self.zoom_factor_signed = 1.0
            
            self.pdf_handler = PdfHandler(filepath)
            self.current_page = 0
            self.zoom_factor = 1.0
            
            if self.tabs:
                if self.tabs.count() > 1:
                    self.tabs.removeTab(1)
                self.tabs.setCurrentIndex(TAB_ORIGINAL)
            
            # Actualizar interfaz
            filename = os.path.basename(filepath)
            self.lbl_pdf_name.setText(filename)
            self.lbl_pdf_name.setStyleSheet("font-style: normal; font-weight: 500;")
            
            self.btn_prev_page.setEnabled(self.pdf_handler.get_page_count() > 1)
            self.btn_next_page.setEnabled(self.pdf_handler.get_page_count() > 1)
            self.btn_zoom_in.setEnabled(True)
            self.btn_zoom_out.setEnabled(True)
            self.btn_fit_page.setEnabled(True)
            self.btn_sign.setEnabled(False)
            self.btn_delete_zone.setEnabled(False)
            self.needs_initial_fit = True
            QTimer.singleShot(150, self.initial_fit_and_render)
            
        except Exception as e:
            QMessageBox.critical(self, "Error al cargar PDF", f"No se pudo abrir el PDF:\n{str(e)}")

    def initial_fit_and_render(self):
        """Ajusta el zoom al cargar el archivo por primera vez tras el renderizado de la UI."""
        if self.needs_initial_fit:
            self.fit_to_page_zoom()
            self.render_current_page()
            self.needs_initial_fit = False

    def fit_to_page_zoom_and_render(self):
        """Calcula el zoom para encajar en el visor y re-renderiza la página."""
        self.fit_to_page_zoom()
        self.render_current_page()

    def render_current_page(self):
        handler = self.get_active_handler()
        if not handler:
            return
            
        viewer = self.get_active_viewer()
        page = self.get_active_page()
        zoom = self.get_active_zoom()

        # Calcular escala de render proporcional al zoom de pantalla
        # Factor 2.0 para mantener nitidez en pantallas HiDPI; mínimo 1.5 para legibilidad
        render_scale = max(1.5, min(zoom * 2.0, 4.0))
        qimg, _, _ = handler.render_page(page, render_scale)
        pdf_w, pdf_h = handler.get_page_size(page)
        
        # Cargar en el visor pasando el zoom real de pantalla
        viewer.set_page(qimg, pdf_w, pdf_h, zoom)
        self.update_page_info()
        self.refresh_viewer_zones()

    def fit_to_page_zoom(self):
        """Calcula el factor de zoom basándose en el lado más largo para encajar el documento completo."""
        handler = self.get_active_handler()
        if not handler:
            return
        page = self.get_active_page()
        pdf_w, pdf_h = handler.get_page_size(page)
        
        viewer = self.get_active_viewer()
        # Obtener dimensiones reales del widget visor
        viewport_w = viewer.width() - 36
        viewport_h = viewer.height() - 36
        
        if viewport_w > 0 and viewport_h > 0:
            # Ajustar basándose en el lado más largo de la página del PDF
            if pdf_h > pdf_w:
                zoom = viewport_h / pdf_h
            else:
                zoom = viewport_w / pdf_w
                
            # Limitar a un rango lógico (ej. 0.2 a 3.0)
            zoom = max(0.2, min(zoom, 3.0))
            self.set_active_zoom(zoom)

    def update_page_info(self):
        handler = self.get_active_handler()
        if not handler:
            self.lbl_page_info.setText("Página: - / -")
            self.lbl_zoom_info.setText("100%")
            self.btn_prev_page.setEnabled(False)
            self.btn_next_page.setEnabled(False)
            return
        total = handler.get_page_count()
        page = self.get_active_page()
        zoom = self.get_active_zoom()
        self.lbl_page_info.setText(f"Página: {page + 1} / {total}")
        self.lbl_zoom_info.setText(f"{int(zoom * 100)}%")
        
        self.btn_prev_page.setEnabled(page > 0)
        self.btn_next_page.setEnabled(page < total - 1)

    def prev_page(self):
        handler = self.get_active_handler()
        page = self.get_active_page()
        if handler and page > 0:
            self.set_active_page(page - 1)
            self.render_current_page()

    def next_page(self):
        handler = self.get_active_handler()
        page = self.get_active_page()
        if handler and page < handler.get_page_count() - 1:
            self.set_active_page(page + 1)
            self.render_current_page()

    def zoom_in(self):
        handler = self.get_active_handler()
        zoom = self.get_active_zoom()
        if handler and zoom < 4.0:
            self.set_active_zoom(zoom + 0.2)
            self.render_current_page()

    def zoom_out(self):
        handler = self.get_active_handler()
        zoom = self.get_active_zoom()
        if handler and zoom > 0.4:
            self.set_active_zoom(zoom - 0.2)
            self.render_current_page()

    # ---------------- ZONAS DE FIRMA ----------------

    def on_zone_drawn(self, x_pt, y_pt, w_pt, h_pt):
        if not self.pdf_handler:
            return
            
        pdf_w, pdf_h = self.pdf_handler.get_page_size(self.current_page)
        
        # Convertir a las coordenadas de AutoFirma (inferior izquierda) con el zoom total escalado
        coords = qt_to_pdf_coords(
            qt_x=x_pt * (self.zoom_factor * 3.0),
            qt_y=y_pt * (self.zoom_factor * 3.0),
            qt_w=w_pt * (self.zoom_factor * 3.0),
            qt_h=h_pt * (self.zoom_factor * 3.0),
            zoom=self.zoom_factor * 3.0,
            pdf_h=pdf_h,
            pdf_w=pdf_w
        )
        
        # Registrar la zona
        zone_id = self.next_zone_id
        self.next_zone_id += 1
        
        zone = {
            "id": zone_id,
            "page": self.current_page,
            "rect_pt": QRectF(x_pt, y_pt, w_pt, h_pt),
            "coords": coords
        }
        self.signature_zones.append(zone)
        
        # Añadir al QListWidget lateral
        item_text = f"Firma #{zone_id} [Pág {self.current_page + 1}] (X:{coords['lowerLeftX']}, Y:{coords['lowerLeftY']})"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, zone_id)
        self.list_zones.addItem(item)
        
        self.btn_sign.setEnabled(True)
        self.btn_delete_zone.setEnabled(True)
        
        # Refrescar visor
        self.refresh_viewer_zones()

    def refresh_viewer_zones(self):
        if self.tabs and self.tabs.currentIndex() == TAB_SIGNED:
            self.viewer_signed.update_zones([])
        else:
            # Filtrar zonas que corresponden a la página actual
            page_zones = [z for z in self.signature_zones if z["page"] == self.current_page]
            self.viewer.update_zones(page_zones)

    def delete_selected_zone(self):
        selected_items = self.list_zones.selectedItems()
        if not selected_items:
            return
            
        item = selected_items[0]
        zone_id = item.data(Qt.UserRole)
        
        # Eliminar de la lista de estado
        self.signature_zones = [z for z in self.signature_zones if z["id"] != zone_id]
        
        # Eliminar del QListWidget
        self.list_zones.takeItem(self.list_zones.row(item))
        
        if not self.signature_zones:
            self.btn_sign.setEnabled(False)
            self.btn_delete_zone.setEnabled(False)
            
        self.refresh_viewer_zones()

    def go_to_zone_page(self, item):
        zone_id = item.data(Qt.UserRole)
        # Buscar la zona
        for zone in self.signature_zones:
            if zone["id"] == zone_id:
                if self.tabs.currentIndex() != TAB_ORIGINAL:
                    self.tabs.setCurrentIndex(TAB_ORIGINAL)
                if self.current_page != zone["page"]:
                    self.current_page = zone["page"]
                    self.render_current_page()
                break

    # ---------------- OPERACIÓN DE FIRMA ----------------

    def start_signing(self):
        if not self.pdf_handler or not self.signature_zones:
            return
            
        autofirma_path = self.settings.get("autofirma_path", "").strip()
        if not autofirma_path or not os.path.exists(autofirma_path):
            QMessageBox.critical(
                self, "Error de Configuración", 
                "Por favor, selecciona una ruta válida para el ejecutable de AutoFirma."
            )
            return

        # Preguntar dónde guardar el PDF firmado
        dir_name = os.path.dirname(self.pdf_handler.filepath)
        base_name = os.path.basename(self.pdf_handler.filepath)
        name, ext = os.path.splitext(base_name)
        default_output = os.path.join(dir_name, f"{name}_firmado{ext}")
        
        output_pdf, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF firmado", default_output, "Archivos PDF (*.pdf)"
        )
        if not output_pdf:
            return
            
        self.last_output_pdf = output_pdf
            
        # Obtener el perfil activo
        active_profile = get_active_profile(self.settings, self.profiles)

        cert_filter = active_profile.get("cert_filter", "").strip()
        sig_text = active_profile.get("signature_text", "").strip()
        rubric_path = active_profile.get("rubric_image_path", "").strip()
        font_name = active_profile.get("signature_font", "Helvetica")
        font_size = int(active_profile.get("signature_font_size", 0))
        rubric_layout = active_profile.get("rubric_layout", "side_by_side")
        store = active_profile.get("store", "auto")
        store_pkcs12_path = active_profile.get("store_pkcs12_path", "").strip()

        # Si el almacén es PKCS12, solicitar la contraseña interactivamente
        store_pkcs12_password = bytearray()
        if store == "pkcs12":
            if not store_pkcs12_path:
                QMessageBox.critical(
                    self, "Error de Configuración",
                    "El almacén seleccionado es PKCS12 pero no se ha especificado "
                    "la ruta al fichero .p12 / .pfx.\n\n"
                    "Por favor, configurálo en Configuración de Firma."
                )
                return
            password, ok = QInputDialog.getText(
                self,
                "Contraseña del certificado",
                f"Introduzca la contraseña del fichero PKCS12:\n{store_pkcs12_path}",
                QLineEdit.Password
            )
            if not ok:
                return  # El usuario canceló
            store_pkcs12_password = bytearray(password.encode("utf-8"))

        # Mostrar indicador de carga/progreso modal
        self.progress_dialog = QProgressDialog("Invocando AutoFirma y firmando documento...", "Cancelar", 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)
        self.progress_dialog.setCancelButton(None)  # Evitar que se cancele a mitad de la firma
        self.progress_dialog.show()

        # Desactivar botones principales
        self.btn_sign.setEnabled(False)

        # Crear y arrancar hilo secundario para evitar congelar la interfaz
        self.sign_thread = SignThread(
            input_pdf=self.pdf_handler.filepath,
            output_pdf=output_pdf,
            zones=self.signature_zones,
            cert_filter=cert_filter,
            sig_text=sig_text,
            rubric_path=rubric_path,
            autofirma_path=autofirma_path,
            font_name=font_name,
            font_size=font_size,
            rubric_layout=rubric_layout,
            store=store,
            store_pkcs12_path=store_pkcs12_path,
            store_pkcs12_password=store_pkcs12_password
        )
        self.sign_thread.finished_signal.connect(self.on_signing_finished)
        self.sign_thread.start()

    @Slot(bool, str, bool)
    def on_signing_finished(self, success, message, text_overflow):
        # Cerrar barra de progreso
        if self.progress_dialog:
            self.progress_dialog.close()

        # SECURITY: Wipe PKCS12 password from memory and delete thread reference
        if self.sign_thread:
            if getattr(self.sign_thread, "store_pkcs12_password", None) and isinstance(self.sign_thread.store_pkcs12_password, bytearray):
                self.sign_thread.store_pkcs12_password[:] = b'\x00' * len(self.sign_thread.store_pkcs12_password)
            self.sign_thread.deleteLater()
            self.sign_thread = None
            
        self.btn_sign.setEnabled(True)
        
        if success:
            if text_overflow:
                QMessageBox.warning(
                    self, "Texto de firma desbordado",
                    "⚠ El texto de la firma no cabía completamente en el área seleccionada.\n\n"
                    "Se ha reducido el tamaño de fuente automáticamente al mínimo posible. "
                    "Considera ampliar el área de firma, acortar el texto o reducir el tamaño de fuente "
                    "en la Configuración de Firma."
                )
            QMessageBox.information(
                self, "Operación Exitosa",
                "El documento ha sido firmado de manera exitosa y guardado en la ubicación elegida."
            )
            
            # Cargar el PDF firmado en la segunda pestaña
            if self.last_output_pdf and os.path.exists(self.last_output_pdf):
                try:
                    if self.pdf_handler_signed:
                        self.pdf_handler_signed.close()
                    
                    self.pdf_handler_signed = PdfHandler(self.last_output_pdf)
                    self.current_page_signed = 0
                    self.zoom_factor_signed = 1.0
                    
                    if self.tabs.count() < 2:
                        self.tabs.addTab(self.viewer_signed, "Documento Firmado")
                    
                    self.tabs.setCurrentIndex(TAB_SIGNED)
                    self.render_current_page()
                except Exception as e:
                    QMessageBox.warning(
                        self, "Error al cargar PDF firmado",
                        f"No se pudo cargar el PDF firmado en la pestaña:\n{str(e)}"
                    )
        else:
            QMessageBox.critical(
                self, "Fallo al Firmar",
                f"Ocurrió un error durante el proceso de firma:\n{message}"
            )

    # ---------------- AJUSTES Y CONFIGURACIÓN ----------------

    def open_config_dialog(self):
        dialog = ConfigDialog(self, self.settings, self.profiles)
        if dialog.exec() == QDialog.Accepted:
            new_profiles, active_idx, autofirma_path = dialog.get_result()
            self.profiles = new_profiles
            active_name = self.profiles[active_idx]["name"] if self.profiles else ""
            self.settings["active_profile"] = active_name
            self.settings["autofirma_path"] = autofirma_path
            save_profiles(self.profiles)
            save_settings(self.settings)
            self._update_active_profile_label()

    def toggle_theme(self):
        # Intercambiar tema
        current_theme = self.settings.get("theme", "light")
        new_theme = "light" if current_theme == "dark" else "dark"
        self.settings["theme"] = new_theme
        save_settings(self.settings)
        self.apply_theme(new_theme)

    def apply_theme(self, theme):
        if theme == "dark":
            self.setStyleSheet(DARK_STYLE)
            self.btn_toggle_theme.setText("Modo Claro")
            self.viewer.set_theme("dark")
            self.viewer_signed.set_theme("dark")
        else:
            self.setStyleSheet(LIGHT_STYLE)
            self.btn_toggle_theme.setText("Modo Oscuro")
            self.viewer.set_theme("light")
            self.viewer_signed.set_theme("light")
        self.style().unpolish(self)
        self.style().polish(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Si la ventana se redimensiona / muestra por primera vez y necesita ajuste inicial
        if self.needs_initial_fit and self.pdf_handler:
            self.fit_to_page_zoom()
            self.render_current_page()
            self.needs_initial_fit = False

    def closeEvent(self, event):
        # Cerrar el handler al salir
        if self.pdf_handler:
            self.pdf_handler.close()
        if hasattr(self, "pdf_handler_signed") and self.pdf_handler_signed:
            self.pdf_handler_signed.close()
        event.accept()

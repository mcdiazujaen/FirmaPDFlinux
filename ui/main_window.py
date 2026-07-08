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

class SignThread(QThread):
    # Señal emitida al finalizar la operación: (success, message, text_overflow)
    finished_signal = Signal(bool, str, bool)

    def __init__(self, input_pdf, output_pdf, zones, cert_filter, sig_text, rubric_path,
                 autofirma_path, font_name, font_size, rubric_layout,
                 store="auto", store_pkcs12_path="", store_pkcs12_password=""):
        super().__init__()
        self.input_pdf = input_pdf
        self.output_pdf = output_pdf
        self.zones = zones
        self.cert_filter = cert_filter
        self.sig_text = sig_text
        self.rubric_path = rubric_path
        self.autofirma_path = autofirma_path
        self.font_name = font_name
        self.font_size = font_size
        self.rubric_layout = rubric_layout
        self.store = store
        self.store_pkcs12_path = store_pkcs12_path
        self.store_pkcs12_password = store_pkcs12_password

    def run(self):
        # Ejecutar firma múltiple secuencial
        success, message, text_overflow = sign_pdf_multiple_zones(
            input_pdf_path=self.input_pdf,
            output_pdf_path=self.output_pdf,
            zones=self.zones,
            cert_filter=self.cert_filter,
            signature_text=self.sig_text,
            rubric_path=self.rubric_path,
            autofirma_path=self.autofirma_path,
            font_name=self.font_name,
            font_size=self.font_size,
            rubric_layout=self.rubric_layout,
            store=self.store,
            store_pkcs12_path=self.store_pkcs12_path,
            store_pkcs12_password=self.store_pkcs12_password
        )
        self.finished_signal.emit(success, message, text_overflow)


# ---------------------------------------------------------------------------
# Diálogo de Configuración de Firma con Gestión de Perfiles
# ---------------------------------------------------------------------------

class ConfigDialog(QDialog):
    def __init__(self, parent=None, settings=None, profiles=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Firma")
        self.resize(680, 560)
        self.settings = settings or {}
        self.profiles = [dict(p) for p in (profiles or [])]  # copia profunda
        if not self.profiles:
            self.profiles = [DEFAULT_PROFILE.copy()]

        self._current_profile_index = self._find_active_index()
        self._building = True  # suprimir cambios durante construcción

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # ---- Sección superior: gestión de perfiles ----
        profile_group = QGroupBox("Perfiles de Firma")
        pg_layout = QVBoxLayout(profile_group)

        # Nombre del perfil + controles
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Nombre:"))
        self.input_profile_name = QLineEdit()
        self.input_profile_name.setPlaceholderText("Nombre del perfil")
        name_row.addWidget(self.input_profile_name, 1)

        self.btn_new_profile = QPushButton("Nuevo")
        self.btn_new_profile.clicked.connect(self.new_profile)
        self.btn_duplicate_profile = QPushButton("Duplicar")
        self.btn_duplicate_profile.clicked.connect(self.duplicate_profile)
        self.btn_delete_profile = QPushButton("Eliminar")
        self.btn_delete_profile.setObjectName("dangerButton")
        self.btn_delete_profile.clicked.connect(self.delete_profile)
        name_row.addWidget(self.btn_new_profile)
        name_row.addWidget(self.btn_duplicate_profile)
        name_row.addWidget(self.btn_delete_profile)
        pg_layout.addLayout(name_row)

        # Lista de perfiles
        self.list_profiles = QListWidget()
        self.list_profiles.setFixedHeight(100)
        self.list_profiles.currentRowChanged.connect(self._on_profile_selected)
        pg_layout.addWidget(self.list_profiles)

        layout.addWidget(profile_group)

        # ---- Sección inferior: parámetros del perfil activo ----
        params_group = QGroupBox("Parámetros del Perfil Activo")
        form = QFormLayout(params_group)
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(8)

        # Filtro de Certificado
        self.input_cert_filter = QLineEdit()
        self.input_cert_filter.setPlaceholderText("Ej. DNI / Nombre (Firma silenciosa)")
        form.addRow("Filtro Certificado:", self.input_cert_filter)

        # Texto de la firma
        self.input_sig_text = QLineEdit()
        form.addRow("Texto Firma:", self.input_sig_text)

        # Fuente del texto
        font_row = QHBoxLayout()
        self.combo_font = QComboBox()
        for font_name in SUPPORTED_FONTS.keys():
            self.combo_font.addItem(font_name)
        font_row.addWidget(self.combo_font, 1)

        font_row.addWidget(QLabel("Tamaño:"))
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(0, 36)
        self.spin_font_size.setSpecialValueText("Auto")  # 0 = automático
        self.spin_font_size.setSuffix(" pt")
        self.spin_font_size.setFixedWidth(80)
        font_row.addWidget(self.spin_font_size)
        form.addRow("Fuente:", font_row)

        # Imagen de Rúbrica
        rubric_row = QHBoxLayout()
        self.input_rubric_path = QLineEdit()
        self.input_rubric_path.setReadOnly(True)
        self.btn_browse_rubric = QPushButton("Examinar…")
        self.btn_browse_rubric.clicked.connect(self.select_rubric_image)
        self.btn_clear_rubric = QPushButton()
        # Icono de papelera: se busca en el tema del sistema, con fallback al estilo Qt
        trash_icon = QIcon.fromTheme("user-trash", QIcon.fromTheme("edit-delete"))
        if trash_icon.isNull():
            # Último recurso: icono estándar de la aplicación
            trash_icon = self.style().standardIcon(QStyle.SP_TrashIcon)
        self.btn_clear_rubric.setIcon(trash_icon)
        self.btn_clear_rubric.setFixedWidth(32)
        self.btn_clear_rubric.setFixedHeight(32)
        self.btn_clear_rubric.setToolTip("Borrar ruta de imagen")
        self.btn_clear_rubric.setStyleSheet(
            "QPushButton { color: #dc2626; border: 1px solid #dc2626; border-radius: 5px; }"
            "QPushButton:hover { background-color: #fee2e2; color: #b91c1c; }"
            "QPushButton:pressed { background-color: #fecaca; }"
        )
        self.btn_clear_rubric.clicked.connect(self.clear_rubric)
        rubric_row.addWidget(self.input_rubric_path, 1)
        rubric_row.addWidget(self.btn_browse_rubric)
        rubric_row.addWidget(self.btn_clear_rubric)
        form.addRow("Rúbrica (Imagen):", rubric_row)

        # Disposición de la rúbrica
        self.combo_rubric_layout = QComboBox()
        self.combo_rubric_layout.addItem(
            "Imagen de fondo, texto superpuesto centrado arriba",
            userData="background"
        )
        self.combo_rubric_layout.addItem(
            "Imagen a la izquierda (1/3), texto a la derecha (2/3)",
            userData="side_by_side"
        )
        layout_help = QLabel(
            "ℹ La disposición solo aplica cuando hay imagen de rúbrica."
        )
        layout_help.setStyleSheet("color: #6b7280; font-size: 11px;")
        layout_help.setWordWrap(True)
        rubric_layout_col = QVBoxLayout()
        rubric_layout_col.addWidget(self.combo_rubric_layout)
        rubric_layout_col.addWidget(layout_help)
        form.addRow("Disposición Rúbrica:", rubric_layout_col)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        form.addRow(sep)

        # --- Almacén de claves ---
        self.combo_store = QComboBox()
        self.combo_store.addItem("Auto (por defecto)", userData="auto")
        self.combo_store.addItem("Windows", userData="windows")
        self.combo_store.addItem("Mac (Llavero del sistema)", userData="mac")
        self.combo_store.addItem("Mozilla / Firefox", userData="mozilla")
        self.combo_store.addItem("PKCS12 (.p12 / .pfx)", userData="pkcs12")
        form.addRow("Almacén de claves:", self.combo_store)

        # Fila de ruta PKCS12 (visible solo cuando store == pkcs12)
        pkcs12_row = QHBoxLayout()
        self.input_pkcs12_path = QLineEdit()
        self.input_pkcs12_path.setReadOnly(True)
        self.input_pkcs12_path.setPlaceholderText("Ruta al fichero .p12 / .pfx")
        self.btn_browse_pkcs12 = QPushButton("Examinar…")
        self.btn_browse_pkcs12.clicked.connect(self.select_pkcs12_file)
        pkcs12_row.addWidget(self.input_pkcs12_path, 1)
        pkcs12_row.addWidget(self.btn_browse_pkcs12)
        self.lbl_pkcs12 = QLabel("Fichero PKCS12:")
        self.lbl_pkcs12.setVisible(False)
        self.input_pkcs12_path.setVisible(False)
        self.btn_browse_pkcs12.setVisible(False)
        self._pkcs12_row_widget = QWidget()
        self._pkcs12_row_widget.setLayout(pkcs12_row)
        self._pkcs12_row_widget.setVisible(False)
        form.addRow(self.lbl_pkcs12, self._pkcs12_row_widget)

        # Conectar cambio de store para mostrar/ocultar campo PKCS12
        self.combo_store.currentIndexChanged.connect(self._on_store_changed)

        # Ruta AutoFirma
        autofirma_row = QHBoxLayout()
        self.input_autofirma_path = QLineEdit()
        self.input_autofirma_path.setText(self.settings.get("autofirma_path", ""))
        self.btn_browse_autofirma = QPushButton("Examinar…")
        self.btn_browse_autofirma.clicked.connect(self.select_autofirma_bin)
        autofirma_row.addWidget(self.input_autofirma_path, 1)
        autofirma_row.addWidget(self.btn_browse_autofirma)
        form.addRow("Ruta AutoFirma:", autofirma_row)

        layout.addWidget(params_group)

        # ---- Botones de diálogo ----
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self
        )
        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.Save).setText("Guardar")
        self.button_box.button(QDialogButtonBox.Cancel).setText("Cancelar")
        layout.addWidget(self.button_box)

        # Poblar la lista de perfiles
        self._populate_profile_list()
        self._building = False
        # Seleccionar el perfil activo sin disparar efectos secundarios
        self.list_profiles.blockSignals(True)
        self.list_profiles.setCurrentRow(self._current_profile_index)
        self.list_profiles.blockSignals(False)
        self._load_profile_fields(self._current_profile_index)

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _find_active_index(self):
        active_name = self.settings.get("active_profile", "")
        for i, p in enumerate(self.profiles):
            if p["name"] == active_name:
                return i
        return 0

    def _populate_profile_list(self):
        self.list_profiles.blockSignals(True)
        self.list_profiles.clear()
        for p in self.profiles:
            self.list_profiles.addItem(p["name"])
        self.list_profiles.blockSignals(False)

    def _load_profile_fields(self, index):
        """Rellena los campos del formulario con los datos del perfil en `index`."""
        if not (0 <= index < len(self.profiles)):
            return
        p = self.profiles[index]
        self.input_profile_name.setText(p.get("name", ""))
        self.input_cert_filter.setText(p.get("cert_filter", ""))
        self.input_sig_text.setText(p.get("signature_text", ""))
        self.input_rubric_path.setText(p.get("rubric_image_path", ""))

        # Fuente
        font_display = p.get("signature_font", "Helvetica")
        idx = self.combo_font.findText(font_display)
        self.combo_font.setCurrentIndex(idx if idx >= 0 else 0)

        # Tamaño
        self.spin_font_size.setValue(int(p.get("signature_font_size", 0)))

        # Disposición de la rúbrica
        layout_val = p.get("rubric_layout", "side_by_side")
        for i in range(self.combo_rubric_layout.count()):
            if self.combo_rubric_layout.itemData(i) == layout_val:
                self.combo_rubric_layout.setCurrentIndex(i)
                break

        # Almacén de claves
        store_val = p.get("store", "auto")
        for i in range(self.combo_store.count()):
            if self.combo_store.itemData(i) == store_val:
                self.combo_store.setCurrentIndex(i)
                break
        self.input_pkcs12_path.setText(p.get("store_pkcs12_path", ""))
        self._on_store_changed()  # actualizar visibilidad del campo PKCS12

    def _save_current_profile_fields(self):
        """Guarda los valores del formulario en el perfil actualmente seleccionado."""
        idx = self._current_profile_index
        if not (0 <= idx < len(self.profiles)):
            return
        # Actualizar el nombre del perfil
        new_name = self.input_profile_name.text().strip() or f"Perfil {idx + 1}"
        self.profiles[idx]["name"] = new_name
        self.profiles[idx]["cert_filter"] = self.input_cert_filter.text().strip()
        self.profiles[idx]["signature_text"] = self.input_sig_text.text().strip()
        self.profiles[idx]["rubric_image_path"] = self.input_rubric_path.text().strip()
        self.profiles[idx]["signature_font"] = self.combo_font.currentText()
        self.profiles[idx]["signature_font_size"] = self.spin_font_size.value()
        self.profiles[idx]["rubric_layout"] = self.combo_rubric_layout.currentData()
        self.profiles[idx]["store"] = self.combo_store.currentData()
        self.profiles[idx]["store_pkcs12_path"] = self.input_pkcs12_path.text().strip()
        # Refrescar el item en la lista si el nombre cambió
        self.list_profiles.item(idx).setText(new_name)

    # ------------------------------------------------------------------
    # Slots de perfiles
    # ------------------------------------------------------------------

    def _on_profile_selected(self, row):
        if self._building or row < 0:
            return
        # Guardar cambios del perfil actual antes de cambiar
        self._save_current_profile_fields()
        self._current_profile_index = row
        self._load_profile_fields(row)

    def new_profile(self):
        self._save_current_profile_fields()
        new_p = DEFAULT_PROFILE.copy()
        new_p["name"] = f"Nuevo Perfil {len(self.profiles) + 1}"
        self.profiles.append(new_p)
        self.list_profiles.addItem(new_p["name"])
        new_idx = len(self.profiles) - 1
        self._current_profile_index = new_idx
        self.list_profiles.setCurrentRow(new_idx)
        self._load_profile_fields(new_idx)

    def duplicate_profile(self):
        self._save_current_profile_fields()
        idx = self._current_profile_index
        if not (0 <= idx < len(self.profiles)):
            return
        import copy
        dup = copy.deepcopy(self.profiles[idx])
        dup["name"] = dup["name"] + " (copia)"
        self.profiles.append(dup)
        self.list_profiles.addItem(dup["name"])
        new_idx = len(self.profiles) - 1
        self._current_profile_index = new_idx
        self.list_profiles.setCurrentRow(new_idx)
        self._load_profile_fields(new_idx)

    def delete_profile(self):
        if len(self.profiles) <= 1:
            QMessageBox.warning(self, "No se puede eliminar",
                                "Debe existir al menos un perfil de firma.")
            return
        idx = self._current_profile_index
        self.profiles.pop(idx)
        self.list_profiles.takeItem(idx)
        new_idx = max(0, idx - 1)
        self._current_profile_index = new_idx
        self.list_profiles.setCurrentRow(new_idx)
        self._load_profile_fields(new_idx)

    # ------------------------------------------------------------------
    # Seleccion de archivos
    # ------------------------------------------------------------------

    def _on_store_changed(self):
        """Muestra u oculta el campo de ruta PKCS12 según la selección del almacén."""
        is_pkcs12 = (self.combo_store.currentData() == "pkcs12")
        self.lbl_pkcs12.setVisible(is_pkcs12)
        self._pkcs12_row_widget.setVisible(is_pkcs12)

    def select_pkcs12_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar fichero PKCS12", "",
            "Certificados PKCS12 (*.p12 *.pfx);;Todos los archivos (*)"
        )
        if filepath:
            self.input_pkcs12_path.setText(filepath)

    def select_rubric_image(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar imagen de rúbrica", "", "Imágenes (*.png *.jpg *.jpeg)"
        )
        if filepath:
            self.input_rubric_path.setText(filepath)

    def clear_rubric(self):
        self.input_rubric_path.clear()

    def select_autofirma_bin(self):
        title = "Seleccionar ejecutable de AutoFirma"
        filt = "Todos los archivos (*)"
        if sys.platform.startswith("win"):
            filt = "Ejecutables (*.exe)"
        elif sys.platform.startswith("darwin"):
            filt = "AutoFirma.jar (*.jar)"
        filepath, _ = QFileDialog.getOpenFileName(self, title, "", filt)
        if filepath:
            self.input_autofirma_path.setText(filepath)

    # ------------------------------------------------------------------
    # Guardar
    # ------------------------------------------------------------------

    def _on_save(self):
        self._save_current_profile_fields()
        self.accept()

    def get_result(self):
        """Devuelve (profiles, active_index, autofirma_path)."""
        return self.profiles, self._current_profile_index, self.input_autofirma_path.text().strip()


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
        
        self.viewer_signed = PdfViewer()
        self.viewer_signed.canvas.setMouseTracking(False)
        self.viewer_signed.setAcceptDrops(False)
        self.viewer_signed.hide()
        
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.viewer, "Documento Original")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        main_layout.addWidget(self.tabs, 1)  # Estirar para tomar todo el espacio restante

    # ---------------- MÉTODOS AUXILIARES DE ESTADO ACTIVO ----------------

    def get_active_viewer(self):
        if hasattr(self, "tabs") and self.tabs.currentIndex() == 1:
            return self.viewer_signed
        return self.viewer

    def get_active_pdf_handler(self):
        if hasattr(self, "tabs") and self.tabs.currentIndex() == 1:
            return self.pdf_handler_signed
        return self.pdf_handler

    def get_active_page(self):
        if hasattr(self, "tabs") and self.tabs.currentIndex() == 1:
            return self.current_page_signed
        return self.current_page

    def set_active_page(self, page):
        if hasattr(self, "tabs") and self.tabs.currentIndex() == 1:
            self.current_page_signed = page
        else:
            self.current_page = page

    def get_active_zoom(self):
        if hasattr(self, "tabs") and self.tabs.currentIndex() == 1:
            return self.zoom_factor_signed
        return self.zoom_factor

    def set_active_zoom(self, zoom):
        if hasattr(self, "tabs") and self.tabs.currentIndex() == 1:
            self.zoom_factor_signed = zoom
        else:
            self.zoom_factor = zoom

    def on_tab_changed(self, index):
        self.update_page_info()
        self.render_current_page()
        
        if index == 1:
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
            # Cerrar el anterior handler
            if self.pdf_handler:
                self.pdf_handler.close()
                
            self.pdf_handler = PdfHandler(filepath)
            self.current_page = 0
            self.zoom_factor = 1.0
            self.signature_zones = []
            self.next_zone_id = 1
            self.list_zones.clear()
            
            # Limpiar estado del PDF firmado
            if hasattr(self, "pdf_handler_signed") and self.pdf_handler_signed:
                self.pdf_handler_signed.close()
            self.pdf_handler_signed = None
            self.current_page_signed = 0
            self.zoom_factor_signed = 1.0
            
            if hasattr(self, "tabs"):
                if self.tabs.count() > 1:
                    self.tabs.removeTab(1)
                self.tabs.setCurrentIndex(0)
            
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
            # Ajustar el zoom automáticamente para adaptar el documento al visor la primera vez
            # Se difiere 150ms para asegurar que el viewport de la UI tenga dimensiones calculadas
            QTimer.singleShot(150, self.initial_fit_and_render)
            
        except Exception as e:
            QMessageBox.critical(self, "Error al cargar PDF", f"No se pudo abrir el PDF:\n{str(e)}")

    def initial_fit_and_render(self):
        """Ajusta el zoom al cargar el archivo por primera vez tras el renderizado de la UI."""
        if hasattr(self, "needs_initial_fit") and self.needs_initial_fit:
            self.fit_to_page_zoom()
            self.render_current_page()
            self.needs_initial_fit = False

    def fit_to_page_zoom_and_render(self):
        """Calcula el zoom para encajar en el visor y re-renderiza la página."""
        self.fit_to_page_zoom()
        self.render_current_page()

    def render_current_page(self):
        handler = self.get_active_pdf_handler()
        if not handler:
            return
            
        viewer = self.get_active_viewer()
        page = self.get_active_page()
        zoom = self.get_active_zoom()

        # Renderizar la página actual en una QImage a alta resolución constante (3.0x = 216 DPI)
        qimg, _, _ = handler.render_page(page, 3.0)
        pdf_w, pdf_h = handler.get_page_size(page)
        
        # Cargar en el visor pasando el zoom real de pantalla
        viewer.set_page(qimg, pdf_w, pdf_h, zoom)
        self.update_page_info()
        self.refresh_viewer_zones()

    def fit_to_page_zoom(self):
        """Calcula el factor de zoom basándose en el lado más largo para encajar el documento completo."""
        handler = self.get_active_pdf_handler()
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
        handler = self.get_active_pdf_handler()
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
        handler = self.get_active_pdf_handler()
        page = self.get_active_page()
        if handler and page > 0:
            self.set_active_page(page - 1)
            self.render_current_page()

    def next_page(self):
        handler = self.get_active_pdf_handler()
        page = self.get_active_page()
        if handler and page < handler.get_page_count() - 1:
            self.set_active_page(page + 1)
            self.render_current_page()

    def zoom_in(self):
        handler = self.get_active_pdf_handler()
        zoom = self.get_active_zoom()
        if handler and zoom < 4.0:
            self.set_active_zoom(zoom + 0.2)
            self.render_current_page()

    def zoom_out(self):
        handler = self.get_active_pdf_handler()
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
        if hasattr(self, "tabs") and self.tabs.currentIndex() == 1:
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
                if self.tabs.currentIndex() != 0:
                    self.tabs.setCurrentIndex(0)
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
        store_pkcs12_password = ""
        if store == "pkcs12":
            if not store_pkcs12_path:
                QMessageBox.critical(
                    self, "Error de Configuración",
                    "El almacén seleccionado es PKCS12 pero no se ha especificado "
                    "la ruta al fichero .p12 / .pfx.\n\n"
                    "Por favor, configúralo en Configuración de Firma."
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
            store_pkcs12_password = password

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
        if hasattr(self, "progress_dialog"):
            self.progress_dialog.close()
            
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
            if hasattr(self, "last_output_pdf") and self.last_output_pdf and os.path.exists(self.last_output_pdf):
                try:
                    if hasattr(self, "pdf_handler_signed") and self.pdf_handler_signed:
                        self.pdf_handler_signed.close()
                    
                    self.pdf_handler_signed = PdfHandler(self.last_output_pdf)
                    self.current_page_signed = 0
                    self.zoom_factor_signed = 1.0
                    
                    if self.tabs.count() < 2:
                        self.tabs.addTab(self.viewer_signed, "Documento Firmado")
                    
                    self.tabs.setCurrentIndex(1)
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
        if hasattr(self, "needs_initial_fit") and self.needs_initial_fit and self.pdf_handler:
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

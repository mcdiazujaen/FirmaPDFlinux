import sys
import copy
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QListWidget, QGroupBox, QFormLayout, QFileDialog, QMessageBox,
    QDialogButtonBox, QComboBox, QSpinBox, QWidget, QFrame, QStyle
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from core.settings import DEFAULT_PROFILE
from core.pdf_handler import SUPPORTED_FONTS

class ConfigDialog(QDialog):
    def __init__(self, parent=None, settings=None, profiles=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Firma")
        self.resize(680, 560)
        self.settings = settings or {}
        self.profiles = copy.deepcopy(profiles or [DEFAULT_PROFILE])

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

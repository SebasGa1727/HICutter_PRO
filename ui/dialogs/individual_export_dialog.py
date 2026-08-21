import os
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from PyQt6 import QtWidgets, QtCore, QtGui
from ui.components.neon_widgets import CustomPushButton, CustomComboBox, CustomSpinBox
from utils.individual_config import config_manager 

class CustomLabel(QtWidgets.QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setProperty("estilo", "title")
        # Alineación a la izquierda para un look más limpio en un cuadro de diálogo pequeño
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

class IndividualExportDialog(QtWidgets.QDialog):
    """
    Diálogo modal de 'Exportar Como...' para el procesamiento de una sola imagen.
    """
    def __init__(self, original_filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exportar Imagen")
        self.setFixedSize(500, 450)
        self.setModal(True)
        
        # Extraemos el nombre sin extensión para usarlo por defecto
        self.base_name, _ = os.path.splitext(original_filename)
        
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        # Layout Principal
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setSpacing(5)
        self.main_layout.setContentsMargins(15, 15, 15, 15)

        # --- Ruta de guardado ---
        dir_group = QtWidgets.QGroupBox()
        dir_layout = QtWidgets.QVBoxLayout(dir_group)
        dir_layout.setSpacing(15)

        dir_btn_layout = QtWidgets.QHBoxLayout()
        dir_btn_layout.setSpacing(0)

        lbl_dest = CustomLabel("Guardar en...")
        
        self.txt_output_dir = QtWidgets.QLineEdit()
        self.txt_output_dir.setPlaceholderText("Seleccione la ruta de guardado")
        self.txt_output_dir.setProperty("converter_setup_view", "out_dir_style")
        self.txt_output_dir.setReadOnly(True)
        
        self.btn_browse = CustomPushButton(". . .")
        self.btn_browse.setToolTip("Explorar")
        self.btn_browse.setFixedSize(50, 30)
        self.btn_browse.setProperty("converter_setup_view", "out_dir_style")
        self.btn_browse.clicked.connect(self._browse_output)

        dir_btn_layout.addWidget(self.txt_output_dir, stretch=1)
        dir_btn_layout.addWidget(self.btn_browse)

        dir_layout.addWidget(lbl_dest)
        dir_layout.addLayout(dir_btn_layout)

        # --- NOMBRE DEL ARCHIVO ---
        name_group = QtWidgets.QGroupBox()
        name_layout = QtWidgets.QVBoxLayout(name_group)
        name_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        name_layout.setSpacing(15)

        lbl_name = CustomLabel("Nombre del archivo")

        self.txt_filename = QtWidgets.QLineEdit()
        self.txt_filename.setText(self.base_name)
        self.txt_filename.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.txt_filename.setMaximumWidth(300)

        name_layout.addWidget(lbl_name)
        name_layout.addWidget(self.txt_filename)

        # --- CONFIGURACIÓN DE EXPORTACIÓN ---
        config_group = QtWidgets.QGroupBox()
        config_layout = QtWidgets.QVBoxLayout(config_group)
        config_layout.setSpacing(10)

        lbl_config = CustomLabel("Configuración de exportación")

        container_form_layout = QtWidgets.QHBoxLayout()
        
        # Formulario Izquierdo
        left_form_container = QtWidgets.QWidget()
        left_config_form_layout = QtWidgets.QFormLayout(left_form_container)
        left_config_form_layout.setSpacing(10)
        
        self.quality_spinbox = CustomSpinBox()
        self.quality_spinbox.setRange(10, 100)
        self.quality_spinbox.setSuffix("%")
        
        self.dpi_spinbox = CustomSpinBox()
        self.dpi_spinbox.setRange(72, 1200)
        
        left_config_form_layout.addRow("Calidad de compresión:", self.quality_spinbox)
        left_config_form_layout.addRow("DPI:", self.dpi_spinbox)

        # Formulario Derecho
        right_form_container = QtWidgets.QWidget()
        right_config_form_layout = QtWidgets.QFormLayout(right_form_container)
        right_config_form_layout.setSpacing(10)

        self.export_combobox = CustomComboBox()
        self.export_combobox.addItems(["jpg", "png"])

        size_side_layout = QtWidgets.QHBoxLayout()
        size_side_layout.setSpacing(5)
        
        self.size_spinbox = CustomSpinBox()
        self.size_spinbox.setRange(1, 10000)
        self.size_spinbox.setSuffix("px")
        
        self.side_size_combobox = CustomComboBox()
        self.side_size_combobox.addItems(["Lado largo", "Lado corto", "Cuadrado"])
        
        size_side_layout.addWidget(self.size_spinbox)
        size_side_layout.addWidget(self.side_size_combobox)

        right_config_form_layout.addRow("Formato:", self.export_combobox)
        right_config_form_layout.addRow("Dimensiones:", size_side_layout)

        container_form_layout.addWidget(left_form_container)
        container_form_layout.addWidget(right_form_container)

        config_layout.addWidget(lbl_config)
        config_layout.addSpacing(5)
        config_layout.addLayout(container_form_layout)

        # --- BOTONES ---
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setContentsMargins(0, 15, 0, 0)
        
        self.btn_cancel = CustomPushButton("Cancelar")
        self.btn_cancel.setProperty("estilo", "cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_accept = CustomPushButton("Exportar")
        self.btn_accept.setProperty("estilo", "primario")
        self.btn_accept.clicked.connect(self._validate_and_accept)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_accept)

        # --- ENSAMBLAJE FINAL ---
        self.main_layout.addWidget(dir_group)
        self.main_layout.addWidget(name_group)
        self.main_layout.addWidget(config_group)
        self.main_layout.addLayout(btn_layout)

    def _browse_output(self):
        last_dir = config_manager.get("paths", "last_output_dir") or ""
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Seleccionar ruta de guardado", last_dir)
        if dir_path:
            self.txt_output_dir.setText(dir_path)

    def _load_settings(self):
        """Precarga la información previamente guardada."""
        # Ruta guardada en sesión anterior
        last_dir = config_manager.get("paths", "last_output_dir")
        if last_dir:
            self.txt_output_dir.setText(last_dir)

        # Configuraciones de exportación
        self.quality_spinbox.setValue(config_manager.get("export_config", "quality") or 90)
        self.dpi_spinbox.setValue(config_manager.get("export_config", "dpi") or 72)
        self.export_combobox.setCurrentIndex(config_manager.get("export_config", "format") or 0)
        self.size_spinbox.setValue(config_manager.get("export_config", "size") or 2000)
        self.side_size_combobox.setCurrentIndex(config_manager.get("export_config", "side") or 0)

    def _save_and_continue(self):
        """Guarda la información en el JSON y cierra la ventana."""
        config_manager.set("paths", "last_output_dir", self.txt_output_dir.text().strip())
        
        config_manager.set("export_config", "quality", self.quality_spinbox.value())
        config_manager.set("export_config", "dpi", self.dpi_spinbox.value())
        config_manager.set("export_config", "format", self.export_combobox.currentIndex())
        config_manager.set("export_config", "size", self.size_spinbox.value())
        config_manager.set("export_config", "side", self.side_size_combobox.currentIndex())

        self.accept()

    def _validate_and_accept(self):
        """Valida campos críticos antes de procesar."""
        if not self.txt_output_dir.text().strip():
            QtWidgets.QMessageBox.warning(self, "Aviso", "Debe seleccionar una ruta de guardado.")
            return
            
        if not self.txt_filename.text().strip():
            QtWidgets.QMessageBox.warning(self, "Aviso", "El nombre del archivo no puede estar vacío.")
            return

        self._save_and_continue()

    def get_export_data(self) -> dict:
        """
        Retorna la ruta y nombre definidos por el usuario. 
        Los datos técnicos (dpi, calidad) ya se guardaron en el JSON, 
        por lo que el 'output_fmt.py' los leerá directo desde allí.
        """
        return {
            "output_dir": self.txt_output_dir.text().strip(),
            "filename": self.txt_filename.text().strip(),
        }

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """Evita que presionar Enter accione el botón accidentalmente, a menos que esté en foco."""
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            if self.focusWidget() == self.btn_accept:
                self.btn_accept.click()
            elif self.focusWidget() == self.btn_cancel:
                self.btn_cancel.click()
            else:
                event.ignore()
        else:
            super().keyPressEvent(event)

if __name__ == "__main__":
    def load_global_stylesheet(app: QtWidgets.QApplication):
        try:
            with open("resources/theme.qss", "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        except FileNotFoundError:
            pass

    # TRUCO PARA MOCK: Agregar la raíz del proyecto al PATH para ejecuciones aisladas
    from ui.components.neon_widgets import NeonProxyStyle
    from utils.asset_manager import assets
    
    app = QtWidgets.QApplication(sys.argv)
    base_style = QtWidgets.QStyleFactory.create("Fusion")
    app.setStyle(NeonProxyStyle(base_style))
    load_global_stylesheet(app)
    assets.init_graphic_resources()

    mock_name = "Archivo_1"

    window = IndividualExportDialog(mock_name)
    window.resize(1200, 750)
    window.setWindowTitle("batch-setup-dialog")
    window.show()
    sys.exit(app.exec()) 
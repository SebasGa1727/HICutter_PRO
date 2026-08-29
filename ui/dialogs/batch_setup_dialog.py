# TRUCO PARA MOCK: Agregar la raíz del proyecto al PATH para ejecuciones aisladas
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from enum import IntEnum
from PyQt6 import QtWidgets, QtCore, QtGui
from ui.components.neon_widgets import CustomPushButton, CustomComboBox, CustomCheckBox, CustomSpinBox
from utils.batch_config import config_manager

class CustomLabel(QtWidgets.QLabel):
    def __init__(self, text, parent= None):
        super().__init__(text, parent)
        self.setProperty("estilo", "title")
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

class ViewIndex(IntEnum):
    """Controla los valores del combobox para la ruta de salida"""
    OVERWRITE = 0
    SUFIX = 1
    OUTDIR = 2

class BatchSetupDialog(QtWidgets.QDialog):
    """
    Diálogo de configuración para el procesamiento por lotes.
    Captura: Carpeta origen, inclusión de subcarpetas y política de exportación.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Procesamiento por Lotes")
        self.setFixedSize(500, 630)
        self.setModal(True)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        middle_layout = QtWidgets.QVBoxLayout(self)
        middle_layout.setSpacing(0)
        middle_layout.setContentsMargins(15, 15, 15, 15)

        # --- ORIGEN ---
        origen_group = QtWidgets.QGroupBox(self)
        origen_layout = QtWidgets.QVBoxLayout(origen_group)
        origen_layout.setSpacing(20)
        origen_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Titulo de la seccion
        input_title = CustomLabel("Origen de las Imágenes")

        # Selector de carpeta
        dir_layout = QtWidgets.QHBoxLayout()
        dir_layout.setSpacing(0)

        self.txt_input_dir = QtWidgets.QLineEdit()
        self.txt_input_dir.setPlaceholderText("Seleccione la carpeta a procesar...")
        self.txt_input_dir.setProperty("converter_setup_view", "out_dir_style")
        self.txt_input_dir.setReadOnly(True)
        
        self.btn_browse_input = CustomPushButton(". . .")
        self.btn_browse_input.setToolTip("Explorar")
        self.btn_browse_input.setFixedSize(50, 30)
        self.btn_browse_input.setProperty("converter_setup_view", "out_dir_style")
        self.btn_browse_input.clicked.connect(self._browse_input)

        dir_layout.addWidget(self.txt_input_dir, stretch=1)
        dir_layout.addWidget(self.btn_browse_input)
        
        # Checkbox retroactivo
        self.check_subfolders = CustomCheckBox("INCLUIR IMAGENES DE TODAS LAS SUB CARPETAS")
        self.check_subfolders.setChecked(False)

        # Armado layout origen
        origen_layout.addWidget(input_title)
        origen_layout.addStretch(1)
        origen_layout.addLayout(dir_layout)
        origen_layout.addWidget(self.check_subfolders, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        origen_layout.addStretch(1)

        # --- DESTINO ---
        destino_group = QtWidgets.QGroupBox(self)
        destino_layout = QtWidgets.QVBoxLayout(destino_group)
        destino_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        destino_lbl = CustomLabel("Destino y Guardado")

        # Modo de guardado
        self.combo_mode = CustomComboBox(self)
        self.combo_mode.addItems([
            "Reemplazar imágenes originales (Sobreescribir)",
            "Guardar en la misma ruta con sufijo",
            "Guardar en una nueva carpeta específica"
        ])
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)

        # Selector de carpeta de salida (Oculto por defecto)
        self.out_dir_widget = QtWidgets.QWidget(self)
        out_dir_layout = QtWidgets.QVBoxLayout(self.out_dir_widget)
        lbl_btn_out_dir_layout = QtWidgets.QHBoxLayout()
        lbl_btn_out_dir_layout.setContentsMargins(0, 0, 0, 0)
        lbl_btn_out_dir_layout.setSpacing(0)
        
        self.txt_output_dir = QtWidgets.QLineEdit()
        self.txt_output_dir.setPlaceholderText("Seleccione la carpeta de destino...")
        self.txt_output_dir.setProperty("converter_setup_view", "out_dir_style")
        self.txt_output_dir.setReadOnly(True)
        
        self.btn_browse_output = CustomPushButton(". . .")
        self.btn_browse_output.setToolTip("Explorar")
        self.btn_browse_output.setFixedSize(50, 30)
        self.btn_browse_output.setProperty("converter_setup_view", "out_dir_style")
        self.btn_browse_output.clicked.connect(self._browse_output)
        
        lbl_btn_out_dir_layout.addWidget(self.txt_output_dir, stretch=1)
        lbl_btn_out_dir_layout.addWidget(self.btn_browse_output)

        self.keep_folder_structure = CustomCheckBox("MANTENER ESTRUCTURA DE CARPETAS")
        self.keep_folder_structure.setChecked(False)

        out_dir_layout.addLayout(lbl_btn_out_dir_layout)
        out_dir_layout.addSpacing(15)
        out_dir_layout.addWidget(self.keep_folder_structure, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.out_dir_widget.setVisible(False)

        # Contenido de sufijo oculto por defecto
        self.sufix_name = QtWidgets.QLineEdit(parent=self)
        self.sufix_name.setPlaceholderText("Coloca el sufijo de tu archivo")
        self.sufix_name.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.sufix_name.setMaximumWidth(300)
        self.sufix_name.setVisible(False)

        # Armado layout_destino
        destino_layout.addWidget(destino_lbl)
        destino_layout.addStretch(1)
        destino_layout.addWidget(self.combo_mode, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        destino_layout.addSpacing(15)
        destino_layout.addWidget(self.out_dir_widget)
        destino_layout.addWidget(self.sufix_name)
        destino_layout.addStretch(1)

        # --- Config exportacion ---
        config_group = QtWidgets.QGroupBox(self)
        config_layout = QtWidgets.QVBoxLayout(config_group)
        config_layout.setSpacing(10)

        # Titulo del layout de exportacion
        config_export_lbl = CustomLabel("Configuracion de exportacion")

        # Componenetes del formulario
        container_form_layout = QtWidgets.QHBoxLayout()
        left_form_container = QtWidgets.QWidget(self)
        left_config_form_layout = QtWidgets.QFormLayout(left_form_container)
        left_config_form_layout.setSpacing(10)
        left_config_form_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        right_form_container = QtWidgets.QWidget(self)
        right_config_form_layout = QtWidgets.QFormLayout(right_form_container)
        right_config_form_layout.setSpacing(10)
        right_config_form_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.export_combobox = CustomComboBox()
        self.export_combobox.addItems(["jpg", "png"])

        self.quality_spinbox = CustomSpinBox()
        self.quality_spinbox.setRange(10, 100)
        self.quality_spinbox.setSuffix("%")

        self.dpi_spinbox = CustomSpinBox()
        self.dpi_spinbox.setRange(72, 1200)

        # Layout de "dimensiones"
        size_side_layout = QtWidgets.QHBoxLayout()
        size_side_layout.setSpacing(5)

        self.size_spinbox = CustomSpinBox()
        self.size_spinbox.setRange(1, 10000)
        self.size_spinbox.setSuffix("px")

        self.side_size_combobox = CustomComboBox()
        self.side_size_combobox.addItems(["Lado largo", "Lado corto", "Cuadrado"])

        #Armado de layout "Dimensiones"
        size_side_layout.addWidget(self.size_spinbox)
        size_side_layout.addWidget(self.side_size_combobox)

        # Armado del formulario izquierdo
        left_config_form_layout.addRow("Formato: ", self.export_combobox)
        left_config_form_layout.addRow("Calidad: ", self.quality_spinbox)

        # Armado del formulario derecho
        right_config_form_layout.addRow("DPI: ", self.dpi_spinbox)
        right_config_form_layout.addRow("Dimensiones:", size_side_layout)

        container_form_layout.addSpacing(10)
        container_form_layout.addWidget(left_form_container)
        container_form_layout.addWidget(right_form_container)
        container_form_layout.addStretch(1)

        # Armado del layout
        config_layout.addWidget(config_export_lbl)
        config_layout.addStretch(1)
        config_layout.addLayout(container_form_layout)
        config_layout.addStretch(1)

        # --- BOTONES DE ACCIÓN ---
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setContentsMargins(0, 15, 0, 0)
        
        self.btn_cancel = CustomPushButton("Cancelar")
        self.btn_cancel.setProperty("estilo", "cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_accept = CustomPushButton("Iniciar Lote")
        self.btn_accept.setProperty("estilo", "primario")
        self.btn_accept.clicked.connect(self._validate_and_accept)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_accept)

        # Armado global
        middle_layout.addWidget(origen_group, stretch=1)
        middle_layout.addWidget(destino_group, stretch=2)
        middle_layout.addWidget(config_group, stretch= 2)
        middle_layout.addLayout(btn_layout)

    def _browse_input(self):
        # Obtenemos la ruta que ya está en el textbox (cargada desde el JSON)
        current_path = self.txt_input_dir.text().strip()
        
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, 
            "Seleccionar carpeta origen",
            current_path # <-le indicamos a Windows dónde abrir
        )
        if dir_path:
            self.txt_input_dir.setText(dir_path)

    def _browse_output(self):
        # Obtenemos la ruta que ya está en el textbox (cargada desde el JSON)
        current_path = self.txt_output_dir.text().strip()
        
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, 
            "Seleccionar carpeta destino",
            current_path 
        )
        if dir_path:
            self.txt_output_dir.setText(dir_path)

    def _on_mode_changed(self, index: int):
        """Muestra el selector de ruta solo si se elige 'nueva carpeta específica' (índice 2)"""
        self.out_dir_widget.setVisible(index == ViewIndex.OUTDIR)
        self.sufix_name.setVisible(index == ViewIndex.SUFIX)

    def _validate_and_accept(self):
        """Valida que los campos requeridos estén llenos antes de aceptar."""
        if not self.txt_input_dir.text().strip():
            QtWidgets.QMessageBox.warning(self, "Aviso", "Debe seleccionar una carpeta de origen.")
            return
            
        if self.combo_mode.currentIndex() == ViewIndex.OUTDIR and not self.txt_output_dir.text().strip():
            QtWidgets.QMessageBox.warning(self, "Aviso", "Debe seleccionar una carpeta de destino.")
            return
            
        if self.combo_mode.currentIndex() == ViewIndex.SUFIX and not self.sufix_name.text().strip():
            QtWidgets.QMessageBox.warning(self, "Aviso", "Debe colocar un sufijo válido.")
            return

        self._save_and_continue()

    def _load_settings(self):
        """Precarga la información guardada previamente en el JSON."""
        # --- Origen ---
        self.check_subfolders.setChecked(config_manager.get("export_config", "check_subfolders"))
        last_input = config_manager.get("save_config", "last_input_route")
        if last_input:
            self.txt_input_dir.setText(last_input)

        # --- Destino y Guardado ---
        save_mode = config_manager.get("save_config", "save_mode")
        self.combo_mode.setCurrentIndex(save_mode)
        self._on_mode_changed(save_mode)  # mostrar/ocultar paneles según el modo
        
        # Cargamos rutas y textos
        self.txt_output_dir.setText(config_manager.get("save_config", "route") or "")
        self.sufix_name.setText(config_manager.get("save_config", "sufix") or "_copia")
        self.keep_folder_structure.setChecked(config_manager.get("save_config", "keep_structure")or False)

        # --- Configuración de Exportación ---
        self.export_combobox.setCurrentIndex(config_manager.get("export_config", "format"))
        self.quality_spinbox.setValue(config_manager.get("export_config", "quality"))
        self.dpi_spinbox.setValue(config_manager.get("export_config", "dpi"))
        self.size_spinbox.setValue(config_manager.get("export_config", "size"))
        self.side_size_combobox.setCurrentIndex(config_manager.get("export_config", "size_side"))

    def _save_and_continue(self):
        """Guarda la información en el JSON y cierra la ventana exitosamente."""
        # --- Origen ---
        config_manager.set("export_config", "check_subfolders", self.check_subfolders.isChecked())
        config_manager.set("save_config", "last_input_route", self.txt_input_dir.text().strip())

        # --- Destino y Guardado ---
        config_manager.set("save_config", "save_mode", self.combo_mode.currentIndex())
        config_manager.set("save_config", "route", self.txt_output_dir.text().strip())
        config_manager.set("save_config", "sufix", self.sufix_name.text().strip())
        config_manager.set("save_config", "keep_structure", self.keep_folder_structure.isChecked())

        # --- Configuración de Exportación ---
        config_manager.set("export_config", "format", self.export_combobox.currentIndex())
        config_manager.set("export_config", "quality", self.quality_spinbox.value())
        config_manager.set("export_config", "dpi", self.dpi_spinbox.value())
        config_manager.set("export_config", "size", self.size_spinbox.value())
        config_manager.set("export_config", "size_side", self.side_size_combobox.currentIndex())

        # Finalizamos el diálogo con éxito
        self.accept()

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """Sobrescribe el evento de teclado para evitar que Enter/Return cierre el diálogo"""
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            # Si el click esta sobre el widget de crear o cancelar, se efectua el "enter"
            if self.focusWidget() == self.btn_accept:
                self.btn_accept.click()

            elif self.focusWidget() == self.btn_cancel:
                self.btn_cancel.click()
            else:
                # si el enter no es en ninguno de esos botones, se ignora
                event.ignore()
        else:
            # Permitimos el comportamiento predeterminado para cualquier otra tecla 
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

    window = BatchSetupDialog()
    window.resize(1200, 750)
    window.setWindowTitle("batch-setup-dialog")
    window.show()
    sys.exit(app.exec()) 
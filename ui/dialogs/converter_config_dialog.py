from PyQt6 import QtWidgets, QtCore

class ConfigDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, current_config: dict = None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Exportación")
        self.resize(500, 400)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowContextHelpButtonHint, False)
        
        self.current_config = current_config or {}
        
        self._setup_ui()
        self._load_current_settings()

    def _setup_ui(self):
        # Usamos QFormLayout que es perfecto para alinear Labels y Controles (Inputs)
        form_layout = QtWidgets.QFormLayout()
        form_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        form_layout.setSpacing(15)
        
        # 1. Formato de Salida
        self.combo_formato = QtWidgets.QComboBox()
        self.combo_formato.addItems(["JPG (Recomendado)", "PNG (Sin pérdida)"])
        form_layout.addRow("Formato de Exportación:", self.combo_formato)
        
        # 2. Calidad de Compresión
        self.spin_calidad = QtWidgets.QSpinBox()
        self.spin_calidad.setRange(10, 100)
        self.spin_calidad.setValue(90)
        self.spin_calidad.setSuffix(" %")
        form_layout.addRow("Calidad de Compresión:", self.spin_calidad)
        
        # 3. Espacio de Color
        self.combo_color = QtWidgets.QComboBox()
        self.combo_color.addItems(["sRGB (Web/Universal)", "Adobe RGB", "ProPhoto RGB", "Escala de Grises"])
        form_layout.addRow("Espacio de Color:", self.combo_color)
        
        # 4. Conservar Metadatos EXIF
        self.check_exif = QtWidgets.QCheckBox("Conservar metadatos originales de la cámara")
        self.check_exif.setChecked(True)
        form_layout.addRow("", self.check_exif)

        # Botones inferiores
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_cancel = QtWidgets.QPushButton("Cancelar")
        self.btn_accept = QtWidgets.QPushButton("Guardar Configuración")
        
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_accept.clicked.connect(self.accept)
        
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_accept)

        # Layout Principal
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Título
        lbl_titulo = QtWidgets.QLabel("Ajustes Técnicos de Conversión")
        lbl_titulo.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        
        main_layout.addWidget(lbl_titulo)
        main_layout.addLayout(form_layout)
        main_layout.addStretch(1)
        main_layout.addLayout(btn_layout)

    def _load_current_settings(self):
        """Si la ventana se abre y ya había configuración previa, cargamos los datos."""
        if "calidad" in self.current_config:
            self.spin_calidad.setValue(self.current_config["calidad"])
            #TODO: Conectar y guardar las configuraciones en mi formato json
        # ... hacer lo mismo con los demás combos

    def get_export_settings(self) -> dict:
        """Empaqueta y devuelve la configuración final para ser usada por el motor."""
        #TODO: Configurar el guardado en el json para que el motor pueda realizar los cambios con la configuracion adecuada
        return {
            "formato": self.combo_formato.currentText(),
            "calidad": self.spin_calidad.value(),
            "espacio_color": self.combo_color.currentText(),
            "conservar_exif": self.check_exif.isChecked()
        }
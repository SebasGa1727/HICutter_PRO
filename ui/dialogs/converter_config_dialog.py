from PyQt6 import QtWidgets, QtCore, QtGui

class ConfigDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, current_config: dict = None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de conversión")
        self.resize(360, 300)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowContextHelpButtonHint, False)
        
        self.current_config = current_config or {}
        
        self._setup_ui()
        self._load_current_settings()

    def _setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(25, 20, 25, 20)

        # Panel de conversion
        converter_layout = QtWidgets.QVBoxLayout()

        converter_lbl_title = QtWidgets.QLabel("CONFIGURACIÓN DE CONVERSIÓN")
        converter_lbl_title.setProperty("estilo", "title")
        converter_lbl_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        
        self.converter_format = QtWidgets.QComboBox()
        self.converter_format.addItems(["JPG (Recomendado)", "PNG (Sin pérdida)"])
        
        self.converter_quality = QtWidgets.QSpinBox()
        self.converter_quality.setMaximumWidth(43)
        self.converter_quality.setRange(10, 100)
        self.converter_quality.setSuffix(" %")
        self.converter_quality.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.converter_quality.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        self.converter_color_space = QtWidgets.QComboBox()
        self.converter_color_space.addItems(["sRGB (Web/Universal)", "Adobe RGB", "ProPhoto RGB", "Escala de Grises"])

        for combobox in [self.converter_format, self.converter_color_space]:
            combobox.setEditable(True)
            line_edit = combobox.lineEdit()
            line_edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            line_edit.setReadOnly(True)

        # Creacion del formulario
        form_layout = QtWidgets.QFormLayout()
        form_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        form_layout.setSpacing(15)
        form_layout.addRow("Formato de Exportación:", self.converter_format)
        form_layout.addRow("Calidad de Compresión:", self.converter_quality)
        form_layout.addRow("Espacio de Color:", self.converter_color_space)

        # Armado del layout de conversion
        converter_layout.addWidget(converter_lbl_title)
        converter_layout.addSpacing(20)
        converter_layout.addLayout(form_layout)

        # Botones inferiores
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_cancel = QtWidgets.QPushButton("CANCELAR")
        self.btn_cancel.setProperty("estilo", "cancelar")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_accept = QtWidgets.QPushButton("GUARDAR")
        self.btn_accept.setProperty("estilo", "primario")
        self.btn_accept.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_accept)
        
        # Layout Principal
        main_layout.addSpacing(20)
        main_layout.addLayout(converter_layout)
        main_layout.addStretch(1)
        main_layout.addLayout(btn_layout)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """Sobrescribe el evento de teclado para evitar que Enter/Return cierre el diálogo"""
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            # Si el click esta sobre el widget de crear o cancelar, se efectua el "enter"
            focused_widget = self.focusWidget()
            
            if focused_widget == self.btn_accept:
                self.btn_accept.click()

            elif focused_widget == self.btn_cancel:
                self.btn_cancel.click()

            # Habilitamos el enter para los combobox, haciendo que despliegue su menu
            elif isinstance(focused_widget, QtWidgets.QComboBox):
                focused_widget.showPopup()

            else:
                # si el enter no es en ninguno de esos botones, se ignora
                event.ignore()
        else:
            # Permitimos el comportamiento predeterminado para cualquier otra tecla 
            super().keyPressEvent(event)

    def _load_current_settings(self):
        """Si la ventana se abre y ya había configuración previa, cargamos los datos."""
        #TODO

    def get_export_settings(self) -> dict:
        """Empaqueta y devuelve la configuración final para ser usada por el motor."""
        #TODO
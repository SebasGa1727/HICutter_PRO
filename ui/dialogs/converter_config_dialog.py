from PyQt6 import QtWidgets, QtCore, QtGui
from ui.components.neon_widgets import CustomComboBox, CustomSpinBox, CustomPushButton
from utils.converter_config import config_manager

class ConfigDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de conversión")
        self.resize(360, 250)
        
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
        
        self.converter_format = CustomComboBox()
        self.converter_format.addItems(["JPG", "PNG"])
        
        self.converter_quality = CustomSpinBox()
        self.converter_quality.setMaximumWidth(50)
        self.converter_quality.setRange(10, 100)
        self.converter_quality.setSuffix(" %")

        # Creacion del formulario
        form_layout = QtWidgets.QFormLayout()
        form_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        form_layout.setSpacing(15)
        form_layout.addRow("Formato de Exportación:", self.converter_format)
        form_layout.addRow("Calidad de Compresión:", self.converter_quality)

        # Armado del layout de conversion
        converter_layout.addWidget(converter_lbl_title)
        converter_layout.addSpacing(20)
        converter_layout.addLayout(form_layout)

        # Botones inferiores
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_cancel = CustomPushButton("CANCELAR")
        self.btn_cancel.setProperty("estilo", "cancelar")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_accept = CustomPushButton("GUARDAR")
        self.btn_accept.setProperty("estilo", "primario")
        self.btn_accept.clicked.connect(self._accept_and_save)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_accept)
        
        # Layout Principal
        main_layout.addSpacing(20)
        main_layout.addLayout(converter_layout)
        main_layout.addStretch(1)
        main_layout.addLayout(btn_layout)

    def _load_current_settings(self):
        """Si la ventana se abre y ya había configuración previa, cargamos los datos."""
        self.converter_format.setCurrentIndex(config_manager.get("convert_image", "format") or 0)
        self.converter_quality.setValue(config_manager.get("convert_image", "quality") or 90)

    def _save_export_settings(self):
        """Almacena la informacion en el JSON de conversion"""
        config_manager.set("convert_image", "format", self.converter_format.currentIndex())
        config_manager.set("convert_image", "quality", self.converter_quality.value())

    def _accept_and_save(self):
        """Guarda los datos y cierra la ventana"""
        self._save_export_settings()
        self.accept()

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
            elif isinstance(focused_widget, CustomComboBox):
                focused_widget.showPopup()

            else:
                # si el enter no es en ninguno de esos botones, se ignora
                event.ignore()
        else:
            # Permitimos el comportamiento predeterminado para cualquier otra tecla 
            super().keyPressEvent(event)
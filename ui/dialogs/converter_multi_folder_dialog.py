from PyQt6 import QtWidgets, QtCore, QtGui
# TRUCO PARA MOCK: Agregar la raíz del proyecto al PATH para ejecuciones aisladas
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from utils.logger import setup_logger
from utils.asset_manager import assets
from utils.converter_config import config_manager
from ui.components.neon_widgets import NeonProxyStyle, CustomPushButton, CustomSpinBox

logger = setup_logger(__name__)

class MultiFolderDialog(QtWidgets.QDialog):
    INVALID_CHARS = {"\\", "/", ":", "*", "?", '"', "<", ">", "|", "'"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generador de Carpetas")
        self.setFixedSize(600, 360)
        self.setModal(True)             # Bloquea la interfaz principal
        self._setup_ui()
        self._update_preview()          # Generar preview inicial
        self._preload_user_info()       # Carga la informacion del usuario

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)

        # Título y descripción
        lbl_title = QtWidgets.QLabel("Genera la estructura de tus carpetas")
        lbl_title.setProperty("estilo", "title")
        lbl_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl_title.setWordWrap(True)

        middle_layout = QtWidgets.QHBoxLayout()
        middle_layout.setSpacing(15)

        # Formulario de configuración 
        left_layout = QtWidgets.QVBoxLayout()

        # Titulo izquierdo
        left_title = QtWidgets.QLabel("SECUENCIA")
        left_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        left_title.setProperty("estilo","splitter_title")

        left_form_layout = QtWidgets.QGridLayout()
        left_form_layout.setVerticalSpacing(11)

        # Cantidad de carpetas
        self.spin_count = CustomSpinBox()
        self.spin_count.setRange(2, 10000)
        self.spin_count.setValue(2)

        # Número Inicial
        self.spin_start = CustomSpinBox()
        self.spin_start.setRange(0, 99999)
        self.spin_start.setValue(1)

        # Padding (Ceros a la izquierda)
        self.spin_padding = CustomSpinBox()
        self.spin_padding.setRange(1, 6)
        self.spin_padding.setValue(2)
        self.spin_padding.setToolTip("Ej: 2 dígitos = 01, 3 dígitos = 001")

        for s in [self.spin_count, self.spin_start, self.spin_padding]:
            s.setFixedSize(46,19)
            s.valueChanged.connect(self._update_preview)
            
        # Creacion del formulario
        left_form_layout.addWidget(self._create_label("Cantidad de careptas a crear:"), 0, 0)
        left_form_layout.addWidget(self.spin_count, 0, 1, QtCore.Qt.AlignmentFlag.AlignCenter)
        left_form_layout.addWidget(self._create_label("Empezar numeración desde:"), 1, 0)
        left_form_layout.addWidget(self.spin_start, 1, 1, QtCore.Qt.AlignmentFlag.AlignCenter)
        left_form_layout.addWidget(self._create_label("Cantidad de dígitos (Ceros):"), 2, 0)
        left_form_layout.addWidget(self.spin_padding, 2, 1, QtCore.Qt.AlignmentFlag.AlignCenter)

        # Agregamos todo al left_layout
        left_layout.addWidget(left_title)
        left_layout.addSpacing(5)
        left_layout.addLayout(left_form_layout)
        left_layout.addStretch(1)

        # Creamos el right_layout
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.setSpacing(10)

        # Titulo derecho
        right_title = QtWidgets.QLabel("NOMENCLATURA")
        right_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        right_title.setProperty("estilo","splitter_title")

        # Line Edit del right_layout
        self.first_line_edit = self._create_line_edit(1, "Ej: Carpeta_")
        self.second_line_edit = self._create_line_edit(2)
        self.third_line_edit = self._create_line_edit(3)

        # Lista de los objetos
        self.line_edit_list = [self.first_line_edit, self.second_line_edit, self.third_line_edit]

        # Armado del Right layout
        right_layout.addWidget(right_title) 
        right_layout.addSpacing(10)
        for line_edit in self.line_edit_list:
            right_layout.addWidget(line_edit)
        right_layout.addStretch(1)

        # Linea vertical divisoria
        vertical_line = QtWidgets.QFrame()
        vertical_line.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        vertical_line.setProperty("linea", "gris")

        # Agregamos al middle layout
        middle_layout.addLayout(left_layout, stretch=1)
        middle_layout.addWidget(vertical_line)
        middle_layout.addLayout(right_layout, stretch=1)

        # Panel de Previsualización 
        preview_group = QtWidgets.QGroupBox("Previsualización", self)
        preview_group.setStyleSheet("QGroupBox::title { margin-top: -7px; color: #BBB;} QGroupBox { border: 1px solid rgba(12, 140, 233, 0.5);}")
        preview_layout = QtWidgets.QVBoxLayout(preview_group)
        self.lbl_preview = QtWidgets.QLabel()
        self.lbl_preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.lbl_preview)

        # Botones de Acción
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_cancel = CustomPushButton("Cancelar")
        self.btn_cancel.setProperty("estilo", "cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_create = CustomPushButton("Generar Carpetas")
        self.btn_create.setProperty("estilo", "primario")
        self.btn_create.clicked.connect(self._accept)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_create)

        # Armado del layout
        layout.addWidget(lbl_title)
        layout.addSpacing(20)
        layout.addLayout(middle_layout)
        layout.addSpacing(20)
        layout.addWidget(preview_group)
        layout.addSpacing(20)
        layout.addLayout(btn_layout)

    def _create_label(self, name: str) -> QtWidgets.QLabel:
            label = QtWidgets.QLabel(name)
            label.setProperty("estilo", "label_form")
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
            return label
    
    def _create_line_edit(self, order: int, placeholder: str = "") -> QtWidgets.QLineEdit:
        line_edit = QtWidgets.QLineEdit()
        line_edit.setText(config_manager.get("multi_folder_dialog",str(order)) or "")
        line_edit.setPlaceholderText(placeholder)
        line_edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        line_edit.textChanged.connect(self._update_preview)
        return line_edit

    def _update_preview(self):
        """Calcula matemáticamente el primer y último elemento para mostrar un ejemplo claro"""
        # Verificacion de seguridad para caracteres prohibidos
        unavailable_character = self._check_unavailable_character()

        if unavailable_character:
            self.lbl_preview.setText(f'El carácter "{unavailable_character}" no es válido')
        else:
            # Colocamos la previsualizacion del texto y regresamos los colores a la normalidad
            self._visual_valid()

            start = self.spin_start.value()
            pad = self.spin_padding.value()
            end = start + self.spin_count.value() - 1
            base_text = ''.join(line_edit.text() for line_edit in self.line_edit_list)

            first_item = f"{base_text}{str(start).zfill(pad)}"
            last_item = f"{base_text}{str(end).zfill(pad)}"

            self.lbl_preview.setText(f"{first_item}  . . .  {last_item}")

    def _check_unavailable_character(self):
        """Verificacion de caracteres invalidos y llamamos a la funcion para cambiar el color de los botones"""
        for line_edit in self.line_edit_list:
            text_chars = set(line_edit.text())
            invalid_intersection = text_chars.intersection(self.INVALID_CHARS)
            
            if invalid_intersection:
                char = invalid_intersection.pop()
                self._visual_invalid(line_edit)
                return char
        return None
            
    def _visual_invalid(self, invalid_line: QtWidgets.QLineEdit):
        """Modificacion visual de los botones cuando es un caracter invalido"""
        invalid_line.setProperty("estilo", "invalido")
        invalid_line.style().unpolish(invalid_line)
        invalid_line.style().polish(invalid_line)

        self.btn_create.setEnabled(False)

    def _visual_valid(self):
        """Modificacion visual para cambiar al estado normal"""
        for line_edit in self.line_edit_list:
            if line_edit.property("estilo") == "invalido" or line_edit.text() == "":
                line_edit.setProperty("estilo", None)
                line_edit.style().unpolish(line_edit)
                line_edit.style().polish(line_edit)

            if line_edit.text() != "":
                line_edit.setProperty("estilo", "valido")
                line_edit.style().unpolish(line_edit)
                line_edit.style().polish(line_edit)

        self.btn_create.setEnabled(True)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """Sobrescribe el evento de teclado para evitar que Enter/Return cierre el diálogo"""
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            # Si el click esta sobre el widget de crear o cancelar, se efectua el "enter"
            if self.focusWidget() == self.btn_create:
                self.btn_create.click()

            elif self.focusWidget() == self.btn_cancel:
                self.btn_cancel.click()
            else:
                # si el enter no es en ninguno de esos botones, se ignora
                event.ignore()
        else:
            # Permitimos el comportamiento predeterminado para cualquier otra tecla 
            super().keyPressEvent(event)

    def get_config(self) -> dict:
        """Retorna la configuración matemática"""
        try:
            base_text = ''.join(line_edit.text() for line_edit in self.line_edit_list)
            return {
                "count": self.spin_count.value(),
                "base_name": base_text,
                "start": self.spin_start.value(),
                "padding": self.spin_padding.value()
            }
        except Exception:
            logger.error("Error al intentar obtener los datos del multi_folder_Dialog", exc_info=True)

    def _preload_user_info(self):
        """Carga la informacion del JSON utilizada previamente"""
        self.spin_count.setValue(config_manager.get("multi_folder_dialog", "count") or 2)
        self.spin_start.setValue(config_manager.get("multi_folder_dialog", "start") or 1)
        self.spin_padding.setValue(config_manager.get("multi_folder_dialog", "padding") or 2)
        number = 1
        for line_edit in self.line_edit_list :
            line_edit.setText(config_manager.get("multi_folder_dialog", str(number)))
            number += 1

    def _accept(self):
        """Guarda la configuración antes de cerrar el diálogo."""
        number = 1
        for line_edit in self.line_edit_list:
            config_manager.set("multi_folder_dialog", str(number), str(line_edit.text()))
            number += 1
            
        config_manager.set("multi_folder_dialog", "count", self.spin_count.value())
        config_manager.set("multi_folder_dialog", "start", self.spin_start.value())
        config_manager.set("multi_folder_dialog", "padding", self.spin_padding.value())
        super().accept()
    

# ==========================================
# ENTORNO AISLADO (MOCK ENVIRONMENT)
# ==========================================
def load_global_stylesheet(app: QtWidgets.QApplication):
    """Lee el archivo QSS y lo inyecta a toda la aplicación."""
    try:
        with open("resources/theme.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Advertencia: No se encontró theme.qss")
        
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    base_style = QtWidgets.QStyleFactory.create("Fusion")
    app.setStyle(NeonProxyStyle(base_style))
    load_global_stylesheet(app)

    assets.init_graphic_resources()
    
    test_view = MultiFolderDialog()
    test_view.resize(1200, 800)
    test_view.show()
    
    sys.exit(app.exec())
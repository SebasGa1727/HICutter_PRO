from PyQt6 import QtWidgets, QtCore, QtGui
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from utils.logger import setup_logger
from utils.asset_manager import assets
from utils.converter_config import config_manager
from ui.components.neon_widgets import NeonProxyStyle

logger = setup_logger(__name__)

class BatchRenameDialog(QtWidgets.QDialog):
    INVALID_CHARS = {"\\", "/", ":", "*", "?", '"', "<", ">", "|", "'", "¿"}

    def __init__(self, items_to_rename: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Renombrado en Lote")
        self.setFixedSize(800, 450) # Más ancho para acomodar la tabla
        self.setModal(True)
        self.original_items = items_to_rename # Recibimos los nombres actuales
        self._setup_ui()
        self._populate_table()
        self._update_preview()

    def _setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Título superior
        lbl_title = QtWidgets.QLabel("  Configuracion de renombramiento")
        lbl_title.setProperty("estilo", "title")

        # Contenedor dividido (Izquierda: Configuración / Derecha: Lista)
        split_layout = QtWidgets.QHBoxLayout()
        
        # --- PANEL IZQUIERDO (Configuración - Mismo modelo que carpetas) ---
        config_frame = QtWidgets.QFrame()
        config_frame.setMinimumWidth(230)
        config_layout = QtWidgets.QVBoxLayout(config_frame)
        config_layout.setContentsMargins(10, 10, 10, 10)

        # Creacion de los spinbox con self para acceder a sus atributos
        self.spin_start = QtWidgets.QSpinBox()
        self.spin_start.setRange(0, 99999)
        self.spin_start.setValue(1)

        self.spin_padding = QtWidgets.QSpinBox()
        self.spin_padding.setRange(1, 6)
        self.spin_padding.setValue(3)

        self.spin_step = QtWidgets.QSpinBox()
        self.spin_step.setRange(1, 10000)
        self.spin_step.setValue(1)

        for spinbox in [self.spin_start, self.spin_padding, self.spin_step]:
            spinbox.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            spinbox.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            spinbox.setMinimumWidth(40)
            spinbox.valueChanged.connect(self._update_preview)

        # Creacion del "form layout" que contiene los spinboxes
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(self._create_label("Empezar numeracion desde:"), self.spin_start)
        form_layout.addRow(self._create_label("Cantidad de incremento:"), self.spin_step)
        form_layout.addRow(self._create_label("Cantidad de ceros:"), self.spin_padding)

        # Creacion de los bloques de layout con su respectivo titulo a travez de nuestro metodo constructor
        self.first_block_layout = self._block_layout_builder("NOMENCLATURA", "Ejemplo: Nombre_", "", "", line_edit=True)
        self.second_block_layout = self._block_layout_builder("SECUENCIA NUMERICA", form_layout)

        # Ensamble de todo nuestro layout de configuracion (izquierdo)
        config_layout.setSpacing(10)
        config_layout.addLayout(self.first_block_layout)
        config_layout.addSpacing(10)
        config_layout.addLayout(self.second_block_layout)
        config_layout.addStretch(1)

        # --- PANEL DERECHO (Tabla Antes vs Después) ---
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["ORIGINAL", "NUEVO"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers) # Solo lectura
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)

        # Ensamblaje del Split
        split_layout.addWidget(config_frame)
        split_layout.addWidget(self.table, stretch=1)

        # Botones de Acción (layout inferior)
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_cancel = QtWidgets.QPushButton("Cancelar")
        self.btn_cancel.setProperty("estilo", "cancelar")
        
        self.btn_apply = QtWidgets.QPushButton("Aplicar Renombrado")
        self.btn_apply.setProperty("estilo", "primario")

        self.invalid_char_warning = self._create_label("")
        self.invalid_char_warning.setHidden(True)

        # Armado del btnlayout
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.invalid_char_warning)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_apply)

        # Armado global
        main_layout.addWidget(lbl_title)
        main_layout.addSpacing(10)
        main_layout.addLayout(split_layout, stretch=1)
        main_layout.addSpacing(10)
        main_layout.addLayout(btn_layout)

        # Conexiones
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self._continue)

    def _continue(self):
        """Guarda la informacion de los line edit para futuras ediciones y cierra el dialogo"""
        number = 1
        for line_edit in self.line_edit_list:
            config_manager.set("batch_rename_dialog", str(number), str(line_edit.text()))
            number += 1
        self.accept()

    def _block_layout_builder(self, title: str, *args, line_edit: bool = None) -> QtWidgets.QVBoxLayout :
        """Creador de los bloques izquierdos, utilizando subfunciones de creacion de titulos y lineas editables"""
        main_layout = QtWidgets.QVBoxLayout()
        label = self._create_label(title)
        main_layout.addWidget(label)

        # Verifica si quiere o no crear un line edit, si si, LOS ARGS TIENEN QUE SER SOLAMENTE STRINGS
        if line_edit:
            self.line_edit_list = []
            number = 1
            for arg in args:
                widget = self._create_line_edit(number, arg)
                main_layout.addWidget(widget)
                self.line_edit_list.append(widget)
                number += 1
        else:
            # En caso de que no sean line_edits, verifica si son layouts o widgets para agregarlos al layoutprincipal
            for arg in args:
                if isinstance(arg, QtWidgets.QLayout):
                    main_layout.addLayout(arg)

                elif isinstance(arg, QtWidgets.QWidget):
                    main_layout.addWidget(arg)

        # Retorna el layout con tl titulo y todo a quello que se le haya pasado
        return main_layout

    def _create_label(self, name: str) -> QtWidgets.QLabel:
        """Metodo interno para crear un label de manera constante"""
        label = QtWidgets.QLabel(name)
        label.setProperty("estilo", "label_form")
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        return label

    def _create_line_edit(self, order: int, placeholder: str = "") -> QtWidgets.QLineEdit:
        """Metodo para crear una linea editable y que contenga todas las conexciones necesarias"""
        line_edit = QtWidgets.QLineEdit()
        line_edit.setText(config_manager.get("batch_rename_dialog",str(order)) or "")
        if placeholder: line_edit.setPlaceholderText(placeholder)
        line_edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        line_edit.textChanged.connect(self._update_preview)
        return line_edit

    def _populate_table(self):
        """Llena la columna izquierda una sola vez con los datos originales."""
        self.table.setRowCount(len(self.original_items))
        for row, original_name in enumerate(self.original_items):
            item = QtWidgets.QTableWidgetItem(original_name)
            item.setForeground(QtGui.QBrush(QtGui.QColor("#888888"))) # Gris para el original
            self.table.setItem(row, 0, item)

    def _update_preview(self):
        """Verifica si tiene caracteres invalidos e itera sobre la tabla y actualiza la columna derecha en tiempo real."""
        # Verificamos si existe algun caracter invalido en el string colocado por el usuario
        unavailable_character = self._check_unavailable_character()
        if unavailable_character:
            self.invalid_char_warning.setText(f'Caracter "{unavailable_character}" invalido.')
        # Si no lo hay, mostramos el conjunto de caracteres colocados en tiempo real
        else:
            self._visual_valid()
            base = ''.join(line_edit.text() for line_edit in self.line_edit_list)
            start = self.spin_start.value()
            pad = self.spin_padding.value()
            step = self.spin_step.value()

            for row in range(self.table.rowCount()):
                # Conservamos la extensión original del archivo/carpeta (si la tiene)
                original = self.table.item(row, 0).text()
                ext = ""
                if "." in original:
                    ext = original[original.rfind("."):] # Extrae '.jpg', '.cr2', etc.

                current_num = start + (row * step)
                new_name = f"{base}{str(current_num).zfill(pad)}{ext}"
                
                new_item = QtWidgets.QTableWidgetItem(new_name)
                new_item.setForeground(QtGui.QBrush(QtGui.QColor("#0c8ce9"))) # Azul Neón para el nuevo
                self.table.setItem(row, 1, new_item)

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
            """Modificacion visual de los botones cuando es un caracter invalido y activamos la visualizacion del label"""
            invalid_line.setProperty("estilo", "invalido")
            invalid_line.style().unpolish(invalid_line)
            invalid_line.style().polish(invalid_line)
            self.invalid_char_warning.setHidden(False)
            self.btn_apply.setEnabled(False)
    
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


        self.btn_apply.setEnabled(True)
        self.invalid_char_warning.setHidden(True)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """Sobrescribe el evento de teclado para evitar que Enter/Return cierre el diálogo"""
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            # Si el click esta sobre el widget de crear o cancelar, se efectua el "enter"
            if self.focusWidget() == self.btn_apply:
                self.btn_apply.click()

            elif self.focusWidget() == self.btn_cancel:
                self.btn_cancel.click()
            else:
                # si el enter no es en ninguno de esos botones, se ignora
                event.ignore()
        else:
            # Permitimos el comportamiento predeterminado para cualquier otra tecla 
            super().keyPressEvent(event)

    def get_config(self) -> dict:
        try:
            base_text = ''.join(line_edit.text() for line_edit in self.line_edit_list)
            return{
                "base_name": base_text,
                "start": self.spin_start.value(),
                "pad": self.spin_padding.value(),
                "step": self.spin_step.value(),
            }
        except Exception:
            logger.error("Error al intentar obtener los datos de 'batch_rename_dialog", exc_info=True)

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
    
    items = []
    number = 1
    for item in range(20):
        item = f"Nombre de prueba {number}.jpg"
        items.append(item)
        number += 1

    test_view = BatchRenameDialog(items_to_rename=items)
    test_view.resize(1200, 800)
    test_view.show()
    
    sys.exit(app.exec())
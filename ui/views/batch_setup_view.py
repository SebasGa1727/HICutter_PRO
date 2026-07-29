import sys
import os
# TRUCO PARA MOCK: Agregar la raíz del proyecto al PATH para ejecuciones aisladas
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from PyQt6 import QtWidgets, QtCore, QtGui
from ui.components.neon_widgets import HiddenFilesFilterProxyModel, NeonTreeView, NeonSelectionDelegate
from ui.dialogs.converter_filter_dialog import FilterDialog
from ui.dialogs.converter_config_dialog import ConfigDialog
from ui.dialogs.multi_folder_dialog import MultiFolderDialog
from ui.dialogs.batch_rename_dialog import BatchRenameDialog
from utils.logger import setup_logger
from utils.asset_manager import assets

logger = setup_logger(__name__)

def load_global_stylesheet(app: QtWidgets.QApplication):
    """Lee el archivo QSS y lo inyecta a toda la aplicación."""
    #TODO: Realizar el cambio en main para que toda mi app tenga este diseño
    try:
        with open("resources/theme.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Advertencia: No se encontró theme.qss")

class DirectConvertView(QtWidgets.QWidget):
    # Señales para comunicarse con main.py
    request_cancel = QtCore.pyqtSignal()
    request_convert = QtCore.pyqtSignal(dict) # Enviaremos la configuración final
    request_help = QtCore.pyqtSignal() #Enviaremos video tutorial de ayuda
    request_create_folder = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self._setup_ui()
        self._setup_mock_data() # Datos falsos solo para ver cómo se verá

        
    def _setup_ui(self):
        """
                                                    1. PANEL SUPERIOR (Titulo de la vista y boton de ayuda)
        """
        top_layout = QtWidgets.QHBoxLayout()

        lbl_title = QtWidgets.QLabel("Preparacion de lote")
        lbl_title.setProperty("estilo", "title")
        lbl_title.setStyleSheet("margin: 0px 0px 0px 10px;")

        self.help_btn = QtWidgets.QPushButton("AYUDA")
        self.help_btn.setProperty("estilo", "primario")
        self.help_btn.clicked.connect(self.request_help.emit)

        # Armado del layout superior
        top_layout.addWidget(lbl_title)
        top_layout.addStretch(1)
        top_layout.addWidget(self.help_btn)
        top_layout.addSpacing(15)
        
        """
                                                    2. ZONA CENTRAL (El Splitter de 3 Paneles)
        """
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(14)

        # --- PANEL IZQUIERDO: Explorador de Windows ---
        left_frame = QtWidgets.QGroupBox()
        left_layout = QtWidgets.QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 10, 0) #<- Margen derecho para separar del splitter
        
        lbl_left = QtWidgets.QLabel("ARCHIVOS LOCALES")
        lbl_left.setProperty("estilo", "splitter_title")

        self.os_model = QtGui.QFileSystemModel()
        self.os_model.setRootPath(QtCore.QDir.rootPath())
        self.os_model.setFilter(QtCore.QDir.Filter.NoDotAndDotDot | QtCore.QDir.Filter.AllDirs | QtCore.QDir.Filter.Files | QtCore.QDir.Filter.NoDot)

        # Filtro visual para que el usuario solo vea carpetas y fotos
        self.os_model.setNameFilters(["*.jpg", "*.jpeg", "*.png", "*.tif", "*.tiff", "*.cr2"])
        self.os_model.setNameFilterDisables(False) # Oculta lo que no coincida

        self.proxy_model = HiddenFilesFilterProxyModel()
        self.proxy_model.setSourceModel(self.os_model)
        
        self.tree_os = NeonTreeView()
        self.tree_os.setModel(self.proxy_model)
        root_index = self.os_model.index(QtCore.QDir.homePath())
        self.tree_os.setRootIndex(self.proxy_model.mapFromSource(root_index))
        self.tree_os.setColumnHidden(1, True) # Ocultar tamaño
        self.tree_os.setColumnHidden(2, True) # Ocultar tipo
        self.tree_os.setColumnHidden(3, True) # Ocultar fecha
        self.tree_os.setAnimated(True)
        self.tree_os.setHeaderHidden(True)
        self.tree_os.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection) # <-Seleccion tipo "Ruber band"
        self.tree_os.setDragEnabled(True)
        self.tree_os.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragOnly) #<- Poder arrastrar objetos
        self.tree_os.setItemDelegate(NeonSelectionDelegate(self.tree_os))

        self.btn_add_element_to_sandbox = QtWidgets.QPushButton("→ AÑADIR AL ORGANIZADOR")
        self.btn_add_element_to_sandbox.setStyleSheet("QPushButton { padding: 6px;}")

        # Armado del layout izquierdo
        left_layout.addWidget(lbl_left)
        left_layout.addSpacing(10)
        left_layout.addWidget(self.tree_os, stretch=1)
        left_layout.addWidget(self.btn_add_element_to_sandbox)
        left_layout.addSpacing(5)

        # --- PANEL CENTRAL: Árbol del Sandbox ---
        center_frame = QtWidgets.QGroupBox()
        center_layout = QtWidgets.QVBoxLayout(center_frame)
        center_layout.setContentsMargins(10, 0, 10, 0) #<- para separar de ambos splitters

        sandbox_header_layout = QtWidgets.QHBoxLayout()
        lbl_center = QtWidgets.QLabel("ORGANIZADOR VIRTUAL")
        lbl_center.setProperty("estilo", "splitter_title")

        # CONFIGURACION DEL MENU DE CARPETAS 
        self.menu_virtual_folder = QtWidgets.QMenu()
        self.menu_virtual_folder.setToolTipsVisible(True)

        self.single_folder_menu = QtGui.QAction("Carpeta individual", self)
        self.single_folder_menu.setIcon(assets.get_icon("folder.svg"))
        self.single_folder_menu.setShortcut("ctrl+shift+n")
        self.single_folder_menu.setToolTip("Atajo: ctrl+shift+N")
        self.single_folder_menu.setShortcutVisibleInContextMenu(False)
        self.single_folder_menu.triggered.connect(self.request_create_folder.emit)

        self.multi_folder_menu = QtGui.QAction("Multiples carpetas", self)
        self.multi_folder_menu.setIcon(assets.get_icon("multi_folder.svg"))
        self.multi_folder_menu.setShortcut("ctrl+shift+m")
        self.multi_folder_menu.setToolTip("Atajo: ctrl+shift+M")
        self.multi_folder_menu.setShortcutVisibleInContextMenu(False)
        self.multi_folder_menu.triggered.connect(self._open_create_multi_folder)

        self.menu_virtual_folder.addAction(self.single_folder_menu)
        self.menu_virtual_folder.addSeparator()
        self.menu_virtual_folder.addAction(self.multi_folder_menu)

        # Configuracion de botones
        self.btn_add_virtual_folder = QtWidgets.QPushButton()
        self.btn_add_virtual_folder.setIcon(assets.get_icon("folder.svg"))
        self.btn_add_virtual_folder.setToolTip("Crear carpeta")
        self.btn_add_virtual_folder.setMenu(self.menu_virtual_folder)

        self.btn_rename_virutal_element = QtWidgets.QPushButton()
        self.btn_rename_virutal_element.setIcon(assets.get_icon("lapiz.svg"))
        self.btn_rename_virutal_element.setToolTip("Renombrar")
        self.btn_rename_virutal_element.clicked.connect(self._open_rename_visualizer)

        self.btn_filter_tool = QtWidgets.QPushButton()
        self.btn_filter_tool.setIcon(assets.get_icon("filtro_color.svg"))
        self.btn_filter_tool.setToolTip("Aplicar filtros")
        self.btn_filter_tool.clicked.connect(self._open_filters_dialog)

        self.btn_delete_virtual_element = QtWidgets.QPushButton()
        self.btn_delete_virtual_element.setIcon(assets.get_icon("basura.svg"))
        self.btn_delete_virtual_element.setToolTip("Eliminar elemento")
        self.btn_delete_virtual_element.clicked.connect(self._delete_selected_element)

        for btn in [self.btn_add_virtual_folder, self.btn_rename_virutal_element, self.btn_filter_tool, self.btn_delete_virtual_element]:
            btn.setProperty("estilo", "tool_btn")
            if btn == self.btn_delete_virtual_element:
                btn.setProperty("estilo", "eliminar")
            if btn == self.btn_filter_tool:
                btn.setProperty("estilo", "rainbow")
            btn.setFixedSize(65, 40)
        
        sandbox_header_layout.addWidget(lbl_center)
        sandbox_header_layout.addStretch(1)
        sandbox_header_layout.addWidget(self.btn_add_virtual_folder)
        sandbox_header_layout.addWidget(self.btn_rename_virutal_element)
        sandbox_header_layout.addWidget(self.btn_filter_tool)
        sandbox_header_layout.addWidget(self.btn_delete_virtual_element)

        self.tree_sandbox = NeonTreeView()
        self.tree_sandbox.setHeaderHidden(True)
        self.tree_sandbox.setAnimated(True)
        self.tree_sandbox.setMinimumWidth(250)
        self.tree_sandbox.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection) # <-Seleccion tipo "Ruber band"
        self.tree_sandbox.setDragEnabled(True)
        self.tree_sandbox.setAcceptDrops(True)                                                       # <- Acepta los elementos que suelten aqui
        self.tree_sandbox.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop) # <- Solo acepta que suelten y arrastren archivos 
        self.tree_sandbox.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)             #<- Solo mueve la carpeta, no genera copia
        self.tree_sandbox.setItemDelegate(NeonSelectionDelegate(self.tree_sandbox))

        self.lbl_sandbox_info = QtWidgets.QLabel("Selecciona elementos para modificar")
        self.lbl_sandbox_info.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        self.lbl_sandbox_info.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Armado del layout central
        center_layout.addLayout(sandbox_header_layout)
        center_layout.addSpacing(5)
        center_layout.addWidget(self.tree_sandbox, stretch=1)
        center_layout.addSpacing(7)
        center_layout.addWidget(self.lbl_sandbox_info)
        center_layout.addSpacing(13)
    
        # --- PANEL DERECHO: Cuadrícula de Miniaturas (visualizador) ---
        right_frame = QtWidgets.QGroupBox()
        right_layout = QtWidgets.QVBoxLayout(right_frame)
        right_layout.setContentsMargins(10, 0, 0, 0) #<- Margenes para separar del splitter

        lbl_right = QtWidgets.QLabel("VISUALIZADOR")
        lbl_right.setProperty("estilo", "splitter_title")

        self.list_thumbnails = QtWidgets.QListView()
        self.list_thumbnails.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.list_thumbnails.setIconSize(QtCore.QSize(140, 140))
        self.list_thumbnails.setGridSize(QtCore.QSize(170, 180))
        self.list_thumbnails.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.list_thumbnails.setSpacing(10)
        self.list_thumbnails.setWordWrap(True)
        self.list_thumbnails.setItemDelegate(NeonSelectionDelegate(self.list_thumbnails))
        self.list_thumbnails.setMinimumWidth(185)
        self.list_thumbnails.setDragEnabled(False)
        self.list_thumbnails.setAcceptDrops(False)
        self.list_thumbnails.setMovement(QtWidgets.QListView.Movement.Static) #<- Impide el movimiento de los elementos
        self.list_thumbnails.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers) #<- No permite que se edite el texto
        
        #Armado del layout derecho
        right_layout.addWidget(lbl_right)
        right_layout.addSpacing(10)
        right_layout.addWidget(self.list_thumbnails, stretch=1)

        # Armado del splitter
        self.splitter.addWidget(left_frame)
        self.splitter.addWidget(center_frame)
        self.splitter.addWidget(right_frame)
        # Ajustar proporciones del Splitter
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 1)
        """
                                                    3. PANEL INFERIOR (Botones de Acción)
        """
        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)

        # Seccion de "ruta" de SALIDA y boton "explorar"
        out_dir_layout = QtWidgets.QHBoxLayout()
        self.txt_out_dir = QtWidgets.QLineEdit()
        self.txt_out_dir.setPlaceholderText("Carpeta de salida...")
        self.txt_out_dir.setReadOnly(True)
        self.txt_out_dir.setMaximumWidth(520)
        self.txt_out_dir.setProperty("batch_setup_view", "out_dir_style")

        self.btn_explore_right = QtWidgets.QPushButton(". . .")
        self.btn_explore_right.setToolTip("Explorar")
        self.btn_explore_right.setFixedSize(50, 30)
        self.btn_explore_right.setProperty("batch_setup_view", "out_dir_style")
        
        out_dir_layout.addWidget(self.txt_out_dir, stretch=1)
        out_dir_layout.setSpacing(0)
        out_dir_layout.addWidget(self.btn_explore_right)
        out_dir_layout.addSpacing(0)
        
        # Boton de formato
        self.btn_config_export = QtWidgets.QPushButton("⚙️ FORMATO")
        self.btn_config_export.setToolTip("Formatos de exportacion")
        self.btn_config_export.clicked.connect(self._open_config_dialog)

        # Botones principales
        self.btn_cancel = QtWidgets.QPushButton("CANCELAR")
        self.btn_cancel.setProperty("estilo", "cancelar")
        self.btn_cancel.clicked.connect(self.request_cancel.emit)

        self.btn_convert = QtWidgets.QPushButton("CONVERTIR")
        self.btn_convert.setProperty("estilo", "primario")
        self.btn_convert.clicked.connect(lambda: self.request_convert.emit({}))

        for btn in [self.btn_cancel, self.btn_convert]:
            btn.setFixedSize(100, 32)

        #armado del bottom layout
        bottom_layout.addLayout(out_dir_layout, stretch=5)
        bottom_layout.addStretch(2)
        bottom_layout.addWidget(self.btn_config_export)
        bottom_layout.addStretch(5)
        bottom_layout.addWidget(self.btn_cancel)
        bottom_layout.addSpacing(15)
        bottom_layout.addWidget(self.btn_convert)

        """
                                                                Armado global
        """
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.addLayout(top_layout)
        self.main_layout.addWidget(self.splitter, stretch=1)
        self.main_layout.addSpacing(15)
        self.main_layout.addLayout(bottom_layout)
        self.main_layout.addSpacing(5)

    def _open_filters_dialog(self) -> None:
        """Instancia y ejecuta el diálogo de filtros en modo síncrono (Modal)"""
        #TODO - Borrar esto cuando se conecte a main:
        # Fallback por si estás ejecutando el script de manera aislada 
        # y las carpetas aún no están organizadas en el PATH de esa forma

        # LOGICA DE SELECCIÓN DE IMAGEN
        # 1. Intentamos obtener la selección del visualizador derecho
        selected_indexes = self.list_thumbnails.selectionModel().selectedIndexes()
        image_path = None
        
        if selected_indexes:
            #TODO
            # Si hay algo seleccionado, extraemos su ruta (cuando conectemos el modelo real)
            # Por ahora para el mock, usaremos una cadena o lo dejamos vacío
            pass
            
        # Imagen para poder realizar la muestra
        image_path = "601.jpg"

        dialog = FilterDialog(self, initial_image_path=image_path)
        
        # .exec() congela la ventana principal y espera la respuesta del Pop-Up
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            filtros_elegidos = dialog.get_filter_settings()
            logger.info(f"Filtros aceptados en la UI: {filtros_elegidos}")
            #TODO
            # Aquí guardarás los filtros en una variable para cuando el usuario dé a 'Convertir'

    def _open_config_dialog(self) -> None:
        """Instancia y ejecuta el diálogo de configuración técnica"""

        dialog = ConfigDialog(self, current_config=getattr(self, "_saved_config", {}))
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._saved_config = dialog.get_export_settings()
            logger.info(f"Configuración técnica actualizada: {self._saved_config}")

    def _open_create_multi_folder(self):
        """Abre el dialogo de la creacion de folder"""
        dialog = MultiFolderDialog(self)

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            #TODO Crear una funcion que cree carpetas en el arbol
            # create_folders(**dialog)
            logger.info("Valores guardados")

    def _open_rename_visualizer(self):
        """Abre el dialogo para renombrar los elementos"""
        self.element_list = ["prueba.jpg", "prueba_2.jpg", "prueba_3.raw"]
        dialog = BatchRenameDialog(parent=self, items_to_rename=self.element_list)

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                    #TODO Crear la conexcion entre el diccionario recibido y el renombrado de los elementos
                    logger.info("Valores guardados")
    
    def _delete_selected_element(self):
        pass

    def _setup_mock_data(self):
        """Datos visuales falsos solo para la Fase 1 (Visualización)."""
        # Árbol Virtual Falso
        model_tree = QtGui.QStandardItemModel()
        root_item = QtGui.QStandardItem("📁 Lote_Principal_Acervo")
        sub1 = QtGui.QStandardItem("📁 Carpeta_01")
        sub2 = QtGui.QStandardItem("📁 Carpeta_02")
        root_item.appendRow(sub1)
        root_item.appendRow(sub2)
        model_tree.appendRow(root_item)
        self.tree_sandbox.setModel(model_tree)
        self.tree_sandbox.expandAll()

        # Cuadrícula de Fotos Falsa
        model_list = QtGui.QStandardItemModel()
        for i in range(1, 15):
            item = QtGui.QStandardItem(f"Archivo_00{i}.cr2")
            # Usa un ícono nativo del sistema como placeholder temporal
            icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileIcon)
            item.setIcon(icon)
            model_list.appendRow(item)
        self.list_thumbnails.setModel(model_list)

# ==========================================
# ENTORNO AISLADO (MOCK ENVIRONMENT)
# ==========================================
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    load_global_stylesheet(app)

    assets.init_graphic_resources()
    
    test_view = DirectConvertView()
    test_view.resize(1200, 800)
    test_view.showMaximized()
    
    sys.exit(app.exec())
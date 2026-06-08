import sys
import os
# TRUCO PARA MOCK: Agregar la raíz del proyecto al PATH para ejecuciones aisladas
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from PyQt6 import QtWidgets, QtCore, QtGui
from ui.components.neon_widgets import HiddenFilesFilterProxyModel, NeonTreeView, NeonSelectionDelegate
from utils.logger import setup_logger

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
    request_create_multi_folder = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self._setup_ui()
        self._setup_mock_data() # Datos falsos solo para ver cómo se verá
        
    def _setup_ui(self):
        self.universal_btn_width = 112
        """
                                                    1. PANEL SUPERIOR (Controles y Reglas)
        """
        top_layout = QtWidgets.QHBoxLayout()

        # Bloque Derecho
        top_group_right = QtWidgets.QGroupBox()
        top_group_right.setObjectName("top")
        top_right_layout = QtWidgets.QHBoxLayout(top_group_right)
        top_right_layout.setContentsMargins(0, 0, 0, 0)

        # Botones
        self.btn_config_export = QtWidgets.QPushButton("⚙️ Formato")
        self.btn_config_export.setMinimumWidth(self.universal_btn_width)
        self.btn_config_export.clicked.connect(self._open_config_dialog)

        self.btn_filter_tool = QtWidgets.QPushButton("🪄 Filtros")
        self.btn_filter_tool.setMinimumWidth(self.universal_btn_width)
        self.btn_filter_tool.clicked.connect(self._open_filters_dialog)

        self.help_btn = QtWidgets.QPushButton("Ayuda")
        self.help_btn.setObjectName("help_btn")
        self.help_btn.setMinimumWidth(self.universal_btn_width)
        self.help_btn.clicked.connect(self.request_help.emit)

        top_right_layout.addStretch(1)
        top_right_layout.addWidget(self.btn_config_export)
        top_right_layout.setSpacing(10)
        top_right_layout.addWidget(self.btn_filter_tool)
        top_right_layout.setSpacing(10)
        top_right_layout.addWidget(self.help_btn)

        # Bloque Izquierdo
        top_group_left = QtWidgets.QGroupBox()
        top_group_left.setObjectName("top")
        top_left_layout = QtWidgets.QVBoxLayout(top_group_left)
        top_left_layout.setContentsMargins(0, 0, 0, 0)

        # Seccion de "ruta" de SALIDA y boton "explorar"
        ruta_salida_layout = QtWidgets.QHBoxLayout()
        self.txt_out_dir = QtWidgets.QLineEdit()
        self.txt_out_dir.setPlaceholderText("Carpeta de salida...")
        self.txt_out_dir.setReadOnly(True)
        self.txt_out_dir.setMaximumWidth(520)

        self.btn_explore_right = QtWidgets.QPushButton("Explorar")
        self.btn_explore_right.setObjectName("explore")
        
        ruta_salida_layout.addWidget(self.txt_out_dir, stretch=100)
        ruta_salida_layout.setSpacing(0)
        ruta_salida_layout.addWidget(self.btn_explore_right)
        ruta_salida_layout.addStretch(1)
        
        top_left_layout.addLayout(ruta_salida_layout)

        # Armamos el top_layout 
        top_layout.addWidget(top_group_left, stretch=1)
        top_layout.addWidget(top_group_right, stretch=1)
        """
                                                    2. ZONA CENTRAL (El Splitter de 3 Paneles)
        """
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # --- PANEL IZQUIERDO: Explorador de Windows ---
        left_group = QtWidgets.QGroupBox()
        left_layout = QtWidgets.QVBoxLayout(left_group)
        left_layout.setSpacing(0)
        
        # Contenedor superior
        left_top_container = QtWidgets.QFrame()
        left_top_container.setObjectName("container")

        # Contenedor inferior
        left_bottom_container = QtWidgets.QFrame()
        left_bottom_container.setObjectName("container")

        #Layout de titulo superior
        left_top_layout = QtWidgets.QHBoxLayout()
        left_top_layout.setContentsMargins(7, 7, 7, 7)

        #Layout de boton inferior
        left_bottom_layout = QtWidgets.QHBoxLayout()
        left_bottom_layout.setContentsMargins(7, 7, 7, 7)

        #Titulo recuadro izquierdo
        self.left_top_title = QtWidgets.QLabel("Explorador de Archivos")
        self.left_top_title.setContentsMargins(0, 0, 0, 0)

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

        # Botones de la parte inferior del grupo
        self.btn_add_element_to_sandbox = QtWidgets.QPushButton("➕ Agregar al organizador")

        left_top_layout.addStretch(1)
        left_top_layout.addWidget(self.left_top_title)
        left_top_layout.addStretch(1)
        left_top_container.setLayout(left_top_layout)

        left_bottom_layout.addWidget(self.btn_add_element_to_sandbox)
        left_bottom_container.setLayout(left_bottom_layout)

        left_layout.addWidget(left_top_container)
        left_layout.setSpacing(5)
        left_layout.addWidget(self.tree_os, stretch=1)
        left_layout.setSpacing(5)
        left_layout.addWidget(left_bottom_container)

        # --- PANEL CENTRAL: Árbol del Sandbox ---
        center_group = QtWidgets.QGroupBox()
        center_layout = QtWidgets.QVBoxLayout(center_group)
        center_layout.setSpacing(0)

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

        # Contenedor de los botones
        center_top_container = QtWidgets.QFrame()
        center_top_container.setObjectName("container")

        center_butons = QtWidgets.QHBoxLayout()
        center_butons.setContentsMargins(7, 7, 7, 7)

        #Titulo del recuadro central
        self.center_title = QtWidgets.QLabel("Organizador de exportación")
        self.center_title.setContentsMargins(0, 0, 0, 0)

        #Botones del recuadro
        self.menu_virtual_folder = QtWidgets.QMenu()
        self.menu_virtual_folder.setToolTipsVisible(True)

        self.single_folder_menu = QtGui.QAction("📂 Carpeta individual", self)
        self.single_folder_menu.setShortcut("ctrl+shift+n")
        self.single_folder_menu.setToolTip("Atajo: ctrl+shift+N")
        self.single_folder_menu.setShortcutVisibleInContextMenu(False)
        self.single_folder_menu.triggered.connect(self.request_create_folder.emit)

        self.multi_folder_menu = QtGui.QAction("🗂️ Multiples carpetas", self)
        self.multi_folder_menu.setShortcut("ctrl+shift+m")
        self.multi_folder_menu.setToolTip("Atajo: ctrl+shift+M")
        self.multi_folder_menu.setShortcutVisibleInContextMenu(False)
        self.multi_folder_menu.triggered.connect(self.request_create_multi_folder.emit)

        self.menu_virtual_folder.addAction(self.single_folder_menu)
        self.menu_virtual_folder.addSeparator()
        self.menu_virtual_folder.addAction(self.multi_folder_menu)

        self.btn_add_virtual_folder = QtWidgets.QPushButton("➕ Crear")
        self.btn_add_virtual_folder.setMinimumWidth(self.universal_btn_width)
        self.btn_add_virtual_folder.setMenu(self.menu_virtual_folder)

        self.btn_rename_virutal_element = QtWidgets.QPushButton("✏️ Renombrar")
        self.btn_rename_virutal_element.setMinimumWidth(self.universal_btn_width)

        self.btn_delete_virtual_element = QtWidgets.QPushButton("🗑️ Eliminar")
        self.btn_delete_virtual_element.setObjectName("delete_button")
        self.btn_delete_virtual_element.setMinimumWidth(self.universal_btn_width)

        center_butons.addSpacing(2)
        center_butons.addWidget(self.center_title)
        center_butons.addStretch(1)
        center_butons.addWidget(self.btn_add_virtual_folder)
        center_butons.addSpacing(4)
        center_butons.addWidget(self.btn_rename_virutal_element)
        center_butons.addSpacing(4)
        center_butons.addWidget(self.btn_delete_virtual_element)

        center_top_container.setLayout(center_butons)

        center_layout.addWidget(center_top_container)
        center_layout.addSpacing(5)
        center_layout.addWidget(self.tree_sandbox, stretch=1)
    
        # --- PANEL DERECHO: Cuadrícula de Miniaturas ---
        right_group = QtWidgets.QGroupBox()
        right_layout = QtWidgets.QVBoxLayout(right_group)
        right_layout.setSpacing(0)

        right_title_container = QtWidgets.QFrame()
        right_title_container.setObjectName("container")

        right_top_layout = QtWidgets.QHBoxLayout()
        right_top_layout.setContentsMargins(7, 7, 7, 7)

        self.right_title = QtWidgets.QLabel("Visualizador")
        self.right_title.setContentsMargins(0, 0, 0, 0)

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

        # Armado de titulo
        right_top_layout.addStretch(1)
        right_top_layout.addWidget(self.right_title)
        right_top_layout.addStretch(1)

        right_title_container.setLayout(right_top_layout)

        # Armado final derecho
        right_layout.addWidget(right_title_container)
        right_layout.addSpacing(5)
        right_layout.addWidget(self.list_thumbnails, stretch=1)
        
        # Armado del splitter
        self.splitter.addWidget(left_group)
        self.splitter.addWidget(center_group)
        self.splitter.addWidget(right_group)
        self.splitter.setHandleWidth(14)

        # Ajustar proporciones del Splitter
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 1)
        """
                                                    3. PANEL INFERIOR (Botones de Acción)
        """
        bottom_layout = QtWidgets.QHBoxLayout()

        # Botones principales
        self.btn_cancel = QtWidgets.QPushButton("Cancelar")
        self.btn_cancel.setObjectName("cancel_btn")
        self.btn_cancel.clicked.connect(self.request_cancel.emit)

        self.btn_convert = QtWidgets.QPushButton("Convertir")
        self.btn_convert.setObjectName("convert_btn")
        self.btn_convert.clicked.connect(lambda: self.request_convert.emit({}))

        bottom_layout.addSpacing(6)
        bottom_layout.addWidget(self.btn_cancel)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(self.btn_convert)
        bottom_layout.addSpacing(6)
        """
                                                                Armado global
        """
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(2, 2, 2, 10)
        self.main_layout.addLayout(top_layout)
        self.main_layout.addWidget(self.splitter, stretch=1)
        self.main_layout.addLayout(bottom_layout)

    def _open_filters_dialog(self) -> None:
        """Instancia y ejecuta el diálogo de filtros en modo síncrono (Modal)"""
        try:
            from ui.dialogs.converter_filter_dialog import FilterDialog
        except ImportError:
            #TODO - Borrar esto cuando se conecte a main:
            # Fallback por si estás ejecutando el script de manera aislada 
            # y las carpetas aún no están organizadas en el PATH de esa forma
            import sys
            logger.warning("Asegúrate de que filter_dialog.py exista en ui/dialogs/")
            return

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
        image_path = "input\MX_EXCE_MARZO23_01.JPG" 

        dialog = FilterDialog(self, initial_image_path=image_path)
        
        # .exec() congela la ventana principal y espera la respuesta del Pop-Up
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            filtros_elegidos = dialog.get_filter_settings()
            logger.info(f"Filtros aceptados en la UI: {filtros_elegidos}")
            #TODO
            # Aquí guardarás los filtros en una variable para cuando el usuario dé a 'Convertir'

    def _open_config_dialog(self) -> None:
        """Instancia y ejecuta el diálogo de configuración técnica"""
        try:
            from ui.dialogs.converter_config_dialog import ConfigDialog
        except ImportError:
            #TODO: Borrar esto cuando se conecte a main
            logger.warning("Asegúrate de que config_dialog.py exista en ui/dialogs/")
            return

        dialog = ConfigDialog(self, current_config=getattr(self, "_saved_config", {}))
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._saved_config = dialog.get_export_settings()
            logger.info(f"Configuración técnica actualizada: {self._saved_config}")

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
    
    test_view = DirectConvertView()
    test_view.resize(1200, 800)
    test_view.showMaximized()
    
    sys.exit(app.exec())
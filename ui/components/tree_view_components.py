import os
from PyQt6 import QtWidgets, QtCore, QtGui
from ui.components.neon_widgets import HiddenFilesFilterProxyModel, NeonTreeView, NeonSelectionDelegate, CustomPushButton

class LocalFilesSearcher(QtWidgets.QGroupBox):
    """Componente modularizado para el buscador de archivos del sistema."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        # Configuraciones base heredadas del diseño anterior
        self.setMinimumWidth(210)
        self.setMaximumWidth(400)

        os_layout = QtWidgets.QVBoxLayout(self)
        os_layout.setContentsMargins(10, 0, 10, 0)
        
        lbl_viewer = QtWidgets.QLabel("ARCHIVOS LOCALES")
        lbl_viewer.setProperty("estilo", "splitter_title")
        
        # Instancia y configuración del modelo OS
        self.os_model = QtGui.QFileSystemModel()
        self.os_model.setRootPath(QtCore.QDir.rootPath())
        self.os_model.setFilter(QtCore.QDir.Filter.NoDotAndDotDot | QtCore.QDir.Filter.AllDirs | QtCore.QDir.Filter.Files | QtCore.QDir.Filter.NoDot)
        self.os_model.setNameFilters(["*.jpg", "*.jpeg", "*.png", "*.tif", "*.tiff", "*.cr2"])
        self.os_model.setNameFilterDisables(False)
        
        self.proxy_model = HiddenFilesFilterProxyModel()
        self.proxy_model.setSourceModel(self.os_model)
        
        # Instancia del Árbol Neón
        self.tree_os = NeonTreeView()
        self.tree_os.setModel(self.proxy_model)
        root_index = self.os_model.index(QtCore.QDir.homePath())
        self.tree_os.setRootIndex(self.proxy_model.mapFromSource(root_index))
        
        for i in range(1, 4): self.tree_os.setColumnHidden(i, True)
        
        # Configuraciones visuales
        self.tree_os.setAnimated(True)
        self.tree_os.setHeaderHidden(True)
        self.tree_os.setItemDelegate(NeonSelectionDelegate(self.tree_os))
        
        # Activamos selección múltiple (Shift/Ctrl) y APAGAMOS el drag and drop 
        self.tree_os.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree_os.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree_os.setDragEnabled(False) 
        
        # Botón dinámico expuesto para que la vista padre lo modifique/conecte
        self.btn_add_element = CustomPushButton("AÑADIR")
        self.btn_add_element.setStyleSheet("QPushButton { padding: 6px;}")
        
        os_layout.addWidget(lbl_viewer)
        os_layout.addSpacing(10)
        os_layout.addWidget(self.tree_os, stretch=1)
        os_layout.addWidget(self.btn_add_element)
        os_layout.addSpacing(10)

    def get_selected_paths(self) -> list[str]:
        """Extrae rutas absolutas. Si es un archivo, lo añade. Si es carpeta, escanea recursivamente."""
        paths = []
        valid_exts = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.cr2'}
        
        # 1. Obtenemos los índices visuales
        selected_indexes = self.tree_os.selectionModel().selectedIndexes()
        
        for index in selected_indexes:
            if index.column() == 0:
                # 2. Traducimos a índice del sistema
                source_index = self.proxy_model.mapToSource(index)
                file_path = self.os_model.filePath(source_index)
                file_info = QtCore.QFileInfo(file_path)
                
                # 3. Lógica bifurcada (Archivo vs Directorio)
                if file_info.isFile():
                    if os.path.splitext(file_path)[1].lower() in valid_exts:
                        norm_path = os.path.normpath(file_path)
                        if norm_path not in paths:
                            paths.append(norm_path)
                            
                elif file_info.isDir():
                    # Escaneo profundo de la carpeta seleccionada
                    for root, _, files in os.walk(file_path):
                        for file in files:
                            if os.path.splitext(file)[1].lower() in valid_exts:
                                full_path = os.path.normpath(os.path.join(root, file))
                                if full_path not in paths:
                                    paths.append(full_path)
        return paths


class SandboxTreeView(NeonTreeView):
    """
    Versión pre-configurada del NeonTreeView exclusiva para las áreas de Sandbox.
    Ya contiene todas las reglas de Drag & Drop, selección múltiple y delegados neón.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setMinimumWidth(250)
        
        # Delegado para el pintado azul
        self.setItemDelegate(NeonSelectionDelegate(self))
        
        # Reglas de Interacción (Sin edición de texto, multi-selección)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        
        # Reglas de Drag & Drop interno
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.setDropIndicatorShown(True)
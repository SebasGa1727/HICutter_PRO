import os
from enum import IntEnum
from PyQt6 import QtWidgets, QtCore, QtGui
from ui.components.neon_widgets import HiddenFilesFilterProxyModel, NeonTreeView, NeonSelectionDelegate, CustomPushButton
from utils.asset_manager import assets

USER_ROLE_BASE = QtCore.Qt.ItemDataRole.UserRole.value

class SandboxRoles(IntEnum):
    """
    Definimos identificadores únicos para guardar información invisible en cada nodo.
    Heredamos de IntEnum nativo de Python (no de Qt) sumando a partir del UserRole.
    """
    NodeTypeRole = USER_ROLE_BASE + 1       # Guarda 'FOLDER' o 'FILE'
    OriginalPathRole = USER_ROLE_BASE + 2   # Guarda la Ruta absoluta del disco duro
    HasFilterRole = USER_ROLE_BASE + 3      # Booleano: ¿Tiene un filtro aplicado?
    FilterDataRole = USER_ROLE_BASE + 4     # Diccionario técnico con los valores del filtro
    FilterIdRole = USER_ROLE_BASE + 5       # Guarda un id (int)


class SandboxItem(QtGui.QStandardItem):
    """
    Representa un elemento individual en el árbol (Carpeta o Archivo).
    Hereda de QStandardItem pero expone un constructor limpio y tipado para nuestra lógica de negocio.
    """
    def __init__(self, name: str, node_type: str, original_path: str = ""):
        super().__init__(name)
        
        # Guardamos los metadatos en los roles personalizados
        self.setData(node_type, SandboxRoles.NodeTypeRole)
        self.setData(original_path, SandboxRoles.OriginalPathRole)
        self.setData(False, SandboxRoles.HasFilterRole)
        self.setData({}, SandboxRoles.FilterDataRole)

        # Pre-configuramos el nodo para que no se pueda hacer drag&drop nativo 
        self.setEditable(True)
        self.setDropEnabled(node_type == "FOLDER") # Solo las carpetas pueden recibir elementos
        
        # Asignación de icono base usando el asset_manager
        if node_type == "FOLDER":
            self.setIcon(assets.get_icon("folder.svg")) # Asegúrate de que este icono exista en tu icon_map/assets
        else:
            # Placeholder temporal, en la Fase 3 lo cambiaremos por la miniatura diferida
            self.setIcon(assets.get_icon("image_file.svg")) 

    def update_filters(self, filter_data: dict):
        """
        Método encapsulado para actualizar los filtros de este nodo de forma segura.
        """
        has_filters = bool(filter_data) # Si el diccionario tiene algo, es True
        self.setData(has_filters, SandboxRoles.HasFilterRole)
        self.setData(filter_data, SandboxRoles.FilterDataRole)


class SandboxItemDelegate(QtWidgets.QStyledItemDelegate):
    """
    Toma control de cómo se dibuja CADA CELDA del árbol.
    Nos permite interceptar el renderizado nativo y agregar nuestro icono de filtro a la derecha
    sin instanciar widgets pesados, garantizando máxima eficiencia de memoria.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Precargamos el pixmap del icono del filtro para no leerlo del disco en cada frame
        self.filter_icon_pixmap = assets.get_icon("filtro_color.svg").pixmap(16, 16)
        # TODO: Cambiar "filtro_carpeta.svg" por una variante cuando genere el neuvo svg
        self.filter_folder_icon = assets.get_icon("filtro_color_folder.svg").pixmap(16, 16)
        self.padding_right = 10 # Margen derecho para que el icono no pegue con el borde

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex):
        # Dejamos que Qt dibuje el fondo, la selección, el texto y el icono izquierdo (comportamiento nativo)
        super().paint(painter, option, index)

        # Preguntamos al nodo si tiene el rol de filtro activo
        filter_id = index.data(SandboxRoles.FilterIdRole)
        node_type = index.data(SandboxRoles.NodeTypeRole)
        
        if filter_id and filter_id > 0: # Si tiene un ID válido de filtro
            # Si tiene filtro, calculamos las coordenadas matemáticas para dibujar el icono a la extrema derecha
            rect = option.rect
            pixmap_to_draw = self.filter_folder_icon if node_type == "FOLDER" else self.filter_icon_pixmap
            
            # Posición Y: Centrado verticalmente
            icon_y = rect.top() + (rect.height() - pixmap_to_draw.height()) // 2
            
            # Posición X: A la extrema derecha del rectángulo total de la celda, menos el padding y el ancho del icono
            icon_x = rect.right() - pixmap_to_draw.width() - self.padding_right
            
            # Usamos el hardware para pintar el icono sobre la celda
            painter.drawPixmap(icon_x, icon_y, pixmap_to_draw)

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

    def get_raw_selected_paths(self) -> list[str]:
        """Devuelve únicamente las rutas raíz seleccionadas por el usuario, sin aplanar el contenido."""
        paths = []
        selected_indexes = self.tree_os.selectionModel().selectedIndexes()
        
        for index in selected_indexes:
            if index.column() == 0:
                source_index = self.proxy_model.mapToSource(index)
                file_path = self.os_model.filePath(source_index)
                norm_path = os.path.normpath(file_path)
                if norm_path not in paths:
                    paths.append(norm_path)
                    
        # Filtro de seguridad: Si el usuario selecciona "Carpeta A" y "Carpeta A/foto.jpg" al mismo tiempo,
        # eliminamos "foto.jpg" de esta lista raíz para no duplicarla, ya que la recursividad de "Carpeta A" la incluirá.
        paths.sort(key=len)
        filtered_paths = []
        for p in paths:
            if not any(p.startswith(fp + os.sep) for fp in filtered_paths):
                filtered_paths.append(p)
                
        return filtered_paths


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
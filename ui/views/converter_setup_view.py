import sys
import os
# TRUCO PARA MOCK: Agregar la raíz del proyecto al PATH para ejecuciones aisladas
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from PyQt6 import QtWidgets, QtCore, QtGui
from ui.components.neon_widgets import NeonSelectionDelegate, NeonProxyStyle, CustomPushButton
from ui.components.tree_view_components import LocalFilesSearcher, SandboxTreeView, SandboxItemDelegate, SandboxItem, SandboxRoles
from ui.components.thumbnail_model import ThumbnailListModel
from ui.dialogs.converter_filter_dialog import FilterDialog
from ui.dialogs.converter_config_dialog import ConfigDialog
from ui.dialogs.converter_multi_folder_dialog import MultiFolderDialog
from ui.dialogs.converter_rename_dialog import BatchRenameDialog
from utils.logger import setup_logger
from utils.asset_manager import assets
from utils.icon_map import HICutterIcons
from utils.converter_config import config_manager
from core.filter_registry import FilterRegistry

logger = setup_logger(__name__)

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
        self.sandbox_model = QtGui.QStandardItemModel()
        self.tree_sandbox.setItemDelegate(SandboxItemDelegate(self.tree_sandbox))
        self.tree_sandbox.setModel(self.sandbox_model)
        self.tree_sandbox.selectionModel().selectionChanged.connect(self._on_tree_selection_changed)
        self._show_export_path()
        
    def _setup_ui(self):
        """
                                                    1. PANEL SUPERIOR (Titulo de la vista y boton de ayuda)
        """
        top_layout = QtWidgets.QHBoxLayout()
        top_layout.setSpacing(0)

        return_button = CustomPushButton(HICutterIcons.BACK)
        return_button.setProperty("estilo", "icono")
        return_button.setProperty("variante", "regresar")
        return_button.setFixedSize(30,20)
        return_button.setToolTip("Atras")
        return_button.clicked.connect(self.request_cancel.emit)

        lbl_title = QtWidgets.QLabel("CONVERTIDOR")
        lbl_title.setProperty("estilo", "title")

        self.help_btn = CustomPushButton("AYUDA")
        self.help_btn.setProperty("estilo", "primario")
        self.help_btn.clicked.connect(self.request_help.emit)

        # Armado del layout superior
        top_layout.addWidget(return_button, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        top_layout.addWidget(lbl_title, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        top_layout.addStretch(1)
        top_layout.addWidget(self.help_btn)
        top_layout.addSpacing(15)
        
        """
                                                    2. ZONA CENTRAL (El Splitter de 3 Paneles)
        """
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(14)

        # --- PANEL IZQUIERDO: Explorador de Windows ---
        self.local_searcher = LocalFilesSearcher(self)
        # Sobreescribimos el texto del botón dinámicamente 
        self.local_searcher.btn_add_element.setText("AÑADIR AL ORGANIZADOR")
        self.local_searcher.btn_add_element.clicked.connect(self._add_elements_to_sandbox)

        # --- PANEL CENTRAL: Árbol del Sandbox ---
        center_frame = QtWidgets.QGroupBox(self)
        center_layout = QtWidgets.QVBoxLayout(center_frame)
        center_layout.setContentsMargins(10, 0, 10, 0) #<- para separar de ambos splitters

        sandbox_header_layout = QtWidgets.QHBoxLayout()
        lbl_center = QtWidgets.QLabel("ORGANIZADOR VIRTUAL")
        lbl_center.setProperty("estilo", "splitter_title")

        # CONFIGURACION DEL MENU DE CARPETAS 
        self.menu_virtual_folder = QtWidgets.QMenu(self)
        self.menu_virtual_folder.setToolTipsVisible(True)

        self.single_folder_menu = QtGui.QAction("Carpeta individual", self)
        self.single_folder_menu.setIcon(assets.get_icon("folder.svg"))
        self.single_folder_menu.setShortcut("ctrl+shift+n")
        self.single_folder_menu.setToolTip("Atajo: ctrl+shift+N")
        self.single_folder_menu.setShortcutVisibleInContextMenu(False)
        self.single_folder_menu.triggered.connect(self._create_single_folder)

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
        self.btn_add_virtual_folder = CustomPushButton()
        self.btn_add_virtual_folder.setIcon(assets.get_icon("folder.svg"))
        self.btn_add_virtual_folder.setObjectName("boton_crear_carpeta")
        self.btn_add_virtual_folder.setToolTip("Crear carpeta")
        self.btn_add_virtual_folder.setMenu(self.menu_virtual_folder)

        self.btn_rename_virutal_element = CustomPushButton()
        self.btn_rename_virutal_element.setIcon(assets.get_icon("lapiz.svg"))
        self.btn_rename_virutal_element.setToolTip("Renombrar")
        self.btn_rename_virutal_element.clicked.connect(self._open_rename_visualizer)

        self.btn_filter_tool = CustomPushButton()
        self.btn_filter_tool.setIcon(assets.get_icon("filtro_color.svg"))
        self.btn_filter_tool.setToolTip("Aplicar filtros")
        self.btn_filter_tool.clicked.connect(self._open_filters_dialog)

        self.btn_delete_virtual_element = CustomPushButton()
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

        # Creamos el sandbox desde el tree_view_components
        self.tree_sandbox = SandboxTreeView(center_frame)
        self.tree_sandbox.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked | 
            QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed)
        # Atajo de teclado - eliminar con la tecla "Supr / Delete"
        self.shortcut_delete = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete), self.tree_sandbox)
        self.shortcut_delete.activated.connect(self._delete_selected_element)

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
        right_frame = QtWidgets.QGroupBox(self)
        right_layout = QtWidgets.QVBoxLayout(right_frame)
        right_layout.setContentsMargins(10, 0, 0, 0) #<- Margenes para separar del splitter

        lbl_right = QtWidgets.QLabel("VISUALIZADOR")
        lbl_right.setProperty("estilo", "splitter_title")

        self.list_thumbnails = QtWidgets.QListView(right_frame)
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
        self.thumb_model = ThumbnailListModel(self)
        self.list_thumbnails.setModel(self.thumb_model)

        #Armado del layout derecho
        right_layout.addWidget(lbl_right)
        right_layout.addSpacing(10)
        right_layout.addWidget(self.list_thumbnails, stretch=1)

        # Armado del splitter
        self.splitter.addWidget(self.local_searcher)
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
        out_dir_layout.setSpacing(0)

        self.txt_out_dir = QtWidgets.QLineEdit()
        self.txt_out_dir.setReadOnly(True)
        self.txt_out_dir.setMaximumWidth(520)
        self.txt_out_dir.setProperty("converter_setup_view", "out_dir_style")
        
        self.btn_explore_right = CustomPushButton(". . .")
        self.btn_explore_right.setToolTip("Explorar")
        self.btn_explore_right.setFixedSize(50, 30)
        self.btn_explore_right.setProperty("converter_setup_view", "out_dir_style")
        self.btn_explore_right.clicked.connect(self._select_output_directory)
        
        out_dir_layout.addWidget(self.txt_out_dir, stretch=1)
        out_dir_layout.addWidget(self.btn_explore_right)
        out_dir_layout.addSpacing(0)
        
        # Boton de formato
        self.btn_config_export = CustomPushButton("⚙️ CONFIGURACIÓN")
        self.btn_config_export.setToolTip("Formatos de exportacion")
        self.btn_config_export.clicked.connect(self._open_config_dialog)

        # Boton de convertir
        self.btn_convert = CustomPushButton("CONVERTIR")
        self.btn_convert.setProperty("estilo", "primario")
        self.btn_convert.setFixedSize(100, 32)
        self.btn_convert.clicked.connect(self._execute_conversion)

        # Armado del bottom layout
        bottom_layout.addLayout(out_dir_layout, stretch=5)
        bottom_layout.addStretch(2)
        bottom_layout.addWidget(self.btn_config_export)
        bottom_layout.addStretch(5)
        bottom_layout.addSpacing(15)
        bottom_layout.addWidget(self.btn_convert)
        bottom_layout.addSpacing(15)

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

    def _add_elements_to_sandbox(self):
        """Construye el árbol virtual respetando la jerarquía original y eliminando ramas sin imágenes."""
        # 1. Usamos el método que nos da las rutas exactas seleccionadas
        paths = self.local_searcher.get_raw_selected_paths()
        
        if not paths:
            QtWidgets.QMessageBox.information(self, "Aviso", "Seleccione archivos o carpetas del explorador izquierdo primero.")
            return

        # 2. Determinar el nodo padre virtual donde inyectaremos los datos
        selected_indexes = self.tree_sandbox.selectionModel().selectedIndexes()
        if selected_indexes:
            current_node = self.sandbox_model.itemFromIndex(selected_indexes[0])
            parent_node = current_node if current_node.data(SandboxRoles.NodeTypeRole) == "FOLDER" else (current_node.parent() or self.sandbox_model.invisibleRootItem())
        else:
            parent_node = self.sandbox_model.invisibleRootItem()

        # 3. Función Recursiva de Poda (Pruning)
        valid_exts = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.cr2'}
        
        def build_node_recursive(current_path: str) -> SandboxItem | None:
            """Navega el disco. Retorna un nodo si es válido o tiene hijos válidos. Retorna None si es basura."""
            if os.path.isfile(current_path):
                # Si es archivo, verificamos la extensión
                if os.path.splitext(current_path)[1].lower() in valid_exts:
                    return SandboxItem(os.path.basename(current_path), "FILE", current_path)
                return None
                
            if os.path.isdir(current_path):
                # Si es carpeta, creamos el nodo temporalmente
                folder_node = SandboxItem(os.path.basename(current_path), "FOLDER", current_path)
                has_valid_children = False
                
                try:
                    # Escaneamos el interior de la carpeta en el disco duro
                    for item in os.listdir(current_path):
                        child_path = os.path.join(current_path, item)
                        # Llamada recursiva hacia el fondo del árbol
                        child_node = build_node_recursive(child_path)
                        
                        if child_node is not None:
                            folder_node.appendRow(child_node)
                            has_valid_children = True
                except PermissionError:
                    logger.warning(f"Permiso denegado al leer: {current_path}")
                    
                # Si la carpeta está vacía o solo tenía archivos no válidos (ej. .txt, .pdf), la destruimos
                if has_valid_children:
                    return folder_node
                return None

        # 4. Ejecución del constructor sobre la selección del usuario
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor) # Cursor de carga
        try:
            for path in paths:
                node = build_node_recursive(path)
                if node: # Solo lo agregamos si pasó el filtro
                    parent_node.appendRow(node)
                    
            if parent_node != self.sandbox_model.invisibleRootItem():
                self.tree_sandbox.expand(parent_node.index())
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _on_tree_selection_changed(self):
        """Aplica las políticas de negocio en tiempo real según la selección del usuario"""
        indexes = self.tree_sandbox.selectionModel().selectedIndexes()
        
        # Extraemos los nodos reales de los índices
        nodes = [self.sandbox_model.itemFromIndex(idx) for idx in indexes]
        
        folders = [n for n in nodes if n.data(SandboxRoles.NodeTypeRole) == "FOLDER"]
        files = [n for n in nodes if n.data(SandboxRoles.NodeTypeRole) == "FILE"]
        
        # --- 1. REGLAS DE RENOMBRADO ---
        if len(folders) > 0 and len(files) > 0:
            self.btn_rename_virutal_element.setEnabled(False) # Mixto: Prohibido
        elif len(folders) == 1 and len(files) == 0:
            self.btn_rename_virutal_element.setEnabled(True)  # Renombrar CONTENIDO de carpeta
        elif len(folders) > 1 and len(files) == 0:
            self.btn_rename_virutal_element.setEnabled(True)  # Renombrar CARPETAS
        elif len(folders) == 0 and len(files) > 1:
            self.btn_rename_virutal_element.setEnabled(True)  # Renombrar ARCHIVOS
        else:
            self.btn_rename_virutal_element.setEnabled(False) # 1 archivo o 0 selección -> Inline
            
        # --- 2. ACTUALIZACIÓN DEL LABEL DE INFO ---
        if not nodes:
            self.lbl_sandbox_info.setText("Selecciona elementos para modificar")
            return

        filter_ids = set([n.data(SandboxRoles.FilterIdRole) for n in nodes if n.data(SandboxRoles.FilterIdRole)])
        
        info_texts = []
        info_texts.append(f"{len(folders)} Carpetas, {len(files)} Archivos")
        
        if len(filter_ids) == 1:
            f_id = list(filter_ids)[0]
            info_texts.append(f"Filtro aplicado (Estilo #{f_id})")
        elif len(filter_ids) > 1:
            info_texts.append("Múltiples estilos de filtro en la selección")
            
        self.lbl_sandbox_info.setText(" | ".join(info_texts))

        # ACTUALIZACIÓN DE CUADRÍCULA DE MINIATURAS
        display_files = []
        
        # Si el usuario selecciona 1 sola carpeta, mostramos su contenido
        if len(folders) == 1 and len(files) == 0:
            parent_folder = folders[0]
            display_files = [parent_folder.child(i) for i in range(parent_folder.rowCount()) 
                             if parent_folder.child(i).data(SandboxRoles.NodeTypeRole) == "FILE"]
        # Si el usuario selecciona archivos sueltos directamente, mostramos esos archivos
        elif len(files) > 0:
            display_files = files
            
        # Inyectamos los archivos al modelo. Él se encargará de cargarlos asíncronamente
        self.thumb_model.set_nodes(display_files)

    def _build_export_manifest(self) -> list[dict]:
        """Recorre el árbol del Sandbox de forma recursiva y genera el plan de ejecución."""
        manifest = []
        
        # Leemos la configuración de formato de salida. Por defecto jpg si no se ha configurado.
        from utils.converter_config import config_manager
        export_fmt_idx = config_manager.get("export_image", "format")
        target_extension = ".png" if export_fmt_idx == 1 else ".jpg"

        def traverse(node: SandboxItem, current_virtual_path: str = ""):
            node_type = node.data(SandboxRoles.NodeTypeRole)
            
            # Construimos la ruta relativa estructurada por el usuario
            node_virtual_path = os.path.join(current_virtual_path, node.text()) if current_virtual_path else node.text()
            
            if node_type == "FILE":
                orig_path = node.data(SandboxRoles.OriginalPathRole)
                ext_origen = os.path.splitext(orig_path)[1].lower()
                
                # Obtenemos el diccionario técnico si es que tiene filtro
                filter_id = node.data(SandboxRoles.FilterIdRole)
                filter_data = FilterRegistry.get_filter_by_id(filter_id) if filter_id else {}
                
                # POLÍTICA DE NEGOCIO: Enrutamiento Inteligente (Safeguard)
                action = "process"
                
                # Si no hay filtros visuales Y la extensión origen coincide con la deseada: Cero desgaste de CPU
                if not filter_data and ext_origen == target_extension:
                    action = "copy"
                    
                # Nos aseguramos de que la ruta virtual de salida termine con la extensión correcta (ej. un .cr2 ahora terminará en .jpg)
                base_name_no_ext = os.path.splitext(node_virtual_path)[0]
                final_virtual_path = f"{base_name_no_ext}{target_extension}"
                
                manifest.append({
                    "original_path": orig_path,
                    "virtual_path": final_virtual_path, # Esta será la ruta relativa de exportación
                    "action": action,
                    "filters": filter_data
                })
                
            elif node_type == "FOLDER":
                # Si es carpeta, viajamos a sus hijos recursivamente
                for i in range(node.rowCount()):
                    traverse(node.child(i), node_virtual_path)
                    
        # Iniciar la recursividad desde la raíz invisible del Sandbox
        root = self.sandbox_model.invisibleRootItem()
        for i in range(root.rowCount()):
            traverse(root.child(i), "")
            
        return manifest

    def _execute_conversion(self):
        """Valida los campos obligatorios, construye el manifiesto y emite la señal final hacia main.py."""
        out_dir = self.txt_out_dir.text()
        
        if not out_dir:
            QtWidgets.QMessageBox.warning(self, "Atención", "Por favor, defina una carpeta de salida en el panel inferior.")
            return
            
        manifest = self._build_export_manifest()
        
        if not manifest:
            QtWidgets.QMessageBox.information(self, "Aviso", "El organizador virtual está vacío. Añada elementos antes de convertir.")
            return
            
        # Empaquetamos todo lo necesario para que el motor asíncrono empiece a trabajar
        payload = {
            "output_dir": out_dir,
            "manifest": manifest
        }
        
        logger.info(f"Lanzando conversión masiva: {len(manifest)} archivos encolados.")
        self.request_convert.emit(payload)

    def _show_export_path(self):
        text = config_manager.get("paths", "last_dir")
        if text:    
            self.txt_out_dir.setText(text)
        else:   
            self.txt_out_dir.setPlaceholderText("Carpeta de salida...")

    def _select_output_directory(self):
        text = config_manager.get("paths", "last_dir") 
        if text:
            dir_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Seleccione carpeta de exportación", text)
        else:
            dir_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Seleccione carpeta de exportación", os.path.expanduser("~"))

        if dir_path:
            self.txt_out_dir.setText(os.path.normpath(dir_path))
            config_manager.set("paths", "last_dir", os.path.normpath(dir_path))

    def _create_single_folder(self):
        """Política de Negocio: Creación segura de carpetas sin colisiones de nombre"""
        # 1. Determinar el nodo padre
        selected_indexes = self.tree_sandbox.selectionModel().selectedIndexes()
        
        if selected_indexes:
            current_node = self.sandbox_model.itemFromIndex(selected_indexes[0])
            if current_node.data(SandboxRoles.NodeTypeRole) == "FOLDER":
                parent_node = current_node
            else:
                parent_node = current_node.parent() or self.sandbox_model.invisibleRootItem()
        else:
            parent_node = self.sandbox_model.invisibleRootItem()

        # 2. Lógica para evitar nombres duplicados
        base_name = "Nueva carpeta"
        new_name = base_name
        counter = 1
        
        # Obtenemos los nombres de los hijos actuales del padre
        existing_names = [parent_node.child(i).text() for i in range(parent_node.rowCount())]
        
        while new_name in existing_names:
            new_name = f"{base_name} ({counter})"
            counter += 1

        # 3. Instanciamos e inyectamos al árbol
        new_folder = SandboxItem(new_name, "FOLDER")
        parent_node.appendRow(new_folder)
        
        # Expandimos el padre para que el usuario vea la nueva carpeta
        if parent_node != self.sandbox_model.invisibleRootItem():
            self.tree_sandbox.expand(parent_node.index())

    def _open_filters_dialog(self) -> None:
        """Instancia el diálogo, registra la configuración en memoria y la aplica a la selección."""
        selected_indexes = self.tree_sandbox.selectionModel().selectedIndexes()
        if not selected_indexes:
             QtWidgets.QMessageBox.warning(self, "Atención", "Por favor, seleccione un elemento para aplicar filtros.")
             return

        # 1. Extraemos los nodos de la selección actual
        nodes = [self.sandbox_model.itemFromIndex(idx) for idx in selected_indexes if idx.column() == 0]
        
        # 2. Búsqueda recursiva de la imagen de muestra
        image_path = None
        def find_first_file(node: SandboxItem):
            if node.data(SandboxRoles.NodeTypeRole) == "FILE":
                return node.data(SandboxRoles.OriginalPathRole)
            # Si es carpeta, revisamos a sus hijos
            for i in range(node.rowCount()):
                res = find_first_file(node.child(i))
                if res: return res # Detiene la búsqueda en cuanto encuentra 1 archivo
            return None

        # Iteramos lo seleccionado hasta encontrar la primera imagen
        for n in nodes:
            image_path = find_first_file(n)
            if image_path: break
            
        # Si la carpeta está completamente vacía, usamos el placeholder
        if not image_path:
            image_path = "resources/hicutter_full_black.png"

        # 3. Si solo hay un nodo seleccionado y ya tiene un filtro, lo pasamos al diálogo
        current_filter_data = {}
        if len(nodes) == 1:
            f_id = nodes[0].data(SandboxRoles.FilterIdRole)
            if f_id:
                # Extraemos los datos del registro en RAM
                current_filter_data = FilterRegistry.get_filter_by_id(f_id)

        # 4. Abrimos el diálogo pasándole la imagen dinámica
        dialog = FilterDialog(self, initial_image_path=image_path)

        if current_filter_data:
            dialog.load_settings(current_filter_data)
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            filtros_elegidos = dialog.get_filter_settings()
            
            filter_id = FilterRegistry.register_filter(filtros_elegidos)
            
            def apply_filter_recursive(node: SandboxItem):
                node.setData(filter_id, SandboxRoles.FilterIdRole)
                if node.data(SandboxRoles.NodeTypeRole) == "FOLDER":
                    for i in range(node.rowCount()):
                        apply_filter_recursive(node.child(i))

            for n in nodes:
                apply_filter_recursive(n)
                
            self.tree_sandbox.viewport().update()
            self._on_tree_selection_changed()

    def _open_config_dialog(self) -> None:
        """Instancia y ejecuta el diálogo de configuración técnica"""
        dialog = ConfigDialog(self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            logger.info(f"Configuración técnica actualizada")

    def _open_create_multi_folder(self):
        """Abre el diálogo, recolecta la configuración y genera la secuencia en el Sandbox"""
        dialog = MultiFolderDialog(self)

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            cfg = dialog.get_config()
            
            # 1. Determinar el nodo padre (igual que en carpeta individual)
            selected_indexes = self.tree_sandbox.selectionModel().selectedIndexes()
            if selected_indexes:
                current_node = self.sandbox_model.itemFromIndex(selected_indexes[0])
                parent_node = current_node if current_node.data(SandboxRoles.NodeTypeRole) == "FOLDER" else (current_node.parent() or self.sandbox_model.invisibleRootItem())
            else:
                parent_node = self.sandbox_model.invisibleRootItem()

            existing_names = [parent_node.child(i).text() for i in range(parent_node.rowCount())]
            
            # 2. Generación iterativa
            for i in range(cfg["count"]):
                num_str = str(cfg["start"] + i).zfill(cfg["padding"])
                base_new_name = f"{cfg['base_name']}{num_str}"
                
                # Prevención de colisiones por seguridad
                final_name = base_new_name
                counter = 1
                while final_name in existing_names:
                    final_name = f"{base_new_name} ({counter})"
                    counter += 1
                    
                existing_names.append(final_name)
                new_folder = SandboxItem(final_name, "FOLDER")
                parent_node.appendRow(new_folder)
            
            # 3. Expandir la vista
            if parent_node != self.sandbox_model.invisibleRootItem():
                self.tree_sandbox.expand(parent_node.index())

    def _open_rename_visualizer(self):
        """Identifica el objetivo del renombrado (archivos, carpetas o contenido) y ejecuta el lote."""
        indexes = self.tree_sandbox.selectionModel().selectedIndexes()
        if not indexes:
            return
        
        nodes = [self.sandbox_model.itemFromIndex(idx) for idx in indexes if idx.column() == 0]
        folders = [n for n in nodes if n.data(SandboxRoles.NodeTypeRole) == "FOLDER"]
        files = [n for n in nodes if n.data(SandboxRoles.NodeTypeRole) == "FILE"]
        
        target_nodes = []
        
        # Validación de negocio
        if len(folders) == 1 and len(files) == 0:
            # Caso especial: Renombrar CONTENIDO de una sola carpeta
            parent_folder = folders[0]
            target_nodes = [parent_folder.child(i) for i in range(parent_folder.rowCount())]
        elif len(folders) > 1 and len(files) == 0:
            # Renombrar múltiples CARPETAS seleccionadas
            target_nodes = folders
        elif len(folders) == 0 and len(files) > 1:
            # Renombrar múltiples ARCHIVOS seleccionados
            target_nodes = files
        else:
            return # Mixtos bloqueados

        if not target_nodes:
            QtWidgets.QMessageBox.information(self, "Aviso", "No hay elementos dentro de la carpeta para renombrar.")
            return

        original_names = [n.text() for n in target_nodes]
        
        dialog = BatchRenameDialog(items_to_rename=original_names, parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            cfg = dialog.get_config()
            
            base = cfg["base_name"]
            start = cfg["start"]
            pad = cfg["pad"]
            step = cfg["step"]
            
            # Aplicar matemática a cada nodo
            for row, node in enumerate(target_nodes):
                original = original_names[row]
                ext = ""
                # Preservamos la extensión solo si es un archivo
                if "." in original and node.data(SandboxRoles.NodeTypeRole) == "FILE":
                    ext = original[original.rfind("."):]
                
                current_num = start + (row * step)
                new_name = f"{base}{str(current_num).zfill(pad)}{ext}"
                node.setText(new_name)
    
    def _delete_selected_element(self):
        """Elimina elementos del árbol de forma segura utilizando índices persistentes."""
        indexes = self.tree_sandbox.selectionModel().selectedIndexes()
        if not indexes:
            return

        # Convertimos a índices persistentes para que no se corrompan al borrar elementos superiores
        persistent_indexes = [QtCore.QPersistentModelIndex(idx) for idx in indexes if idx.column() == 0]
        
        for p_idx in persistent_indexes:
            if p_idx.isValid():
                node = self.sandbox_model.itemFromIndex(QtCore.QModelIndex(p_idx))
                if node:
                    parent = node.parent()
                    if parent:
                        parent.removeRow(node.row())
                    else:
                        self.sandbox_model.removeRow(node.row())

# ==========================================
# ENTORNO AISLADO (MOCK ENVIRONMENT)
# ==========================================
if __name__ == "__main__":
    def load_global_stylesheet(app: QtWidgets.QApplication):
        """Lee el archivo QSS y lo inyecta a toda la aplicación."""
        try:
            with open("resources/theme.qss", "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Advertencia: No se encontró theme.qss")
            
    app = QtWidgets.QApplication(sys.argv)
    base_style = QtWidgets.QStyleFactory.create("Fusion")

    app.setStyle(NeonProxyStyle(base_style))
    load_global_stylesheet(app)

    assets.init_graphic_resources()
    
    test_view = DirectConvertView()
    test_view.resize(1200, 800)
    test_view.showMaximized()
    
    sys.exit(app.exec())
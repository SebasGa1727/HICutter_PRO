from collections import OrderedDict
from PyQt6 import QtCore, QtGui
from ui.components.tree_view_components import SandboxRoles
from core.thumbnail_worker import ThumbnailWorker
from utils.asset_manager import assets

class ThumbnailListModel(QtCore.QAbstractListModel):
    """Modelo de datos con paginación visual y protección de RAM."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.nodes = [] # Lista de SandboxItem (Nodos tipo FILE)
        
        # Caché LRU: Protege la RAM limitando el número de QPixmaps cargados simultáneamente
        self.cache = OrderedDict()
        self.MAX_CACHE_SIZE = 200
        
        self.loading = set() # Evita procesar la misma foto dos veces si el usuario hace scroll rápido
        self.thread_pool = QtCore.QThreadPool.globalInstance()
        self.placeholder = assets.get_icon("image_file.svg").pixmap(120, 120) 

    def set_nodes(self, file_nodes: list):
        """Actualiza la cuadrícula de fotos."""
        self.beginResetModel()
        self.nodes = file_nodes
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self.nodes)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """Este método es llamado nativamente por PyQt ÚNICAMENTE para las celdas visibles."""
        if not index.isValid():
            return None
            
        node = self.nodes[index.row()]
        path = node.data(SandboxRoles.OriginalPathRole)

        # 1. Qt pide el texto de la celda
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return node.text()

        # 2. Qt pide la imagen de la celda
        if role == QtCore.Qt.ItemDataRole.DecorationRole:
            # Si ya está en RAM, la devolvemos inmediatamente
            if path in self.cache:
                self.cache.move_to_end(path) # Marcamos como "recién usada"
                return self.cache[path]
            
            # Si no está cargando, despachamos el hilo al procesador
            if path not in self.loading:
                self.loading.add(path)
                worker = ThumbnailWorker(index.row(), path)
                worker.signals.finished.connect(self._on_thumbnail_ready)
                self.thread_pool.start(worker)
            
            # Mientras se carga en 2do plano, devolvemos un ícono genérico
            return self.placeholder
            
        return None

    def _on_thumbnail_ready(self, row: int, path: str, q_img: QtGui.QImage):
        """Recibe la imagen del hilo de fondo y redibuja la celda específica."""
        if path in self.loading:
            self.loading.remove(path)
        
        # Convertimos QImage a QPixmap en el hilo principal (Seguridad GUI)
        pixmap = QtGui.QPixmap.fromImage(q_img)
        self.cache[path] = pixmap
        self.cache.move_to_end(path)
        
        # Si excedemos el límite de caché, borramos la imagen más vieja
        if len(self.cache) > self.MAX_CACHE_SIZE:
            self.cache.popitem(last=False)
        
        # Validamos que el usuario no haya cambiado de carpeta mientras cargaba la foto
        if row < len(self.nodes) and self.nodes[row].data(SandboxRoles.OriginalPathRole) == path:
            idx = self.index(row)
            # Emitimos señal para que Qt redibuje solo esta celda (no toda la pantalla)
            self.dataChanged.emit(idx, idx, [QtCore.Qt.ItemDataRole.DecorationRole])
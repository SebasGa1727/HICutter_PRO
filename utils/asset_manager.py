import os
from PyQt6 import QtGui, QtCore
from utils.logger import setup_logger

logger = setup_logger(__name__)

class AssetManager:
    """
    Gestor centralizado de recursos
    Usa el patrón Singleton para mantener una única caché de memoria en toda la app.
    """
    _instance = None
    _icon_cache = {}    # Almacena QIcons (vectores ligeros)
    _pixmap_cache = {}  # Almacena QPixmaps (imágenes pesadas)

    def __new__(cls): #<- Crea una unica instancia de memoria para este elemento, cada que se crea, verifica si ya existe para no crear mas
        if cls._instance is None:
            cls._instance = super(AssetManager, cls).__new__(cls)
            # Definimos la ruta absoluta a la carpeta resources desde este archivo
            cls._base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'resources'))
        return cls._instance

    def __init__(self):
        self._loaded_resources = False

    def init_graphic_resources(self):
        """
        Este método inyecta todos los recursos pesados en la GPU/RAM de Qt.
        IMPORTANTE: Solo debe llamarse DESPUÉS de instanciar QApplication.
        """
        if self._loaded_resources:
            return # Si ya se cargaron, ignoramos
        
        self._load_fonts()
        self._loaded_resources = True
        logger.info("Recursos cargados exitosamente")

    def _load_fonts(self):
        """Método privado que interactúa con la base de datos tipográfica de Qt."""
        font_id = QtGui.QFontDatabase.addApplicationFont("resources/hicutter_icons.ttf")
        if font_id == -1:
            logger.error("No se pudo cargar la fuente 'hicutter_icons.ttf'.")
        else:
            QtGui.QFontDatabase.applicationFontFamilies(font_id)

    def get_icon(self, filename: str) -> QtGui.QIcon:
        """Devuelve un QIcon. Si ya se usó antes, lo saca de la RAM instantáneamente."""
        if filename not in self._icon_cache:
            path = os.path.join(self._base_path, 'icons', filename)
            if not os.path.exists(path):
                logger.warning(f"Ícono no encontrado: {path}")
                return QtGui.QIcon() # Retorna ícono vacío para no crashear
            self._icon_cache[filename] = QtGui.QIcon(path)
        
        return self._icon_cache[filename]

    def get_pixmap(self, filename: str) -> QtGui.QPixmap:
        """Devuelve un QPixmap (para logos o fotos en QLabels). Usa caché."""
        if filename not in self._pixmap_cache:
            path = os.path.join(self._base_path, 'images', filename)
            if not os.path.exists(path):
                logger.warning(f"Imagen no encontrada: {path}")
                return QtGui.QPixmap()
            self._pixmap_cache[filename] = QtGui.QPixmap(path)
            
        return self._pixmap_cache[filename]

# Instancia global para importar en toda la aplicación
assets = AssetManager()
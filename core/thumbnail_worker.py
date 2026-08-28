import os
import io
from PyQt6 import QtCore, QtGui
from PIL import Image, ImageOps
import rawpy
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ThumbnailSignals(QtCore.QObject):
    # Emite: fila_en_la_lista, ruta_original, imagen_procesada
    finished = QtCore.pyqtSignal(int, str, QtGui.QImage)

class ThumbnailWorker(QtCore.QRunnable):
    """Obrero asíncrono que extrae miniaturas sin bloquear la interfaz gráfica."""
    
    def __init__(self, row: int, path: str, target_size: int = 150):
        super().__init__()
        self.row = row
        self.path = path
        self.target_size = target_size
        self.signals = ThumbnailSignals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            ext = os.path.splitext(self.path)[1].lower()
            q_img = None

            # 1. EXTRACCIÓN ULTRA RÁPIDA PARA .CR2 (Lee el JPG embebido en los metadatos)
            if ext == '.cr2':
                try:
                    with rawpy.imread(self.path) as raw:
                        thumb = raw.extract_thumb()
                        if thumb.format == rawpy.ThumbFormat.JPEG:
                            # Usamos BytesIO para que Pillow lea el JPG embebido y aplique el EXIF
                            with Image.open(io.BytesIO(thumb.data)) as img:
                                img = ImageOps.exif_transpose(img) 
                                img.thumbnail((self.target_size, self.target_size))
                                if img.mode != "RGB": img = img.convert("RGB")
                                data = img.tobytes("raw", "RGB")
                                temp_img = QtGui.QImage(data, img.width, img.height, img.width * 3, QtGui.QImage.Format.Format_RGB888)
                                q_img = temp_img.copy()
                        elif thumb.format == rawpy.ThumbFormat.BITMAP:
                            temp_img = QtGui.QImage(thumb.data, thumb.width, thumb.height, QtGui.QImage.Format.Format_RGB888)
                            q_img = temp_img.copy()
                except Exception:
                    pass # Si falla, pasamos al método de respaldo de Pillow

            # 2. CARGA PEREZOSA (LAZY LOADING) PARA .TIFF, .JPG, .PNG
            if q_img is None:
                with Image.open(self.path) as img:
                    # El método thumbnail de PIL no carga la matriz completa, lee los bytes inteligentemente
                    img = ImageOps.exif_transpose(img)
                    img.thumbnail((self.target_size, self.target_size))
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    data = img.tobytes("raw", "RGB")
                    
                    # SEPARACIÓN EN 2 PASOS PARA SEGURIDAD DE MEMORIA
                    temp_img = QtGui.QImage(data, img.width, img.height, img.width * 3, QtGui.QImage.Format.Format_RGB888)
                    q_img = temp_img.copy()

            # 3. ENVIAMOS LA IMAGEN AL HILO PRINCIPAL
            if q_img is not None:
                self.signals.finished.emit(self.row, self.path, q_img)
                
        except Exception as e:
            logger.warning(f"Error generando miniatura para {os.path.basename(self.path)}: {e}")
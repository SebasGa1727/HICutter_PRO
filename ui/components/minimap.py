from PyQt6 import QtCore, QtGui, QtWidgets
import numpy as np
from utils.utils import _cv_to_qpixmap

class MinimapOverlay(QtWidgets.QWidget):
    """
    Radar/Mini-mapa minimalista.
    Muestra una versión proxy (baja resolución) de la imagen y un recuadro
    indicando el área visible actual (Viewport) del Canvas.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Tamaño fijo y minimalista
        self.setFixedSize(160, 160)
        
        # El radar no debe bloquear los clics que van al Canvas
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.thumbnail: QtCore.QPixmap = None
        self.zoom_level: float = 1.0
        
        # Variables para calcular el recuadro blanco
        self.view_left = 0
        self.view_top = 0
        self.scaled_w = 1
        self.scaled_h = 1
        self.canvas_w = 1
        self.canvas_h = 1

        # Efecto de desvanecimiento (Fade In/Out)
        self.opacity_effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0) # Inicia invisible
        self.setGraphicsEffect(self.opacity_effect)
        
        self.fade_anim = QtCore.QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(250) # 250ms de animación suave
        self.is_visible = False

    def set_image(self, cv_image: np.ndarray):
        """Genera el proxy de baja resolución una sola vez al cargar la imagen."""
        if cv_image is None:
            self.thumbnail = None
            return
            
        full_pixmap = _cv_to_qpixmap(cv_image)
        # Escalar a un tamaño máximo de 140x140 para dejar un margen interno de 10px
        self.thumbnail = full_pixmap.scaled(
            140, 140, 
            QtCore.Qt.AspectRatioMode.KeepAspectRatio, 
            QtCore.Qt.TransformationMode.SmoothTransformation
        )
        self.update()

    def update_state(self, zoom: float, left: int, top: int, scaled_w: int, scaled_h: int, canvas_w: int, canvas_h: int):
        """Recibe el estado matemático del ScaledPixmapManager y actualiza la vista."""
        self.zoom_level = zoom
        self.view_left = left
        self.view_top = top
        self.scaled_w = max(1, scaled_w) # Evitar división por cero
        self.scaled_h = max(1, scaled_h)
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h

        # Lógica de UX: Solo se muestra si el zoom es mayor estricto a 100%
        should_be_visible = (self.zoom_level > 1.0)
        
        if should_be_visible and not self.is_visible:
            self.fade_anim.setEndValue(1.0)
            self.fade_anim.start()
            self.is_visible = True
        elif not should_be_visible and self.is_visible:
            self.fade_anim.setEndValue(0.0)
            self.fade_anim.start()
            self.is_visible = False

        self.update() # Forzar redibujado del rectángulo blanco

    def paintEvent(self, event: QtGui.QPaintEvent):
        # Si la opacidad es 0 o no hay miniatura, no gastamos CPU dibujando
        if self.opacity_effect.opacity() == 0 or self.thumbnail is None:
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Dibuja el fondo oscuro semi-transparente del widget (Minimalista)
        bg_rect = QtCore.QRectF(0, 0, self.width(), self.height())
        painter.setBrush(QtGui.QColor(20, 20, 20, 200))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bg_rect, 8, 8)

        # Dibuja el proxy (Thumbnail) centrado en el radar
        thumb_x = (self.width() - self.thumbnail.width()) // 2
        thumb_y = (self.height() - self.thumbnail.height()) // 2
        painter.drawPixmap(thumb_x, thumb_y, self.thumbnail)

        # Calcular la porción visible
        # Obtiene el porcentaje "oculto" de la imagen de top-left
        ratio_left = max(0, -self.view_left) / self.scaled_w
        ratio_top = max(0, -self.view_top) / self.scaled_h
        
        # obtiene el porcentaje de la imagen que se ve
        ratio_w = min(self.scaled_w, self.canvas_w) / self.scaled_w
        ratio_h = min(self.scaled_h, self.canvas_h) / self.scaled_h

        # Traslada los porcentajes a los pixeles físicos del thumbnail
        rect_x = thumb_x + (ratio_left * self.thumbnail.width())
        rect_y = thumb_y + (ratio_top * self.thumbnail.height())
        rect_w = ratio_w * self.thumbnail.width()
        rect_h = ratio_h * self.thumbnail.height()

        # 4. Dibujar el recuadro blanco del Viewport
        painter.setBrush(QtGui.QColor(255, 255, 255, 40)) # Relleno blanco muy tenue
        pen = QtGui.QPen(QtCore.Qt.GlobalColor.white, 1.5)
        painter.setPen(pen)
        painter.drawRect(QtCore.QRectF(rect_x, rect_y, rect_w, rect_h))

        # 5. Dibujar el texto del porcentaje de Zoom (Acento Neón)
        painter.setPen(QtGui.QColor("#0c8ce9"))
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        
        zoom_text = f"{int(self.zoom_level * 100)}%"
        # Texto alineado abajo a la derecha
        painter.drawText(
            self.rect().adjusted(0, 0, -10, -5), 
            QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignRight, 
            zoom_text
        )
        painter.end()
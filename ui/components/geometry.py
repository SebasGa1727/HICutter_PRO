from typing import Optional, Tuple
from PyQt6 import QtCore, QtGui

class ScaledPixmapManager:
    """
    Gestor de geometría matemática para el Canvas.
    Maneja el escalado de la imagen, el zoom, el paneo y las conversiones
    entre el espacio del widget (pantalla) y el espacio de la imagen original.
    """
    def __init__(self):
        self._pixmap: Optional[QtGui.QPixmap] = None
        self._cached_scaled: Optional[QtGui.QPixmap] = None
        
        # Dimensiones originales de la imagen OpenCV
        self.img_w: int = 0
        self.img_h: int = 0
        
        # Coordenadas de dibujado en el Widget
        self.left: int = 0
        self.top: int = 0
        
        # SISTEMA DE ZOOM Y PANEO 
        self.zoom_level: float = 1.0  # 1.0 = 100% (Ajuste perfecto a la pantalla)
        self.pan_x: float = 0.0
        self.pan_y: float = 0.0
        
        # Límites estrictos definidos (Hardcoded por seguridad)
        self.MIN_ZOOM = 1.0   # 100%
        self.MAX_ZOOM = 5.0   # 500%
        
        # Almacena el widget_size del último update para recálculos rápidos
        self._last_widget_size = QtCore.QSize(0, 0)

    def set_pixmap(self, pixmap: Optional[QtGui.QPixmap]) -> None:
        self._pixmap = pixmap
        if pixmap:
            self.img_w = pixmap.width()
            self.img_h = pixmap.height()

    def set_explicit_dimensions(self, w: int, h: int) -> None:
        """Usado para optimización de memoria cuando viene del pre-escalador."""
        self.img_w = w
        self.img_h = h

    def inject_scaled_cache(self, scaled: QtGui.QPixmap, left: int, top: int) -> None:
        """Inyecta una imagen pre-escalada a 100% de zoom."""
        self._cached_scaled = scaled
        self.left = left
        self.top = top
        # Al inyectar una imagen fresca, reseteamos el zoom y el paneo
        self.zoom_level = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0

    def get_scaled_and_offset(self) -> Tuple[Optional[QtGui.QPixmap], int, int]:
        return self._cached_scaled, self.left, self.top

    def reset_view(self) -> None:
        """Restaura la imagen al 100% y centrada."""
        self.zoom_level = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0

    def apply_zoom(self, delta_zoom: float, anchor_wx: float, anchor_wy: float, widget_size: QtCore.QSize) -> bool:
        """
        Aplica un acercamiento/alejamiento orientado hacia la coordenada del ratón (Zoom Inteligente).
        Retorna True si el zoom cambió (para forzar redibujado), False si se golpeó un límite.
        """
        if self.img_w == 0 or self.img_h == 0:
            return False

        new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self.zoom_level + delta_zoom))
        
        # Si no hubo cambio (estamos en un límite) no calculamos nada
        if new_zoom == self.zoom_level:
            return False

        # obtenemos el pixel exacto donde se encuentra el mouse
        img_pt = self.widget_to_image_coords(anchor_wx, anchor_wy)
        if img_pt is None:
            # Si el ratón está fuera de la imagen (márgenes negros), 
            # hacemos zoom tomando el centro del widget como ancla.
            img_pt = self.widget_to_image_coords(widget_size.width()/2, widget_size.height()/2)
            if img_pt is None: return False

        ix, iy = img_pt

        # Actualizamos el zoom
        self.zoom_level = new_zoom

        # Calculamos la Escala Base (Fit Screen)
        base_scale = min(widget_size.width() / self.img_w, widget_size.height() / self.img_h)
        total_scale = base_scale * self.zoom_level

        # obtenemos las nuevas medidas
        new_math_left = anchor_wx - (ix * total_scale)
        new_math_top = anchor_wy - (iy * total_scale)

        base_left = (widget_size.width() - (self.img_w * total_scale)) / 2.0
        base_top = (widget_size.height() - (self.img_h * total_scale)) / 2.0

        self.pan_x = new_math_left - base_left
        self.pan_y = new_math_top - base_top

        # Generamos la nueva caché de la imagen escalada
        self.update_scaled_cache(widget_size)
        return True

    def update_scaled_cache(self, widget_size: QtCore.QSize) -> None:
        """
        Recalcula la imagen redimensionada (el QPixmap) para dibujarla rápidamente
        en el Canvas con las coordenadas de Zoom y Paneo actuales.
        """
        self._last_widget_size = widget_size

        if self._pixmap is None:
            return

        # Escala base para que encaje en la pantalla (100%)
        base_scale = min(widget_size.width() / self.img_w, widget_size.height() / self.img_h)
        # Escala total con el modificador de zoom
        total_scale = base_scale * self.zoom_level

        new_w = int(self.img_w * total_scale)
        new_h = int(self.img_h * total_scale)

        # Evitar crear un pixmap de 0 px o de tamaños catastróficos si falla el clamping
        if new_w <= 0 or new_h <= 0: return

        # Calculamos cuánto sobra de la imagen respecto a la ventana para delimitarlo por los espacios vacios
        max_pan_x = max(0.0, (new_w - widget_size.width()) / 2.0)
        max_pan_y = max(0.0, (new_h - widget_size.height()) / 2.0)

        # Limitamos (Clamp) el pan actual para que no exceda el sobrante disponible.
        # Si la imagen es más pequeña o igual a la ventana, max_pan es 0 y pan_x/y se ancla a 0.0
        self.pan_x = max(-max_pan_x, min(max_pan_x, self.pan_x))
        self.pan_y = max(-max_pan_y, min(max_pan_y, self.pan_y))

        # Transformación suave y de alta calidad (Bilinear filtering)
        self._cached_scaled = self._pixmap.scaled(
            new_w, new_h,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation
        )

        # Centrado base + Paneo calculado en apply_zoom
        self.left = int((widget_size.width() - new_w) / 2 + self.pan_x)
        self.top = int((widget_size.height() - new_h) / 2 + self.pan_y)

    def widget_to_image_coords(self, wx: float, wy: float) -> Optional[Tuple[float, float]]:
        """Mapeo inverso. Crucial que incluya la matemática del zoom/pan."""
        if self._cached_scaled is None or self.img_w == 0 or self.img_h == 0:
            return None

        # Posición local relativa a la esquina de la imagen dibujada
        local_x = wx - self.left
        local_y = wy - self.top

        # Factores de escala actuales
        scale_x = self.img_w / self._cached_scaled.width()
        scale_y = self.img_h / self._cached_scaled.height()

        ix = local_x * scale_x
        iy = local_y * scale_y

        # Validación: ¿Está dentro de los límites de la imagen matemática?
        if 0 <= ix <= self.img_w and 0 <= iy <= self.img_h:
            return (ix, iy)
        return None

    def image_to_widget_coords(self, ix: float, iy: float) -> Optional[Tuple[int, int]]:
        """Mapeo directo para dibujar elementos de UI sobre la imagen."""
        if self._cached_scaled is None or self.img_w == 0 or self.img_h == 0:
            return None

        scale_x = self._cached_scaled.width() / self.img_w
        scale_y = self._cached_scaled.height() / self.img_h

        wx = int((ix * scale_x) + self.left)
        wy = int((iy * scale_y) + self.top)

        return (wx, wy)
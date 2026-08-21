from __future__ import annotations

from typing import Optional, Tuple
from enum import Enum
import math
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from ui.components.geometry import ScaledPixmapManager
from ui.components.point_manager import PointManager
from ui.components.magnifier import MagnifierTool
from ui.components.sniper_mode import SniperModeManager
from utils.utils import _cv_to_qpixmap
from utils.canvas_config_manager import CanvasConfigManager
from ui.components.config_drawer import ConfigDrawerOverlay
from ui.components.minimap import MinimapOverlay

class ToolMode(Enum):
    FREEHAND = 1      # Modo original: clic por clic
    BOX_SELECT = 2    # Modo nuevo: arrastrar y soltar
    EDITING = 3       # Mover puntos ya creados

class ImageCanvas(QtWidgets.QWidget):
    """Widget para mostrar la imagen y realizar todo el control de recorte ya sea individual o por lote
    delega funciones como el sniper mode, magnifier, zoom, minimapa, rotaciones y shortcuts
    a travez de un pintado estricto y definido 
    """
    fourPointsSelected = QtCore.pyqtSignal(object)
    sig_save_requested = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)

        self.cv_image: Optional[np.ndarray] = None
        self._pixmap: Optional[QtGui.QPixmap] = None

        # Variables del HUD
        self.hud_filename: str = ""
        self.hud_progress: str = ""
        self.hud_colorspace: str = ""

        # helpers
        self._scaled_manager = ScaledPixmapManager()
        self._point_manager = PointManager()

        #Shortcuts
        self.KEY_ERRASE = "Backspace"
        self.KEY_SNIPER = "Shift"
        self.BTN_LEFT_CLICK = QtCore.Qt.MouseButton.LeftButton
        self.BTN_MAGNIFIER = QtCore.Qt.MouseButton.RightButton
        self.BTN_TO_SAVE = QtCore.Qt.MouseButton.RightButton

        # interacción/cursor
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self._mouse_in_img: bool = False
        self._mouse_wx: float = 0
        self._mouse_wy: float = 0
        self.cross_len: int = 10
        self.cross_color = QtGui.QColor(12, 140, 233)
        self.line_color = QtGui.QColor(0, 0, 0)
        self.cross_width: int = 3
        self.border_color = QtGui.QColor(190, 190, 190)

        # valores para la Lupa de enfoque 
        MAG_SIZE = 270
        MAG_ZOOM = 1.3
        MAG_BORDER = 2
        MAG_OFFSET = 60
        self._magnifier_enabled: bool = False
        self._magnifier = MagnifierTool(size=MAG_SIZE, zoom=MAG_ZOOM, border=MAG_BORDER, offset=MAG_OFFSET)
       
        # Modo sniper/precisión
        SNIPER_SENSITIVITY = 0.07
        self._sniper = SniperModeManager(sensitivity=SNIPER_SENSITIVITY)

        self.tool_mode = ToolMode.FREEHAND
        # Variables para Drag & Drop (Coordenadas en pixeles del widget)
        self._box_start_w: Optional[Tuple[int, int]] = None
        self._box_current_w: Optional[Tuple[int, int]] = None
        
        # Variables para Arrastre (Drag) de nodos
        self._dragged_point_idx: Optional[int] = None
        self._hitbox_radius = 15.0 # Pixeles en pantalla para atrapar el clic

        self.config_manager = CanvasConfigManager()
        self.config_overlay = ConfigDrawerOverlay(self, self.config_manager)

        self.minimap = MinimapOverlay(self)
        self.ZOOM_STEP = 0.1  # Cuánto aumenta/disminuye el zoom por cada "tick" (10%)

        # --- BANDERAS DE CONTROL PARA BOUNDING BOX ---
        self._press_pos: Optional[Tuple[int, int]] = None
        self._is_dragging_box: bool = False
        self._click_to_click_box: bool = False

        # bandera de control de hover (modo edicion)
        self._hovered_point_idx: Optional[int] = None

    def set_tool_mode(self, mode: ToolMode) -> None:
        """Controlador externo para cambiar de herramienta desde el UI"""
        self.tool_mode = mode
        if mode == ToolMode.BOX_SELECT:
            self.reset_points() # Limpia si se cambia de herramienta abruptamente

    def _get_hit_point_index(self, wx: int, wy: int) -> Optional[int]:
        """
        Implementación matemática de Hit-Testing (Ley de Fitts).
        Evalúa si el clic ocurrió cerca de algún nodo renderizado, operando en pixeles 
        de pantalla absolutos para que el área de interacción no cambie con el zoom.
        """
        for i, (ix, iy) in enumerate(self._point_manager.points):
            wcoords = self.image_to_widget_coords(ix, iy)
            if wcoords:
                p_wx, p_wy = wcoords
                # Distancia euclidiana plana
                dist = math.sqrt((wx - p_wx)**2 + (wy - p_wy)**2)
                if dist <= self._hitbox_radius:
                    return i
        return None

    def _toggle_magnifier(self) -> None:
        self._magnifier_enabled = not self._magnifier_enabled
        self.update()

    def set_hud_info(self, filename: str, progress: str) -> None:
        '''Actualiza la informacion del archivo actual para mostrarla en el HUD'''
        self.hud_filename = filename
        self.hud_progress = progress

    # ---------- Carga y conversión
    def load_image(self, cv_image: Optional[np.ndarray] = None, pre_scaled_qimage: Optional[QtGui.QImage] = None) -> None:
        if cv_image is None:
            raise ValueError("Se recibio un cv_image vacio o nulo")
        
        self.cv_image = cv_image
        
        # Color space para el HUD
        if self.cv_image.ndim == 3 and self.cv_image.shape[2] == 3:
            self.hud_colorspace = "RGB (Color Estándar)"
        elif self.cv_image.ndim == 3 and self.cv_image.shape[2] == 4:
            self.hud_colorspace = "RGBA (Color con Transparencia)"
        elif self.cv_image.ndim == 2:
            self.hud_colorspace = "Grayscale (Escala de Grises)"
        else:
            self.hud_colorspace = "Desconocido"

        # Cargamos el pixmap
        if pre_scaled_qimage is not None:
            # Limpiamos cualquier rastro del pixmap pesado
            self._pixmap = None
            self._scaled_manager.set_pixmap(None)
            
            # Le decimos al manager las dimensiones matemáticas originales
            h, w = self.cv_image.shape[:2]
            self._scaled_manager.set_explicit_dimensions(w, h)
            
            # Inyectamos la imagen ya escalada
            scaled_pixmap = QtGui.QPixmap.fromImage(pre_scaled_qimage)
            widget_size = self.size()
            left = (widget_size.width() - scaled_pixmap.width()) // 2
            top = (widget_size.height() - scaled_pixmap.height()) // 2
            
            self._scaled_manager.inject_scaled_cache(scaled_pixmap, left, top)
        else:
            # Modo Lento: Solo se usa al abrir una foto manual (1x1) o sin lote
            self._pixmap = _cv_to_qpixmap(self.cv_image)
            self._scaled_manager.set_pixmap(self._pixmap)
            self._update_scaled_pixmap_cache()

        self.minimap.set_image(self.cv_image)
        self._point_manager.reset()
        self._notify_minimap()
        self.update()

    def _create_cross_cursor(self, cross_len: int) -> QtGui.QCursor:
        """Crea un QCursor con una cruceta roja centrada."""
        size = cross_len * 2 + 7
        pix = QtGui.QPixmap(size, size)
        pix.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        pen = QtGui.QPen(self.cross_color)
        pen.setWidth(self.cross_width)
        pen.setCosmetic(True)
        painter.setPen(pen)
        center = size // 2
        painter.drawLine(center - cross_len, center, center + cross_len, center)
        painter.drawLine(center, center - cross_len, center, center + cross_len)
        painter.end()
        return QtGui.QCursor(pix, center, center)

    # ---------- Utilidades de mapeo coordenadas
    def _scaled_pixmap_and_offset(self) -> Tuple[Optional[QtGui.QPixmap], int, int]:
        """Devuelve (scaled_pixmap, left, top) para centrar la imagen en el widget."""
        scaled, left, top = self._scaled_manager.get_scaled_and_offset()
        
        if scaled is None:
            # Si no hay caché, intentamos generarla. Si _pixmap es None, no hará nada.
            self._update_scaled_pixmap_cache()
            return self._scaled_manager.get_scaled_and_offset()
            
        return scaled, left, top

    def _update_scaled_pixmap_cache(self) -> None:
        """Actualiza `self._scaled_pixmap_cache`, `left` y `top` en función
        del tamaño actual del widget y `self._pixmap`.
        Se debe llamar sólo en `load_image` y `resizeEvent`.
        """
        # Delegate scaled-cache computation to the manager
        self._scaled_manager.set_pixmap(self._pixmap)
        self._scaled_manager.update_scaled_cache(self.size())

    def widget_to_image_coords(self, wx: int, wy: int) -> Optional[Tuple[float, float]]:
        """Convierte coordenadas de widget (px) a coordenadas en la imagen (px).
        Retorna None si el punto está fuera del área de la imagen (margen negro alrededor).
        """
        return self._scaled_manager.widget_to_image_coords(wx, wy)

    def image_to_widget_coords(self, ix: float, iy: float) -> Optional[Tuple[int, int]]:
        return self._scaled_manager.image_to_widget_coords(ix, iy)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        # Si el usuario cambia el tamaño de la ventana a medio lote, 
        # forzamos a crear el Pixmap pesado para recalcular sin perder calidad.
        if self._pixmap is None and self.cv_image is not None:
            self._pixmap = _cv_to_qpixmap(self.cv_image)
            self._scaled_manager.set_pixmap(self._pixmap)

        # Mantener el minimapa en la esquina inferior izquierda
        margin = 15
        radar_x = margin
        radar_y = self.height() - self.minimap.height() - margin
        self.minimap.move(radar_x, radar_y)
        self._notify_minimap()

        self.config_overlay.resize(self.size())
        self._update_scaled_pixmap_cache()
        super().resizeEvent(event)
        self.update()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        # Brindamos prioridad a lo que pasa si se tiene presionado "CTRL"
        if modifiers == QtCore.Qt.KeyboardModifier.ControlModifier:
            if key == QtCore.Qt.Key.Key_0:
                self._smooth_reset_zoom()
                return
            
            # Si presiona Ctrl + Flecha Arriba/Abajo, forzamos el zoom, ignorando cualquier otro estado
            if key in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down):
                if self._pixmap is None and self.cv_image is not None:
                    self._pixmap = _cv_to_qpixmap(self.cv_image)
                    self._scaled_manager.set_pixmap(self._pixmap)
                    self._scaled_manager.update_scaled_cache(self.size())

                cx = self.width() / 2.0
                cy = self.height() / 2.0
                delta = self.ZOOM_STEP if key == QtCore.Qt.Key.Key_Up else -self.ZOOM_STEP
                self._handle_zoom(delta, cx, cy)
                return

        # --- NAVEGACIÓN POR FLECHAS CUANDO EL ZOOM ESTÁ ACTIVO ---
        if self._is_zoomed() and modifiers != QtCore.Qt.KeyboardModifier.ControlModifier:
            pan_speed = 30 # Píxeles de desplazamiento por pulsación
            if key == QtCore.Qt.Key.Key_Up:
                self._pan_view(0, pan_speed) # Mueve imagen hacia abajo (revela arriba)
                return
            elif key == QtCore.Qt.Key.Key_Down:
                self._pan_view(0, -pan_speed) # Mueve imagen hacia arriba
                return
            elif key == QtCore.Qt.Key.Key_Left:
                self._pan_view(pan_speed, 0) # Mueve imagen hacia la derecha
                return
            elif key == QtCore.Qt.Key.Key_Right:
                self._pan_view(-pan_speed, 0) # Mueve imagen hacia la izquierda
                return

            # Ignora Borrar Puntos, Enter, etc. mientras haya zoom
            super().keyPressEvent(event)
            return

        # --- LÓGICA NORMAL (Solo si no hay zoom) ---
        if key == QtCore.Qt.Key.Key_Return or key == QtCore.Qt.Key.Key_Enter:
            self.sig_save_requested.emit()
            self._mouse_in_img = False
            self.unsetCursor()
            self.update()
        
        if key == QtGui.QKeySequence(self.KEY_ERRASE):
            if len(self._point_manager) > 0:
                self._point_manager.pop_last()
                self.update()

        if self._is_sniper_allowed() and self.config_manager.get("enable_sniper"):
            sniper_key = QtGui.QKeySequence(self.KEY_SNIPER)
            handled, mwx, mwy = self._sniper.handle_key_press(event, self, key_type=sniper_key)
            if handled:
                if mwx is not None and mwy is not None:
                    self._mouse_wx = mwx
                    self._mouse_wy = mwy
                self._refresh_cursor_state()
                self.update()
                return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        """Maneja la liberación de Shift para salir del modo precisión.
        Evita el glitch del ratón teletransportando el cursor del SO a la posición virtual.
        """
        if self.config_manager.get("enable_sniper"):
            sniper_key = QtGui.QKeySequence(self.KEY_SNIPER)
            handled = self._sniper.handle_key_release(event, self, key_type=sniper_key)
            if handled:
                # Obtenemos la última coordenada (x, y) de tu cursor lento (Sniper)
                wfx, wfy = self._sniper.get_current_widget_pos(None, self)
                # Convertimos esa coordenada interna de la app a coordenadas absolutas del monitor
                global_pos = self.mapToGlobal(QtCore.QPoint(int(wfx), int(wfy)))
                # Obligamos al mouse físico de Windows a moverse a esa coordenada
                QtGui.QCursor.setPos(global_pos)
                self._refresh_cursor_state()
                self.update()
                return

        super().keyReleaseEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """Rastrea la posición del cursor y actualiza el cursor cuando está sobre la imagen"""
        # Verifica si esta en estado de zoom, si lo esta no delega el movimiento a ningun elemento
        if self._is_zoomed():
            # Restauramos la flecha normal de Windows si está en zoom
            if self.cursor().shape() == QtCore.Qt.CursorShape.BlankCursor:
                self.unsetCursor()
            self._mouse_in_img = False
            return

        wx = int(event.position().x())
        wy = int(event.position().y())
        
        # Delega el movimiento a el modo sniper
        if self._is_sniper_allowed() and self.config_manager.get("enable_sniper"):
            handled, mwx, mwy, s_min_img = self._sniper.handle_mouse_move(event, self)
            if handled:
                if mwx is not None and mwy is not None:
                    wx = int(round(mwx))
                    wy = int(round(mwy))
                if isinstance(s_min_img, bool):
                    self._mouse_in_img = s_min_img

        # Guardamos la coordenada final unificada para que el paintEvent la dibuje
        self._mouse_wx = wx
        self._mouse_wy = wy
        img_pt = self.widget_to_image_coords(wx, wy)

        # Evaluamos si se esta realizando un arrastre
        if event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            if self.tool_mode == ToolMode.FREEHAND and self._press_pos is not None and self._dragged_point_idx is None:
                # Distancia Euclidiana
                dist = math.hypot(wx - self._press_pos[0], wy - self._press_pos[1])
                if dist > 20 and self.config_manager.get("enable_drag_drop"):
                    # El usuario está arrastrando. Borramos el punto erróneo y activamos la caja.
                    self.reset_points()
                    self.tool_mode = ToolMode.BOX_SELECT
                    self._is_dragging_box = True
                    self._box_start_w = self._press_pos

        # Actualización visual de la caja en movimiento
        if self.tool_mode == ToolMode.BOX_SELECT and self._box_start_w is not None:
            self._box_current_w = (wx, wy)
        
        if self.tool_mode == ToolMode.EDITING and self._dragged_point_idx is not None:
            if img_pt:
                self._point_manager.update_point(self._dragged_point_idx, img_pt)

        # --- EVALUACIÓN DE ESTADOS UX ---
        is_dragging_node = (self.tool_mode == ToolMode.EDITING and self._dragged_point_idx is not None)
        
        # Detectar si el ratón está sobre un nodo (solo si no estamos arrastrando)
        if not is_dragging_node and img_pt is not None:
            self._hovered_point_idx = self._get_hit_point_index(wx, wy)
        else:
            self._hovered_point_idx = None

        if img_pt is not None:
            self._mouse_in_img = True
        else:
            self._mouse_in_img = False

        # --- ACTUALIZACIÓN VISUAL (Qué cursor debe mostrarse) ---
        self._refresh_cursor_state()
        self.update()

    # ---------- Interacción de usuario
    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self._smooth_reset_zoom()
            return
        # Seguro de UI/UX - implementamos un tool tip si el usuario quiere ejecutar alguna herramienta
        if self._is_zoomed():
            if event.button() in (self.BTN_LEFT_CLICK, self.BTN_MAGNIFIER):
                QtWidgets.QToolTip.showText(
                    event.globalPosition().toPoint(),
                    "🔎 Modo Zoom Activo.\nUsa Scroll, Clic Central o Ctrl+0 para salir y editar.",
                    self
                )
            return
        
        if event.button() == self.BTN_LEFT_CLICK:
            wfx, wfy = self._sniper.get_current_widget_pos(event, self)
            wx = int(round(wfx))
            wy = int(round(wfy))
            
            img_pt = self.widget_to_image_coords(wx, wy)
            if img_pt is None: return

            # Cerrar caja iniciada por Doble Clic 
            if self.tool_mode == ToolMode.BOX_SELECT and self._click_to_click_box:
                if self._box_start_w:
                    self._box_current_w = (wx, wy)
                    pt1 = self.widget_to_image_coords(*self._box_start_w)
                    pt2 = img_pt
                    if pt1 and pt2:
                        self._point_manager.set_points_from_rect(pt1, pt2)
                    
                    self._box_start_w = None
                    self._box_current_w = None
                    self._click_to_click_box = False
                    self.tool_mode = ToolMode.EDITING
                self._refresh_cursor_state()
                self.update()
                return

            self._press_pos = (wx, wy)
            self._is_dragging_box = False
            
            # si hicimos clic sobre un punto existente, lo edita
            hit_idx = self._get_hit_point_index(wx, wy)
            if hit_idx is not None:
                self.tool_mode = ToolMode.EDITING
                self._dragged_point_idx = hit_idx
                return

            # Si no tocamos un punto, actuamos según la herramienta seleccionada (si el usuario arrastra el mouse, se actualiza en otra funcion)
            if self.tool_mode in (ToolMode.FREEHAND, ToolMode.EDITING):
                if len(self._point_manager) < 4:
                    self.tool_mode = ToolMode.FREEHAND
                    self._point_manager.add_point(img_pt)
            
            self.update()

        elif event.button() == self.BTN_MAGNIFIER:
            if self.config_manager.get("enable_magnifier"):
                self._toggle_magnifier()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == self.BTN_LEFT_CLICK:
            # Soltar un punto que estábamos arrastrando
            if self.tool_mode == ToolMode.EDITING:
                self._dragged_point_idx = None
                
            # Finaliza la creacion de la caja por el metodo drag n drop
            elif self.tool_mode == ToolMode.BOX_SELECT and self._is_dragging_box:
                if self._box_start_w and self._box_current_w:
                    pt1 = self.widget_to_image_coords(*self._box_start_w)
                    pt2 = self.widget_to_image_coords(*self._box_current_w)
                    
                    if pt1 and pt2:
                        self._point_manager.set_points_from_rect(pt1, pt2)
                
                self._box_start_w = None
                self._box_current_w = None
                self._is_dragging_box = False
                self.tool_mode = ToolMode.EDITING #<- Trancision al modo edicion
            
            self._press_pos = None # Limpiamos la memoria del clic
            self._refresh_cursor_state()
            self.update()

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._is_zoomed(): return

        if event.button() == self.BTN_LEFT_CLICK:
            # Opción 1: Confirmar el guardado rápido si ya hay 4 puntos
            if self.config_manager.get("enable_double_click") and len(self._point_manager) == 4:
                self.sig_save_requested.emit()
                self._mouse_in_img = False
                self.unsetCursor()
                self.update()
                return

            # Opción 2: INICIAR CAJA POR DOBLE CLIC
            # Solucionamos la condición de carrera permitiendo "len <= 1"
            if len(self._point_manager) <= 1 and self.config_manager.get("enable_drag_drop"):
                self.reset_points() # Borramos el punto del primer clic fantasma
                
                wfx, wfy = self._sniper.get_current_widget_pos(event, self)
                wx = int(round(wfx))
                wy = int(round(wfy))
                
                self.tool_mode = ToolMode.BOX_SELECT
                self._click_to_click_box = True
                self._box_start_w = (wx, wy)
                self._box_current_w = (wx, wy)
                self.update()
                return

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """Control del Zoom Inteligente mediante Ctrl + Scroll."""
        # Solo actuar si se presiona la tecla Control
        if event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:

            # Si estamos en modo lote y el usuario quiere hacer zoom, generamos el Pixmap de alta resolución en el momento.
            if self._pixmap is None and self.cv_image is not None:
                self._pixmap = _cv_to_qpixmap(self.cv_image)
                self._scaled_manager.set_pixmap(self._pixmap)
                self._scaled_manager.update_scaled_cache(self.size())

            # event.angleDelta().y() devuelve un valor positivo si se hace scroll hacia arriba (Zoom In)
            delta = -1 if event.angleDelta().y() > 0 else 1
            
            # Pasamos la posición actual del ratón para hacer el zoom hacia allí
            anchor_wx = event.position().x()
            anchor_wy = event.position().y()
            
            self._handle_zoom(delta * self.ZOOM_STEP, anchor_wx, anchor_wy)
            event.accept()
        else:
            super().wheelEvent(event)

    # ---------- Acceso a datos
    def get_points(self) -> np.ndarray:
        return self._point_manager.get_points()

    def reset_points(self) -> None:
        self._point_manager.reset()
        self.update()

    def _confirm_selection(self) -> None:
        """
        Centraliza la lógica de confirmación (Principio DRY).
        Valida que existan 4 puntos, emite la señal hacia main.py y limpia el estado del UI.
        """
        ordered = self._point_manager.finalize_if_full()
        if ordered is not None:
            # Delega a main.py
            self.fourPointsSelected.emit(ordered)
            
            # Restaurar el estado de la interfaz
            self._mouse_in_img = False
            self.unsetCursor()
            self.update()

    def unload_image(self) -> None:
        """Descarga la imagen actual y restaura el widget al estado inicial.
        - Limpia `self.cv_image`, `self._pixmap` y la caché escalada.
        - Limpia `self.points_img`, desactiva la lupa y el seguimiento del cursor.
        - Fuerza un repintado para mostrar el mensaje 'Carga una imagen'.
        """
        self.cv_image = None
        self._pixmap = None
        self._scaled_manager.set_pixmap(None)

        self._point_manager.reset()
        self._mouse_in_img = False
        self.unsetCursor()

        # Limpiamos las variables del HUD de la memoria
        self.hud_filename = ""
        self.hud_progress = ""
        self.hud_colorspace = ""
        # no hay pantalla de inicio embebida en el canvas (orquestada por MainWindow)
        self.update()

    # ---------- Señales para controlar el minimapa y control del zoom
    def _handle_zoom(self, delta_zoom: float, anchor_wx: float, anchor_wy: float) -> None:
        """Aplica la transformación y, si hay cambios, notifica a la UI."""
        changed = self._scaled_manager.apply_zoom(delta_zoom, anchor_wx, anchor_wy, self.size())
        if changed:
            self._notify_minimap()
            self.update() # Forzar repintado del canvas

    def _is_zoomed(self) -> bool:
        """Comprobador de estado limpio con tolerancia de punto flotante."""
        return not math.isclose(self._scaled_manager.zoom_level, 1.0, abs_tol=0.01)

    def _is_sniper_allowed(self) -> bool:
        """Valida las reglas de UX para permitir la activación del Sniper Mode."""
        is_dragging_node = (self.tool_mode == ToolMode.EDITING and self._dragged_point_idx is not None)
        is_dragging_box = (self.tool_mode == ToolMode.BOX_SELECT and self._is_dragging_box)
    
        # Se permite si hay menos de 4 puntos, o si estamos arrastrando un nodo/caja.
        return len(self._point_manager) < 4 or is_dragging_node or is_dragging_box

    def _refresh_cursor_state(self) -> None:
        """Garantiza que el ratón nativo se oculta o muestra estrictamente."""
        if not self._mouse_in_img or self._is_zoomed():
            if self.cursor().shape() == QtCore.Qt.CursorShape.BlankCursor:
                self.unsetCursor()
            return

        is_dragging_node = (self.tool_mode == ToolMode.EDITING and self._dragged_point_idx is not None)
        is_dragging_box = (self.tool_mode == ToolMode.BOX_SELECT and self._is_dragging_box)
        four_points_placed = (len(self._point_manager) == 4)

        # El mouse original de Windows solo aparecera cuando se hayan colocado los 4 puntos y no este encima de un punto
        if four_points_placed and not is_dragging_node and not is_dragging_box:
            if self._hovered_point_idx is not None:
                # ESTADO HOVER: Ocultamos ratón nativo
                if self.cursor().shape() != QtCore.Qt.CursorShape.BlankCursor:
                    self.setCursor(QtCore.Qt.CursorShape.BlankCursor)
            else:
                # 4 PUNTOS, ÁREA LIBRE: Mostramos ratón original
                if self.cursor().shape() == QtCore.Qt.CursorShape.BlankCursor:
                    self.unsetCursor()
        else:
            # ESTADO CREACIÓN O ARRASTRE (Nodos o Caja): Ocultamos el ratón nativo
            if self.cursor().shape() != QtCore.Qt.CursorShape.BlankCursor:
                self.setCursor(QtCore.Qt.CursorShape.BlankCursor)

    def _smooth_reset_zoom(self):
        """Devuelve el Canvas al 100% con una interpolación suave de 200ms."""
        if not self._is_zoomed(): return
        
        self.zoom_anim = QtCore.QVariantAnimation(self)
        self.zoom_anim.setDuration(200) # 200ms para un paneo suave
        self.zoom_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutQuad)
        
        start_zoom = self._scaled_manager.zoom_level
        start_px = self._scaled_manager.pan_x
        start_py = self._scaled_manager.pan_y
        
        def animate(progress):
            # Interpola los valores desde el estado actual hacia 1.0 y 0.0
            self._scaled_manager.zoom_level = start_zoom + (1.0 - start_zoom) * progress
            self._scaled_manager.pan_x = start_px + (0.0 - start_px) * progress
            self._scaled_manager.pan_y = start_py + (0.0 - start_py) * progress
            
            self._scaled_manager.update_scaled_cache(self.size())
            self._notify_minimap()
            self.update()

        def on_finished():
            self._scaled_manager.zoom_level = 1.0
            self._scaled_manager.pan_x = 0.0
            self._scaled_manager.pan_y = 0.0
            self._scaled_manager.update_scaled_cache(self.size())
            self._notify_minimap()
            self.update()
            
        self.zoom_anim.valueChanged.connect(animate)
        self.zoom_anim.setStartValue(0.0)
        self.zoom_anim.setEndValue(1.0)
        self.zoom_anim.start()

    def _notify_minimap(self) -> None:
        """Extrae el estado actual del escalado y se lo envía al radar."""
        scaled_pixmap, left, top = self._scaled_manager.get_scaled_and_offset()
        if scaled_pixmap:
            self.minimap.update_state(
                zoom=self._scaled_manager.zoom_level,
                left=left,
                top=top,
                scaled_w=scaled_pixmap.width(),
                scaled_h=scaled_pixmap.height(),
                canvas_w=self.width(),
                canvas_h=self.height()
            )

    def _pan_view(self, dx: float, dy: float) -> None:
        """Desplaza la visualización (paneo) por teclado cuando el zoom está activo."""
        if not self._is_zoomed():
            return
        
        # Desplazamos la coordenada de paneo en píxeles
        self._scaled_manager.pan_x += dx
        self._scaled_manager.pan_y += dy
        
        self._scaled_manager.update_scaled_cache(self.size())
        self._notify_minimap()
        self.update()

    # ---------- Pintado
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        # Verificacion rapida por si inhabilitaron el magnifier estando activado
        if not self.config_manager.get("enable_magnifier"):
            self._magnifier_enabled = False

        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0))

        scaled, left, top = self._scaled_pixmap_and_offset()
        if scaled is None:
            painter.end()
            return

        painter.drawPixmap(left, top, scaled)
        # dibujar crucetas rojas finas (sin numeración)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        pen = QtGui.QPen(self.cross_color)
        pen.setWidth(self.cross_width)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        # líneas punteadas de referencia (conectan puntos y con el cursor)
        dash_pen = QtGui.QPen(self.line_color)
        dash_pen.setStyle(QtCore.Qt.PenStyle.DashLine)
        dash_pen.setWidth(1)
        dash_pen.setCosmetic(True)

        # Dibujar conexiones entre puntos (ordenadas)
        if len(self._point_manager) >= 2:
            painter.setPen(dash_pen)
            prev_w = None
            prev_h = None
            for (ix, iy) in self._point_manager.points:
                wcoords = self.image_to_widget_coords(ix, iy)
                if wcoords is None:
                    continue
                wx, wy = wcoords
                if prev_w is not None:
                    painter.drawLine(prev_w, prev_h, wx, wy)
                prev_w, prev_h = wx, wy
            # Efecto visual adicional cuando hay 4 puntos: conectar 1-3, 1-4 y 2-4
            if len(self._point_manager) == 4:
                w0 = self.image_to_widget_coords(*self._point_manager.points[0])
                w1 = self.image_to_widget_coords(*self._point_manager.points[1])
                w2 = self.image_to_widget_coords(*self._point_manager.points[2])
                w3 = self.image_to_widget_coords(*self._point_manager.points[3])
                if w0 is not None and w2 is not None:
                    painter.drawLine(w0[0], w0[1], w2[0], w2[1])
                if w0 is not None and w3 is not None:
                    painter.drawLine(w0[0], w0[1], w3[0], w3[1])
                if w1 is not None and w3 is not None:
                    painter.drawLine(w1[0], w1[1], w3[0], w3[1])

        # Si NO estamos en zoom, dibujamos los cursores dinámicos y la Lupa
        if not self._is_zoomed():
            # Si hay cursor sobre la imagen, dibujar líneas hacia el cursor
            if self._mouse_in_img and self._point_manager.points and len(self._point_manager) < 4:
                painter.setPen(dash_pen)
                for (ix, iy) in self._point_manager.points:
                    wcoords = self.image_to_widget_coords(ix, iy)
                    if wcoords:
                        painter.drawLine(QtCore.QPointF(wcoords[0], wcoords[1]), QtCore.QPointF(self._mouse_wx, self._mouse_wy))

            # DIBUJADO DEL RECUADRO TEMPORAL (DIVULGACIÓN PROGRESIVA)
            if self.tool_mode == ToolMode.BOX_SELECT and self._box_start_w and self._box_current_w:
                box_pen = QtGui.QPen(self.cross_color)
                box_pen.setStyle(QtCore.Qt.PenStyle.DashLine)
                box_pen.setWidth(2)
                painter.setPen(box_pen)
                painter.setBrush(QtGui.QColor(12, 140, 233, 40)) # Fondo semi-transparente
                
                x = min(self._box_start_w[0], self._box_current_w[0])
                y = min(self._box_start_w[1], self._box_current_w[1])
                w = abs(self._box_start_w[0] - self._box_current_w[0])
                h = abs(self._box_start_w[1] - self._box_current_w[1])
                painter.drawRect(x, y, w, h)
            
            # Dibujamos los cursores personalizados, para el dibujado tradicional y otro para cuando se modifican los puntos
            # Evaluamos si el usuario está arrastrando un nodo
            is_dragging_node = (self.tool_mode == ToolMode.EDITING and self._dragged_point_idx is not None)
            four_points_placed = (len(self._point_manager) == 4)

            if self._mouse_in_img and not is_dragging_node:
                painter.setPen(pen)
                cx, cy = self._mouse_wx, self._mouse_wy

                if not four_points_placed:
                    # Cursor de Creación (La Cruceta Original)
                    cl = self.cross_len
                    painter.drawLine(QtCore.QPointF(cx - cl, cy), QtCore.QPointF(cx + cl, cy))
                    painter.drawLine(QtCore.QPointF(cx, cy - cl), QtCore.QPointF(cx, cy + cl))

                elif self._hovered_point_idx is not None:
                    # Cursor de Edición (Anillo de Precisión)
                    # Solo se dibuja si esta en hover de algun punto colocado
                    radius = 6.0
                    painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)
                    
                    # Un diminuto punto sólido en el centro exacto para máxima precisión
                    painter.setBrush(QtGui.QColor(12, 140, 233)) # Tu azul neón
                    painter.drawEllipse(QtCore.QPointF(cx, cy), 1.0, 1.0)

            # dibujar crucetas en cada punto
            painter.setPen(pen)
            for (ix, iy) in self._point_manager.points:
                wcoords = self.image_to_widget_coords(ix, iy)
                if wcoords is None:
                    continue
                wx, wy = wcoords
                cl = self.cross_len
                painter.drawLine(wx - cl, wy, wx + cl, wy)
                painter.drawLine(wx, wy - cl, wx, wy + cl)

            # Lupa de enfoque: delegar en el MagnifierTool
            if self._magnifier_enabled and self._mouse_in_img and self.cv_image is not None:
                # obtener la posición de widget a usar (sniper virtual o real)
                wfx, wfy = self._sniper.get_current_widget_pos(None, self)
                img_pt = self.widget_to_image_coords(wfx, wfy)
                if img_pt is not None:
                    # pasar posición widget en enteros para el overlay
                    widget_pos = (int(round(wfx)), int(round(wfy)))
                    # delegar dibujo a la herramienta
                    self._magnifier.draw(
                        painter, 
                        widget_pos, 
                        img_pt, 
                        self.cv_image, 
                        widget=self, 
                        cross_len=self.cross_len*4,
                        cross_color=self.cross_color,
                        cross_width=self.cross_width,
                        border_color=self.border_color
                        )
        # Aviso de que se encuentra dentro del modo zoom
        else:
            zoom_warning = "ZOOM ACTIVADO"
            
            painter.setPen(QtGui.QColor(255, 255, 255))
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            
            # Calcular ancho del texto para centrarlo
            fm = QtGui.QFontMetrics(font)
            text_width = fm.horizontalAdvance(zoom_warning)
            text_x = (self.width() - text_width) // 2
            text_y = 35 # Margen superior
            
            # Fondo del texto (Pastilla)
            bg_rect = QtCore.QRectF(text_x - 15, text_y - 20, text_width + 30, 30)
            painter.setBrush(QtGui.QColor(12, 140, 233, 200)) # Azul primario con transparencia
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bg_rect, 15, 15)
            
            # Dibujar texto
            painter.setPen(QtGui.QColor(255, 255, 255))
            painter.drawText(text_x, text_y, zoom_warning)

        #informacion del HUD
        if self.hud_filename:
            # Fondo semi-transparente con borde
            hud_border_color = QtGui.QColor(self.cross_color)
            hud_border_color.setAlpha(130)
            hud_border_width = 2
            pen_hud = QtGui.QPen(hud_border_color)
            pen_hud.setWidth(hud_border_width)
            pen_hud.setJoinStyle(QtCore.Qt.PenJoinStyle.MiterJoin)
            painter.setPen(pen_hud)
            painter.setBrush(QtGui.QColor(55, 55, 55, 130))
            painter.drawRoundedRect(15, 15, 290, 85, 12, 12) # (x, y, width, height, radius_x, radius_y)
            
            # Textos en blanco
            painter.setPen(QtGui.QColor(255, 255, 255))
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            
            painter.drawText(25, 35, f"{self.hud_filename}")
            
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(25, 60, f"{self.hud_colorspace}")
            painter.drawText(25, 85, f"Progreso: {self.hud_progress}")

        painter.end()

if __name__ == "__main__":
    # pequeño sanity-check si se ejecuta como script
    import sys

    app = QtWidgets.QApplication(sys.argv)
    w = ImageCanvas()
    w.resize(800, 600)
    w.show()
    sys.exit(app.exec())
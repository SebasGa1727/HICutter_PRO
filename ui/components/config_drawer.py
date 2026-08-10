from PyQt6 import QtCore, QtGui, QtWidgets
from utils.canvas_config_manager import CanvasConfigManager

class ConfigTab(QtWidgets.QWidget):
    """
    La pestaña diminuta que sobresale a la derecha. 
    Dibuja el texto de abajo hacia arriba.
    """
    clicked = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 120)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.bg_color = QtGui.QColor(12, 140, 233, 153) 

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
            
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        
        # Dibujar fondo con esquinas redondeadas a la izquierda
        path = QtGui.QPainterPath()
        path.addRoundedRect(0, 0, self.width() + 10, self.height(), 10, 10) # +10 para ocultar el redondeo derecho
        painter.fillPath(path, self.bg_color)
        
        # Rotar el sistema de coordenadas para dibujar de abajo hacia arriba
        painter.setPen(QtCore.Qt.GlobalColor.white)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        
        painter.translate(0, self.height())
        painter.rotate(-90)
        
        # Tras rotar, el ancho y alto se invierten lógicamente para el dibujado
        rect = QtCore.QRectF(0, 0, self.height(), self.width())
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, "CONFIGURACIÓN")
        painter.end()


class ConfigDrawerOverlay(QtWidgets.QWidget):
    """
    Contenedor principal superpuesto al Canvas.
    Maneja el oscurecimiento del fondo y la animación del menú.
    """
    def __init__(self, parent, config_manager: CanvasConfigManager):
        # Es hijo del Canvas, por lo que flotará sobre él
        super().__init__(parent)
        self.config = config_manager
        self.is_open = False

        # Evitamos robar foco
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.drawer_width = 250
        
        # 1. Capa de oscurecimiento (Modal Background)
        self.dim_bg = QtWidgets.QWidget(self)
        self.dim_bg.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        self.dim_bg.hide() # Oculto por defecto
        
        # 2. El cajón de opciones (Drawer)
        self.drawer = QtWidgets.QFrame(self)
        self.drawer.setStyleSheet("background-color: #1e1e1e; border-left: 1px solid #0c8ce9;")
        self.drawer.setFixedWidth(self.drawer_width)
        
        # 3. La pestaña externa
        self.tab = ConfigTab(self)
        self.tab.clicked.connect(self.toggle_drawer)
        
        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self):
        """Construye los botones y la divulgación progresiva con Tooltips"""
        layout = QtWidgets.QVBoxLayout(self.drawer)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Título y botón de cerrado (Flecha)
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Herramientas")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        
        close_btn = QtWidgets.QPushButton(">")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("background-color: transparent; color: white; font-weight: bold; border: 1px solid white; border-radius: 15px;")
        close_btn.clicked.connect(self.close_drawer)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        layout.addLayout(header_layout)
        
        layout.addSpacing(20)

        # Helper para crear opciones consistentes
        def create_toggle(label_text, config_key, tooltip_text):
            chk = QtWidgets.QCheckBox(label_text)
            chk.setStyleSheet("color: white; padding: 5px;")
            chk.setChecked(self.config.get(config_key))
            chk.setToolTip(tooltip_text)
            chk.toggled.connect(lambda checked, k=config_key: self.config.set(k, checked))
            layout.addWidget(chk)
            return chk

        # Creación de las 4 opciones solicitadas
        create_toggle("Modo Sniper", "enable_sniper", "Mantén 'Shift' para reducir la sensibilidad.")
        create_toggle("Lupa Inmersiva", "enable_magnifier", "Click Derecho para desplegar una ventana de aumento sobre el área de interés.")
        create_toggle("Selección por Recuadro", "enable_drag_drop", "Seleccion por arrastre.")
        create_toggle("Doble Clic para Confirmar", "enable_double_click", "Continuar con doble click izquierdo.")
        
        layout.addStretch()

    def _setup_animation(self):
        self.anim = QtCore.QPropertyAnimation(self.drawer, b"geometry")
        self.anim.setDuration(300) # 300 milisegundos
        self.anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic) # Movimiento suave de Desaceleración
        
        # Animación de la pestaña acompañando al cajón
        self.tab_anim = QtCore.QPropertyAnimation(self.tab, b"geometry")
        self.tab_anim.setDuration(300)
        self.tab_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

    def toggle_drawer(self):
        if self.is_open:
            self.close_drawer()
        else:
            self.open_drawer()

    def open_drawer(self):
        if self.is_open: return
        self.is_open = True
        self.dim_bg.show()
        
        # Posición final: El cajón pegado a la derecha
        target_drawer_rect = QtCore.QRect(self.width() - self.drawer_width, 0, self.drawer_width, self.height())
        # La pestaña se mueve a la izquierda empujada por el cajón
        target_tab_rect = QtCore.QRect(self.width() - self.drawer_width - self.tab.width(), (self.height() - self.tab.height()) // 2, self.tab.width(), self.tab.height())
        
        self.anim.setEndValue(target_drawer_rect)
        self.tab_anim.setEndValue(target_tab_rect)
        self.anim.start()
        self.tab_anim.start()

    def close_drawer(self):
        if not self.is_open: return
        self.is_open = False
        self.dim_bg.hide()
        
        # Posición final: El cajón fuera de la pantalla hacia la derecha
        target_drawer_rect = QtCore.QRect(self.width(), 0, self.drawer_width, self.height())
        # La pestaña regresa al borde derecho
        target_tab_rect = QtCore.QRect(self.width() - self.tab.width(), (self.height() - self.tab.height()) // 2, self.tab.width(), self.tab.height())
        
        self.anim.setEndValue(target_drawer_rect)
        self.tab_anim.setEndValue(target_tab_rect)
        self.anim.start()
        self.tab_anim.start()

    def resizeEvent(self, event):
        """Mantiene los elementos en su sitio si la ventana de la App cambia de tamaño."""
        super().resizeEvent(event)
        self.dim_bg.setFixedSize(self.size())
        
        if not self.is_open:
            self.drawer.setGeometry(self.width(), 0, self.drawer_width, self.height())
            self.tab.setGeometry(self.width() - self.tab.width(), (self.height() - self.tab.height()) // 2, self.tab.width(), self.tab.height())
        else:
            self.drawer.setGeometry(self.width() - self.drawer_width, 0, self.drawer_width, self.height())
            self.tab.setGeometry(self.width() - self.drawer_width - self.tab.width(), (self.height() - self.tab.height()) // 2, self.tab.width(), self.tab.height())

    def mouseMoveEvent(self, event):
        event.ignore() # Atraviesa el overlay y llega al Canvas

    def mousePressEvent(self, event):
        """Si el panel está abierto y el usuario hace clic en el área oscurecida, se cierra."""
        if self.is_open:
            self.close_drawer()
        else:
            # Si está cerrado, dejamos que el clic pase a través de este overlay hacia el Canvas principal
            event.ignore()
    
    def mouseReleaseEvent(self, event):
        event.ignore()

    def mouseDoubleClickEvent(self, event):
        event.ignore()

    def wheelEvent(self, event):
        event.ignore()
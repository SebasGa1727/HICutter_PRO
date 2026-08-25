import sys
import os
from typing import Optional, List, Tuple

# TRUCO PARA MOCK: Agregar la raíz del proyecto al PATH para ejecuciones aisladas
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from PyQt6 import QtCore, QtGui, QtWidgets
from ui.components.neon_widgets import NeonProxyStyle, CustomPushButton
from utils.asset_manager import assets
from utils.logger import setup_logger

logger = setup_logger(__name__)

BUTTON_MAXIMUM_HEIGHT = 60

class LandingCustomPushButton(CustomPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("landing_view", "botones")


class HoverSplitFrame(QtWidgets.QFrame):
    """
    Componente contenedor que actúa como un botón unificado pero, al recibir 
    el evento de entrada del mouse, revela suavemente múltiples sub-botones.
    """
    def __init__(self, main_title: str, sub_buttons: List[Tuple[str, callable]], parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("HoverSplitFrame")
        
        # implementamos QStackedWidget para poder sobreponer 2 widgets sin interacciones raras o confusas
        self.stacked_widget = QtWidgets.QStackedWidget(self)
        self.stacked_widget.setObjectName("HoverStackedWidget")
        
        # Primer gran "boton"
        self.main_btn = LandingCustomPushButton(main_title)
        # Dejamos pasar los "clicks" para que no se interponga con los botones inferiores
        self.main_btn.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # Contenedor de los botones internos
        self.hover_container = QtWidgets.QFrame()
        self.hover_container.setObjectName("HoverContainer")
        self.hover_layout = QtWidgets.QHBoxLayout(self.hover_container)
        self.hover_layout.setContentsMargins(0, 0, 0, 0)
        self.hover_layout.setSpacing(5) # Separación armónica entre sub-botones
        
        # Inyección de dependencias para la creación de sub-botones
        for btn_text, callback in sub_buttons:
            btn = LandingCustomPushButton(btn_text)
            btn.setFixedHeight(BUTTON_MAXIMUM_HEIGHT)
            btn.clicked.connect(callback)
            self.hover_layout.addWidget(btn, stretch=1)

        # Agregamos los elementos al stackedWidget
        self.stacked_widget.addWidget(self.main_btn)
        self.stacked_widget.addWidget(self.hover_container)
        
        # Encapsulación en el layout del componente
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stacked_widget)

        self._apply_structural_transparency()

    def _apply_structural_transparency(self) -> None:
        """
        Sobrescribe la herencia del theme.qss aislando los contenedores.
        """
        transparent_css = """
            #HoverSplitFrame, #HoverStackedWidget, #HoverContainer {
                background-color: transparent;
                border: none;
            }"""
        self.setStyleSheet(transparent_css)

    def enterEvent(self, event: QtGui.QEnterEvent) -> None:
        """Intercepta la entrada del cursor al área de bounding box del widget."""
        self.stacked_widget.setCurrentIndex(1)
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        """Restaura el estado al salir del área total del frame."""
        self.stacked_widget.setCurrentIndex(0)
        super().leaveEvent(event)


class LandingView(QtWidgets.QWidget):
    """
    Vista de bienvenida.
    Divide el viewport en dos proporciones equitativas para balance cognitivo.
    """
    requestConverter = QtCore.pyqtSignal()
    requestLoadImage = QtCore.pyqtSignal()
    requestLoadBatch = QtCore.pyqtSignal()
    requestLoadAI = QtCore.pyqtSignal()
    requestCreatePDF = QtCore.pyqtSignal()
    requestEditPDF = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Paneles semánticos
        self.left_panel = QtWidgets.QFrame()
        self.left_panel.setProperty("landing_view", "izquierda")

        self.right_panel = QtWidgets.QFrame()
        self.right_panel.setProperty("landing_view", "derecha")
        
        self.main_layout.addWidget(self.left_panel, stretch=1)
        self.main_layout.addWidget(self.right_panel, stretch=1)

        self._setup_left_panel()
        self._setup_right_panel()

    def _setup_left_panel(self) -> None:
        """Construye el componente de identidad visual (Logo)."""
        layout = QtWidgets.QVBoxLayout(self.left_panel)
        
        self.logo_label = QtWidgets.QLabel()
        self.logo_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        
        # Obtenemos el logo ya escalado y cacheado desde el AssetManager
        pixmap = assets.get_scaled_pixmap("hicutter_full_black.png", 650, 650)
        
        if not pixmap.isNull():
            self.logo_label.setPixmap(pixmap)
            self.logo_label.setMaximumHeight(650)
        else:
            # Fallback seguro en caso de que borren el archivo
            self.logo_label.setText("LOGO HICUTTER")
            self.logo_label.setStyleSheet("color: #555; font-size: 24pt; font-weight: bold;")

        sub_title = QtWidgets.QLabel('"Optimiza tu trabajo, preserva la historia"')
        sub_title.setProperty("landing_view", "subtitulo")

        footer_credits = QtWidgets.QLabel("HICutter - Historical Image Cutter by SGV.dev")

        # Armado general
        layout.addStretch(2)
        layout.addWidget(self.logo_label)
        layout.addWidget(sub_title, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(3)
        layout.addWidget(footer_credits, alignment= QtCore.Qt.AlignmentFlag.AlignHCenter)

    def _setup_right_panel(self) -> None:
        """Construye el panel de iteración del usuario."""
        layout = QtWidgets.QVBoxLayout(self.right_panel)
        layout.setContentsMargins(40, 40, 60, 40)

        # --- Convertidor/Organizador ---
        btn_organize = LandingCustomPushButton("CONVERTIDOR/ORGANIZADOR")
        btn_organize.clicked.connect(self.requestConverter.emit)
        group1 = self._create_action_group(
            btn_organize, 
            "Convierte archivos RAW o TIF y organiza tu estructura de carpetas"
        )

        # --- Procesamiento de Imágenes ---
        sub_buttons_2 = [
            ("INDIVIDUAL", self.requestLoadImage.emit),
            ("LOTE", self.requestLoadBatch.emit),
            ("IA (beta)", self.requestLoadAI.emit)
        ]
        btn_process = HoverSplitFrame("PROCESAMIENTO DE IMAGENES", sub_buttons_2)
        group2 = self._create_action_group(
            btn_process, 
            "Procesa tus imagenes en modo Individual, Lote o con IA (beta)"
        )

        # --- Convertidor PDF ---
        sub_buttons_3 = [
            ("CREAR", self.requestCreatePDF.emit),
            ("Proximamente", self.requestEditPDF.emit)
        ]
        btn_pdf = HoverSplitFrame("CONVERTIDOR PDF", sub_buttons_3)
        group3 = self._create_action_group(
            btn_pdf, 
            "Crea documentos PDF a partir de imagenes (Proximamente, modifica)"
        )
        # Armado general
        layout.addStretch(1)
        layout.addLayout(group1)
        layout.addStretch(1)
        layout.addLayout(group2)
        layout.addStretch(1)
        layout.addLayout(group3)
        layout.addStretch(1)

    def _create_action_group(self, widget: QtWidgets.QWidget, description_text: str) -> QtWidgets.QVBoxLayout:
        """
        Ensamblador de grupos lógicos (Acción + Descripción).
        """
        group_layout = QtWidgets.QVBoxLayout()
        group_layout.setSpacing(8)
        group_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        
        # Dimensiones para mantener coherencia en la interacción
        widget.setMaximumWidth(500)
        widget.setFixedHeight(BUTTON_MAXIMUM_HEIGHT)
        
        desc_label = QtWidgets.QLabel(description_text)
        desc_label.setProperty("landing_view", "descripcion")
        desc_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        group_layout.addWidget(widget)
        group_layout.addWidget(desc_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        
        return group_layout

if __name__ == "__main__":
    def load_global_stylesheet(app: QtWidgets.QApplication):
        try:
            with open("resources/theme.qss", "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        except FileNotFoundError:
            pass
            
    app = QtWidgets.QApplication(sys.argv)
    base_style = QtWidgets.QStyleFactory.create("Fusion")
    app.setStyle(NeonProxyStyle(base_style))
    load_global_stylesheet(app)
    assets.init_graphic_resources()
    
    window = LandingView()
    window.resize(1200, 750)
    window.setWindowTitle("HICutter PRO")
    window.showMaximized()
    sys.exit(app.exec())
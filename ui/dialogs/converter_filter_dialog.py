import cv2
import numpy as np
from PyQt6 import QtWidgets, QtCore, QtGui
from utils.logger import setup_logger

logger = setup_logger(__name__)

class FilterDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, initial_image_path: str = None):
        super().__init__(parent)
        self.setWindowTitle("Filtros y Ajustes Visuales")
        self.resize(1000, 600)
        
        # Ocultar botón de ayuda nativo de Windows y fijar como ventana modal
        self.setWindowFlag(QtCore.Qt.WindowType.WindowContextHelpButtonHint, False)
        
        # --- Variables de Estado ---
        self.original_image: np.ndarray = None # Imagen base sin alterar
        self.current_image_path = initial_image_path
        
        # --- Lógica de Retardo (Cooldown de 150ms) ---
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150) # 150ms de cooldown
        self._preview_timer.timeout.connect(self._apply_filters_and_preview)

        self._setup_ui()
        self._load_initial_image()

    def _setup_ui(self):
        # DISEÑO: 2 Paneles (Izquierdo: Controles, Derecho: Previsualización)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        
        # --- PANEL IZQUIERDO: Controles ---
        self.left_panel = QtWidgets.QFrame()
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        left_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        
        lbl_titulo_controles = QtWidgets.QLabel("Ajustes Rápidos")
        lbl_titulo_controles.setStyleSheet("font-weight: bold; font-size: 16px;")
        left_layout.addWidget(lbl_titulo_controles)
        
        # Ejemplo: Slider de Brillo
        layout_brillo = QtWidgets.QHBoxLayout()
        lbl_brillo = QtWidgets.QLabel("Brillo:")
        self.slider_brillo = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider_brillo.setRange(-100, 100) # Rango de modificación
        self.slider_brillo.setValue(0)
        # Cuando el slider cambia, disparamos la petición de preview (reiniciando el cooldown)
        self.slider_brillo.valueChanged.connect(self._request_preview_update) 
        
        layout_brillo.addWidget(lbl_brillo)
        layout_brillo.addWidget(self.slider_brillo)
        left_layout.addLayout(layout_brillo)
        
        # Aquí puedes agregar más sliders (Contraste, Temperatura, etc.)
        # ...
        
        # --- PANEL DERECHO: Previsualización ---
        self.right_panel = QtWidgets.QFrame()
        right_layout = QtWidgets.QVBoxLayout(self.right_panel)
        
        self.preview_label = QtWidgets.QLabel("No hay imagen disponible")
        self.preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #171717; border: 1px solid #555;")
        
        # Esto hace que la imagen se adapte al label si es muy grande
        self.preview_label.setScaledContents(False) 
        
        right_layout.addWidget(self.preview_label, stretch=1)
        
        # Ensamblar Splitter
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 1) # Controles (Más angosto)
        self.splitter.setStretchFactor(1, 3) # Imagen (Más ancho)
        
        # Botones inferiores (Aceptar/Cancelar)
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_cancel = QtWidgets.QPushButton("Cancelar")
        self.btn_accept = QtWidgets.QPushButton("Aplicar Filtros")
        
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_accept.clicked.connect(self.accept)
        
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_accept)

        # Layout Principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.splitter, stretch=1)
        main_layout.addLayout(btn_layout)

    def _load_initial_image(self):
        """Carga la imagen base si se proporcionó una ruta."""
        if not self.current_image_path:
            return
            
        try:
            self.original_image = cv2.imread(self.current_image_path)
            if self.original_image is not None:
                # Mostramos la imagen original al abrir
                self._display_image(self.original_image)
        except Exception as e:
            logger.error(f"No se pudo cargar la imagen de preview: {e}")

    def _request_preview_update(self):
        """Se llama cada vez que el usuario mueve un control. 
        Reinicia el cooldown para evitar crasheos por sobreprocesamiento."""
        self._preview_timer.start()

    def _apply_filters_and_preview(self):
        """Aplica la matemática del filtro y actualiza el Qlabel. 
        Solo se ejecuta tras 150ms de inactividad del usuario."""
        if self.original_image is None:
            return
            
        # 1. Obtener valores de la interfaz
        brillo_val = self.slider_brillo.value()
        
        # 2. Hacer una copia de la original para no destruir los datos
        img_modificada = self.original_image.copy()
        
        # 3. MÁGIA MATEMÁTICA AQUÍ (Ejemplo básico de brillo)
        # Esto debes cambiarlo por algoritmos eficientes (LUTs o conversiones HSV)
        if brillo_val != 0:
            pass # Lógica de OpenCV para brillo
            
        # 4. Mostrar el resultado
        self._display_image(img_modificada)

    def _display_image(self, cv_img: np.ndarray):
        """Convierte la matriz BGR de OpenCV a QPixmap para la interfaz."""
        # TODO: Implementar redimensionado (cv2.resize) de la matriz antes 
        # de convertir a QPixmap para que la previsualización sea ultra rápida.
        pass

    def get_filter_settings(self) -> dict:
        """Devuelve un diccionario con los valores elegidos para que el motor 
        principal los aplique durante el procesamiento en lote."""
        return {
            "brillo": self.slider_brillo.value(),
            # ... otros parámetros
        }
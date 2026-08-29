# TRUCO PARA MOCK: Agregar la raíz del proyecto al PATH para ejecuciones aisladas
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
import cv2
import os
import io
from PIL import Image, ImageOps
import numpy as np
from PyQt6 import QtWidgets, QtCore, QtGui
from utils.icon_map import HICutterIcons
from utils.logger import setup_logger
from utils.asset_manager import assets
from utils.utils import _cv_to_qpixmap
from ui.components.geometry import ScaledPixmapManager
from ui.components.neon_widgets import CustomPushButton, CustomSpinBox

logger = setup_logger(__name__)

class FilterBlockBuilder:
    """Clase constructora que fabrica bloques de filtros"""
    def __init__(self, titulo_bloque: str):
        # Crea la caja principal del bloque
        self.layout_principal = QtWidgets.QVBoxLayout()

        # Crea el frame del titulo
        self.header_frame = QtWidgets.QFrame()
        self.header_frame.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.header_frame.setProperty("interaccion", "hover")

        # Lista de sliders para detectarlos y modificar el color del titulo
        self._sliders = []

        # Crea la caja horizontal del titulo
        header_layout = QtWidgets.QHBoxLayout(self.header_frame)
        
        # Crea el título general y lo añade a la caja
        self.lbl_titulo = QtWidgets.QLabel(titulo_bloque.upper())
        self.lbl_titulo.setProperty("converter_filter_dialog", "filter_title")
        self.lbl_titulo.setProperty("estado", "normal")

        # Creamos el boton de tipo flecha
        btn_toggle = QtWidgets.QPushButton(HICutterIcons.ARROW_DOWN)
        btn_toggle.setProperty("estilo", "icono")
        btn_toggle.setProperty("variante", "icono_flecha")
        btn_toggle.setFixedSize(30, 30)
        btn_toggle.setCheckable(True)
        btn_toggle.setChecked(False)
        btn_toggle.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        header_layout.addWidget(self.lbl_titulo)
        header_layout.addStretch(1)
        header_layout.addWidget(btn_toggle)

        self.layout_principal.addWidget(self.header_frame)

        self.body_container = QtWidgets.QFrame()
        self.body_container.setVisible(False)
        self.body_layout = QtWidgets.QVBoxLayout(self.body_container)
        self.body_layout.setContentsMargins(10, 0, 5, 10)

        self.layout_principal.addWidget(self.body_container)

        # cambiamos el estado del boton cuando se levanta el mouse siempre y cuando el click sea el izquierdo
        self.header_frame.mouseReleaseEvent = lambda event: btn_toggle.setChecked(not btn_toggle.isChecked()) if event.button() == QtCore.Qt.MouseButton.LeftButton else None

        def _sync_hover(is_hovered: bool):
            btn_toggle.setProperty("frame_hover", str(is_hovered).lower())
            btn_toggle.style().unpolish(btn_toggle)
            btn_toggle.style().polish(btn_toggle)
        
        self.header_frame.enterEvent = lambda event: _sync_hover(True)
        self.header_frame.leaveEvent = lambda event: _sync_hover(False)

        # Conexion con la funcion para ocultar o mostrar el contenido
        btn_toggle.toggled.connect(
            lambda checked, box=self.body_container, btn=btn_toggle: self._toggle_visibility(checked, box, btn)
        )

    def _toggle_visibility(self, checked: bool, box: QtWidgets.QFrame, btn: QtWidgets.QPushButton):
        '''Metodo para definir visibilidad del contenido de los filtros'''
        box.setVisible(checked)
        btn.setText(HICutterIcons.ARROW_UP if checked else HICutterIcons.ARROW_DOWN)

    def build(self) -> QtWidgets.QVBoxLayout:
        """Devuelve el bloque terminado y empaquetado para ponerlo en la ventana."""
        return self.layout_principal
    
    def _verificar_estado_slider(self, *args):
        '''Verifica dinamicamente el estado de sliders para pintar el titulo'''
        # Verificamos si hay un cambio
        was_modified = any(s.value() != 0 for s in self._sliders)
        new_state = "modificado" if was_modified else "normal"

        if self.lbl_titulo.property("estado") != new_state:
            self.lbl_titulo.setProperty("estado", new_state)
            self.lbl_titulo.style().unpolish(self.lbl_titulo)
            self.lbl_titulo.style().polish(self.lbl_titulo)

    def add_control_row(self, nombre_etiqueta: str):
        """Fabrica una fila completa de controles sincronizados y la añade al bloque."""
        
        # Creamos la fila horizontal
        first_row_layout = QtWidgets.QHBoxLayout()

        second_row_layout = QtWidgets.QHBoxLayout()
        
        # Fabricamos las piezas
        lbl = QtWidgets.QLabel(nombre_etiqueta)
        
        slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        slider.setRange(-100, 100)
        slider.setValue(0)
        slider.wheelEvent = lambda event: event.ignore()
        slider.setProperty("nombre_filtro", nombre_etiqueta)
        
        spinbox = CustomSpinBox()
        spinbox.setRange(-100, 100)
        spinbox.setValue(0)
        spinbox.setFixedWidth(34)

        # Conexiones entre slider y spinbox
        slider.valueChanged.connect(spinbox.setValue) #<- El slider actualiza al spinbox
        spinbox.valueChanged.connect(slider.setValue) #<- El spinbox actualiza al slider

        btn_menos = QtWidgets.QPushButton(HICutterIcons.MINUS)
        btn_menos.clicked.connect(spinbox.stepDown)

        btn_mas = QtWidgets.QPushButton(HICutterIcons.PLUS)
        btn_mas.clicked.connect(spinbox.stepUp)

        btn_reset = QtWidgets.QPushButton(HICutterIcons.RESTART)
        btn_reset.clicked.connect(lambda: spinbox.setValue(0)) #<- El botón de reseteo envía un 0 al SpinBox (y este actualizará al Slider)

        # Aplicamos CSS
        for btn in [btn_menos, btn_mas, btn_reset]:
            btn.setProperty("estilo", "icono")
            btn.setFixedSize(18, 18)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        # Metemos las piezas en la caja horizontal
        first_row_layout.addWidget(slider)
        first_row_layout.addSpacing(10)
        first_row_layout.addWidget(btn_reset)

        second_row_layout.addStretch(1)
        second_row_layout.addWidget(btn_menos)
        second_row_layout.addWidget(spinbox)
        second_row_layout.addWidget(btn_mas)
        second_row_layout.addStretch(1)
        second_row_layout.addSpacing(32)

        # Agregamos la conexion para cambiar el color del titulo del filtro
        self._sliders.append(slider)
        slider.valueChanged.connect(self._verificar_estado_slider)
        
        # Añadimos la fila completa a nuestra caja vertical principal
        self.body_layout.addWidget(lbl)
        self.body_layout.addLayout(first_row_layout)
        self.body_layout.addLayout(second_row_layout)
        
        # Devolvemos el slider al programador principal para poder solicitarle informacion de estado despues
        return slider

class FilterDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, initial_image_path: str = None):
        super().__init__(parent)
        self.setWindowTitle("Filtros y Ajustes Visuales")
        self.resize(1000, 660)
        
        # Ocultar botón de ayuda nativo de Windows y fijar como ventana modal
        self.setWindowFlag(QtCore.Qt.WindowType.WindowContextHelpButtonHint, False)
        
        # --- Variables de Estado ---
        self.original_image: np.ndarray = None # Imagen base sin alterar
        self.current_image_path = initial_image_path
        self._scaled_manager = ScaledPixmapManager()

        # --- Lógica de Retardo  ---
        self._preview_timer = QtCore.QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(200) # cooldown
        self._preview_timer.timeout.connect(self._apply_filters_and_preview)

        self._setup_ui()
        self._load_initial_image()

    def _setup_ui(self):
        # DISEÑO: 2 Paneles (Izquierdo: Controles, Derecho: Previsualización)
        top_layout = QtWidgets.QHBoxLayout()
        
        # --- PANEL IZQUIERDO: Controles ---
        # Creamos area de scroll
        self.scroll_area = QtWidgets.QScrollArea(self)
        self.scroll_area.setWidgetResizable(True) #<- Permite que el contenido interno se adapte al ancho
        self.scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame) #<- Elimina bordes dobles nativos
        self.scroll_area.setMinimumWidth(200)
        self.scroll_area.setMaximumWidth(350)

        self.left_panel = QtWidgets.QFrame(self.scroll_area)
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        left_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        
        lbl_titulo_controles = QtWidgets.QLabel("AJUSTES RÁPIDOS")
        lbl_titulo_controles.setStyleSheet("font-weight: bold; font-size: 16px;")
        lbl_titulo_controles.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        
        # --- SLIDERS ---
        # Slider de temperatura
        builder_temperatura = FilterBlockBuilder("Temperatura")
        self.slider_temperatura = builder_temperatura.add_control_row("Frio / Calido")

        # Slider de Exposicion
        builder_exposicion = FilterBlockBuilder("Exposicion")
        self.slider_exposicion = builder_exposicion.add_control_row("Intensidad")

        # Slider de Luz y sombra
        builder_luz_sombra = FilterBlockBuilder("Luz y Sombra")
        self.slider_luz = builder_luz_sombra.add_control_row("luces")
        self.slider_sombra = builder_luz_sombra.add_control_row("Sombras")

        # Slider de Niveles
        builder_niveles = FilterBlockBuilder("Niveles")
        self.slider_nivel_negro = builder_niveles.add_control_row("Negros")
        self.slider_nivel_medio = builder_niveles.add_control_row("Medios")
        self.slider_nivel_blanco = builder_niveles.add_control_row("Blancos")

        # Armado del layuout izquierdo
        left_layout.addWidget(lbl_titulo_controles)
        left_layout.addSpacing(25)
        left_layout.addLayout(builder_temperatura.build())
        left_layout.addSpacing(15)
        left_layout.addLayout(builder_exposicion.build())
        left_layout.addSpacing(15)
        left_layout.addLayout(builder_luz_sombra.build())
        left_layout.addSpacing(15)
        left_layout.addLayout(builder_niveles.build())

        self.scroll_area.setWidget(self.left_panel)

        # Conexion al motor de previsualizacion
        sliders_list = [self.slider_exposicion, self.slider_temperatura, self.slider_luz, self.slider_sombra, 
                       self.slider_nivel_negro, self.slider_nivel_medio, self.slider_nivel_blanco]
        for slider in sliders_list:
            slider.valueChanged.connect(lambda: self._request_preview_update(sliders_list))
        
        # --- PANEL DERECHO: Previsualización ---
        self.right_panel = QtWidgets.QFrame(self)
        self.right_panel.setMinimumWidth(500)
        right_layout = QtWidgets.QVBoxLayout(self.right_panel)
        
        self.preview_label = QtWidgets.QLabel("No hay imagen disponible", self.right_panel)
        self.preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #171717; border: 1px solid #555;")
        self.preview_label.setScaledContents(False)
        self.preview_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)

        # Etiqueta de filtros aplicados
        self.lbl_active_values = QtWidgets.QLabel("Ningún filtro aplicado")
        self.lbl_active_values.setStyleSheet("color: #999; font-size: 9pt; font-style: italic;")
        self.lbl_active_values.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        right_layout.addWidget(self.preview_label, stretch=1)
        right_layout.addSpacing(10)
        right_layout.addWidget(self.lbl_active_values)
        right_layout.addSpacing(10)
        
        # Ensamblar el top layout
        top_layout.addWidget(self.scroll_area, stretch=1)
        top_layout.addWidget(self.right_panel, stretch=2)

        # Botones inferiores (Aceptar/Cancelar)
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_cancel = CustomPushButton("CANCELAR")
        self.btn_cancel.setProperty("estilo", "cancelar")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_accept = CustomPushButton("APLICAR")
        self.btn_accept.setProperty("estilo", "primario")
        self.btn_accept.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_accept)

        # Layout Principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(top_layout, stretch=1)
        main_layout.addLayout(btn_layout)

    def _load_initial_image(self):
        """Carga la imagen base utilizando la tubería matemática exacta del motor de exportación."""
        if not self.current_image_path:
            return
            
        try:
            import io
            from PIL import Image, ImageOps
            
            ext = os.path.splitext(self.current_image_path)[1].lower()
            img_bgr = None

            # RENDERIZADO RAW PRECISO (Sincronizado con converter_engine)
            if ext == '.cr2':
                try:
                    import rawpy
                    with rawpy.imread(self.current_image_path) as raw:
                        # Usamos la MISMA configuración del motor para que la luz sea idéntica,
                        # pero activamos half_size=True para que el diálogo se abra hiper-rápido
                        rgb = raw.postprocess(
                            use_camera_wb=True,
                            no_auto_bright=False, # Sincronizado con el motor
                            half_size=True,       # Truco de velocidad UI (1/4 del tiempo de proceso)
                            demosaic_algorithm=rawpy.DemosaicAlgorithm.LINEAR,
                            output_color=rawpy.ColorSpace.sRGB
                        )
                        # El diálogo trabaja en BGR para sus LUTs
                        img_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                except Exception as e:
                    logger.warning(f"Fallo al renderizar RAW para preview: {e}")

            # 2. CARGA UNIVERSAL PARA TIFF, JPG, PNG
            if img_bgr is None:
                with Image.open(self.current_image_path) as img:
                    img = ImageOps.exif_transpose(img)
                    if img.mode != "RGB": 
                        img = img.convert("RGB")
                    img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

            # 3. GENERACIÓN DEL PROXY EN RAM PARA LA INTERFAZ
            if img_bgr is not None:
                self.original_image = img_bgr
                alto, ancho = self.original_image.shape[:2]
                max_dim = 800
                
                # Escalamos para que los cálculos de sliders en tiempo real sean a 60 FPS
                if max(alto, ancho) > max_dim:
                    escala = max_dim / max(alto, ancho)
                    nuevo_ancho = int(ancho * escala)
                    nuevo_alto = int(alto * escala)
                    self.preview_image_base = cv2.resize(self.original_image, (nuevo_ancho, nuevo_alto), interpolation=cv2.INTER_AREA)
                else:
                    self.preview_image_base = self.original_image.copy()

                # Disparamos la primera previsualización
                self._apply_filters_and_preview()
                
        except Exception as e:
            logger.error(f"No se pudo cargar la imagen de preview: {e}", exc_info=True)
            self.preview_label.setText("Formato no soportado o archivo corrupto")

    def _request_preview_update(self, sliders_list: QtWidgets.QSlider):
        """Se llama cada vez que el usuario mueve un control. 
        Reinicia el cooldown para evitar crasheos por sobreprocesamiento."""
        self._preview_timer.start()

        active_filters = []

        for s in sliders_list:
            value = s.value()
            if value != 0:
                name = s.property("nombre_filtro")
                active_filters.append(f"{name}: {value}")
        
        if active_filters:
            msj = "  |  ".join(active_filters)
            self.lbl_active_values.setText(f"Filtros activos:  {msj}")
        else:
            self.lbl_active_values.setText("Ningún filtro aplicado")

    def _apply_filters_and_preview(self):
        """Aplica la matemática del filtro usando LUTs (Look-Up Tables) para máximo rendimiento."""
        if not hasattr(self, 'preview_image_base') or self.preview_image_base is None:
            return

        settings = self.get_filter_settings()
        
        # Si todos los filtros están en 0, renderizamos directamente el proxy sin hacer matemáticas
        if all(v == 0 for v in settings.values()):
            self._display_image(self.preview_image_base)
            return

        # 1. GENERACIÓN DEL LUT DE 256 VALORES (Calculamos la matemática solo 256 veces)
        x = np.arange(256, dtype=np.float32)
        
        # --- EXPOSICIÓN ---
        expo = settings["exposicion"]
        y = x + (expo * 1.2) # Factor multiplicador sensible
        
        # --- LUZ Y SOMBRA (Máscaras no lineales) ---
        luces = settings["luces"]
        sombras = settings["sombras"]
        
        shadow_mask = (255 - x) / 255.0  # Afecta más cerca del 0
        y += sombras * shadow_mask * 0.8
        
        highlight_mask = x / 255.0       # Afecta más cerca del 255
        y += luces * highlight_mask * 0.8
        
        # --- NIVELES (Contraste extendido) ---
        negros = settings["negros"]
        blancos = settings["blancos"]
        
        if negros != 0 or blancos != 0:
            # Desplazamos el punto negro y el punto blanco
            in_black = max(0, negros)
            in_white = min(255, 255 - blancos)
            if in_white > in_black:
                y = (y - in_black) * (255.0 / (in_white - in_black))

        y = np.clip(y, 0, 255)
        
        # --- TEMPERATURA (Se aplica por canal) ---
        temp = settings["temperatura"]
        
        # Si temp > 0 (Cálido): Sube Rojo, Baja Azul
        # Si temp < 0 (Frío): Baja Rojo, Sube Azul
        lut_b = np.clip(y - (temp * 0.6), 0, 255).astype(np.uint8)
        lut_g = np.clip(y, 0, 255).astype(np.uint8)
        lut_r = np.clip(y + (temp * 0.6), 0, 255).astype(np.uint8)
        
        lut_bgr = np.dstack((lut_b, lut_g, lut_r))

        # 2. APLICACIÓN CIBERNÉTICA DE LUT (Tiempo de ejecución: < 5 ms)
        filtered_img = cv2.LUT(self.preview_image_base, lut_bgr)
        
        # 3. Mostrar el resultado
        self._display_image(filtered_img)

    def _display_image(self, cv_img: np.ndarray):
        """Convierte la matriz BGR de OpenCV a QPixmap usando utilerías y ajusta al Label."""
        try:
            # Reutilizamos la función de tus utilerías o lo generamos nativamente
            rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_img.shape
            bytes_per_line = ch * w
            
            q_img = QtGui.QImage(rgb_img.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(q_img)
            
            # Escalamos el pixmap para que encaje perfectamente en el QLabel sin estirarse
            scaled_pixmap = pixmap.scaled(
                self.preview_label.size(), 
                QtCore.Qt.AspectRatioMode.KeepAspectRatio, 
                QtCore.Qt.TransformationMode.SmoothTransformation
            )
            
            self.preview_label.setPixmap(scaled_pixmap)
        except Exception as e:
            logger.error("Error renderizando miniatura del filtro", exc_info=True)
            self.preview_label.setText("Error al renderizar preview")

    def resizeEvent(self, event):
        """Evento nativo: Si el usuario agranda la ventana, redibujamos para que la imagen crezca."""
        super().resizeEvent(event)
        if hasattr(self, 'preview_image_base'):
            self._apply_filters_and_preview()

    def load_settings(self, settings: dict):
        """Carga la configuración técnica si el usuario seleccionó un nodo que ya tenía filtros aplicados."""
        if not settings:
            return
            
        # Desactivamos temporalmente el timer para que no recalcule mientras seteamos valores
        self._preview_timer.blockSignals(True)
        
        self.slider_temperatura.setValue(settings.get("temperatura", 0))
        self.slider_exposicion.setValue(settings.get("exposicion", 0))
        self.slider_luz.setValue(settings.get("luces", 0))
        self.slider_sombra.setValue(settings.get("sombras", 0))
        self.slider_nivel_negro.setValue(settings.get("negros", 0))
        self.slider_nivel_medio.setValue(settings.get("medios", 0))
        self.slider_nivel_blanco.setValue(settings.get("blancos", 0))
        
        self._preview_timer.blockSignals(False)
        self._apply_filters_and_preview()

    def get_filter_settings(self) -> dict:
        """Devuelve un diccionario limpio con los valores elegidos para registrar en el Sandbox."""
        return {
            "temperatura": self.slider_temperatura.value(),
            "exposicion": self.slider_exposicion.value(),
            "luces": self.slider_luz.value(),
            "sombras": self.slider_sombra.value(),
            "negros": self.slider_nivel_negro.value(),
            "medios": self.slider_nivel_medio.value(),
            "blancos": self.slider_nivel_blanco.value()
        }

# ==========================================
# ENTORNO AISLADO (MOCK ENVIRONMENT)
# ==========================================
def load_global_stylesheet(app: QtWidgets.QApplication):
    """Lee el archivo QSS y lo inyecta a toda la aplicación."""
    try:
        with open("resources/theme.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Advertencia: No se encontró theme.qss")
        
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    load_global_stylesheet(app)

    assets.init_graphic_resources()
    
    test_view = FilterDialog()
    test_view.resize(1200, 800)
    test_view.show()
    
    sys.exit(app.exec())
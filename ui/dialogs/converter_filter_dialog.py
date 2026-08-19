import cv2
import numpy as np
from PyQt6 import QtWidgets, QtCore, QtGui
# TRUCO PARA MOCK: Agregar la raíz del proyecto al PATH para ejecuciones aisladas
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from utils.icon_map import HICutterIcons
from utils.logger import setup_logger
from utils.asset_manager import assets
from utils.utils import _cv_to_qpixmap
from ui.components.geometry import ScaledPixmapManager

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
        
        spinbox = QtWidgets.QSpinBox()
        spinbox.setRange(-100, 100)
        spinbox.setValue(0)
        spinbox.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        spinbox.setFixedWidth(34)
        spinbox.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        spinbox.setCursor(QtCore.Qt.CursorShape.IBeamCursor)

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
        self._preview_timer = QtCore.QTimer()
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
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True) #<- Permite que el contenido interno se adapte al ancho
        self.scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame) #<- Elimina bordes dobles nativos
        self.scroll_area.setMinimumWidth(200)
        self.scroll_area.setMaximumWidth(350)

        self.left_panel = QtWidgets.QFrame()
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
        self.right_panel = QtWidgets.QFrame()
        self.right_panel.setMinimumWidth(500)
        right_layout = QtWidgets.QVBoxLayout(self.right_panel)
        
        self.preview_label = QtWidgets.QLabel("No hay imagen disponible")
        self.preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #171717; border: 1px solid #555;")
        
        # Esto hace que la imagen se adapte al label si es muy grande
        self.preview_label.setScaledContents(False) 

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
        self.btn_cancel = QtWidgets.QPushButton("CANCELAR")
        self.btn_cancel.setProperty("estilo", "cancelar")
        self.btn_cancel.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_accept = QtWidgets.QPushButton("APLICAR")
        self.btn_accept.setProperty("estilo", "primario")
        self.btn_accept.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_accept.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_accept)

        # Layout Principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(top_layout, stretch=1)
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
        """Aplica la matemática del filtro y actualiza el Qlabel. 
        Solo se ejecuta tras 150ms de inactividad del usuario."""
        pass
        #TODO
        # 1. Obtener valores de la interfaz creando el diccionario
        # self.get_filter_settings(values)
        
        # 2. emitir señales con los valores al creador de proxies para que genere el calculo de la imagen
        
        # 3. recibir el calculo y la imagen con los valores efectuados
        
        # 4. Mostrar el resultado

    def _display_image(self, cv_img: np.ndarray):
        """Convierte la matriz BGR de OpenCV a QPixmap para la interfaz."""
        pass

    def get_filter_settings(self) -> dict:
        """Devuelve un diccionario con los valores elegidos para que el motor 
        principal los aplique durante el procesamiento en lote."""
        #TODO
        pass

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
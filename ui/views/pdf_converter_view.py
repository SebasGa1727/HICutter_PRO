import os
import cv2
from utils.pdf_th_config import config_manager
from PyQt6 import QtWidgets, QtCore, QtGui
from ui.components.neon_widgets import NeonSelectionDelegate, CustomComboBox, CustomSpinBox, CustomCheckBox, CustomPushButton
from ui.components.tree_view_components import LocalFilesSearcher, SandboxTreeView
from core.output_pdf_fmt import export_to_pdf
from core.output_fmt import export_image
from utils.logger import setup_logger
from utils.icon_map import HICutterIcons

logger = setup_logger(__name__)

class PDFWorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(int) 
    error = QtCore.pyqtSignal(str)

class PDFWorker(QtCore.QRunnable):
    def __init__(self, batches: dict, base_dir: str, quality: int, dpi: int, avg_width: bool):
        super().__init__()
        self.batches = batches # dict: {"Nombre_Carpeta": [rutas]}
        self.base_dir = base_dir
        self.quality = quality
        self.dpi = dpi
        self.avg_width = avg_width
        self.signals = PDFWorkerSignals()
    
    @QtCore.pyqtSlot()
    def run(self):
        try:
            count = 0
            for pdf_name, paths in self.batches.items():
                if not paths: continue
                out_path = os.path.join(self.base_dir, f"{pdf_name}.pdf")
                export_to_pdf(paths, out_path, self.quality, self.dpi, self.avg_width)
                count += 1
            self.signals.finished.emit(count)
        except Exception as e:
            self.signals.error.emit(str(e))


class THWorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal()

class THWorker(QtCore.QRunnable):
    def __init__(self, first_images: dict, base_dir: str):
        super().__init__()
        self.first_images = first_images  
        self.base_dir = base_dir # Este es el directorio real (ej. C:/Exports/)
        self.signals = THWorkerSignals()
        
    @QtCore.pyqtSlot()
    def run(self):
        try:
            # Leemos la configuración SOLO UNA VEZ para todo el bucle
            fmt_index = config_manager.get("export_th", "format")
            fmt = "jpg" if fmt_index == 0 else "png"
            quality = config_manager.get("export_th", "quality")
            dpi = config_manager.get("export_th", "dpi")
            target_size = config_manager.get("export_th", "size")
            size_side_idx = config_manager.get("export_th", "size_side")
            save_route_idx = config_manager.get("export_th", "save_route")

            # Mapeo de anclas según la UI de PDF Converter
            anchor_map = {0: "longest_edge", 1: "shortest_edge", 2: "square"}
            anchor = anchor_map.get(size_side_idx, "shortest_edge")

            # Si save_route_idx == 1 ("En carpeta a parte"), creamos la subcarpeta
            subfolder = "Thumbnail" if save_route_idx == 1 else None

            # Iteramos y procesamos
            for pdf_name, img_path in self.first_images.items():
                cv_img = cv2.imread(img_path)
                if cv_img is not None:
                    # Usamos la nueva función universal
                    export_image(
                        cv_image=cv_img, 
                        out_dir=self.base_dir, 
                        base_filename=pdf_name, 
                        target_size=target_size, 
                        anchor=anchor, 
                        quality=quality, 
                        dpi=dpi, 
                        fmt=fmt,
                        sufix="_TH", # Le ponemos un sufijo para diferenciarlo del PDF
                        subfolder_name=subfolder
                    )

            self.signals.finished.emit()
        except Exception as e:
            logger.error(f"Error generando TH: {e}", exc_info=True)


class BlockBuilder:
    """Clase constructora de los bloques de configuracion"""
    def __init__(self, header_title: str, is_block_header: bool):
        self.main_layout = QtWidgets.QVBoxLayout()

        # Verificamos si es un bloque nuevo o solo un titulo
        if is_block_header:
            # Creamos un frame clickable que despliega el contenedor
            self.header_frame = QtWidgets.QFrame()
            self.header_frame.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.header_frame.setProperty("interaccion", "hover")

            header_layout = QtWidgets.QHBoxLayout(self.header_frame)
            self.lbl_title = QtWidgets.QLabel(header_title.upper())
            self.lbl_title.setProperty("estilo", "label_form")
            self.lbl_title.setProperty("estado", "normal")

            btn_toggle = QtWidgets.QPushButton(HICutterIcons.ARROW_DOWN)
            btn_toggle.setProperty("estilo", "icono")
            btn_toggle.setProperty("variante", "icono_flecha")
            btn_toggle.setFixedSize(30, 30)
            btn_toggle.setCheckable(True)
            btn_toggle.setChecked(False)
            btn_toggle.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            header_layout.addWidget(self.lbl_title)
            header_layout.addStretch(1)
            header_layout.addWidget(btn_toggle)

            # Armado del contenedor de este bloque
            self.body_container = QtWidgets.QFrame()
            self.body_container.setVisible(False)

            self.body_layout = QtWidgets.QVBoxLayout(self.body_container)
            self.body_layout.setSpacing(10)
            self.body_layout.setContentsMargins(25, 0, 0, 20)

            self.main_layout.addWidget(self.header_frame)
            self.main_layout.addWidget(self.body_container)

            self.header_frame.mouseReleaseEvent = lambda event: btn_toggle.setChecked(not btn_toggle.isChecked()) if event.button() == QtCore.Qt.MouseButton.LeftButton else None

            def _sync_hover(is_hovered: bool):
                btn_toggle.setProperty("frame_hover", str(is_hovered).lower())
                btn_toggle.style().unpolish(btn_toggle)
                btn_toggle.style().polish(btn_toggle)

            self.header_frame.enterEvent = lambda event: _sync_hover(True)
            self.header_frame.leaveEvent = lambda event: _sync_hover(False)

            btn_toggle.toggled.connect(
                lambda checked, box= self.body_container, btn= btn_toggle: self._toggle_visibility(checked, box, btn)
            )

        else:
            lbl_title = QtWidgets.QLabel(header_title.upper())
            lbl_title.setProperty("estilo", "label_form")

            self.body_layout = QtWidgets.QVBoxLayout()
            self.body_layout.setContentsMargins(10, 0, 0, 15)

            self.main_layout.addWidget(lbl_title)
            self.main_layout.addLayout(self.body_layout)

    def _toggle_visibility(self, checked: bool, box: QtWidgets.QFrame, btn: QtWidgets.QPushButton) -> None:
        """Metodo para mostrar u ocultar el contenido de la caja y cambiar el estilo de las flechas"""
        box.setVisible(checked)
        btn.setText(HICutterIcons.ARROW_UP if checked else HICutterIcons.ARROW_DOWN)

    def add_widget(self, widget: QtWidgets.QWidget) -> None:
        self.body_layout.addWidget(widget)

    def add_layout(self, layout: QtWidgets.QLayout) -> None:
        self.body_layout.addLayout(layout)

    def add_form(self, label_list: list, field_list: list) -> None:
        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        if len(label_list) == len(field_list):
            for label, field in zip(label_list, field_list):
                form.addRow(label, field)
            self.body_layout.addLayout(form)

    def build(self) -> QtWidgets.QLayout:
        return self.main_layout


class ExportConfigPanel(QtWidgets.QScrollArea):
    """Componente aislado para la configuración de exportación. Protege el encapsulamiento de datos."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setMinimumWidth(350)
        self.setMaximumWidth(390)
        
        self.right_panel = QtWidgets.QFrame()
        right_layout = QtWidgets.QVBoxLayout(self.right_panel)
        right_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        
        # Opciones de Guardado
        self.builder_save_options = BlockBuilder("Opciones de guardado", is_block_header=True)
        
        # Checkbox maestro para el modo manual
        self.check_manual_path = CustomCheckBox("SELECCIONAR RUTA MANUALMENTE")
        
        # Contenedor A: Modo Tradicional (Comboboxes)
        self.container_traditional = QtWidgets.QWidget()
        layout_traditional = QtWidgets.QVBoxLayout(self.container_traditional)
        layout_traditional.setContentsMargins(0, 0, 0, 0)
        
        self.save_combo = CustomComboBox()
        self.save_combo.addItems(["Carpeta raíz", "Carpeta de origen"])
        self.structure_combo = CustomComboBox()
        self.structure_combo.addItems(["Crear subcarpeta", "Sin subcarpeta"])
        
        form_trad = QtWidgets.QFormLayout()
        form_trad.setSpacing(10)
        form_trad.addRow("Ruta de guardado", self.save_combo)
        form_trad.addRow("Estructura de guardado", self.structure_combo)
        layout_traditional.addLayout(form_trad)

        # Contenedor B: Modo Manual (Explorador Windows)
        self.container_manual = QtWidgets.QWidget()
        layout_manual = QtWidgets.QVBoxLayout(self.container_manual)
        layout_manual.setContentsMargins(0, 0, 0, 0)
        layout_manual.setSpacing(8)
        
        self.lbl_selected_path = QtWidgets.QLabel("Ninguna ruta seleccionada")
        self.lbl_selected_path.setWordWrap(True) # Para que rutas largas no deformen la UI
        self.lbl_selected_path.setStyleSheet("color: #888; font-style: italic; font-size: 8pt;")
        
        self.btn_browse_path = CustomPushButton("EXPLORAR")
        self.btn_browse_path.setMaximumWidth(100)
        self.btn_browse_path.clicked.connect(self._open_file_dialog)

        layout_manual.addWidget(self.btn_browse_path, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        layout_manual.addWidget(self.lbl_selected_path)

        # -- Ensamblaje y Conexión --
        self.builder_save_options.add_widget(self.check_manual_path)
        self.builder_save_options.add_widget(self.container_traditional)
        self.builder_save_options.add_widget(self.container_manual)

        self.check_manual_path.toggled.connect(self._toggle_save_mode)
        
        # Estado inicial
        self._toggle_save_mode(False)

        # Opciones de Exportación
        self.builder_export_options = BlockBuilder("Configuración de exportación", is_block_header=True)
        
        self.dpi_spinbox = CustomSpinBox()
        self.dpi_spinbox.setRange(72, 600)
        self.quality_spinbox = CustomSpinBox()
        self.quality_spinbox.setRange(1, 100)
        self.quality_spinbox.setSuffix("%")
        
        for spinbox in [self.dpi_spinbox, self.quality_spinbox]:
            spinbox.setMaximumWidth(80)
        
        self.average_width_checkbox = CustomCheckBox("PROMEDIAR EL ANCHO DE LAS PÁGINAS")
        self.builder_export_options.add_form(["DPI: ", "Calidad de compresión: "], [self.dpi_spinbox, self.quality_spinbox])
        self.builder_export_options.add_widget(self.average_width_checkbox)
        
        # Opciones de Thumbnails
        self.builder_th_options = BlockBuilder("Configuración de Thumbnails", is_block_header=True)
        
        self.enable_create_th = CustomCheckBox("CREAR THUMBNAIL")
        self.enable_create_th.setChecked(True)

        # Contenedor de configuracion de TH
        self.th_options_container = QtWidgets.QWidget()
        th_options_layout = QtWidgets.QVBoxLayout(self.th_options_container)

        # Elementos dentro del cuerpo del checkbox
        self.export_th = BlockBuilder("Exportación", is_block_header=False)

        self.th_format_combobox = CustomComboBox()
        self.th_format_combobox.addItems(["jpg", "png"])

        self.th_dpi_spinbox = CustomSpinBox()
        self.th_dpi_spinbox.setRange(72, 600)

        self.th_quality_spinbox = CustomSpinBox()
        self.th_quality_spinbox.setSuffix("%")
        self.th_quality_spinbox.setRange(1, 100)

        self.th_size_spinbox = CustomSpinBox()
        self.th_size_spinbox.setRange(100, 2000)

        for spinbox in [self.th_dpi_spinbox, self.th_size_spinbox, self.th_quality_spinbox]:
            spinbox.setMaximumWidth(80)

        self.th_size_side_combobox = CustomComboBox()
        self.th_size_side_combobox.addItems(["Lado largo", "Lado corto", "Cuadrado"])
        
        size_layout = QtWidgets.QHBoxLayout()
        size_layout.addWidget(self.th_size_spinbox)
        size_layout.addWidget(self.th_size_side_combobox)
        
        self.export_th.add_form(["Formato:", "DPI:", "Calidad:", "Dimensiones:"],
                                [self.th_format_combobox, self.th_dpi_spinbox, self.th_quality_spinbox, size_layout])
        
        self.save_th = BlockBuilder("Guardado", is_block_header=False)

        self.th_save_route = CustomComboBox()
        self.th_save_route.addItems(["Misma que el PDF", "En carpeta a parte"])
        self.save_th.add_form(["Almacenamiento: "], [self.th_save_route])
        
        th_options_layout.addLayout(self.export_th.build())
        th_options_layout.addLayout(self.save_th.build())

        # funcion para mostrar u ocultar el contenido ssegun el estado del checkbox
        self.enable_create_th.toggled.connect(self.th_options_container.setVisible)
        
        self.builder_th_options.add_widget(self.enable_create_th)
        self.builder_th_options.add_widget(self.th_options_container)

        # Armado global
        right_layout.addLayout(self.builder_save_options.build())
        right_layout.addLayout(self.builder_export_options.build())
        right_layout.addLayout(self.builder_th_options.build())
        
        self.setWidget(self.right_panel)

    def _toggle_save_mode(self, is_manual: bool):
        """Maneja la divulgación progresiva ocultando/mostrando los paneles pertinentes."""
        self.container_traditional.setVisible(not is_manual)
        self.container_manual.setVisible(is_manual)

    def _open_file_dialog(self):
        """Abre el explorador nativo para elegir un directorio."""
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, 
            "Seleccionar ruta de exportación",
            "" # Puedes poner QtCore.QDir.homePath() para iniciar en una ruta específica
        )
        if directory:
            self.lbl_selected_path.setText(directory)

    def load_settings(self, config):
        """Precarga la información del JSON en los widgets interactivos."""
        # --- Guardado ---
        self.save_combo.setCurrentIndex(config.get("save_options", "save_route"))
        self.structure_combo.setCurrentIndex(config.get("save_options", "structure"))
        is_manual = config.get("save_options", "manual_mode")
        self.check_manual_path.setChecked(is_manual)
        saved_path = config.get("save_options", "path")
        if saved_path:
            self.lbl_selected_path.setText(saved_path)
        else:
            self.lbl_selected_path.setText("Ninguna ruta seleccionada")
        
        # --- Exportación de PDF ---
        self.dpi_spinbox.setValue(config.get("export_pdf", "dpi"))
        self.quality_spinbox.setValue(config.get("export_pdf", "quality"))
        self.average_width_checkbox.setChecked(config.get("export_pdf", "average_width"))
        
        # --- Exportación de Thumbnails ---
        self.enable_create_th.setChecked(config.get("export_th", "enabled"))
        self.th_format_combobox.setCurrentIndex(config.get("export_th", "format"))
        self.th_dpi_spinbox.setValue(config.get("export_th", "dpi"))
        self.th_quality_spinbox.setValue(config.get("export_th", "quality"))
        self.th_size_spinbox.setValue(config.get("export_th", "size"))
        self.th_size_side_combobox.setCurrentIndex(config.get("export_th", "size_side"))
        self.th_save_route.setCurrentIndex(config.get("export_th", "save_route"))

    def save_settings(self, config):
        """Extrae la información actual de los widgets y la envía al disco."""
        # --- Guardado ---
        config.set("save_options", "save_route", self.save_combo.currentIndex())
        config.set("save_options", "structure", self.structure_combo.currentIndex())
        config.set("save_options", "manual_mode", self.check_manual_path.isChecked())
        current_path = self.lbl_selected_path.text()
        if current_path == "Ninguna ruta seleccionada":
            current_path = "" # Almacena string vacio en json para evitar errores
        config.set("save_options", "manual_path", current_path)
        
        # --- Exportación de PDF ---
        config.set("export_pdf", "dpi", self.dpi_spinbox.value())
        config.set("export_pdf", "quality", self.quality_spinbox.value())
        config.set("export_pdf", "average_width", self.average_width_checkbox.isChecked())
        
        # --- Exportación de Thumbnails ---
        config.set("export_th", "enabled", self.enable_create_th.isChecked())
        config.set("export_th", "format", self.th_format_combobox.currentIndex())
        config.set("export_th", "dpi", self.th_dpi_spinbox.value())
        config.set("export_th", "quality", self.th_quality_spinbox.value())
        config.set("export_th", "size", self.th_size_spinbox.value())
        config.set("export_th", "size_side", self.th_size_side_combobox.currentIndex())
        config.set("export_th", "save_route", self.th_save_route.currentIndex())


class PDFConverterView(QtWidgets.QWidget):
    request_cancel = QtCore.pyqtSignal()
    request_convert = QtCore.pyqtSignal()
    request_help = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("pdfConverterViewBase")
        self.setup_ui()

    def setup_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        self.setup_header()
        self.setup_tabs()
        self.setup_footer()

        self._load_current_settings()
        self._setup_models()

    def setup_header(self):
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(0)

        return_button = CustomPushButton(HICutterIcons.BACK)
        return_button.setProperty("estilo", "icono")
        return_button.setProperty("variante", "regresar")
        return_button.setFixedSize(30,20)
        return_button.clicked.connect(self.request_cancel.emit)
        
        lbl_title = QtWidgets.QLabel("CREAR PDF")
        lbl_title.setProperty("estilo", "title")
        
        self.help_btn = CustomPushButton("AYUDA")
        self.help_btn.setProperty("estilo", "primario")
        self.help_btn.clicked.connect(self.request_help.emit)

        header_layout.addWidget(return_button, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(lbl_title, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        header_layout.addStretch() 
        header_layout.addWidget(self.help_btn)
        header_layout.addSpacing(15)

        self.main_layout.addLayout(header_layout)

    def setup_tabs(self):
        self.tab_widget = QtWidgets.QTabWidget()
        
        self.tab_batch = QtWidgets.QWidget()
        self.tab_individual = QtWidgets.QWidget()
        
        self.build_batch_tab(self.tab_batch)
        self.build_individual_tab(self.tab_individual)
        
        self.tab_widget.addTab(self.tab_batch, "LOTE")
        self.tab_widget.addTab(self.tab_individual, "INDIVIDUAL")
        
        self.main_layout.addWidget(self.tab_widget, stretch=1) 

    def build_batch_tab(self, parent_widget):
        layout = QtWidgets.QHBoxLayout(parent_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        splitter_h = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        
        # Instanciar clase de búsqueda independiente
        self.batch_searcher = LocalFilesSearcher()
        
        center_frame = QtWidgets.QGroupBox()
        center_frame.setMinimumWidth(400)
        center_layout = QtWidgets.QVBoxLayout(center_frame)

        lbl_sandbox = QtWidgets.QLabel("PANEL DE TRABAJO")
        lbl_sandbox.setProperty("estilo", "splitter_title")

        # Creamos el elemento de sandbox previamente armado en tree_view_components
        self.tree_sandbox = SandboxTreeView()

        # Instanciar clase de configuración independiente
        self.batch_config = ExportConfigPanel()

        sandbox_config_layout = QtWidgets.QHBoxLayout()
        sandbox_config_layout.addWidget(self.tree_sandbox, stretch=1)
        sandbox_config_layout.addWidget(self.batch_config, stretch=1)

        center_layout.addWidget(lbl_sandbox)
        center_layout.addSpacing(10)
        center_layout.addLayout(sandbox_config_layout)

        splitter_h.addWidget(self.batch_searcher)
        splitter_h.addWidget(center_frame)

        splitter_h.setStretchFactor(0, 0)
        splitter_h.setStretchFactor(1, 1)
        splitter_h.setCollapsible(0, False)
        splitter_h.setCollapsible(1, False)

        layout.addWidget(splitter_h)

    def build_individual_tab(self, parent_widget):
        layout = QtWidgets.QHBoxLayout(parent_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        splitter_h = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        
        # Instanciar NUEVA clase de búsqueda independiente
        self.ind_searcher = LocalFilesSearcher()
        
        center_frame = QtWidgets.QGroupBox()
        center_frame.setMinimumWidth(400)
        center_frame.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        center_layout = QtWidgets.QVBoxLayout(center_frame)
        
        lbl_sandbox = QtWidgets.QLabel("PANEL DE TRABAJO INDIVIDUAL")
        lbl_sandbox.setProperty("estilo", "splitter_title")
        
        self.list_sandbox = QtWidgets.QListView() 
        self.list_sandbox.setMinimumWidth(200)
        self.list_sandbox.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_sandbox.setSelectionRectVisible(True)
        self.list_sandbox.setDragEnabled(True)
        self.list_sandbox.setAcceptDrops(True)
        self.list_sandbox.setDropIndicatorShown(True)
        self.list_sandbox.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.list_sandbox.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.list_sandbox.setItemDelegate(NeonSelectionDelegate(self.list_sandbox))
        self.list_sandbox.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        preview_container = QtWidgets.QFrame()
        preview_container.setMinimumWidth(150)
        preview_container.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        preview_layout = QtWidgets.QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(10)
        
        lbl_preview_title = QtWidgets.QLabel("VISTA PREVIA")
        lbl_preview_title.setProperty("estilo", "label_form")
        lbl_preview_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl_preview_title.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Maximum)
        
        self.canvas_ind = QtWidgets.QLabel("SIN SELECCIÓN")
        self.canvas_ind.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.canvas_ind.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.canvas_ind.setObjectName("viewerCanvas")
        
        preview_layout.addWidget(lbl_preview_title)
        preview_layout.addWidget(self.canvas_ind, stretch=1)
        
        # 2. Instanciar NUEVA clase de configuración independiente
        self.ind_config = ExportConfigPanel()
        
        sandbox_config_layout = QtWidgets.QHBoxLayout()
        sandbox_config_layout.addWidget(self.list_sandbox, stretch=1)
        sandbox_config_layout.addWidget(preview_container, stretch=1, )
        sandbox_config_layout.addWidget(self.ind_config, stretch=1)
        
        center_layout.addWidget(lbl_sandbox)
        center_layout.addSpacing(10)
        center_layout.addLayout(sandbox_config_layout)
        
        splitter_h.addWidget(self.ind_searcher)
        splitter_h.addWidget(center_frame)
        
        splitter_h.setStretchFactor(0, 0)
        splitter_h.setStretchFactor(1, 1)
        splitter_h.setCollapsible(0, False)
        splitter_h.setCollapsible(1, False)
        
        layout.addWidget(splitter_h)

    def setup_footer(self):
        self.footer_layout = QtWidgets.QHBoxLayout()
        self.btn_convert = CustomPushButton("CONVERTIR")
        self.btn_convert.setProperty("estilo", "primario")
        self.btn_convert.setFixedSize(100, 32)
        self.btn_convert.clicked.connect(self._save_and_continue)

        self.footer_layout.addStretch()
        self.footer_layout.addWidget(self.btn_convert)
        self.footer_layout.addSpacing(15)

        self.main_layout.addSpacing(5)
        self.main_layout.addLayout(self.footer_layout)
        self.main_layout.addSpacing(5)

    def _load_current_settings(self):
        """Se ejecuta al iniciar la app. Carga los valores predeterminados en ambas pestañas."""
        self.batch_config.load_settings(config_manager)
        self.ind_config.load_settings(config_manager)

    def _get_export_batches(self) -> dict:
        """Extrae el Sandbox. Si es Lote agrupa por carpetas. Si es Ind. crea un grupo genérico."""
        batches = {}
        is_batch = (self.tab_widget.currentIndex() == 0)
        
        if is_batch:
            # Iteramos por carpetas (Nodos Raíz)
            for row in range(self.batch_sandbox_model.rowCount()):
                folder_item = self.batch_sandbox_model.item(row)
                folder_name = folder_item.text()
                paths = []
                for child_row in range(folder_item.rowCount()):
                    child_item = folder_item.child(child_row)
                    paths.append(child_item.data(QtCore.Qt.ItemDataRole.UserRole))
                if paths:
                    batches[folder_name] = paths
        else:
            # Lista individual
            paths = []
            for row in range(self.ind_sandbox_model.rowCount()):
                item = self.ind_sandbox_model.item(row)
                paths.append(item.data(QtCore.Qt.ItemDataRole.UserRole))
            if paths:
                batches["INDIVIDUAL_MODE"] = paths # Key temporal
                
        return batches

    def _save_and_continue(self):
        """Captura configuración, evalúa nombres y despacha Workers."""
        is_batch = (self.tab_widget.currentIndex() == 0)
        config_panel = self.batch_config if is_batch else self.ind_config
        config_panel.save_settings(config_manager)
        
        batches = self._get_export_batches()
        if not batches:
            QtWidgets.QMessageBox.warning(self, "Aviso", "No hay imágenes en el área de trabajo.")
            return

        # 1. Definir Ruta Base de Exportación
        is_manual = config_manager.get("save_options", "manual_mode")
        save_route_idx = config_manager.get("save_options", "save_route")
        
        if is_manual:
            base_dir = config_manager.get("save_options", "manual_path")
            if not base_dir:
                QtWidgets.QMessageBox.warning(self, "Aviso", "Seleccione una ruta de guardado manual.")
                return
        else:
            # Tomar ruta del primer archivo encontrado como referencia
            first_path = next(iter(batches.values()))[0]
            first_img_dir = os.path.dirname(first_path)
            base_dir = first_img_dir if save_route_idx == 1 else os.path.dirname(first_img_dir)

        # 2. Lógica de Nombrado (Individual vs Lote)
        if not is_batch:
            pdf_name, ok = QtWidgets.QInputDialog.getText(self, "Nombre del Documento", "Ingrese el nombre para el archivo PDF:", text="Documento_HICutter")
            if not ok or not pdf_name.strip(): return
            
            # Reemplazamos el Key genérico por el nombre real
            paths = batches.pop("INDIVIDUAL_MODE")
            batches[pdf_name.strip()] = paths
            
            self.first_images_for_th = {pdf_name.strip(): paths[0]}
        else:
            # En Lote, 'batches' ya tiene los nombres de carpetas y las rutas correctas.
            self.first_images_for_th = {k: v[0] for k, v in batches.items()}

        # 3. Datos técnicos
        quality = config_manager.get("export_pdf", "quality")
        dpi = config_manager.get("export_pdf", "dpi")
        avg_width = config_manager.get("export_pdf", "average_width")

        # 4. Lanzar Worker PDF
        self.pdf_wait_dialog = QtWidgets.QProgressDialog("Ensamblando PDF(s), por favor espere...", None, 0, 0, self)
        self.pdf_wait_dialog.setWindowTitle("Generando PDF")
        self.pdf_wait_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.pdf_wait_dialog.setCancelButton(None)
        self.pdf_wait_dialog.show()

        worker = PDFWorker(batches, base_dir, quality, dpi, avg_width)
        worker.signals.finished.connect(lambda count: self._on_pdf_success(count, base_dir))
        worker.signals.error.connect(self._on_pdf_error)
        
        QtCore.QThreadPool.globalInstance().start(worker)

    def _on_pdf_success(self, count: int, base_dir: str):
        # Ocultar UI de progreso PDF
        if hasattr(self, 'pdf_wait_dialog') and self.pdf_wait_dialog:
            self.pdf_wait_dialog.close()

        # Limpiar Sandbox
        if self.tab_widget.currentIndex() == 0:
            self.batch_sandbox_model.clear()
        else:
            self.ind_sandbox_model.clear()
            self.canvas_ind.setText("SIN SELECCIÓN")
            self.canvas_ind.setPixmap(QtGui.QPixmap())

        # Evaluar exportación de Thumbnail (Encadenamiento de Hilos)
        if config_manager.get("export_th", "enabled"):
            logger.info("Thumbnails activados. Iniciando Worker TH...")
            th_worker = THWorker(self.first_images_for_th, base_dir)
            th_worker.signals.finished.connect(lambda: self._finish_process_ui(count))
            QtCore.QThreadPool.globalInstance().start(th_worker)
        else:
            self._finish_process_ui(count)

    def _finish_process_ui(self, count: int):
        QtWidgets.QMessageBox.information(self, "Éxito", f"Se generaron {count} documento(s) correctamente.")
        self.request_convert.emit() # Informar a main para regresar al Landing View

    def _on_pdf_error(self, e: str):
        if hasattr(self, 'pdf_wait_dialog') and self.pdf_wait_dialog:
            self.pdf_wait_dialog.close()
        logger.error("Error crítico creando el PDF", exc_info=True)
        QtWidgets.QMessageBox.critical(self, "Error", f"Fallo al generar el PDF:\n\n{e}")

    def _setup_models(self):
        """Inicializa los modelos de datos ligeros para los Sandboxes."""
        # Modelo para Lote (Árbol)
        self.batch_sandbox_model = QtGui.QStandardItemModel()
        self.tree_sandbox.setModel(self.batch_sandbox_model)
        
        # Modelo para Individual (Lista plana)
        self.ind_sandbox_model = QtGui.QStandardItemModel()
        self.list_sandbox.setModel(self.ind_sandbox_model)

        # Conectar el cambio de selección en la lista individual para renderizar la vista previa
        self.list_sandbox.selectionModel().selectionChanged.connect(self._on_individual_selection_changed)
        
        # Obtenemos la lista de las rutas proporcionadas por el "Explorador"
        self.ind_searcher.btn_add_element.clicked.connect(self._add_to_individual_sandbox)
        self.batch_searcher.btn_add_element.clicked.connect(self._add_to_batch_sandbox)

        # Atajos de teclado para eliminar
        self.del_shortcut_ind = QtGui.QShortcut(QtGui.QKeySequence("Delete"), self.list_sandbox)
        self.del_shortcut_ind.activated.connect(self._delete_selected_individual)
        self.back_shortcut_ind = QtGui.QShortcut(QtGui.QKeySequence("Backspace"), self.list_sandbox)
        self.back_shortcut_ind.activated.connect(self._delete_selected_individual)
        
        self.del_shortcut_batch = QtGui.QShortcut(QtGui.QKeySequence("Delete"), self.tree_sandbox)
        self.del_shortcut_batch.activated.connect(self._delete_selected_batch)
        self.back_shortcut_batch = QtGui.QShortcut(QtGui.QKeySequence("Backspace"), self.tree_sandbox)
        self.back_shortcut_batch.activated.connect(self._delete_selected_batch)

    def _add_to_individual_sandbox(self):
        """Pasa los archivos del explorador al Sandbox Individual guardando solo la ruta en memoria."""
        paths = self.ind_searcher.get_selected_paths() 
        
        for path in paths:
            # Validar que sea imagen
            if not path.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.cr2')):
                continue
                
            filename = os.path.basename(path)
            item = QtGui.QStandardItem(filename)
            item.setToolTip(path)
            
            # MAGIA DE RAM: Guardamos la ruta absoluta como un dato oculto (Role)
            item.setData(path, QtCore.Qt.ItemDataRole.UserRole)
            
            # Ponemos un ícono por defecto (ligero) en lugar de renderizar la foto real
            icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileIcon)
            item.setIcon(icon)
            
            self.ind_sandbox_model.appendRow(item)

    def _on_individual_selection_changed(self, selected, deselected):
        """Lazy Loading Ultra-Optimizado con lectura EXIF."""
        indexes = self.list_sandbox.selectionModel().selectedIndexes()
        if not indexes:
            self.canvas_ind.setText("SIN SELECCIÓN")
            self.canvas_ind.setPixmap(QtGui.QPixmap()) 
            return
            
        index = indexes[0]
        real_path = self.ind_sandbox_model.data(index, QtCore.Qt.ItemDataRole.UserRole)
        
        # OPTIMIZACIÓN Y ROTACIÓN del thumbnail
        reader = QtGui.QImageReader(real_path)
        # Lee los metadatos para otorgar la rotacion correcta
        reader.setAutoTransform(True) 
        
        orig_size = reader.size()
        if orig_size.width() > 0 and orig_size.height() > 0:
            # Calculamos dinámicamente el tamaño que tiene el canvas en este momento
            target_w = self.canvas_ind.width()
            target_h = self.canvas_ind.height()
            
            # Prevención de tamaño inválido en el arranque de la app
            if target_w < 100: target_w = 600
            if target_h < 100: target_h = 600

            # Escalamos basándonos en el espacio disponible en la UI
            scaled_size = orig_size.scaled(target_w, target_h, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            reader.setScaledSize(scaled_size)
        
        image = reader.read()
        if not image.isNull():
            self.canvas_ind.setPixmap(QtGui.QPixmap.fromImage(image))
        else:
            self.canvas_ind.setText("PREVIEW NO DISPONIBLE")

    def _add_to_batch_sandbox(self):
        """Agrupa los archivos seleccionados por carpeta y construye el árbol."""
        paths = self.batch_searcher.get_selected_paths()
        if not paths: return
        
        # 1. Agrupamos los archivos en un diccionario según su carpeta padre
        grouped_paths = {}
        for path in paths:
            if not path.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.cr2')):
                continue
            parent_dir = os.path.dirname(path)
            if parent_dir not in grouped_paths:
                grouped_paths[parent_dir] = []
            grouped_paths[parent_dir].append(path)
            
        # 2. Construimos el árbol visual
        for folder_path, files in grouped_paths.items():
            folder_name = os.path.basename(folder_path)
            
            # Buscamos si la carpeta ya existe en el modelo para no duplicarla
            folder_item = None
            for row in range(self.batch_sandbox_model.rowCount()):
                item = self.batch_sandbox_model.item(row)
                if item.text() == folder_name and item.data(QtCore.Qt.ItemDataRole.UserRole) == folder_path:
                    folder_item = item
                    break
            
            # Si no existe, creamos la fila de la carpeta
            if not folder_item:
                folder_item = QtGui.QStandardItem(folder_name)
                folder_item.setData(folder_path, QtCore.Qt.ItemDataRole.UserRole)
                folder_icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon)
                folder_item.setIcon(folder_icon)
                self.batch_sandbox_model.appendRow(folder_item)
            
            # 3. Añadimos los archivos como hijos de esta carpeta
            for file_path in files:
                filename = os.path.basename(file_path)
                
                # Evitamos duplicar un archivo que ya estaba agregado
                exists = False
                for i in range(folder_item.rowCount()):
                    if folder_item.child(i).data(QtCore.Qt.ItemDataRole.UserRole) == file_path:
                        exists = True
                        break
                if exists: continue
                
                file_item = QtGui.QStandardItem(filename)
                file_item.setData(file_path, QtCore.Qt.ItemDataRole.UserRole)
                file_icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileIcon)
                file_item.setIcon(file_icon)
                
                folder_item.appendRow(file_item)
        
        # Expandimos el árbol para que el usuario vea lo que acaba de añadir
        self.tree_sandbox.expandAll()

    def _delete_selected_individual(self):
        """Borra elementos de la lista individual (de abajo hacia arriba para evitar errores de índice)."""
        indexes = self.list_sandbox.selectionModel().selectedRows()
        for index in sorted(indexes, key=lambda x: x.row(), reverse=True):
            self.ind_sandbox_model.removeRow(index.row())
            
    def _delete_selected_batch(self):
        """Borra elementos del árbol (Respeta la jerarquía)."""
        indexes = self.tree_sandbox.selectionModel().selectedRows()
        # Ordenamos para borrar primero hijos y luego padres si están ambos seleccionados
        for index in sorted(indexes, key=lambda x: (x.parent().row(), x.row()), reverse=True):
            parent = index.parent()
            if parent.isValid():
                self.batch_sandbox_model.itemFromIndex(parent).removeRow(index.row())
            else:
                self.batch_sandbox_model.removeRow(index.row())

    def _get_ordered_paths(self) -> list[str]:
        """Extrae las rutas en el orden exacto en el que aparecen visualmente."""
        paths = []
        is_batch = (self.tab_widget.currentIndex() == 0)
        
        if is_batch:
            # Recorrer estructura de árbol (Carpetas -> Archivos)
            for row in range(self.batch_sandbox_model.rowCount()):
                folder_item = self.batch_sandbox_model.item(row)
                for child_row in range(folder_item.rowCount()):
                    child_item = folder_item.child(child_row)
                    paths.append(child_item.data(QtCore.Qt.ItemDataRole.UserRole))
        else:
            # Recorrer lista plana
            for row in range(self.ind_sandbox_model.rowCount()):
                item = self.ind_sandbox_model.item(row)
                paths.append(item.data(QtCore.Qt.ItemDataRole.UserRole))
                
        return paths
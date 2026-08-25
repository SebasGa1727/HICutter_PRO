import sys
import os
from PyQt6 import QtCore, QtGui, QtWidgets

# TRUCO PARA MOCK: Agregar la raíz del proyecto al PATH para ejecuciones aisladas
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from ui.components.neon_widgets import CustomPushButton
from utils.asset_manager import assets
from utils.logger import setup_logger

logger = setup_logger(__name__)

class AIBatchProcessView(QtWidgets.QWidget):
    """
    Vista de Procesamiento IA por Lotes.
    Panel Izquierdo: Controles, contadores y terminal de logs.
    Panel Derecho: Feedback visual (Logo, barra de progreso y tiempos).
    """
    request_cancel = QtCore.pyqtSignal()
    request_pause_resume = QtCore.pyqtSignal(bool) # Emite True para pausar, False para reanudar

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_paused = False
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- PANEL IZQUIERDO (Azul - Controles y Datos) ---
        self.left_panel = QtWidgets.QFrame()
        self.left_panel.setProperty("landing_view", "derecha") # Fondo Azul del theme.qss
        
        # --- PANEL DERECHO (Negro - Feedback y Progreso) ---
        self.right_panel = QtWidgets.QFrame()
        self.right_panel.setProperty("landing_view", "izquierda") # Fondo Negro del theme.qss

        self.main_layout.addWidget(self.left_panel, stretch=1)
        self.main_layout.addWidget(self.right_panel, stretch=1)

        self._setup_left_panel()
        self._setup_right_panel()

    def _setup_left_panel(self):
        layout = QtWidgets.QVBoxLayout(self.left_panel)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # QFrame envolvente (Wrapper) para separar visualmente el contenido del fondo azul
        self.wrapper_frame = QtWidgets.QFrame()
        self.wrapper_frame.setProperty("ai_batch_view", "contenedor")
    
        wrapper_layout = QtWidgets.QVBoxLayout(self.wrapper_frame)
        wrapper_layout.setContentsMargins(50, 30, 50, 30)
        wrapper_layout.setSpacing(25)

        # Título
        self.lbl_title = QtWidgets.QLabel("Procesamiento de IA en curso")
        self.lbl_title.setProperty("estilo", "title")
        self.lbl_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Contadores de Triaje
        counters_layout = QtWidgets.QHBoxLayout()
        counters_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        
        self.lbl_success = QtWidgets.QLabel("✔️ Procesadas con éxito: 0")
        self.lbl_success.setProperty("ai_batch_view", "exito")
        self.lbl_success.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_review = QtWidgets.QLabel("⚠️ Revisión requerida: 0")
        self.lbl_review.setProperty("ai_batch_view", "aviso")
        
        counters_layout.addWidget(self.lbl_success)
        counters_layout.addStretch(1)
        counters_layout.addWidget(self.lbl_review)

        # Archivo Actual
        self.lbl_current_file = QtWidgets.QLabel("Preparando motor de inferencia...")
        self.lbl_current_file.setProperty("ai_batch_view", "archivo")
        self.lbl_current_file.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Widget contenedor de los elementos superiores
        widget_container = QtWidgets.QWidget()
        widget_container.setProperty("estilo", "fondo_transparente")
        widget_container_layout = QtWidgets.QVBoxLayout(widget_container)
        widget_container_layout.setSpacing(20)

        widget_container_layout.addWidget(self.lbl_title)
        widget_container_layout.addLayout(counters_layout)
        widget_container_layout.addWidget(self.lbl_current_file)

        # Terminal de Logs (Oculta por defecto)
        self.log_terminal = QtWidgets.QTextEdit()
        self.log_terminal.setReadOnly(True)
        self.log_terminal.setVisible(False)
        self.log_terminal.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, 
                                        QtWidgets.QSizePolicy.Policy.Expanding)

        # Controles (Botones)
        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.setSpacing(15)

        self.btn_cancel = CustomPushButton("Cancelar")
        self.btn_cancel.setProperty("estilo", "cancelar")
        self.btn_cancel.clicked.connect(self.request_cancel.emit)

        self.btn_pause = CustomPushButton("Pausar")
        self.btn_pause.clicked.connect(self._toggle_pause)

        self.btn_toggle_logs = CustomPushButton("Mostrar Detalles")
        self.btn_toggle_logs.setProperty("estilo", "primario")
        self.btn_toggle_logs.clicked.connect(self._toggle_logs)

        controls_layout.addWidget(self.btn_cancel)
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_toggle_logs)

        # Ensamblaje del Wrapper
        wrapper_layout.addWidget(widget_container, alignment=QtCore.Qt.AlignmentFlag.AlignTop)
        wrapper_layout.addWidget(self.log_terminal, stretch=1)
        wrapper_layout.addLayout(controls_layout)

        layout.addWidget(self.wrapper_frame)

    def _setup_right_panel(self):
        layout = QtWidgets.QVBoxLayout(self.right_panel)
        layout.setContentsMargins(60, 60, 60, 60)

        # 1. Logo
        self.logo_label = QtWidgets.QLabel()
        self.logo_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop)
        # Obtenemos el logo ya escalado y cacheado desde el AssetManager
        pixmap = assets.get_scaled_pixmap("hicutter_full_black.png", 650, 650)
        
        if not pixmap.isNull():
            self.logo_label.setPixmap(pixmap)
            self.logo_label.setMaximumHeight(650)
        else:
            # Fallback seguro en caso de que borren el archivo
            self.logo_label.setText("LOGO HICUTTER")
            self.logo_label.setStyleSheet("color: #555; font-size: 24pt; font-weight: bold;")

        # 2. Barra de Progreso
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setFixedHeight(25)

        # 3. Tiempos (ETA y Transcurrido)
        times_layout = QtWidgets.QHBoxLayout()
        self.lbl_elapsed = QtWidgets.QLabel("Transcurrido: 00:00")
        self.lbl_elapsed.setProperty("ai_batch_view", "ETA")
        
        self.lbl_eta = QtWidgets.QLabel("ETA: Calculando...")
        self.lbl_eta.setProperty("ai_batch_view", "ETA")
        self.lbl_eta.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        times_layout.addWidget(self.lbl_elapsed)
        times_layout.addWidget(self.lbl_eta)

        # Armado
        layout.addStretch(1)
        layout.addWidget(self.logo_label)
        layout.addStretch(1)
        layout.addWidget(self.progress_bar)
        layout.addSpacing(10)
        layout.addLayout(times_layout)

    # --- Métodos de Interacción UX/UI ---

    def _toggle_logs(self):
        """Muestra u oculta la terminal de logs."""
        is_visible = self.log_terminal.isVisible()
        self.log_terminal.setVisible(not is_visible)
        if not is_visible:
            self.btn_toggle_logs.setText("Ocultar Detalles")
            self.log_terminal.verticalScrollBar().setValue(self.log_terminal.verticalScrollBar().maximum())
        else:
            self.btn_toggle_logs.setText("Mostrar Detalles")

    def _toggle_pause(self):
        """Alterna el estado de pausa y emite la señal al Worker."""
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.btn_pause.setText("Reanudar")
            self.btn_pause.setProperty("estilo", "primario")
            self.btn_pause.style().unpolish(self.btn_pause)
            self.btn_pause.style().polish(self.btn_pause)
            self.log_message("⚠️ PROCESO PAUSADO POR EL USUARIO")
        else:
            self.btn_pause.setText("Pausar")
            self.btn_pause.setProperty("estilo", "")
            self.btn_pause.style().unpolish(self.btn_pause)
            self.btn_pause.style().polish(self.btn_pause)
            self.log_message("▶️ PROCESO REANUDADO")
            
        self.request_pause_resume.emit(self.is_paused)

    # --- API Pública para actualizar la vista desde el hilo principal ---

    def update_progress(self, current: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{current} / {total} procesadas (%p%)")

    def update_counters(self, success_count: int, review_count: int):
        self.lbl_success.setText(f"✔️ Procesadas con éxito: {success_count}")
        self.lbl_review.setText(f"⚠️ Revisión requerida: {review_count}")

    def update_current_file(self, filename: str):
        self.lbl_current_file.setText(f"Procesando:  {filename}")

    def update_times(self, elapsed: str, eta: str):
        self.lbl_elapsed.setText(f"Transcurrido: {elapsed}")
        self.lbl_eta.setText(f"ETA: {eta}")

    def log_message(self, message: str):
        self.log_terminal.append(message)
        # Auto-scroll hacia abajo
        self.log_terminal.verticalScrollBar().setValue(self.log_terminal.verticalScrollBar().maximum())

if __name__ == "__main__":
    from ui.components.neon_widgets import NeonProxyStyle
    
    app = QtWidgets.QApplication(sys.argv)
    base_style = QtWidgets.QStyleFactory.create("Fusion")
    app.setStyle(NeonProxyStyle(base_style))
    
    try:
        with open("resources/theme.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        pass

    window = AIBatchProcessView()
    window.resize(1000, 600)
    window.showMaximized()
    
    # Mock de actualización para probar la UI visualmente
    window.update_progress(45, 100)
    window.update_counters(42, 3)
    window.update_current_file("AHUNAM_fondo1_0045.tif")
    window.log_message("[Disco] Leyendo matriz de imagen...")
    window.log_message("[IA] Inferencia YOLO ejecutada en 0.8s (Conf: 94%)")
    window.log_message("[Memoria] Recorte matemático aplicado.")
    window.log_message("[I/O] Guardado exitoso en out/AHUNAM_fondo1_0045_crop.jpg")
    
    sys.exit(app.exec())
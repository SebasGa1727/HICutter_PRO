#Truco mock data
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
import os
from PyQt6 import QtWidgets, QtCore, QtGui
from ui.components.neon_widgets import CustomPushButton, CustomCheckBox
from utils.logger import setup_logger

logger = setup_logger(__name__)

class AIReviewItemWidget(QtWidgets.QWidget):
    """Widget personalizado para cada fila de la lista de revisión."""
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = data
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # Checkbox (Si se marca, se acepta el recorte de la IA)
        self.checkbox = CustomCheckBox("")
        self.checkbox.setChecked(False) # Por defecto, todo se va a manual
        
        # Nombre del archivo
        filename = os.path.basename(self.data["path"])
        self.lbl_name = QtWidgets.QLabel(filename)
        # self.lbl_name.setStyleSheet("font-weight: bold; font-size: 10pt; color: #E0E0E0;")
        
        # Confianza
        conf_percent = self.data["conf"] * 100
        self.lbl_conf = QtWidgets.QLabel(f"Confianza: {conf_percent:.1f}%")
        
        # Color semántico según la confianza
        if conf_percent >= 80:
            color = "#FFC107" # Amarillo (Muy cerca de pasar)
        elif conf_percent >= 60:
            color = "#FF9800" # Naranja (Dudoso)
        else:
            color = "#F44336" # Rojo (Poco confiable)
            
        self.lbl_conf.setStyleSheet(f"color: {color}; font-size: 9pt;")

        layout.addWidget(self.checkbox)
        layout.addWidget(self.lbl_name, stretch=1)
        layout.addWidget(self.lbl_conf)

class AIResumeDialog(QtWidgets.QDialog):
    """
    Diálogo de Triaje (Human-in-the-Loop) para imágenes que no pasaron el umbral de IA.
    Permite aceptar el recorte de IA (rescatar) o mandarlo a lote manual.
    """
    def __init__(self, review_data: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Revisión de IA - HICutter")
        self.setMinimumSize(1100, 650)
        self.setModal(True)
        self.review_data = review_data
        
        # Almacenaremos referencias a los widgets personalizados para extraer su estado
        self.item_widgets = []
        
        self._setup_ui()
        self._populate_list()

    def _setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # --- CABECERA ---
        lbl_title = QtWidgets.QLabel("IMÁGENES CON BAJA CONFIANZA")
        lbl_title.setProperty("estilo", "title")
        lbl_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        lbl_subtitle = QtWidgets.QLabel(
            "Selecciona las imágenes cuyo recorte propuesto por la IA sea aceptable.\n"
            "Las que no selecciones serán enviadas al procesamiento manual por lote."
        )
        lbl_subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(lbl_title)
        main_layout.addWidget(lbl_subtitle)

        # --- CUERPO DIVIDIDO ---
        body_layout = QtWidgets.QHBoxLayout()
        
        # Panel Izquierdo (Visor)
        self.preview_group = QtWidgets.QGroupBox("Visión de IA", self)
        preview_layout = QtWidgets.QVBoxLayout(self.preview_group)
        
        self.lbl_preview = QtWidgets.QLabel("Selecciona una imagen de la lista")
        self.lbl_preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.lbl_preview.setMinimumSize(500, 500)
        
        preview_layout.addWidget(self.lbl_preview)
        
        # Panel Derecho (Lista)
        self.list_group = QtWidgets.QGroupBox("Lista de Revisión", self)
        list_layout = QtWidgets.QVBoxLayout(self.list_group)
        
        self.list_widget = QtWidgets.QListWidget(self)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.currentItemChanged.connect(self._on_item_selected)
        
        list_layout.addWidget(self.list_widget)
        
        # Proporciones 60% Visor / 40% Lista
        body_layout.addWidget(self.preview_group, stretch=6)
        body_layout.addWidget(self.list_group, stretch=4)
        
        main_layout.addLayout(body_layout, stretch=1)

        # --- CONTROLES BOTTOM ---
        bottom_layout = QtWidgets.QHBoxLayout()
        
        self.btn_select_all = CustomPushButton("Seleccionar Todo")
        self.btn_select_all.clicked.connect(lambda: self._toggle_all(True))
        
        self.btn_deselect_all = CustomPushButton("Deseleccionar Todo")
        self.btn_deselect_all.clicked.connect(lambda: self._toggle_all(False))
        
        self.btn_accept = CustomPushButton("Confirmar Triaje")
        self.btn_accept.setProperty("estilo", "primario")
        self.btn_accept.clicked.connect(self.accept)

        bottom_layout.addWidget(self.btn_select_all)
        bottom_layout.addWidget(self.btn_deselect_all)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(self.btn_accept)

        main_layout.addLayout(bottom_layout)

    def _populate_list(self):
        """Llena la lista con los Custom Widgets"""
        for data in self.review_data:
            item = QtWidgets.QListWidgetItem(self.list_widget)
            custom_widget = AIReviewItemWidget(data, self)
            
            # Ajustamos el tamaño del QListWidgetItem al CustomWidget
            item.setSizeHint(custom_widget.sizeHint())
            
            # Enlazamos el item lógico con el visual
            item.setData(QtCore.Qt.ItemDataRole.UserRole, data)
            self.list_widget.setItemWidget(item, custom_widget)
            self.item_widgets.append(custom_widget)
            
        # Seleccionamos el primero por defecto
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_item_selected(self, current: QtWidgets.QListWidgetItem, previous: QtWidgets.QListWidgetItem):
        if not current:
            return
            
        data = current.data(QtCore.Qt.ItemDataRole.UserRole)
        thumb_path = data.get("thumb_path")
        
        if thumb_path and os.path.exists(thumb_path):
            pixmap = QtGui.QPixmap(thumb_path)
            # Escalamos conservando aspecto
            pixmap = pixmap.scaled(
                self.lbl_preview.width(), 
                self.lbl_preview.height(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_preview.setPixmap(pixmap)
        else:
            self.lbl_preview.setText("Imagen no disponible")

    def _toggle_all(self, state: bool):
        for widget in self.item_widgets:
            widget.checkbox.setChecked(state)

    def get_triage_results(self) -> tuple[list[dict], list[str]]:
        """
        Retorna dos estructuras:
        1. accepted_for_ai: Lista de diccionarios (con sus coords) aprobados por el usuario.
        2. rejected_for_manual: Lista de rutas (strings puros) para inyectar al BatchManager.
        """
        accepted_for_ai = []
        rejected_for_manual = []
        
        for widget in self.item_widgets:
            if widget.checkbox.isChecked():
                accepted_for_ai.append(widget.data)
            else:
                rejected_for_manual.append(widget.data["path"])
                
        return accepted_for_ai, rejected_for_manual

if __name__ == "__main__":
    import sys
    import cv2
    import numpy as np
    from ui.components.neon_widgets import NeonProxyStyle

    app = QtWidgets.QApplication(sys.argv)
    base_style = QtWidgets.QStyleFactory.create("Fusion")
    app.setStyle(NeonProxyStyle(base_style))

    try:
        with open("resources/theme.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        pass

    # 1. GENERACIÓN DE IMÁGENES FALSAS PARA EL MOCK
    mock_data = []
    niveles_confianza = [0.895, 0.723, 0.451] # Simulan los 3 colores (Amarillo, Naranja, Rojo)
    colores_caja = [(0, 215, 255), (0, 152, 255), (54, 67, 244)] # BGR adaptado a los tonos del theme

    for i in range(3):
        # Crear un lienzo gris oscuro (simulando una imagen original)
        img = np.zeros((800, 800, 3), dtype=np.uint8)
        img[:] = (30, 30, 30)

        # Dibujar un rectángulo claro (simulando el documento histórico)
        cv2.rectangle(img, (150, 150), (650, 700), (200, 200, 180), -1)

        # Coordenadas falsas de la caja de YOLO (ligeramente desfasadas para notar el error)
        x1, y1 = 120 + (i * 30), 130 + (i * 40)
        x2, y2 = 630 - (i * 20), 680 - (i * 50)
        
        # Dibujar el "Bounding Box" de la IA
        cv2.rectangle(img, (x1, y1), (x2, y2), colores_caja[i], 3)
        cv2.putText(img, f"YOLO {niveles_confianza[i]*100:.1f}%", (x1, y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, colores_caja[i], 2)

        # Guardar en archivo temporal
        thumb_path = f"temp_mock_thumb_{i}.jpg"
        cv2.imwrite(thumb_path, img)

        # Construir el DTO (Data Transfer Object)
        mock_data.append({
            "path": f"C:/Acervos/AHUNAM/Fondo_Principal/doc_historico_{i:04d}.tif",
            "thumb_path": thumb_path,
            "coords": (x1, y1, x2, y2),
            "conf": niveles_confianza[i]
        })

    # 2. INSTANCIACIÓN DEL DIÁLOGO
    dialog = AIResumeDialog(mock_data)
    
    # 3. VERIFICACIÓN DE RESULTADOS AL CERRAR
    if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
        aceptadas, rechazadas = dialog.get_triage_results()
        print("\n--- RESULTADOS DEL TRIAJE ---")
        print(f"✔️ Aceptadas por el usuario para IA: {len(aceptadas)}")
        for ac in aceptadas:
            print(f"   -> {ac['path']}")
            
        print(f"⚠️ Rechazadas (Van a lote manual): {len(rechazadas)}")
        for re in rechazadas:
            print(f"   -> {re}")

    # 4. LIMPIEZA DE ARCHIVOS TEMPORALES
    for data in mock_data:
        if os.path.exists(data["thumb_path"]):
            os.remove(data["thumb_path"])
            
    sys.exit()
import os
import cv2
import time
import tempfile
import numpy as np
from PIL import Image
from PyQt6 import QtCore
from ultralytics import YOLO
from utils.logger import setup_logger
from utils.batch_config import config_manager

logger = setup_logger(__name__)

class ConfiguredSaverMixin:
    """
    Proporciona la lectura de configuraciones y el método de guardado rápido
    tanto para la IA principal como para el procesador post-triaje.
    """
    def load_save_configs(self):
        self.out_dir = config_manager.get("save_config", "route")
        self.save_mode = config_manager.get("save_config", "save_mode")
        self.sufix = config_manager.get("save_config", "sufix")
        
        self.format_idx = config_manager.get("export_config", "format")
        self.fmt = "jpg" if self.format_idx == 0 else "png"
        self.quality = config_manager.get("export_config", "quality")
        self.dpi = config_manager.get("export_config", "dpi")
        self.target_size = config_manager.get("export_config", "size")
        
        size_side_idx = config_manager.get("export_config", "size_side")
        anchor_map = {0: "longest_edge", 1: "shortest_edge", 2: "square"}
        self.anchor = anchor_map.get(size_side_idx, "longest_edge")

    def _fast_save(self, cv_image: np.ndarray, original_path: str) -> str:
        """Exportación directa y optimizada."""
        try:
            if self.save_mode == 0: 
                out_dir = os.path.dirname(original_path)
                final_sufix = ""
            elif self.save_mode == 1: 
                out_dir = os.path.dirname(original_path)
                final_sufix = self.sufix
            else: 
                out_dir = self.out_dir
                final_sufix = ""

            os.makedirs(out_dir, exist_ok=True)

            if cv_image.ndim == 3 and cv_image.shape[2] == 3:
                rgb_img = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            else:
                rgb_img = cv_image
                
            pil_img = Image.fromarray(rgb_img)
            orig_w, orig_h = pil_img.size

            if self.anchor == "square":
                new_w, new_h = self.target_size, self.target_size
            elif self.anchor == "longest_edge":
                max_side = max(orig_w, orig_h)
                ratio = self.target_size / float(max_side) if max_side > 0 else 1
                new_w, new_h = int(round(orig_w * ratio)), int(round(orig_h * ratio))
            else: 
                min_side = min(orig_w, orig_h)
                ratio = self.target_size / float(min_side) if min_side > 0 else 1
                new_w, new_h = int(round(orig_w * ratio)), int(round(orig_h * ratio))

            if self.anchor == "square" or orig_w > self.target_size or orig_h > self.target_size:
                pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            base_name, _ = os.path.splitext(os.path.basename(original_path))
            final_name = f"{base_name}{final_sufix}.{self.fmt}"
            out_path = os.path.join(out_dir, final_name)

            pil_format = "JPEG" if self.fmt.lower() == "jpg" else self.fmt.upper()
            pil_img.save(out_path, format=pil_format, quality=self.quality, dpi=(self.dpi, self.dpi))

            return out_path
        except Exception as e:
            logger.error(f"Error en guardado rápido IA para {original_path}", exc_info=True)
            return ""

# HILO 1: WORKER PRINCIPAL DE IA (Inferencia)
class AIBatchSignals(QtCore.QObject):
    progress = QtCore.pyqtSignal(int, int, int, int, str)
    log = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal(list, list) # success_list (str), review_list (dict DTOs)
    error = QtCore.pyqtSignal(str)

class AIBatchWorker(QtCore.QRunnable, ConfiguredSaverMixin):
    def __init__(self, image_list: list[str], check_cancel_func, check_pause_func):
        super().__init__()
        self.image_list = image_list
        self.check_cancel = check_cancel_func
        self.check_pause = check_pause_func
        self.signals = AIBatchSignals()
        self.CONFIDENCE_THRESHOLD = 0.90 
        
        self.success_list = []
        self.review_list = [] # Almacena diccionarios (DTOs)
        
        self.load_save_configs() # Heredado del Mixin

    @QtCore.pyqtSlot()
    def run(self):
        try:
            self.signals.log.emit("Cargando modelo de IA...")
            
            model_path = os.path.join(os.getcwd(), "ai", "YOLO_pose_2.0_medium.pt")
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"No se encontró el modelo IA en: {model_path}")
            
            model = YOLO(model_path)
            self.signals.log.emit("Modelo cargado exitosamente. Iniciando lote.")

            total_images = len(self.image_list)

            for i, img_path in enumerate(self.image_list):
                if self.check_cancel():
                    self.signals.log.emit("⚠️ PROCESO ABORTADO POR EL USUARIO.")
                    break
                
                while self.check_pause():
                    if self.check_cancel(): break
                    time.sleep(0.5)

                filename = os.path.basename(img_path)
                self.signals.log.emit(f"\n--- Procesando: {filename} ---")
                self.signals.progress.emit(i + 1, total_images, len(self.success_list), len(self.review_list), filename)

                img = cv2.imread(img_path)
                if img is None:
                    self.signals.log.emit("❌ Error de I/O: Matriz corrupta. Enviando a revisión manual.")
                    self._add_to_review(img_path, img=None, coords=(0,0,0,0), conf=0.0)
                    continue

                start_time = time.perf_counter()
                results = model(img, verbose=False)
                inference_time = time.perf_counter() - start_time
                
                boxes = results[0].boxes
                
                if len(boxes) == 0:
                    self.signals.log.emit(f"⚠️ No se detectó objeto ({inference_time:.2f}s). Enviando a revisión.")
                    self._add_to_review(img_path, img, coords=(0,0,img.shape[1],img.shape[0]), conf=0.0)
                    continue

                best_box = max(boxes, key=lambda b: b.conf[0].item())
                confidence = best_box.conf[0].item()
                x1, y1, x2, y2 = map(int, best_box.xyxy[0].cpu().numpy())

                if confidence >= self.CONFIDENCE_THRESHOLD:
                    self.signals.log.emit(f"✔️ Recorte exitoso: {confidence*100:.1f}% de confianza ({inference_time:.2f}s).")
                    cropped_img = img[y1:y2, x1:x2]
                    
                    saved_path = self._fast_save(cropped_img, img_path)
                    if saved_path:
                        self.success_list.append(saved_path)
                        self.signals.log.emit(f"💾 Guardado en: {os.path.basename(saved_path)}")
                    else:
                        self.signals.log.emit("❌ Error al guardar el recorte. Enviando original a revisión.")
                        self._add_to_review(img_path, img, coords=(x1,y1,x2,y2), conf=confidence)
                else:
                    self.signals.log.emit(f"⚠️ Confianza baja ({confidence*100:.1f}%). Enviando a triaje de IA.")
                    self._add_to_review(img_path, img, coords=(x1,y1,x2,y2), conf=confidence)

            if not self.check_cancel():
                self.signals.log.emit("\n✅ Lote IA finalizado con éxito.")
            
            self.signals.finished.emit(self.success_list, self.review_list)

        except Exception as e:
            logger.error("Error crítico en el hilo de IA", exc_info=True)
            self.signals.error.emit(str(e))

    def _add_to_review(self, path: str, img: np.ndarray, coords: tuple, conf: float):
        """Genera el DTO y el thumbnail optimizado."""
        thumb_path = ""
        if img is not None:
            thumb_path = self._generate_thumbnail(img, coords, conf)
            
        self.review_list.append({
            "path": path,
            "thumb_path": thumb_path,
            "coords": coords,
            "conf": conf
        })

    def _generate_thumbnail(self, img: np.ndarray, coords: tuple, conf: float) -> str:
        """
        Redimensiona usando OpenCV (ultrarrápido), dibuja el cuadro de IA
        y lo guarda en un archivo temporal del sistema.
        """
        h, w = img.shape[:2]
        max_dim = 800
        scale = min(max_dim / w, max_dim / h)
        
        # Redimensionado veloz
        if scale < 1.0:
            new_w, new_h = int(w * scale), int(h * scale)
            thumb = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        else:
            thumb = img.copy()
            scale = 1.0

        # Dibujado del rectángulo sobre el thumbnail
        x1, y1, x2, y2 = coords
        tx1, ty1, tx2, ty2 = int(x1 * scale), int(y1 * scale), int(x2 * scale), int(y2 * scale)
        
        # Determinar color basado en confianza
        if conf >= 0.80:
            color = (0, 215, 255) # Amarillo (BGR)
        elif conf >= 0.60:
            color = (0, 152, 255) # Naranja (BGR)
        else:
            color = (54, 67, 244) # Rojo (BGR)

        if conf > 0.0:
            cv2.rectangle(thumb, (tx1, ty1), (tx2, ty2), color, 3)
            cv2.putText(thumb, f"{conf*100:.1f}%", (tx1, max(ty1 - 10, 20)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # Usar tempfile para delegar la gestión del archivo al SO
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", prefix="hicutter_thumb_")
        temp_file.close() # Lo cerramos para que OpenCV pueda escribir en él
        
        cv2.imwrite(temp_file.name, thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        return temp_file.name

# HILO 2: WORKER DE CORTES RÁPIDOS POST-TRIAJE
class AIFastCropSignals(QtCore.QObject):
    progress = QtCore.pyqtSignal(int, int) # current, total
    finished = QtCore.pyqtSignal(list, list) # success_list, error_list

class AIFastCropWorker(QtCore.QRunnable, ConfiguredSaverMixin):
    """
    Obrero que se encarga de procesar instantáneamente la lista de diccionarios
    aceptados por el usuario en el AIResumeDialog. (Slicing matemático sin inferencia).
    """
    def __init__(self, accepted_data: list[dict]):
        super().__init__()
        self.accepted_data = accepted_data
        self.signals = AIFastCropSignals()
        
        self.success_list = []
        self.error_list = []
        self.load_save_configs() # Heredado del Mixin

    @QtCore.pyqtSlot()
    def run(self):
        total = len(self.accepted_data)
        
        for i, item in enumerate(self.accepted_data):
            try:
                img_path = item["path"]
                x1, y1, x2, y2 = map(int, item["coords"])
                
                img = cv2.imread(img_path)
                if img is None:
                    self.error_list.append(img_path)
                    continue
                
                # Recorte matemático en memoria RAM
                cropped_img = img[y1:y2, x1:x2]
                
                # Guardado
                saved_path = self._fast_save(cropped_img, img_path)
                if saved_path:
                    self.success_list.append(saved_path)
                else:
                    self.error_list.append(img_path)
                    
            except Exception as e:
                logger.error(f"Error procesando {item.get('path', 'unknown')}", exc_info=True)
                self.error_list.append(item.get("path", ""))
                
            finally:
                # Actualizar barra de progreso si es que main quiere mostrarla
                self.signals.progress.emit(i + 1, total)

        self.signals.finished.emit(self.success_list, self.error_list)
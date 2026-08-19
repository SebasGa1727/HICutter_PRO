import os
import ctypes
import numpy as np
import cv2
import shutil
import random
from utils.logger import setup_logger

logger = setup_logger(__name__)

def _get_hidden_dataset_dir() -> str:
    """
    Calcula la raíz del programa, crea la carpeta y le inyecta el 
    atributo nativo de 'Carpeta Oculta' en Windows.
    """
    # 1. Obtenemos la raíz del programa (Subiendo un nivel desde la carpeta 'core')
    core_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(core_dir)
    
    # 2. Definimos el nombre de la bóveda (Con un punto para ocultar en Unix/Linux)
    dataset_dir = os.path.join(root_dir, ".ai_dataset")
    
    if not os.path.exists(dataset_dir):
        os.makedirs(dataset_dir)
        
        # 3. Magia de Windows: Modificamos los atributos del sistema de archivos
        if os.name == 'nt':
            FILE_ATTRIBUTE_HIDDEN = 0x02
            # Llamamos a la API del Kernel32 de Windows para ocultarla
            ret = ctypes.windll.kernel32.SetFileAttributesW(dataset_dir, FILE_ATTRIBUTE_HIDDEN)
            if not ret:
                logger.warning(f"No se pudo aplicar el atributo oculto a {dataset_dir}")
                
    return dataset_dir

def export_yolo_data(cv_image: np.ndarray, points: np.ndarray, base_filename: str, class_id: int = 0) -> bool:
    """
    Extrae la imagen optimizada (1024px) y calcula el Bounding Box Orientado normalizado (YOLO-POSE).
    Guarda ambos archivos (.jpg y .txt) en la bóveda oculta.
    """
    try:
        images_dataset_dir = os.path.join(_get_hidden_dataset_dir(), "images")
        if not os.path.exists(images_dataset_dir):
            os.makedirs(images_dataset_dir, exist_ok=True)

        txt_dataset_dir = os.path.join(_get_hidden_dataset_dir(), "labels")
        if not os.path.exists(txt_dataset_dir):
            os.makedirs(txt_dataset_dir, exist_ok=True)
        
        # Limpiamos el nombre base para generar los archivos emparejados
        name_no_ext = os.path.splitext(os.path.basename(base_filename))[0]
        txt_path = os.path.join(txt_dataset_dir, f"{name_no_ext}.txt")
        img_path = os.path.join(images_dataset_dir, f"{name_no_ext}.jpg")

        img_h, img_w = cv_image.shape[:2]
        
        # --- 1. MATEMÁTICA YOLO-POSE (Keypoint Detection) ---
        norm_points = points.copy().astype(np.float64)
        
        # Normalización porcentual (0.0 a 1.0)
        norm_points[:, 0] = norm_points[:, 0] / img_w
        norm_points[:, 1] = norm_points[:, 1] / img_h
        
        # Extracción de vectores X e Y
        xs = norm_points[:, 0]
        ys = norm_points[:, 1]
        
        # Cálculo de la Caja Delimitadora (Bounding Box Envolvente)
        x_min, x_max = np.min(xs), np.max(xs)
        y_min, y_max = np.min(ys), np.max(ys)
        
        w = x_max - x_min
        h = y_max - y_min
        x_c = x_min + (w / 2.0)
        y_c = y_min + (h / 2.0)
        
        # Formateo a 6 decimales para la cadena base
        pose_line = f"{class_id} {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f} "
        
        # Ensamblado de Keypoints con bandera de visibilidad (v=2)
        keypoints_str = " ".join([f"{x:.6f} {y:.6f} 2" for x, y in zip(xs, ys)])
        
        yolo_line = pose_line + keypoints_str + "\n"
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(yolo_line)
            
        # --- 2. EXTRACCIÓN DE LA FOTO (manteniendo proporción) ---
        max_edge = 1024
        if max(img_w, img_h) > max_edge:
            ratio = max_edge / float(max(img_w, img_h))
            new_w = int(round(img_w * ratio))
            new_h = int(round(img_h * ratio))
            img_optimized = cv2.resize(cv_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            img_optimized = cv_image
            
        cv2.imwrite(img_path, img_optimized, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            
        logger.info(f"IA info Generado exitosamente (Pose): {name_no_ext}")
        return True
        
    except Exception:
        logger.error("Error al generar los datos de IA", exc_info=True)
        return False

def split_dataset_train_val(porcentaje_train: float = 0.8) -> bool:
    """
    Ordena y distribuye las imágenes y etiquetas que se encuentren en la raíz 
    de las carpetas 'images' y 'labels' hacia las subcarpetas 'train' y 'val',
    manteniendo la paridad estricta entre el JPG y su TXT.
    """
    try:
        dataset_dir = _get_hidden_dataset_dir()
        img_dir = os.path.join(dataset_dir, "images")
        lbl_dir = os.path.join(dataset_dir, "labels")

        # 1. Crear la estructura de carpetas destino si no existen
        for sub in ['train', 'val']:
            os.makedirs(os.path.join(img_dir, sub), exist_ok=True)
            os.makedirs(os.path.join(lbl_dir, sub), exist_ok=True)

        # 2. Escanear archivos en la raíz (ignorando lo que ya esté en carpetas)
        archivos_img = [f for f in os.listdir(img_dir) 
                        if os.path.isfile(os.path.join(img_dir, f)) and f.lower().endswith(('.jpg', '.png'))]
        
        total_archivos = len(archivos_img)
        if total_archivos == 0:
            logger.warning("No se encontraron imágenes en la raíz para particionar.")
            return False

        # 3. Ordenamiento inicial y mezcla determinista
        # Se ordena alfabéticamente primero para que la semilla actúe siempre sobre la misma base
        archivos_img.sort()
        
        # Mezclamos para dar varianza al entrenamiento (Crucial para que val sea heterogéneo)
        # La semilla 42 asegura que si ocurre un error y corres el script de nuevo, el orden sea el mismo
        random.seed(42)
        random.shuffle(archivos_img)

        # 4. Cálculo del límite 80 / 20
        limite = int(total_archivos * porcentaje_train)
        archivos_train = archivos_img[:limite]
        archivos_val = archivos_img[limite:]

        # 5. Función interna de movimiento sincrónico
        def mover_lote(lista_archivos, subcarpeta):
            movidos = 0
            for archivo_img in lista_archivos:
                nombre_base = os.path.splitext(archivo_img)[0]
                archivo_txt = f"{nombre_base}.txt"

                ruta_img_origen = os.path.join(img_dir, archivo_img)
                ruta_txt_origen = os.path.join(lbl_dir, archivo_txt)

                ruta_img_destino = os.path.join(img_dir, subcarpeta, archivo_img)
                ruta_txt_destino = os.path.join(lbl_dir, subcarpeta, archivo_txt)

                # Validar la paridad: Solo movemos si existe su coordenada matemática
                if os.path.exists(ruta_txt_origen):
                    shutil.move(ruta_img_origen, ruta_img_destino)
                    shutil.move(ruta_txt_origen, ruta_txt_destino)
                    movidos += 1
                else:
                    logger.warning(f"Huérfano ignorado: {archivo_img} no tiene su TXT.")
            
            return movidos

        # 6. Ejecución
        movidos_train = mover_lote(archivos_train, 'train')
        movidos_val = mover_lote(archivos_val, 'val')

        logger.info(f"Partición exitosa. Train: {movidos_train} imágenes | Val: {movidos_val} imágenes.")
        return True

    except Exception:
        logger.error("Error al dividir el dataset en Train/Val.", exc_info=True)
        return False
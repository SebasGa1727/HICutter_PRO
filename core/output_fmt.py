import os
import cv2
import numpy as np
from PIL import Image
from utils.logger import setup_logger

logger = setup_logger(__name__)

def _calculate_proportional_size(orig_w: int, orig_h: int, target_size: int, anchor: str) -> tuple[int, int]:
    if anchor == "square":
        return target_size, target_size
    
    if anchor == "longest_edge":
        max_side = max(orig_w, orig_h)
        if max_side == 0: return orig_w, orig_h
        ratio = target_size / float(max_side)
    elif anchor == "shortest_edge":
        min_side = min(orig_w, orig_h)
        if min_side == 0: return orig_w, orig_h
        ratio = target_size / float(min_side)
    else:
        raise ValueError("El ancla debe ser 'longest_edge', 'shortest_edge' o 'square'")
    
    return int(round(orig_w * ratio)), int(round(orig_h * ratio))

def _cv2_to_pil(cv_img: np.ndarray) -> Image.Image:
    if cv_img.ndim == 3 and cv_img.shape[2] == 3:
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    else:
        rgb_img = cv_img
    return Image.fromarray(rgb_img)

def export_image(cv_image: np.ndarray, out_dir: str, base_filename: str, 
                 target_size: int, anchor: str, quality: int, dpi: int, 
                 fmt: str, sufix: str = "", subfolder_name: str = None) -> str:
    """Función unificada 'Dumb Component'. Sirve para individuales, lotes y thumbnails."""
    try:
        # Si se solicita una subcarpeta (como "Thumbnail"), la anidamos en el directorio de salida
        if subfolder_name:
            out_dir = os.path.join(out_dir, subfolder_name)
            
        os.makedirs(out_dir, exist_ok=True)

        # Procesamiento Pillow
        pil_img = _cv2_to_pil(cv_image)
        orig_w , orig_h = pil_img.size

        new_w , new_h = _calculate_proportional_size(orig_w, orig_h, target_size, anchor)

        # Reescalamos si supera los limites o si el usuario selecciono "square"
        if anchor == "square" or orig_w > target_size or orig_h > target_size:
            pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            logger.warning(f"No reescalado (Imagen original menor al target): {base_filename}")

        # Construcción del nombre final
        name, _ = os.path.splitext(base_filename)
        final_name = f"{name}{sufix}.{fmt}"
        out_path = os.path.join(out_dir, final_name)

        pil_format = "JPEG" if fmt.lower() == "jpg" else fmt.upper()
        pil_img.save(out_path, format=pil_format, quality=quality, dpi=(dpi, dpi))

        logger.info(f"Imagen exportada con éxito: {out_path}")
        return out_path
    
    except Exception as e:
        logger.error(f"Error crítico exportando: {base_filename}", exc_info=True)
        raise e
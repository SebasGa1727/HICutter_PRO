import os
import io
import img2pdf
from PIL import Image
from utils.logger import setup_logger

logger = setup_logger(__name__)

def _img_stream_generator(image_paths: list[str], quality: int, dpi: int, average_width: bool):
    '''Generador de flujo continuo de bajo consumo de RAM con normalización de anchura'''
    
    avg_w = None
    if average_width and image_paths:
        # Fast Pass: Leer anchos rápidamente sin cargar las matrices completas
        widths = []
        for p in image_paths:
            try:
                with Image.open(p) as img:
                    widths.append(img.width)
            except Exception:
                pass
        if widths:
            avg_w = int(sum(widths) / len(widths))
            logger.info(f"Ancho promedio calculado: {avg_w}px")

    for path in image_paths:
        try:
            with Image.open(path) as img: 
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                # Normalización de ancho si el usuario lo solicitó
                if avg_w and img.width != avg_w:
                    ratio = avg_w / float(img.width)
                    new_h = int(round(img.height * ratio))
                    img = img.resize((avg_w, new_h), Image.Resampling.LANCZOS)
                
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format="JPEG", quality=quality, dpi=(dpi, dpi))
                
                yield img_byte_arr.getvalue()
        except Exception as e:
            logger.error(f"Error al procesar la imagen {path} en PDF: {e}", exc_info=True)

def export_to_pdf(ordered_paths: list[str], out_path: str, quality: int, dpi: int, average_width: bool) -> str:
    '''Toma la lista de imagenes, las compila y crea el pdf utilizando I/O Streaming directo a disco'''
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        compressed_images = list(_img_stream_generator(ordered_paths, quality, dpi, average_width))
        if not compressed_images:
            raise ValueError("No se pudo procesar ninguna imagen a PDF")

        logger.info(f"Iniciando escritura de PDF en: {out_path}")
        with open(out_path, "wb") as pdf_file:
            pdf_bytes = img2pdf.convert(compressed_images)
            pdf_file.write(pdf_bytes)

        return out_path
        
    except Exception as e:
        logger.error(f"Error crítico al exportar PDF: {out_path}", exc_info=True)
        raise e
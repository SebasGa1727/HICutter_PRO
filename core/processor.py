import numpy as np
import cv2
from utils.logger import setup_logger

logger = setup_logger(__name__)

def process_perspective_crop(cv_image: np.ndarray, points: np.ndarray) -> np.ndarray:
    """ Realiza el recorte de los puntos recibidos, y retorna la imagen recortada"""
    pts = np.array(points, dtype=np.float32)
    if pts.shape[0] != 4:
        raise ValueError("Se requieren 4 puntos para el recorte de perspectiva")

    def _dist(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.linalg.norm(a - b))

    widthA = _dist(pts[2], pts[3])
    widthB = _dist(pts[1], pts[0])
    maxWidth = max(int(round(widthA)), int(round(widthB)))

    heightA = _dist(pts[1], pts[2])
    heightB = _dist(pts[0], pts[3])
    maxHeight = max(int(round(heightA)), int(round(heightB)))

    if maxWidth <= 0 or maxHeight <= 0:
        raise ValueError("Dimensiones inválidas calculadas para el recorte (ancho/alto <= 0)")

    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(pts, dst)
    warped = cv2.warpPerspective(cv_image, M, (maxWidth, maxHeight), flags=cv2.INTER_LANCZOS4)
    return warped


def rotate_image(cv_image: np.ndarray, direction_rotate: int) -> np.ndarray:
    """ Recibe la orientacion de reotacion y rota la imagen"""
    try:
        match direction_rotate:
            case "derecha":
                code = cv2.ROTATE_90_CLOCKWISE
            case "izquierda":
                code = cv2.ROTATE_90_COUNTERCLOCKWISE
            case "180":
                code = cv2.ROTATE_180
    except Exception:
        logger.error("Fallo al intentar realizar la rotacion", exc_info=True)

    return cv2.rotate(cv_image, code)

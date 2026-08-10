from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np


class PointManager:
    """Manage a small list of image points and provide ordering logic.

    This centralizes point addition/removal/reset and the `_order_points`
    heuristic that orders 4 points as top-left, top-right, bottom-right,
    bottom-left.
    """

    def __init__(self) -> None:
        self.points: List[Tuple[float, float]] = []

    def add_point(self, pt: Tuple[float, float]) -> None:
        self.points.append((float(pt[0]), float(pt[1])))

    def pop_last(self) -> Optional[Tuple[float, float]]:
        if not self.points:
            return None
        return self.points.pop()

    def reset(self) -> None:
        self.points = []

    def __len__(self) -> int:
        return len(self.points)

    def get_points(self) -> np.ndarray:
        pts = np.array(self.points, dtype=np.float32)
        if pts.shape[0] == 4:
            return self._order_points(pts)
        return pts

    def finalize_if_full(self) -> Optional[np.ndarray]:
        """If 4 points are present, order them, update internal list, and return the ordered array."""
        if len(self.points) == 4:
            pts = np.array(self.points, dtype=np.float32)
            ordered = self._order_points(pts)
            self.points = [tuple(p) for p in ordered.tolist()]
            return ordered
        return None

    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        pts = np.array(pts, dtype=np.float32)
        if pts.shape[0] != 4:
            return pts.copy()

        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # top-left  (min sum)
        rect[2] = pts[np.argmax(s)]  # bottom-right (max sum)

        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # top-right (min diff)
        rect[3] = pts[np.argmax(diff)]  # bottom-left (max diff)

        return rect
    
    def update_point(self, index: int, new_pt: Tuple[float, float]) -> None:
        """
        Actualiza las coordenadas de un punto específico.
        Fundamental para la función de arrastre (drag) de nodos existentes.
        """
        if 0 <= index < len(self.points):
            self.points[index] = (float(new_pt[0]), float(new_pt[1]))

    def set_points_from_rect(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> None:
        """
        Genera 4 puntos ordenados a partir de 2 puntos diagonales de un recuadro.
        Sobrescribe los puntos existentes.
        """
        self.reset()
        
        # Determinar limites lógicos del rectángulo matemático
        min_x = min(p1[0], p2[0])
        max_x = max(p1[0], p2[0])
        min_y = min(p1[1], p2[1])
        max_y = max(p1[1], p2[1])

        # Se añaden en orden: Top-Left, Top-Right, Bottom-Right, Bottom-Left
        self.add_point((min_x, min_y))
        self.add_point((max_x, min_y))
        self.add_point((max_x, max_y))
        self.add_point((min_x, max_y))
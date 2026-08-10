import json
import os
from typing import Dict, Any

class CanvasConfigManager:
    """
    Gestor de configuración Singleton-like para almacenar persistencia de herramientas.
    Aplica el Principio de Responsabilidad Única (SRP).
    """
    def __init__(self, filepath: str = "canvas_settings.json"):
        self.filepath = filepath
        # Valores por defecto en caso de que sea la primera vez que se ejecuta
        self.settings: Dict[str, bool] = {
            "enable_sniper": True,
            "enable_magnifier": True,
            "enable_double_click": True,
            "enable_drag_drop": True
        }
        self.load()

    def load(self) -> None:
        """Carga la configuración desde el disco si existe."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    self.settings.update(loaded_data)
            except json.JSONDecodeError:
                print("Error leyendo el JSON de configuración. Se usarán valores por defecto.")

    def save(self) -> None:
        """Vuelca el estado actual al disco."""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=4)

    def get(self, key: str) -> bool:
        return self.settings.get(key, False)

    def set(self, key: str, value: bool) -> None:
        self.settings[key] = value
        self.save() # Autoguardado al modificar cualquier valor
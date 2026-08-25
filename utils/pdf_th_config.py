import json
import os
from typing import Dict, Any
from utils.logger import setup_logger

logger = setup_logger(__name__)

class PDFConfigManager:
    """Gestor de configuración exclusivo para la exportación de PDFs y Thumbnails."""
    
    CONFIG_FILE = "pdf_settings.json"

    # Diccionario adaptado estrictamente a las opciones de tu ExportConfigPanel
    DEFAULT_CONFIG = {
        "save_options": {
            "save_route": 0,        # Index 0: Carpeta raíz, 1: Origen
            "structure": 0,         # Index 0: Crear subcarpeta, 1: Sin subcarpeta
            "manual_mode": False,   # Estado del checkbox - False: ruta por checkbox, True: ruta definida por usuario
            "path": ""              # Ruta elegida
        },
        "export_pdf": {
            "dpi": 150,             # Valor del SpinBox
            "quality": 75,          # Valor del SpinBox
            "average_width": False  # Estado del CheckBox
        },
        "export_th": {
            "enabled": True,        # Estado del CheckBox maestro de TH
            "format": 0,            # Index 0: jpg, 1: png
            "dpi": 72,
            "quality": 60,
            "size": 500,
            "size_side": 0,         # Index 0: Lado largo, 1: Lado corto, 2: Cuadrado
            "save_route": 0         # Index 0: Misma que PDF, 1: Raíz
        }
    }

    def __init__(self) -> None:
        self.config: Dict[str, Any] = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Carga el archivo JSON, si no existe, lo crea con la configuracion base"""
        if not os.path.exists(self.CONFIG_FILE):
            return self._create_default_config()
        try:
            with open(self.CONFIG_FILE, 'r', encoding='UTF-8') as file:
                data = json.load(file)
                data_backup = self.DEFAULT_CONFIG.copy()
                data_backup.update(data)
                return data_backup
        except Exception:
            logger.warning("Error al codificar json de PDF", exc_info=True)
            return self.DEFAULT_CONFIG.copy()
        
    def _create_default_config(self) -> Dict[str, Any]:
        default_data = self.DEFAULT_CONFIG.copy()
        self._save_to_disk(default_data)
        return default_data
    
    def _save_to_disk(self, data:Dict[str, Any]) -> None:
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
        except Exception:
            logger.error("Error al guardar la configuracion de PDF", exc_info=True)
        
    def get(self, category:str, key:str) -> Any:
        return self.config.get(category, {}).get(key, self.DEFAULT_CONFIG.get(category, {}).get(key))
    
    def set(self, category:str, key:str, value:Any) -> None:
        if category not in self.config:
            self.config[category] = {}
        self.config[category][key] = value
        self._save_to_disk(self.config)

# Instancia global para importar en las vistas
config_manager = PDFConfigManager()
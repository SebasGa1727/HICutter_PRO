import json
import os
from typing import Dict, Any
from utils.logger import setup_logger

logger = setup_logger(__name__)

class BatchConfigManager:
    """Gestor de configuración exclusivo para la vista de Recorte (Converter Setup)."""
    
    CONFIG_FILE = "setup_batch_settings.json"

    DEFAULT_CONFIG = {
        "export_config": {
            "check_subfolders": False,      # Estado booleano
            "format": 0,                    # Index 0: jpg, 1: png
            "quality": 80,
            "dpi": 96,
            "size": 3000,
            "size_side": 0,                 # Index 0: Lado largo, 1: Lado corto, 2: Cuadrado
        },
        "save_config": {
            "last_input_route": "",
            "save_mode": 0,                 # Index 0: sobreescribir, 1: imagen con sufijo, 2: nueva ruta
            "route": "",                    # Guarda la ruta de guardardado en caso de que save_mode sea 2
            "sufix": "",
        }
    }

    def __init__(self) -> None:
        self.config: Dict[str, Any] = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.CONFIG_FILE):
            return self._create_default_config()
        try:
            with open(self.CONFIG_FILE, 'r', encoding='UTF-8') as file:
                data = json.load(file)
                data_backup = self.DEFAULT_CONFIG.copy()
                data_backup.update(data)
                return data_backup
        except Exception:
            logger.warning("Error al codificar json de Setup", exc_info=True)
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
            logger.error("Error al guardar la configuracion de Setup", exc_info=True)
        
    def get(self, category:str, key:str) -> Any:
        return self.config.get(category, {}).get(key, self.DEFAULT_CONFIG.get(category, {}).get(key))
    
    def set(self, category:str, key:str, value:Any) -> None:
        if category not in self.config:
            self.config[category] = {}
        self.config[category][key] = value
        self._save_to_disk(self.config)

# Instancia global
config_manager = BatchConfigManager()
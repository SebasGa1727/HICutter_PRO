import json

class FilterRegistry:
    """Gestor de memoria hiper-ligero para configuraciones de filtros"""
    _active_filters = {}
    _next_id = 1

    @classmethod
    def register_filter(cls, filter_data: dict) -> int:
        """Recibe un diccionario, lo evalúa y retorna un ID único. No duplica datos."""
        if not filter_data:
            return 0    # 0 = Sin filtro
            
        # Convertimos el dict en un string ordenado para generar un Hash inmutable y rápido
        filter_hash = hash(json.dumps(filter_data, sort_keys=True))
        
        if filter_hash not in cls._active_filters:
            cls._active_filters[filter_hash] = {
                "id": cls._next_id,
                "data": filter_data,
            }
            cls._next_id += 1
            
        return cls._active_filters[filter_hash]["id"]

    @classmethod
    def get_filter_by_id(cls, filter_id: int) -> dict:
        """Recupera la configuración técnica para el motor de renderizado."""
        for f in cls._active_filters.values():
            if f["id"] == filter_id:
                return f["data"]
        return {}

    @classmethod
    def clear_memory(cls):
        """Se llamará al terminar la conversión en el main.py para purgar la RAM"""
        cls._active_filters.clear()
        cls._next_id = 1
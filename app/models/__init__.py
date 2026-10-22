"""Modelos (capa M del patrón MVC)."""
from app.models.inconsistencia import Inconsistencia
from app.models.muestra import Muestra
from app.models.sondaje import Sondaje

__all__ = ["Sondaje", "Muestra", "Inconsistencia"]

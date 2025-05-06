# handlers/__init__.py

from .feeding import router as feeding_router
from .polts import router as plots_router
from .sleep import router as sleep_router
from .start import router as start_router
from .stats import router as stats_router

__all__ = ["sleep_router", "feeding_router", "stats_router", "start_router", "plots_router"]

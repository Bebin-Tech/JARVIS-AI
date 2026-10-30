import platform

import psutil
from fastapi import APIRouter

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("")
def system_info():
    memory = psutil.virtual_memory()
    return {
        "platform": platform.system(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "ram_percent": memory.percent,
        "ram_available_gb": round(memory.available / 1024**3, 2),
        "ram_total_gb": round(memory.total / 1024**3, 2),
    }

"""Run from the repository root with python -m backend.run."""

import uvicorn

from backend.app.config import Settings

if __name__ == "__main__":
    config = Settings()
    uvicorn.run(
        "backend.app.main:app", host=config.host, port=config.port, ws_max_size=4096, ws_max_queue=8
    )

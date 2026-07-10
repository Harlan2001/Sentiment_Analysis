import os
from backend.app import app
from backend.common.logging_config import get_uvicorn_log_config

if __name__ == "__main__":
    import uvicorn

    reload = os.getenv("UVICORN_RELOAD", "").lower() in ("1", "true", "yes")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=reload,
        log_config=get_uvicorn_log_config(),
    )

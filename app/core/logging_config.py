import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

_log_file_path: Optional[Path] = None

class EndpointFilter(logging.Filter):
    """
    Filters out frequent health checks and polling requests to keep logs clean.
    """
    def __init__(self, excluded_substrings: Optional[list] = None):
        super().__init__()
        self.excluded = excluded_substrings or [
            "/api/health",
            "/system_stats",
            "/api/system_stats"
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(sub in msg for sub in self.excluded)


def setup_logging(project_root: Optional[Path] = None) -> Path:
    """
    Configures application-wide logging writing to both standard console
    and a timestamped log file in the `logs/` directory at the project root.
    """
    global _log_file_path
    if _log_file_path is not None:
        return _log_file_path

    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent.parent

    logs_dir = project_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"balladeer_{timestamp_str}.log"
    _log_file_path = log_file

    log_format = "%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s]: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(log_format, datefmt=date_format)
    endpoint_filter = EndpointFilter()

    # Root logger configured to DEBUG so full debug traces are available
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 1. Console Handler (stdout) with safe encoding
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_level = logging.DEBUG if os.getenv("BALLADEER_DEBUG", "").lower() in ("1", "true") else logging.INFO
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(endpoint_filter)
    root_logger.addHandler(console_handler)

    # 2. File Handler (timestamped utf-8) captures full DEBUG logs
    file_handler = logging.FileHandler(str(log_file), mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(endpoint_filter)
    root_logger.addHandler(file_handler)

    # 3. Configure uvicorn access and httpx loggers
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.addFilter(endpoint_filter)

    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.addFilter(endpoint_filter)

    httpx_logger = logging.getLogger("httpx")
    httpx_logger.addFilter(endpoint_filter)

    # 4. Silence noisy third-party internal debug loggers (e.g. numba JIT compiler, llvmlite, matplotlib)
    noisy_loggers = [
        "numba",
        "numba.core",
        "llvmlite",
        "matplotlib",
        "PIL",
        "urllib3",
        "filelock",
        "asyncio",
        "torch.distributed"
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    root_logger.info("=" * 70)
    root_logger.info(f"   Balladeer Logging Session Started at {datetime.now().isoformat()}")
    root_logger.info(f"   Log File: {log_file.resolve()} (Level: DEBUG)")
    root_logger.info(f"   Console Level: {logging.getLevelName(console_level)}")
    root_logger.info("=" * 70)

    return log_file

def get_current_log_file() -> Optional[Path]:
    return _log_file_path

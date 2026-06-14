import sys

from loguru import logger

logger.remove()
logger.add(
    sys.stderr,
    format="{time:ISO8601} | {level} | {extra[run_id]} | {message}",
    serialize=False,
    level="INFO",
)


def get_run_logger(run_id: str):
    return logger.bind(run_id=run_id)


# Default logger bound to no run (for startup/shutdown logs)
app_logger = logger.bind(run_id="system")

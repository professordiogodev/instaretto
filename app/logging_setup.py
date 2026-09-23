import logging
import os
from logging.handlers import TimedRotatingFileHandler


def configure_logging(app):
    log_dir = app.config["LOG_DIR"]
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")

    # Rotates at midnight; rotated files are suffixed app.log.YYYY-MM-DD.
    # The active file is always plain "app.log" -- scripts/ship_logs.sh
    # relies on that to know which file is still being written to.
    handler = TimedRotatingFileHandler(
        log_path, when="midnight", backupCount=0, utc=True
    )
    handler.suffix = "%Y-%m-%d"
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )

    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(handler)

    # Also log to stdout so `docker logs` / `docker compose logs` still work.
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    app.logger.addHandler(stream_handler)

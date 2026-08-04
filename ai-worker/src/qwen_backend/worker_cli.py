from __future__ import annotations

import argparse
import logging
from pathlib import Path

import anyio
from dotenv import load_dotenv
from pydantic import ValidationError

from qwen_backend.worker_settings import NotebookWorkerSettings

logger = logging.getLogger(__name__)


def parser() -> argparse.ArgumentParser:
    """Build the notebook worker command-line parser."""

    command_parser = argparse.ArgumentParser(
        description="Run the notebook-hosted EyesOnU AI Worker against the central server."
    )
    command_parser.add_argument(
        "--once",
        action="store_true",
        help="Consume at most one RabbitMQ job and exit.",
    )
    command_parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional dotenv file to load before worker settings and model initialization.",
    )
    command_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return command_parser


def load_worker_env_file(env_file: Path | None) -> None:
    """Load an explicitly supplied dotenv file before parsing worker settings."""

    if env_file is None:
        return
    if not env_file.is_file():
        raise ValueError(f"AI Worker environment file does not exist: {env_file}")
    load_dotenv(env_file, override=False)


def main() -> int:
    """Run the notebook Worker with a bounded startup-error surface."""

    from qwen_backend.notebook_worker import NotebookWorker

    args = parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        load_worker_env_file(args.env_file)
        settings = NotebookWorkerSettings()  # pyright: ignore[reportCallIssue]
        worker = NotebookWorker(settings)
        if args.once:
            anyio.run(worker.run_once)
        else:
            anyio.run(worker.run_forever)
    except KeyboardInterrupt:
        logger.info("AI Worker stopped by operator")
    except (OSError, ValidationError, ValueError) as exception:
        logger.error("AI Worker startup failed: %s", exception)
        return 2
    return 0

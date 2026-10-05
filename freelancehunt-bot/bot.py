"""Freelancehunt → Telegram monitor.

    python bot.py              # loop, every check_interval_seconds
    python bot.py --once       # one check (for cron / Task Scheduler)
    python bot.py --dry-run    # print matches to the console, nothing is sent or saved
"""

import argparse
import logging
import logging.handlers
import os
import sys
import time

from fh_monitor.config import ConfigError, load_config
from fh_monitor.filters import ProjectFilter
from fh_monitor.freelancehunt import FreelancehuntClient
from fh_monitor.monitor import Monitor
from fh_monitor.storage import SeenStorage
from fh_monitor.telegram import TelegramClient

log = logging.getLogger("fh_monitor")


class RedactSecrets(logging.Filter):
    """Last line of defence: tokens never reach the console or the log file."""

    def __init__(self, secrets):
        super().__init__()
        self._secrets = [s for s in secrets if s]

    def filter(self, record):
        message = record.getMessage()
        for secret in self._secrets:
            message = message.replace(secret, "***")
        record.msg, record.args = message, None
        return True


def setup_logging(log_file, secrets, verbose):
    handlers = [logging.StreamHandler()]
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        )
    redact = RedactSecrets(secrets)
    for handler in handlers:
        handler.addFilter(redact)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Freelancehunt → Telegram monitor")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--once", action="store_true", help="одна перевірка і вихід")
    parser.add_argument("--dry-run", action="store_true", help="показати збіги в консолі, нічого не надсилати")
    parser.add_argument("--verbose", action="store_true", help="писати причину пропуску кожного проєкту")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config, require_telegram=not args.dry_run)
    except ConfigError as e:
        print(f"Помилка конфігурації: {e}", file=sys.stderr)
        return 2

    setup_logging(None if args.dry_run else config.log_file, config.secrets, args.verbose)

    storage = SeenStorage(None if args.dry_run else config.state_file)
    monitor = Monitor(
        freelancehunt=FreelancehuntClient(config.freelancehunt_token),
        project_filter=ProjectFilter(
            config.keywords, config.stop_words, config.skip_employers, config.skip_personal
        ),
        storage=storage,
        telegram=None if args.dry_run else TelegramClient(config.telegram_bot_token, config.telegram_chat_id),
        max_pages=config.max_pages_per_check,
        first_run_limit=config.first_run_limit,
        skill_ids=config.skill_ids,
    )

    if args.dry_run:
        storage.initialized = True  # show every match from the last pages, not the first-run limit
        monitor.check()
        return 0

    log.info("Бот запущено. Інтервал перевірки: %d с.", config.check_interval_seconds)
    while True:
        try:
            monitor.check()
        except Exception:
            log.exception("Неочікувана помилка під час перевірки, продовжую роботу.")
        if args.once:
            return 0
        time.sleep(config.check_interval_seconds)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.info("Зупинено користувачем.")

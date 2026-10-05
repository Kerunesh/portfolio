"""Loading and validating config.json. Secrets can be overridden by environment variables."""

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

ENV_FH_TOKEN = "FH_TOKEN"
ENV_TELEGRAM_TOKEN = "TELEGRAM_BOT_TOKEN"
ENV_TELEGRAM_CHAT_ID = "TELEGRAM_CHAT_ID"

PLACEHOLDER_PREFIX = "YOUR_"


class ConfigError(Exception):
    pass


@dataclass
class Config:
    telegram_bot_token: str
    telegram_chat_id: str
    freelancehunt_token: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    stop_words: List[str] = field(default_factory=list)
    skip_employers: List[str] = field(default_factory=list)
    skill_ids: List[int] = field(default_factory=list)
    skip_personal: bool = True
    check_interval_seconds: int = 300
    max_pages_per_check: int = 3
    first_run_limit: int = 3
    state_file: str = "data/state.json"
    log_file: str = "logs/bot.log"

    @property
    def secrets(self) -> List[str]:
        return [s for s in (self.telegram_bot_token, self.freelancehunt_token) if s]


def _is_set(value: Optional[str]) -> bool:
    return bool(value) and not str(value).startswith(PLACEHOLDER_PREFIX)


def load_config(path: str, require_telegram: bool = True) -> Config:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raise ConfigError(
            f"Не знайдено {path}. Скопіюйте config.example.json у config.json і впишіть свої дані."
        )
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path}: помилка JSON у рядку {e.lineno}: {e.msg}")

    raw["telegram_bot_token"] = os.environ.get(ENV_TELEGRAM_TOKEN) or raw.get("telegram_bot_token", "")
    raw["telegram_chat_id"] = os.environ.get(ENV_TELEGRAM_CHAT_ID) or str(raw.get("telegram_chat_id", ""))
    raw["freelancehunt_token"] = os.environ.get(ENV_FH_TOKEN) or raw.get("freelancehunt_token")

    known = set(Config.__dataclass_fields__)
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ConfigError(f"Невідомі параметри у {path}: {', '.join(unknown)}")

    config = Config(**raw)
    if not _is_set(config.freelancehunt_token):
        config.freelancehunt_token = None

    if require_telegram:
        if not _is_set(config.telegram_bot_token):
            raise ConfigError("Не вказано telegram_bot_token (config.json або змінна TELEGRAM_BOT_TOKEN).")
        if not _is_set(config.telegram_chat_id):
            raise ConfigError("Не вказано telegram_chat_id (config.json або змінна TELEGRAM_CHAT_ID).")
    if not config.keywords:
        raise ConfigError("Список keywords порожній: бот не пропустить жодного проєкту.")
    if config.check_interval_seconds < 60:
        raise ConfigError("check_interval_seconds має бути не менше 60.")
    if config.max_pages_per_check < 1:
        raise ConfigError("max_pages_per_check має бути не менше 1.")
    return config
